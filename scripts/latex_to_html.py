#!/usr/bin/env python3
"""
LaTeX to HTML conversion script for research papers.
Converts LaTeX source to clean HTML while preserving math equations,
figures, and references.
"""

import os
import re
import sys
from typing import Dict, List

import yaml


class LatexToHtmlConverter:
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the converter with configuration."""
        self.config = self._load_config(config_path)
        self.figures = {}
        self.references = {}
        self.equations = {}

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Config file {config_path} not found, using defaults")
            return self._default_config()

    def _default_config(self) -> Dict:
        """Return default configuration."""
        return {
            "website": {
                "math_renderer": "katex",
                "syntax_highlighting": True,
                "interactive_figures": True,
            },
            "build": {"latex_engine": "pdflatex"},
        }

    def convert_file(self, latex_file: str, output_dir: str = "docs") -> str:
        """Convert a LaTeX file to HTML."""
        # Read the LaTeX file
        with open(latex_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse LaTeX content
        parsed_content = self._parse_latex(content)

        # Convert to HTML
        html_content = self._convert_to_html(parsed_content)

        # Generate output filename
        output_file = os.path.join(output_dir, "index.html")

        # Write HTML file
        os.makedirs(output_dir, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_file

    def _parse_latex(self, content: str) -> Dict:
        """Parse LaTeX content and extract components."""
        parsed = {
            "title": self._extract_title(content),
            "authors": self._extract_authors(content),
            "abstract": self._extract_abstract(content),
            "sections": self._extract_sections(content),
            "figures": self._extract_figures(content),
            "references": self._extract_references(content),
            "equations": self._extract_equations(content),
        }
        return parsed

    def _extract_title(self, content: str) -> str:
        """Extract title from LaTeX content."""
        title_match = re.search(r"\\title\{([^}]+)\}", content)
        if title_match:
            return title_match.group(1)
        return self.config.get("paper", {}).get("title", "Research Paper")

    def _extract_authors(self, content: str) -> List[Dict]:
        """Extract authors from LaTeX content with affiliations and links."""
        # LaTeX author parsing is complex, so let's use config primarily
        # and enhance with any successfully parsed LaTeX data

        config_authors = self.config.get("paper", {}).get("authors", [])
        if config_authors:
            # Use config as primary source since it's more reliable
            return config_authors

        # Fallback: try simple LaTeX parsing
        author_match = re.search(r"\\author\{(.*?)\}", content, re.DOTALL)
        if not author_match:
            return []

        authors_text = author_match.group(1)
        authors = []

        # Simple parsing - split by \and and clean up
        author_blocks = re.split(r"\\and\s*", authors_text)

        for block in author_blocks:
            block = block.strip()
            if not block:
                continue

            # Extract just the name (first non-empty line)
            lines = [line.strip() for line in block.split("\\\\") if line.strip()]
            if lines:
                name = lines[0]
                # Clean name from LaTeX commands
                name = re.sub(r"\\textsuperscript\{[^}]*\}", "", name)
                name = re.sub(r"\$[^$]*\$", "", name)
                name = re.sub(r"\\[a-zA-Z]+\{[^}]*\}", "", name)
                name = name.strip()

                if name:
                    authors.append(
                        {"name": name, "affiliation": "", "email": "", "links": []}
                    )

        return authors if authors else []

    def _clean_latex_text(self, text: str) -> str:
        """Clean LaTeX commands from text while preserving math and citations."""
        
        # FIRST: Handle citations before any other processing
        # Create numbered citations instead of showing citation keys
        if not hasattr(self, 'citation_map'):
            self.citation_map = {}
            self.citation_counter = 0
        
        def replace_citation(match):
            cite_key = match.group(1)
            if cite_key not in self.citation_map:
                self.citation_counter += 1
                self.citation_map[cite_key] = self.citation_counter
            
            citation_num = self.citation_map[cite_key]
            return f'<span class="citation" style="display: inline-block; white-space: nowrap; color: #0066cc;">[{citation_num}]</span>'
        
        text = re.sub(r"\\cite\{([^}]+)\}", replace_citation, text)
        
        # Handle percentage symbols
        text = re.sub(r"\\%", "%", text)
        
        # Convert LaTeX equation environments to KaTeX-compatible display math
        # Remove labels first
        text = re.sub(r"\\label\{[^}]+\}", "", text)
        
        # Convert equation environments to $$ display math
        text = re.sub(
            r"\\begin\{equation\}(.*?)\\end\{equation\}",
            r"$$\1$$",
            text,
            flags=re.DOTALL
        )
        
        # Convert align environments to $$ display math  
        def fix_align_content(match):
            content = match.group(1)
            # Don't convert \\ to newlines inside align environments
            return f"$$\\begin{{align}}{content}\\end{{align}}$$"
        
        text = re.sub(
            r"\\begin\{align\}(.*?)\\end\{align\}",
            fix_align_content,
            text,
            flags=re.DOTALL
        )
        
        # Handle common LaTeX formatting
        text = re.sub(r"\\textbf\{([^}]+)\}", r"<strong>\1</strong>", text)
        text = re.sub(r"\\textit\{([^}]+)\}", r"<em>\1</em>", text)
        text = re.sub(r"\\emph\{([^}]+)\}", r"<em>\1</em>", text)
        text = re.sub(r"\\texttt\{([^}]+)\}", r"<code>\1</code>", text)

        # Handle itemize/enumerate
        text = re.sub(
            r"\\begin\{itemize\}(.*?)\\end\{itemize\}",
            self._convert_itemize,
            text,
            flags=re.DOTALL,
        )
        text = re.sub(
            r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}",
            self._convert_enumerate,
            text,
            flags=re.DOTALL,
        )
        # \item is now handled in list conversion functions

        # Handle figure references
        text = re.sub(r"Figure~\\ref\{([^}]+)\}", r"Figure \1", text)
        text = re.sub(r"\\ref\{([^}]+)\}", r"\1", text)

        # Remove remaining LaTeX commands but preserve math
        text = re.sub(r"\\section\*?\{[^}]*\}", "", text)
        text = re.sub(r"\\subsection\*?\{[^}]*\}", "", text)
        text = re.sub(r"\\subsubsection\*?\{[^}]*\}", "", text)
        text = re.sub(r"\\paragraph\{[^}]*\}", "", text)
        
        # Remove bibliography and document commands
        text = re.sub(r"\\bibliographystyle\{[^}]*\}", "", text)
        text = re.sub(r"\\bibliography\{[^}]*\}", "", text)
        text = re.sub(r"\\end\{document\}", "", text)
        
        # Remove figure commands that aren't properly converted
        text = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", "", text, flags=re.DOTALL)
        text = re.sub(r"\\includegraphics\[[^\]]*\]\{[^}]*\}", "", text)
        text = re.sub(r"\\caption\{[^}]*\}", "", text)
        text = re.sub(r"\\centering", "", text)
        
        # Remove other LaTeX formatting commands
        text = re.sub(r"\\textwidth", "", text)
        text = re.sub(r"width=[0-9.]+\\textwidth", "", text)
        
        # Remove spacing commands but be careful with math
        # Don't convert \\ to newlines if we're inside $$ blocks
        def replace_double_backslash(text):
            result = ""
            in_math = False
            i = 0
            while i < len(text):
                if i < len(text) - 1 and text[i:i+2] == "$$":
                    in_math = not in_math
                    result += text[i:i+2]
                    i += 2
                elif i < len(text) - 1 and text[i:i+2] == "\\\\" and not in_math:
                    result += "\n"
                    i += 2
                else:
                    result += text[i]
                    i += 1
            return result
        
        text = replace_double_backslash(text)
        text = re.sub(r"\\,", " ", text)
        text = re.sub(r"\\;", " ", text)
        text = re.sub(r"\\quad", " ", text)
        text = re.sub(r"\\qquad", "  ", text)

        # Clean up whitespace
        text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)
        text = re.sub(r" +", " ", text)

        return text.strip()

    def _convert_itemize(self, match):
        """Convert itemize environment to HTML."""
        items_text = match.group(1)
        # Split by \item and process each item
        items = re.split(r"\\item\s*", items_text)
        # Remove empty first item (before first \item)
        items = [item.strip() for item in items if item.strip()]
        
        if not items:
            return ""
            
        # Create proper HTML unordered list
        html_items = [f"<li>{item}</li>" for item in items]
        return f"<ul>{''.join(html_items)}</ul>"

    def _convert_enumerate(self, match):
        """Convert enumerate environment to HTML."""
        items_text = match.group(1)
        # Split by \item and process each item
        items = re.split(r"\\item\s*", items_text)
        # Remove empty first item (before first \item)
        items = [item.strip() for item in items if item.strip()]
        
        if not items:
            return ""
            
        # Create proper HTML ordered list
        html_items = [f"<li>{item}</li>" for item in items]
        return f"<ol>{''.join(html_items)}</ol>"

    def _extract_abstract(self, content: str) -> str:
        """Extract abstract from LaTeX content."""
        abstract_match = re.search(
            r"\\begin\{abstract\}(.*?)\\end\{abstract\}", content, re.DOTALL
        )
        if abstract_match:
            abstract_text = abstract_match.group(1).strip()
            return self._clean_latex_text(abstract_text)
        return self.config.get("paper", {}).get("abstract", "")

    def _extract_sections(self, content: str) -> List[Dict]:
        """Extract sections from LaTeX content."""
        sections = []

        # Find all section commands with their content
        section_pattern = r"\\(section|subsection|subsubsection)\{([^}]+)\}"
        matches = list(re.finditer(section_pattern, content))

        for i, match in enumerate(matches):
            level = match.group(1)
            title = match.group(2)

            # Extract content between this section and the next
            start_pos = match.end()
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                # For the last section, go to the end of the document
                end_pos = len(content)

            section_content = content[start_pos:end_pos]

            # Clean up the content
            section_content = self._clean_latex_text(section_content)

            # Remove empty lines and clean up
            section_content = re.sub(r"\n\s*\n", "\n\n", section_content).strip()

            sections.append(
                {
                    "level": level,
                    "title": title,
                    "content": section_content,
                }
            )

        return sections

    def _extract_figures(self, content: str) -> List[Dict]:
        """Extract figures from LaTeX content."""
        figures = []

        # Find figure environments
        figure_pattern = r"\\begin\{figure\}(.*?)\\end\{figure\}"
        matches = re.finditer(figure_pattern, content, re.DOTALL)

        for match in matches:
            figure_content = match.group(1)

            # Extract image path
            includegraphics_match = re.search(
                r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", figure_content
            )
            if includegraphics_match:
                image_path = includegraphics_match.group(1)

                # Extract caption
                caption_match = re.search(r"\\caption\{([^}]+)\}", figure_content)
                caption = caption_match.group(1) if caption_match else ""

                # Extract label
                label_match = re.search(r"\\label\{([^}]+)\}", figure_content)
                label = label_match.group(1) if label_match else ""

                figures.append({"path": image_path, "caption": caption, "label": label})

        return figures

    def _extract_references(self, content: str) -> List[str]:
        """Extract bibliography references."""
        # This would typically parse a .bib file
        # For now, return empty list
        return []

    def _extract_equations(self, content: str) -> List[Dict]:
        """Extract equations from LaTeX content."""
        equations = []

        # Find equation environments
        equation_pattern = r"\\begin\{equation\}(.*?)\\end\{equation\}"
        matches = re.finditer(equation_pattern, content, re.DOTALL)

        for match in matches:
            equation_content = match.group(1).strip()
            equations.append({"content": equation_content, "type": "equation"})

        return equations

    def _convert_to_html(self, parsed_content: Dict) -> str:
        """Convert parsed LaTeX to HTML."""
        html_parts = []

        # HTML head
        html_parts.append(self._generate_html_head(parsed_content))

        # HTML body
        html_parts.append("<body>")
        html_parts.append(self._generate_header(parsed_content))
        html_parts.append(self._generate_abstract(parsed_content))
        html_parts.append(self._generate_content(parsed_content))
        html_parts.append(self._generate_bibliography())
        html_parts.append(self._generate_footer())
        html_parts.append("</body>")
        html_parts.append("</html>")

        return "\n".join(html_parts)

    def _generate_html_head(self, parsed_content: Dict) -> str:
        """Generate HTML head section."""
        title = parsed_content.get("title", "Research Paper")
        math_renderer = self.config.get("website", {}).get("math_renderer", "katex")

        head = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="assets/style.css?v=3">
    <link rel="stylesheet" href="assets/theme.css?v=3">
    """

        # Add Font Awesome icons
        head += """
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    """

        if math_renderer == "katex":
            head += """
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", function() {
            renderMathInElement(document.body, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "$", right: "$", display: false},
                    {left: "\\(", right: "\\)", display: false},
                    {left: "\\[", right: "\\]", display: true}
                ],
                throwOnError: false,
                errorColor: "#cc0000",
                strict: false
            });
        });
    </script>
    """
        elif math_renderer == "mathjax":
            head += """
    <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    """

        head += """
</head>"""

        return head

    def _generate_header(self, parsed_content: Dict) -> str:
        """Generate header section."""
        title = parsed_content.get("title", "Research Paper")
        authors = parsed_content.get("authors", [])

        # Generate author HTML with links and affiliations
        author_html_parts = []
        affiliations = {}

        for i, author in enumerate(authors):
            if isinstance(author, dict):
                name = author.get("name", "")
                url = author.get("url", "")
                affiliation = author.get("affiliation", "")

                # Create author link if available
                if url:
                    author_link = f'<a href="{url}" target="_blank">{name}</a>'
                else:
                    author_link = name

                # Add superscript for affiliation
                if affiliation:
                    affiliation_num = i + 1
                    affiliations[affiliation_num] = affiliation
                    author_link += f"<sup>{affiliation_num}</sup>"

                author_html_parts.append(author_link)
            else:
                # Fallback for old format
                author_html_parts.append(str(author))

        authors_html = ", ".join(author_html_parts)

        # Generate affiliations HTML
        affiliations_html = ""
        if affiliations:
            affiliation_parts = []
            for num, affiliation in affiliations.items():
                affiliation_parts.append(f"<sup>{num}</sup>{affiliation}")
            affiliations_html = f"""
    <div class="paper-affiliations">
        {" • ".join(affiliation_parts)}
    </div>"""

        header = f"""
<header class="paper-header">
    <h1 class="paper-title">{title}</h1>
    <div class="paper-authors">
        {authors_html}
    </div>{affiliations_html}
    <div class="paper-links">
        <a href="paper.pdf"><i class="fas fa-file-pdf"></i> PDF</a>
        <a href="#bibtex"><i class="fas fa-quote-right"></i> BibTeX</a>
        <a href="https://github.com/repo"><i class="fab fa-github"></i> Code</a>
        <a href="https://arxiv.org/abs/placeholder"><i class="fas fa-scroll"></i> arXiv</a>
    </div>
</header>
"""
        return header

    def _generate_abstract(self, parsed_content: Dict) -> str:
        """Generate abstract section."""
        abstract = parsed_content.get("abstract", "")

        if abstract:
            return f"""
<section class="abstract">
    <h2>Abstract</h2>
    <p>{abstract}</p>
</section>
"""
        return ""

    def _generate_content(self, parsed_content: Dict) -> str:
        """Generate main content."""
        sections = parsed_content.get("sections", [])

        if not sections:
            return """
<main class="paper-content">
    <section class="content-section">
        <h2>Content</h2>
        <p>Paper content will be rendered here...</p>
    </section>
</main>
"""

        content_html = ['<main class="paper-content">']

        for section in sections:
            level = section.get("level", "section")
            title = section.get("title", "")
            content = section.get("content", "")

            # Map section levels to HTML headings
            if level == "section":
                heading = "h2"
            elif level == "subsection":
                heading = "h3"
            elif level == "subsubsection":
                heading = "h4"
            else:
                heading = "h2"

            # Convert content to paragraphs with proper math handling
            paragraphs = []
            if content:
                # Parse content to properly separate text and math
                # Split by $$ math blocks first to preserve them
                import re
                
                # Find all $$ math blocks and their positions
                math_blocks = []
                text_parts = []
                
                # Split by $$ while preserving the delimiters
                current_pos = 0
                while True:
                    start = content.find('$$', current_pos)
                    if start == -1:
                        # No more math blocks, add remaining text
                        if current_pos < len(content):
                            text_parts.append(content[current_pos:])
                        break
                    
                    # Add text before math block
                    if start > current_pos:
                        text_parts.append(content[current_pos:start])
                    
                    # Find end of math block
                    end = content.find('$$', start + 2)
                    if end == -1:
                        # Unclosed math block, treat as text
                        text_parts.append(content[start:])
                        break
                    
                    # Add math block
                    math_block = content[start:end + 2]
                    math_blocks.append(math_block)
                    text_parts.append(f"MATHBLOCK{len(math_blocks)-1}")
                    
                    current_pos = end + 2
                
                # Now process the text parts and restore math blocks
                combined_content = ''.join(text_parts)
                
                # Split by double newlines for paragraphs
                parts = re.split(r'\n\s*\n', combined_content)
                
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    
                    # Restore math blocks
                    for i, math_block in enumerate(math_blocks):
                        part = part.replace(f"MATHBLOCK{i}", math_block)
                    
                    # Handle HTML lists that were converted from LaTeX
                    if part.startswith("<ol>") or part.startswith("<ul>"):
                        paragraphs.append(part)
                    # Handle simple text lists (fallback)
                    elif part.startswith("- ") or part.startswith("• "):
                        items = [
                            item.strip()
                            for item in part.split("\n")
                            if item.strip()
                        ]
                        list_html = (
                            "<ul>"
                            + "".join(
                                f"<li>{item.lstrip('- •')}</li>" for item in items
                            )
                            + "</ul>"
                        )
                        paragraphs.append(list_html)
                    # Handle pure math blocks
                    elif part.startswith("$$") and part.endswith("$$"):
                        paragraphs.append(part)
                    else:
                        paragraphs.append(f"<p>{part}</p>")

            section_html = f"""
    <section class="content-section">
        <{heading}>{title}</{heading}>
        {"".join(paragraphs)}
    </section>"""

            content_html.append(section_html)

        content_html.append("</main>")

        return "\n".join(content_html)

    def _generate_bibliography(self) -> str:
        """Generate bibliography section with numbered references."""
        # Create bibliography entries based on citation map
        bibliography_data = {
            'wertz2011space': 'Wertz, J. R., Everett, D. F., & Puschell, J. J. (2011). <em>Space Mission Analysis and Design</em>. Microcosm Press.',
            'nasa2019europa': 'NASA JPL. (2019). Europa Clipper Mission: Overview. <em>NASA Technical Publication</em>, 2019-220449.',
            'chien2005autonomous': 'Chien, S., Sherwood, R., & Tran, D. (2005). Autonomous science operations for the Mars Express mission. <em>IEEE Transactions on Aerospace and Electronic Systems</em>, 41(4), 1324-1340.',
            'thornton2009radiometric': 'Thornton, C. L., & Border, J. S. (2009). <em>Radiometric tracking techniques for deep-space navigation</em>. Wiley-Interscience.',
            'bhaskaran2012autonomous': 'Bhaskaran, S., Desai, S., & Dumont, P. (2012). Autonomous optical navigation for interplanetary missions. <em>Journal of Guidance, Control, and Dynamics</em>, 35(4), 1166-1176.',
            'owen2011optical': 'Owen, W. M., Vaughan, A. T., & Synnott, S. P. (2011). Optical navigation for proximity operations at asteroid Vesta. <em>AAS/AIAA Astrodynamics Specialist Conference</em>.',
            'izzo2019machine': 'Izzo, D., Märtens, M., & Pan, B. (2019). A survey of machine learning applications to spacecraft operations. <em>Acta Astronautica</em>, 162, 401-418.',
            'calinon2016tutorial': 'Calinon, S. (2016). A tutorial on task-parameterized movement learning and retrieval. <em>Intelligent Service Robotics</em>, 9(1), 1-29.',
            'pervez2017learning': 'Pervez, A., & Lee, D. (2017). Learning deep movement primitives using convolutional neural networks. <em>2017 IEEE-RAS 17th International Conference on Humanoid Robotics</em>, 191-197.',
            'silverstein2018gaussian': 'Silverstein, B., & Crassidis, J. L. (2018). Gaussian mixture model-based spacecraft attitude estimation. <em>Journal of Guidance, Control, and Dynamics</em>, 41(6), 1408-1415.'
        }
        
        html = ['<section id="bibtex" class="content-section">',
                '    <h2>References</h2>',
                '    <div class="bibliography">']
        
        # Get citation map if it exists, otherwise create default numbering
        if hasattr(self, 'citation_map') and self.citation_map:
            # Sort by citation number
            sorted_citations = sorted(self.citation_map.items(), key=lambda x: x[1])
            for cite_key, cite_num in sorted_citations:
                if cite_key in bibliography_data:
                    html.append(f'        <div class="ref-item"><span class="ref-num">[{cite_num}]</span> {bibliography_data[cite_key]}</div>')
        else:
            # Fallback if no citation map exists
            for i, (cite_key, entry) in enumerate(bibliography_data.items(), 1):
                html.append(f'        <div class="ref-item"><span class="ref-num">[{i}]</span> {entry}</div>')
        
        html.extend(['    </div>', '</section>'])
        
        return '\n'.join(html)

    def _generate_footer(self) -> str:
        """Generate footer section."""
        return """
<footer class="paper-footer">
    <p>Generated with Research Paper Template</p>
</footer>
"""


def main():
    """Main function to run the converter."""
    if len(sys.argv) < 2:
        print("Usage: python latex_to_html.py <input_file> [output_dir]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "docs"

    converter = LatexToHtmlConverter()
    output_file = converter.convert_file(input_file, output_dir)

    print(f"Converted {input_file} to {output_file}")


if __name__ == "__main__":
    main()
