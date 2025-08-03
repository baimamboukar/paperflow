"""Equation processor for converting LaTeX math to HTML with MathJax/KaTeX."""

import logging
import re
from typing import List

from paperflow.models.processor import (
    Equation,
    LaTeXDocument,
    MathRenderer,
    ProcessingError,
    ProcessingResult,
    ProcessingWarning,
)

logger = logging.getLogger(__name__)


class EquationProcessor:
    """Processor for handling mathematical equations."""

    def __init__(self, math_renderer: MathRenderer = MathRenderer.MATHJAX):
        """Initialize the equation processor.

        Args:
            math_renderer: Math rendering engine to use
        """
        self.math_renderer = math_renderer
        self._setup_patterns()

    def _setup_patterns(self) -> None:
        """Set up regex patterns for equation processing."""
        # Inline math patterns
        self.inline_math_patterns = [
            re.compile(r"\$([^$\n]+)\$"),  # Single dollar signs
            re.compile(r"\\[(]([^)]+)\\[)]"),  # \( ... \)
        ]

        # Display math patterns with environment names
        self.display_math_patterns = [
            (
                re.compile(r"\\begin\{equation\}(.*?)\\end\{equation\}", re.DOTALL),
                "equation",
                True,
            ),
            (
                re.compile(r"\\begin\{equation\*\}(.*?)\\end\{equation\*\}", re.DOTALL),
                "equation*",
                False,
            ),
            (
                re.compile(r"\\begin\{align\}(.*?)\\end\{align\}", re.DOTALL),
                "align",
                True,
            ),
            (
                re.compile(r"\\begin\{align\*\}(.*?)\\end\{align\*\}", re.DOTALL),
                "align*",
                False,
            ),
            (
                re.compile(r"\\begin\{gather\}(.*?)\\end\{gather\}", re.DOTALL),
                "gather",
                True,
            ),
            (
                re.compile(r"\\begin\{gather\*\}(.*?)\\end\{gather\*\}", re.DOTALL),
                "gather*",
                False,
            ),
            (
                re.compile(r"\\begin\{multline\}(.*?)\\end\{multline\}", re.DOTALL),
                "multline",
                True,
            ),
            (
                re.compile(r"\\begin\{multline\*\}(.*?)\\end\{multline\*\}", re.DOTALL),
                "multline*",
                False,
            ),
            (re.compile(r"\\\[(.*?)\\\]", re.DOTALL), "displaymath", False),
            (re.compile(r"\$\$(.*?)\$\$", re.DOTALL), "displaymath", False),
        ]

        # Label pattern
        self.label_pattern = re.compile(r"\\label\{([^}]+)\}")

        # Common LaTeX math commands that need special handling
        self.math_command_replacements = {
            r"\\text\{([^}]+)\}": r"\\text{\1}",  # Keep text commands
            r"\\mathrm\{([^}]+)\}": r"\\mathrm{\1}",
            r"\\mathbf\{([^}]+)\}": r"\\mathbf{\1}",
            r"\\mathit\{([^}]+)\}": r"\\mathit{\1}",
            r"\\mathcal\{([^}]+)\}": r"\\mathcal{\1}",
            r"\\mathfrak\{([^}]+)\}": r"\\mathfrak{\1}",
            r"\\mathbb\{([^}]+)\}": r"\\mathbb{\1}",
        }

    def process_equations(self, latex_document: LaTeXDocument) -> ProcessingResult:
        """Process equations in a LaTeX document for HTML conversion.

        Args:
            latex_document: LaTeX document to process

        Returns:
            ProcessingResult with processed equations
        """
        result = ProcessingResult(status="success")

        try:
            # Clear existing equations to reprocess
            latex_document.equations.clear()

            # Process all content
            all_content = self._gather_document_content(latex_document)

            # Process display equations
            equation_counter = self._process_display_equations(
                all_content, latex_document, result
            )

            # Process inline equations
            self._process_inline_equations(all_content, latex_document, result)

            # Update document sections with processed math
            self._update_document_content(latex_document, result)

            result.latex_document = latex_document
            result.statistics["equations_processed"] = len(latex_document.equations)

            logger.info(f"Processed {len(latex_document.equations)} equations")

        except Exception as e:
            logger.error(f"Error processing equations: {e}")
            error = ProcessingError(
                error_type="EquationProcessingError",
                message=f"Failed to process equations: {str(e)}",
                suggestion="Check LaTeX math syntax",
            )
            result.add_error(error)

        return result

    def _gather_document_content(self, latex_document: LaTeXDocument) -> str:
        """Gather all document content for equation processing."""
        content_parts = []

        if latex_document.abstract:
            content_parts.append(latex_document.abstract)

        for section in latex_document.sections:
            content_parts.append(section.content)

        return "\n\n".join(content_parts)

    def _process_display_equations(
        self, content: str, latex_document: LaTeXDocument, result: ProcessingResult
    ) -> int:
        """Process display equations and return the next equation number.

        Args:
            content: Document content to process
            latex_document: LaTeX document to update
            result: Processing result for errors/warnings

        Returns:
            Next equation number
        """
        equation_counter = 1

        for pattern, env_name, numbered in self.display_math_patterns:
            for match in pattern.finditer(content):
                equation_content = match.group(1).strip()

                # Clean and validate equation content
                cleaned_content = self._clean_equation_content(equation_content)

                if not cleaned_content:
                    warning = ProcessingWarning(
                        warning_type="EmptyEquation",
                        message=f"Empty equation found in {env_name} environment",
                        context=match.group(0)[:100],
                    )
                    result.add_warning(warning)
                    continue

                # Create equation object
                equation = Equation(
                    latex_code=cleaned_content,
                    is_inline=False,
                    renderer=self.math_renderer,
                )

                # Handle numbering
                if numbered:
                    equation.number = equation_counter
                    equation_counter += 1

                # Extract label if present
                label_match = self.label_pattern.search(equation_content)
                if label_match:
                    equation.label = label_match.group(1)
                    # Remove label from equation content for rendering
                    equation.latex_code = self.label_pattern.sub(
                        "", equation.latex_code
                    ).strip()

                # Add to document
                if equation.label:
                    latex_document.equations[equation.label] = equation
                else:
                    # Generate a unique key for unlabeled equations
                    key = f"eq_{match.start()}_{env_name}"
                    latex_document.equations[key] = equation

        return equation_counter

    def _process_inline_equations(
        self, content: str, latex_document: LaTeXDocument, result: ProcessingResult
    ) -> None:
        """Process inline equations.

        Args:
            content: Document content to process
            latex_document: LaTeX document to update
            result: Processing result for errors/warnings
        """
        for pattern in self.inline_math_patterns:
            for match in pattern.finditer(content):
                equation_content = match.group(1).strip()

                # Clean and validate equation content
                cleaned_content = self._clean_equation_content(equation_content)

                if not cleaned_content:
                    continue

                # Create inline equation
                equation = Equation(
                    latex_code=cleaned_content,
                    is_inline=True,
                    renderer=self.math_renderer,
                )

                # Generate unique key for inline equations
                key = f"inline_{match.start()}"
                latex_document.equations[key] = equation

    def _clean_equation_content(self, content: str) -> str:
        """Clean and normalize equation content.

        Args:
            content: Raw equation content

        Returns:
            Cleaned equation content
        """
        if not content:
            return ""

        # Remove extra whitespace
        content = re.sub(r"\s+", " ", content.strip())

        # Apply command replacements
        for pattern, replacement in self.math_command_replacements.items():
            content = re.sub(pattern, replacement, content)

        # Remove comments
        content = re.sub(r"%.*$", "", content, flags=re.MULTILINE)

        # Clean up spacing around operators
        content = re.sub(r"\s*=\s*", " = ", content)
        content = re.sub(r"\s*\+\s*", " + ", content)
        content = re.sub(r"\s*-\s*", " - ", content)

        return content.strip()

    def _update_document_content(
        self, latex_document: LaTeXDocument, result: ProcessingResult
    ) -> None:
        """Update document content with processed equations.

        Args:
            latex_document: LaTeX document to update
            result: Processing result for errors/warnings
        """
        # This method would update the content in sections to replace
        # LaTeX math with appropriate HTML placeholders
        # For now, we'll leave the original content intact
        pass

    def convert_to_html(self, equation: Equation) -> str:
        """Convert an equation to HTML.

        Args:
            equation: Equation to convert

        Returns:
            HTML representation of the equation
        """
        if self.math_renderer == MathRenderer.MATHJAX:
            return self._convert_to_mathjax_html(equation)
        elif self.math_renderer == MathRenderer.KATEX:
            return self._convert_to_katex_html(equation)
        else:
            return self._convert_to_mathjax_html(equation)  # Default fallback

    def _convert_to_mathjax_html(self, equation: Equation) -> str:
        """Convert equation to MathJax HTML.

        Args:
            equation: Equation to convert

        Returns:
            MathJax HTML representation
        """
        if equation.is_inline:
            return f"\\({equation.latex_code}\\)"
        else:
            if equation.number:
                # Numbered equation
                eq_id = f"eq-{equation.number}"
                if equation.label:
                    eq_id = equation.label

                return f'''<div class="equation" id="{eq_id}">
\\begin{{equation}}
{equation.latex_code} \\tag{{{equation.number}}}
\\end{{equation}}
</div>'''
            else:
                # Unnumbered equation
                return f"""<div class="equation">
\\[
{equation.latex_code}
\\]
</div>"""

    def _convert_to_katex_html(self, equation: Equation) -> str:
        """Convert equation to KaTeX HTML.

        Args:
            equation: Equation to convert

        Returns:
            KaTeX HTML representation
        """
        if equation.is_inline:
            return f'<span class="katex-inline">\\({equation.latex_code}\\)</span>'
        else:
            css_class = "katex-display"
            if equation.number:
                css_class += " katex-numbered"

            eq_id = ""
            if equation.label:
                eq_id = f'id="{equation.label}"'
            elif equation.number:
                eq_id = f'id="eq-{equation.number}"'

            number_span = ""
            if equation.number:
                number_span = (
                    f'<span class="equation-number">({equation.number})</span>'
                )

            return f'''<div class="{css_class}" {eq_id}>
<span class="katex-equation">\\[{equation.latex_code}\\]</span>
{number_span}
</div>'''

    def get_required_scripts(self) -> List[str]:
        """Get required JavaScript libraries for math rendering.

        Returns:
            List of script URLs or paths
        """
        if self.math_renderer == MathRenderer.MATHJAX:
            return [
                "https://polyfill.io/v3/polyfill.min.js?features=es6",
                "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js",
            ]
        elif self.math_renderer == MathRenderer.KATEX:
            return ["https://cdn.jsdelivr.net/npm/katex@0.16.0/dist/katex.min.js"]
        else:
            return []

    def get_required_styles(self) -> List[str]:
        """Get required CSS files for math rendering.

        Returns:
            List of CSS URLs or paths
        """
        if self.math_renderer == MathRenderer.KATEX:
            return ["https://cdn.jsdelivr.net/npm/katex@0.16.0/dist/katex.min.css"]
        else:
            return []

    def get_math_config(self) -> str:
        """Get JavaScript configuration for math rendering.

        Returns:
            JavaScript configuration code
        """
        if self.math_renderer == MathRenderer.MATHJAX:
            return """
<script>
window.MathJax = {
  tex: {
    inlineMath: [['\\\\(', '\\\\)']],
    displayMath: [['\\\\[', '\\\\]']],
    tags: 'ams',
    tagSide: 'right',
    tagIndent: '0.8em'
  },
  options: {
    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
  }
};
</script>"""
        elif self.math_renderer == MathRenderer.KATEX:
            return """
<script>
document.addEventListener("DOMContentLoaded", function() {
    renderMathInElement(document.body, {
        delimiters: [
            {left: "\\\\(", right: "\\\\)", display: false},
            {left: "\\\\[", right: "\\\\]", display: true}
        ]
    });
});
</script>"""
        else:
            return ""
