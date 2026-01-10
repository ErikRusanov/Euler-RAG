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

    All endpoints except public paths require X-API-KEY header.
    """

    @classmethod
    def public_paths(cls) -> set[str]:
        """Return set of public endpoints that don't require authentication."""
        return {
            "/",
            "/health",
            "/health/db",
            "/docs",
            "/redoc",
            "/openapi.json",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate API key if required."""
        if request.url.path in self.public_paths():
            return await call_next(request)

        # Get and validate API key
        api_key = request.headers.get("X-API-KEY") or request.headers.get("x-api-key")
        settings = get_settings()

        if not api_key or api_key != settings.api_key:
            logger.warning(
                "Unauthorized request",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "has_key": bool(api_key),
                },
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Invalid or missing API key",
                },
            )

        return await call_next(request)
