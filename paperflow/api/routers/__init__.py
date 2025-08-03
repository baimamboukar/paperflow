"""
API routers for Paperflow.

This module provides FastAPI routers for all API endpoints,
organizing them by functionality and resource type.
"""

from .analytics import router as analytics_router
from .build import router as build_router
from .github import router as github_router
from .health import router as health_router
from .projects import router as projects_router
from .sync import router as sync_router
from .templates import router as templates_router
from .webhooks import router as webhooks_router
from .websocket_analytics import router as websocket_analytics_router

__all__ = [
    "analytics_router",
    "build_router",
    "github_router", 
    "health_router",
    "projects_router",
    "sync_router",
    "templates_router",
    "webhooks_router",
    "websocket_analytics_router",
]