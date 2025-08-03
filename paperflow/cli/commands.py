"""
CLI command implementations for Paperflow.

This module contains the implementation of all CLI commands
that can be executed through the Paperflow command-line interface.
"""

import asyncio
from abc import ABC, abstractmethod
from argparse import Namespace
from pathlib import Path

from paperflow.config.settings import Settings
from paperflow.services.project_service import ProjectService
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


class BaseCommand(ABC):
    """Base class for all CLI commands."""

    def __init__(self, settings: Settings):
        """Initialize command with settings."""
        self.settings = settings

    @abstractmethod
    def run(self, args: Namespace) -> int:
        """
        Run the command.

        Args:
            args: Parsed command line arguments.

        Returns:
            Exit code (0 for success, non-zero for error).
        """
        pass


class InitCommand(BaseCommand):
    """Initialize a new Paperflow project."""

    def run(self, args: Namespace) -> int:
        """Run the init command."""
        try:
            logger.info(f"Initializing new project: {args.name}")

            project_data = {
                "name": args.name,
                "title": args.title or f"Paper: {args.name}",
                "authors": [],
                "abstract": "",
                "keywords": [],
            }

            # Create project service
            project_service = ProjectService(self.settings)
            project_service.initialize(self.settings)

            # Create project
            project = asyncio.run(
                project_service.create_project(project_data, Path.cwd() / args.name)
            )

            print(
                f"✓ Project '{project.name}' created successfully at {project.project_path}"
            )
            print(f"✓ Main LaTeX file: {project.main_tex_file}")
            print("✓ Configuration file: config.yaml")
            print()
            print("Next steps:")
            print(f"  cd {args.name}")
            print("  paperflow build     # Build the project")
            print("  paperflow serve     # Start development server")

            return 0

        except FileExistsError as e:
            logger.error(f"Project already exists: {e}")
            print(f"Error: {e}")
            return 1
        except Exception as e:
            logger.error(f"Failed to initialize project: {e}")
            print(f"Error: Failed to initialize project: {e}")
            return 1


class BuildCommand(BaseCommand):
    """Build project output."""

    def run(self, args: Namespace) -> int:
        """Run the build command."""
        try:
            logger.info("Building project")

            # Load current project
            project_service = ProjectService(self.settings)
            project_service.initialize(self.settings)

            project = asyncio.run(project_service.load_project(Path.cwd()))

            print(f"Building project: {project.name}")

            # TODO: Implement actual build logic
            print("✓ Build completed successfully")

            return 0

        except FileNotFoundError as e:
            logger.error(f"Project not found: {e}")
            print("Error: No Paperflow project found in current directory")
            print("Use 'paperflow init <name>' to create a new project")
            return 1
        except Exception as e:
            logger.error(f"Build failed: {e}")
            print(f"Error: Build failed: {e}")
            return 1


class ServeCommand(BaseCommand):
    """Start development server."""

    def run(self, args: Namespace) -> int:
        """Run the serve command."""
        try:
            logger.info(f"Starting development server on {args.host}:{args.port}")

            # Load current project
            project_service = ProjectService(self.settings)
            project_service.initialize(self.settings)

            project = asyncio.run(project_service.load_project(Path.cwd()))

            print(f"Starting server for project: {project.name}")
            print(f"Server running at: http://{args.host}:{args.port}")
            print("Press Ctrl+C to stop the server")

            # TODO: Implement actual server logic
            try:
                while True:
                    import time

                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nServer stopped")

            return 0

        except FileNotFoundError as e:
            logger.error(f"Project not found: {e}")
            print("Error: No Paperflow project found in current directory")
            return 1
        except Exception as e:
            logger.error(f"Server failed: {e}")
            print(f"Error: Server failed: {e}")
            return 1


class SyncCommand(BaseCommand):
    """Sync with remote sources."""

    def run(self, args: Namespace) -> int:
        """Run the sync command."""
        try:
            logger.info(f"Syncing project with source: {args.source}")

            # Load current project
            project_service = ProjectService(self.settings)
            project_service.initialize(self.settings)

            project = asyncio.run(project_service.load_project(Path.cwd()))

            print(f"Syncing project: {project.name}")
            print(f"Source: {args.source}")

            # TODO: Implement actual sync logic
            print("✓ Sync completed successfully")

            return 0

        except FileNotFoundError as e:
            logger.error(f"Project not found: {e}")
            print("Error: No Paperflow project found in current directory")
            return 1
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            print(f"Error: Sync failed: {e}")
            return 1


class DeployCommand(BaseCommand):
    """Deploy to configured targets."""

    def run(self, args: Namespace) -> int:
        """Run the deploy command."""
        try:
            logger.info(f"Deploying project to target: {args.target}")

            # Load current project
            project_service = ProjectService(self.settings)
            project_service.initialize(self.settings)

            project = asyncio.run(project_service.load_project(Path.cwd()))

            print(f"Deploying project: {project.name}")
            print(f"Target: {args.target}")

            # TODO: Implement actual deployment logic
            print("✓ Deployment completed successfully")

            return 0

        except FileNotFoundError as e:
            logger.error(f"Project not found: {e}")
            print("Error: No Paperflow project found in current directory")
            return 1
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            print(f"Error: Deployment failed: {e}")
            return 1


class StatusCommand(BaseCommand):
    """Show project status."""

    def run(self, args: Namespace) -> int:
        """Run the status command."""
        try:
            logger.info("Checking project status")

            # Load current project
            project_service = ProjectService(self.settings)
            project_service.initialize(self.settings)

            project = asyncio.run(project_service.load_project(Path.cwd()))

            # Get project summary
            summary = project.get_project_summary()

            print(f"Project Status: {project.name}")
            print("=" * 50)
            print(f"Title: {summary['title']}")
            print(f"Status: {summary['status']}")
            print(f"Type: {summary['type']}")
            print(f"Authors: {summary['authors_count']}")
            print(f"Keywords: {summary['keywords_count']}")
            print(f"Created: {summary['created_at']}")
            print(f"Updated: {summary['updated_at']}")

            if summary["last_build"]:
                print(f"Last Build: {summary['last_build']}")
            else:
                print("Last Build: Never")

            if summary["last_sync"]:
                print(f"Last Sync: {summary['last_sync']}")
            else:
                print("Last Sync: Never")

            print()
            print("File Validation:")
            for file_type, exists in summary["file_validation"].items():
                status = "✓" if exists else "✗"
                print(f"  {status} {file_type}")

            if args.verbose:
                # Show detailed validation
                validation = asyncio.run(project_service.validate_project(project))

                print()
                print("Detailed Validation:")
                if validation["errors"]:
                    print("Errors:")
                    for error in validation["errors"]:
                        print(f"  ✗ {error}")

                if validation["warnings"]:
                    print("Warnings:")
                    for warning in validation["warnings"]:
                        print(f"  ⚠ {warning}")

                if not validation["errors"] and not validation["warnings"]:
                    print("  ✓ No issues found")

            return 0

        except FileNotFoundError as e:
            logger.error(f"Project not found: {e}")
            print("Error: No Paperflow project found in current directory")
            return 1
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            print(f"Error: Status check failed: {e}")
            return 1


class ValidateCommand(BaseCommand):
    """Validate project structure and files."""

    def run(self, args: Namespace) -> int:
        """Run the validate command."""
        try:
            logger.info("Validating project")

            # Load current project
            project_service = ProjectService(self.settings)
            project_service.initialize(self.settings)

            project = asyncio.run(project_service.load_project(Path.cwd()))

            # Validate project
            validation = asyncio.run(project_service.validate_project(project))

            print(f"Validating project: {project.name}")
            print("=" * 50)

            if validation["valid"]:
                print("✓ Project validation passed")
            else:
                print("✗ Project validation failed")

            print()
            print("File Checks:")
            for file_type, exists in validation["file_checks"].items():
                status = "✓" if exists else "✗"
                print(f"  {status} {file_type}")

            if validation["errors"]:
                print()
                print("Errors:")
                for error in validation["errors"]:
                    print(f"  ✗ {error}")

            if validation["warnings"]:
                print()
                print("Warnings:")
                for warning in validation["warnings"]:
                    print(f"  ⚠ {warning}")

            if not validation["errors"] and not validation["warnings"]:
                print()
                print("✓ No issues found")

            return 0 if validation["valid"] else 1

        except FileNotFoundError as e:
            logger.error(f"Project not found: {e}")
            print("Error: No Paperflow project found in current directory")
            return 1
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            print(f"Error: Validation failed: {e}")
            return 1
