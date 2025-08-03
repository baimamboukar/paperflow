"""
Main CLI entry point for Paperflow.

This module provides the command-line interface for Paperflow,
handling argument parsing and routing to appropriate commands.
"""

import argparse
import sys
from typing import List, Optional

from paperflow import __version__
from paperflow.config.loader import ConfigLoader
from paperflow.config.settings import Settings
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="paperflow",
        description="Generate beautiful academic paper websites with ease",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  paperflow init my-paper              # Create new project
  paperflow build                      # Build current project
  paperflow serve                      # Start development server
  paperflow sync                       # Sync with remote sources
  paperflow deploy                     # Deploy to configured targets

For more information, visit: https://paperflow.github.io/docs
        """,
    )

    parser.add_argument(
        "--version", action="version", version=f"paperflow {__version__}"
    )

    parser.add_argument("--config", type=str, help="Path to configuration file")

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level",
    )

    parser.add_argument("--log-file", type=str, help="Path to log file")

    # Create subcommands
    subparsers = parser.add_subparsers(
        dest="command", help="Available commands", metavar="COMMAND"
    )

    # Init command
    init_parser = subparsers.add_parser(
        "init", help="Initialize a new Paperflow project"
    )
    init_parser.add_argument("name", help="Project name")
    init_parser.add_argument("--title", help="Paper title")
    init_parser.add_argument("--template", help="Project template to use")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build project output")
    build_parser.add_argument(
        "--clean", action="store_true", help="Clean build directory before building"
    )
    build_parser.add_argument(
        "--format",
        choices=["html", "pdf", "all"],
        default="all",
        help="Output format to build",
    )

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start development server")
    serve_parser.add_argument("--host", default="localhost", help="Server host")
    serve_parser.add_argument("--port", type=int, default=8000, help="Server port")
    serve_parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync with remote sources")
    sync_parser.add_argument(
        "--source",
        choices=["overleaf", "git", "all"],
        default="all",
        help="Sync source",
    )

    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Deploy to configured targets")
    deploy_parser.add_argument(
        "--target",
        choices=["github-pages", "netlify", "vercel", "all"],
        default="all",
        help="Deployment target",
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Show project status")
    status_parser.add_argument(
        "--verbose", action="store_true", help="Show detailed status"
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate project structure and files"
    )

    return parser


def load_settings(config_path: Optional[str] = None) -> Settings:
    """Load application settings."""
    try:
        config_loader = ConfigLoader(config_path)
        return config_loader.load_settings()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        # Return default settings on failure
        return Settings()


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point.

    Args:
        argv: Command line arguments (defaults to sys.argv).

    Returns:
        Exit code.
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Setup logging
    setup_logging(__name__, level=args.log_level, log_file=args.log_file)

    try:
        # Load settings
        settings = load_settings(args.config)

        # Handle commands
        if args.command == "init":
            from paperflow.cli.commands import InitCommand

            command = InitCommand(settings)
            return command.run(args)

        elif args.command == "build":
            from paperflow.cli.commands import BuildCommand

            command = BuildCommand(settings)
            return command.run(args)

        elif args.command == "serve":
            from paperflow.cli.commands import ServeCommand

            command = ServeCommand(settings)
            return command.run(args)

        elif args.command == "sync":
            from paperflow.cli.commands import SyncCommand

            command = SyncCommand(settings)
            return command.run(args)

        elif args.command == "deploy":
            from paperflow.cli.commands import DeployCommand

            command = DeployCommand(settings)
            return command.run(args)

        elif args.command == "status":
            from paperflow.cli.commands import StatusCommand

            command = StatusCommand(settings)
            return command.run(args)

        elif args.command == "validate":
            from paperflow.cli.commands import ValidateCommand

            command = ValidateCommand(settings)
            return command.run(args)

        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
