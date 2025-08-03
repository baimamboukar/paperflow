"""Web interface for Paperflow."""

from paperflow.web.app import create_app
from paperflow.web.routes import register_routes

__all__ = [
    "create_app",
    "register_routes",
]