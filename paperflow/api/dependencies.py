"""
FastAPI dependency injection for Paperflow.

This module provides dependency injection functions for services,
authentication, and configuration used throughout the API.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic_settings import BaseSettings

from paperflow.config.settings import Settings
from paperflow.services.git_service import GitService
from paperflow.services.github_service import GitHubService
from paperflow.services.project_service import ProjectService
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)

# Security scheme for API key authentication
security = HTTPBearer(auto_error=False)


class APISettings(BaseSettings):
    """API-specific settings configuration."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    api_key: Optional[str] = None

    # CORS
    cors_origins: list = ["http://localhost:3000", "http://localhost:8080"]

    # Database
    database_url: str = "sqlite:///./paperflow.db"

    # File storage
    data_directory: str = "./data"
    temp_directory: str = "./temp"
    upload_directory: str = "./uploads"
    max_file_size: int = 100 * 1024 * 1024  # 100MB

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # Background tasks
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # GitHub integration
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None
    github_webhook_secret: Optional[str] = None

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    class Config:
        env_file = ".env"
        env_prefix = "PAPERFLOW_"


@lru_cache()
def get_api_settings() -> APISettings:
    """Get cached API settings instance."""
    return APISettings()


@lru_cache()
def get_settings() -> Settings:
    """Get cached Paperflow settings instance."""
    return Settings()


# Service dependencies
def get_project_service(settings: Settings = Depends(get_settings)) -> ProjectService:
    """Get project service instance."""
    return ProjectService(settings)


def get_git_service(settings: Settings = Depends(get_settings)) -> GitService:
    """Get Git service instance."""
    return GitService(settings)


def get_github_service(settings: Settings = Depends(get_settings)) -> GitHubService:
    """Get GitHub service instance."""
    return GitHubService(settings)


# Authentication dependencies
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    api_settings: APISettings = Depends(get_api_settings),
) -> Optional[Dict[str, Any]]:
    """
    Get current authenticated user.

    This function handles both API key and session-based authentication.
    Returns None if authentication is optional for the endpoint.
    """
    # Check for API key authentication
    if credentials:
        if api_settings.api_key and credentials.credentials == api_settings.api_key:
            return {"type": "api_key", "authenticated": True, "user_id": "api_user"}

    # Check for session-based authentication
    session = request.session
    if session.get("authenticated"):
        return {
            "type": "session",
            "authenticated": True,
            "user_id": session.get("user_id"),
            "github_token": session.get("github_token"),
        }

    return None


async def require_authentication(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Require authentication for protected endpoints.

    Raises HTTP 401 if user is not authenticated.
    """
    if not current_user or not current_user.get("authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return current_user


async def require_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    api_settings: APISettings = Depends(get_api_settings),
) -> str:
    """
    Require valid API key for sensitive operations.

    Raises HTTP 401 if API key is missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not api_settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="API key authentication not configured",
        )

    if credentials.credentials != api_settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


# Request validation dependencies
def validate_project_id(project_id: str) -> str:
    """Validate project ID format."""
    if not project_id or len(project_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Project ID is required"
        )
    return project_id.strip()


def validate_file_upload(
    file_size: int, api_settings: APISettings = Depends(get_api_settings)
) -> None:
    """Validate file upload constraints."""
    if file_size > api_settings.max_file_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum limit of {api_settings.max_file_size} bytes",
        )


# Path validation dependencies
def get_upload_directory(api_settings: APISettings = Depends(get_api_settings)) -> Path:
    """Get and ensure upload directory exists."""
    upload_dir = Path(api_settings.upload_directory)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def get_temp_directory(api_settings: APISettings = Depends(get_api_settings)) -> Path:
    """Get and ensure temporary directory exists."""
    temp_dir = Path(api_settings.temp_directory)
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


# GitHub integration dependencies
def get_github_credentials(
    current_user: Dict[str, Any] = Depends(require_authentication),
    api_settings: APISettings = Depends(get_api_settings),
) -> Dict[str, str]:
    """
    Get GitHub credentials for authenticated user.

    Returns OAuth token from session or raises error if not available.
    """
    if current_user.get("type") == "session":
        github_token = current_user.get("github_token")
        if not github_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub integration not configured for this user",
            )
        return {"token": github_token}

    # For API key authentication, check if client credentials are configured
    if not api_settings.github_client_id or not api_settings.github_client_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub integration not configured",
        )

    return {
        "client_id": api_settings.github_client_id,
        "client_secret": api_settings.github_client_secret,
    }


# WebSocket dependencies
class ConnectionManager:
    """WebSocket connection manager for real-time updates."""

    def __init__(self):
        self.active_connections: Dict[str, list] = {}

    async def connect(self, websocket, channel: str):
        """Connect to a specific channel."""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)

    def disconnect(self, websocket, channel: str):
        """Disconnect from a channel."""
        if channel in self.active_connections:
            self.active_connections[channel].remove(websocket)

    async def send_personal_message(self, message: str, websocket):
        """Send message to specific websocket."""
        await websocket.send_text(message)

    async def broadcast_to_channel(self, message: str, channel: str):
        """Broadcast message to all connections in a channel."""
        if channel in self.active_connections:
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to websocket: {e}")


# Global connection manager instance
connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get WebSocket connection manager."""
    return connection_manager


# Background task dependencies
def get_background_task_settings() -> Dict[str, Any]:
    """Get background task configuration."""
    api_settings = get_api_settings()
    return {
        "broker_url": api_settings.celery_broker_url,
        "result_backend": api_settings.celery_result_backend,
    }
