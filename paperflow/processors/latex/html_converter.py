"""HTML converter that combines all LaTeX processors to generate publication-quality HTML."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from paperflow.models.processor import (
    LaTeXDocument, HTMLDocument, ProcessingResult, ProcessingError,
    ProcessingWarning, ProcessorConfig, ProcessingStatus, CitationStyle, MathRenderer
)
from paperflow.processors.latex.latex_parser import LaTeXParser
from paperflow.processors.latex.citation_processor import CitationProcessor
from paperflow.processors.latex.equation_processor import EquationProcessor
from paperflow.processors.latex.figure_processor import FigureProcessor

logger = logging.getLogger(__name__)


class HTMLConverter:
    """Main HTML converter that orchestrates all LaTeX processing."""
    
    def __init__(self, config: Optional[ProcessorConfig] = None):
        """Initialize the HTML converter.
        
        Args:
            config: Processor configuration
        """
        self.config = config or ProcessorConfig()
        
        # Initialize individual processors
        self.latex_parser = LaTeXParser(self.config)
        self.citation_processor = CitationProcessor(self.config.citation_style)
        self.equation_processor = EquationProcessor(self.config.math_renderer)
        self.figure_processor = FigureProcessor(self.config)
        
        self._setup_html_templates()
    
    def _setup_html_templates(self) -> None:
        """Set up HTML templates for different document parts."""
        # Main document template
        self.document_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="{encoding}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {css_includes}
    {math_config}
    <style>
        {inline_css}
    </style>
</head>
<body>
    <article class="paper">
        {header}
        {content}
        {bibliography}
    </article>
    {js_includes}
</body>
</html>'''
        
        # Header template
        self.header_template = '''<header class="paper-header">
    <h1 class="paper-title">{title}</h1>
    {authors}
    {abstract}
</header>'''
        
        # Authors template
        self.authors_template = '''<div class="paper-authors">
    {author_list}
</div>'''
        
        # Abstract template
        self.abstract_template = '''<div class="paper-abstract">
    <h2>Abstract</h2>
    <p>{abstract_content}</p>
</div>'''
        
        # Section template
        self.section_template = '''<section class="paper-section level-{level}" {section_id}>
    <h{heading_level} class="section-title">{title}</h{heading_level}>
    <div class="section-content">
        {content}
    </div>
    {subsections}
</section>'''
    
    def convert_file(self, latex_file: Union[str, Path], 
                    output_file: Optional[Union[str, Path]] = None,
                    bibliography_files: Optional[List[Union[str, Path]]] = None) -> ProcessingResult:
        """Convert a LaTeX file to HTML.
        
        Args:
            latex_file: Path to LaTeX file
            output_file: Optional output HTML file path
            bibliography_files: Optional bibliography files
            
        Returns:
            ProcessingResult with HTML document
        """
        latex_file = Path(latex_file)
        
        try:
            # Parse LaTeX document
            logger.info(f"Parsing LaTeX file: {latex_file}")
            parse_result = self.latex_parser.parse_file(latex_file)
            
            if not parse_result.is_successful:
                return parse_result
            
            # Convert to HTML
            return self.convert_document(
                parse_result.latex_document, 
                output_file=output_file,
                bibliography_files=bibliography_files
            )
            
        except Exception as e:
            logger.error(f"Error converting LaTeX file: {e}")
            error = ProcessingError(
                error_type="ConversionError",
                message=f"Failed to convert LaTeX file: {str(e)}",
                suggestion="Check file path and LaTeX syntax"
            )
            result = ProcessingResult(status=ProcessingStatus.ERROR)
            result.add_error(error)
            return result
    
    def convert_document(self, latex_document: LaTeXDocument,
                        output_file: Optional[Union[str, Path]] = None,
                        bibliography_files: Optional[List[Union[str, Path]]] = None) -> ProcessingResult:
        """Convert a parsed LaTeX document to HTML.
        
        Args:
            latex_document: Parsed LaTeX document
            output_file: Optional output HTML file path
            bibliography_files: Optional bibliography files
            
        Returns:
            ProcessingResult with HTML document
        """
        result = ProcessingResult(status=ProcessingStatus.SUCCESS)
        
        try:
            # Process citations
            logger.info("Processing citations and bibliography")
            citation_result = self.citation_processor.process_citations(
                latex_document, bibliography_files
            )
            result.warnings.extend(citation_result.warnings)
            result.errors.extend(citation_result.errors)
            
            # Process equations
            logger.info("Processing equations")
            equation_result = self.equation_processor.process_equations(latex_document)
            result.warnings.extend(equation_result.warnings)
            result.errors.extend(equation_result.errors)
            
            # Process figures
            logger.info("Processing figures")
            figure_result = self.figure_processor.process_figures(latex_document)
            result.warnings.extend(figure_result.warnings)
            result.errors.extend(figure_result.errors)
            
            # Generate HTML
            logger.info("Generating HTML")
            html_document = self._generate_html(latex_document, result)
            
            # Save to file if specified
            if output_file:
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(html_document.html_content)
                
                logger.info(f"HTML saved to: {output_path}")
            
            result.latex_document = latex_document
            result.html_document = html_document
            
            # Update statistics
            result.statistics.update({
                'sections': len(latex_document.sections),
                'figures': len(latex_document.figures),
                'equations': len(latex_document.equations),
                'citations': len(latex_document.bibliography.citations) if latex_document.bibliography else 0
            })
            
        except Exception as e:
            logger.error(f"Error during HTML conversion: {e}")
            error = ProcessingError(
                error_type="HTMLGenerationError",
                message=f"Failed to generate HTML: {str(e)}",
                suggestion="Check document structure and processor configuration"
            )
            result.add_error(error)
        
        return result
    
    def _generate_html(self, latex_document: LaTeXDocument, 
                      result: ProcessingResult) -> HTMLDocument:
        """Generate HTML from processed LaTeX document.
        
        Args:
            latex_document: Processed LaTeX document
            result: Processing result for warnings/errors
            
        Returns:
            Generated HTML document
        """
        # Generate document parts
        header_html = self._generate_header(latex_document)
        content_html = self._generate_content(latex_document, result)
        bibliography_html = self._generate_bibliography(latex_document)
        
        # Get required includes
        css_includes = self._generate_css_includes()
        js_includes = self._generate_js_includes()
        math_config = self.equation_processor.get_math_config()
        inline_css = self._generate_inline_css()
        
        # Fill main template
        html_content = self.document_template.format(
            encoding=self.config.output_encoding,
            title=latex_document.title or "Untitled Document",
            css_includes=css_includes,
            math_config=math_config,
            inline_css=inline_css,
            header=header_html,
            content=content_html,
            bibliography=bibliography_html,
            js_includes=js_includes
        )
        
        # Create HTML document
        html_document = HTMLDocument(
            html_content=html_content,
            math_renderer=self.config.math_renderer,
            citation_style=self.config.citation_style,
            css_includes=self.equation_processor.get_required_styles(),
            javascript_includes=self.equation_processor.get_required_scripts()
        )
        
        return html_document
    
    def _generate_header(self, latex_document: LaTeXDocument) -> str:
        """Generate document header HTML.
        
        Args:
            latex_document: LaTeX document
            
        Returns:
            Header HTML
        """
        # Generate authors HTML
        authors_html = ""
        if latex_document.authors:
            author_items = [f'<span class="author">{author}</span>' 
                          for author in latex_document.authors]
            authors_html = self.authors_template.format(
                author_list=" • ".join(author_items)
            )
        
        # Generate abstract HTML
        abstract_html = ""
        if latex_document.abstract:
            abstract_html = self.abstract_template.format(
                abstract_content=self._process_text_content(latex_document.abstract, latex_document)
            )
        
        return self.header_template.format(
            title=latex_document.title or "Untitled Document",
            authors=authors_html,
            abstract=abstract_html
        )
    
    def _generate_content(self, latex_document: LaTeXDocument, 
                         result: ProcessingResult) -> str:
        """Generate main content HTML.
        
        Args:
            latex_document: LaTeX document
            result: Processing result
            
        Returns:
            Content HTML
        """
        content_parts = []
        
        for section in latex_document.sections:
            section_html = self._generate_section(section, latex_document, result)
            content_parts.append(section_html)
        
        return "\n".join(content_parts)
    
    def _generate_section(self, section, latex_document: LaTeXDocument,
                         result: ProcessingResult, parent_numbering: str = "") -> str:
        """Generate HTML for a document section.
        
        Args:
            section: Document section
            latex_document: LaTeX document
            result: Processing result
            parent_numbering: Parent section numbering
            
        Returns:
            Section HTML
        """
        # Generate section ID
        section_id = f'id="section-{section.label}"' if section.label else ""
        
        # Calculate heading level (h1-h6)
        heading_level = min(section.level + 1, 6)
        
        # Process section content
        processed_content = self._process_text_content(section.content, latex_document)
        
        # Generate subsections
        subsections_html = ""
        if hasattr(section, 'subsections') and section.subsections:
            subsection_parts = []
            for subsection in section.subsections:
                subsection_html = self._generate_section(
                    subsection, latex_document, result, parent_numbering
                )
                subsection_parts.append(subsection_html)
            subsections_html = "\n".join(subsection_parts)
        
        return self.section_template.format(
            level=section.level,
            section_id=section_id,
            heading_level=heading_level,
            title=section.title,
            content=processed_content,
            subsections=subsections_html
        )
    
    def _process_text_content(self, content: str, latex_document: LaTeXDocument) -> str:
        """Process text content, replacing LaTeX commands with HTML.
        
        Args:
            content: Raw content
            latex_document: LaTeX document for context
            
        Returns:
            Processed HTML content
        """
        if not content:
            return ""
        
        # Process citations
        content = self._process_citations(content, latex_document)
        
        # Process cross-references
        content = self._process_cross_references(content, latex_document)
        
        # Process equations
        content = self._process_inline_equations(content, latex_document)
        
        # Process figures (inline includegraphics)
        content = self._process_inline_figures(content, latex_document)
        
        # Process basic text formatting
        content = self._process_text_formatting(content)
        
        # Convert paragraphs
        content = self._convert_paragraphs(content)
        
        return content
    
    def _process_citations(self, content: str, latex_document: LaTeXDocument) -> str:
        """Process citation commands in content.
        
        Args:
            content: Content to process
            latex_document: LaTeX document
            
        Returns:
            Content with citations converted to HTML
        """
        if not latex_document.bibliography:
            return content
        
        # Process different citation commands
        citation_patterns = {
            r'\\cite\{([^}]+)\}': self._format_cite,
            r'\\citep\{([^}]+)\}': self._format_citep,
            r'\\citet\{([^}]+)\}': self._format_citet,
        }
        
        for pattern, formatter in citation_patterns.items():
            content = re.sub(pattern, lambda m: formatter(m.group(1), latex_document.bibliography), content)
        
        return content
    
    def _format_cite(self, citation_keys: str, bibliography) -> str:
        """Format basic citation."""
        keys = [k.strip() for k in citation_keys.split(',')]
        citation_numbers = []
        
        for key in keys:
            citation = bibliography.get_citation(key)
            if citation:
                # For now, use simple numbering
                idx = list(bibliography.citations.keys()).index(key) + 1
                citation_numbers.append(f'<a href="#cite-{key}" class="citation">[{idx}]</a>')
            else:
                citation_numbers.append(f'<span class="citation-missing">[{key}?]</span>')
        
        return "".join(citation_numbers)
    
    def _format_citep(self, citation_keys: str, bibliography) -> str:
        """Format parenthetical citation."""
        formatted = self._format_cite(citation_keys, bibliography)
        return f"({formatted})" if not formatted.startswith('(') else formatted
    
    def _format_citet(self, citation_keys: str, bibliography) -> str:
        """Format textual citation."""
        keys = [k.strip() for k in citation_keys.split(',')]
        if len(keys) == 1:
            citation = bibliography.get_citation(keys[0])
            if citation and citation.author:
                author = citation.author.split(' and ')[0]  # First author
                idx = list(bibliography.citations.keys()).index(keys[0]) + 1
                return f'{author} <a href="#cite-{keys[0]}" class="citation">[{idx}]</a>'
        
        return self._format_cite(citation_keys, bibliography)
    
    def _process_cross_references(self, content: str, latex_document: LaTeXDocument) -> str:
        """Process cross-references (\\ref commands).
        
        Args:
            content: Content to process
            latex_document: LaTeX document
            
        Returns:
            Content with cross-references converted to HTML
        """
        def replace_ref(match):
            label = match.group(1)
            
            # Check if it's a figure reference
            if label in latex_document.figures:
                figure = latex_document.figures[label]
                if figure.number:
                    return f'<a href="#{label}" class="figure-ref">Figure {figure.number}</a>'
            
            # Check if it's an equation reference
            if label in latex_document.equations:
                equation = latex_document.equations[label]
                if equation.number:
                    return f'<a href="#{label}" class="equation-ref">Equation ({equation.number})</a>'
            
            # Default reference
            return f'<a href="#{label}" class="ref">{label}</a>'
        
        return re.sub(r'\\ref\{([^}]+)\}', replace_ref, content)
    
    def _process_inline_equations(self, content: str, latex_document: LaTeXDocument) -> str:
        """Process inline equations in content.
        
        Args:
            content: Content to process
            latex_document: LaTeX document
            
        Returns:
            Content with inline equations converted to HTML
        """
        # Process inline math
        def replace_inline_math(match):
            math_content = match.group(1)
            if self.config.math_renderer == MathRenderer.MATHJAX:
                return f'\\({math_content}\\)'
            else:  # KaTeX
                return f'<span class="katex-inline">\\({math_content}\\)</span>'
        
        content = re.sub(r'\$([^$]+)\$', replace_inline_math, content)
        content = re.sub(r'\\[(]([^)]+)\\[)]', replace_inline_math, content)
        
        return content
    
    def _process_inline_figures(self, content: str, latex_document: LaTeXDocument) -> str:
        """Process inline figure references.
        
        Args:
            content: Content to process
            latex_document: LaTeX document
            
        Returns:
            Content with figures converted to HTML
        """
        # For now, we'll leave figure processing to the main figure processor
        # This could be extended to handle inline graphics
        return content
    
    def _process_text_formatting(self, content: str) -> str:
        """Process basic text formatting commands.
        
        Args:
            content: Content to process
            
        Returns:
            Content with formatting converted to HTML
        """
        # Bold text
        content = re.sub(r'\\textbf\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', r'<strong>\1</strong>', content)
        
        # Italic text
        content = re.sub(r'\\textit\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', r'<em>\1</em>', content)
        content = re.sub(r'\\emph\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', r'<em>\1</em>', content)
        
        # Typewriter text
        content = re.sub(r'\\texttt\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', r'<code>\1</code>', content)
        
        # Remove remaining simple commands
        content = re.sub(r'\\[a-zA-Z]+\*?\s*', '', content)
        content = re.sub(r'[{}]', '', content)
        
        return content
    
    def _convert_paragraphs(self, content: str) -> str:
        """Convert paragraph breaks to HTML.
        
        Args:
            content: Content to process
            
        Returns:
            Content with HTML paragraphs
        """
        # Split on double newlines (paragraph breaks)
        paragraphs = re.split(r'\n\s*\n', content.strip())
        
        # Wrap non-empty paragraphs in <p> tags
        html_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            if para:
                html_paragraphs.append(f'<p>{para}</p>')
        
        return '\n'.join(html_paragraphs)
    
    def _generate_bibliography(self, latex_document: LaTeXDocument) -> str:
        """Generate bibliography HTML.
        
        Args:
            latex_document: LaTeX document
            
        Returns:
            Bibliography HTML
        """
        if not latex_document.bibliography or not latex_document.bibliography.citations:
            return ""
        
        return self.citation_processor.generate_bibliography_html(latex_document.bibliography)
    
    def _generate_css_includes(self) -> str:
        """Generate CSS include tags."""
        css_links = []
        
        # Math renderer CSS
        for css_url in self.equation_processor.get_required_styles():
            css_links.append(f'<link rel="stylesheet" href="{css_url}">')
        
        return '\n    '.join(css_links)
    
    def _generate_js_includes(self) -> str:
        """Generate JavaScript include tags."""
        js_scripts = []
        
        # Math renderer scripts
        for js_url in self.equation_processor.get_required_scripts():
            js_scripts.append(f'<script src="{js_url}"></script>')
        
        return '\n    '.join(js_scripts)
    
    def _generate_inline_css(self) -> str:
        """Generate inline CSS for paper styling."""
        return '''
        /* Paper Layout */
        body {
            font-family: 'Times New Roman', serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #fafafa;
        }
        
        .paper {
            background: white;
            padding: 40px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            border-radius: 5px;
        }
        
        /* Header */
        .paper-header {
            text-align: center;
            margin-bottom: 40px;
            border-bottom: 2px solid #333;
            padding-bottom: 20px;
        }
        
        .paper-title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 20px;
            color: #333;
        }
        
        .paper-authors {
            font-size: 16px;
            margin-bottom: 20px;
            color: #666;
        }
        
        .author {
            font-weight: 500;
        }
        
        .paper-abstract {
            margin: 20px 0;
            padding: 20px;
            background: #f8f9fa;
            border-left: 4px solid #007bff;
        }
        
        .paper-abstract h2 {
            margin-top: 0;
            font-size: 18px;
            color: #333;
        }
        
        /* Sections */
        .paper-section {
            margin: 30px 0;
        }
        
        .section-title {
            color: #333;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
        }
        
        .level-1 .section-title {
            font-size: 20px;
        }
        
        .level-2 .section-title {
            font-size: 18px;
        }
        
        .level-3 .section-title {
            font-size: 16px;
        }
        
        /* Figures */
        .figure {
            margin: 20px 0;
            text-align: center;
        }
        
        .figure-img {
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 4px;
        }
        
        .figure-caption {
            margin-top: 10px;
            font-style: italic;
            color: #666;
            font-size: 14px;
        }
        
        /* Equations */
        .equation {
            margin: 20px 0;
            text-align: center;
            position: relative;
        }
        
        .katex-display {
            margin: 20px 0;
            position: relative;
        }
        
        .equation-number {
            position: absolute;
            right: 0;
            top: 50%;
            transform: translateY(-50%);
        }
        
        /* Citations */
        .citation {
            color: #007bff;
            text-decoration: none;
        }
        
        .citation:hover {
            text-decoration: underline;
        }
        
        .citation-missing {
            color: #dc3545;
            font-weight: bold;
        }
        
        /* Cross-references */
        .figure-ref, .equation-ref, .ref {
            color: #007bff;
            text-decoration: none;
        }
        
        .figure-ref:hover, .equation-ref:hover, .ref:hover {
            text-decoration: underline;
        }
        
        /* Bibliography */
        .bibliography {
            margin-top: 40px;
            border-top: 2px solid #333;
            padding-top: 20px;
        }
        
        .bibliography h2 {
            font-size: 20px;
            margin-bottom: 20px;
            color: #333;
        }
        
        .bibliography-list {
            list-style: none;
            padding: 0;
            counter-reset: bib-counter;
        }
        
        .bibliography-entry {
            counter-increment: bib-counter;
            margin-bottom: 15px;
            padding-left: 40px;
            position: relative;
            line-height: 1.5;
        }
        
        .bibliography-entry::before {
            content: "[" counter(bib-counter) "]";
            position: absolute;
            left: 0;
            top: 0;
            font-weight: bold;
            color: #666;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            body {
                padding: 10px;
            }
            
            .paper {
                padding: 20px;
            }
            
            .paper-title {
                font-size: 20px;
            }
        }
        '''