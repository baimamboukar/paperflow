"""Citation and bibliography processor for LaTeX documents."""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

try:
    import bibtexparser
    from bibtexparser.bparser import BibTexParser
    from bibtexparser.customization import convert_to_unicode
except ImportError:
    bibtexparser = None

from paperflow.models.processor import (
    Citation, Bibliography, LaTeXDocument, ProcessingResult, 
    ProcessingError, ProcessingWarning, CitationStyle
)

logger = logging.getLogger(__name__)


class CitationProcessor:
    """Processor for handling citations and bibliography."""
    
    def __init__(self, citation_style: CitationStyle = CitationStyle.IEEE):
        """Initialize the citation processor.
        
        Args:
            citation_style: Citation style to use
        """
        self.citation_style = citation_style
        self._setup_patterns()
    
    def _setup_patterns(self) -> None:
        """Set up regex patterns for citation parsing."""
        # Citation command patterns
        self.citation_patterns = {
            'cite': re.compile(r'\\cite(?:\[[^\]]*\])?\{([^}]+)\}'),
            'citep': re.compile(r'\\citep(?:\[[^\]]*\])?\{([^}]+)\}'),
            'citet': re.compile(r'\\citet(?:\[[^\]]*\])?\{([^}]+)\}'),
            'citealp': re.compile(r'\\citealp(?:\[[^\]]*\])?\{([^}]+)\}'),
            'citealt': re.compile(r'\\citealt(?:\[[^\]]*\])?\{([^}]+)\}'),
            'citeauthor': re.compile(r'\\citeauthor(?:\[[^\]]*\])?\{([^}]+)\}'),
            'citeyear': re.compile(r'\\citeyear(?:\[[^\]]*\])?\{([^}]+)\}'),
        }
        
        # Bibliography patterns
        self.bibliography_pattern = re.compile(r'\\bibliography\{([^}]+)\}')
        self.bibstyle_pattern = re.compile(r'\\bibliographystyle\{([^}]+)\}')
    
    def process_citations(self, latex_document: LaTeXDocument, 
                         bibliography_paths: Optional[List[Union[str, Path]]] = None) -> ProcessingResult:
        """Process citations in a LaTeX document.
        
        Args:
            latex_document: Parsed LaTeX document
            bibliography_paths: Optional paths to .bib files
            
        Returns:
            ProcessingResult with updated document
        """
        result = ProcessingResult(status="success")
        
        try:
            # Find citation keys in the document
            citation_keys = self._extract_citation_keys(latex_document)
            
            # Load bibliography
            bibliography = self._load_bibliography(bibliography_paths, latex_document, result)
            
            if bibliography:
                # Process and validate citations
                self._validate_citations(citation_keys, bibliography, result)
                
                # Add bibliography to document
                latex_document.bibliography = bibliography
                
                logger.info(f"Processed {len(citation_keys)} citations with {len(bibliography.citations)} references")
            
            result.latex_document = latex_document
            
        except Exception as e:
            logger.error(f"Error processing citations: {e}")
            error = ProcessingError(
                error_type="CitationProcessingError",
                message=f"Failed to process citations: {str(e)}",
                suggestion="Check bibliography files and citation syntax"
            )
            result.add_error(error)
        
        return result
    
    def _extract_citation_keys(self, latex_document: LaTeXDocument) -> Set[str]:
        """Extract all citation keys from the LaTeX document.
        
        Args:
            latex_document: Parsed LaTeX document
            
        Returns:
            Set of citation keys found in the document
        """
        citation_keys = set()
        
        # Combine all text content
        all_content = ""
        if latex_document.abstract:
            all_content += latex_document.abstract + " "
        
        for section in latex_document.sections:
            all_content += section.content + " "
        
        # Extract citations from all content
        for pattern_name, pattern in self.citation_patterns.items():
            for match in pattern.finditer(all_content):
                keys = match.group(1).split(',')
                for key in keys:
                    citation_keys.add(key.strip())
        
        return citation_keys
    
    def _load_bibliography(self, bibliography_paths: Optional[List[Union[str, Path]]], 
                          latex_document: LaTeXDocument, 
                          result: ProcessingResult) -> Optional[Bibliography]:
        """Load bibliography from .bib files.
        
        Args:
            bibliography_paths: Paths to .bib files
            latex_document: LaTeX document for metadata
            result: Processing result for errors/warnings
            
        Returns:
            Loaded bibliography or None if failed
        """
        if bibtexparser is None:
            error = ProcessingError(
                error_type="MissingDependency",
                message="bibtexparser library not installed",
                suggestion="Install bibtexparser: pip install bibtexparser"
            )
            result.add_error(error)
            return None
        
        bibliography = Bibliography(style=self.citation_style)
        
        # Get bibliography paths from various sources
        bib_paths = []
        
        if bibliography_paths:
            bib_paths.extend([Path(p) for p in bibliography_paths])
        
        # Check document metadata for bibliography files
        if 'bibliography_files' in latex_document.metadata:
            for bib_file in latex_document.metadata['bibliography_files']:
                bib_paths.append(Path(bib_file))
        
        # If source file is known, look for .bib files in same directory
        if latex_document.source_file:
            source_dir = latex_document.source_file.parent
            for bib_file in source_dir.glob('*.bib'):
                if bib_file not in bib_paths:
                    bib_paths.append(bib_file)
        
        # Load each bibliography file
        for bib_path in bib_paths:
            try:
                self._load_bib_file(bib_path, bibliography, result)
            except Exception as e:
                warning = ProcessingWarning(
                    warning_type="BibliographyLoadError",
                    message=f"Failed to load bibliography file {bib_path}: {str(e)}",
                    context=str(bib_path)
                )
                result.add_warning(warning)
        
        return bibliography if bibliography.citations else None
    
    def _load_bib_file(self, bib_path: Path, bibliography: Bibliography, 
                       result: ProcessingResult) -> None:
        """Load a single .bib file.
        
        Args:
            bib_path: Path to .bib file
            bibliography: Bibliography to add entries to
            result: Processing result for errors/warnings
        """
        if not bib_path.exists():
            warning = ProcessingWarning(
                warning_type="FileNotFound",
                message=f"Bibliography file not found: {bib_path}",
                context=str(bib_path)
            )
            result.add_warning(warning)
            return
        
        try:
            with open(bib_path, 'r', encoding='utf-8') as bib_file:
                parser = BibTexParser()
                parser.customization = convert_to_unicode
                bib_database = bibtexparser.load(bib_file, parser=parser)
            
            # Convert to our Citation objects
            for entry in bib_database.entries:
                citation = self._convert_bibtex_entry(entry)
                bibliography.add_citation(citation)
            
            logger.info(f"Loaded {len(bib_database.entries)} entries from {bib_path}")
            
        except Exception as e:
            error = ProcessingError(
                error_type="BibTexParseError",
                message=f"Failed to parse .bib file {bib_path}: {str(e)}",
                suggestion="Check BibTeX syntax in the file"
            )
            result.add_error(error)
    
    def _convert_bibtex_entry(self, entry: Dict) -> Citation:
        """Convert a BibTeX entry to a Citation object.
        
        Args:
            entry: BibTeX entry dictionary
            
        Returns:
            Citation object
        """
        # Extract standard fields
        citation = Citation(
            key=entry.get('ID', ''),
            entry_type=entry.get('ENTRYTYPE', 'misc').lower(),
            title=entry.get('title', ''),
            author=entry.get('author', ''),
            journal=entry.get('journal', ''),
            booktitle=entry.get('booktitle', ''),
            year=entry.get('year', ''),
            volume=entry.get('volume', ''),
            number=entry.get('number', ''),
            pages=entry.get('pages', ''),
            publisher=entry.get('publisher', ''),
            doi=entry.get('doi', ''),
            url=entry.get('url', ''),
            note=entry.get('note', '')
        )
        
        # Store extra fields
        standard_fields = {
            'ID', 'ENTRYTYPE', 'title', 'author', 'journal', 'booktitle',
            'year', 'volume', 'number', 'pages', 'publisher', 'doi', 'url', 'note'
        }
        
        for key, value in entry.items():
            if key not in standard_fields:
                citation.extra_fields[key.lower()] = str(value)
        
        return citation
    
    def _validate_citations(self, citation_keys: Set[str], bibliography: Bibliography, 
                           result: ProcessingResult) -> None:
        """Validate that all citations have corresponding bibliography entries.
        
        Args:
            citation_keys: Set of citation keys found in document
            bibliography: Loaded bibliography
            result: Processing result for warnings
        """
        missing_citations = []
        
        for key in citation_keys:
            if not bibliography.get_citation(key):
                missing_citations.append(key)
        
        if missing_citations:
            warning = ProcessingWarning(
                warning_type="MissingBibliographyEntries",
                message=f"Found {len(missing_citations)} citations without bibliography entries",
                context=f"Missing keys: {', '.join(missing_citations[:10])}" + 
                       ("..." if len(missing_citations) > 10 else "")
            )
            result.add_warning(warning)
    
    def format_citation(self, citation: Citation, citation_style: Optional[CitationStyle] = None) -> str:
        """Format a citation according to the specified style.
        
        Args:
            citation: Citation to format
            citation_style: Style to use (defaults to processor style)
            
        Returns:
            Formatted citation string
        """
        style = citation_style or self.citation_style
        
        if style == CitationStyle.IEEE:
            return self._format_ieee_citation(citation)
        elif style == CitationStyle.ACM:
            return self._format_acm_citation(citation)
        elif style == CitationStyle.APA:
            return self._format_apa_citation(citation)
        else:
            return self._format_ieee_citation(citation)  # Default fallback
    
    def _format_ieee_citation(self, citation: Citation) -> str:
        """Format citation in IEEE style."""
        parts = []
        
        # Author
        if citation.author:
            # Simplify author formatting for now
            authors = citation.author.replace(' and ', ', ')
            parts.append(authors)
        
        # Title
        if citation.title:
            title = citation.title.strip('{}')
            if citation.entry_type == 'article':
                parts.append(f'"{title},"')
            else:
                parts.append(f"{title},")
        
        # Journal/Booktitle
        if citation.journal:
            journal_part = f"*{citation.journal}*"
            if citation.volume:
                journal_part += f", vol. {citation.volume}"
            if citation.number:
                journal_part += f", no. {citation.number}"
            if citation.pages:
                journal_part += f", pp. {citation.pages}"
            parts.append(journal_part + ",")
        elif citation.booktitle:
            parts.append(f"in *{citation.booktitle}*,")
        
        # Publisher
        if citation.publisher:
            parts.append(f"{citation.publisher},")
        
        # Year
        if citation.year:
            parts.append(f"{citation.year}.")
        
        return " ".join(parts)
    
    def _format_acm_citation(self, citation: Citation) -> str:
        """Format citation in ACM style."""
        # Similar to IEEE but with different formatting
        return self._format_ieee_citation(citation)  # Simplified for now
    
    def _format_apa_citation(self, citation: Citation) -> str:
        """Format citation in APA style."""
        parts = []
        
        # Author (Last, F.)
        if citation.author:
            parts.append(f"{citation.author}.")
        
        # Year
        if citation.year:
            parts.append(f"({citation.year}).")
        
        # Title
        if citation.title:
            title = citation.title.strip('{}')
            parts.append(f"{title}.")
        
        # Journal/Publisher info
        if citation.journal:
            journal_part = f"*{citation.journal}*"
            if citation.volume:
                journal_part += f", {citation.volume}"
            if citation.number:
                journal_part += f"({citation.number})"
            if citation.pages:
                journal_part += f", {citation.pages}"
            parts.append(journal_part + ".")
        
        return " ".join(parts)
    
    def generate_bibliography_html(self, bibliography: Bibliography) -> str:
        """Generate HTML for the bibliography section.
        
        Args:
            bibliography: Bibliography to format
            
        Returns:
            HTML string for bibliography
        """
        if not bibliography.citations:
            return ""
        
        html_parts = ['<div class="bibliography">']
        html_parts.append('<h2>References</h2>')
        html_parts.append('<ol class="bibliography-list">')
        
        # Get citations in order (could be by appearance or alphabetical)
        ordered_citations = bibliography.get_ordered_citations()
        
        for i, citation in enumerate(ordered_citations, 1):
            formatted_citation = self.format_citation(citation, bibliography.style)
            html_parts.append(f'<li id="cite-{citation.key}" class="bibliography-entry">')
            html_parts.append(formatted_citation)
            html_parts.append('</li>')
        
        html_parts.append('</ol>')
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)