"""Tests for HTML converter."""

import pytest
from pathlib import Path
from paperflow.processors.latex.html_converter import HTMLConverter
from paperflow.models.processor import ProcessorConfig, MathRenderer, CitationStyle


class TestHTMLConverter:
    """Test cases for HTML converter."""
    
    def setup_method(self):
        """Set up test environment."""
        self.converter = HTMLConverter()
    
    def test_convert_simple_document(self):
        """Test converting a simple LaTeX document to HTML."""
        latex_content = r"""
        \documentclass{article}
        \title{Test Paper}
        \author{Jane Smith}
        
        \begin{document}
        \maketitle
        
        \begin{abstract}
        This is a comprehensive test of the HTML conversion system.
        \end{abstract}
        
        \section{Introduction}
        This paper presents a novel approach to \textbf{testing} HTML conversion.
        
        \subsection{Motivation}
        The motivation is to ensure \emph{quality} output.
        
        \section{Methodology}
        Our approach uses advanced \textit{parsing} techniques.
        
        \section{Conclusion}
        The results demonstrate the effectiveness of our approach.
        
        \end{document}
        """
        
        # Parse the document first
        parse_result = self.converter.latex_parser.parse_content(latex_content)
        assert parse_result.is_successful
        
        # Convert to HTML
        result = self.converter.convert_document(parse_result.latex_document)
        
        assert result.is_successful
        assert result.html_document is not None
        
        html_content = result.html_document.html_content
        
        # Check basic structure
        assert "<!DOCTYPE html>" in html_content
        assert "<title>Test Paper</title>" in html_content
        assert "Jane Smith" in html_content
        assert "comprehensive test" in html_content
        
        # Check sections
        assert "Introduction" in html_content
        assert "Motivation" in html_content
        assert "Methodology" in html_content
        assert "Conclusion" in html_content
        
        # Check formatting conversion
        assert "<strong>testing</strong>" in html_content
        assert "<em>quality</em>" in html_content
        assert "<em>parsing</em>" in html_content
    
    def test_convert_with_equations(self):
        """Test converting document with equations."""
        latex_content = r"""
        \section{Mathematics}
        
        The fundamental equation is:
        \begin{equation}
        E = mc^2
        \label{eq:einstein}
        \end{equation}
        
        We also have inline math: $F = ma$.
        
        See Equation~\ref{eq:einstein} for details.
        """
        
        parse_result = self.converter.latex_parser.parse_content(latex_content)
        result = self.converter.convert_document(parse_result.latex_document)
        
        assert result.is_successful
        html_content = result.html_document.html_content
        
        # Check MathJax content
        assert "\\(F = ma\\)" in html_content  # Inline math
        assert "E = mc^2" in html_content  # Display math
        
        # Check equation reference
        assert 'href="#eq:einstein"' in html_content or "eq:einstein" in html_content
    
    def test_convert_with_figures(self):
        """Test converting document with figures."""
        latex_content = r"""
        \section{Results}
        
        The results are shown in Figure~\ref{fig:results}.
        
        \begin{figure}[htbp]
        \centering
        \includegraphics[width=0.8\textwidth]{results.png}
        \caption{Experimental results showing improved performance.}
        \label{fig:results}
        \end{figure}
        
        As demonstrated above, our method works well.
        """
        
        parse_result = self.converter.latex_parser.parse_content(latex_content)
        result = self.converter.convert_document(parse_result.latex_document)
        
        assert result.is_successful
        html_content = result.html_document.html_content
        
        # Check figure HTML structure
        assert "<figure" in html_content
        assert "<img" in html_content
        assert "<figcaption" in html_content
        assert "Experimental results" in html_content
        assert "results.png" in html_content
        
        # Check figure reference
        assert 'href="#fig:results"' in html_content or "Figure" in html_content
    
    def test_convert_with_citations(self):
        """Test converting document with citations."""
        latex_content = r"""
        \section{Related Work}
        
        Previous studies \cite{smith2020,jones2019} have shown important results.
        According to \citet{brown2021}, this approach is promising.
        
        \bibliography{references}
        """
        
        # Create a mock bibliography
        from paperflow.models.processor import Bibliography, Citation
        bibliography = Bibliography()
        bibliography.add_citation(Citation(
            key="smith2020",
            entry_type="article", 
            title="Important Research",
            author="Smith, John",
            journal="Journal of Science",
            year="2020"
        ))
        bibliography.add_citation(Citation(
            key="jones2019",
            entry_type="article",
            title="Foundational Work", 
            author="Jones, Jane",
            journal="Science Letters",
            year="2019"
        ))
        bibliography.add_citation(Citation(
            key="brown2021",
            entry_type="book",
            title="Advanced Methods",
            author="Brown, Bob",
            publisher="Academic Press",
            year="2021"
        ))
        
        parse_result = self.converter.latex_parser.parse_content(latex_content)
        parse_result.latex_document.bibliography = bibliography
        
        result = self.converter.convert_document(parse_result.latex_document)
        
        assert result.is_successful
        html_content = result.html_document.html_content
        
        # Check citation formatting
        assert "[1]" in html_content or "[2]" in html_content  # Citation numbers
        assert 'class="citation"' in html_content
        
        # Check bibliography section
        assert "References" in html_content
        assert "Smith, John" in html_content
        assert "Jones, Jane" in html_content
        assert "Brown, Bob" in html_content
    
    def test_convert_with_custom_config(self):
        """Test converting with custom configuration."""
        config = ProcessorConfig(
            math_renderer=MathRenderer.KATEX,
            citation_style=CitationStyle.APA,
            enable_equation_numbering=True,
            enable_figure_numbering=True
        )
        
        converter = HTMLConverter(config)
        
        latex_content = r"""
        \title{Custom Config Test}
        \section{Test}
        Math: $x = y$
        """
        
        parse_result = converter.latex_parser.parse_content(latex_content)
        result = converter.convert_document(parse_result.latex_document)
        
        assert result.is_successful
        html_content = result.html_document.html_content
        
        # Check KaTeX is used
        assert result.html_document.math_renderer == MathRenderer.KATEX
        assert "katex" in html_content.lower()
    
    def test_css_and_js_includes(self):
        """Test that required CSS and JS are included."""
        latex_content = r"""
        \title{Include Test}
        \section{Test}
        Math: $E = mc^2$
        """
        
        parse_result = self.converter.latex_parser.parse_content(latex_content)
        result = self.converter.convert_document(parse_result.latex_document)
        
        assert result.is_successful
        html_content = result.html_document.html_content
        
        # Check MathJax includes (default renderer)
        assert "mathjax" in html_content.lower()
        assert "<script" in html_content
        
        # Check inline CSS
        assert "<style>" in html_content
        assert "font-family" in html_content
        assert ".paper" in html_content
    
    def test_responsive_design(self):
        """Test that responsive design elements are included."""
        latex_content = r"""
        \title{Responsive Test}
        \section{Content}
        Test content.
        """
        
        parse_result = self.converter.latex_parser.parse_content(latex_content)
        result = self.converter.convert_document(parse_result.latex_document)
        
        assert result.is_successful
        html_content = result.html_document.html_content
        
        # Check viewport meta tag
        assert 'name="viewport"' in html_content
        
        # Check responsive CSS
        assert "@media" in html_content
        assert "max-width" in html_content
    
    def test_semantic_html_structure(self):
        """Test that semantic HTML5 structure is used."""
        latex_content = r"""
        \title{Semantic Test}
        \author{Test Author}
        
        \begin{abstract}
        Test abstract.
        \end{abstract}
        
        \section{Introduction}
        Introduction content.
        """
        
        parse_result = self.converter.latex_parser.parse_content(latex_content)
        result = self.converter.convert_document(parse_result.latex_document)
        
        assert result.is_successful
        html_content = result.html_document.html_content
        
        # Check semantic elements
        assert "<article" in html_content
        assert "<header" in html_content
        assert "<section" in html_content
        
        # Check proper heading hierarchy
        assert "<h1" in html_content  # Title
        assert "<h2" in html_content  # Sections
    
    def test_error_handling(self):
        """Test error handling in conversion."""
        # Test with None document
        result = self.converter.convert_document(None)
        assert not result.is_successful
        assert len(result.errors) > 0
    
    def test_statistics_collection(self):
        """Test that conversion statistics are collected."""
        latex_content = r"""
        \title{Statistics Test}
        \section{Test}
        Content with \cite{ref1}.
        
        \begin{equation}
        x = y
        \end{equation}
        
        \begin{figure}
        \includegraphics{image.png}
        \caption{Test}
        \end{figure}
        """
        
        parse_result = self.converter.latex_parser.parse_content(latex_content)
        result = self.converter.convert_document(parse_result.latex_document)
        
        assert result.is_successful
        assert 'sections' in result.statistics
        assert 'figures' in result.statistics
        assert 'equations' in result.statistics
        
        # Verify reasonable counts
        assert result.statistics['sections'] >= 1
        assert result.statistics['figures'] >= 1
        assert result.statistics['equations'] >= 1