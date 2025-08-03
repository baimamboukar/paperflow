"""Figure processor for handling images and graphics in LaTeX documents."""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from paperflow.models.processor import (
    LaTeXDocument, Figure, ProcessingResult, ProcessingError, 
    ProcessingWarning, ProcessorConfig
)

logger = logging.getLogger(__name__)


class FigureProcessor:
    """Processor for handling figures and images."""
    
    def __init__(self, config: Optional[ProcessorConfig] = None):
        """Initialize the figure processor.
        
        Args:
            config: Processor configuration
        """
        self.config = config or ProcessorConfig()
        self._setup_patterns()
    
    def _setup_patterns(self) -> None:
        """Set up regex patterns for figure processing."""
        # Figure environment pattern
        self.figure_pattern = re.compile(
            r'\\begin\{figure\*?\}(?:\[([htbp!]*)\])?(.*?)\\end\{figure\*?\}', 
            re.DOTALL
        )
        
        # Graphics inclusion patterns
        self.includegraphics_pattern = re.compile(
            r'\\includegraphics(?:\[([^\]]*)\])?\{([^}]+)\}'
        )
        
        # Caption and label patterns
        self.caption_pattern = re.compile(
            r'\\caption\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', 
            re.DOTALL
        )
        self.label_pattern = re.compile(r'\\label\{([^}]+)\}')
        
        # Graphics options pattern
        self.graphics_options_pattern = re.compile(
            r'(?:width|height|scale|angle)\s*=\s*([^,\]]+)'
        )
        
        # Supported image extensions
        self.supported_extensions = {
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif',
            '.pdf', '.eps', '.svg', '.webp'
        }
    
    def process_figures(self, latex_document: LaTeXDocument, 
                       base_path: Optional[Path] = None) -> ProcessingResult:
        """Process figures in a LaTeX document.
        
        Args:
            latex_document: LaTeX document to process
            base_path: Base path for resolving relative image paths
            
        Returns:
            ProcessingResult with processed figures
        """
        result = ProcessingResult(status="success")
        
        try:
            # Determine base path
            if base_path is None and latex_document.source_file:
                base_path = latex_document.source_file.parent
            elif base_path is None:
                base_path = Path.cwd()
            
            # Clear existing figures to reprocess
            latex_document.figures.clear()
            
            # Process all content
            all_content = self._gather_document_content(latex_document)
            
            # Process figure environments
            figure_counter = self._process_figure_environments(
                all_content, latex_document, base_path, result
            )
            
            # Process standalone includegraphics commands
            self._process_standalone_graphics(
                all_content, latex_document, base_path, result, figure_counter
            )
            
            result.latex_document = latex_document
            result.statistics['figures_processed'] = len(latex_document.figures)
            
            logger.info(f"Processed {len(latex_document.figures)} figures")
            
        except Exception as e:
            logger.error(f"Error processing figures: {e}")
            error = ProcessingError(
                error_type="FigureProcessingError",
                message=f"Failed to process figures: {str(e)}",
                suggestion="Check image paths and LaTeX figure syntax"
            )
            result.add_error(error)
        
        return result
    
    def _gather_document_content(self, latex_document: LaTeXDocument) -> str:
        """Gather all document content for figure processing."""
        content_parts = []
        
        if latex_document.abstract:
            content_parts.append(latex_document.abstract)
        
        for section in latex_document.sections:
            content_parts.append(section.content)
        
        return "\n\n".join(content_parts)
    
    def _process_figure_environments(self, content: str, latex_document: LaTeXDocument,
                                   base_path: Path, result: ProcessingResult) -> int:
        """Process figure environments.
        
        Args:
            content: Document content
            latex_document: LaTeX document to update
            base_path: Base path for resolving images
            result: Processing result
            
        Returns:
            Next figure number
        """
        figure_counter = 1
        
        for match in self.figure_pattern.finditer(content):
            placement = match.group(1) or ""
            figure_content = match.group(2)
            
            # Extract includegraphics command
            graphics_match = self.includegraphics_pattern.search(figure_content)
            if not graphics_match:
                warning = ProcessingWarning(
                    warning_type="MissingGraphics",
                    message="Figure environment found without \\includegraphics command",
                    context=figure_content[:100]
                )
                result.add_warning(warning)
                continue
            
            # Parse graphics options and filename
            graphics_options = graphics_match.group(1) or ""
            image_filename = graphics_match.group(2)
            
            # Resolve image path
            image_path = self._resolve_image_path(image_filename, base_path, result)
            if not image_path:
                continue
            
            # Create figure object
            figure = Figure(
                file_path=image_path,
                placement=placement,
                number=figure_counter
            )
            
            # Parse graphics options
            self._parse_graphics_options(graphics_options, figure)
            
            # Extract caption
            caption_match = self.caption_pattern.search(figure_content)
            if caption_match:
                figure.caption = self._clean_latex_text(caption_match.group(1))
            
            # Extract label
            label_match = self.label_pattern.search(figure_content)
            if label_match:
                figure.label = label_match.group(1)
            
            # Generate alt text from caption if not provided
            if not figure.alt_text and figure.caption:
                figure.alt_text = self._generate_alt_text(figure.caption)
            
            # Validate and process image
            self._validate_and_process_image(figure, result)
            
            # Add to document
            latex_document.add_figure(figure)
            figure_counter += 1
        
        return figure_counter
    
    def _process_standalone_graphics(self, content: str, latex_document: LaTeXDocument,
                                   base_path: Path, result: ProcessingResult,
                                   start_counter: int) -> None:
        """Process standalone includegraphics commands (outside figure environments).
        
        Args:
            content: Document content
            latex_document: LaTeX document to update
            base_path: Base path for resolving images
            result: Processing result
            start_counter: Starting figure number
        """
        figure_counter = start_counter
        
        # Remove figure environments from content to avoid double processing
        content_without_figures = self.figure_pattern.sub('', content)
        
        for match in self.includegraphics_pattern.finditer(content_without_figures):
            graphics_options = match.group(1) or ""
            image_filename = match.group(2)
            
            # Resolve image path
            image_path = self._resolve_image_path(image_filename, base_path, result)
            if not image_path:
                continue
            
            # Create figure object
            figure = Figure(
                file_path=image_path,
                number=figure_counter
            )
            
            # Parse graphics options
            self._parse_graphics_options(graphics_options, figure)
            
            # Generate label for standalone graphics
            figure.label = f"standalone_fig_{figure_counter}"
            
            # Validate and process image
            self._validate_and_process_image(figure, result)
            
            # Add to document
            latex_document.add_figure(figure)
            figure_counter += 1
    
    def _resolve_image_path(self, image_filename: str, base_path: Path,
                          result: ProcessingResult) -> Optional[Path]:
        """Resolve image path from LaTeX filename.
        
        Args:
            image_filename: Image filename from LaTeX
            base_path: Base path for resolution
            result: Processing result for warnings
            
        Returns:
            Resolved image path or None if not found
        """
        # Clean filename
        image_filename = image_filename.strip()
        
        # Try exact path first
        image_path = base_path / image_filename
        if image_path.exists():
            return image_path
        
        # Try with different extensions if no extension provided
        if not Path(image_filename).suffix:
            for ext in self.supported_extensions:
                test_path = base_path / (image_filename + ext)
                if test_path.exists():
                    return test_path
        
        # Try common subdirectories
        for subdir in ['figures', 'images', 'graphics', 'fig']:
            subdir_path = base_path / subdir / image_filename
            if subdir_path.exists():
                return subdir_path
            
            # Try with extensions in subdirectories
            if not Path(image_filename).suffix:
                for ext in self.supported_extensions:
                    test_path = base_path / subdir / (image_filename + ext)
                    if test_path.exists():
                        return test_path
        
        # Image not found
        warning = ProcessingWarning(
            warning_type="ImageNotFound",
            message=f"Image file not found: {image_filename}",
            context=f"Searched in {base_path} and subdirectories"
        )
        result.add_warning(warning)
        
        return None
    
    def _parse_graphics_options(self, options: str, figure: Figure) -> None:
        """Parse includegraphics options.
        
        Args:
            options: Options string from includegraphics
            figure: Figure object to update
        """
        if not options:
            return
        
        # Parse key=value pairs
        for match in self.graphics_options_pattern.finditer(options):
            value = match.group(1).strip()
            
            # Extract the key from the full match
            full_match = match.group(0)
            key = full_match.split('=')[0].strip()
            
            if key == 'width':
                figure.width = value
            elif key == 'height':
                figure.height = value
            elif key in ['scale', 'angle']:
                # Store in metadata for potential processing
                if 'graphics_options' not in figure.__dict__:
                    figure.__dict__['graphics_options'] = {}
                figure.__dict__['graphics_options'][key] = value
    
    def _validate_and_process_image(self, figure: Figure, result: ProcessingResult) -> None:
        """Validate image file and extract metadata.
        
        Args:
            figure: Figure to validate
            result: Processing result for warnings/errors
        """
        try:
            if not figure.file_path.exists():
                warning = ProcessingWarning(
                    warning_type="ImageFileNotFound",
                    message=f"Image file does not exist: {figure.file_path}",
                    context=str(figure.file_path)
                )
                result.add_warning(warning)
                return
            
            # Check file size
            file_size = figure.file_path.stat().st_size
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                warning = ProcessingWarning(
                    warning_type="LargeImageFile",
                    message=f"Large image file ({file_size // 1024 // 1024}MB): {figure.file_path.name}",
                    context="Consider optimizing image size for web"
                )
                result.add_warning(warning)
            
            # Extract image metadata if PIL is available
            if PIL_AVAILABLE:
                self._extract_image_metadata(figure, result)
            
        except Exception as e:
            warning = ProcessingWarning(
                warning_type="ImageValidationError",
                message=f"Error validating image {figure.file_path}: {str(e)}",
                context=str(figure.file_path)
            )
            result.add_warning(warning)
    
    def _extract_image_metadata(self, figure: Figure, result: ProcessingResult) -> None:
        """Extract image metadata using PIL.
        
        Args:
            figure: Figure to process
            result: Processing result for warnings
        """
        try:
            with Image.open(figure.file_path) as img:
                # Store image dimensions and format
                if 'metadata' not in figure.__dict__:
                    figure.__dict__['metadata'] = {}
                
                figure.__dict__['metadata'].update({
                    'width_px': img.width,
                    'height_px': img.height,
                    'format': img.format,
                    'mode': img.mode
                })
                
                # Check for potential issues
                if img.width > 2048 or img.height > 2048:
                    warning = ProcessingWarning(
                        warning_type="HighResolutionImage",
                        message=f"High resolution image ({img.width}x{img.height}): {figure.file_path.name}",
                        context="Consider resizing for web use"
                    )
                    result.add_warning(warning)
                
        except Exception as e:
            logger.debug(f"Could not extract metadata from {figure.file_path}: {e}")
    
    def _clean_latex_text(self, text: str) -> str:
        """Clean LaTeX text for captions.
        
        Args:
            text: Raw LaTeX text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Convert common LaTeX commands
        text = re.sub(r'\\textbf\{([^}]+)\}', r'<strong>\1</strong>', text)
        text = re.sub(r'\\textit\{([^}]+)\}', r'<em>\1</em>', text)
        text = re.sub(r'\\emph\{([^}]+)\}', r'<em>\1</em>', text)
        
        # Remove other LaTeX commands (simple approach)
        text = re.sub(r'\\[a-zA-Z]+\*?\s*', '', text)
        text = re.sub(r'[{}]', '', text)
        
        # Clean up spacing
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _generate_alt_text(self, caption: str) -> str:
        """Generate alt text from caption.
        
        Args:
            caption: Figure caption
            
        Returns:
            Generated alt text
        """
        # Remove HTML tags from cleaned caption
        alt_text = re.sub(r'<[^>]+>', '', caption)
        
        # Limit length
        if len(alt_text) > 120:
            alt_text = alt_text[:117] + "..."
        
        return alt_text
    
    def convert_to_html(self, figure: Figure, base_url: Optional[str] = None) -> str:
        """Convert a figure to HTML.
        
        Args:
            figure: Figure to convert
            base_url: Base URL for image paths
            
        Returns:
            HTML representation of the figure
        """
        # Determine image URL
        if base_url:
            img_src = f"{base_url.rstrip('/')}/{figure.file_path.name}"
        else:
            img_src = str(figure.file_path)
        
        # Build HTML
        html_parts = []
        
        # Figure element
        figure_attrs = ['class="figure"']
        if figure.label:
            figure_attrs.append(f'id="{figure.label}"')
        
        html_parts.append(f'<figure {" ".join(figure_attrs)}>')
        
        # Image element
        img_attrs = [f'src="{img_src}"']
        
        if figure.alt_text:
            img_attrs.append(f'alt="{figure.alt_text}"')
        elif figure.caption:
            alt_text = self._generate_alt_text(figure.caption)
            img_attrs.append(f'alt="{alt_text}"')
        
        if figure.width:
            # Convert LaTeX width to CSS
            css_width = self._convert_latex_width(figure.width)
            if css_width:
                img_attrs.append(f'style="width: {css_width}"')
        
        img_attrs.append('class="figure-img"')
        
        html_parts.append(f'  <img {" ".join(img_attrs)} />')
        
        # Caption
        if figure.caption:
            caption_html = f'  <figcaption class="figure-caption">'
            if figure.number:
                caption_html += f'Figure {figure.number}: '
            caption_html += f'{figure.caption}</figcaption>'
            html_parts.append(caption_html)
        
        html_parts.append('</figure>')
        
        return '\n'.join(html_parts)
    
    def _convert_latex_width(self, latex_width: str) -> Optional[str]:
        """Convert LaTeX width specification to CSS.
        
        Args:
            latex_width: LaTeX width (e.g., "0.5\\textwidth", "10cm")
            
        Returns:
            CSS width or None if cannot convert
        """
        latex_width = latex_width.strip()
        
        # Handle textwidth fractions
        if 'textwidth' in latex_width:
            # Extract fraction (e.g., "0.5\\textwidth" -> "50%")
            match = re.search(r'([\d.]+)\\textwidth', latex_width)
            if match:
                fraction = float(match.group(1))
                percentage = int(fraction * 100)
                return f"{percentage}%"
        
        # Handle absolute units
        unit_conversions = {
            'cm': 'cm',
            'mm': 'mm', 
            'in': 'in',
            'pt': 'pt',
            'px': 'px'
        }
        
        for latex_unit, css_unit in unit_conversions.items():
            if latex_width.endswith(latex_unit):
                value = latex_width.replace(latex_unit, '')
                try:
                    float(value)  # Validate it's a number
                    return f"{value}{css_unit}"
                except ValueError:
                    continue
        
        return None
    
    def optimize_image_for_web(self, figure: Figure, output_dir: Path,
                             max_width: int = 1200, quality: int = 85) -> Optional[Path]:
        """Optimize image for web use.
        
        Args:
            figure: Figure to optimize
            output_dir: Output directory for optimized image
            max_width: Maximum width in pixels
            quality: JPEG quality (if converting to JPEG)
            
        Returns:
            Path to optimized image or None if failed
        """
        if not PIL_AVAILABLE:
            logger.warning("PIL not available, cannot optimize images")
            return None
        
        try:
            with Image.open(figure.file_path) as img:
                # Calculate new dimensions
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                
                # Convert to RGB if necessary for JPEG
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Save optimized image
                output_path = output_dir / f"{figure.file_path.stem}_optimized.jpg"
                img.save(output_path, 'JPEG', quality=quality, optimize=True)
                
                return output_path
                
        except Exception as e:
            logger.error(f"Failed to optimize image {figure.file_path}: {e}")
            return None