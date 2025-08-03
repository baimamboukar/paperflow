"""
Base schemas and common models for Paperflow API.

This module provides base classes and common models used
across different API endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class APIResponse(BaseModel):
    """Base API response model."""

    success: bool = Field(True, description="Whether the request was successful")
    message: Optional[str] = Field(None, description="Response message")
    data: Optional[Any] = Field(None, description="Response data")
    errors: Optional[List[str]] = Field(None, description="List of errors if any")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )


class APIError(BaseModel):
    """API error response model."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
    code: Optional[str] = Field(None, description="Error code")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp"
    )


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(1, ge=1, description="Page number (1-based)")
    page_size: int = Field(20, ge=1, le=100, description="Number of items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel):
    """Paginated response model."""

    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")

    @classmethod
    def create(
        cls, items: List[Any], total: int, pagination: PaginationParams
    ) -> "PaginatedResponse":
        """Create paginated response from items and pagination params."""
        total_pages = (total + pagination.page_size - 1) // pagination.page_size

        return cls(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
            has_next=pagination.page < total_pages,
            has_prev=pagination.page > 1,
        )


class SortOrder(str, Enum):
    """Sort order enumeration."""

    ASC = "asc"
    DESC = "desc"


class SortParams(BaseModel):
    """Sort parameters for list endpoints."""

    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: SortOrder = Field(SortOrder.ASC, description="Sort order")


class FilterParams(BaseModel):
    """Base filter parameters."""

    search: Optional[str] = Field(None, description="Search query")
    created_after: Optional[datetime] = Field(
        None, description="Filter items created after this date"
    )
    created_before: Optional[datetime] = Field(
        None, description="Filter items created before this date"
    )
    updated_after: Optional[datetime] = Field(
        None, description="Filter items updated after this date"
    )
    updated_before: Optional[datetime] = Field(
        None, description="Filter items updated before this date"
    )


class FileInfo(BaseModel):
    """File information model."""

    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type")
    checksum: Optional[str] = Field(None, description="File checksum (MD5/SHA256)")
    uploaded_at: datetime = Field(
        default_factory=datetime.utcnow, description="Upload timestamp"
    )


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    REVOKED = "revoked"


class TaskInfo(BaseModel):
    """Background task information."""

    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatus = Field(..., description="Current task status")
    progress: Optional[int] = Field(
        None, ge=0, le=100, description="Task progress percentage"
    )
    message: Optional[str] = Field(None, description="Current task message")
    result: Optional[Any] = Field(None, description="Task result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
    started_at: Optional[datetime] = Field(None, description="Task start time")
    completed_at: Optional[datetime] = Field(None, description="Task completion time")
    total_time: Optional[float] = Field(
        None, description="Total execution time in seconds"
    )


class HealthStatus(str, Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheck(BaseModel):
    """Health check response model."""

    status: HealthStatus = Field(..., description="Overall health status")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Health check timestamp"
    )
    uptime: float = Field(..., description="Application uptime in seconds")
    checks: Dict[str, Any] = Field(
        default_factory=dict, description="Individual component checks"
    )


class ValidationError(BaseModel):
    """Validation error details."""

    field: str = Field(..., description="Field name with error")
    message: str = Field(..., description="Error message")
    value: Optional[Any] = Field(None, description="Invalid value")


class BulkOperationRequest(BaseModel):
    """Base model for bulk operations."""

    ids: List[str] = Field(..., min_items=1, description="List of IDs to operate on")

    @validator("ids")
    def validate_ids(cls, v):
        """Validate that IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("IDs must be unique")
        return v


class BulkOperationResponse(BaseModel):
    """Response model for bulk operations."""

    total: int = Field(..., description="Total number of items processed")
    successful: int = Field(..., description="Number of successful operations")
    failed: int = Field(..., description="Number of failed operations")
    errors: List[Dict[str, str]] = Field(
        default_factory=list, description="Errors for failed operations"
    )
    results: List[Any] = Field(
        default_factory=list, description="Results for successful operations"
    )


class WebhookPayload(BaseModel):
    """Base webhook payload model."""

    event: str = Field(..., description="Event type")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Event timestamp"
    )
    data: Dict[str, Any] = Field(..., description="Event data")
    source: str = Field(..., description="Event source")


class GitRefInfo(BaseModel):
    """Git reference information."""

    ref: str = Field(..., description="Git reference (branch/tag)")
    sha: str = Field(..., description="Commit SHA")
    url: Optional[str] = Field(None, description="Reference URL")


class GitCommitInfo(BaseModel):
    """Git commit information."""

    sha: str = Field(..., description="Commit SHA")
    message: str = Field(..., description="Commit message")
    author: str = Field(..., description="Commit author")
    timestamp: datetime = Field(..., description="Commit timestamp")
    url: Optional[str] = Field(None, description="Commit URL")


class GitRepositoryInfo(BaseModel):
    """Git repository information."""

    name: str = Field(..., description="Repository name")
    url: str = Field(..., description="Repository URL")
    branch: str = Field(..., description="Current branch")
    remote: Optional[str] = Field(None, description="Remote name")
    is_dirty: bool = Field(
        ..., description="Whether repository has uncommitted changes"
    )
    last_commit: Optional[GitCommitInfo] = Field(
        None, description="Last commit information"
    )


class LogEntry(BaseModel):
    """Log entry model."""

    level: str = Field(..., description="Log level")
    message: str = Field(..., description="Log message")
    timestamp: datetime = Field(..., description="Log timestamp")
    logger: str = Field(..., description="Logger name")
    extra: Optional[Dict[str, Any]] = Field(None, description="Additional log data")


class ConfigUpdate(BaseModel):
    """Configuration update model."""

    key: str = Field(..., description="Configuration key")
    value: Any = Field(..., description="Configuration value")
    description: Optional[str] = Field(None, description="Configuration description")
