"""Authentication middleware for API key validation."""

import logging
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to validate API key for protected endpoints.

    Public endpoints (accessible without API key):
    - / (root)
    - /health
    - /health/db
    - /docs
    - /redoc
    - /openapi.json

    All other endpoints require X-API-KEY header.
    """

    # List of paths that don't require authentication
    PUBLIC_PATHS = {
        "/",
        "/health",
        "/health/db",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate API key if required.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or endpoint handler.

        Returns:
            HTTP response.
        """
        # Check if path is public
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get("X-API-KEY") or request.headers.get("x-api-key")

        if not api_key:
            logger.warning(
                "Request without API key",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "client": request.client.host if request.client else None,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "API key is required. Please provide X-API-KEY header.",
                },
            )

        # Validate API key
        settings = get_settings()
        if api_key != settings.api_key:
            logger.warning(
                "Request with invalid API key",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "client": request.client.host if request.client else None,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Invalid API key provided.",
                },
            )

        # API key is valid, proceed with request
        return await call_next(request)
