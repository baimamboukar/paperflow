"""
Base service interfaces for Paperflow.

This module defines abstract base classes and interfaces that all
services should implement, ensuring consistent behavior and enabling
dependency injection and testing.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol
from pathlib import Path

from paperflow.models.project import Project
from paperflow.config.settings import Settings


class ServiceProtocol(Protocol):
    """Protocol defining the basic service interface."""
    
    def initialize(self, settings: Settings) -> None:
        """Initialize the service with settings."""
        ...
    
    def cleanup(self) -> None:
        """Clean up service resources."""
        ...


class BaseService(ABC):
    """
    Abstract base class for all Paperflow services.
    
    Provides common functionality and enforces interface contracts
    for all service implementations.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize base service.
        
        Args:
            settings: Service configuration settings.
        """
        self._settings = settings
        self._initialized = False
        
    @property
    def settings(self) -> Optional[Settings]:
        """Get service settings."""
        return self._settings
    
    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
    
    def initialize(self, settings: Settings) -> None:
        """
        Initialize the service with settings.
        
        Args:
            settings: Service configuration.
        """
        self._settings = settings
        self._perform_initialization()
        self._initialized = True
    
    @abstractmethod
    def _perform_initialization(self) -> None:
        """Perform service-specific initialization."""
        pass
    
    def cleanup(self) -> None:
        """Clean up service resources."""
        if self._initialized:
            self._perform_cleanup()
            self._initialized = False
    
    def _perform_cleanup(self) -> None:
        """Perform service-specific cleanup."""
        pass
    
    def validate_settings(self) -> bool:
        """
        Validate service settings.
        
        Returns:
            True if settings are valid, False otherwise.
        """
        return self._settings is not None
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get service status information.
        
        Returns:
            Dictionary containing service status.
        """
        return {
            "service_name": self.__class__.__name__,
            "initialized": self._initialized,
            "has_settings": self._settings is not None,
        }


class ProjectServiceInterface(ABC):
    """Interface for project management services."""
    
    @abstractmethod
    async def create_project(self, project_data: Dict[str, Any]) -> Project:
        """Create a new project."""
        pass
    
    @abstractmethod
    async def load_project(self, project_path: Path) -> Project:
        """Load an existing project."""
        pass
    
    @abstractmethod
    async def save_project(self, project: Project) -> None:
        """Save project to disk."""
        pass
    
    @abstractmethod
    async def validate_project(self, project: Project) -> Dict[str, Any]:
        """Validate project structure and files."""
        pass


class SyncServiceInterface(ABC):
    """Interface for synchronization services."""
    
    @abstractmethod
    async def sync_project(self, project: Project) -> Dict[str, Any]:
        """Synchronize project with remote source."""
        pass
    
    @abstractmethod
    async def check_sync_status(self, project: Project) -> Dict[str, Any]:
        """Check synchronization status."""
        pass
    
    @abstractmethod
    async def resolve_conflicts(self, project: Project, resolution: str) -> None:
        """Resolve synchronization conflicts."""
        pass


class BuildServiceInterface(ABC):
    """Interface for build services."""
    
    @abstractmethod
    async def build_project(self, project: Project) -> Dict[str, Any]:
        """Build project output."""
        pass
    
    @abstractmethod
    async def clean_build(self, project: Project) -> None:
        """Clean build artifacts."""
        pass
    
    @abstractmethod
    async def get_build_status(self, project: Project) -> Dict[str, Any]:
        """Get build status information."""
        pass


class WebServiceInterface(ABC):
    """Interface for web services."""
    
    @abstractmethod
    async def start_server(self, project: Project) -> None:
        """Start development server."""
        pass
    
    @abstractmethod
    async def stop_server(self) -> None:
        """Stop development server."""
        pass
    
    @abstractmethod
    async def get_server_status(self) -> Dict[str, Any]:
        """Get server status."""
        pass


class DeployServiceInterface(ABC):
    """Interface for deployment services."""
    
    @abstractmethod
    async def deploy_project(self, project: Project, target: str) -> Dict[str, Any]:
        """Deploy project to target."""
        pass
    
    @abstractmethod
    async def get_deployment_status(self, project: Project) -> Dict[str, Any]:
        """Get deployment status."""
        pass
    
    @abstractmethod
    async def rollback_deployment(self, project: Project, version: str) -> None:
        """Rollback to previous deployment."""
        pass


class ServiceManager:
    """
    Service manager for dependency injection and lifecycle management.
    
    Manages service instances, their dependencies, and provides
    a central point for service lookup and configuration.
    """
    
    def __init__(self):
        """Initialize service manager."""
        self._services: Dict[str, BaseService] = {}
        self._settings: Optional[Settings] = None
    
    def register_service(self, name: str, service: BaseService) -> None:
        """
        Register a service with the manager.
        
        Args:
            name: Service name for lookup.
            service: Service instance to register.
        """
        self._services[name] = service
        
        # Initialize service if settings are available
        if self._settings and not service.is_initialized:
            service.initialize(self._settings)
    
    def get_service(self, name: str) -> Optional[BaseService]:
        """
        Get a service by name.
        
        Args:
            name: Service name.
            
        Returns:
            Service instance or None if not found.
        """
        return self._services.get(name)
    
    def initialize_all(self, settings: Settings) -> None:
        """
        Initialize all registered services.
        
        Args:
            settings: Global settings to use for initialization.
        """
        self._settings = settings
        
        for service in self._services.values():
            if not service.is_initialized:
                service.initialize(settings)
    
    def cleanup_all(self) -> None:
        """Clean up all registered services."""
        for service in self._services.values():
            service.cleanup()
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all registered services.
        
        Returns:
            Dictionary mapping service names to their status.
        """
        return {
            name: service.get_status() 
            for name, service in self._services.items()
        }
    
    def list_services(self) -> list[str]:
        """Get list of registered service names."""
        return list(self._services.keys())