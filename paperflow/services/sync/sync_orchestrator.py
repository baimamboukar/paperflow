"""
Sync orchestration service for Paperflow.

This service manages the complete workflow: Overleaf → GitHub → Build → Deploy.
It coordinates between different sync services and provides a unified interface
for synchronization operations.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable

from paperflow.config.settings import Settings
from paperflow.models.project import Project
from paperflow.models.sync import (
    SyncConfiguration, SyncResult, SyncStatus, SyncOperationType,
    SyncTrigger, SyncPriority, SyncQueue, SyncProgress, SyncStage,
    SyncConflict, ConflictResolution, WebhookSyncTrigger,
    ScheduledSyncConfig, SyncNotification
)
from paperflow.services.base import BaseService, SyncServiceInterface
from paperflow.services.project_service import ProjectService
from paperflow.services.sync.overleaf_sync import OverleafSync
from paperflow.services.sync.github_sync import GitHubSyncService
from paperflow.services.sync.build_sync import BuildSync
from paperflow.services.sync.deploy_sync import DeploySync
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


class SyncOrchestrator(BaseService, SyncServiceInterface):
    """
    Main synchronization orchestrator.
    
    Coordinates the complete sync workflow across all services and provides
    queue management, progress tracking, and error handling.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize sync orchestrator."""
        super().__init__(settings)
        
        # Service dependencies
        self.project_service: Optional[ProjectService] = None
        self.overleaf_sync: Optional[OverleafSync] = None
        self.github_sync: Optional[GitHubSyncService] = None
        self.build_sync: Optional[BuildSync] = None
        self.deploy_sync: Optional[DeploySync] = None
        
        # Queue and state management
        self.sync_queue = SyncQueue()
        self.active_syncs: Dict[str, SyncResult] = {}
        self.sync_locks: Set[str] = set()  # Project locks to prevent concurrent syncs
        
        # Configuration
        self.default_config = SyncConfiguration()
        self.scheduled_syncs: Dict[str, ScheduledSyncConfig] = {}
        
        # Event handlers and notifications
        self.sync_start_handlers: List[Callable] = []
        self.sync_complete_handlers: List[Callable] = []
        self.conflict_handlers: List[Callable] = []
        self.notification_service: Optional[SyncNotification] = None
        
        # Background tasks
        self._queue_processor_task: Optional[asyncio.Task] = None
        self._scheduler_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
    
    def _perform_initialization(self) -> None:
        """Perform service-specific initialization."""
        logger.info("Initializing SyncOrchestrator")
        
        # Initialize child services
        self.project_service = ProjectService(self.settings)
        self.overleaf_sync = OverleafSync(self.settings)
        self.github_sync = GitHubSyncService(self.settings)
        self.build_sync = BuildSync(self.settings)
        self.deploy_sync = DeploySync(self.settings)
        
        # Initialize child services
        if self.settings:
            for service in [
                self.project_service, self.overleaf_sync, self.github_sync,
                self.build_sync, self.deploy_sync
            ]:
                if service:
                    service.initialize(self.settings)
        
        # Start background tasks
        self._start_background_tasks()
        
        logger.info("SyncOrchestrator initialized successfully")
    
    def _perform_cleanup(self) -> None:
        """Perform service cleanup."""
        logger.info("Cleaning up SyncOrchestrator")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel background tasks
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
        if self._scheduler_task:
            self._scheduler_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # Cleanup child services
        for service in [
            self.project_service, self.overleaf_sync, self.github_sync,
            self.build_sync, self.deploy_sync
        ]:
            if service:
                service.cleanup()
        
        logger.info("SyncOrchestrator cleanup completed")
    
    def _start_background_tasks(self) -> None:
        """Start background processing tasks."""
        self._queue_processor_task = asyncio.create_task(self._process_sync_queue())
        self._scheduler_task = asyncio.create_task(self._process_scheduled_syncs())
        self._cleanup_task = asyncio.create_task(self._cleanup_completed_syncs())
    
    # Public API Methods
    
    async def sync_project(
        self,
        project: Project,
        sync_type: SyncOperationType = SyncOperationType.FULL_SYNC,
        trigger: SyncTrigger = SyncTrigger.MANUAL,
        priority: SyncPriority = SyncPriority.NORMAL,
        configuration: Optional[SyncConfiguration] = None,
        triggered_by_user: Optional[str] = None,
        webhook_data: Optional[WebhookSyncTrigger] = None
    ) -> SyncResult:
        """
        Initiate a sync operation for a project.
        
        Args:
            project: Project to sync
            sync_type: Type of sync operation
            trigger: What triggered the sync
            priority: Operation priority
            configuration: Custom sync configuration
            triggered_by_user: User who triggered the sync
            webhook_data: Webhook trigger data if applicable
            
        Returns:
            SyncResult with operation details
        """
        # Check if project is already being synced
        if project.name in self.sync_locks:
            raise ValueError(f"Project '{project.name}' is already being synced")
        
        # Create sync operation
        operation_id = str(uuid.uuid4())
        sync_config = configuration or self.default_config
        
        sync_result = SyncResult(
            operation_id=operation_id,
            operation_type=sync_type,
            trigger=trigger,
            priority=priority,
            configuration=sync_config,
            triggered_by_user=triggered_by_user,
            overleaf_repo_url=getattr(project, 'overleaf_url', None),
            github_repo_url=getattr(project, 'github_url', None)
        )
        
        if webhook_data:
            sync_result.webhook_delivery_id = webhook_data.webhook_id
        
        # Add to queue
        if not self.sync_queue.add_operation(sync_result):
            raise RuntimeError("Sync queue is full")
        
        # Store project reference
        self.active_syncs[operation_id] = sync_result
        
        logger.info(
            f"Queued sync operation {operation_id} for project '{project.name}' "
            f"(type: {sync_type.value}, trigger: {trigger.value})"
        )
        
        return sync_result
    
    async def check_sync_status(self, project: Project) -> Dict[str, Any]:
        """
        Check synchronization status for a project.
        
        Args:
            project: Project to check
            
        Returns:
            Dictionary with sync status information
        """
        status_info = {
            "project_name": project.name,
            "is_syncing": project.name in self.sync_locks,
            "last_sync": project.last_sync,
            "pending_operations": [],
            "active_operations": [],
            "recent_operations": []
        }
        
        # Find operations for this project
        project_ops = []
        for operation in (
            self.sync_queue.pending_operations + 
            self.sync_queue.active_operations + 
            self.sync_queue.completed_operations[-10:]  # Last 10 completed
        ):
            # Check if operation belongs to this project
            # (We would need to store project reference in SyncResult)
            project_ops.append(operation)
        
        # Categorize operations
        for op in project_ops:
            op_summary = op.get_summary()
            if op.status == SyncStatus.PENDING:
                status_info["pending_operations"].append(op_summary)
            elif op.status == SyncStatus.IN_PROGRESS:
                status_info["active_operations"].append(op_summary)
            else:
                status_info["recent_operations"].append(op_summary)
        
        return status_info
    
    async def resolve_conflicts(
        self,
        project: Project,
        resolution: ConflictResolution,
        file_paths: Optional[List[str]] = None
    ) -> None:
        """
        Resolve synchronization conflicts.
        
        Args:
            project: Project with conflicts
            resolution: Resolution strategy
            file_paths: Specific files to resolve (None for all)
        """
        # Find active sync operation for this project
        operation = None
        for sync_result in self.active_syncs.values():
            if sync_result.status == SyncStatus.CONFLICT:
                # Would need project reference to match
                operation = sync_result
                break
        
        if not operation:
            raise ValueError(f"No conflicted sync operation found for project '{project.name}'")
        
        # Resolve conflicts
        if file_paths:
            for file_path in file_paths:
                operation.resolve_conflict(file_path, resolution)
        else:
            # Resolve all conflicts
            for conflict in operation.conflicts:
                if not conflict.resolution:
                    conflict.resolution = resolution
                    conflict.resolved_at = datetime.now()
                    operation.metrics.conflicts_resolved += 1
        
        # If all conflicts resolved, continue sync
        if not operation.has_unresolved_conflicts():
            operation.status = SyncStatus.IN_PROGRESS
            logger.info(f"All conflicts resolved for operation {operation.operation_id}")
    
    async def cancel_sync(self, operation_id: str) -> bool:
        """
        Cancel a sync operation.
        
        Args:
            operation_id: ID of operation to cancel
            
        Returns:
            True if cancelled successfully
        """
        # Try to cancel from queue
        if self.sync_queue.cancel_operation(operation_id):
            self.active_syncs.pop(operation_id, None)
            logger.info(f"Cancelled sync operation {operation_id}")
            return True
        
        # If it's currently running, mark for cancellation
        if operation_id in self.active_syncs:
            operation = self.active_syncs[operation_id]
            operation.status = SyncStatus.CANCELLED
            logger.info(f"Marked running sync operation {operation_id} for cancellation")
            return True
        
        return False
    
    async def get_sync_history(
        self,
        project: Optional[Project] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get sync operation history.
        
        Args:
            project: Filter by project (None for all)
            limit: Maximum number of results
            
        Returns:
            List of sync operation summaries
        """
        operations = self.sync_queue.completed_operations[-limit:]
        
        # Filter by project if specified
        if project:
            # Would need project reference in SyncResult to filter properly
            pass
        
        return [op.get_summary() for op in reversed(operations)]
    
    # Queue Processing
    
    async def _process_sync_queue(self) -> None:
        """Background task to process sync queue."""
        logger.info("Started sync queue processor")
        
        while not self._shutdown_event.is_set():
            try:
                # Get next operation
                operation = self.sync_queue.get_next_operation()
                
                if operation:
                    # Process operation in background
                    asyncio.create_task(self._execute_sync_operation(operation))
                else:
                    # Wait a bit before checking again
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in sync queue processor: {e}")
                await asyncio.sleep(5)
        
        logger.info("Sync queue processor stopped")
    
    async def _execute_sync_operation(self, operation: SyncResult) -> None:
        """
        Execute a sync operation.
        
        Args:
            operation: Sync operation to execute
        """
        logger.info(f"Starting sync operation {operation.operation_id}")
        
        try:
            # Acquire project lock
            project_name = operation.operation_id  # Would need actual project name
            self.sync_locks.add(project_name)
            
            # Mark as started
            operation.mark_started()
            
            # Notify handlers
            await self._notify_sync_start(operation)
            
            # Execute sync stages based on operation type
            await self._execute_sync_stages(operation)
            
            # Mark as completed
            operation.mark_completed(success=True)
            
            logger.info(f"Completed sync operation {operation.operation_id}")
            
        except Exception as e:
            # Mark as failed
            operation.mark_completed(success=False, error=str(e))
            logger.error(f"Sync operation {operation.operation_id} failed: {e}")
            
        finally:
            # Release project lock
            project_name = operation.operation_id  # Would need actual project name
            self.sync_locks.discard(project_name)
            
            # Move to completed queue
            self.sync_queue.complete_operation(operation.operation_id)
            self.active_syncs.pop(operation.operation_id, None)
            
            # Notify handlers
            await self._notify_sync_complete(operation)
    
    async def _execute_sync_stages(self, operation: SyncResult) -> None:
        """
        Execute the sync stages based on operation type.
        
        Args:
            operation: Sync operation to execute
        """
        sync_type = operation.operation_type
        
        try:
            if sync_type in [SyncOperationType.FULL_SYNC, SyncOperationType.PULL_ONLY]:
                await self._stage_pull_overleaf(operation)
            
            if sync_type in [SyncOperationType.FULL_SYNC, SyncOperationType.PUSH_ONLY]:
                await self._stage_push_github(operation)
            
            if sync_type in [SyncOperationType.FULL_SYNC, SyncOperationType.BUILD_ONLY]:
                await self._stage_build_project(operation)
            
            if sync_type in [SyncOperationType.FULL_SYNC, SyncOperationType.DEPLOY_ONLY]:
                await self._stage_deploy_project(operation)
                
        except Exception as e:
            logger.error(f"Error in sync stage execution: {e}")
            raise
    
    async def _stage_pull_overleaf(self, operation: SyncResult) -> None:
        """Pull changes from Overleaf."""
        operation.progress.stage = SyncStage.PULLING_OVERLEAF
        operation.progress.update_progress("Pulling from Overleaf", 1, 4)
        
        if not self.overleaf_sync:
            raise RuntimeError("Overleaf sync service not available")
        
        # Execute Overleaf pull
        # This would call the actual Overleaf sync service
        logger.info(f"Pulling from Overleaf for operation {operation.operation_id}")
        
        # Simulate some work
        await asyncio.sleep(2)
        operation.metrics.files_pulled = 5
    
    async def _stage_push_github(self, operation: SyncResult) -> None:
        """Push changes to GitHub."""
        operation.progress.stage = SyncStage.PUSHING_GITHUB
        operation.progress.update_progress("Pushing to GitHub", 2, 4)
        
        if not self.github_sync:
            raise RuntimeError("GitHub sync service not available")
        
        # Execute GitHub push
        logger.info(f"Pushing to GitHub for operation {operation.operation_id}")
        
        # Simulate some work
        await asyncio.sleep(1)
        operation.metrics.files_pushed = 5
    
    async def _stage_build_project(self, operation: SyncResult) -> None:
        """Build project (LaTeX to HTML)."""
        operation.progress.stage = SyncStage.BUILDING
        operation.progress.update_progress("Building project", 3, 4)
        
        if not self.build_sync:
            raise RuntimeError("Build sync service not available")
        
        # Execute build
        logger.info(f"Building project for operation {operation.operation_id}")
        
        build_start = datetime.now()
        
        # Simulate build process
        await asyncio.sleep(3)
        
        build_end = datetime.now()
        operation.metrics.build_time_seconds = (build_end - build_start).total_seconds()
        operation.build_artifacts = ["index.html", "assets/style.css", "assets/script.js"]
    
    async def _stage_deploy_project(self, operation: SyncResult) -> None:
        """Deploy project to GitHub Pages."""
        operation.progress.stage = SyncStage.DEPLOYING
        operation.progress.update_progress("Deploying to GitHub Pages", 4, 4)
        
        if not self.deploy_sync:
            raise RuntimeError("Deploy sync service not available")
        
        # Execute deployment
        logger.info(f"Deploying project for operation {operation.operation_id}")
        
        deploy_start = datetime.now()
        
        # Simulate deployment
        await asyncio.sleep(2)
        
        deploy_end = datetime.now()
        operation.metrics.deploy_time_seconds = (deploy_end - deploy_start).total_seconds()
        operation.deployment_url = "https://username.github.io/repository"
        operation.deployment_status = "deployed"
    
    # Scheduled Sync Processing
    
    async def _process_scheduled_syncs(self) -> None:
        """Background task to process scheduled syncs."""
        logger.info("Started scheduled sync processor")
        
        while not self._shutdown_event.is_set():
            try:
                current_time = datetime.now()
                
                for config in self.scheduled_syncs.values():
                    if (
                        config.enabled and 
                        config.next_run and 
                        current_time >= config.next_run
                    ):
                        await self._execute_scheduled_sync(config)
                
                # Check every minute
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in scheduled sync processor: {e}")
                await asyncio.sleep(60)
        
        logger.info("Scheduled sync processor stopped")
    
    async def _execute_scheduled_sync(self, config: ScheduledSyncConfig) -> None:
        """Execute a scheduled sync."""
        logger.info(f"Executing scheduled sync for project {config.project_id}")
        
        try:
            # Load project (would need actual project loading)
            # project = await self.project_service.load_project_by_id(config.project_id)
            # 
            # # Start sync
            # await self.sync_project(
            #     project=project,
            #     sync_type=config.sync_type,
            #     trigger=SyncTrigger.SCHEDULED,
            #     configuration=config.configuration
            # )
            
            # Update last run time
            config.last_run = datetime.now()
            # Calculate next run time based on cron expression
            # config.next_run = calculate_next_run(config.cron_expression)
            
        except Exception as e:
            logger.error(f"Failed to execute scheduled sync for {config.project_id}: {e}")
    
    # Cleanup
    
    async def _cleanup_completed_syncs(self) -> None:
        """Background task to clean up old completed syncs."""
        logger.info("Started cleanup task")
        
        while not self._shutdown_event.is_set():
            try:
                # Clean up old completed operations (keep last 1000)
                if len(self.sync_queue.completed_operations) > 1000:
                    self.sync_queue.completed_operations = (
                        self.sync_queue.completed_operations[-500:]
                    )
                
                # Run cleanup every hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(3600)
        
        logger.info("Cleanup task stopped")
    
    # Event Handling and Notifications
    
    async def _notify_sync_start(self, operation: SyncResult) -> None:
        """Notify handlers that sync started."""
        for handler in self.sync_start_handlers:
            try:
                await handler(operation)
            except Exception as e:
                logger.error(f"Error in sync start handler: {e}")
    
    async def _notify_sync_complete(self, operation: SyncResult) -> None:
        """Notify handlers that sync completed."""
        for handler in self.sync_complete_handlers:
            try:
                await handler(operation)
            except Exception as e:
                logger.error(f"Error in sync complete handler: {e}")
        
        # Send notifications if configured
        if self.notification_service:
            await self._send_notification(operation)
    
    async def _send_notification(self, operation: SyncResult) -> None:
        """Send notification about sync operation."""
        if not self.notification_service or not self.notification_service.enabled:
            return
        
        should_notify = (
            (operation.success and self.notification_service.notify_on_success) or
            (not operation.success and self.notification_service.notify_on_failure) or
            (operation.has_unresolved_conflicts() and self.notification_service.notify_on_conflicts) or
            (operation.warnings and self.notification_service.notify_on_warnings)
        )
        
        if should_notify:
            logger.info(f"Sending notification for operation {operation.operation_id}")
            # Implementation would send actual notifications
    
    # Public Configuration Methods
    
    def add_sync_start_handler(self, handler: Callable) -> None:
        """Add handler for sync start events."""
        self.sync_start_handlers.append(handler)
    
    def add_sync_complete_handler(self, handler: Callable) -> None:
        """Add handler for sync complete events."""
        self.sync_complete_handlers.append(handler)
    
    def set_notification_service(self, notification: SyncNotification) -> None:
        """Set notification configuration."""
        self.notification_service = notification
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return self.sync_queue.get_queue_stats()
    
    def get_active_operations(self) -> List[Dict[str, Any]]:
        """Get currently active operations."""
        return [op.get_summary() for op in self.sync_queue.active_operations]