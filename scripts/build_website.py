#!/usr/bin/env python3
"""
Main website builder script that orchestrates the entire build process.
"""

import shutil
import sys
from pathlib import Path

import yaml
from latex_to_html import LatexToHtmlConverter


class WebsiteBuilder:
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the website builder."""
        self.config = self._load_config(config_path)
        self.source_dir = Path("src")
        self.output_dir = Path("docs")
        self.paper_dir = self.source_dir / "paper"
        self.web_dir = self.source_dir / "web"

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Config file {config_path} not found")
            return {}

    def build(self):
        """Build the complete website."""
        print("Building research paper website...")

        # Create output directory
        self.output_dir.mkdir(exist_ok=True)

        # Copy static assets
        self._copy_assets()

        # Find main LaTeX file
        main_tex = self._find_main_tex()
        if not main_tex:
            print("No main.tex file found in src/paper/")
            return False

        # Convert LaTeX to HTML
        self._convert_latex_to_html(main_tex)

        # Copy figures
        self._copy_figures()

        # Generate additional pages
        self._generate_additional_pages()

        print("Website built successfully!")
        return True

    def _copy_assets(self):
        """Copy static assets to output directory."""
        assets_src = self.web_dir / "assets"
        assets_dst = self.output_dir / "assets"

        if assets_src.exists():
            if assets_dst.exists():
                shutil.rmtree(assets_dst)
            shutil.copytree(assets_src, assets_dst)
            print("Copied assets")
        else:
            # Create default assets
            self._create_default_assets()

    def _create_default_assets(self):
        """Create default CSS and JS assets."""
        assets_dir = self.output_dir / "assets"
        assets_dir.mkdir(exist_ok=True)

        # Create default CSS
        css_content = self._generate_default_css()
        with open(assets_dir / "style.css", "w") as f:
            f.write(css_content)

        # Create theme CSS
        theme_css = self._generate_theme_css()
        with open(assets_dir / "theme.css", "w") as f:
            f.write(theme_css)

        print("Created default assets")

    def _generate_default_css(self) -> str:
        """Generate default CSS styles."""
        return """
/* Reset and base styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
    color: #333;
    background-color: #fff;
}

/* Header styles */
.paper-header {
    text-align: center;
    padding: 2rem 0;
    border-bottom: 1px solid #eee;
    margin-bottom: 2rem;
}

.paper-title {
    font-size: 2.5rem;
    font-weight: 700;
    margin-bottom: 1rem;
    color: #1a1a1a;
}

.paper-authors {
    font-size: 1.1rem;
    color: #666;
    margin-bottom: 1.5rem;
}

.paper-links {
    display: flex;
    justify-content: center;
    gap: 1rem;
}

.btn {
    padding: 0.5rem 1rem;
    text-decoration: none;
    border-radius: 4px;
    font-weight: 500;
    transition: all 0.2s;
}

.btn-primary {
    background-color: #007bff;
    color: white;
}

.btn-primary:hover {
    background-color: #0056b3;
}

.btn-secondary {
    background-color: #6c757d;
    color: white;
}

.btn-secondary:hover {
    background-color: #545b62;
}

/* Content styles */
.paper-content {
    max-width: 800px;
    margin: 0 auto;
    padding: 0 2rem;
}

.abstract {
    background-color: #f8f9fa;
    padding: 2rem;
    border-radius: 8px;
    margin-bottom: 2rem;
}

.abstract h2 {
    color: #495057;
    margin-bottom: 1rem;
}

.content-section {
    margin-bottom: 3rem;
}

.content-section h2 {
    color: #343a40;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #007bff;
}

/* Figure styles */
.figure {
    margin: 2rem 0;
    text-align: center;
}

.figure img {
    max-width: 100%;
    height: auto;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.figure-caption {
    margin-top: 0.5rem;
    font-size: 0.9rem;
    color: #666;
}

/* Footer styles */
.paper-footer {
    text-align: center;
    padding: 2rem 0;
    margin-top: 3rem;
    border-top: 1px solid #eee;
    color: #666;
}

/* Responsive design */
@media (max-width: 768px) {
    .paper-title {
        font-size: 2rem;
    }
    
    .paper-content {
        padding: 0 1rem;
    }
    
    .abstract {
        padding: 1.5rem;
    }
}
"""

    def _generate_theme_css(self) -> str:
        """Generate theme-specific CSS."""
        theme = self.config.get("website", {}).get("theme", "modern")

        if theme == "modern":
            return """
/* Modern theme styles */
:root {
    --primary-color: #007bff;
    --secondary-color: #6c757d;
    --accent-color: #28a745;
    --background-color: #ffffff;
    --text-color: #333333;
    --border-color: #e9ecef;
}

.paper-header {
    background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
    color: white;
    padding: 3rem 0;
}

.paper-title {
    color: white;
    text-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.paper-authors {
    color: rgba(255,255,255,0.9);
}
"""
        elif theme == "academic":
            return """
/* Academic theme styles */
:root {
    --primary-color: #2c3e50;
    --secondary-color: #34495e;
    --accent-color: #3498db;
    --background-color: #ffffff;
    --text-color: #2c3e50;
    --border-color: #bdc3c7;
}

body {
    font-family: 'Times New Roman', serif;
}

.paper-header {
    background-color: var(--background-color);
    color: var(--text-color);
}

.paper-title {
    color: var(--primary-color);
    font-weight: 400;
}
"""
        else:  # minimal
            return """
/* Minimal theme styles */
:root {
    --primary-color: #000000;
    --secondary-color: #666666;
    --accent-color: #999999;
    --background-color: #ffffff;
    --text-color: #000000;
    --border-color: #cccccc;
}

.paper-header {
    background-color: var(--background-color);
    color: var(--text-color);
    border-bottom: 2px solid var(--border-color);
}

.paper-title {
    color: var(--primary-color);
    font-weight: 300;
}
"""

    def _find_main_tex(self) -> str:
        """Find the main LaTeX file."""
        possible_files = ["main.tex", "paper.tex", "document.tex"]

        for filename in possible_files:
            filepath = self.paper_dir / filename
            if filepath.exists():
                return str(filepath)

        # If no standard file found, look for any .tex file
        tex_files = list(self.paper_dir.glob("*.tex"))
        if tex_files:
            return str(tex_files[0])

        return None

    def _convert_latex_to_html(self, main_tex: str):
        """Convert LaTeX to HTML."""
        converter = LatexToHtmlConverter()
        converter.convert_file(main_tex, str(self.output_dir))
        print(f"Converted {main_tex} to HTML")

    def _copy_figures(self):
        """Copy figures from paper directory to output."""
        figures_src = self.paper_dir / "figures"
        figures_dst = self.output_dir / "figures"

        if figures_src.exists():
            if figures_dst.exists():
                shutil.rmtree(figures_dst)
            shutil.copytree(figures_src, figures_dst)
            print("Copied figures")

    def _generate_additional_pages(self):
        """Generate additional pages like BibTeX, etc."""
        # Generate BibTeX page
        bib_file = self.paper_dir / "bibliography.bib"
        if bib_file.exists():
            self._generate_bibtex_page(bib_file)

    def _generate_bibtex_page(self, bib_file: Path):
        """Generate a BibTeX citation page."""
        with open(bib_file, "r") as f:
            bib_content = f.read()

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BibTeX Citation</title>
    <link rel="stylesheet" href="assets/style.css">
    <link rel="stylesheet" href="assets/theme.css">
</head>
<body>
    <div class="paper-content">
        <h1>BibTeX Citation</h1>
        <pre><code>{bib_content}</code></pre>
        <a href="index.html" class="btn btn-primary">Back to Paper</a>
    </div>
</body>
</html>
"""

        with open(self.output_dir / "bibtex.html", "w") as f:
            f.write(html_content)

        print("Generated BibTeX page")


def main():
    """Main function."""
    builder = WebsiteBuilder()
    success = builder.build()

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
