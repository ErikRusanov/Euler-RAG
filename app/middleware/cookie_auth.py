"""Cookie-based authentication middleware for browser access to public routes."""

import hashlib
import hmac
import logging
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.middleware.auth import APIKeyMiddleware

logger = logging.getLogger(__name__)

COOKIE_NAME = "euler_session"
SESSION_MESSAGE = "euler_rag_session_valid"


def generate_session_token(api_key: str) -> str:
    """Generate a session token using HMAC.

    Args:
        api_key: The API key to use as secret.

    Returns:
        Hex-encoded HMAC digest.
    """
    return hmac.new(
        api_key.encode(), SESSION_MESSAGE.encode(), hashlib.sha256
    ).hexdigest()


def verify_session_token(token: str, api_key: str) -> bool:
    """Verify a session token.

    Args:
        token: The token to verify.
        api_key: The API key to use as secret.

    Returns:
        True if token is valid, False otherwise.
    """
    expected = generate_session_token(api_key)
    return hmac.compare_digest(token, expected)


class CookieAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for cookie-based authentication on public routes.

    Public routes (not under /api) require a valid session cookie.
    If no valid cookie is present, returns 403 Forbidden.
    """

    # Paths that don't require cookie authentication
    EXCLUDED_PATHS: set[str] = {"/login", "/auth", "/logout"}
    # Path prefixes that don't require cookie authentication
    EXCLUDED_PREFIXES: tuple[str, ...] = ("/static/",)

    @classmethod
    def is_excluded_path(cls, path: str) -> bool:
        """Check if path is excluded from cookie authentication.

        Args:
            path: Request URL path.

        Returns:
            True if path should skip cookie auth.
        """
        if path in cls.EXCLUDED_PATHS:
            return True
        return path.startswith(cls.EXCLUDED_PREFIXES)

    @classmethod
    def is_public_path(cls, path: str) -> bool:
        """Check if path is a public route (not under /api).

        Args:
            path: Request URL path.

        Returns:
            True if path is public and requires cookie auth.
        """
        return not APIKeyMiddleware.is_protected_path(path)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate session cookie for public routes.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            Response from handler or 403 if unauthorized.
        """
        path = request.url.path

        # Skip authentication for excluded paths and protected API routes
        if self.is_excluded_path(path) or not self.is_public_path(path):
            return await call_next(request)

        settings = get_settings()
        session_token = request.cookies.get(COOKIE_NAME)

        if not session_token or not verify_session_token(
            session_token, settings.api_key
        ):
            logger.warning(
                "Unauthorized browser access",
                extra={
                    "path": path,
                    "method": request.method,
                    "has_cookie": bool(session_token),
                },
            )
            # Store the original URL to redirect after login
            redirect_url = f"/login?next={path}"
            return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

        return await call_next(request)
