"""Tests for LaTeX parser."""

import pytest
from pathlib import Path
from paperflow.processors.latex.latex_parser import LaTeXParser
from paperflow.models.processor import ProcessingStatus


class TestLaTeXParser:
    """Test cases for LaTeX parser."""
    
    def setup_method(self):
        """Set up test environment."""
        self.parser = LaTeXParser()
    
    def test_parse_simple_document(self):
        """Test parsing a simple LaTeX document."""
        latex_content = r"""
        \documentclass{article}
        \title{Test Document}
        \author{John Doe}
        
        \begin{document}
        \maketitle
        
        \begin{abstract}
        This is a test abstract.
        \end{abstract}
        
        \section{Introduction}
        This is the introduction.
        
        \subsection{Background}
        Some background information.
        
        \section{Conclusion}
        This is the conclusion.
        
        \end{document}
        """
        
        result = self.parser.parse_content(latex_content)
        
        assert result.status == ProcessingStatus.SUCCESS
        assert result.latex_document is not None
        
        doc = result.latex_document
        assert doc.title == "Test Document"
        assert doc.authors == ["John Doe"]
        assert doc.abstract == "This is a test abstract."
        assert len(doc.sections) == 3  # Introduction, Background (subsection), Conclusion
    
    def test_parse_document_with_figures(self):
        """Test parsing document with figures."""
        latex_content = r"""
        \section{Results}
        Here are the results.
        
        \begin{figure}[htbp]
        \centering
        \includegraphics[width=0.5\textwidth]{test_image.png}
        \caption{Test image caption}
        \label{fig:test}
        \end{figure}
        
        As shown in Figure~\ref{fig:test}, the results are clear.
        """
        
        result = self.parser.parse_content(latex_content)
        
        assert result.status == ProcessingStatus.SUCCESS
        doc = result.latex_document
        
        assert len(doc.figures) == 1
        figure = list(doc.figures.values())[0]
        assert figure.caption == "Test image caption"
        assert figure.label == "fig:test"
        assert str(figure.file_path).endswith("test_image.png")
    
    def test_parse_document_with_equations(self):
        """Test parsing document with equations."""
        latex_content = r"""
        \section{Mathematics}
        
        The equation is:
        \begin{equation}
        E = mc^2
        \label{eq:einstein}
        \end{equation}
        
        We also have inline math like $x + y = z$.
        """
        
        result = self.parser.parse_content(latex_content)
        
        assert result.status == ProcessingStatus.SUCCESS
        doc = result.latex_document
        
        # Should find the labeled equation
        assert len([eq for eq in doc.equations.values() if eq.label]) >= 1
        
        # Check if Einstein equation was captured
        einstein_eq = doc.equations.get("eq:einstein")
        assert einstein_eq is not None
        assert "E = mc^2" in einstein_eq.latex_code
        assert not einstein_eq.is_inline
    
    def test_parse_document_with_citations(self):
        """Test parsing document with citations."""
        latex_content = r"""
        \section{Related Work}
        
        Previous research \cite{smith2020} has shown that \citep{jones2019,brown2021}
        are important. According to \citet{davis2018}, this is significant.
        
        \bibliography{references}
        """
        
        result = self.parser.parse_content(latex_content)
        
        assert result.status == ProcessingStatus.SUCCESS
        doc = result.latex_document
        
        # Should find cross-references (citations are parsed as cross-references)
        assert len(doc.cross_references) > 0
        
        # Should find bibliography metadata
        assert 'bibliography_files' in doc.metadata
        assert 'references.bib' in doc.metadata['bibliography_files']
    
    def test_parse_complex_sections(self):
        """Test parsing complex section hierarchy."""
        latex_content = r"""
        \section{Main Section}
        Main content.
        
        \subsection{First Subsection}
        First subsection content.
        
        \subsubsection{First Subsubsection}
        Subsubsection content.
        
        \subsection{Second Subsection}
        Second subsection content.
        
        \section{Another Main Section}
        Another main section.
        """
        
        result = self.parser.parse_content(latex_content)
        
        assert result.status == ProcessingStatus.SUCCESS
        doc = result.latex_document
        
        # Check section structure
        assert len(doc.sections) == 5  # All sections at their respective levels
        
        # Check section levels
        levels = [section.level for section in doc.sections]
        assert 1 in levels  # Main sections
        assert 2 in levels  # Subsections
        assert 3 in levels  # Subsubsections
    
    def test_parse_text_formatting(self):
        """Test parsing text formatting commands."""
        latex_content = r"""
        \section{Formatting Test}
        
        This has \textbf{bold text} and \textit{italic text}.
        Also \emph{emphasized text}.
        """
        
        result = self.parser.parse_content(latex_content)
        
        assert result.status == ProcessingStatus.SUCCESS
        doc = result.latex_document
        
        section_content = doc.sections[0].content
        # The parser should clean some LaTeX, but preserve formatting info
        assert "bold text" in section_content
        assert "italic text" in section_content
        assert "emphasized text" in section_content
    
    def test_parse_empty_content(self):
        """Test parsing empty content."""
        result = self.parser.parse_content("")
        
        assert result.status == ProcessingStatus.SUCCESS
        doc = result.latex_document
        
        assert doc.title is None
        assert len(doc.authors) == 0
        assert doc.abstract is None
        assert len(doc.sections) == 0
    
    def test_parse_malformed_latex(self):
        """Test parsing malformed LaTeX."""
        latex_content = r"""
        \section{Broken Section
        Missing closing brace...
        
        \begin{figure}
        \includegraphics{image.png}
        % Missing \end{figure}
        """
        
        result = self.parser.parse_content(latex_content)
        
        # Should still parse what it can
        assert result.status in [ProcessingStatus.SUCCESS, ProcessingStatus.WARNING]
        
        # May have warnings about malformed content
        if result.status == ProcessingStatus.WARNING:
            assert len(result.warnings) > 0
    
    def test_statistics_generation(self):
        """Test that statistics are properly generated."""
        latex_content = r"""
        \title{Test Document}
        \author{Test Author}
        
        \section{Section 1}
        Content with \cite{ref1}.
        
        \begin{figure}
        \includegraphics{image.png}
        \caption{Test figure}
        \end{figure}
        
        \begin{equation}
        x = y
        \end{equation}
        """
        
        result = self.parser.parse_content(latex_content)
        
        assert result.status == ProcessingStatus.SUCCESS
        assert 'sections' in result.statistics
        assert 'figures' in result.statistics
        assert 'equations' in result.statistics
        assert 'cross_references' in result.statistics
        
        # Verify counts
        assert result.statistics['sections'] >= 1
        assert result.statistics['figures'] >= 1
        assert result.statistics['equations'] >= 1