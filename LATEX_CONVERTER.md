# Paperflow LaTeX to HTML Converter

A comprehensive LaTeX to HTML conversion system that transforms academic papers into publication-quality web pages with perfect math rendering, citations, and responsive design.

## Features

### 🔍 **Document Structure Parsing**
- Hierarchical section parsing (`\section`, `\subsection`, `\subsubsection`, `\paragraph`)
- Document metadata extraction (title, authors, abstract)
- Label and cross-reference resolution
- Semantic HTML5 output structure

### 🧮 **Mathematical Content**
- **MathJax** and **KaTeX** support
- Inline math: `$...$` and `\(...\)`
- Display equations: `\begin{equation}`, `\begin{align}`, `\[...\]`
- Equation numbering and labeling
- Cross-references to equations

### 🖼️ **Figure Processing**
- `\includegraphics` command parsing
- Figure environment handling with captions
- Automatic figure numbering
- Image path resolution and validation
- Responsive image scaling
- Alt text generation for accessibility
- PIL-based image optimization

### 📚 **Citations and Bibliography**
- **BibTeX** file parsing with `bibtexparser`
- Multiple citation styles (IEEE, ACM, APA)
- Citation commands: `\cite{}`, `\citep{}`, `\citet{}`
- Automatic bibliography generation
- Citation linking and numbering
- Missing reference detection

### 🎨 **Styling and Layout**
- Publication-quality CSS styling
- Responsive design for all devices
- Academic journal-style formatting
- Proper typography and spacing
- Cross-reference highlighting
- Print-friendly layouts

### ⚡ **Advanced Features**
- Comprehensive error handling and warnings
- Processing statistics and reporting
- Configurable output options
- Template-based HTML generation
- Performance optimization for large documents

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Key dependencies:
- `bibtexparser>=1.4.0` - BibTeX file parsing
- `TexSoup>=0.3.1` - Enhanced LaTeX parsing
- `Pillow>=9.0.0` - Image processing
- `pydantic>=2.0.0` - Data validation

## Quick Start

### Basic Usage

```python
from paperflow.processors.latex.html_converter import HTMLConverter

# Create converter
converter = HTMLConverter()

# Convert LaTeX file to HTML
result = converter.convert_file(
    latex_file="paper.tex",
    output_file="paper.html",
    bibliography_files=["references.bib"]
)

if result.is_successful:
    print("Conversion completed!")
    print(f"Sections: {result.statistics['sections']}")
    print(f"Figures: {result.statistics['figures']}")
    print(f"Equations: {result.statistics['equations']}")
else:
    print("Conversion failed:")
    for error in result.errors:
        print(f"- {error.message}")
```

### Advanced Configuration

```python
from paperflow.models.processor import ProcessorConfig, MathRenderer, CitationStyle

# Configure processor
config = ProcessorConfig(
    math_renderer=MathRenderer.KATEX,  # or MathRenderer.MATHJAX
    citation_style=CitationStyle.IEEE,  # or APA, ACM
    enable_equation_numbering=True,
    enable_figure_numbering=True,
    enable_cross_references=True,
    figure_width="100%",
    output_encoding="utf-8"
)

converter = HTMLConverter(config)
```

## Supported LaTeX Features

### Document Structure
```latex
\title{Paper Title}
\author{Author Name}
\begin{abstract}...\end{abstract}
\section{Introduction}
\subsection{Background}
\subsubsection{Details}
\paragraph{Point}
```

### Mathematical Content
```latex
% Inline math
The equation $E = mc^2$ is famous.

% Display equations
\begin{equation}
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
\label{eq:gaussian}
\end{equation}

% Multiple environments
\begin{align}
x &= y + z \\
a &= b + c
\end{align}
```

### Figures
```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=0.8\textwidth]{image.png}
\caption{Figure caption}
\label{fig:example}
\end{figure}
```

### Citations
```latex
% Various citation commands
Previous work \cite{author2020} shows...
According to \citet{smith2019}, ...
Multiple studies \citep{jones2018,brown2021} indicate...

% Bibliography
\bibliography{references}
\bibliographystyle{plain}
```

### Text Formatting
```latex
\textbf{bold text}
\textit{italic text}
\emph{emphasized text}
\texttt{monospace text}
```

### Cross-References
```latex
\label{sec:intro}
See Section~\ref{sec:intro} and Figure~\ref{fig:example}.
Equation~\ref{eq:gaussian} shows the result.
```

## Architecture

### Core Components

```
paperflow/processors/latex/
├── latex_parser.py      # LaTeX document parsing
├── citation_processor.py # Bibliography and citations
├── equation_processor.py # Mathematical content
├── figure_processor.py  # Images and figures  
└── html_converter.py    # Main HTML generation
```

### Data Models

```
paperflow/models/processor.py
├── LaTeXDocument       # Parsed document structure
├── HTMLDocument        # Generated HTML output
├── Citation           # Bibliography entries
├── Bibliography       # Citation collections
├── Figure            # Image metadata
├── Equation          # Mathematical expressions
└── ProcessingResult  # Conversion results
```

### Processing Pipeline

1. **LaTeX Parsing** - Extract document structure and content
2. **Citation Processing** - Parse bibliography and resolve citations
3. **Equation Processing** - Convert math to MathJax/KaTeX format
4. **Figure Processing** - Handle images and generate HTML
5. **HTML Generation** - Combine all elements into semantic HTML
6. **Output Writing** - Save HTML with proper encoding

## Configuration Options

### ProcessorConfig

```python
config = ProcessorConfig(
    # Math rendering
    math_renderer=MathRenderer.MATHJAX,  # or KATEX
    
    # Citation style
    citation_style=CitationStyle.IEEE,   # IEEE, ACM, APA, etc.
    
    # Feature toggles
    enable_cross_references=True,
    enable_equation_numbering=True,
    enable_figure_numbering=True,
    
    # Output settings
    figure_width="100%",
    figure_format="webp",
    output_encoding="utf-8",
    base_url=None,
    
    # Template customization
    template_path=None
)
```

### Math Renderers

#### MathJax (Default)
- Comprehensive LaTeX support
- High-quality rendering
- Accessibility features
- Larger JavaScript bundle

#### KaTeX
- Fast rendering
- Smaller bundle size
- Good LaTeX coverage
- Better performance

### Citation Styles

#### IEEE (Default)
```
[1] A. Smith, "Title," Journal, vol. 1, no. 2, pp. 10-20, 2020.
```

#### APA
```
Smith, A. (2020). Title. Journal, 1(2), 10-20.
```

#### ACM
```
A. Smith. 2020. Title. Journal 1, 2 (2020), 10-20.
```

## HTML Output Structure

The converter generates semantic HTML5:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Paper Title</title>
    <!-- Math renderer CSS/JS -->
    <style>/* Responsive academic styling */</style>
</head>
<body>
    <article class="paper">
        <header class="paper-header">
            <h1 class="paper-title">Title</h1>
            <div class="paper-authors">Authors</div>
            <div class="paper-abstract">Abstract</div>
        </header>
        
        <section class="paper-section level-1">
            <h2 class="section-title">Introduction</h2>
            <div class="section-content">...</div>
        </section>
        
        <figure class="figure" id="fig:example">
            <img src="image.png" alt="Description" class="figure-img">
            <figcaption class="figure-caption">Caption</figcaption>
        </figure>
        
        <div class="equation" id="eq:example">
            <!-- MathJax/KaTeX content -->
        </div>
        
        <div class="bibliography">
            <h2>References</h2>
            <ol class="bibliography-list">
                <li class="bibliography-entry">Citation</li>
            </ol>
        </div>
    </article>
</body>
</html>
```

## CSS Classes

The generated HTML uses semantic CSS classes:

- `.paper` - Main article container
- `.paper-header` - Document header
- `.paper-title` - Document title
- `.paper-authors` - Author list
- `.paper-abstract` - Abstract section
- `.paper-section` - Document sections
- `.section-title` - Section headings
- `.figure` - Figure containers
- `.figure-img` - Images
- `.figure-caption` - Figure captions
- `.equation` - Equation containers
- `.citation` - Citation links
- `.bibliography` - References section

## Error Handling

The converter provides comprehensive error handling:

### Error Types
- `FileNotFound` - Missing LaTeX or bibliography files
- `ParseError` - LaTeX syntax errors
- `BibTexParseError` - Bibliography parsing issues
- `ImageNotFound` - Missing figure files
- `ConversionError` - General conversion failures

### Warnings
- `MissingBibliographyEntries` - Citations without references
- `LargeImageFile` - Oversized images
- `HighResolutionImage` - Images that need optimization
- `MissingGraphics` - Figure environments without images

### Processing Result
```python
result = converter.convert_file("paper.tex")

# Check status
if result.is_successful:
    print("Success!")
elif result.has_errors:
    print("Errors occurred:")
    for error in result.errors:
        print(f"- {error.message}")
elif result.has_warnings:
    print("Completed with warnings:")
    for warning in result.warnings:
        print(f"- {warning.message}")

# Access statistics
print(f"Processed {result.statistics['sections']} sections")
print(f"Found {result.statistics['figures']} figures")
print(f"Rendered {result.statistics['equations']} equations")
```

## Performance Considerations

### Large Documents
- Efficient regex-based parsing
- Streaming file processing
- Memory-conscious image handling
- Progress reporting for long operations

### Optimization Tips
1. **Optimize Images** - Use web-friendly formats and sizes
2. **Split Large Documents** - Break into chapters/sections
3. **Bibliography Management** - Keep .bib files organized
4. **Template Caching** - Reuse configured converters

## Examples

### Complete Academic Paper
```python
from paperflow.processors.latex.html_converter import HTMLConverter

converter = HTMLConverter()
result = converter.convert_file(
    latex_file="manuscript.tex",
    output_file="publication.html", 
    bibliography_files=["references.bib", "additional.bib"]
)

# Check result and save
if result.is_successful:
    print(f"Generated HTML: {result.html_document.html_content[:100]}...")
```

### Batch Processing
```python
from pathlib import Path

converter = HTMLConverter()
papers_dir = Path("papers/")

for tex_file in papers_dir.glob("*.tex"):
    html_file = tex_file.with_suffix(".html")
    bib_file = tex_file.with_suffix(".bib")
    
    result = converter.convert_file(
        tex_file, 
        html_file,
        [bib_file] if bib_file.exists() else None
    )
    
    if result.is_successful:
        print(f"Converted: {tex_file} -> {html_file}")
    else:
        print(f"Failed: {tex_file}")
```

### Custom Styling
```python
from paperflow.models.processor import ProcessorConfig

# Configure for journal submission
config = ProcessorConfig(
    math_renderer=MathRenderer.MATHJAX,
    citation_style=CitationStyle.IEEE,
    figure_width="80%",
    enable_equation_numbering=True
)

converter = HTMLConverter(config)
```

## Testing

Run the test suite:

```bash
# Unit tests
pytest tests/processors/test_latex_parser.py
pytest tests/processors/test_html_converter.py

# Integration tests
pytest tests/processors/test_integration.py

# All processor tests
pytest tests/processors/
```

## Contributing

When extending the converter:

1. **Follow the modular architecture** - Each processor handles specific content
2. **Add comprehensive tests** - Include unit and integration tests
3. **Handle errors gracefully** - Provide meaningful error messages
4. **Document new features** - Update this README and code comments
5. **Maintain backwards compatibility** - Preserve existing APIs

## Troubleshooting

### Common Issues

**Missing Dependencies**
```bash
pip install bibtexparser texsoup pillow
```

**BibTeX Parsing Errors**
- Check .bib file syntax
- Ensure proper encoding (UTF-8)
- Validate entry structure

**Image Not Found**
- Verify image paths relative to LaTeX file
- Check supported formats: PNG, JPG, PDF, SVG
- Ensure images exist in expected directories

**Math Rendering Issues**
- Check LaTeX math syntax
- Verify MathJax/KaTeX configuration
- Test with simpler equations first

**Large File Processing**
- Monitor memory usage
- Consider splitting large documents
- Optimize images before processing

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Converter will now output detailed processing information
converter = HTMLConverter()
```

## License

This LaTeX to HTML converter is part of the Paperflow project and follows the same licensing terms.