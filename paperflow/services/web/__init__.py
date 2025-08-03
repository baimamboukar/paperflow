"""Web services for Paperflow."""

from paperflow.services.web.web_service import WebService
from paperflow.services.web.server import PaperflowServer
from paperflow.services.web.theme_manager import ThemeManager

__all__ = [
    "WebService",
    "PaperflowServer",
    "ThemeManager", 
]