"""Tests for website building functionality."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from build_website import WebsiteBuilder


class TestWebsiteBuilder:
    """Test cases for WebsiteBuilder."""

    def test_init_default_config(self):
        """Test initialization with default configuration."""
        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = FileNotFoundError()
            builder = WebsiteBuilder()

            assert builder.config == {}
            assert builder.source_dir == Path("src")
            assert builder.output_dir == Path("docs")

    def test_init_custom_config(self):
        """Test initialization with custom configuration."""
        config_content = """
website:
  theme: academic
  show_pdf: true
paper:
  title: Custom Paper
"""
        with patch("builtins.open", mock_open(read_data=config_content)):
            builder = WebsiteBuilder()

            assert builder.config["website"]["theme"] == "academic"
            assert builder.config["website"]["show_pdf"] is True
            assert builder.config["paper"]["title"] == "Custom Paper"

    def test_find_main_tex_standard_file(self):
        """Test finding main.tex file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create directory structure
            paper_dir = Path(temp_dir) / "src" / "paper"
            paper_dir.mkdir(parents=True)

            # Create main.tex
            main_tex = paper_dir / "main.tex"
            main_tex.write_text(
                r"\documentclass{article}\begin{document}Test\end{document}"
            )

            builder = WebsiteBuilder()
            builder.source_dir = Path(temp_dir) / "src"
            builder.paper_dir = paper_dir

            found_file = builder._find_main_tex()
            assert found_file == str(main_tex)

    def test_find_main_tex_alternative_names(self):
        """Test finding LaTeX file with alternative names."""
        with tempfile.TemporaryDirectory() as temp_dir:
            paper_dir = Path(temp_dir) / "src" / "paper"
            paper_dir.mkdir(parents=True)

            # Create paper.tex instead of main.tex
            paper_tex = paper_dir / "paper.tex"
            paper_tex.write_text(
                r"\documentclass{article}\begin{document}Test\end{document}"
            )

            builder = WebsiteBuilder()
            builder.source_dir = Path(temp_dir) / "src"
            builder.paper_dir = paper_dir

            found_file = builder._find_main_tex()
            assert found_file == str(paper_tex)

    def test_find_main_tex_no_file(self):
        """Test behavior when no LaTeX file is found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            paper_dir = Path(temp_dir) / "src" / "paper"
            paper_dir.mkdir(parents=True)

            builder = WebsiteBuilder()
            builder.source_dir = Path(temp_dir) / "src"
            builder.paper_dir = paper_dir

            found_file = builder._find_main_tex()
            assert found_file is None

    def test_generate_default_css(self):
        """Test CSS generation."""
        builder = WebsiteBuilder()
        css = builder._generate_default_css()

        assert "body {" in css
        assert "paper-header" in css
        assert "paper-title" in css
        assert "font-family" in css
        assert "responsive" in css.lower()

    def test_generate_theme_css_modern(self):
        """Test modern theme CSS generation."""
        builder = WebsiteBuilder()
        builder.config = {"website": {"theme": "modern"}}

        theme_css = builder._generate_theme_css()

        assert ":root {" in theme_css
        assert "--primary-color" in theme_css
        assert "gradient" in theme_css

    def test_generate_theme_css_academic(self):
        """Test academic theme CSS generation."""
        builder = WebsiteBuilder()
        builder.config = {"website": {"theme": "academic"}}

        theme_css = builder._generate_theme_css()

        assert ":root {" in theme_css
        assert "Times New Roman" in theme_css
        assert "--primary-color" in theme_css

    def test_generate_theme_css_minimal(self):
        """Test minimal theme CSS generation."""
        builder = WebsiteBuilder()
        builder.config = {"website": {"theme": "minimal"}}

        theme_css = builder._generate_theme_css()

        assert ":root {" in theme_css
        assert "font-weight: 300" in theme_css

    def test_create_default_assets(self):
        """Test creation of default assets."""
        with tempfile.TemporaryDirectory() as temp_dir:
            builder = WebsiteBuilder()
            builder.output_dir = Path(temp_dir) / "docs"

            builder._create_default_assets()

            assets_dir = builder.output_dir / "assets"
            assert assets_dir.exists()
            assert (assets_dir / "style.css").exists()
            assert (assets_dir / "theme.css").exists()

            # Check CSS content
            with open(assets_dir / "style.css", "r") as f:
                css_content = f.read()
                assert "body {" in css_content

    def test_copy_assets_existing(self):
        """Test copying existing assets."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create source assets
            src_assets = Path(temp_dir) / "src" / "web" / "assets"
            src_assets.mkdir(parents=True)

            # Create some asset files
            (src_assets / "custom.css").write_text("/* custom styles */")
            (src_assets / "script.js").write_text("console.log('test');")

            builder = WebsiteBuilder()
            builder.source_dir = Path(temp_dir) / "src"
            builder.output_dir = Path(temp_dir) / "docs"
            builder.web_dir = Path(temp_dir) / "src" / "web"

            builder._copy_assets()

            # Check files were copied
            dst_assets = builder.output_dir / "assets"
            assert (dst_assets / "custom.css").exists()
            assert (dst_assets / "script.js").exists()

    def test_copy_figures(self):
        """Test copying figures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create source figures
            src_figures = Path(temp_dir) / "src" / "paper" / "figures"
            src_figures.mkdir(parents=True)

            # Create some figure files
            (src_figures / "figure1.png").write_text("fake image data")
            (src_figures / "figure2.jpg").write_text("fake image data")

            builder = WebsiteBuilder()
            builder.source_dir = Path(temp_dir) / "src"
            builder.output_dir = Path(temp_dir) / "docs"
            builder.paper_dir = Path(temp_dir) / "src" / "paper"

            builder._copy_figures()

            # Check figures were copied
            dst_figures = builder.output_dir / "figures"
            assert (dst_figures / "figure1.png").exists()
            assert (dst_figures / "figure2.jpg").exists()

    def test_generate_bibtex_page(self):
        """Test BibTeX page generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create BibTeX file
            bib_content = """@article{doe2023,
  title={Test Paper},
  author={Doe, John},
  journal={Test Journal},
  year={2023}
}"""

            bib_file = Path(temp_dir) / "bibliography.bib"
            bib_file.write_text(bib_content)

            builder = WebsiteBuilder()
            builder.output_dir = Path(temp_dir) / "docs"
            builder.output_dir.mkdir()

            builder._generate_bibtex_page(bib_file)

            # Check BibTeX page was created
            bibtex_page = builder.output_dir / "bibtex.html"
            assert bibtex_page.exists()

            content = bibtex_page.read_text()
            assert "Test Paper" in content
            assert "Doe, John" in content
            assert "<pre><code>" in content

    @patch("build_website.LatexToHtmlConverter")
    def test_convert_latex_to_html(self, mock_converter_class):
        """Test LaTeX to HTML conversion."""
        mock_converter = MagicMock()
        mock_converter_class.return_value = mock_converter

        builder = WebsiteBuilder()
        builder.output_dir = Path("docs")

        builder._convert_latex_to_html("test.tex")

        mock_converter_class.assert_called_once()
        mock_converter.convert_file.assert_called_once_with("test.tex", "docs")

    def test_build_no_main_tex(self):
        """Test build when no main.tex is found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            builder = WebsiteBuilder()
            builder.source_dir = Path(temp_dir) / "src"
            builder.output_dir = Path(temp_dir) / "docs"
            builder.paper_dir = Path(temp_dir) / "src" / "paper"
            builder.web_dir = Path(temp_dir) / "src" / "web"

            # Create directories but no tex file
            builder.paper_dir.mkdir(parents=True)
            builder.web_dir.mkdir(parents=True)

            result = builder.build()
            assert result is False

    @patch("build_website.LatexToHtmlConverter")
    def test_build_success(self, mock_converter_class):
        """Test successful build process."""
        mock_converter = MagicMock()
        mock_converter_class.return_value = mock_converter

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create directory structure
            src_dir = Path(temp_dir) / "src"
            paper_dir = src_dir / "paper"
            web_dir = src_dir / "web"

            paper_dir.mkdir(parents=True)
            web_dir.mkdir(parents=True)

            # Create main.tex
            main_tex = paper_dir / "main.tex"
            main_tex.write_text(
                r"\documentclass{article}\begin{document}Test\end{document}"
            )

            # Create bibliography
            bib_file = paper_dir / "bibliography.bib"
            bib_file.write_text(
                "@article{test,title={Test},author={Author},year={2023}}"
            )

            builder = WebsiteBuilder()
            builder.source_dir = src_dir
            builder.output_dir = Path(temp_dir) / "docs"
            builder.paper_dir = paper_dir
            builder.web_dir = web_dir

            result = builder.build()

            assert result is True
            assert builder.output_dir.exists()
            assert (builder.output_dir / "assets").exists()
            assert (builder.output_dir / "bibtex.html").exists()

            # Check that converter was called
            mock_converter.convert_file.assert_called_once()


class TestWebsiteBuilderIntegration:
    """Integration tests for WebsiteBuilder."""

    @pytest.mark.integration
    def test_full_build_workflow(self):
        """Test the complete build workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create complete directory structure
            src_dir = Path(temp_dir) / "src"
            paper_dir = src_dir / "paper"
            web_dir = src_dir / "web"
            assets_dir = web_dir / "assets"
            figures_dir = paper_dir / "figures"

            for dir_path in [paper_dir, web_dir, assets_dir, figures_dir]:
                dir_path.mkdir(parents=True)

            # Create LaTeX file
            latex_content = r"""
\documentclass{article}
\title{Integration Test Paper}
\author{Test Author}
\begin{document}
\maketitle
\begin{abstract}
This is a test abstract.
\end{abstract}
\section{Introduction}
Test content.
\end{document}
"""
            (paper_dir / "main.tex").write_text(latex_content)

            # Create bibliography
            bib_content = """@article{test2023,
  title={Test Reference},
  author={Test, Author},
  journal={Test Journal},
  year={2023}
}"""
            (paper_dir / "bibliography.bib").write_text(bib_content)

            # Create figures
            (figures_dir / "test_figure.png").write_text("fake image data")

            # Create custom assets
            (assets_dir / "custom.css").write_text("/* custom styles */")

            # Create config
            config_content = """
website:
  theme: modern
  show_pdf: true
  math_renderer: katex
paper:
  title: Integration Test Paper
  authors:
    - name: Test Author
      affiliation: Test University
"""
            config_file = Path(temp_dir) / "config.yaml"
            config_file.write_text(config_content)

            # Change to temp directory and build
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                builder = WebsiteBuilder()
                result = builder.build()

                assert result is True

                # Check output structure
                docs_dir = Path(temp_dir) / "docs"
                assert docs_dir.exists()
                assert (docs_dir / "index.html").exists()
                assert (docs_dir / "assets" / "style.css").exists()
                assert (docs_dir / "assets" / "theme.css").exists()
                assert (docs_dir / "figures" / "test_figure.png").exists()
                assert (docs_dir / "bibtex.html").exists()

                # Check HTML content
                with open(docs_dir / "index.html", "r") as f:
                    html_content = f.read()
                    assert "Integration Test Paper" in html_content
                    assert "Test Author" in html_content
                    assert "test abstract" in html_content
                    assert "katex" in html_content

                # Check BibTeX page
                with open(docs_dir / "bibtex.html", "r") as f:
                    bibtex_content = f.read()
                    assert "Test Reference" in bibtex_content
                    assert "Test, Author" in bibtex_content

            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__])
