"""Tests for LaTeX to HTML conversion."""

import os
import sys
import tempfile
from unittest.mock import mock_open, patch

import pytest

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from latex_to_html import LatexToHtmlConverter


class TestLatexToHtmlConverter:
    """Test cases for LatexToHtmlConverter."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = FileNotFoundError()
            converter = LatexToHtmlConverter()

            assert converter.config["website"]["math_renderer"] == "katex"
            assert converter.config["website"]["syntax_highlighting"] is True
            assert converter.config["build"]["latex_engine"] == "pdflatex"

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        config_content = """
website:
  math_renderer: mathjax
  syntax_highlighting: false
build:
  latex_engine: xelatex
"""
        with patch("builtins.open", mock_open(read_data=config_content)):
            converter = LatexToHtmlConverter()

            assert converter.config["website"]["math_renderer"] == "mathjax"
            assert converter.config["website"]["syntax_highlighting"] is False
            assert converter.config["build"]["latex_engine"] == "xelatex"

    def test_extract_title(self):
        """Test title extraction from LaTeX content."""
        converter = LatexToHtmlConverter()

        # Test with title in LaTeX
        latex_content = r"""
\documentclass{article}
\title{Test Paper Title}
\begin{document}
\maketitle
\end{document}
"""
        title = converter._extract_title(latex_content)
        assert title == "Test Paper Title"

        # Test without title (should use config default)
        latex_content_no_title = r"""
\documentclass{article}
\begin{document}
Content without title
\end{document}
"""
        title_default = converter._extract_title(latex_content_no_title)
        assert title_default == "Research Paper"

    def test_extract_authors(self):
        """Test author extraction from LaTeX content."""
        converter = LatexToHtmlConverter()

        # Test with authors in LaTeX
        latex_content = r"""
\author{John Doe \\ University of Example \and Jane Smith \\ Another University}
"""
        authors = converter._extract_authors(latex_content)
        assert len(authors) == 2
        assert "John Doe" in authors[0]
        assert "Jane Smith" in authors[1]

    def test_extract_abstract(self):
        """Test abstract extraction from LaTeX content."""
        converter = LatexToHtmlConverter()

        latex_content = r"""
\begin{abstract}
This is the abstract of the paper.
It contains multiple lines.
\end{abstract}
"""
        abstract = converter._extract_abstract(latex_content)
        assert "This is the abstract of the paper." in abstract
        assert "It contains multiple lines." in abstract

    def test_extract_figures(self):
        """Test figure extraction from LaTeX content."""
        converter = LatexToHtmlConverter()

        latex_content = r"""
\begin{figure}[h]
\centering
\includegraphics[width=0.8\textwidth]{figures/example.png}
\caption{This is a figure caption.}
\label{fig:example}
\end{figure}
"""
        figures = converter._extract_figures(latex_content)
        assert len(figures) == 1
        assert figures[0]["path"] == "figures/example.png"
        assert figures[0]["caption"] == "This is a figure caption."
        assert figures[0]["label"] == "fig:example"

    def test_extract_equations(self):
        """Test equation extraction from LaTeX content."""
        converter = LatexToHtmlConverter()

        latex_content = r"""
\begin{equation}
E = mc^2
\end{equation}
"""
        equations = converter._extract_equations(latex_content)
        assert len(equations) == 1
        assert equations[0]["content"] == "E = mc^2"
        assert equations[0]["type"] == "equation"

    def test_parse_latex(self):
        """Test complete LaTeX parsing."""
        converter = LatexToHtmlConverter()

        latex_content = r"""
\documentclass{article}
\title{Test Paper}
\author{Test Author}
\begin{document}
\maketitle
\begin{abstract}
Test abstract.
\end{abstract}
\section{Introduction}
This is the introduction.
\end{document}
"""

        parsed = converter._parse_latex(latex_content)

        assert parsed["title"] == "Test Paper"
        assert "Test Author" in parsed["authors"]
        assert parsed["abstract"] == "Test abstract."
        assert isinstance(parsed["sections"], list)
        assert isinstance(parsed["figures"], list)
        assert isinstance(parsed["equations"], list)

    def test_generate_html_head_katex(self):
        """Test HTML head generation with KaTeX."""
        converter = LatexToHtmlConverter()
        converter.config["website"]["math_renderer"] = "katex"

        parsed_content = {"title": "Test Paper"}
        head = converter._generate_html_head(parsed_content)

        assert "Test Paper" in head
        assert "katex" in head
        assert "DOCTYPE html" in head

    def test_generate_html_head_mathjax(self):
        """Test HTML head generation with MathJax."""
        converter = LatexToHtmlConverter()
        converter.config["website"]["math_renderer"] = "mathjax"

        parsed_content = {"title": "Test Paper"}
        head = converter._generate_html_head(parsed_content)

        assert "Test Paper" in head
        assert "mathjax" in head

    def test_generate_header(self):
        """Test header generation."""
        converter = LatexToHtmlConverter()

        parsed_content = {"title": "Test Paper", "authors": ["John Doe", "Jane Smith"]}
        header = converter._generate_header(parsed_content)

        assert "Test Paper" in header
        assert "John Doe" in header
        assert "Jane Smith" in header
        assert "paper-header" in header

    def test_generate_abstract(self):
        """Test abstract generation."""
        converter = LatexToHtmlConverter()

        # Test with abstract
        parsed_content = {"abstract": "This is the abstract."}
        abstract_html = converter._generate_abstract(parsed_content)

        assert "This is the abstract." in abstract_html
        assert "abstract" in abstract_html

        # Test without abstract
        parsed_content_no_abstract = {"abstract": ""}
        abstract_html_empty = converter._generate_abstract(parsed_content_no_abstract)

        assert abstract_html_empty == ""

    def test_convert_to_html(self):
        """Test complete HTML conversion."""
        converter = LatexToHtmlConverter()

        parsed_content = {
            "title": "Test Paper",
            "authors": ["Test Author"],
            "abstract": "Test abstract.",
            "sections": [],
            "figures": [],
            "equations": [],
        }

        html = converter._convert_to_html(parsed_content)

        assert "DOCTYPE html" in html
        assert "Test Paper" in html
        assert "Test Author" in html
        assert "Test abstract." in html
        assert "</html>" in html

    def test_convert_file(self):
        """Test file conversion."""
        converter = LatexToHtmlConverter()

        latex_content = r"""
\documentclass{article}
\title{Test Paper}
\author{Test Author}
\begin{document}
\maketitle
\begin{abstract}
Test abstract.
\end{abstract}
\section{Introduction}
This is the introduction.
\end{document}
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create input file
            input_file = os.path.join(temp_dir, "test.tex")
            with open(input_file, "w") as f:
                f.write(latex_content)

            # Create output directory
            output_dir = os.path.join(temp_dir, "output")

            # Convert file
            output_file = converter.convert_file(input_file, output_dir)

            # Check output file exists
            assert os.path.exists(output_file)
            assert output_file.endswith("index.html")

            # Check content
            with open(output_file, "r") as f:
                content = f.read()
                assert "Test Paper" in content
                assert "Test Author" in content
                assert "Test abstract." in content


class TestLatexToHtmlIntegration:
    """Integration tests for LaTeX to HTML conversion."""

    @pytest.mark.integration
    def test_full_conversion_workflow(self):
        """Test the complete conversion workflow."""
        converter = LatexToHtmlConverter()

        # Create a more complex LaTeX document
        latex_content = r"""
\documentclass{article}
\usepackage{graphicx}
\usepackage{amsmath}

\title{Advanced Research Paper}
\author{Dr. John Doe \\ University of Example \and Dr. Jane Smith \\ Another University}

\begin{document}
\maketitle

\begin{abstract}
This is a comprehensive abstract that describes the research paper.
It contains multiple sentences and provides an overview of the work.
\end{abstract}

\section{Introduction}
This is the introduction section.

\section{Methodology}
This section describes the methodology.

\begin{equation}
E = mc^2
\end{equation}

\begin{figure}[h]
\centering
\includegraphics[width=0.8\textwidth]{figures/result.png}
\caption{Main result figure showing important findings.}
\label{fig:result}
\end{figure}

\section{Results}
This section presents the results.

\section{Conclusion}
This is the conclusion.

\end{document}
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create input file
            input_file = os.path.join(temp_dir, "paper.tex")
            with open(input_file, "w") as f:
                f.write(latex_content)

            # Create output directory
            output_dir = os.path.join(temp_dir, "website")

            # Convert file
            output_file = converter.convert_file(input_file, output_dir)

            # Verify output
            assert os.path.exists(output_file)

            with open(output_file, "r") as f:
                html_content = f.read()

                # Check title
                assert "Advanced Research Paper" in html_content

                # Check authors
                assert "Dr. John Doe" in html_content
                assert "Dr. Jane Smith" in html_content

                # Check abstract
                assert "comprehensive abstract" in html_content

                # Check HTML structure
                assert "<!DOCTYPE html>" in html_content
                assert "<head>" in html_content
                assert "<body>" in html_content
                assert "</html>" in html_content

                # Check CSS links
                assert "style.css" in html_content
                assert "theme.css" in html_content

                # Check math rendering setup
                assert "katex" in html_content or "mathjax" in html_content


if __name__ == "__main__":
    pytest.main([__file__])
