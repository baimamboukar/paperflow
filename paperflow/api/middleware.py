"""
Custom middleware for Paperflow FastAPI application.

This module provides middleware for logging, error handling,
rate limiting, and other cross-cutting concerns.
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Dict

from fastapi import HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from paperflow.utils.logging import setup_logging

logger = setup_logging(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests and responses.

    Logs request details, response status, and timing information.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details."""
        start_time = time.time()

        # Log request details
        client_ip = get_remote_address(request)
        method = request.method
        url = str(request.url)
        user_agent = request.headers.get("user-agent", "")

        logger.info(
            f"Request started: {method} {url} from {client_ip}",
            extra={
                "method": method,
                "url": url,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        # Process request
        try:
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Log response details
            logger.info(
                f"Request completed: {method} {url} - {response.status_code} ({process_time:.3f}s)",
                extra={
                    "method": method,
                    "url": url,
                    "status_code": response.status_code,
                    "process_time": process_time,
                    "client_ip": client_ip,
                },
            )

            # Add timing header
            response.headers["X-Process-Time"] = str(process_time)

            return response

        except Exception as e:
            process_time = time.time() - start_time

            logger.error(
                f"Request failed: {method} {url} - {str(e)} ({process_time:.3f}s)",
                extra={
                    "method": method,
                    "url": url,
                    "error": str(e),
                    "process_time": process_time,
                    "client_ip": client_ip,
                },
                exc_info=True,
            )

            raise


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for global error handling.

    Catches unhandled exceptions and returns appropriate JSON responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with error handling."""
        try:
            return await call_next(request)

        except HTTPException:
            # Re-raise HTTP exceptions (handled by FastAPI)
            raise

        except ValueError as e:
            logger.warning(f"Validation error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Validation Error",
                    "message": str(e),
                    "type": "validation_error",
                },
            )

        except FileNotFoundError as e:
            logger.warning(f"File not found: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": "File Not Found",
                    "message": str(e),
                    "type": "file_not_found",
                },
            )

        except PermissionError as e:
            logger.warning(f"Permission denied: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Permission Denied",
                    "message": str(e),
                    "type": "permission_error",
                },
            )

        except Exception as e:
            logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "type": "internal_error",
                },
            )


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Simple rate limiting middleware.

    Implements per-IP rate limiting for API endpoints.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        client_ip = get_remote_address(request)
        now = datetime.utcnow()

        # Clean old requests
        cutoff_time = now - timedelta(minutes=1)
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip] if req_time > cutoff_time
        ]

        # Check rate limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate Limit Exceeded",
                    "message": f"Too many requests. Limit: {self.requests_per_minute} per minute",
                    "retry_after": 60,
                },
                headers={"Retry-After": "60"},
            )

        # Record this request
        self.requests[client_ip].append(now)

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware for adding security headers to responses.

    Adds common security headers to improve application security.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self'"
        )

        return response


class CacheControlMiddleware(BaseHTTPMiddleware):
    """
    Middleware for adding cache control headers.

    Sets appropriate caching headers based on request path.
    """

    def __init__(self, app):
        super().__init__(app)
        self.cache_rules = {
            "/static/": "public, max-age=86400",  # 1 day for static files
            "/api/v1/health": "no-cache",  # No cache for health checks
            "/api/v1/projects": "private, max-age=300",  # 5 minutes for projects
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add cache control headers."""
        response = await call_next(request)

        # Determine cache control based on path
        path = request.url.path
        cache_control = "private, no-cache"  # Default

        for pattern, control in self.cache_rules.items():
            if path.startswith(pattern):
                cache_control = control
                break

        response.headers["Cache-Control"] = cache_control

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware for adding unique request IDs.

    Adds a unique ID to each request for tracing and logging.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request ID to request and response."""
        import uuid

        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Add to request state for use in endpoints
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add to response headers
        response.headers["X-Request-ID"] = request_id

        return response


# Advanced rate limiter using slowapi
limiter = Limiter(key_func=get_remote_address)


def create_rate_limiter() -> Limiter:
    """Create and configure rate limiter."""
    return limiter


# Custom rate limit exceeded handler
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded errors."""
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "Rate Limit Exceeded",
            "message": f"Rate limit exceeded: {exc.detail}",
            "retry_after": exc.retry_after,
        },
    )
    response.headers["Retry-After"] = str(exc.retry_after)
    return response


class WebSocketMiddleware(BaseHTTPMiddleware):
    """
    Middleware for WebSocket request handling.

    Handles WebSocket upgrade requests and adds necessary headers.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle WebSocket requests."""
        # Check if this is a WebSocket upgrade request
        if (
            request.headers.get("upgrade", "").lower() == "websocket"
            and request.headers.get("connection", "").lower() == "upgrade"
        ):
            logger.info(
                f"WebSocket connection request from {get_remote_address(request)}"
            )

        return await call_next(request)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware for managing request context.

    Stores request-specific data that can be accessed throughout the request lifecycle.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Initialize request context."""
        # Initialize request context
        request.state.start_time = time.time()
        request.state.client_ip = get_remote_address(request)
        request.state.user_agent = request.headers.get("user-agent", "")

        return await call_next(request)
