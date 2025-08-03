"""
Build synchronization service for Paperflow.

This service handles the build process for converting LaTeX projects to HTML,
including theme application, asset management, and build optimization.
"""

import asyncio
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from paperflow.config.settings import Settings
from paperflow.models.project import Project
from paperflow.models.processor import ProcessorConfig, MathRenderer, CitationStyle
from paperflow.models.sync import (
    SyncResult, SyncStatus, SyncOperationType, SyncConfiguration,
    SyncMetrics, SyncStage
)
from paperflow.processors.latex.html_converter import HTMLConverter
from paperflow.services.base import BaseService
from paperflow.utils.logging import setup_logging
from paperflow.utils.file_utils import FileUtils

logger = setup_logging(__name__)


class BuildConfiguration:
    """Configuration for build operations."""
    
    def __init__(
        self,
        output_directory: str = "docs",
        theme: str = "midnight-scholar",
        math_renderer: MathRenderer = MathRenderer.MATHJAX,
        citation_style: CitationStyle = CitationStyle.IEEE,
        enable_syntax_highlighting: bool = True,
        enable_figure_numbering: bool = True,
        enable_equation_numbering: bool = True,
        enable_cross_references: bool = True,
        generate_pdf: bool = False,
        optimize_images: bool = True,
        minify_assets: bool = True,
        custom_css_path: Optional[str] = None,
        custom_js_path: Optional[str] = None,
        include_source_files: bool = False,
        build_timeout_seconds: int = 300
    ):
        self.output_directory = output_directory
        self.theme = theme
        self.math_renderer = math_renderer
        self.citation_style = citation_style
        self.enable_syntax_highlighting = enable_syntax_highlighting
        self.enable_figure_numbering = enable_figure_numbering
        self.enable_equation_numbering = enable_equation_numbering
        self.enable_cross_references = enable_cross_references
        self.generate_pdf = generate_pdf
        self.optimize_images = optimize_images
        self.minify_assets = minify_assets
        self.custom_css_path = custom_css_path
        self.custom_js_path = custom_js_path
        self.include_source_files = include_source_files
        self.build_timeout_seconds = build_timeout_seconds


class BuildAssetManager:
    """Manages build assets and themes."""
    
    def __init__(self, framework_root: Path):
        self.framework_root = framework_root
        self.templates_dir = framework_root / "project-templates"
        self.file_utils = FileUtils()
    
    def get_available_themes(self) -> List[str]:
        """Get list of available themes."""
        themes = []
        themes_dir = self.templates_dir / "themes"
        
        if themes_dir.exists():
            for theme_file in themes_dir.glob("*.css"):
                theme_name = theme_file.stem
                themes.append(theme_name)
        
        return themes
    
    def copy_theme_assets(self, theme: str, output_dir: Path) -> bool:
        """Copy theme assets to output directory."""
        try:
            assets_dir = output_dir / "assets"
            assets_dir.mkdir(exist_ok=True)
            
            # Copy main theme CSS
            theme_file = self.templates_dir / "themes" / f"{theme}.css"
            if theme_file.exists():
                shutil.copy2(theme_file, assets_dir / "theme.css")
            
            # Copy base assets
            base_assets = self.templates_dir / "assets"
            if base_assets.exists():
                for asset_file in base_assets.glob("*"):
                    if asset_file.is_file():
                        shutil.copy2(asset_file, assets_dir / asset_file.name)
            
            logger.info(f"Copied theme assets for '{theme}' to {assets_dir}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to copy theme assets: {e}")
            return False
    
    def optimize_images(self, directory: Path) -> Dict[str, Any]:
        """Optimize images in directory."""
        optimization_stats = {
            "processed": 0,
            "size_before": 0,
            "size_after": 0,
            "savings": 0
        }
        
        try:
            for image_file in directory.rglob("*.png"):
                if image_file.is_file():
                    original_size = image_file.stat().st_size
                    optimization_stats["size_before"] += original_size
                    
                    # Simple optimization using PIL if available
                    try:
                        from PIL import Image
                        
                        with Image.open(image_file) as img:
                            # Convert to RGB if necessary
                            if img.mode in ("RGBA", "P"):
                                img = img.convert("RGB")
                            
                            # Save with optimization
                            img.save(image_file, "PNG", optimize=True)
                            
                            new_size = image_file.stat().st_size
                            optimization_stats["size_after"] += new_size
                            optimization_stats["processed"] += 1
                    
                    except ImportError:
                        # PIL not available, skip optimization
                        optimization_stats["size_after"] += original_size
                    except Exception as e:
                        logger.warning(f"Failed to optimize {image_file}: {e}")
                        optimization_stats["size_after"] += original_size
            
            optimization_stats["savings"] = (
                optimization_stats["size_before"] - optimization_stats["size_after"]
            )
            
        except Exception as e:
            logger.error(f"Error during image optimization: {e}")
        
        return optimization_stats
    
    def minify_css(self, css_file: Path) -> bool:
        """Minify CSS file."""
        try:
            content = css_file.read_text(encoding="utf-8")
            
            # Simple CSS minification
            # Remove comments
            import re
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
            
            # Remove extra whitespace
            content = re.sub(r'\s+', ' ', content)
            content = re.sub(r';\s*}', '}', content)
            content = re.sub(r'{\s*', '{', content)
            content = re.sub(r'}\s*', '}', content)
            content = content.strip()
            
            css_file.write_text(content, encoding="utf-8")
            return True
        
        except Exception as e:
            logger.warning(f"Failed to minify CSS {css_file}: {e}")
            return False
    
    def minify_js(self, js_file: Path) -> bool:
        """Minify JavaScript file."""
        try:
            content = js_file.read_text(encoding="utf-8")
            
            # Simple JS minification
            import re
            
            # Remove single-line comments
            content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
            
            # Remove multi-line comments
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
            
            # Remove extra whitespace
            content = re.sub(r'\s+', ' ', content)
            content = content.strip()
            
            js_file.write_text(content, encoding="utf-8")
            return True
        
        except Exception as e:
            logger.warning(f"Failed to minify JS {js_file}: {e}")
            return False


class BuildSync(BaseService):
    """
    Build synchronization service.
    
    Handles the build process for converting LaTeX projects to HTML,
    including theme application and asset management.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize build sync service."""
        super().__init__(settings)
        
        # Configuration
        self.default_config = BuildConfiguration()
        
        # Asset management
        framework_root = Path(__file__).parent.parent.parent.parent
        self.asset_manager = BuildAssetManager(framework_root)
        self.file_utils = FileUtils()
        
        # Build state
        self.active_builds: Dict[str, Dict[str, Any]] = {}
    
    def _perform_initialization(self) -> None:
        """Perform service-specific initialization."""
        logger.info("Initializing BuildSync service")
        
        # Verify build dependencies
        self._check_build_dependencies()
        
        logger.info("BuildSync service initialized")
    
    def _perform_cleanup(self) -> None:
        """Perform service cleanup."""
        logger.info("Cleaning up BuildSync service")
        
        self.active_builds.clear()
        
        logger.info("BuildSync service cleanup completed")
    
    def _check_build_dependencies(self) -> None:
        """Check if build dependencies are available."""
        try:
            # Check if LaTeX converter is available
            from paperflow.processors.latex.html_converter import HTMLConverter
            
            # Check if PIL is available for image optimization
            try:
                from PIL import Image
                logger.info("PIL available for image optimization")
            except ImportError:
                logger.warning("PIL not available, image optimization will be skipped")
            
        except Exception as e:
            logger.warning(f"Some build dependencies may not be available: {e}")
    
    async def build_project(
        self,
        project: Project,
        source_directory: Path,
        config: Optional[BuildConfiguration] = None
    ) -> SyncResult:
        """
        Build project from LaTeX to HTML.
        
        Args:
            project: Project to build
            source_directory: Directory containing LaTeX source
            config: Build configuration
            
        Returns:
            SyncResult with build details
        """
        operation_id = f"build_{project.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        build_config = config or self.default_config
        
        sync_result = SyncResult(
            operation_id=operation_id,
            operation_type=SyncOperationType.BUILD_ONLY,
            trigger=datetime.now(),
            configuration=build_config
        )
        
        sync_result.mark_started()
        sync_result.progress.stage = SyncStage.BUILDING
        
        self.active_builds[operation_id] = {
            "project": project,
            "config": build_config,
            "start_time": datetime.now()
        }
        
        try:
            logger.info(f"Starting build for project '{project.name}'")
            
            # Setup output directory
            output_dir = source_directory / build_config.output_directory
            output_dir.mkdir(exist_ok=True)
            
            sync_result.build_output_path = output_dir
            
            # Find main LaTeX file
            main_tex_file = await self._find_main_tex_file(
                source_directory, project, sync_result
            )
            
            if not main_tex_file:
                raise RuntimeError("No main LaTeX file found")
            
            # Setup build environment
            await self._setup_build_environment(
                source_directory, output_dir, build_config, sync_result
            )
            
            # Convert LaTeX to HTML
            await self._convert_latex_to_html(
                main_tex_file, output_dir, project, build_config, sync_result
            )
            
            # Copy and process assets
            await self._process_build_assets(
                source_directory, output_dir, build_config, sync_result
            )
            
            # Generate additional files
            await self._generate_additional_files(
                project, output_dir, build_config, sync_result
            )
            
            # Optimize build output
            if build_config.optimize_images or build_config.minify_assets:
                await self._optimize_build_output(
                    output_dir, build_config, sync_result
                )
            
            # Update project metadata
            project.last_build = datetime.now()
            
            sync_result.mark_completed(success=True)
            logger.info(f"Successfully completed build for project '{project.name}'")
        
        except Exception as e:
            sync_result.mark_completed(success=False, error=str(e))
            logger.error(f"Build failed for project '{project.name}': {e}")
        
        finally:
            self.active_builds.pop(operation_id, None)
        
        return sync_result
    
    async def _find_main_tex_file(
        self,
        source_directory: Path,
        project: Project,
        sync_result: SyncResult
    ) -> Optional[Path]:
        """Find the main LaTeX file."""
        # Try project's main_tex_file setting first
        if hasattr(project, 'main_tex_file') and project.main_tex_file:
            main_tex_path = source_directory / project.main_tex_file
            if main_tex_path.exists():
                return main_tex_path
        
        # Common main file names
        common_names = ["main.tex", "paper.tex", "document.tex", "thesis.tex"]
        
        for name in common_names:
            tex_file = source_directory / name
            if tex_file.exists():
                return tex_file
        
        # Look for any .tex file in the root
        tex_files = list(source_directory.glob("*.tex"))
        if tex_files:
            # Use the first one found
            return tex_files[0]
        
        # Look recursively
        tex_files = list(source_directory.rglob("*.tex"))
        if tex_files:
            return tex_files[0]
        
        sync_result.add_warning("No LaTeX file found")
        return None
    
    async def _setup_build_environment(
        self,
        source_directory: Path,
        output_dir: Path,
        config: BuildConfiguration,
        sync_result: SyncResult
    ) -> None:
        """Setup build environment."""
        try:
            # Copy theme assets
            theme_copied = self.asset_manager.copy_theme_assets(config.theme, output_dir)
            if not theme_copied:
                sync_result.add_warning(f"Failed to copy theme assets for '{config.theme}'")
            
            # Copy custom CSS if specified
            if config.custom_css_path:
                custom_css = source_directory / config.custom_css_path
                if custom_css.exists():
                    assets_dir = output_dir / "assets"
                    shutil.copy2(custom_css, assets_dir / "custom.css")
            
            # Copy custom JS if specified
            if config.custom_js_path:
                custom_js = source_directory / config.custom_js_path
                if custom_js.exists():
                    assets_dir = output_dir / "assets"
                    shutil.copy2(custom_js, assets_dir / "custom.js")
            
            logger.info("Build environment setup completed")
        
        except Exception as e:
            logger.error(f"Error setting up build environment: {e}")
            raise
    
    async def _convert_latex_to_html(
        self,
        main_tex_file: Path,
        output_dir: Path,
        project: Project,
        config: BuildConfiguration,
        sync_result: SyncResult
    ) -> None:
        """Convert LaTeX to HTML."""
        try:
            # Create processor configuration
            processor_config = ProcessorConfig(
                math_renderer=config.math_renderer,
                citation_style=config.citation_style,
                enable_equation_numbering=config.enable_equation_numbering,
                enable_figure_numbering=config.enable_figure_numbering,
                enable_cross_references=config.enable_cross_references,
                enable_syntax_highlighting=config.enable_syntax_highlighting
            )
            
            # Create HTML converter
            converter = HTMLConverter(processor_config)
            
            # Find bibliography files
            bibliography_files = []
            bib_files = main_tex_file.parent.glob("*.bib")
            for bib_file in bib_files:
                bibliography_files.append(bib_file)
            
            # Convert to HTML
            html_output = output_dir / "index.html"
            
            logger.info(f"Converting {main_tex_file} to {html_output}")
            
            # Run conversion with timeout
            conversion_task = asyncio.create_task(
                self._run_latex_conversion(
                    converter, main_tex_file, html_output, bibliography_files
                )
            )
            
            try:
                result = await asyncio.wait_for(
                    conversion_task, 
                    timeout=config.build_timeout_seconds
                )
                
                if result.is_successful:
                    sync_result.build_artifacts.append(str(html_output))
                    
                    # Add conversion statistics to metrics
                    if result.statistics:
                        stats = result.statistics
                        sync_result.metrics.files_modified += 1  # HTML file
                        
                        # Log statistics
                        logger.info(f"Conversion statistics: {stats}")
                    
                    # Add warnings if any
                    for warning in result.warnings:
                        sync_result.add_warning(f"LaTeX conversion: {warning.message}")
                
                else:
                    error_msg = "LaTeX conversion failed"
                    if result.errors:
                        error_msg += f": {'; '.join([e.message for e in result.errors])}"
                    raise RuntimeError(error_msg)
            
            except asyncio.TimeoutError:
                conversion_task.cancel()
                raise RuntimeError(f"LaTeX conversion timed out after {config.build_timeout_seconds} seconds")
        
        except Exception as e:
            logger.error(f"Error converting LaTeX to HTML: {e}")
            raise
    
    async def _run_latex_conversion(
        self,
        converter: HTMLConverter,
        input_file: Path,
        output_file: Path,
        bibliography_files: List[Path]
    ):
        """Run LaTeX conversion in executor to avoid blocking."""
        loop = asyncio.get_event_loop()
        
        def run_conversion():
            return converter.convert_file(
                input_file, output_file, bibliography_files
            )
        
        return await loop.run_in_executor(None, run_conversion)
    
    async def _process_build_assets(
        self,
        source_directory: Path,
        output_dir: Path,
        config: BuildConfiguration,
        sync_result: SyncResult
    ) -> None:
        """Process and copy build assets."""
        try:
            assets_dir = output_dir / "assets"
            
            # Copy figures and images
            figures_copied = 0
            for pattern in ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg", "*.pdf"]:
                for image_file in source_directory.rglob(pattern):
                    if image_file.is_file():
                        # Copy to assets/figures/
                        figures_dir = assets_dir / "figures"
                        figures_dir.mkdir(exist_ok=True)
                        
                        dest_path = figures_dir / image_file.name
                        shutil.copy2(image_file, dest_path)
                        figures_copied += 1
            
            logger.info(f"Copied {figures_copied} image files")
            
            # Include source files if requested
            if config.include_source_files:
                source_dir = output_dir / "source"
                source_dir.mkdir(exist_ok=True)
                
                # Copy LaTeX files
                for tex_file in source_directory.rglob("*.tex"):
                    if tex_file.is_file():
                        shutil.copy2(tex_file, source_dir / tex_file.name)
                
                # Copy bibliography files
                for bib_file in source_directory.rglob("*.bib"):
                    if bib_file.is_file():
                        shutil.copy2(bib_file, source_dir / bib_file.name)
                
                sync_result.build_artifacts.append(str(source_dir))
        
        except Exception as e:
            logger.error(f"Error processing build assets: {e}")
            raise
    
    async def _generate_additional_files(
        self,
        project: Project,
        output_dir: Path,
        config: BuildConfiguration,
        sync_result: SyncResult
    ) -> None:
        """Generate additional files for the website."""
        try:
            # Generate metadata JSON
            metadata = {
                "title": project.title,
                "authors": [{"name": author.name, "affiliation": author.affiliation} 
                           for author in project.authors] if project.authors else [],
                "abstract": project.abstract,
                "keywords": project.keywords,
                "built_at": datetime.now().isoformat(),
                "theme": config.theme,
                "paperflow_version": "1.0.0"  # Would get from package
            }
            
            metadata_file = output_dir / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            sync_result.build_artifacts.append(str(metadata_file))
            
            # Generate sitemap.xml if needed
            sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.github.io/{project.name}/</loc>
        <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>1.0</priority>
    </url>
</urlset>"""
            
            sitemap_file = output_dir / "sitemap.xml"
            sitemap_file.write_text(sitemap_content, encoding='utf-8')
            
            sync_result.build_artifacts.append(str(sitemap_file))
            
            logger.info("Generated additional website files")
        
        except Exception as e:
            logger.warning(f"Error generating additional files: {e}")
            sync_result.add_warning(f"Failed to generate some additional files: {e}")
    
    async def _optimize_build_output(
        self,
        output_dir: Path,
        config: BuildConfiguration,
        sync_result: SyncResult
    ) -> None:
        """Optimize build output."""
        try:
            optimization_stats = {"images": {}, "css": 0, "js": 0}
            
            # Optimize images
            if config.optimize_images:
                optimization_stats["images"] = self.asset_manager.optimize_images(output_dir)
                logger.info(f"Image optimization: {optimization_stats['images']}")
            
            # Minify CSS files
            if config.minify_assets:
                css_files = list(output_dir.rglob("*.css"))
                for css_file in css_files:
                    if self.asset_manager.minify_css(css_file):
                        optimization_stats["css"] += 1
                
                # Minify JS files
                js_files = list(output_dir.rglob("*.js"))
                for js_file in js_files:
                    if self.asset_manager.minify_js(js_file):
                        optimization_stats["js"] += 1
                
                logger.info(f"Minified {optimization_stats['css']} CSS and {optimization_stats['js']} JS files")
            
            # Update metrics
            if optimization_stats["images"]:
                bytes_saved = optimization_stats["images"].get("savings", 0)
                sync_result.metrics.bytes_transferred = bytes_saved
        
        except Exception as e:
            logger.warning(f"Error during build optimization: {e}")
            sync_result.add_warning(f"Build optimization failed: {e}")
    
    def get_available_themes(self) -> List[str]:
        """Get list of available themes."""
        return self.asset_manager.get_available_themes()
    
    def get_build_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get status of active build operation."""
        if operation_id in self.active_builds:
            build_info = self.active_builds[operation_id].copy()
            build_info["elapsed_time"] = (
                datetime.now() - build_info["start_time"]
            ).total_seconds()
            return build_info
        return None
    
    def cancel_build(self, operation_id: str) -> bool:
        """Cancel active build operation."""
        if operation_id in self.active_builds:
            self.active_builds.pop(operation_id)
            logger.info(f"Cancelled build operation: {operation_id}")
            return True
        return False