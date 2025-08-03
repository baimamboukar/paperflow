"""
Template-related schemas for Paperflow API.

This module provides request and response models for template
and theme management operations.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .base import APIResponse


class TemplateType(str, Enum):
    """Template type enumeration."""

    ACADEMIC_PAPER = "academic_paper"
    THESIS = "thesis"
    ARTICLE = "article"
    BOOK = "book"
    PRESENTATION = "presentation"
    POSTER = "poster"
    LETTER = "letter"
    CV = "cv"
    CUSTOM = "custom"


class TemplateCategory(str, Enum):
    """Template category enumeration."""

    RESEARCH = "research"
    EDUCATION = "education"
    BUSINESS = "business"
    PERSONAL = "personal"
    TECHNICAL = "technical"
    CREATIVE = "creative"


class TemplateEngine(str, Enum):
    """Template engine enumeration."""

    LATEX = "latex"
    MARKDOWN = "markdown"
    HTML = "html"
    MIXED = "mixed"


class TemplateLicense(str, Enum):
    """Template license enumeration."""

    MIT = "mit"
    CC_BY = "cc_by"
    CC_BY_SA = "cc_by_sa"
    CC0 = "cc0"
    CUSTOM = "custom"
    PROPRIETARY = "proprietary"


class TemplateAuthor(BaseModel):
    """Template author information."""

    name: str = Field(..., description="Author name")
    email: Optional[str] = Field(None, description="Author email")
    url: Optional[str] = Field(None, description="Author website")
    affiliation: Optional[str] = Field(None, description="Author affiliation")


class TemplateFile(BaseModel):
    """Template file information."""

    path: str = Field(..., description="File path within template")
    type: str = Field(..., description="File type: tex, cls, sty, bib, figure, etc.")
    required: bool = Field(True, description="Whether file is required")
    description: Optional[str] = Field(None, description="File description")
    size: int = Field(..., description="File size in bytes")
    checksum: str = Field(..., description="File checksum")


class TemplateVariable(BaseModel):
    """Template variable configuration."""

    name: str = Field(..., description="Variable name")
    type: str = Field(..., description="Variable type: string, boolean, integer, etc.")
    default: Optional[Any] = Field(None, description="Default value")
    required: bool = Field(False, description="Whether variable is required")
    description: Optional[str] = Field(None, description="Variable description")
    options: Optional[List[Any]] = Field(None, description="Allowed values")
    validation: Optional[str] = Field(None, description="Validation pattern")


class TemplateMetadata(BaseModel):
    """Template metadata."""

    name: str = Field(..., description="Template name")
    display_name: str = Field(..., description="Human-readable template name")
    description: str = Field(..., description="Template description")
    version: str = Field(..., description="Template version")
    type: TemplateType = Field(..., description="Template type")
    category: TemplateCategory = Field(..., description="Template category")
    engine: TemplateEngine = Field(..., description="Template engine")
    license: TemplateLicense = Field(..., description="Template license")
    
    # Author information
    authors: List[TemplateAuthor] = Field(
        default_factory=list, description="Template authors"
    )
    
    # Tags and keywords
    tags: List[str] = Field(default_factory=list, description="Template tags")
    keywords: List[str] = Field(default_factory=list, description="Template keywords")
    
    # Compatibility
    latex_engines: List[str] = Field(
        default_factory=list, description="Compatible LaTeX engines"
    )
    required_packages: List[str] = Field(
        default_factory=list, description="Required LaTeX packages"
    )
    
    # Requirements
    min_latex_version: Optional[str] = Field(
        None, description="Minimum LaTeX version"
    )
    min_paperflow_version: Optional[str] = Field(
        None, description="Minimum Paperflow version"
    )
    
    # URLs
    homepage: Optional[str] = Field(None, description="Template homepage")
    repository: Optional[str] = Field(None, description="Source repository")
    documentation: Optional[str] = Field(None, description="Documentation URL")
    
    # Statistics
    downloads: int = Field(0, description="Download count")
    rating: float = Field(0.0, description="Average rating")
    rating_count: int = Field(0, description="Number of ratings")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class Template(BaseModel):
    """Complete template information."""

    metadata: TemplateMetadata = Field(..., description="Template metadata")
    files: List[TemplateFile] = Field(..., description="Template files")
    variables: List[TemplateVariable] = Field(
        default_factory=list, description="Template variables"
    )
    
    # Configuration
    build_config: Dict[str, Any] = Field(
        default_factory=dict, description="Default build configuration"
    )
    project_structure: Dict[str, Any] = Field(
        default_factory=dict, description="Project structure definition"
    )
    
    # Preview
    preview_images: List[str] = Field(
        default_factory=list, description="Preview image URLs"
    )
    example_output: Optional[str] = Field(
        None, description="Example output file URL"
    )


class TemplateSummary(BaseModel):
    """Template summary for listings."""

    name: str
    display_name: str
    description: str
    version: str
    type: TemplateType
    category: TemplateCategory
    engine: TemplateEngine
    license: TemplateLicense
    authors: List[str]  # Just author names
    tags: List[str]
    
    # Statistics
    downloads: int
    rating: float
    rating_count: int
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    # Preview
    preview_image: Optional[str] = Field(None, description="Main preview image")


class TemplateFilter(BaseModel):
    """Template filtering options."""

    type: Optional[TemplateType] = Field(None, description="Filter by type")
    category: Optional[TemplateCategory] = Field(None, description="Filter by category")
    engine: Optional[TemplateEngine] = Field(None, description="Filter by engine")
    license: Optional[TemplateLicense] = Field(None, description="Filter by license")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    author: Optional[str] = Field(None, description="Filter by author")
    search: Optional[str] = Field(None, description="Search query")
    min_rating: Optional[float] = Field(None, description="Minimum rating")
    latex_engine: Optional[str] = Field(None, description="Compatible LaTeX engine")


class TemplateSort(BaseModel):
    """Template sorting options."""

    sort_by: str = Field("updated_at", description="Sort field")
    sort_order: str = Field("desc", description="Sort order: asc, desc")

    @validator("sort_by")
    def validate_sort_field(cls, v):
        """Validate sort field."""
        allowed_fields = [
            "name", "display_name", "type", "category", "downloads", 
            "rating", "created_at", "updated_at"
        ]
        if v not in allowed_fields:
            raise ValueError(f"Invalid sort field. Allowed: {allowed_fields}")
        return v

    @validator("sort_order")
    def validate_sort_order(cls, v):
        """Validate sort order."""
        if v not in ["asc", "desc"]:
            raise ValueError("Sort order must be 'asc' or 'desc'")
        return v


class TemplateInstall(BaseModel):
    """Template installation request."""

    template_name: str = Field(..., description="Template name to install")
    version: Optional[str] = Field(None, description="Specific version to install")
    target_directory: Optional[str] = Field(
        None, description="Installation directory"
    )
    overwrite: bool = Field(False, description="Overwrite existing files")
    variables: Dict[str, Any] = Field(
        default_factory=dict, description="Template variable values"
    )


class TemplateApply(BaseModel):
    """Template application request."""

    template_name: str = Field(..., description="Template name to apply")
    project_name: str = Field(..., description="Target project name")
    variables: Dict[str, Any] = Field(
        default_factory=dict, description="Template variable values"
    )
    overwrite_existing: bool = Field(
        False, description="Overwrite existing project files"
    )
    backup_existing: bool = Field(
        True, description="Backup existing files before applying"
    )
    apply_build_config: bool = Field(
        True, description="Apply template build configuration"
    )


class TemplateCreate(BaseModel):
    """Template creation request."""

    metadata: TemplateMetadata = Field(..., description="Template metadata")
    source_type: str = Field(..., description="Source type: directory, zip, git")
    source_path: str = Field(..., description="Source path or URL")
    variables: List[TemplateVariable] = Field(
        default_factory=list, description="Template variables"
    )
    build_config: Dict[str, Any] = Field(
        default_factory=dict, description="Default build configuration"
    )

    @validator("source_type")
    def validate_source_type(cls, v):
        """Validate source type."""
        allowed_types = ["directory", "zip", "git"]
        if v not in allowed_types:
            raise ValueError(f"Invalid source type. Allowed: {allowed_types}")
        return v


class TemplateUpdate(BaseModel):
    """Template update request."""

    metadata: Optional[TemplateMetadata] = Field(None, description="Updated metadata")
    variables: Optional[List[TemplateVariable]] = Field(
        None, description="Updated variables"
    )
    build_config: Optional[Dict[str, Any]] = Field(
        None, description="Updated build configuration"
    )
    increment_version: bool = Field(True, description="Auto-increment version")


class TemplateValidation(BaseModel):
    """Template validation result."""

    valid: bool = Field(..., description="Whether template is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    
    # File validation
    missing_files: List[str] = Field(
        default_factory=list, description="Missing required files"
    )
    invalid_files: List[str] = Field(
        default_factory=list, description="Invalid or corrupted files"
    )
    
    # Variable validation
    invalid_variables: List[str] = Field(
        default_factory=list, description="Invalid variable definitions"
    )
    
    # LaTeX validation
    latex_errors: List[str] = Field(
        default_factory=list, description="LaTeX compilation errors"
    )
    missing_packages: List[str] = Field(
        default_factory=list, description="Missing LaTeX packages"
    )


class TemplateRating(BaseModel):
    """Template rating."""

    template_name: str = Field(..., description="Template name")
    rating: int = Field(..., ge=1, le=5, description="Rating (1-5 stars)")
    comment: Optional[str] = Field(None, description="Rating comment")
    user: str = Field(..., description="User who provided rating")
    created_at: datetime = Field(..., description="Rating timestamp")


class TemplateStats(BaseModel):
    """Template usage statistics."""

    total_templates: int = Field(..., description="Total number of templates")
    by_type: Dict[str, int] = Field(
        default_factory=dict, description="Templates by type"
    )
    by_category: Dict[str, int] = Field(
        default_factory=dict, description="Templates by category"
    )
    by_engine: Dict[str, int] = Field(
        default_factory=dict, description="Templates by engine"
    )
    
    # Usage statistics
    most_downloaded: List[TemplateSummary] = Field(
        default_factory=list, description="Most downloaded templates"
    )
    highest_rated: List[TemplateSummary] = Field(
        default_factory=list, description="Highest rated templates"
    )
    recently_updated: List[TemplateSummary] = Field(
        default_factory=list, description="Recently updated templates"
    )


# Response schemas
class TemplateResponse(APIResponse):
    """Response for template operations."""

    data: Template


class TemplateListResponse(APIResponse):
    """Response for template listing."""

    data: List[TemplateSummary]


class TemplateValidationResponse(APIResponse):
    """Response for template validation."""

    data: TemplateValidation


class TemplateStatsResponse(APIResponse):
    """Response for template statistics."""

    data: TemplateStats


class TemplateRatingResponse(APIResponse):
    """Response for template rating operations."""

    data: TemplateRating


class TemplateInstallResponse(APIResponse):
    """Response for template installation."""

    pass  # Just success/failure message


class TemplateApplyResponse(APIResponse):
    """Response for template application."""

    pass  # Just success/failure message