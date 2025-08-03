"""
Health check router for Paperflow API.

This module provides endpoints for monitoring system health,
uptime, and component status.
"""

import asyncio
import os
import psutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from paperflow.api.dependencies import get_settings
from paperflow.api.schemas.base import HealthCheck, HealthStatus
from paperflow.config.settings import Settings
from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter()

# Application start time for uptime calculation
_start_time = time.time()


def get_uptime() -> float:
    """Get application uptime in seconds."""
    return time.time() - _start_time


async def check_disk_space(path: str, min_free_gb: float = 1.0) -> Dict[str, Any]:
    """Check disk space for a given path."""
    try:
        usage = psutil.disk_usage(path)
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        used_percent = (usage.used / usage.total) * 100
        
        return {
            "status": "healthy" if free_gb >= min_free_gb else "unhealthy",
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "used_percent": round(used_percent, 2),
            "threshold_gb": min_free_gb,
        }
    except Exception as e:
        logger.error(f"Error checking disk space for {path}: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


async def check_memory() -> Dict[str, Any]:
    """Check system memory usage."""
    try:
        memory = psutil.virtual_memory()
        return {
            "status": "healthy" if memory.percent < 90 else "degraded",
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_percent": round(memory.percent, 2),
            "threshold_percent": 90,
        }
    except Exception as e:
        logger.error(f"Error checking memory: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


async def check_cpu() -> Dict[str, Any]:
    """Check CPU usage."""
    try:
        # Get CPU usage over 1 second interval
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        return {
            "status": "healthy" if cpu_percent < 80 else "degraded",
            "usage_percent": round(cpu_percent, 2),
            "core_count": cpu_count,
            "threshold_percent": 80,
        }
    except Exception as e:
        logger.error(f"Error checking CPU: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


async def check_latex_installation() -> Dict[str, Any]:
    """Check if LaTeX is installed and accessible."""
    try:
        # Try to run pdflatex --version
        process = await asyncio.create_subprocess_exec(
            "pdflatex", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            # Extract version info from stdout
            version_info = stdout.decode().split('\n')[0] if stdout else "Unknown"
            return {
                "status": "healthy",
                "installed": True,
                "version": version_info.strip(),
            }
        else:
            return {
                "status": "unhealthy",
                "installed": False,
                "error": stderr.decode() if stderr else "Unknown error",
            }
    except FileNotFoundError:
        return {
            "status": "unhealthy",
            "installed": False,
            "error": "LaTeX not found in PATH",
        }
    except Exception as e:
        logger.error(f"Error checking LaTeX installation: {e}")
        return {
            "status": "error",
            "installed": False,
            "error": str(e),
        }


async def check_git_installation() -> Dict[str, Any]:
    """Check if Git is installed and accessible."""
    try:
        process = await asyncio.create_subprocess_exec(
            "git", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            version_info = stdout.decode().strip() if stdout else "Unknown"
            return {
                "status": "healthy",
                "installed": True,
                "version": version_info,
            }
        else:
            return {
                "status": "unhealthy",
                "installed": False,
                "error": stderr.decode() if stderr else "Unknown error",
            }
    except FileNotFoundError:
        return {
            "status": "unhealthy",
            "installed": False,
            "error": "Git not found in PATH",
        }
    except Exception as e:
        logger.error(f"Error checking Git installation: {e}")
        return {
            "status": "error",
            "installed": False,
            "error": str(e),
        }


async def check_directories(settings: Settings) -> Dict[str, Any]:
    """Check that required directories exist and are writable."""
    directories = {
        "data": settings.data_directory,
        "temp": settings.temp_directory,
        "projects": settings.projects_directory,
    }
    
    results = {}
    overall_status = "healthy"
    
    for name, path in directories.items():
        try:
            path_obj = Path(path)
            exists = path_obj.exists()
            is_dir = path_obj.is_dir() if exists else False
            writable = os.access(path, os.W_OK) if exists else False
            
            if exists and is_dir and writable:
                status = "healthy"
            elif not exists:
                # Try to create the directory
                try:
                    path_obj.mkdir(parents=True, exist_ok=True)
                    status = "healthy"
                    exists = True
                    is_dir = True
                    writable = True
                except Exception as create_error:
                    status = "unhealthy"
                    overall_status = "unhealthy"
                    logger.error(f"Cannot create directory {path}: {create_error}")
            else:
                status = "unhealthy"
                overall_status = "unhealthy"
            
            results[name] = {
                "status": status,
                "path": str(path),
                "exists": exists,
                "is_directory": is_dir,
                "writable": writable,
            }
            
        except Exception as e:
            logger.error(f"Error checking directory {path}: {e}")
            results[name] = {
                "status": "error",
                "path": str(path),
                "error": str(e),
            }
            overall_status = "degraded"
    
    return {
        "status": overall_status,
        "directories": results,
    }


async def check_python_packages() -> Dict[str, Any]:
    """Check that required Python packages are available."""
    required_packages = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "jinja2",
        "click",
        "pyyaml",
        "gitpython",
        "pygithub",
        "requests",
        "aiofiles",
        "python-multipart",
    ]
    
    results = {}
    overall_status = "healthy"
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            results[package] = {
                "status": "healthy",
                "installed": True,
            }
        except ImportError:
            results[package] = {
                "status": "unhealthy",
                "installed": False,
                "error": "Package not installed",
            }
            overall_status = "degraded"
        except Exception as e:
            results[package] = {
                "status": "error",
                "installed": False,
                "error": str(e),
            }
            overall_status = "degraded"
    
    return {
        "status": overall_status,
        "packages": results,
    }


def determine_overall_status(checks: Dict[str, Any]) -> HealthStatus:
    """Determine overall health status from individual checks."""
    statuses = []
    
    for check_name, check_result in checks.items():
        if isinstance(check_result, dict):
            check_status = check_result.get("status", "unknown")
            statuses.append(check_status)
    
    if "error" in statuses or "unhealthy" in statuses:
        return HealthStatus.UNHEALTHY
    elif "degraded" in statuses:
        return HealthStatus.DEGRADED
    else:
        return HealthStatus.HEALTHY


@router.get("/", response_model=HealthCheck)
async def basic_health_check():
    """
    Basic health check endpoint.
    
    Returns minimal health information for quick status checks.
    """
    try:
        uptime = get_uptime()
        
        return HealthCheck(
            status=HealthStatus.HEALTHY,
            version="1.0.0",
            uptime=uptime,
            checks={
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": uptime,
            }
        )
    except Exception as e:
        logger.error(f"Error in basic health check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed"
        )


@router.get("/detailed", response_model=HealthCheck)
async def detailed_health_check(settings: Settings = Depends(get_settings)):
    """
    Detailed health check endpoint.
    
    Returns comprehensive system health information including:
    - System resources (CPU, memory, disk)
    - Required software (LaTeX, Git)
    - Directory accessibility
    - Python package availability
    """
    try:
        uptime = get_uptime()
        
        # Perform all health checks concurrently
        checks = await asyncio.gather(
            check_memory(),
            check_cpu(),
            check_disk_space(settings.data_directory),
            check_latex_installation(),
            check_git_installation(),
            check_directories(settings),
            check_python_packages(),
            return_exceptions=True
        )
        
        # Process results
        check_results = {
            "memory": checks[0] if not isinstance(checks[0], Exception) else {"status": "error", "error": str(checks[0])},
            "cpu": checks[1] if not isinstance(checks[1], Exception) else {"status": "error", "error": str(checks[1])},
            "disk": checks[2] if not isinstance(checks[2], Exception) else {"status": "error", "error": str(checks[2])},
            "latex": checks[3] if not isinstance(checks[3], Exception) else {"status": "error", "error": str(checks[3])},
            "git": checks[4] if not isinstance(checks[4], Exception) else {"status": "error", "error": str(checks[4])},
            "directories": checks[5] if not isinstance(checks[5], Exception) else {"status": "error", "error": str(checks[5])},
            "packages": checks[6] if not isinstance(checks[6], Exception) else {"status": "error", "error": str(checks[6])},
        }
        
        # Add system information
        check_results["system"] = {
            "status": "healthy",
            "platform": os.name,
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            "process_id": os.getpid(),
            "uptime_seconds": uptime,
            "uptime_human": str(timedelta(seconds=int(uptime))),
        }
        
        # Determine overall status
        overall_status = determine_overall_status(check_results)
        
        return HealthCheck(
            status=overall_status,
            version="1.0.0",
            uptime=uptime,
            checks=check_results
        )
        
    except Exception as e:
        logger.error(f"Error in detailed health check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detailed health check failed: {str(e)}"
        )


@router.get("/readiness")
async def readiness_check(settings: Settings = Depends(get_settings)):
    """
    Readiness check for Kubernetes/container orchestration.
    
    Returns 200 if the service is ready to accept requests.
    Returns 503 if the service is not ready.
    """
    try:
        # Check critical dependencies
        critical_checks = await asyncio.gather(
            check_directories(settings),
            check_latex_installation(),
            check_git_installation(),
            return_exceptions=True
        )
        
        # Check if any critical component is unhealthy
        for check in critical_checks:
            if isinstance(check, Exception):
                logger.error(f"Readiness check failed: {check}")
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "ready": False,
                        "error": "Critical dependency check failed"
                    }
                )
            
            if isinstance(check, dict) and check.get("status") == "unhealthy":
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "ready": False,
                        "error": "Critical dependency is unhealthy"
                    }
                )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"ready": True}
        )
        
    except Exception as e:
        logger.error(f"Readiness check error: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "ready": False,
                "error": str(e)
            }
        )


@router.get("/liveness")
async def liveness_check():
    """
    Liveness check for Kubernetes/container orchestration.
    
    Returns 200 if the service is alive and responding.
    This is a minimal check that should always succeed unless
    the process is completely unresponsive.
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "alive": True,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": get_uptime()
        }
    )