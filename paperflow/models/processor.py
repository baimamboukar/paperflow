"""Data models for LaTeX processing and HTML conversion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class ProcessingStatus(str, Enum):
    """Status of processing operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"


class CitationStyle(str, Enum):
    """Citation styles supported."""
    IEEE = "ieee"
    ACM = "acm"
    APA = "apa"
    CHICAGO = "chicago"
    HARVARD = "harvard"


class MathRenderer(str, Enum):
    """Math rendering engines."""
    MATHJAX = "mathjax"
    KATEX = "katex"


class DocumentSection(BaseModel):
    """Represents a section in a LaTeX document."""
    
    level: int = Field(..., description="Section level (1=section, 2=subsection, etc.)")
    title: str = Field(..., description="Section title")
    label: Optional[str] = Field(None, description="LaTeX label for cross-referencing")
    content: str = Field("", description="Section content")
    subsections: List[DocumentSection] = Field(default_factory=list, description="Nested subsections")
    
    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True


class Citation(BaseModel):
    """Represents a citation entry."""
    
    key: str = Field(..., description="Citation key/identifier")
    entry_type: str = Field(..., description="Type of entry (article, book, etc.)")
    title: Optional[str] = Field(None, description="Publication title")
    author: Optional[str] = Field(None, description="Author(s)")
    journal: Optional[str] = Field(None, description="Journal name")
    booktitle: Optional[str] = Field(None, description="Book title")
    year: Optional[str] = Field(None, description="Publication year")
    volume: Optional[str] = Field(None, description="Volume number")
    number: Optional[str] = Field(None, description="Issue number")
    pages: Optional[str] = Field(None, description="Page numbers")
    publisher: Optional[str] = Field(None, description="Publisher")
    doi: Optional[str] = Field(None, description="DOI")
    url: Optional[str] = Field(None, description="URL")
    note: Optional[str] = Field(None, description="Additional notes")
    extra_fields: Dict[str, str] = Field(default_factory=dict, description="Additional BibTeX fields")
    
    @validator('year')
    def validate_year(cls, v):
        """Validate year format."""
        if v and not v.isdigit():
            raise ValueError("Year must be numeric")
        return v


class Bibliography(BaseModel):
    """Represents a bibliography collection."""
    
    citations: Dict[str, Citation] = Field(default_factory=dict, description="Citation entries by key")
    style: CitationStyle = Field(CitationStyle.IEEE, description="Citation style")
    file_path: Optional[Path] = Field(None, description="Path to .bib file")
    
    def add_citation(self, citation: Citation) -> None:
        """Add a citation to the bibliography."""
        self.citations[citation.key] = citation
    
    def get_citation(self, key: str) -> Optional[Citation]:
        """Get citation by key."""
        return self.citations.get(key)
    
    def get_ordered_citations(self) -> List[Citation]:
        """Get citations ordered by first appearance or alphabetically."""
        return list(self.citations.values())


class Equation(BaseModel):
    """Represents a mathematical equation."""
    
    latex_code: str = Field(..., description="LaTeX equation code")
    label: Optional[str] = Field(None, description="Equation label for referencing")
    number: Optional[int] = Field(None, description="Equation number")
    is_inline: bool = Field(False, description="Whether equation is inline or display")
    renderer: MathRenderer = Field(MathRenderer.MATHJAX, description="Math rendering engine")
    
    @validator('latex_code')
    def validate_latex_code(cls, v):
        """Validate LaTeX code is not empty."""
        if not v.strip():
            raise ValueError("LaTeX code cannot be empty")
        return v


class Figure(BaseModel):
    """Represents a figure in the document."""
    
    file_path: Path = Field(..., description="Path to image file")
    caption: Optional[str] = Field(None, description="Figure caption")
    label: Optional[str] = Field(None, description="Figure label for referencing")
    number: Optional[int] = Field(None, description="Figure number")
    width: Optional[str] = Field(None, description="Figure width specification")
    height: Optional[str] = Field(None, description="Figure height specification")
    placement: Optional[str] = Field(None, description="LaTeX placement options")
    alt_text: Optional[str] = Field(None, description="Alternative text for accessibility")
    
    @validator('file_path')
    def validate_file_path(cls, v):
        """Validate file path exists."""
        if isinstance(v, str):
            v = Path(v)
        return v


class CrossReference(BaseModel):
    """Represents a cross-reference in the document."""
    
    ref_type: str = Field(..., description="Type of reference (fig, eq, sec, etc.)")
    label: str = Field(..., description="Referenced label")
    text: Optional[str] = Field(None, description="Reference text")
    number: Optional[str] = Field(None, description="Referenced number")


class LaTeXDocument(BaseModel):
    """Represents a parsed LaTeX document."""
    
    title: Optional[str] = Field(None, description="Document title")
    authors: List[str] = Field(default_factory=list, description="Document authors")
    abstract: Optional[str] = Field(None, description="Document abstract")
    keywords: List[str] = Field(default_factory=list, description="Document keywords")
    sections: List[DocumentSection] = Field(default_factory=list, description="Document sections")
    bibliography: Optional[Bibliography] = Field(None, description="Document bibliography")
    figures: Dict[str, Figure] = Field(default_factory=dict, description="Figures by label")
    equations: Dict[str, Equation] = Field(default_factory=dict, description="Equations by label")
    cross_references: List[CrossReference] = Field(default_factory=list, description="Cross-references")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    source_file: Optional[Path] = Field(None, description="Source LaTeX file path")
    
    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True
    
    def add_figure(self, figure: Figure) -> None:
        """Add a figure to the document."""
        if figure.label:
            self.figures[figure.label] = figure
    
    def add_equation(self, equation: Equation) -> None:
        """Add an equation to the document."""
        if equation.label:
            self.equations[equation.label] = equation
    
    def get_all_figures(self) -> List[Figure]:
        """Get all figures in document order."""
        return list(self.figures.values())
    
    def get_all_equations(self) -> List[Equation]:
        """Get all equations in document order."""
        return list(self.equations.values())


class HTMLDocument(BaseModel):
    """Represents the generated HTML document."""
    
    html_content: str = Field(..., description="Generated HTML content")
    css_classes: Dict[str, str] = Field(default_factory=dict, description="CSS class mappings")
    javascript_includes: List[str] = Field(default_factory=list, description="Required JavaScript libraries")
    css_includes: List[str] = Field(default_factory=list, description="Required CSS files")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="HTML metadata")
    math_renderer: MathRenderer = Field(MathRenderer.MATHJAX, description="Math rendering engine used")
    citation_style: CitationStyle = Field(CitationStyle.IEEE, description="Citation style used")
    generated_at: datetime = Field(default_factory=datetime.now, description="Generation timestamp")
    
    @validator('html_content')
    def validate_html_content(cls, v):
        """Validate HTML content is not empty."""
        if not v.strip():
            raise ValueError("HTML content cannot be empty")
        return v


class ProcessingError(BaseModel):
    """Represents a processing error."""
    
    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Error message")
    line_number: Optional[int] = Field(None, description="Line number where error occurred")
    column: Optional[int] = Field(None, description="Column where error occurred")
    context: Optional[str] = Field(None, description="Context around error")
    suggestion: Optional[str] = Field(None, description="Suggested fix")


class ProcessingWarning(BaseModel):
    """Represents a processing warning."""
    
    warning_type: str = Field(..., description="Type of warning")
    message: str = Field(..., description="Warning message")
    line_number: Optional[int] = Field(None, description="Line number where warning occurred")
    context: Optional[str] = Field(None, description="Context around warning")


class ProcessingResult(BaseModel):
    """Represents the result of a processing operation."""
    
    status: ProcessingStatus = Field(..., description="Processing status")
    latex_document: Optional[LaTeXDocument] = Field(None, description="Parsed LaTeX document")
    html_document: Optional[HTMLDocument] = Field(None, description="Generated HTML document")
    errors: List[ProcessingError] = Field(default_factory=list, description="Processing errors")
    warnings: List[ProcessingWarning] = Field(default_factory=list, description="Processing warnings")
    processing_time: float = Field(0.0, description="Processing time in seconds")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="Processing statistics")
    
    @property
    def is_successful(self) -> bool:
        """Check if processing was successful."""
        return self.status == ProcessingStatus.SUCCESS
    
    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0
    
    def add_error(self, error: ProcessingError) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        if self.status == ProcessingStatus.SUCCESS:
            self.status = ProcessingStatus.ERROR
    
    def add_warning(self, warning: ProcessingWarning) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)
        if self.status == ProcessingStatus.SUCCESS:
            self.status = ProcessingStatus.WARNING


class ProcessorConfig(BaseModel):
    """Configuration for LaTeX processors."""
    
    math_renderer: MathRenderer = Field(MathRenderer.MATHJAX, description="Math rendering engine")
    citation_style: CitationStyle = Field(CitationStyle.IEEE, description="Citation style")
    figure_width: str = Field("100%", description="Default figure width")
    figure_format: str = Field("webp", description="Output figure format")
    enable_cross_references: bool = Field(True, description="Enable cross-reference processing")
    enable_equation_numbering: bool = Field(True, description="Enable equation numbering")
    enable_figure_numbering: bool = Field(True, description="Enable figure numbering")
    output_encoding: str = Field("utf-8", description="Output HTML encoding")
    base_url: Optional[str] = Field(None, description="Base URL for relative links")
    template_path: Optional[Path] = Field(None, description="Custom HTML template path")
    
    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True