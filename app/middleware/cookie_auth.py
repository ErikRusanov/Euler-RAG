"""Cookie-based authentication middleware for browser access to public routes."""

import hashlib
import hmac
import logging
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

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
    """Middleware for cookie-based authentication on protected browser routes.

    Only paths explicitly listed in PROTECTED_PATHS or matching PROTECTED_PREFIXES
    require a valid session cookie. If no valid cookie is present, redirects to login.
    """

    # Paths that require cookie authentication (whitelist)
    PROTECTED_PATHS: set[str] = set()
    # Path prefixes that require cookie authentication
    PROTECTED_PREFIXES: tuple[str, ...] = ()

    @classmethod
    def requires_cookie_auth(cls, path: str) -> bool:
        """Check if path requires cookie authentication.

        Args:
            path: Request URL path.

        Returns:
            True if path requires cookie auth.
        """
        if path in cls.PROTECTED_PATHS:
            return True
        return path.startswith(cls.PROTECTED_PREFIXES)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate session cookie for protected paths.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            Response from handler or redirect to login if unauthorized.
        """
        path = request.url.path

        # Only require authentication for explicitly protected paths
        if not self.requires_cookie_auth(path):
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
            redirect_url = f"/login?next={path}"
            return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

        return await call_next(request)
