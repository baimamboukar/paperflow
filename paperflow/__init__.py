"""
Paperflow - Academic paper website generator.

A comprehensive framework for converting LaTeX academic papers into beautiful,
interactive websites with modern web technologies.
"""

__version__ = "2.0.0"
__author__ = "Paperflow Team"
__email__ = "contact@paperflow.dev"

from paperflow.models.project import Project
from paperflow.config.settings import Settings

__all__ = [
    "Project",
    "Settings",
]