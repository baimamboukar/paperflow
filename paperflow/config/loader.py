"""
Configuration loader for Paperflow.

This module handles loading configuration from various sources including
YAML files, environment variables, and command-line arguments with proper
validation and merging.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from pydantic import ValidationError

from paperflow.config.settings import Settings
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


class ConfigLoader:
    """
    Configuration loader with support for multiple sources.

    Loads and merges configuration from:
    1. Default values
    2. YAML configuration files
    3. Environment variables
    4. Command-line overrides
    """

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize configuration loader.

        Args:
            config_path: Path to configuration file. If None, will search
                        for config.yaml in current directory.
        """
        self.config_path = self._resolve_config_path(config_path)
        self._config_data: Dict[str, Any] = {}

    def _resolve_config_path(
        self, config_path: Optional[Union[str, Path]]
    ) -> Optional[Path]:
        """Resolve configuration file path."""
        if config_path is None:
            # Search for default config file
            default_names = [
                "config.yaml",
                "config.yml",
                ".paperflow.yaml",
                ".paperflow.yml",
            ]
            for name in default_names:
                path = Path.cwd() / name
                if path.exists():
                    return path
            return None

        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Configuration file not found: {path}")
            return None

        return path

    def load_yaml_config(self, path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Args:
            path: Path to YAML file. If None, uses default config path.

        Returns:
            Dictionary containing configuration data.
        """
        config_file = path or self.config_path
        if not config_file or not config_file.exists():
            logger.info("No YAML configuration file found, using defaults")
            return {}

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            logger.info(f"Loaded configuration from {config_file}")
            return self._flatten_config(data)

        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            raise ValueError(f"Invalid YAML configuration: {e}")
        except Exception as e:
            logger.error(f"Error loading configuration file: {e}")
            raise

    def _flatten_config(self, data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """
        Flatten nested configuration dictionary.

        Converts nested dictionaries to flat structure with underscore-separated keys.
        For example: {"paper": {"title": "..."}} becomes {"paper_title": "..."}
        """
        flattened = {}

        for key, value in data.items():
            new_key = f"{prefix}_{key}" if prefix else key

            if isinstance(value, dict):
                # Recursively flatten nested dictionaries
                flattened.update(self._flatten_config(value, new_key))
            else:
                flattened[new_key] = value

        return flattened

    def load_env_config(self) -> Dict[str, Any]:
        """
        Load configuration from environment variables.

        Looks for environment variables with PAPERFLOW_ prefix and converts
        them to the appropriate configuration keys.

        Returns:
            Dictionary containing environment configuration.
        """
        env_config = {}
        prefix = "PAPERFLOW_"

        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix) :].lower()

                # Handle boolean values
                if value.lower() in ("true", "false"):
                    env_config[config_key] = value.lower() == "true"
                # Handle integer values
                elif value.isdigit():
                    env_config[config_key] = int(value)
                # Handle list values (comma-separated)
                elif "," in value:
                    env_config[config_key] = [item.strip() for item in value.split(",")]
                else:
                    env_config[config_key] = value

        if env_config:
            logger.info(
                f"Loaded {len(env_config)} configuration values from environment"
            )

        return env_config

    def merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge multiple configuration dictionaries.

        Later dictionaries override earlier ones for conflicting keys.

        Args:
            *configs: Configuration dictionaries to merge.

        Returns:
            Merged configuration dictionary.
        """
        merged = {}

        for config in configs:
            if config:
                merged.update(config)

        return merged

    def load_settings(
        self,
        yaml_config: Optional[Dict[str, Any]] = None,
        env_overrides: Optional[Dict[str, Any]] = None,
        cli_overrides: Optional[Dict[str, Any]] = None,
    ) -> Settings:
        """
        Load and validate complete settings configuration.

        Args:
            yaml_config: YAML configuration dictionary. If None, loads from file.
            env_overrides: Environment variable overrides.
            cli_overrides: Command-line argument overrides.

        Returns:
            Validated Settings object.

        Raises:
            ValidationError: If configuration validation fails.
        """
        try:
            # Load from different sources
            if yaml_config is None:
                yaml_config = self.load_yaml_config()

            if env_overrides is None:
                env_overrides = self.load_env_config()

            if cli_overrides is None:
                cli_overrides = {}

            # Merge configurations (order determines precedence)
            merged_config = self.merge_configs(
                yaml_config, env_overrides, cli_overrides
            )

            # Store for debugging
            self._config_data = merged_config

            # Create and validate settings
            settings = Settings(**merged_config)

            # Update project path if config file was found
            if self.config_path:
                settings.project_path = self.config_path.parent

            logger.info("Configuration loaded and validated successfully")
            return settings

        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            raise

    def save_config(self, settings: Settings, path: Optional[Path] = None) -> None:
        """
        Save settings to YAML configuration file.

        Args:
            settings: Settings object to save.
            path: Output file path. If None, uses default config path.
        """
        output_path = path or self.config_path or Path.cwd() / "config.yaml"

        # Convert settings to nested dictionary structure
        config_dict = self._unflatten_config(settings.to_dict())

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    config_dict, f, default_flow_style=False, sort_keys=True, indent=2
                )

            logger.info(f"Configuration saved to {output_path}")

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            raise

    def _unflatten_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert flat configuration dictionary back to nested structure.

        Reverses the flattening process for saving to YAML.
        """
        nested = {}

        for key, value in data.items():
            parts = key.split("_")
            current = nested

            # Navigate/create nested structure
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Set final value
            current[parts[-1]] = value

        return nested

    def validate_config(self, config_dict: Dict[str, Any]) -> bool:
        """
        Validate configuration dictionary without creating Settings object.

        Args:
            config_dict: Configuration dictionary to validate.

        Returns:
            True if valid, False otherwise.
        """
        try:
            Settings(**config_dict)
            return True
        except ValidationError:
            return False

    def get_config_info(self) -> Dict[str, Any]:
        """
        Get information about loaded configuration.

        Returns:
            Dictionary with configuration metadata.
        """
        return {
            "config_path": str(self.config_path) if self.config_path else None,
            "config_exists": self.config_path.exists() if self.config_path else False,
            "loaded_keys": list(self._config_data.keys()),
            "source_count": len(self._config_data),
        }
