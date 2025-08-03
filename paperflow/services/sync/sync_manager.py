"""
Sync Manager for Paperflow.

This module provides a unified interface for managing all sync services
and coordinates their interactions.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from paperflow.config.settings import Settings
from paperflow.models.project import Project
from paperflow.models.sync import (
    SyncResult, SyncOperationType, SyncTrigger, SyncPriority,
    SyncConfiguration, WebhookSyncTrigger
)
from paperflow.services.base import BaseService, ServiceManager
from paperflow.services.project_service import ProjectService
from paperflow.services.sync.sync_orchestrator import SyncOrchestrator
from paperflow.services.sync.overleaf_sync import OverleafSync
from paperflow.services.sync.github_sync import GitHubSyncService
from paperflow.services.sync.build_sync import BuildSync
from paperflow.services.sync.deploy_sync import DeploySync
from paperflow.services.sync.websocket_sync import WebSocketSyncService
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


class SyncManager(BaseService):
    """
    Unified sync service manager.
    
    Coordinates all sync services and provides a single interface
    for sync operations across the Paperflow ecosystem.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize sync manager."""
        super().__init__(settings)
        
        # Core services
        self.service_manager = ServiceManager()
        self.project_service: Optional[ProjectService] = None
        
        # Sync services
        self.orchestrator: Optional[SyncOrchestrator] = None
        self.overleaf_sync: Optional[OverleafSync] = None
        self.github_sync: Optional[GitHubSyncService] = None
        self.build_sync: Optional[BuildSync] = None
        self.deploy_sync: Optional[DeploySync] = None
        self.websocket_sync: Optional[WebSocketSyncService] = None
        
        # Event integration
        self._event_handlers_registered = False
    
    def _perform_initialization(self) -> None:
        """Perform service-specific initialization."""
        logger.info("Initializing SyncManager")
        
        # Initialize project service
        self.project_service = ProjectService(self.settings)
        
        # Initialize sync services
        self.orchestrator = SyncOrchestrator(self.settings)
        self.overleaf_sync = OverleafSync(self.settings)
        self.github_sync = GitHubSyncService(self.settings)
        self.build_sync = BuildSync(self.settings)
        self.deploy_sync = DeploySync(self.settings)
        self.websocket_sync = WebSocketSyncService(self.settings)
        
        # Register all services
        self.service_manager.register_service("project", self.project_service)
        self.service_manager.register_service("orchestrator", self.orchestrator)
        self.service_manager.register_service("overleaf", self.overleaf_sync)
        self.service_manager.register_service("github", self.github_sync)
        self.service_manager.register_service("build", self.build_sync)
        self.service_manager.register_service("deploy", self.deploy_sync)
        self.service_manager.register_service("websocket", self.websocket_sync)
        
        # Initialize all services
        if self.settings:
            self.service_manager.initialize_all(self.settings)
        
        # Setup event handlers
        self._setup_event_handlers()
        
        logger.info("SyncManager initialized successfully")
    
    def _perform_cleanup(self) -> None:
        """Perform service cleanup."""
        logger.info("Cleaning up SyncManager")
        
        # Cleanup all services
        self.service_manager.cleanup_all()
        
        logger.info("SyncManager cleanup completed")
    
    def _setup_event_handlers(self) -> None:
        """Setup event handlers between services."""
        if self._event_handlers_registered or not self.orchestrator or not self.websocket_sync:
            return
        
        # Register WebSocket handlers with orchestrator
        self.orchestrator.add_sync_start_handler(self.websocket_sync.on_sync_started)
        self.orchestrator.add_sync_complete_handler(self.websocket_sync.on_sync_completed)
        
        self._event_handlers_registered = True
        logger.info("Event handlers registered")
    
    # Public API Methods
    
    async def sync_project_full(
        self,
        project_path: Path,
        overleaf_url: str,
        github_url: str,
        trigger: SyncTrigger = SyncTrigger.MANUAL,
        priority: SyncPriority = SyncPriority.NORMAL,
        config: Optional[SyncConfiguration] = None,
        user_id: Optional[str] = None
    ) -> SyncResult:
        """
        Perform full sync: Overleaf → GitHub → Build → Deploy.
        
        Args:
            project_path: Path to project directory
            overleaf_url: Overleaf Git URL
            github_url: GitHub repository URL  
            trigger: What triggered the sync
            priority: Sync priority
            config: Custom sync configuration
            user_id: User who triggered the sync
            
        Returns:
            SyncResult with operation details
        """
        if not self.project_service or not self.orchestrator:
            raise RuntimeError("Sync services not initialized")
        
        try:
            # Load project
            project = await self.project_service.load_project(project_path)
            if not project:
                raise ValueError(f"Could not load project from {project_path}")
            
            # Store sync URLs in project
            project.overleaf_url = overleaf_url
            project.github_url = github_url
            await self.project_service.save_project(project)
            
            # Start full sync
            sync_result = await self.orchestrator.sync_project(
                project=project,
                sync_type=SyncOperationType.FULL_SYNC,
                trigger=trigger,
                priority=priority,
                configuration=config,
                triggered_by_user=user_id
            )
            
            logger.info(f"Started full sync for project '{project.name}': {sync_result.operation_id}")
            return sync_result
        
        except Exception as e:
            logger.error(f"Failed to start full sync: {e}")
            raise
    
    async def sync_from_overleaf(
        self,
        project_path: Path,
        overleaf_url: str,
        config: Optional[SyncConfiguration] = None
    ) -> SyncResult:
        """
        Sync project from Overleaf only.
        
        Args:
            project_path: Path to project directory
            overleaf_url: Overleaf Git URL
            config: Sync configuration
            
        Returns:
            SyncResult with operation details
        """
        if not self.project_service or not self.overleaf_sync:
            raise RuntimeError("Services not initialized")
        
        # Load project
        project = await self.project_service.load_project(project_path)
        if not project:
            raise ValueError(f"Could not load project from {project_path}")
        
        # Sync from Overleaf
        sync_result = await self.overleaf_sync.sync_from_overleaf(
            project=project,
            overleaf_url=overleaf_url,
            target_directory=project_path,
            config=config
        )
        
        return sync_result
    
    async def sync_to_github(
        self,
        project_path: Path,
        github_url: str,
        config: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Sync project to GitHub only.
        
        Args:
            project_path: Path to project directory
            github_url: GitHub repository URL
            config: GitHub sync configuration
            
        Returns:
            SyncResult with operation details
        """
        if not self.project_service or not self.github_sync:
            raise RuntimeError("Services not initialized")
        
        # Load project
        project = await self.project_service.load_project(project_path)
        if not project:
            raise ValueError(f"Could not load project from {project_path}")
        
        # Convert config if provided
        github_config = None
        if config:
            from paperflow.services.sync.github_sync import GitHubSyncConfiguration
            github_config = GitHubSyncConfiguration(**config)
        
        # Sync to GitHub
        sync_result = await self.github_sync.sync_to_github(
            project=project,
            source_directory=project_path,
            github_repo_url=github_url,
            config=github_config
        )
        
        return sync_result
    
    async def build_project(
        self,
        project_path: Path,
        config: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Build project (LaTeX to HTML).
        
        Args:
            project_path: Path to project directory
            config: Build configuration
            
        Returns:
            SyncResult with build details
        """
        if not self.project_service or not self.build_sync:
            raise RuntimeError("Services not initialized")
        
        # Load project
        project = await self.project_service.load_project(project_path)
        if not project:
            raise ValueError(f"Could not load project from {project_path}")
        
        # Convert config if provided
        build_config = None
        if config:
            from paperflow.services.sync.build_sync import BuildConfiguration
            build_config = BuildConfiguration(**config)
        
        # Build project
        sync_result = await self.build_sync.build_project(
            project=project,
            source_directory=project_path,
            config=build_config
        )
        
        return sync_result
    
    async def deploy_project(
        self,
        project_path: Path,
        github_url: str,
        config: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Deploy project to GitHub Pages.
        
        Args:
            project_path: Path to project directory
            github_url: GitHub repository URL
            config: Deployment configuration
            
        Returns:
            SyncResult with deployment details
        """
        if not self.project_service or not self.deploy_sync:
            raise RuntimeError("Services not initialized")
        
        # Load project
        project = await self.project_service.load_project(project_path)
        if not project:
            raise ValueError(f"Could not load project from {project_path}")
        
        # Find build output directory
        build_output = project_path / "docs"
        if not build_output.exists():
            build_output = project_path / "dist"
        
        if not build_output.exists():
            raise ValueError("No build output directory found (docs/ or dist/)")
        
        # Convert config if provided
        deploy_config = None
        if config:
            from paperflow.services.sync.deploy_sync import DeploymentConfiguration
            deploy_config = DeploymentConfiguration(**config)
        
        # Deploy project
        sync_result = await self.deploy_sync.deploy_to_github_pages(
            project=project,
            build_output_directory=build_output,
            github_repo_url=github_url,
            config=deploy_config
        )
        
        return sync_result
    
    async def handle_webhook_sync(
        self,
        webhook_data: WebhookSyncTrigger,
        project_path: Optional[Path] = None
    ) -> SyncResult:
        """
        Handle webhook-triggered sync.
        
        Args:
            webhook_data: Webhook trigger information
            project_path: Optional project path (will be inferred if not provided)
            
        Returns:
            SyncResult with operation details
        """
        if not self.orchestrator:
            raise RuntimeError("Orchestrator not initialized")
        
        # Find project if not provided
        if not project_path:
            # Implementation would find project based on webhook data
            # For now, raise error
            raise ValueError("Project path must be provided for webhook sync")
        
        # Load project
        project = await self.project_service.load_project(project_path)
        if not project:
            raise ValueError(f"Could not load project from {project_path}")
        
        # Start webhook-triggered sync
        sync_result = await self.orchestrator.sync_project(
            project=project,
            sync_type=SyncOperationType.FULL_SYNC,
            trigger=SyncTrigger.WEBHOOK,
            priority=SyncPriority.HIGH,  # Webhooks get high priority
            webhook_data=webhook_data
        )
        
        return sync_result
    
    # Status and Management Methods
    
    async def get_sync_status(self, project_path: Path) -> Dict[str, Any]:
        """Get sync status for project."""
        if not self.project_service or not self.orchestrator:
            raise RuntimeError("Services not initialized")
        
        project = await self.project_service.load_project(project_path)
        if not project:
            raise ValueError(f"Could not load project from {project_path}")
        
        return await self.orchestrator.check_sync_status(project)
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get sync queue status."""
        if not self.orchestrator:
            raise RuntimeError("Orchestrator not initialized")
        
        return self.orchestrator.get_queue_status()
    
    async def get_active_operations(self) -> List[Dict[str, Any]]:
        """Get active sync operations."""
        if not self.orchestrator:
            raise RuntimeError("Orchestrator not initialized")
        
        return self.orchestrator.get_active_operations()
    
    async def cancel_sync(self, operation_id: str) -> bool:
        """Cancel sync operation."""
        if not self.orchestrator:
            raise RuntimeError("Orchestrator not initialized")
        
        return await self.orchestrator.cancel_sync(operation_id)
    
    async def get_sync_history(
        self,
        project_path: Optional[Path] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get sync operation history."""
        if not self.orchestrator:
            raise RuntimeError("Orchestrator not initialized")
        
        project = None
        if project_path:
            project = await self.project_service.load_project(project_path)
        
        return await self.orchestrator.get_sync_history(project, limit)
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all sync services."""
        return self.service_manager.get_all_status()
    
    def get_available_themes(self) -> List[str]:
        """Get available build themes."""
        if not self.build_sync:
            return []
        
        return self.build_sync.get_available_themes()
    
    # WebSocket Integration
    
    async def handle_websocket_connection(self, websocket, connection_id: str) -> None:
        """Handle WebSocket connection for real-time updates."""
        if not self.websocket_sync:
            raise RuntimeError("WebSocket service not initialized")
        
        await self.websocket_sync.handle_websocket_connection(websocket, connection_id)
    
    def get_websocket_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics."""
        if not self.websocket_sync:
            return {"error": "WebSocket service not initialized"}
        
        return self.websocket_sync.get_connection_stats()
    
    # Test and Validation Methods
    
    async def test_overleaf_connection(self, overleaf_url: str) -> Dict[str, Any]:
        """Test connection to Overleaf project."""
        if not self.overleaf_sync:
            raise RuntimeError("Overleaf service not initialized")
        
        return await self.overleaf_sync.test_connection(overleaf_url)
    
    async def test_github_connection(self) -> Dict[str, Any]:
        """Test GitHub API connection."""
        if not self.github_sync or not self.github_sync.github_service:
            raise RuntimeError("GitHub service not initialized")
        
        return await self.github_sync.github_service.test_authentication()
    
    async def validate_project_setup(self, project_path: Path) -> Dict[str, Any]:
        """Validate project setup for sync operations."""
        validation_result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "checks": {}
        }
        
        try:
            # Check if project exists and is valid
            if not self.project_service:
                validation_result["errors"].append("Project service not initialized")
                return validation_result
            
            project = await self.project_service.load_project(project_path)
            if not project:
                validation_result["errors"].append("Could not load project")
                return validation_result
            
            # Validate project
            project_validation = await self.project_service.validate_project(project)
            validation_result["checks"]["project"] = project_validation
            
            if not project_validation["valid"]:
                validation_result["errors"].extend(project_validation["errors"])
            
            validation_result["warnings"].extend(project_validation["warnings"])
            
            # Check if all sync services are available
            service_status = self.get_service_status()
            all_initialized = all(
                status.get("initialized", False) 
                for status in service_status.values()
            )
            
            validation_result["checks"]["services"] = {
                "all_initialized": all_initialized,
                "status": service_status
            }
            
            if not all_initialized:
                validation_result["errors"].append("Some sync services are not initialized")
            
            # Overall validation
            validation_result["valid"] = len(validation_result["errors"]) == 0
            
        except Exception as e:
            validation_result["errors"].append(f"Validation failed: {e}")
            logger.error(f"Project validation error: {e}")
        
        return validation_result