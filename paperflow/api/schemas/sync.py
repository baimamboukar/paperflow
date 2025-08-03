"""
Synchronization-related schemas for Paperflow API.

This module provides request and response models for sync
operations with Overleaf, GitHub, and other platforms.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .base import APIResponse, TaskInfo


class SyncProvider(str, Enum):
    """Sync provider enumeration."""

    OVERLEAF = "overleaf"
    GITHUB = "github"
    GITLAB = "gitlab"
    DROPBOX = "dropbox"
    GOOGLE_DRIVE = "google_drive"


class SyncDirection(str, Enum):
    """Sync direction enumeration."""

    PULL = "pull"  # From remote to local
    PUSH = "push"  # From local to remote
    BIDIRECTIONAL = "bidirectional"  # Both directions


class SyncStatus(str, Enum):
    """Sync status enumeration."""

    IDLE = "idle"
    SYNCING = "syncing"
    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"


class ConflictResolution(str, Enum):
    """Conflict resolution strategy."""

    LOCAL = "local"  # Keep local changes
    REMOTE = "remote"  # Keep remote changes
    MERGE = "merge"  # Attempt to merge
    MANUAL = "manual"  # Require manual resolution


class SyncConfig(BaseModel):
    """Sync configuration schema."""

    provider: SyncProvider = Field(..., description="Sync provider")
    enabled: bool = Field(True, description="Whether sync is enabled")
    auto_sync: bool = Field(False, description="Enable automatic sync")
    sync_interval: int = Field(300, description="Auto sync interval in seconds")
    direction: SyncDirection = Field(
        SyncDirection.BIDIRECTIONAL, description="Sync direction"
    )
    conflict_resolution: ConflictResolution = Field(
        ConflictResolution.MANUAL, description="Conflict resolution strategy"
    )

    # Provider-specific settings
    provider_config: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific configuration"
    )

    @validator("sync_interval")
    def validate_sync_interval(cls, v):
        """Validate sync interval."""
        if v < 60:  # Minimum 1 minute
            raise ValueError("Sync interval must be at least 60 seconds")
        return v


class OverleafConfig(BaseModel):
    """Overleaf-specific sync configuration."""

    project_id: str = Field(..., description="Overleaf project ID")
    email: str = Field(..., description="Overleaf account email")
    password: Optional[str] = Field(
        None, description="Overleaf password (if not using token)"
    )
    token: Optional[str] = Field(None, description="Overleaf API token")
    include_comments: bool = Field(True, description="Include Overleaf comments")
    include_history: bool = Field(False, description="Include version history")


class GitHubConfig(BaseModel):
    """GitHub-specific sync configuration."""

    repository: str = Field(..., description="GitHub repository (owner/repo)")
    branch: str = Field(default="main", description="Git branch")
    path: str = Field(default="", description="Path within repository")
    token: Optional[str] = Field(None, description="GitHub access token")
    ssh_key: Optional[str] = Field(None, description="SSH private key")
    webhook_secret: Optional[str] = Field(None, description="Webhook secret")


class SyncRequest(BaseModel):
    """Base sync request schema."""

    provider: SyncProvider = Field(..., description="Sync provider")
    direction: SyncDirection = Field(SyncDirection.PULL, description="Sync direction")
    force: bool = Field(False, description="Force sync even if conflicts exist")
    dry_run: bool = Field(False, description="Perform dry run without making changes")
    include_files: List[str] = Field(
        default_factory=list, description="Specific files to sync (empty = all)"
    )
    exclude_files: List[str] = Field(
        default_factory=list, description="Files to exclude from sync"
    )


class OverleafSyncRequest(SyncRequest):
    """Overleaf sync request schema."""

    provider: SyncProvider = Field(
        SyncProvider.OVERLEAF, description="Must be overleaf"
    )
    config: OverleafConfig = Field(..., description="Overleaf configuration")


class GitHubSyncRequest(SyncRequest):
    """GitHub sync request schema."""

    provider: SyncProvider = Field(SyncProvider.GITHUB, description="Must be github")
    config: GitHubConfig = Field(..., description="GitHub configuration")
    commit_message: Optional[str] = Field(
        None, description="Custom commit message for push"
    )
    create_pr: bool = Field(False, description="Create pull request for changes")
    pr_title: Optional[str] = Field(None, description="Pull request title")
    pr_description: Optional[str] = Field(None, description="Pull request description")


class SyncFileChange(BaseModel):
    """File change information in sync."""

    path: str = Field(..., description="File path")
    action: str = Field(..., description="Change action: added, modified, deleted")
    size_before: Optional[int] = Field(None, description="File size before change")
    size_after: Optional[int] = Field(None, description="File size after change")
    checksum_before: Optional[str] = Field(
        None, description="File checksum before change"
    )
    checksum_after: Optional[str] = Field(
        None, description="File checksum after change"
    )
    conflict: bool = Field(False, description="Whether file has conflicts")


class SyncConflict(BaseModel):
    """Sync conflict information."""

    path: str = Field(..., description="Conflicted file path")
    description: str = Field(..., description="Conflict description")
    local_version: Optional[str] = Field(None, description="Local version info")
    remote_version: Optional[str] = Field(None, description="Remote version info")
    suggested_resolution: ConflictResolution = Field(
        ..., description="Suggested resolution"
    )


class SyncResult(BaseModel):
    """Sync operation result."""

    success: bool = Field(..., description="Whether sync was successful")
    status: SyncStatus = Field(..., description="Sync status")
    direction: SyncDirection = Field(..., description="Sync direction")
    files_changed: List[SyncFileChange] = Field(
        default_factory=list, description="Files that changed"
    )
    conflicts: List[SyncConflict] = Field(
        default_factory=list, description="Conflicts encountered"
    )

    # Statistics
    files_added: int = Field(0, description="Number of files added")
    files_modified: int = Field(0, description="Number of files modified")
    files_deleted: int = Field(0, description="Number of files deleted")
    bytes_transferred: int = Field(0, description="Bytes transferred")

    # Timing
    started_at: datetime = Field(..., description="Sync start time")
    completed_at: Optional[datetime] = Field(None, description="Sync completion time")
    duration: Optional[float] = Field(None, description="Sync duration in seconds")

    # Messages
    message: Optional[str] = Field(None, description="Sync result message")
    error: Optional[str] = Field(None, description="Error message if failed")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")


class SyncHistory(BaseModel):
    """Sync history entry."""

    id: str = Field(..., description="Sync history ID")
    provider: SyncProvider = Field(..., description="Sync provider")
    direction: SyncDirection = Field(..., description="Sync direction")
    status: SyncStatus = Field(..., description="Sync status")
    initiated_by: str = Field(..., description="Who initiated the sync")
    result: SyncResult = Field(..., description="Sync result")
    created_at: datetime = Field(..., description="Sync timestamp")


class SyncStatus(BaseModel):
    """Current sync status for a project."""

    enabled: bool = Field(..., description="Whether sync is enabled")
    provider: Optional[SyncProvider] = Field(None, description="Current sync provider")
    status: SyncStatus = Field(SyncStatus.IDLE, description="Current sync status")
    last_sync: Optional[datetime] = Field(None, description="Last sync timestamp")
    next_sync: Optional[datetime] = Field(None, description="Next scheduled sync")

    # Current operation
    current_task_id: Optional[str] = Field(None, description="Current sync task ID")
    progress: Optional[int] = Field(
        None, description="Current sync progress percentage"
    )

    # Statistics
    total_syncs: int = Field(0, description="Total number of syncs performed")
    successful_syncs: int = Field(0, description="Number of successful syncs")
    failed_syncs: int = Field(0, description="Number of failed syncs")
    last_success: Optional[datetime] = Field(None, description="Last successful sync")
    last_failure: Optional[datetime] = Field(None, description="Last failed sync")

    # Configuration
    config: Optional[SyncConfig] = Field(None, description="Current sync configuration")


class SyncSchedule(BaseModel):
    """Sync schedule configuration."""

    enabled: bool = Field(True, description="Whether scheduled sync is enabled")
    interval: int = Field(3600, description="Sync interval in seconds")
    time_of_day: Optional[str] = Field(None, description="Specific time of day (HH:MM)")
    days_of_week: List[int] = Field(
        default_factory=list, description="Days of week (0=Monday)"
    )
    timezone: str = Field("UTC", description="Timezone for scheduling")

    @validator("interval")
    def validate_interval(cls, v):
        """Validate sync interval."""
        if v < 300:  # Minimum 5 minutes
            raise ValueError("Sync interval must be at least 300 seconds")
        return v

    @validator("days_of_week")
    def validate_days_of_week(cls, v):
        """Validate days of week."""
        if v and any(day < 0 or day > 6 for day in v):
            raise ValueError("Days of week must be 0-6 (Monday=0)")
        return v


class ConflictResolutionRequest(BaseModel):
    """Request to resolve sync conflicts."""

    conflicts: List[Dict[str, Any]] = Field(..., description="Conflicts to resolve")

    class ConflictResolution(BaseModel):
        path: str = Field(..., description="File path")
        resolution: ConflictResolution = Field(..., description="Resolution strategy")
        custom_content: Optional[str] = Field(
            None, description="Custom file content for manual resolution"
        )


class SyncDryRunResult(BaseModel):
    """Dry run sync result."""

    would_change: List[SyncFileChange] = Field(
        ..., description="Files that would change"
    )
    conflicts: List[SyncConflict] = Field(..., description="Conflicts that would occur")
    safe_to_proceed: bool = Field(..., description="Whether it's safe to proceed")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")


class SyncProviderInfo(BaseModel):
    """Information about a sync provider."""

    provider: SyncProvider = Field(..., description="Provider name")
    display_name: str = Field(..., description="Human-readable provider name")
    description: str = Field(..., description="Provider description")
    supported_directions: List[SyncDirection] = Field(
        ..., description="Supported sync directions"
    )
    requires_auth: bool = Field(
        ..., description="Whether provider requires authentication"
    )
    supports_auto_sync: bool = Field(
        ..., description="Whether provider supports auto sync"
    )
    config_schema: Dict[str, Any] = Field(..., description="Configuration schema")


# Response schemas
class SyncConfigResponse(APIResponse):
    """Response for sync configuration."""

    data: SyncConfig


class SyncRequestResponse(APIResponse):
    """Response for sync request."""

    data: TaskInfo


class SyncResultResponse(APIResponse):
    """Response for sync result."""

    data: SyncResult


class SyncStatusResponse(APIResponse):
    """Response for sync status."""

    data: SyncStatus


class SyncHistoryResponse(APIResponse):
    """Response for sync history."""

    data: List[SyncHistory]


class SyncDryRunResponse(APIResponse):
    """Response for sync dry run."""

    data: SyncDryRunResult


class SyncProvidersResponse(APIResponse):
    """Response for available sync providers."""

    data: List[SyncProviderInfo]
