"""
Sync operation models for Paperflow.

This module defines data models for synchronization operations including
status tracking, progress reporting, and result handling.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class SyncOperationType(str, Enum):
    """Types of sync operations."""
    FULL_SYNC = "full_sync"
    PULL_ONLY = "pull_only"
    PUSH_ONLY = "push_only"
    BUILD_ONLY = "build_only"
    DEPLOY_ONLY = "deploy_only"
    OVERLEAF_SYNC = "overleaf_sync"
    GITHUB_SYNC = "github_sync"


class SyncStatus(str, Enum):
    """Status of sync operations."""
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CONFLICT = "conflict"
    PARTIAL = "partial"


class SyncStage(str, Enum):
    """Stages of the sync process."""
    INITIALIZING = "initializing"
    PULLING_OVERLEAF = "pulling_overleaf"
    PROCESSING_CHANGES = "processing_changes"
    PUSHING_GITHUB = "pushing_github"
    BUILDING = "building"
    DEPLOYING = "deploying"
    FINALIZING = "finalizing"
    COMPLETED = "completed"


class ConflictResolution(str, Enum):
    """Conflict resolution strategies."""
    MANUAL = "manual"
    OVERLEAF_WINS = "overleaf_wins"
    GITHUB_WINS = "github_wins"
    MERGE_AUTOMATIC = "merge_automatic"
    SKIP_CONFLICTED = "skip_conflicted"


class SyncTrigger(str, Enum):
    """What triggered the sync operation."""
    MANUAL = "manual"
    WEBHOOK = "webhook"
    SCHEDULED = "scheduled"
    FILE_WATCHER = "file_watcher"
    API_REQUEST = "api_request"


class SyncPriority(str, Enum):
    """Priority levels for sync operations."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class SyncProgress:
    """Progress tracking for sync operations."""
    stage: SyncStage = SyncStage.INITIALIZING
    current_step: str = ""
    total_steps: int = 0
    completed_steps: int = 0
    percentage: float = 0.0
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    
    def update_progress(self, step: str, completed: int, total: int) -> None:
        """Update progress information."""
        self.current_step = step
        self.completed_steps = completed
        self.total_steps = total
        self.percentage = (completed / total * 100) if total > 0 else 0.0
        self.updated_at = datetime.now()


@dataclass
class SyncConflict:
    """Information about a sync conflict."""
    file_path: str
    conflict_type: str
    overleaf_version: Optional[str] = None
    github_version: Optional[str] = None
    resolution: Optional[ConflictResolution] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncMetrics:
    """Metrics and statistics for sync operations."""
    files_pulled: int = 0
    files_pushed: int = 0
    files_modified: int = 0
    files_added: int = 0
    files_deleted: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    bytes_transferred: int = 0
    build_time_seconds: float = 0.0
    deploy_time_seconds: float = 0.0
    total_time_seconds: float = 0.0


class SyncConfiguration(BaseModel):
    """Configuration for sync operations."""
    auto_resolve_conflicts: bool = False
    conflict_resolution_strategy: ConflictResolution = ConflictResolution.MANUAL
    enable_build_on_sync: bool = True
    enable_deploy_on_build: bool = True
    retry_failed_operations: bool = True
    max_retry_attempts: int = 3
    retry_delay_seconds: int = 30
    notification_webhook_url: Optional[str] = None
    notification_email: Optional[str] = None
    preserve_local_changes: bool = True
    backup_before_sync: bool = True
    skip_build_on_no_changes: bool = True
    custom_build_script: Optional[str] = None
    deployment_environment: str = "production"
    sync_timeout_minutes: int = 30
    file_size_limit_mb: int = 100
    excluded_file_patterns: List[str] = Field(default_factory=lambda: [
        "*.log", "*.tmp", ".DS_Store", "node_modules/*", ".git/*"
    ])
    included_file_patterns: List[str] = Field(default_factory=lambda: [
        "*.tex", "*.bib", "*.cls", "*.sty", "*.png", "*.jpg", "*.pdf"
    ])


class SyncResult(BaseModel):
    """Result of a sync operation."""
    operation_id: str
    operation_type: SyncOperationType
    status: SyncStatus
    trigger: SyncTrigger
    priority: SyncPriority = SyncPriority.NORMAL
    
    # Timing information
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Progress tracking
    progress: SyncProgress = Field(default_factory=SyncProgress)
    
    # Results and errors
    success: bool = False
    error_message: Optional[str] = None
    error_details: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    
    # File and conflict information
    conflicts: List[SyncConflict] = Field(default_factory=list)
    metrics: SyncMetrics = Field(default_factory=SyncMetrics)
    
    # Repository information
    overleaf_repo_url: Optional[str] = None
    github_repo_url: Optional[str] = None
    source_commit_hash: Optional[str] = None
    target_commit_hash: Optional[str] = None
    
    # Build and deployment
    build_output_path: Optional[Path] = None
    build_artifacts: List[str] = Field(default_factory=list)
    deployment_url: Optional[str] = None
    deployment_status: Optional[str] = None
    
    # Additional metadata
    configuration: Optional[SyncConfiguration] = None
    triggered_by_user: Optional[str] = None
    webhook_delivery_id: Optional[str] = None
    
    def mark_started(self) -> None:
        """Mark sync operation as started."""
        self.started_at = datetime.now()
        self.status = SyncStatus.IN_PROGRESS
        self.progress.started_at = self.started_at
    
    def mark_completed(self, success: bool = True, error: Optional[str] = None) -> None:
        """Mark sync operation as completed."""
        self.completed_at = datetime.now()
        self.success = success
        self.status = SyncStatus.COMPLETED if success else SyncStatus.FAILED
        
        if error:
            self.error_message = error
        
        # Calculate total time
        if self.started_at:
            self.metrics.total_time_seconds = (
                self.completed_at - self.started_at
            ).total_seconds()
        
        # Update progress
        self.progress.stage = SyncStage.COMPLETED
        self.progress.percentage = 100.0
        self.progress.updated_at = self.completed_at
    
    def add_conflict(self, conflict: SyncConflict) -> None:
        """Add a conflict to the result."""
        self.conflicts.append(conflict)
        self.metrics.conflicts_detected = len(self.conflicts)
        
        if not conflict.resolution:
            self.status = SyncStatus.CONFLICT
    
    def resolve_conflict(self, file_path: str, resolution: ConflictResolution) -> bool:
        """Resolve a specific conflict."""
        for conflict in self.conflicts:
            if conflict.file_path == file_path and not conflict.resolution:
                conflict.resolution = resolution
                conflict.resolved_at = datetime.now()
                self.metrics.conflicts_resolved += 1
                
                # Check if all conflicts are resolved
                unresolved = [c for c in self.conflicts if not c.resolution]
                if not unresolved and self.status == SyncStatus.CONFLICT:
                    self.status = SyncStatus.IN_PROGRESS
                
                return True
        
        return False
    
    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)
    
    def get_duration(self) -> Optional[float]:
        """Get operation duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def has_unresolved_conflicts(self) -> bool:
        """Check if there are unresolved conflicts."""
        return any(not conflict.resolution for conflict in self.conflicts)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the sync result."""
        return {
            "operation_id": self.operation_id,
            "status": self.status.value,
            "success": self.success,
            "duration_seconds": self.get_duration(),
            "files_modified": self.metrics.files_modified,
            "conflicts": len(self.conflicts),
            "unresolved_conflicts": len([c for c in self.conflicts if not c.resolution]),
            "warnings": len(self.warnings),
            "error": self.error_message,
            "deployment_url": self.deployment_url
        }


class SyncQueue(BaseModel):
    """Queue for managing sync operations."""
    pending_operations: List[SyncResult] = Field(default_factory=list)
    active_operations: List[SyncResult] = Field(default_factory=list)
    completed_operations: List[SyncResult] = Field(default_factory=list)
    max_concurrent_operations: int = 3
    max_queue_size: int = 100
    
    def add_operation(self, operation: SyncResult) -> bool:
        """Add operation to queue."""
        if len(self.pending_operations) >= self.max_queue_size:
            return False
        
        # Sort by priority and creation time
        self.pending_operations.append(operation)
        self.pending_operations.sort(
            key=lambda x: (x.priority.value, x.created_at)
        )
        
        return True
    
    def get_next_operation(self) -> Optional[SyncResult]:
        """Get next operation to process."""
        if (
            self.pending_operations 
            and len(self.active_operations) < self.max_concurrent_operations
        ):
            operation = self.pending_operations.pop(0)
            operation.status = SyncStatus.QUEUED
            self.active_operations.append(operation)
            return operation
        
        return None
    
    def complete_operation(self, operation_id: str) -> Optional[SyncResult]:
        """Mark operation as completed and move to completed list."""
        for i, operation in enumerate(self.active_operations):
            if operation.operation_id == operation_id:
                completed_op = self.active_operations.pop(i)
                self.completed_operations.append(completed_op)
                
                # Keep only recent completed operations
                if len(self.completed_operations) > 1000:
                    self.completed_operations = self.completed_operations[-500:]
                
                return completed_op
        
        return None
    
    def get_operation_status(self, operation_id: str) -> Optional[SyncResult]:
        """Get status of a specific operation."""
        # Check all queues
        all_operations = (
            self.pending_operations + 
            self.active_operations + 
            self.completed_operations
        )
        
        for operation in all_operations:
            if operation.operation_id == operation_id:
                return operation
        
        return None
    
    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a pending operation."""
        for i, operation in enumerate(self.pending_operations):
            if operation.operation_id == operation_id:
                operation.status = SyncStatus.CANCELLED
                cancelled_op = self.pending_operations.pop(i)
                self.completed_operations.append(cancelled_op)
                return True
        
        return False
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "pending": len(self.pending_operations),
            "active": len(self.active_operations),
            "completed": len(self.completed_operations),
            "max_concurrent": self.max_concurrent_operations,
            "max_queue_size": self.max_queue_size
        }


class WebhookSyncTrigger(BaseModel):
    """Webhook trigger information for sync operations."""
    webhook_id: str
    repository_url: str
    branch: str
    commit_hash: str
    commit_message: str
    author_name: str
    author_email: str
    modified_files: List[str] = Field(default_factory=list)
    added_files: List[str] = Field(default_factory=list)
    removed_files: List[str] = Field(default_factory=list)
    webhook_payload: Dict[str, Any] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=datetime.now)


class ScheduledSyncConfig(BaseModel):
    """Configuration for scheduled sync operations."""
    project_id: str
    cron_expression: str
    enabled: bool = True
    sync_type: SyncOperationType = SyncOperationType.FULL_SYNC
    configuration: SyncConfiguration = Field(default_factory=SyncConfiguration)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class SyncNotification(BaseModel):
    """Notification configuration for sync operations."""
    enabled: bool = True
    webhook_url: Optional[str] = None
    email_recipients: List[str] = Field(default_factory=list)
    slack_webhook: Optional[str] = None
    notify_on_success: bool = True
    notify_on_failure: bool = True
    notify_on_conflicts: bool = True
    notify_on_warnings: bool = False
    custom_message_template: Optional[str] = None
    include_detailed_logs: bool = False