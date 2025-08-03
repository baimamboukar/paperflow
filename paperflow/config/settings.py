"""
Core configuration settings for Paperflow.

This module defines the main settings structure using Pydantic for validation
and type safety. It handles loading configuration from various sources and
provides runtime validation.
"""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class LaTeXEngine(str, Enum):
    """Supported LaTeX engines."""

    PDFLATEX = "pdflatex"
    XELATEX = "xelatex"
    LUALATEX = "lualatex"


class OutputFormat(str, Enum):
    """Supported output formats."""

    HTML = "html"
    PDF = "pdf"


class MathRenderer(str, Enum):
    """Supported math rendering engines."""

    KATEX = "katex"
    MATHJAX = "mathjax"


class Theme(str, Enum):
    """Available website themes."""

    MIDNIGHT_SCHOLAR = "midnight-scholar"
    CORAL_REEF = "coral-reef"
    ZEN_GARDEN = "zen-garden"
    COSMIC_LAB = "cosmic-lab"
    SPRINGER_CLASSIC = "springer-classic"


class Settings(BaseSettings):
    """
    Main settings configuration for Paperflow.

    This class defines all configuration options with proper validation
    and default values. Settings can be loaded from environment variables,
    YAML files, or provided directly.
    """

    # Project Information
    project_name: str = Field(default="paperflow-project", description="Project name")
    project_path: Path = Field(default=Path.cwd(), description="Project root directory")
    config_file: str = Field(
        default="config.yaml", description="Configuration file name"
    )

    # Paper Information
    paper_title: str = Field(default="", description="Paper title")
    paper_abstract: str = Field(default="", description="Paper abstract")
    paper_keywords: List[str] = Field(
        default_factory=list, description="Paper keywords"
    )
    paper_arxiv_id: Optional[str] = Field(default=None, description="ArXiv paper ID")
    paper_doi: Optional[str] = Field(default=None, description="Paper DOI")

    # Authors
    authors: List[Dict[str, Any]] = Field(
        default_factory=list, description="Paper authors"
    )

    # Overleaf Integration
    overleaf_project_id: Optional[str] = Field(
        default=None, description="Overleaf project ID"
    )
    overleaf_git_url: Optional[str] = Field(
        default=None, description="Overleaf Git URL"
    )

    # Website Settings
    website_theme: Theme = Field(
        default=Theme.SPRINGER_CLASSIC, description="Website theme"
    )
    website_show_pdf: bool = Field(default=True, description="Show PDF download link")
    website_interactive_figures: bool = Field(
        default=True, description="Enable interactive figures"
    )
    website_math_renderer: MathRenderer = Field(
        default=MathRenderer.KATEX, description="Math rendering engine"
    )
    website_syntax_highlighting: bool = Field(
        default=True, description="Enable syntax highlighting"
    )

    # Navigation Settings
    nav_show_abstract: bool = Field(
        default=True, description="Show abstract in navigation"
    )
    nav_show_authors: bool = Field(
        default=True, description="Show authors in navigation"
    )
    nav_show_bibtex: bool = Field(default=True, description="Show BibTeX in navigation")
    nav_show_code: bool = Field(default=True, description="Show code in navigation")
    nav_show_supplementary: bool = Field(
        default=True, description="Show supplementary in navigation"
    )

    # Social Media
    social_twitter_handle: Optional[str] = Field(
        default=None, description="Twitter handle"
    )
    social_github_repo: Optional[str] = Field(
        default=None, description="GitHub repository"
    )

    # GitHub Integration
    github_token: Optional[str] = Field(
        default=None, description="GitHub Personal Access Token"
    )
    github_username: Optional[str] = Field(default=None, description="GitHub username")
    github_organization: Optional[str] = Field(
        default=None, description="GitHub organization name"
    )

    # GitHub Pages
    pages_custom_domain: Optional[str] = Field(
        default=None, description="Custom domain for GitHub Pages"
    )
    pages_cname: bool = Field(default=False, description="Enable CNAME file")
    pages_source_branch: str = Field(
        default="gh-pages", description="GitHub Pages source branch"
    )
    pages_source_path: str = Field(default="/", description="GitHub Pages source path")
    pages_enforce_https: bool = Field(
        default=True, description="Enforce HTTPS for GitHub Pages"
    )

    # GitHub Repository Settings
    github_repo_private: bool = Field(
        default=False, description="Create private repositories by default"
    )
    github_repo_auto_init: bool = Field(
        default=True, description="Auto-initialize repositories with README"
    )
    github_repo_gitignore_template: Optional[str] = Field(
        default="TeX", description="Default gitignore template"
    )
    github_repo_license_template: Optional[str] = Field(
        default="MIT", description="Default license template"
    )
    github_enable_issues: bool = Field(
        default=True, description="Enable issues on repositories"
    )
    github_enable_projects: bool = Field(
        default=True, description="Enable projects on repositories"
    )
    github_enable_wiki: bool = Field(
        default=True, description="Enable wiki on repositories"
    )
    github_enable_pages: bool = Field(
        default=True, description="Enable GitHub Pages by default"
    )

    # GitHub Webhooks
    github_webhook_url: Optional[str] = Field(
        default=None, description="Default webhook URL"
    )
    github_webhook_secret: Optional[str] = Field(
        default=None, description="Default webhook secret"
    )
    github_webhook_events: List[str] = Field(
        default_factory=lambda: ["push", "pull_request", "issues"],
        description="Default webhook events",
    )

    # Build Settings
    build_latex_engine: LaTeXEngine = Field(
        default=LaTeXEngine.PDFLATEX, description="LaTeX engine"
    )
    build_output_formats: List[OutputFormat] = Field(
        default_factory=lambda: [OutputFormat.HTML, OutputFormat.PDF],
        description="Output formats",
    )
    build_output_dir: str = Field(default="dist", description="Build output directory")
    build_clean_before: bool = Field(
        default=True, description="Clean output directory before build"
    )

    # Interactive Features
    interactive_comments: bool = Field(default=False, description="Enable comments")
    interactive_annotations: bool = Field(
        default=True, description="Enable annotations"
    )
    interactive_figure_zoom: bool = Field(
        default=True, description="Enable figure zoom"
    )
    interactive_equation_links: bool = Field(
        default=True, description="Enable equation links"
    )

    # Development Settings
    dev_host: str = Field(default="localhost", description="Development server host")
    dev_port: int = Field(default=8000, description="Development server port")
    dev_debug: bool = Field(default=False, description="Enable debug mode")
    dev_auto_reload: bool = Field(default=True, description="Enable auto-reload")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Log file path")

    class Config:
        """Pydantic configuration."""

        env_prefix = "PAPERFLOW_"
        case_sensitive = False
        validate_assignment = True
        arbitrary_types_allowed = True

    @validator("project_path", pre=True)
    def validate_project_path(cls, v):
        """Validate and convert project path to Path object."""
        if isinstance(v, str):
            return Path(v).resolve()
        elif isinstance(v, Path):
            return v.resolve()
        else:
            raise ValueError("project_path must be a string or Path object")

    @validator("paper_keywords", pre=True)
    def validate_keywords(cls, v):
        """Validate and clean keywords list."""
        if isinstance(v, str):
            return [kw.strip() for kw in v.split(",") if kw.strip()]
        elif isinstance(v, list):
            return [str(kw).strip() for kw in v if str(kw).strip()]
        else:
            return []

    @validator("dev_port")
    def validate_port(cls, v):
        """Validate port number range."""
        if not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()

    def get_output_path(self) -> Path:
        """Get the full output directory path."""
        return self.project_path / self.build_output_dir

    def get_config_path(self) -> Path:
        """Get the full configuration file path."""
        return self.project_path / self.config_file

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return self.dict(exclude_none=True)

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update settings from dictionary."""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
