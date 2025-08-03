"""
Configuration data models for Paperflow.

This module defines specialized configuration models for different
aspects of the system including sync, build, and web configurations.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, validator

from paperflow.config.settings import LaTeXEngine, MathRenderer, OutputFormat, Theme


class SyncConfig(BaseModel):
    """Configuration for synchronization services."""

    # Overleaf settings
    overleaf_project_id: Optional[str] = Field(
        default=None, description="Overleaf project ID"
    )
    overleaf_git_url: Optional[HttpUrl] = Field(
        default=None, description="Overleaf Git repository URL"
    )
    overleaf_token: Optional[str] = Field(
        default=None, description="Overleaf API token"
    )

    # Git settings
    git_remote_url: Optional[HttpUrl] = Field(
        default=None, description="Git remote repository URL"
    )
    git_branch: str = Field(default="main", description="Git branch to sync")
    git_auto_commit: bool = Field(
        default=True, description="Automatically commit changes"
    )
    git_commit_message_template: str = Field(
        default="Update paper content", description="Template for auto-commit messages"
    )

    # Sync behavior
    sync_interval: int = Field(default=300, description="Sync interval in seconds")
    auto_sync: bool = Field(
        default=False, description="Enable automatic synchronization"
    )
    watch_files: List[str] = Field(
        default_factory=lambda: ["*.tex", "*.bib", "*.yaml", "*.yml"],
        description="File patterns to watch for changes",
    )

    # Conflict resolution
    conflict_resolution: str = Field(
        default="prompt",
        description="Conflict resolution strategy: prompt, local, remote",
    )
    backup_before_sync: bool = Field(
        default=True, description="Create backup before sync"
    )

    class Config:
        """Pydantic configuration."""

        validate_assignment = True

    @validator("sync_interval")
    def validate_sync_interval(cls, v):
        """Validate sync interval range."""
        if v < 60:
            raise ValueError("Sync interval must be at least 60 seconds")
        return v

    @validator("conflict_resolution")
    def validate_conflict_resolution(cls, v):
        """Validate conflict resolution strategy."""
        valid_strategies = {"prompt", "local", "remote"}
        if v not in valid_strategies:
            raise ValueError(f"Conflict resolution must be one of {valid_strategies}")
        return v


class BuildConfig(BaseModel):
    """Configuration for build processes."""

    # LaTeX settings
    latex_engine: LaTeXEngine = Field(
        default=LaTeXEngine.PDFLATEX, description="LaTeX compilation engine"
    )
    latex_options: List[str] = Field(
        default_factory=lambda: ["-interaction=nonstopmode", "-halt-on-error"],
        description="Additional LaTeX compilation options",
    )
    max_compile_attempts: int = Field(
        default=3, description="Maximum LaTeX compilation attempts"
    )

    # Output settings
    output_formats: List[OutputFormat] = Field(
        default_factory=lambda: [OutputFormat.HTML, OutputFormat.PDF],
        description="Output formats to generate",
    )
    output_directory: str = Field(default="dist", description="Output directory name")
    clean_before_build: bool = Field(
        default=True, description="Clean output directory before build"
    )

    # HTML generation settings
    html_template: Optional[str] = Field(
        default=None, description="Custom HTML template path"
    )
    css_framework: str = Field(default="custom", description="CSS framework to use")
    minify_output: bool = Field(default=True, description="Minify HTML/CSS/JS output")
    generate_sitemap: bool = Field(default=True, description="Generate sitemap.xml")

    # Asset processing
    optimize_images: bool = Field(default=True, description="Optimize image assets")
    image_formats: List[str] = Field(
        default_factory=lambda: ["webp", "png", "jpg"],
        description="Supported image formats",
    )

    # Performance settings
    parallel_processing: bool = Field(
        default=True, description="Enable parallel processing"
    )
    max_workers: Optional[int] = Field(
        default=None, description="Maximum worker threads"
    )
    cache_enabled: bool = Field(default=True, description="Enable build caching")

    class Config:
        """Pydantic configuration."""

        validate_assignment = True

    @validator("max_compile_attempts")
    def validate_compile_attempts(cls, v):
        """Validate compilation attempts range."""
        if not (1 <= v <= 10):
            raise ValueError("Max compile attempts must be between 1 and 10")
        return v

    @validator("max_workers")
    def validate_max_workers(cls, v):
        """Validate worker count."""
        if v is not None and v < 1:
            raise ValueError("Max workers must be at least 1")
        return v


class WebConfig(BaseModel):
    """Configuration for web interface and server."""

    # Server settings
    host: str = Field(default="localhost", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Enable debug mode")
    auto_reload: bool = Field(default=True, description="Enable auto-reload")

    # Website appearance
    theme: Theme = Field(default=Theme.SPRINGER_CLASSIC, description="Website theme")
    custom_css: Optional[str] = Field(default=None, description="Custom CSS file path")
    favicon: Optional[str] = Field(default=None, description="Favicon file path")
    logo: Optional[str] = Field(default=None, description="Logo file path")

    # Content settings
    show_pdf_download: bool = Field(default=True, description="Show PDF download link")
    show_source_code: bool = Field(default=True, description="Show source code links")
    show_bibtex: bool = Field(default=True, description="Show BibTeX citation")

    # Interactive features
    math_renderer: MathRenderer = Field(
        default=MathRenderer.KATEX, description="Math rendering engine"
    )
    syntax_highlighting: bool = Field(
        default=True, description="Enable syntax highlighting"
    )
    interactive_figures: bool = Field(
        default=True, description="Enable interactive figures"
    )
    figure_zoom: bool = Field(default=True, description="Enable figure zoom")
    equation_linking: bool = Field(
        default=True, description="Enable equation cross-linking"
    )

    # Navigation
    navigation_sections: Dict[str, bool] = Field(
        default_factory=lambda: {
            "abstract": True,
            "authors": True,
            "sections": True,
            "references": True,
            "appendix": True,
        },
        description="Navigation sections to show",
    )

    # Social and sharing
    enable_sharing: bool = Field(default=True, description="Enable social sharing")
    twitter_handle: Optional[str] = Field(
        default=None, description="Twitter handle for sharing"
    )
    github_repo: Optional[HttpUrl] = Field(
        default=None, description="GitHub repository URL"
    )

    # Analytics and tracking
    google_analytics: Optional[str] = Field(
        default=None, description="Google Analytics tracking ID"
    )
    enable_comments: bool = Field(default=False, description="Enable comments system")

    # Performance
    enable_caching: bool = Field(default=True, description="Enable response caching")
    cache_duration: int = Field(default=3600, description="Cache duration in seconds")
    compress_responses: bool = Field(
        default=True, description="Enable response compression"
    )

    class Config:
        """Pydantic configuration."""

        validate_assignment = True

    @validator("port")
    def validate_port(cls, v):
        """Validate port number range."""
        if not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v

    @validator("cache_duration")
    def validate_cache_duration(cls, v):
        """Validate cache duration."""
        if v < 0:
            raise ValueError("Cache duration must be non-negative")
        return v


class DeployConfig(BaseModel):
    """Configuration for deployment targets."""

    # GitHub Pages
    github_pages_enabled: bool = Field(
        default=False, description="Enable GitHub Pages deployment"
    )
    github_repo: Optional[str] = Field(
        default=None, description="GitHub repository (owner/repo)"
    )
    github_branch: str = Field(default="gh-pages", description="GitHub Pages branch")
    custom_domain: Optional[str] = Field(
        default=None, description="Custom domain for GitHub Pages"
    )

    # Netlify
    netlify_enabled: bool = Field(
        default=False, description="Enable Netlify deployment"
    )
    netlify_site_id: Optional[str] = Field(default=None, description="Netlify site ID")
    netlify_token: Optional[str] = Field(
        default=None, description="Netlify access token"
    )

    # Vercel
    vercel_enabled: bool = Field(default=False, description="Enable Vercel deployment")
    vercel_project_id: Optional[str] = Field(
        default=None, description="Vercel project ID"
    )
    vercel_token: Optional[str] = Field(default=None, description="Vercel access token")

    # Custom deployment
    custom_enabled: bool = Field(default=False, description="Enable custom deployment")
    custom_command: Optional[str] = Field(
        default=None, description="Custom deployment command"
    )
    custom_target: Optional[str] = Field(
        default=None, description="Custom deployment target"
    )

    # Deployment settings
    auto_deploy: bool = Field(default=False, description="Enable automatic deployment")
    deploy_on_build: bool = Field(
        default=True, description="Deploy after successful build"
    )
    include_source: bool = Field(
        default=False, description="Include source files in deployment"
    )

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
