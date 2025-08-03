"""
WebSocket-related schemas for Paperflow API.

This module provides request and response models for WebSocket
communications and real-time updates.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WebSocketMessageType(str, Enum):
    """WebSocket message type enumeration."""

    # Connection management
    PING = "ping"
    PONG = "pong"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    ERROR = "error"
    
    # Build events
    BUILD_STARTED = "build_started"
    BUILD_PROGRESS = "build_progress"
    BUILD_LOG = "build_log"
    BUILD_ERROR = "build_error"
    BUILD_WARNING = "build_warning"
    BUILD_COMPLETED = "build_completed"
    BUILD_FAILED = "build_failed"
    BUILD_CANCELLED = "build_cancelled"
    
    # Sync events
    SYNC_STARTED = "sync_started"
    SYNC_PROGRESS = "sync_progress"
    SYNC_FILE_CHANGED = "sync_file_changed"
    SYNC_CONFLICT = "sync_conflict"
    SYNC_COMPLETED = "sync_completed"
    SYNC_FAILED = "sync_failed"
    
    # Project events
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    PROJECT_DELETED = "project_deleted"
    PROJECT_VALIDATED = "project_validated"
    
    # File events
    FILE_UPLOADED = "file_uploaded"
    FILE_UPDATED = "file_updated"
    FILE_DELETED = "file_deleted"
    
    # Template events
    TEMPLATE_APPLIED = "template_applied"
    TEMPLATE_INSTALLED = "template_installed"
    
    # System events
    SYSTEM_STATUS = "system_status"
    MAINTENANCE_MODE = "maintenance_mode"
    
    # User events
    USER_CONNECTED = "user_connected"
    USER_DISCONNECTED = "user_disconnected"


class WebSocketChannel(str, Enum):
    """WebSocket channel enumeration."""

    # Global channels
    SYSTEM = "system"
    USER = "user"
    
    # Project-specific channels
    PROJECT = "project"
    BUILD = "build"
    SYNC = "sync"
    
    # Feature-specific channels
    TEMPLATES = "templates"
    FILES = "files"


class WebSocketMessage(BaseModel):
    """Base WebSocket message schema."""

    type: WebSocketMessageType = Field(..., description="Message type")
    channel: WebSocketChannel = Field(..., description="Message channel")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Message timestamp"
    )
    message_id: Optional[str] = Field(None, description="Unique message ID")
    user_id: Optional[str] = Field(None, description="User ID if applicable")
    session_id: Optional[str] = Field(None, description="Session ID")
    data: Dict[str, Any] = Field(default_factory=dict, description="Message data")


class ConnectionMessage(WebSocketMessage):
    """Connection management message."""

    type: WebSocketMessageType = Field(
        WebSocketMessageType.CONNECT, description="Connection message type"
    )
    channel: WebSocketChannel = Field(
        WebSocketChannel.SYSTEM, description="System channel"
    )


class PingMessage(WebSocketMessage):
    """Ping message for connection health."""

    type: WebSocketMessageType = Field(
        WebSocketMessageType.PING, description="Ping message"
    )
    channel: WebSocketChannel = Field(
        WebSocketChannel.SYSTEM, description="System channel"
    )


class PongMessage(WebSocketMessage):
    """Pong response message."""

    type: WebSocketMessageType = Field(
        WebSocketMessageType.PONG, description="Pong message"
    )
    channel: WebSocketChannel = Field(
        WebSocketChannel.SYSTEM, description="System channel"
    )


class ErrorMessage(WebSocketMessage):
    """Error message."""

    type: WebSocketMessageType = Field(
        WebSocketMessageType.ERROR, description="Error message"
    )
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")


class BuildProgressMessage(WebSocketMessage):
    """Build progress update message."""

    type: WebSocketMessageType = Field(
        WebSocketMessageType.BUILD_PROGRESS, description="Build progress message"
    )
    channel: WebSocketChannel = Field(
        WebSocketChannel.BUILD, description="Build channel"
    )
    build_id: str = Field(..., description="Build ID")
    project_name: str = Field(..., description="Project name")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")
    current_step: str = Field(..., description="Current build step")
    estimated_time_remaining: Optional[int] = Field(
        None, description="Estimated time remaining in seconds"
    )


class BuildLogMessage(WebSocketMessage):
    """Build log message."""

    type: WebSocketMessageType = Field(
        WebSocketMessageType.BUILD_LOG, description="Build log message"
    )
    channel: WebSocketChannel = Field(
        WebSocketChannel.BUILD, description="Build channel"
    )
    build_id: str = Field(..., description="Build ID")
    project_name: str = Field(..., description="Project name")
    level: str = Field(..., description="Log level")
    message: str = Field(..., description="Log message")
    file: Optional[str] = Field(None, description="Source file")
    line: Optional[int] = Field(None, description="Line number")


class BuildStatusMessage(WebSocketMessage):
    """Build status change message."""

    build_id: str = Field(..., description="Build ID")
    project_name: str = Field(..., description="Project name")
    status: str = Field(..., description="Build status")
    result: Optional[Dict[str, Any]] = Field(None, description="Build result")


class SyncProgressMessage(WebSocketMessage):
    """Sync progress update message."""

    type: WebSocketMessageType = Field(
        WebSocketMessageType.SYNC_PROGRESS, description="Sync progress message"
    )
    channel: WebSocketChannel = Field(
        WebSocketChannel.SYNC, description="Sync channel"
    )
    project_name: str = Field(..., description="Project name")
    provider: str = Field(..., description="Sync provider")
    direction: str = Field(..., description="Sync direction")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")
    current_file: Optional[str] = Field(None, description="Current file being synced")
    files_processed: int = Field(0, description="Files processed")
    total_files: int = Field(0, description="Total files to process")


class SyncFileChangeMessage(WebSocketMessage):
    """Sync file change message."""

    type: WebSocketMessageType = Field(
        WebSocketMessageType.SYNC_FILE_CHANGED, description="Sync file change message"
    )
    channel: WebSocketChannel = Field(
        WebSocketChannel.SYNC, description="Sync channel"
    )
    project_name: str = Field(..., description="Project name")
    file_path: str = Field(..., description="Changed file path")
    action: str = Field(..., description="Change action: added, modified, deleted")
    conflict: bool = Field(False, description="Whether file has conflicts")


class SyncConflictMessage(WebSocketMessage):
    """Sync conflict message."""

    type: WebSocketMessageType = Field(
        WebSocketMessageType.SYNC_CONFLICT, description="Sync conflict message"
    )
    channel: WebSocketChannel = Field(
        WebSocketChannel.SYNC, description="Sync channel"
    )
    project_name: str = Field(..., description="Project name")
    file_path: str = Field(..., description="Conflicted file path")
    description: str = Field(..., description="Conflict description")
    resolution_options: List[str] = Field(
        ..., description="Available resolution options"
    )


class ProjectUpdateMessage(WebSocketMessage):
    """Project update message."""

    type: WebSocketMessageType = Field(
        WebSocketMessageType.PROJECT_UPDATED, description="Project update message"
    )
    channel: WebSocketChannel = Field(
        WebSocketChannel.PROJECT, description="Project channel"
    )
    project_name: str = Field(..., description="Project name")
    updated_fields: List[str] = Field(..., description="Updated fields")
    update_type: str = Field(..., description="Update type")


class FileUpdateMessage(WebSocketMessage):
    """File update message."""

    channel: WebSocketChannel = Field(
        WebSocketChannel.FILES, description="Files channel"
    )
    project_name: str = Field(..., description="Project name")
    file_path: str = Field(..., description="File path")
    file_size: Optional[int] = Field(None, description="File size")
    checksum: Optional[str] = Field(None, description="File checksum")


class SystemStatusMessage(WebSocketMessage):
    """System status update message."""

    type: WebSocketMessageType = Field(
        WebSocketMessageType.SYSTEM_STATUS, description="System status message"
    )
    channel: WebSocketChannel = Field(
        WebSocketChannel.SYSTEM, description="System channel"
    )
    status: str = Field(..., description="System status")
    components: Dict[str, str] = Field(..., description="Component statuses")
    metrics: Dict[str, Any] = Field(..., description="System metrics")


class UserActivityMessage(WebSocketMessage):
    """User activity message."""

    channel: WebSocketChannel = Field(
        WebSocketChannel.USER, description="User channel"
    )
    activity_type: str = Field(..., description="Activity type")
    description: str = Field(..., description="Activity description")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Activity metadata"
    )


class WebSocketSubscription(BaseModel):
    """WebSocket subscription request."""

    channels: List[WebSocketChannel] = Field(..., description="Channels to subscribe to")
    message_types: Optional[List[WebSocketMessageType]] = Field(
        None, description="Specific message types to receive"
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict, description="Message filters"
    )
    
    # Project-specific subscriptions
    project_names: Optional[List[str]] = Field(
        None, description="Specific projects to monitor"
    )
    
    # User-specific subscriptions
    user_id: Optional[str] = Field(None, description="Specific user to monitor")


class WebSocketUnsubscription(BaseModel):
    """WebSocket unsubscription request."""

    channels: Optional[List[WebSocketChannel]] = Field(
        None, description="Channels to unsubscribe from"
    )
    message_types: Optional[List[WebSocketMessageType]] = Field(
        None, description="Message types to stop receiving"
    )
    all: bool = Field(False, description="Unsubscribe from all channels")


class WebSocketStats(BaseModel):
    """WebSocket connection statistics."""

    total_connections: int = Field(..., description="Total active connections")
    connections_by_channel: Dict[str, int] = Field(
        ..., description="Connections per channel"
    )
    messages_sent: int = Field(..., description="Total messages sent")
    messages_received: int = Field(..., description="Total messages received")
    average_latency: float = Field(..., description="Average message latency")
    error_rate: float = Field(..., description="Error rate percentage")
    
    # Recent activity
    messages_last_hour: int = Field(..., description="Messages in last hour")
    connections_last_hour: int = Field(..., description="New connections in last hour")
    errors_last_hour: int = Field(..., description="Errors in last hour")


class WebSocketConfig(BaseModel):
    """WebSocket configuration."""

    max_connections: int = Field(1000, description="Maximum concurrent connections")
    max_message_size: int = Field(1024 * 1024, description="Maximum message size")
    heartbeat_interval: int = Field(30, description="Heartbeat interval in seconds")
    connection_timeout: int = Field(300, description="Connection timeout in seconds")
    
    # Rate limiting
    max_messages_per_minute: int = Field(
        100, description="Maximum messages per minute per connection"
    )
    
    # Channel limits
    max_channels_per_connection: int = Field(
        10, description="Maximum channels per connection"
    )
    
    # Buffer settings
    message_buffer_size: int = Field(
        1000, description="Message buffer size per connection"
    )
    
    # Compression
    compression_enabled: bool = Field(True, description="Enable message compression")
    compression_threshold: int = Field(1024, description="Compression threshold bytes")


# Helper functions for message creation
def create_build_progress_message(
    build_id: str,
    project_name: str,
    progress: int,
    current_step: str,
    user_id: Optional[str] = None,
) -> BuildProgressMessage:
    """Create a build progress message."""
    return BuildProgressMessage(
        build_id=build_id,
        project_name=project_name,
        progress=progress,
        current_step=current_step,
        user_id=user_id,
        data={
            "build_id": build_id,
            "project_name": project_name,
            "progress": progress,
            "current_step": current_step,
        },
    )


def create_sync_progress_message(
    project_name: str,
    provider: str,
    direction: str,
    progress: int,
    current_file: Optional[str] = None,
    user_id: Optional[str] = None,
) -> SyncProgressMessage:
    """Create a sync progress message."""
    return SyncProgressMessage(
        project_name=project_name,
        provider=provider,
        direction=direction,
        progress=progress,
        current_file=current_file,
        user_id=user_id,
        data={
            "project_name": project_name,
            "provider": provider,
            "direction": direction,
            "progress": progress,
            "current_file": current_file,
        },
    )