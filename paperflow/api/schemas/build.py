"""
Build-related schemas for Paperflow API.

This module provides request and response models for build
operations and LaTeX compilation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .base import APIResponse, TaskInfo


class BuildTarget(str, Enum):
    """Build target enumeration."""

    PDF = "pdf"
    HTML = "html"
    EPUB = "epub"
    DOCX = "docx"
    ALL = "all"


class BuildStatus(str, Enum):
    """Build status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BuildEngine(str, Enum):
    """LaTeX build engine enumeration."""

    PDFLATEX = "pdflatex"
    XELATEX = "xelatex"
    LUALATEX = "lualatex"
    TECTONIC = "tectonic"


class BuildRequest(BaseModel):
    """Build request schema."""

    target: BuildTarget = Field(BuildTarget.PDF, description="Build target format")
    engine: BuildEngine = Field(
        BuildEngine.PDFLATEX, description="LaTeX compilation engine"
    )
    clean_first: bool = Field(False, description="Clean auxiliary files before build")
    force_rebuild: bool = Field(False, description="Force complete rebuild")
    include_bibliography: bool = Field(True, description="Include bibliography compilation")
    max_runs: int = Field(3, description="Maximum number of LaTeX runs")
    timeout: int = Field(300, description="Build timeout in seconds")
    
    # Output options
    output_directory: Optional[str] = Field(
        None, description="Custom output directory"
    )
    filename: Optional[str] = Field(None, description="Custom output filename")
    
    # Advanced options
    shell_escape: bool = Field(False, description="Enable shell escape")
    draft_mode: bool = Field(False, description="Enable draft mode")
    halt_on_error: bool = Field(True, description="Halt on first error")
    interaction_mode: str = Field("nonstopmode", description="LaTeX interaction mode")

    @validator("max_runs")
    def validate_max_runs(cls, v):
        """Validate maximum runs."""
        if v < 1 or v > 10:
            raise ValueError("max_runs must be between 1 and 10")
        return v

    @validator("timeout")
    def validate_timeout(cls, v):
        """Validate timeout."""
        if v < 30 or v > 3600:
            raise ValueError("timeout must be between 30 and 3600 seconds")
        return v

    @validator("interaction_mode")
    def validate_interaction_mode(cls, v):
        """Validate interaction mode."""
        allowed_modes = ["nonstopmode", "batchmode", "scrollmode", "errorstopmode"]
        if v not in allowed_modes:
            raise ValueError(f"interaction_mode must be one of: {allowed_modes}")
        return v


class BuildLogEntry(BaseModel):
    """Build log entry."""

    level: str = Field(..., description="Log level: info, warning, error")
    message: str = Field(..., description="Log message")
    timestamp: datetime = Field(..., description="Log timestamp")
    file: Optional[str] = Field(None, description="Source file if applicable")
    line: Optional[int] = Field(None, description="Line number if applicable")
    column: Optional[int] = Field(None, description="Column number if applicable")


class BuildError(BaseModel):
    """Build error information."""

    type: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    file: Optional[str] = Field(None, description="File where error occurred")
    line: Optional[int] = Field(None, description="Line number")
    column: Optional[int] = Field(None, description="Column number")
    context: Optional[str] = Field(None, description="Error context")
    suggestion: Optional[str] = Field(None, description="Suggested fix")


class BuildWarning(BaseModel):
    """Build warning information."""

    type: str = Field(..., description="Warning type")
    message: str = Field(..., description="Warning message")
    file: Optional[str] = Field(None, description="File where warning occurred")
    line: Optional[int] = Field(None, description="Line number")
    severity: str = Field("medium", description="Warning severity")


class BuildResult(BaseModel):
    """Build operation result."""

    success: bool = Field(..., description="Whether build was successful")
    status: BuildStatus = Field(..., description="Build status")
    target: BuildTarget = Field(..., description="Build target")
    engine: BuildEngine = Field(..., description="LaTeX engine used")
    
    # Output information
    output_files: List[str] = Field(
        default_factory=list, description="Generated output files"
    )
    output_size: int = Field(0, description="Total output size in bytes")
    main_output: Optional[str] = Field(None, description="Main output file path")
    
    # Build statistics
    latex_runs: int = Field(0, description="Number of LaTeX runs")
    bibtex_runs: int = Field(0, description="Number of BibTeX runs")
    makeindex_runs: int = Field(0, description="Number of makeindex runs")
    
    # Timing
    started_at: datetime = Field(..., description="Build start time")
    completed_at: Optional[datetime] = Field(None, description="Build completion time")
    duration: Optional[float] = Field(None, description="Build duration in seconds")
    
    # Logs and errors
    logs: List[BuildLogEntry] = Field(default_factory=list, description="Build logs")
    errors: List[BuildError] = Field(default_factory=list, description="Build errors")
    warnings: List[BuildWarning] = Field(
        default_factory=list, description="Build warnings"
    )
    
    # Resource usage
    memory_usage: Optional[int] = Field(None, description="Peak memory usage in MB")
    cpu_time: Optional[float] = Field(None, description="CPU time in seconds")
    
    # Messages
    message: Optional[str] = Field(None, description="Build result message")
    exit_code: int = Field(0, description="Process exit code")


class BuildInfo(BaseModel):
    """Build information and metadata."""

    build_id: str = Field(..., description="Unique build identifier")
    project_name: str = Field(..., description="Project name")
    status: BuildStatus = Field(..., description="Current build status")
    target: BuildTarget = Field(..., description="Build target")
    engine: BuildEngine = Field(..., description="LaTeX engine")
    initiated_by: str = Field(..., description="Who initiated the build")
    
    # Progress
    progress: Optional[int] = Field(
        None, ge=0, le=100, description="Build progress percentage"
    )
    current_step: Optional[str] = Field(None, description="Current build step")
    
    # Timing
    created_at: datetime = Field(..., description="Build creation time")
    started_at: Optional[datetime] = Field(None, description="Build start time")
    completed_at: Optional[datetime] = Field(None, description="Build completion time")
    
    # Result
    result: Optional[BuildResult] = Field(None, description="Build result if completed")


class BuildQueue(BaseModel):
    """Build queue information."""

    total_builds: int = Field(..., description="Total builds in queue")
    pending_builds: int = Field(..., description="Pending builds")
    running_builds: int = Field(..., description="Currently running builds")
    queue_position: Optional[int] = Field(None, description="Position in queue")
    estimated_wait: Optional[int] = Field(
        None, description="Estimated wait time in seconds"
    )


class BuildStats(BaseModel):
    """Build statistics."""

    total_builds: int = Field(..., description="Total number of builds")
    successful_builds: int = Field(..., description="Number of successful builds")
    failed_builds: int = Field(..., description="Number of failed builds")
    average_duration: float = Field(..., description="Average build duration")
    success_rate: float = Field(..., description="Build success rate")
    
    # Recent activity
    builds_today: int = Field(..., description="Builds completed today")
    builds_this_week: int = Field(..., description="Builds completed this week")
    builds_this_month: int = Field(..., description="Builds completed this month")
    
    # Engine statistics
    engine_usage: Dict[str, int] = Field(
        default_factory=dict, description="Usage count by engine"
    )
    target_usage: Dict[str, int] = Field(
        default_factory=dict, description="Usage count by target"
    )


class BuildConfig(BaseModel):
    """Build configuration schema."""

    default_engine: BuildEngine = Field(
        BuildEngine.PDFLATEX, description="Default LaTeX engine"
    )
    default_target: BuildTarget = Field(
        BuildTarget.PDF, description="Default build target"
    )
    max_concurrent_builds: int = Field(
        2, description="Maximum concurrent builds"
    )
    build_timeout: int = Field(300, description="Default build timeout")
    clean_after_build: bool = Field(True, description="Clean auxiliary files after build")
    preserve_logs: bool = Field(True, description="Preserve build logs")
    log_retention_days: int = Field(30, description="Log retention period")

    @validator("max_concurrent_builds")
    def validate_max_concurrent(cls, v):
        """Validate maximum concurrent builds."""
        if v < 1 or v > 10:
            raise ValueError("max_concurrent_builds must be between 1 and 10")
        return v


class BuildWebSocketMessage(BaseModel):
    """WebSocket message for build updates."""

    type: str = Field(..., description="Message type")
    build_id: str = Field(..., description="Build ID")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Message timestamp"
    )
    data: Dict[str, Any] = Field(..., description="Message data")


# Response schemas
class BuildRequestResponse(APIResponse):
    """Response for build request."""

    data: TaskInfo


class BuildStatusResponse(APIResponse):
    """Response for build status."""

    data: BuildInfo


class BuildResultResponse(APIResponse):
    """Response for build result."""

    data: BuildResult


class BuildLogsResponse(APIResponse):
    """Response for build logs."""

    data: List[BuildLogEntry]


class BuildQueueResponse(APIResponse):
    """Response for build queue status."""

    data: BuildQueue


class BuildStatsResponse(APIResponse):
    """Response for build statistics."""

    data: BuildStats


class BuildConfigResponse(APIResponse):
    """Response for build configuration."""

    data: BuildConfig