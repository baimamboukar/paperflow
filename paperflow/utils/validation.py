"""
Validation utilities for Paperflow.

This module provides validation functions and utilities used
throughout the application for data validation and verification.
"""

import re
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


class ValidationUtils:
    """Utility class for validation operations."""

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email address format.

        Args:
            email: Email address to validate.

        Returns:
            True if valid email format.
        """
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate URL format.

        Args:
            url: URL to validate.

        Returns:
            True if valid URL format.
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    @staticmethod
    def validate_orcid(orcid: str) -> bool:
        """
        Validate ORCID identifier format.

        Args:
            orcid: ORCID identifier to validate.

        Returns:
            True if valid ORCID format.
        """
        # Remove URL prefix if present
        orcid_id = orcid.replace("https://orcid.org/", "").replace(
            "http://orcid.org/", ""
        )

        # ORCID format: 0000-0000-0000-0000 or 0000-0000-0000-000X
        pattern = r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
        return bool(re.match(pattern, orcid_id))

    @staticmethod
    def validate_doi(doi: str) -> bool:
        """
        Validate DOI format.

        Args:
            doi: DOI to validate.

        Returns:
            True if valid DOI format.
        """
        # Basic DOI pattern: 10.xxxx/xxxxx
        pattern = r"^10\.\d{4,}/[^\s]+$"

        # Remove common URL prefixes
        clean_doi = doi.replace("https://doi.org/", "").replace(
            "http://dx.doi.org/", ""
        )

        return bool(re.match(pattern, clean_doi))

    @staticmethod
    def validate_arxiv_id(arxiv_id: str) -> bool:
        """
        Validate arXiv identifier format.

        Args:
            arxiv_id: arXiv ID to validate.

        Returns:
            True if valid arXiv format.
        """
        # New format: YYMM.NNNN[vN]
        new_pattern = r"^\d{4}\.\d{4,5}(v\d+)?$"

        # Old format: subject-class/YYMMnnn
        old_pattern = r"^[a-z-]+(\.[A-Z]{2})?/\d{7}$"

        return bool(re.match(new_pattern, arxiv_id) or re.match(old_pattern, arxiv_id))

    @staticmethod
    def validate_file_path(file_path: str, must_exist: bool = False) -> bool:
        """
        Validate file path format and existence.

        Args:
            file_path: File path to validate.
            must_exist: Whether file must exist on disk.

        Returns:
            True if valid file path.
        """
        try:
            path = Path(file_path)

            # Check for invalid characters
            invalid_chars = '<>"|?*' if path.is_absolute() else '<>:"|?*'
            if any(char in str(path) for char in invalid_chars):
                return False

            # Check existence if required
            if must_exist and not path.exists():
                return False

            return True

        except Exception:
            return False

    @staticmethod
    def validate_project_name(name: str) -> Dict[str, Any]:
        """
        Validate project name with detailed feedback.

        Args:
            name: Project name to validate.

        Returns:
            Dictionary with validation results.
        """
        result = {"valid": True, "errors": [], "warnings": []}

        # Check length
        if not name or len(name.strip()) < 1:
            result["valid"] = False
            result["errors"].append("Project name cannot be empty")
            return result

        if len(name) > 255:
            result["valid"] = False
            result["errors"].append("Project name too long (max 255 characters)")

        # Check for invalid filesystem characters
        invalid_chars = '<>:"/\\|?*'
        found_invalid = [char for char in invalid_chars if char in name]
        if found_invalid:
            result["valid"] = False
            result["errors"].append(
                f"Invalid characters found: {', '.join(found_invalid)}"
            )

        # Check for leading/trailing whitespace
        if name != name.strip():
            result["warnings"].append("Project name has leading or trailing whitespace")

        # Check for reserved names (Windows)
        reserved_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        }

        if name.upper() in reserved_names:
            result["valid"] = False
            result["errors"].append(f"'{name}' is a reserved system name")

        return result

    @staticmethod
    def validate_latex_file(file_path: Path) -> Dict[str, Any]:
        """
        Validate LaTeX file structure and syntax.

        Args:
            file_path: Path to LaTeX file.

        Returns:
            Dictionary with validation results.
        """
        result = {"valid": True, "errors": [], "warnings": [], "info": {}}

        if not file_path.exists():
            result["valid"] = False
            result["errors"].append(f"LaTeX file not found: {file_path}")
            return result

        try:
            content = file_path.read_text(encoding="utf-8")

            # Check for document class
            if not re.search(r"\\documentclass\{[^}]+\}", content):
                result["errors"].append("No \\documentclass found")
                result["valid"] = False

            # Check for begin/end document
            if not re.search(r"\\begin\{document\}", content):
                result["errors"].append("No \\begin{document} found")
                result["valid"] = False

            if not re.search(r"\\end\{document\}", content):
                result["errors"].append("No \\end{document} found")
                result["valid"] = False

            # Count environments
            begin_count = len(re.findall(r"\\begin\{[^}]+\}", content))
            end_count = len(re.findall(r"\\end\{[^}]+\}", content))

            if begin_count != end_count:
                result["warnings"].append(
                    f"Unmatched environments: {begin_count} begin, {end_count} end"
                )

            # Basic statistics
            result["info"] = {
                "line_count": len(content.splitlines()),
                "character_count": len(content),
                "word_count": len(content.split()),
                "environment_count": begin_count,
            }

        except UnicodeDecodeError:
            result["valid"] = False
            result["errors"].append("File encoding error - not valid UTF-8")
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Error reading file: {str(e)}")

        return result

    @staticmethod
    def validate_configuration(config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate configuration data structure.

        Args:
            config_data: Configuration dictionary to validate.

        Returns:
            Dictionary with validation results.
        """
        result = {"valid": True, "errors": [], "warnings": []}

        # Required fields
        required_fields = ["name", "title"]

        for field in required_fields:
            if field not in config_data:
                result["valid"] = False
                result["errors"].append(f"Required field missing: {field}")
            elif not config_data[field]:
                result["valid"] = False
                result["errors"].append(f"Required field empty: {field}")

        # Validate authors if present
        if "authors" in config_data:
            authors = config_data["authors"]
            if not isinstance(authors, list):
                result["valid"] = False
                result["errors"].append("Authors must be a list")
            else:
                for i, author in enumerate(authors):
                    if not isinstance(author, dict):
                        result["errors"].append(f"Author {i} must be a dictionary")
                        continue

                    if "name" not in author:
                        result["errors"].append(f"Author {i} missing name")

                    if "email" in author and not ValidationUtils.validate_email(
                        author["email"]
                    ):
                        result["warnings"].append(
                            f"Author {i} has invalid email format"
                        )

                    if "orcid" in author and not ValidationUtils.validate_orcid(
                        author["orcid"]
                    ):
                        result["warnings"].append(
                            f"Author {i} has invalid ORCID format"
                        )

        # Validate optional fields
        if "doi" in config_data and config_data["doi"]:
            if not ValidationUtils.validate_doi(config_data["doi"]):
                result["warnings"].append("Invalid DOI format")

        if "arxiv_id" in config_data and config_data["arxiv_id"]:
            if not ValidationUtils.validate_arxiv_id(config_data["arxiv_id"]):
                result["warnings"].append("Invalid arXiv ID format")

        return result
