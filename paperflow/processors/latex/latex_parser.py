"""LaTeX document parser for extracting structure and content."""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from paperflow.models.processor import (
    LaTeXDocument, DocumentSection, Figure, Equation, CrossReference,
    ProcessingResult, ProcessingError, ProcessingWarning, ProcessingStatus,
    ProcessorConfig
)

logger = logging.getLogger(__name__)


class LaTeXParser:
    """Parser for LaTeX documents."""
    
    def __init__(self, config: Optional[ProcessorConfig] = None):
        """Initialize the LaTeX parser.
        
        Args:
            config: Processor configuration
        """
        self.config = config or ProcessorConfig()
        self._setup_patterns()
    
    def _setup_patterns(self) -> None:
        """Set up regex patterns for LaTeX parsing."""
        # Document structure patterns
        self.title_pattern = re.compile(r'\\title\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL)
        self.author_pattern = re.compile(r'\\author\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL)
        self.abstract_pattern = re.compile(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', re.DOTALL)
        
        # Section patterns
        self.section_patterns = {
            1: re.compile(r'\\section\*?\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL),
            2: re.compile(r'\\subsection\*?\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL),
            3: re.compile(r'\\subsubsection\*?\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL),
            4: re.compile(r'\\paragraph\*?\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL),
        }
        
        # Label pattern
        self.label_pattern = re.compile(r'\\label\{([^}]+)\}')
        
        # Citation patterns
        self.cite_patterns = [
            re.compile(r'\\cite(?:\[[^\]]*\])?\{([^}]+)\}'),
            re.compile(r'\\citep(?:\[[^\]]*\])?\{([^}]+)\}'),
            re.compile(r'\\citet(?:\[[^\]]*\])?\{([^}]+)\}'),
            re.compile(r'\\citealp(?:\[[^\]]*\])?\{([^}]+)\}'),
        ]
        
        # Math patterns
        self.inline_math_pattern = re.compile(r'\$([^$]+)\$')
        self.display_math_patterns = [
            re.compile(r'\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}', re.DOTALL),
            re.compile(r'\\begin\{align\*?\}(.*?)\\end\{align\*?\}', re.DOTALL),
            re.compile(r'\\begin\{gather\*?\}(.*?)\\end\{gather\*?\}', re.DOTALL),
            re.compile(r'\\\[(.*?)\\\]', re.DOTALL),
        ]
        
        # Figure patterns
        self.figure_pattern = re.compile(
            r'\\begin\{figure\*?\}(?:\[[htbp!]*\])?(.*?)\\end\{figure\*?\}', 
            re.DOTALL
        )
        self.includegraphics_pattern = re.compile(
            r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}'
        )
        self.caption_pattern = re.compile(r'\\caption\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL)
        
        # Cross-reference pattern
        self.ref_pattern = re.compile(r'\\ref\{([^}]+)\}')
        
        # Bibliography pattern
        self.bibliography_pattern = re.compile(r'\\bibliography\{([^}]+)\}')
        self.bibstyle_pattern = re.compile(r'\\bibliographystyle\{([^}]+)\}')
        
        # Text formatting patterns
        self.textbf_pattern = re.compile(r'\\textbf\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL)
        self.textit_pattern = re.compile(r'\\textit\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL)
        self.emph_pattern = re.compile(r'\\emph\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL)
    
    def parse_file(self, file_path: Union[str, Path]) -> ProcessingResult:
        """Parse a LaTeX file.
        
        Args:
            file_path: Path to the LaTeX file
            
        Returns:
            ProcessingResult with parsed document
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                error = ProcessingError(
                    error_type="FileNotFound",
                    message=f"LaTeX file not found: {file_path}",
                    suggestion="Check the file path and ensure the file exists"
                )
                result = ProcessingResult(status=ProcessingStatus.ERROR)
                result.add_error(error)
                return result
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self.parse_content(content, source_file=file_path)
            
        except Exception as e:
            logger.error(f"Error parsing LaTeX file {file_path}: {e}")
            error = ProcessingError(
                error_type="ParseError",
                message=f"Failed to parse LaTeX file: {str(e)}",
                suggestion="Check file encoding and LaTeX syntax"
            )
            result = ProcessingResult(status=ProcessingStatus.ERROR)
            result.add_error(error)
            return result
    
    def parse_content(self, content: str, source_file: Optional[Path] = None) -> ProcessingResult:
        """Parse LaTeX content.
        
        Args:
            content: LaTeX content string
            source_file: Optional source file path
            
        Returns:
            ProcessingResult with parsed document
        """
        result = ProcessingResult(status=ProcessingStatus.SUCCESS)
        
        try:
            # Create document
            document = LaTeXDocument(source_file=source_file)
            
            # Parse document metadata
            self._parse_metadata(content, document, result)
            
            # Parse document structure
            self._parse_sections(content, document, result)
            
            # Parse figures
            self._parse_figures(content, document, result)
            
            # Parse equations
            self._parse_equations(content, document, result)
            
            # Parse cross-references
            self._parse_cross_references(content, document, result)
            
            # Parse bibliography info
            self._parse_bibliography_info(content, document, result)
            
            result.latex_document = document
            
            # Add statistics
            result.statistics = {
                "sections": len(document.sections),
                "figures": len(document.figures),
                "equations": len(document.equations),
                "cross_references": len(document.cross_references),
            }
            
            logger.info(f"Successfully parsed LaTeX document with {len(document.sections)} sections")
            
        except Exception as e:
            logger.error(f"Error parsing LaTeX content: {e}")
            error = ProcessingError(
                error_type="ParseError",
                message=f"Failed to parse LaTeX content: {str(e)}",
                suggestion="Check LaTeX syntax and structure"
            )
            result.add_error(error)
        
        return result
    
    def _parse_metadata(self, content: str, document: LaTeXDocument, result: ProcessingResult) -> None:
        """Parse document metadata (title, authors, abstract)."""
        # Parse title
        title_match = self.title_pattern.search(content)
        if title_match:
            document.title = self._clean_latex_text(title_match.group(1))
        
        # Parse authors
        author_match = self.author_pattern.search(content)
        if author_match:
            authors_text = self._clean_latex_text(author_match.group(1))
            # Split by 'and' or '\and'
            authors = re.split(r'\s+and\s+|\\and\s+', authors_text)
            document.authors = [author.strip() for author in authors if author.strip()]
        
        # Parse abstract
        abstract_match = self.abstract_pattern.search(content)
        if abstract_match:
            document.abstract = self._clean_latex_text(abstract_match.group(1))
    
    def _parse_sections(self, content: str, document: LaTeXDocument, result: ProcessingResult) -> None:
        """Parse document sections and subsections."""
        sections = []
        current_positions = {}
        
        # Find all section-like commands with their positions
        all_sections = []
        for level, pattern in self.section_patterns.items():
            for match in pattern.finditer(content):
                all_sections.append({
                    'level': level,
                    'title': self._clean_latex_text(match.group(1)),
                    'start': match.start(),
                    'end': match.end(),
                    'match': match
                })
        
        # Sort by position
        all_sections.sort(key=lambda x: x['start'])
        
        # Extract content for each section
        for i, section_info in enumerate(all_sections):
            section = DocumentSection(
                level=section_info['level'],
                title=section_info['title']
            )
            
            # Find label if present
            label_search_start = section_info['end']
            label_search_end = all_sections[i + 1]['start'] if i + 1 < len(all_sections) else len(content)
            section_content = content[label_search_start:label_search_end]
            
            label_match = self.label_pattern.search(section_content[:200])  # Look in first 200 chars
            if label_match:
                section.label = label_match.group(1)
            
            # Extract section content (up to next section of same or higher level)
            content_end = len(content)
            for j in range(i + 1, len(all_sections)):
                if all_sections[j]['level'] <= section_info['level']:
                    content_end = all_sections[j]['start']
                    break
            
            section.content = content[section_info['end']:content_end].strip()
            sections.append(section)
        
        document.sections = sections
    
    def _parse_figures(self, content: str, document: LaTeXDocument, result: ProcessingResult) -> None:
        """Parse figures from the document."""
        figure_counter = 1
        
        for match in self.figure_pattern.finditer(content):
            figure_content = match.group(1)
            
            # Extract image path
            img_match = self.includegraphics_pattern.search(figure_content)
            if not img_match:
                warning = ProcessingWarning(
                    warning_type="MissingImage",
                    message="Figure environment found without \\includegraphics",
                    context=figure_content[:100]
                )
                result.add_warning(warning)
                continue
            
            image_path = img_match.group(1)
            
            # Create figure object
            figure = Figure(file_path=Path(image_path))
            
            # Extract caption
            caption_match = self.caption_pattern.search(figure_content)
            if caption_match:
                figure.caption = self._clean_latex_text(caption_match.group(1))
            
            # Extract label
            label_match = self.label_pattern.search(figure_content)
            if label_match:
                figure.label = label_match.group(1)
            
            # Set figure number
            figure.number = figure_counter
            figure_counter += 1
            
            # Add to document
            document.add_figure(figure)
    
    def _parse_equations(self, content: str, document: LaTeXDocument, result: ProcessingResult) -> None:
        """Parse equations from the document."""
        equation_counter = 1
        
        # Parse display equations
        for pattern in self.display_math_patterns:
            for match in pattern.finditer(content):
                equation_content = match.group(1).strip()
                
                equation = Equation(
                    latex_code=equation_content,
                    is_inline=False,
                    number=equation_counter
                )
                
                # Look for label near the equation
                search_area = match.group(0)
                label_match = self.label_pattern.search(search_area)
                if label_match:
                    equation.label = label_match.group(1)
                
                equation_counter += 1
                document.add_equation(equation)
        
        # Parse inline equations (don't number these)
        for match in self.inline_math_pattern.finditer(content):
            equation_content = match.group(1).strip()
            
            equation = Equation(
                latex_code=equation_content,
                is_inline=True
            )
            
            # Inline equations typically don't have labels, but check anyway
            document.equations[f"inline_{match.start()}"] = equation
    
    def _parse_cross_references(self, content: str, document: LaTeXDocument, result: ProcessingResult) -> None:
        """Parse cross-references from the document."""
        for match in self.ref_pattern.finditer(content):
            ref_label = match.group(1)
            
            # Determine reference type based on label prefix
            ref_type = "unknown"
            if ref_label.startswith(('fig:', 'figure:')):
                ref_type = "figure"
            elif ref_label.startswith(('eq:', 'equation:')):
                ref_type = "equation"
            elif ref_label.startswith(('sec:', 'section:')):
                ref_type = "section"
            elif ref_label.startswith(('tab:', 'table:')):
                ref_type = "table"
            
            cross_ref = CrossReference(
                ref_type=ref_type,
                label=ref_label
            )
            
            document.cross_references.append(cross_ref)
    
    def _parse_bibliography_info(self, content: str, document: LaTeXDocument, result: ProcessingResult) -> None:
        """Parse bibliography information."""
        # Look for bibliography file references
        bib_match = self.bibliography_pattern.search(content)
        if bib_match:
            bib_files = bib_match.group(1).split(',')
            document.metadata['bibliography_files'] = [f.strip() + '.bib' for f in bib_files]
        
        # Look for bibliography style
        style_match = self.bibstyle_pattern.search(content)
        if style_match:
            document.metadata['bibliography_style'] = style_match.group(1)
    
    def _clean_latex_text(self, text: str) -> str:
        """Clean LaTeX text by removing/converting common commands."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Convert text formatting
        text = self.textbf_pattern.sub(r'<strong>\1</strong>', text)
        text = self.textit_pattern.sub(r'<em>\1</em>', text)
        text = self.emph_pattern.sub(r'<em>\1</em>', text)
        
        # Remove common LaTeX commands
        text = re.sub(r'\\[a-zA-Z]+\*?\s*', '', text)  # Remove unknown commands
        text = re.sub(r'[{}]', '', text)  # Remove braces
        
        # Clean up spacing
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text