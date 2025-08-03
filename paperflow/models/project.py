"""
Project data model for Paperflow.

This module defines the main Project model that represents a complete
academic paper project with all its components and configurations.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from enum import Enum

from paperflow.models.author import Author
from paperflow.models.config import SyncConfig, BuildConfig, WebConfig, DeployConfig


class ProjectStatus(str, Enum):
    """Project status enumeration."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"  
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ProjectType(str, Enum):
    """Project type enumeration."""
    RESEARCH_PAPER = "research_paper"
    CONFERENCE_PAPER = "conference_paper"
    JOURNAL_ARTICLE = "journal_article"
    THESIS = "thesis"
    DISSERTATION = "dissertation"
    REPORT = "report"
    PREPRINT = "preprint"


class Project(BaseModel):
    """
    Main project model representing a complete academic paper project.
    
    This model contains all information about a paper project including
    metadata, authors, configurations, and project state.
    """
    
    # Basic project information
    name: str = Field(..., description="Project name")
    title: str = Field(..., description="Paper title")
    abstract: str = Field(default="", description="Paper abstract")
    keywords: List[str] = Field(default_factory=list, description="Paper keywords")
    
    # Project metadata
    project_type: ProjectType = Field(default=ProjectType.RESEARCH_PAPER, description="Type of project")
    status: ProjectStatus = Field(default=ProjectStatus.DRAFT, description="Project status")
    language: str = Field(default="en", description="Paper language (ISO 639-1 code)")
    
    # Authors
    authors: List[Author] = Field(default_factory=list, description="Paper authors")
    corresponding_author: Optional[str] = Field(default=None, description="Corresponding author name")
    
    # Publication information
    arxiv_id: Optional[str] = Field(default=None, description="ArXiv paper ID")
    doi: Optional[str] = Field(default=None, description="Digital Object Identifier")
    journal: Optional[str] = Field(default=None, description="Journal name")
    conference: Optional[str] = Field(default=None, description="Conference name")
    publication_date: Optional[datetime] = Field(default=None, description="Publication date")
    
    # File paths
    project_path: Path = Field(..., description="Project root directory")
    main_tex_file: str = Field(default="main.tex", description="Main LaTeX file")
    bibliography_file: Optional[str] = Field(default="bibliography.bib", description="Bibliography file")
    
    # Configuration
    sync_config: SyncConfig = Field(default_factory=SyncConfig, description="Synchronization settings")
    build_config: BuildConfig = Field(default_factory=BuildConfig, description="Build settings")
    web_config: WebConfig = Field(default_factory=WebConfig, description="Web interface settings")
    deploy_config: DeployConfig = Field(default_factory=DeployConfig, description="Deployment settings")
    
    # Project timestamps
    created_at: datetime = Field(default_factory=datetime.now, description="Project creation time")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update time")
    last_build: Optional[datetime] = Field(default=None, description="Last successful build time")
    last_sync: Optional[datetime] = Field(default=None, description="Last synchronization time")
    
    # Custom fields for extensibility
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Custom project fields")
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Path: lambda v: str(v)
        }
    
    @validator("name")
    def validate_name(cls, v):
        """Validate project name format."""
        if not v or len(v.strip()) < 1:
            raise ValueError("Project name cannot be empty")
        
        # Remove problematic characters for file systems
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
    
    @validator("language")
    def validate_language(cls, v):
        """Validate language code."""
        # Basic validation for ISO 639-1 codes (2 characters)
        if len(v) != 2 or not v.isalpha():
            raise ValueError("Language must be a valid ISO 639-1 code (e.g., 'en', 'es')")
        
        return v.lower()
    
    @validator("project_path", pre=True)
    def validate_project_path(cls, v):
        """Validate and convert project path."""
        if isinstance(v, str):
            return Path(v).resolve()
        elif isinstance(v, Path):
            return v.resolve()
        else:
            raise ValueError("project_path must be a string or Path object")
    
    @validator("corresponding_author")
    def validate_corresponding_author(cls, v, values):
        """Validate corresponding author exists in authors list."""
        if v is None:
            return v
        
        authors = values.get("authors", [])
        author_names = [author.name for author in authors]
        
        if v not in author_names:
            raise ValueError("Corresponding author must be in the authors list")
        
        return v
    
    def get_main_tex_path(self) -> Path:
        """Get full path to main LaTeX file."""
        return self.project_path / self.main_tex_file
    
    def get_bibliography_path(self) -> Optional[Path]:
        """Get full path to bibliography file."""
        if self.bibliography_file:
            return self.project_path / self.bibliography_file
        return None
    
    def get_output_path(self) -> Path:
        """Get full path to build output directory."""
        return self.project_path / self.build_config.output_directory
    
    def add_author(self, author: Author) -> None:
        """Add an author to the project."""
        if author not in self.authors:
            self.authors.append(author)
            self.touch()
    
    def remove_author(self, author_name: str) -> bool:
        """Remove an author by name."""
        for i, author in enumerate(self.authors):
            if author.name == author_name:
                del self.authors[i]
                # Clear corresponding author if it was the removed author
                if self.corresponding_author == author_name:
                    self.corresponding_author = None
                self.touch()
                return True
        return False
    
    def get_corresponding_author(self) -> Optional[Author]:
        """Get the corresponding author object."""
        if self.corresponding_author:
            for author in self.authors:
                if author.name == self.corresponding_author:
                    return author
        return None
    
    def touch(self) -> None:
        """Update the last modified timestamp."""
        self.updated_at = datetime.now()
    
    def mark_built(self) -> None:
        """Mark project as successfully built."""
        self.last_build = datetime.now()
        self.touch()
    
    def mark_synced(self) -> None:
        """Mark project as synchronized."""
        self.last_sync = datetime.now()
        self.touch()
    
    def get_citation_authors(self) -> str:
        """Get formatted author list for citations."""
        if not self.authors:
            return ""
        
        if len(self.authors) == 1:
            return self.authors[0].get_citation_name()
        elif len(self.authors) == 2:
            return f"{self.authors[0].get_citation_name()} and {self.authors[1].get_citation_name()}"
        else:
            # Three or more authors
            first_author = self.authors[0].get_citation_name()
            return f"{first_author} et al."
    
    def to_bibtex_entry(self, entry_type: str = "article") -> str:
        """Generate BibTeX entry for the project."""
        # Generate a simple citation key
        if self.authors:
            first_author_surname = self.authors[0].name.split()[-1].lower()
            year = self.publication_date.year if self.publication_date else datetime.now().year
            key = f"{first_author_surname}{year}"
        else:
            key = "unknown"
        
        # Basic BibTeX fields
        fields = [
            f"title = {{{self.title}}}",
            f"author = {{{' and '.join([author.to_bibtex_author() for author in self.authors])}}}",
        ]
        
        if self.publication_date:
            fields.append(f"year = {{{self.publication_date.year}}}")
        
        if self.journal:
            fields.append(f"journal = {{{self.journal}}}")
        
        if self.doi:
            fields.append(f"doi = {{{self.doi}}}")
        
        if self.arxiv_id:
            fields.append(f"eprint = {{{self.arxiv_id}}}")
            fields.append("archivePrefix = {arXiv}")
        
        # Format BibTeX entry
        fields_str = ",\n  ".join(fields)
        return f"@{entry_type}{{{key},\n  {fields_str}\n}}"
    
    def validate_project_files(self) -> Dict[str, bool]:
        """Validate that required project files exist."""
        results = {}
        
        # Check main LaTeX file
        main_tex_path = self.get_main_tex_path()
        results["main_tex"] = main_tex_path.exists()
        
        # Check bibliography file
        bib_path = self.get_bibliography_path()
        results["bibliography"] = bib_path.exists() if bib_path else True
        
        # Check project directory
        results["project_directory"] = self.project_path.exists() and self.project_path.is_dir()
        
        return results
    
    def get_project_summary(self) -> Dict[str, Any]:
        """Get a summary of project information."""
        return {
            "name": self.name,
            "title": self.title,
            "status": self.status.value,
            "type": self.project_type.value,
            "authors_count": len(self.authors),
            "has_abstract": bool(self.abstract),
            "keywords_count": len(self.keywords),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_build": self.last_build.isoformat() if self.last_build else None,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "file_validation": self.validate_project_files()
        }