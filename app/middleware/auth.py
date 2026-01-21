"""Authentication middleware for API key validation."""

import hmac
import logging
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.middleware.cookie_auth import COOKIE_NAME, verify_session_token

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to validate API key for protected endpoints.

    All endpoints under /api prefix require X-API-KEY header.
    If request has valid session cookie, automatically injects X-API-KEY header.
    This allows admin panel to make API requests without JavaScript reading cookie.
    Other endpoints (health, docs, root) are public.
    """

    PROTECTED_PREFIX: str = "/api"

    @classmethod
    def is_protected_path(cls, path: str) -> bool:
        """Check if path requires authentication.

        Args:
            path: Request URL path.

        Returns:
            True if path is under protected prefix and requires auth.
        """
        return path.startswith(cls.PROTECTED_PREFIX)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate API key if required."""
        if not self.is_protected_path(request.url.path):
            return await call_next(request)

        settings = get_settings()

        # Get API key from header (if already present)
        api_key = request.headers.get("X-API-KEY") or request.headers.get("x-api-key")

        # If no API key in header, check for valid session cookie
        if not api_key:
            session_token = request.cookies.get(COOKIE_NAME)
            if session_token and verify_session_token(session_token, settings.api_key):
                # Valid session - automatically inject API key header
                # Add header to scope (headers are lowercase in Starlette)
                api_key_bytes = settings.api_key.encode()
                request.scope["headers"].append((b"x-api-key", api_key_bytes))
                # Also update request.headers for downstream handlers
                # Note: request.headers is read-only, but we've added to scope
                api_key = settings.api_key
                logger.debug(
                    "Auto-injected API key from session cookie",
                    extra={"path": request.url.path},
                )

        # Validate API key
        if not api_key or not hmac.compare_digest(api_key, settings.api_key):
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
