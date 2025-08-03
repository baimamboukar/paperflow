"""
Project management service for Paperflow.

This service handles all project-related operations including creation,
loading, saving, and validation of Paperflow projects.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from paperflow.config.settings import Settings
from paperflow.models.author import Author
from paperflow.models.project import Project, ProjectStatus, ProjectType
from paperflow.services.base import BaseService, ProjectServiceInterface
from paperflow.utils.file_utils import FileUtils
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


class ProjectService(BaseService, ProjectServiceInterface):
    """
    Service for managing Paperflow projects.

    Handles project lifecycle operations including creation, loading,
    saving, and validation with proper error handling and logging.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize project service."""
        super().__init__(settings)
        self._file_utils = FileUtils()

    def _perform_initialization(self) -> None:
        """Perform service-specific initialization."""
        logger.info("Initializing ProjectService")

        # Validate settings if available
        if self.settings:
            self._validate_service_settings()

    def _validate_service_settings(self) -> None:
        """Validate service-specific settings."""
        if not self.settings.project_path.exists():
            logger.warning(f"Project path does not exist: {self.settings.project_path}")

    async def create_project(
        self, project_data: Dict[str, Any], project_path: Optional[Path] = None
    ) -> Project:
        """
        Create a new Paperflow project.

        Args:
            project_data: Dictionary containing project information.
            project_path: Optional custom project path.

        Returns:
            Created Project instance.

        Raises:
            ValueError: If project data is invalid.
            FileExistsError: If project already exists.
        """
        logger.info(f"Creating new project: {project_data.get('name', 'unnamed')}")

        try:
            # Determine project path
            if project_path is None:
                project_name = project_data.get("name", "paperflow-project")
                project_path = Path.cwd() / project_name

            # Check if project already exists
            if project_path.exists():
                config_file = project_path / "config.yaml"
                if config_file.exists():
                    raise FileExistsError(f"Project already exists at {project_path}")

            # Create project directory
            project_path.mkdir(parents=True, exist_ok=True)

            # Parse authors
            authors = []
            if "authors" in project_data:
                authors = self._parse_authors(project_data["authors"])

            # Create project instance
            project = Project(
                name=project_data.get("name", "paperflow-project"),
                title=project_data.get("title", "Untitled Paper"),
                abstract=project_data.get("abstract", ""),
                keywords=project_data.get("keywords", []),
                authors=authors,
                project_path=project_path,
                project_type=ProjectType(project_data.get("type", "research_paper")),
                status=ProjectStatus(project_data.get("status", "draft")),
                language=project_data.get("language", "en"),
                arxiv_id=project_data.get("arxiv_id"),
                doi=project_data.get("doi"),
                journal=project_data.get("journal"),
                conference=project_data.get("conference"),
            )

            # Create project structure
            await self._create_project_structure(project)

            # Save project configuration
            await self.save_project(project)

            logger.info(f"Successfully created project at {project_path}")
            return project

        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            # Clean up on failure
            if project_path and project_path.exists():
                self._file_utils.remove_directory(project_path)
            raise

    async def load_project(self, project_path: Path) -> Project:
        """
        Load an existing Paperflow project.

        Args:
            project_path: Path to project directory.

        Returns:
            Loaded Project instance.

        Raises:
            FileNotFoundError: If project or config file not found.
            ValueError: If project configuration is invalid.
        """
        logger.info(f"Loading project from {project_path}")

        if not project_path.exists():
            raise FileNotFoundError(f"Project directory not found: {project_path}")

        # Look for configuration file
        config_file = self._find_config_file(project_path)
        if not config_file:
            raise FileNotFoundError(f"No configuration file found in {project_path}")

        try:
            # Load configuration
            config_data = self._load_config_file(config_file)

            # Parse authors
            authors = []
            if "authors" in config_data:
                authors = self._parse_authors(config_data["authors"])

            # Create project instance
            project = Project(
                name=config_data.get("name", project_path.name),
                title=config_data.get("title", "Untitled Paper"),
                abstract=config_data.get("abstract", ""),
                keywords=config_data.get("keywords", []),
                authors=authors,
                project_path=project_path,
                project_type=ProjectType(config_data.get("type", "research_paper")),
                status=ProjectStatus(config_data.get("status", "draft")),
                language=config_data.get("language", "en"),
                arxiv_id=config_data.get("arxiv_id"),
                doi=config_data.get("doi"),
                journal=config_data.get("journal"),
                conference=config_data.get("conference"),
                main_tex_file=config_data.get("main_tex_file", "main.tex"),
                bibliography_file=config_data.get(
                    "bibliography_file", "bibliography.bib"
                ),
                corresponding_author=config_data.get("corresponding_author"),
            )

            # Load timestamps if available
            if "created_at" in config_data:
                project.created_at = datetime.fromisoformat(config_data["created_at"])
            if "updated_at" in config_data:
                project.updated_at = datetime.fromisoformat(config_data["updated_at"])
            if "last_build" in config_data and config_data["last_build"]:
                project.last_build = datetime.fromisoformat(config_data["last_build"])
            if "last_sync" in config_data and config_data["last_sync"]:
                project.last_sync = datetime.fromisoformat(config_data["last_sync"])

            logger.info(f"Successfully loaded project: {project.name}")
            return project

        except Exception as e:
            logger.error(f"Failed to load project: {e}")
            raise ValueError(f"Invalid project configuration: {e}")

    async def save_project(self, project: Project) -> None:
        """
        Save project configuration to disk.

        Args:
            project: Project instance to save.
        """
        logger.info(f"Saving project: {project.name}")

        try:
            # Update timestamp
            project.touch()

            # Prepare configuration data
            config_data = {
                "name": project.name,
                "title": project.title,
                "abstract": project.abstract,
                "keywords": project.keywords,
                "type": project.project_type.value,
                "status": project.status.value,
                "language": project.language,
                "main_tex_file": project.main_tex_file,
                "bibliography_file": project.bibliography_file,
                "corresponding_author": project.corresponding_author,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
            }

            # Add optional fields
            if project.arxiv_id:
                config_data["arxiv_id"] = project.arxiv_id
            if project.doi:
                config_data["doi"] = project.doi
            if project.journal:
                config_data["journal"] = project.journal
            if project.conference:
                config_data["conference"] = project.conference
            if project.last_build:
                config_data["last_build"] = project.last_build.isoformat()
            if project.last_sync:
                config_data["last_sync"] = project.last_sync.isoformat()

            # Add authors
            if project.authors:
                config_data["authors"] = [author.dict() for author in project.authors]

            # Save to YAML file
            config_file = project.project_path / "config.yaml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(
                    config_data,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    indent=2,
                    allow_unicode=True,
                )

            logger.info(f"Successfully saved project configuration to {config_file}")

        except Exception as e:
            logger.error(f"Failed to save project: {e}")
            raise

    async def validate_project(self, project: Project) -> Dict[str, Any]:
        """
        Validate project structure and files.

        Args:
            project: Project to validate.

        Returns:
            Dictionary containing validation results.
        """
        logger.info(f"Validating project: {project.name}")

        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "file_checks": {},
            "structure_checks": {},
        }

        try:
            # Check project directory
            if not project.project_path.exists():
                results["errors"].append(
                    f"Project directory does not exist: {project.project_path}"
                )
                results["valid"] = False

            # Check required files
            file_checks = project.validate_project_files()
            results["file_checks"] = file_checks

            for file_type, exists in file_checks.items():
                if not exists:
                    if file_type == "main_tex":
                        results["errors"].append(
                            f"Main LaTeX file not found: {project.main_tex_file}"
                        )
                        results["valid"] = False
                    elif file_type == "bibliography":
                        results["warnings"].append(
                            f"Bibliography file not found: {project.bibliography_file}"
                        )

            # Check project metadata
            if not project.title.strip():
                results["errors"].append("Project title cannot be empty")
                results["valid"] = False

            if not project.authors:
                results["warnings"].append("No authors specified")

            # Check for corresponding author
            if project.corresponding_author:
                corresponding = project.get_corresponding_author()
                if not corresponding:
                    results["errors"].append(
                        "Corresponding author not found in authors list"
                    )
                    results["valid"] = False

            # Check build configuration
            output_path = project.get_output_path()
            results["structure_checks"]["output_directory"] = output_path.exists()

            logger.info(f"Project validation completed. Valid: {results['valid']}")
            return results

        except Exception as e:
            logger.error(f"Error during project validation: {e}")
            results["errors"].append(f"Validation error: {str(e)}")
            results["valid"] = False
            return results

    def list_projects(self, search_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        List all Paperflow projects in a directory.

        Args:
            search_path: Directory to search for projects.

        Returns:
            List of project summaries.
        """
        if search_path is None:
            search_path = Path.cwd()

        projects = []

        try:
            for item in search_path.iterdir():
                if item.is_dir():
                    config_file = self._find_config_file(item)
                    if config_file:
                        try:
                            # Load basic project info
                            config_data = self._load_config_file(config_file)
                            projects.append(
                                {
                                    "name": config_data.get("name", item.name),
                                    "title": config_data.get("title", "Untitled"),
                                    "path": str(item),
                                    "status": config_data.get("status", "draft"),
                                    "updated_at": config_data.get("updated_at"),
                                }
                            )
                        except Exception as e:
                            logger.warning(
                                f"Could not load project info from {item}: {e}"
                            )

            return projects

        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return []

    def _parse_authors(self, authors_data: List[Dict[str, Any]]) -> List[Author]:
        """Parse authors from configuration data."""
        authors = []

        for author_data in authors_data:
            try:
                author = Author(**author_data)
                authors.append(author)
            except Exception as e:
                logger.warning(f"Could not parse author {author_data}: {e}")

        return authors

    def _find_config_file(self, project_path: Path) -> Optional[Path]:
        """Find configuration file in project directory."""
        config_names = [
            "config.yaml",
            "config.yml",
            ".paperflow.yaml",
            ".paperflow.yml",
        ]

        for name in config_names:
            config_file = project_path / name
            if config_file.exists():
                return config_file

        return None

    def _load_config_file(self, config_file: Path) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    async def _create_project_structure(self, project: Project) -> None:
        """Create basic project directory structure."""
        project_path = project.project_path

        # Create subdirectories
        directories = ["src", "figures", "assets", "dist"]

        for directory in directories:
            (project_path / directory).mkdir(exist_ok=True)

        # Create basic LaTeX file if it doesn't exist
        main_tex_file = project.get_main_tex_path()
        if not main_tex_file.exists():
            self._create_basic_latex_file(main_tex_file, project)

        # Create bibliography file if specified
        bib_file = project.get_bibliography_path()
        if bib_file and not bib_file.exists():
            self._create_basic_bibliography_file(bib_file)

    def _create_basic_latex_file(self, file_path: Path, project: Project) -> None:
        """Create a basic LaTeX file template."""
        author_string = " \\and ".join([author.name for author in project.authors])
        bib_name = project.bibliography_file.replace(".bib", "") if project.bibliography_file else "bibliography"
        
        content = f"""\\documentclass{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{amsmath}}
\\usepackage{{amsfonts}}
\\usepackage{{amssymb}}
\\usepackage{{graphicx}}
\\usepackage{{hyperref}}

\\title{{{project.title}}}
\\author{{{author_string}}}
\\date{{\\today}}

\\begin{{document}}

\\maketitle

\\begin{{abstract}}
{project.abstract}
\\end{{abstract}}

\\section{{Introduction}}

Your introduction here.

\\section{{Methods}}

Your methods here.

\\section{{Results}}

Your results here.

\\section{{Conclusion}}

Your conclusion here.

\\bibliographystyle{{plain}}
\\bibliography{{{bib_name}}}

\\end{{document}}
"""

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _create_basic_bibliography_file(self, file_path: Path) -> None:
        """Create a basic bibliography file."""
        content = """% Bibliography file for Paperflow project
% Add your references here in BibTeX format

@article{example2023,
    title={Example Paper Title},
    author={Author, First and Author, Second},
    journal={Example Journal},
    year={2023},
    volume={1},
    number={1},
    pages={1--10}
}
"""

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
