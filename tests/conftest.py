"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_latex_content():
    """Sample LaTeX content for testing."""
    return r"""
\documentclass{article}
\usepackage{graphicx}
\usepackage{amsmath}

\title{Sample Research Paper}
\author{John Doe \\ University of Example \and Jane Smith \\ Another University}

\begin{document}
\maketitle

\begin{abstract}
This is a sample abstract that describes the research paper.
It provides an overview of the methodology and findings.
\end{abstract}

\section{Introduction}
This is the introduction section of the paper.

\section{Methodology}
This section describes the research methodology.

\begin{equation}
E = mc^2
\label{eq:einstein}
\end{equation}

\begin{figure}[h]
\centering
\includegraphics[width=0.8\textwidth]{figures/result.png}
\caption{Main result showing the experimental findings.}
\label{fig:result}
\end{figure}

\section{Results}
This section presents the results of the research.

\section{Conclusion}
This section concludes the paper.

\bibliographystyle{plain}
\bibliography{bibliography}

\end{document}
"""


@pytest.fixture
def sample_bibliography():
    """Sample bibliography content for testing."""
    return """@article{einstein1905,
  title={Zur Elektrodynamik bewegter K{\"o}rper},
  author={Einstein, Albert},
  journal={Annalen der Physik},
  volume={17},
  number={10},
  pages={891--921},
  year={1905}
}

@book{feynman1963,
  title={The Feynman Lectures on Physics},
  author={Feynman, Richard P and Leighton, Robert B and Sands, Matthew},
  volume={1},
  year={1963},
  publisher={Addison-Wesley}
}

@inproceedings{doe2023,
  title={Advanced Research Methods},
  author={Doe, John and Smith, Jane},
  booktitle={Proceedings of the International Conference on Research},
  pages={123--145},
  year={2023}
}"""


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "paper": {
            "title": "Sample Research Paper",
            "authors": [
                {
                    "name": "John Doe",
                    "affiliation": "University of Example",
                    "url": "https://johndoe.example.com",
                },
                {
                    "name": "Jane Smith",
                    "affiliation": "Another University",
                    "email": "jane.smith@another.edu",
                },
            ],
            "abstract": "This is a sample abstract.",
            "keywords": ["research", "science", "methodology"],
            "arxiv_id": "2023.12345",
            "doi": "10.1234/sample.2023",
        },
        "website": {
            "theme": "modern",
            "show_pdf": True,
            "interactive_figures": True,
            "math_renderer": "katex",
            "syntax_highlighting": True,
        },
        "build": {"latex_engine": "pdflatex", "output_format": ["html", "pdf"]},
    }


@pytest.fixture
def project_structure(temp_dir):
    """Create a complete project structure for testing."""
    # Create directories
    src_dir = temp_dir / "src"
    paper_dir = src_dir / "paper"
    web_dir = src_dir / "web"
    assets_dir = web_dir / "assets"
    templates_dir = web_dir / "templates"
    figures_dir = paper_dir / "figures"
    docs_dir = temp_dir / "docs"

    for directory in [
        paper_dir,
        web_dir,
        assets_dir,
        templates_dir,
        figures_dir,
        docs_dir,
    ]:
        directory.mkdir(parents=True)

    # Create some sample files
    (paper_dir / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}Test\\end{document}"
    )
    (paper_dir / "bibliography.bib").write_text(
        "@article{test,title={Test},year={2023}}"
    )
    (figures_dir / "figure1.png").write_text("fake image data")
    (assets_dir / "custom.css").write_text("/* custom styles */")

    return {
        "root": temp_dir,
        "src": src_dir,
        "paper": paper_dir,
        "web": web_dir,
        "assets": assets_dir,
        "templates": templates_dir,
        "figures": figures_dir,
        "docs": docs_dir,
    }


@pytest.fixture
def mock_latex_file(temp_dir, sample_latex_content):
    """Create a mock LaTeX file for testing."""
    latex_file = temp_dir / "test.tex"
    latex_file.write_text(sample_latex_content)
    return latex_file


@pytest.fixture
def mock_config_file(temp_dir, sample_config):
    """Create a mock configuration file for testing."""
    import yaml

    config_file = temp_dir / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(sample_config, f)

    return config_file


# Pytest markers
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")


# Skip slow tests by default
def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle markers."""
    if config.getoption("--runslow"):
        return

    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


def pytest_addoption(parser):
    """Add command line options."""
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )
