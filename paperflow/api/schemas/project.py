"""
Project-related schemas for Paperflow API.

This module provides request and response models for project
management operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from paperflow.models.project import ProjectStatus, ProjectType

from .base import APIResponse, FilterParams, PaginatedResponse, SortParams


class AuthorCreate(BaseModel):
    """Schema for creating an author."""

    name: str = Field(..., description="Author full name")
    email: Optional[str] = Field(None, description="Author email")
    affiliation: Optional[str] = Field(None, description="Author affiliation")
    orcid: Optional[str] = Field(None, description="ORCID identifier")

    @validator("email")
    def validate_email(cls, v):
        """Validate email format."""
        if v and "@" not in v:
            raise ValueError("Invalid email format")
        return v


class AuthorResponse(BaseModel):
    """Schema for author response."""

    name: str
    email: Optional[str] = None
    affiliation: Optional[str] = None
    orcid: Optional[str] = None

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""

    name: str = Field(..., description="Project name")
    title: str = Field(..., description="Paper title")
    abstract: str = Field(default="", description="Paper abstract")
    keywords: List[str] = Field(default_factory=list, description="Paper keywords")
    project_type: ProjectType = Field(
        default=ProjectType.RESEARCH_PAPER, description="Project type"
    )
    language: str = Field(default="en", description="Paper language")
    authors: List[AuthorCreate] = Field(
        default_factory=list, description="Project authors"
    )
    corresponding_author: Optional[str] = Field(
        None, description="Corresponding author name"
    )

    # Publication information
    arxiv_id: Optional[str] = Field(None, description="ArXiv ID")
    doi: Optional[str] = Field(None, description="DOI")
    journal: Optional[str] = Field(None, description="Journal name")
    conference: Optional[str] = Field(None, description="Conference name")

    # File configuration
    main_tex_file: str = Field(default="main.tex", description="Main LaTeX file")
    bibliography_file: Optional[str] = Field(
        default="bibliography.bib", description="Bibliography file"
    )

    # Custom path (optional)
    project_path: Optional[str] = Field(None, description="Custom project path")

    @validator("name")
    def validate_name(cls, v):
        """Validate project name."""
        if not v or len(v.strip()) < 1:
            raise ValueError("Project name cannot be empty")

        invalid_chars = '<>:"/\\|?*'
        if any(char in v for char in invalid_chars):
            raise ValueError(f"Project name cannot contain: {invalid_chars}")

        return v.strip()

    @validator("title")
    def validate_title(cls, v):
        """Validate paper title."""
        if not v or len(v.strip()) < 1:
            raise ValueError("Paper title cannot be empty")
        return v.strip()


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    title: Optional[str] = Field(None, description="Paper title")
    abstract: Optional[str] = Field(None, description="Paper abstract")
    keywords: Optional[List[str]] = Field(None, description="Paper keywords")
    status: Optional[ProjectStatus] = Field(None, description="Project status")
    language: Optional[str] = Field(None, description="Paper language")
    corresponding_author: Optional[str] = Field(
        None, description="Corresponding author name"
    )

    # Publication information
    arxiv_id: Optional[str] = Field(None, description="ArXiv ID")
    doi: Optional[str] = Field(None, description="DOI")
    journal: Optional[str] = Field(None, description="Journal name")
    conference: Optional[str] = Field(None, description="Conference name")

    # File configuration
    main_tex_file: Optional[str] = Field(None, description="Main LaTeX file")
    bibliography_file: Optional[str] = Field(None, description="Bibliography file")


class ProjectResponse(BaseModel):
    """Schema for project response."""

    name: str
    title: str
    abstract: str
    keywords: List[str]
    project_type: ProjectType
    status: ProjectStatus
    language: str
    authors: List[AuthorResponse]
    corresponding_author: Optional[str] = None

    # Publication information
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    journal: Optional[str] = None
    conference: Optional[str] = None
    publication_date: Optional[datetime] = None

    # File information
    project_path: str
    main_tex_file: str
    bibliography_file: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_build: Optional[datetime] = None
    last_sync: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProjectSummary(BaseModel):
    """Schema for project summary (used in lists)."""

    name: str
    title: str
    status: ProjectStatus
    project_type: ProjectType
    authors_count: int
    has_abstract: bool
    keywords_count: int
    created_at: datetime
    updated_at: datetime
    last_build: Optional[datetime] = None
    last_sync: Optional[datetime] = None


class ProjectFilters(FilterParams):
    """Extended filters for project listing."""

    status: Optional[ProjectStatus] = Field(
        None, description="Filter by project status"
    )
    project_type: Optional[ProjectType] = Field(
        None, description="Filter by project type"
    )
    has_authors: Optional[bool] = Field(
        None, description="Filter projects with/without authors"
    )
    has_abstract: Optional[bool] = Field(
        None, description="Filter projects with/without abstract"
    )
    language: Optional[str] = Field(None, description="Filter by language")


class ProjectSort(SortParams):
    """Sort parameters for project listing."""

    sort_by: Optional[str] = Field("updated_at", description="Field to sort by")

    @validator("sort_by")
    def validate_sort_field(cls, v):
        """Validate sort field."""
        allowed_fields = [
            "name",
            "title",
            "status",
            "project_type",
            "created_at",
            "updated_at",
            "last_build",
            "last_sync",
        ]
        if v and v not in allowed_fields:
            raise ValueError(f"Invalid sort field. Allowed: {allowed_fields}")
        return v


class ProjectListResponse(PaginatedResponse):
    """Response for project listing."""

    items: List[ProjectSummary]


class ProjectValidation(BaseModel):
    """Project validation results."""

    valid: bool
    errors: List[str]
    warnings: List[str]
    file_checks: Dict[str, bool]
    structure_checks: Dict[str, bool]


class ProjectStats(BaseModel):
    """Project statistics."""

    total_projects: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    recent_activity: List[Dict[str, Any]]
    build_success_rate: float
    sync_success_rate: float


class AuthorManagement(BaseModel):
    """Schema for managing project authors."""

    action: str = Field(..., description="Action: add, remove, update")
    author: Optional[AuthorCreate] = Field(
        None, description="Author data for add/update"
    )
    author_name: Optional[str] = Field(
        None, description="Author name for remove/update"
    )

    @validator("action")
    def validate_action(cls, v):
        """Validate action type."""
        allowed_actions = ["add", "remove", "update"]
        if v not in allowed_actions:
            raise ValueError(f"Invalid action. Allowed: {allowed_actions}")
        return v


class ProjectExport(BaseModel):
    """Schema for project export configuration."""

    format: str = Field(..., description="Export format: zip, tar, pdf")
    include_source: bool = Field(True, description="Include LaTeX source files")
    include_build: bool = Field(True, description="Include build outputs")
    include_assets: bool = Field(True, description="Include assets and figures")
    include_config: bool = Field(True, description="Include configuration files")

    @validator("format")
    def validate_format(cls, v):
        """Validate export format."""
        allowed_formats = ["zip", "tar", "pdf"]
        if v not in allowed_formats:
            raise ValueError(f"Invalid format. Allowed: {allowed_formats}")
        return v


class ProjectImport(BaseModel):
    """Schema for project import configuration."""

    source_type: str = Field(..., description="Import source: file, url, overleaf")
    source_data: str = Field(..., description="Source location or data")
    project_name: Optional[str] = Field(None, description="Custom project name")
    overwrite: bool = Field(False, description="Overwrite existing project")

    @validator("source_type")
    def validate_source_type(cls, v):
        """Validate source type."""
        allowed_types = ["file", "url", "overleaf"]
        if v not in allowed_types:
            raise ValueError(f"Invalid source type. Allowed: {allowed_types}")
        return v


class ProjectArchive(BaseModel):
    """Schema for project archiving."""

    archive: bool = Field(..., description="Archive or unarchive project")
    reason: Optional[str] = Field(None, description="Reason for archiving")


class ProjectClone(BaseModel):
    """Schema for project cloning."""

    new_name: str = Field(..., description="Name for cloned project")
    include_files: bool = Field(True, description="Include source files")
    include_config: bool = Field(True, description="Include configuration")
    reset_timestamps: bool = Field(True, description="Reset creation/update timestamps")


class ProjectFileUpload(BaseModel):
    """Schema for file upload to project."""

    file_type: str = Field(..., description="File type: tex, bib, figure, asset")
    overwrite: bool = Field(False, description="Overwrite existing file")
    destination: Optional[str] = Field(None, description="Custom destination path")

    @validator("file_type")
    def validate_file_type(cls, v):
        """Validate file type."""
        allowed_types = ["tex", "bib", "figure", "asset"]
        if v not in allowed_types:
            raise ValueError(f"Invalid file type. Allowed: {allowed_types}")
        return v


class ProjectFileResponse(BaseModel):
    """Response for project file operations."""

    filename: str
    path: str
    size: int
    mime_type: str
    uploaded_at: datetime
    checksum: str


class ProjectTemplateApply(BaseModel):
    """Schema for applying template to project."""

    template_name: str = Field(..., description="Template name to apply")
    overwrite_existing: bool = Field(False, description="Overwrite existing files")
    backup_existing: bool = Field(
        True, description="Backup existing files before applying"
    )


# Response schemas
class ProjectCreateResponse(APIResponse):
    """Response for project creation."""

    data: ProjectResponse


class ProjectDetailResponse(APIResponse):
    """Response for project details."""

    data: ProjectResponse


class ProjectUpdateResponse(APIResponse):
    """Response for project update."""

    data: ProjectResponse


class ProjectDeleteResponse(APIResponse):
    """Response for project deletion."""

    pass


class ProjectValidationResponse(APIResponse):
    """Response for project validation."""

    data: ProjectValidation


class ProjectStatsResponse(APIResponse):
    """Response for project statistics."""

    data: ProjectStats
