"""
FastAPI main application for Paperflow.

This module sets up the main FastAPI application with all routes,
middleware, and configuration for the Paperflow backend API.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from paperflow.api.dependencies import get_settings
from paperflow.api.middleware import (
    ErrorHandlingMiddleware,
    RateLimitingMiddleware,
    RequestLoggingMiddleware,
)
from paperflow.api.routers import (
    analytics,
    build,
    github,
    health,
    projects,
    sync,
    templates,
    webhooks,
    websocket_analytics,
)
from paperflow.utils.logging import setup_logging

# Setup logging
logger = setup_logging(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Handles startup and shutdown events for the application.
    """
    # Startup
    logger.info("Starting Paperflow API server...")

    # Initialize services here if needed
    settings = get_settings()
    logger.info(f"Loaded settings from: {settings.config_file}")

    # Create necessary directories
    os.makedirs(settings.data_directory, exist_ok=True)
    os.makedirs(settings.temp_directory, exist_ok=True)

    yield

    # Shutdown
    logger.info("Shutting down Paperflow API server...")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    # Create FastAPI app
    app = FastAPI(
        title="Paperflow API",
        description="API for academic paper workflow management",
        version="1.0.0",
        docs_url=None,  # Disable default docs
        redoc_url=None,  # Disable default redoc
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    # Add middleware
    add_middleware(app, settings)

    # Add routers
    add_routers(app)

    # Add custom docs
    add_custom_docs(app)

    # Add static files if they exist
    add_static_files(app)

    # Add exception handlers
    add_exception_handlers(app)

    return app


def add_middleware(app: FastAPI, settings) -> None:
    """Add middleware to the FastAPI application."""

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Session middleware (for authentication)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        max_age=86400,  # 24 hours
    )

    # Compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Custom middleware
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RateLimitingMiddleware)


def add_routers(app: FastAPI) -> None:
    """Add all API routers to the application."""

    # API v1 routes
    api_prefix = "/api/v1"

    app.include_router(health.router, prefix=f"{api_prefix}/health", tags=["health"])

    app.include_router(
        projects.router, prefix=f"{api_prefix}/projects", tags=["projects"]
    )

    app.include_router(
        sync.router, prefix=f"{api_prefix}/sync", tags=["synchronization"]
    )

    app.include_router(build.router, prefix=f"{api_prefix}/build", tags=["build"])

    app.include_router(github.router, prefix=f"{api_prefix}/github", tags=["github"])

    app.include_router(
        templates.router, prefix=f"{api_prefix}/templates", tags=["templates"]
    )

    app.include_router(
        webhooks.router, prefix=f"{api_prefix}/webhooks", tags=["webhooks"]
    )

    app.include_router(
        analytics.router, prefix=f"{api_prefix}/analytics", tags=["analytics"]
    )

    # WebSocket routes (no prefix needed for WebSocket)
    app.include_router(websocket_analytics.router)


def add_custom_docs(app: FastAPI) -> None:
    """Add custom documentation routes."""

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
        )

    @app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
    async def swagger_ui_redirect():
        return get_swagger_ui_oauth2_redirect_html()

    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=app.title + " - ReDoc",
            redoc_js_url="https://unpkg.com/redoc@next/bundles/redoc.standalone.js",
        )


def add_static_files(app: FastAPI) -> None:
    """Add static file serving if directories exist."""

    # Try to mount static files from common locations
    static_paths = [
        ("/static", "static"),
        ("/assets", "assets"),
        ("/uploads", "uploads"),
    ]

    for mount_path, directory in static_paths:
        if Path(directory).exists():
            app.mount(mount_path, StaticFiles(directory=directory), name=directory)


def add_exception_handlers(app: FastAPI) -> None:
    """Add global exception handlers."""

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "Not Found",
                "message": "The requested resource was not found",
                "path": str(request.url.path),
            },
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc):
        logger.error(f"Internal server error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
            },
        )


# Create the app instance
app = create_app()


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Paperflow API",
        "version": "1.0.0",
        "description": "API for academic paper workflow management",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/api/v1/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn

    # Development server
    uvicorn.run(
        "paperflow.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
