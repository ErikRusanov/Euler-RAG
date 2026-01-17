"""Authentication routes for cookie-based browser access."""

import hmac
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Form, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.middleware.cookie_auth import COOKIE_NAME, generate_session_token
from app.utils.templates import templates

logger = logging.getLogger(__name__)


def is_safe_redirect_url(url: str) -> bool:
    """Check if redirect URL is safe (internal path only).

    Prevents open redirect vulnerabilities by rejecting absolute URLs
    and external domains.

    Args:
        url: URL to validate.

    Returns:
        True if URL is a safe internal path, False otherwise.
    """
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return False
    if not url.startswith("/"):
        return False
    if url.startswith("//"):
        return False
    return True


def get_safe_redirect_url(url: str, default: str = "/login") -> str:
    """Get a safe redirect URL, falling back to default if unsafe.

    Args:
        url: URL to validate and return.
        default: Default URL to use if provided URL is unsafe.

    Returns:
        Safe redirect URL.
    """
    return url if is_safe_redirect_url(url) else default


router = APIRouter(tags=["auth"])


@router.get("/login")
async def login_page(
    request: Request,
    next: str = Query(default="/", description="URL to redirect after login"),
    error: str = Query(default="", description="Error message to display"),
) -> Response:
    """Display login form.

    Args:
        request: Incoming HTTP request.
        next: URL to redirect to after successful login.
        error: Optional error message to display.

    Returns:
        HTML login form.
    """
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error, "next_url": next},
    )


@router.post("/auth", response_model=None)
async def authenticate(
    request: Request,
    api_key: str = Form(..., description="API key for authentication"),
    next: str = Form(default="/", description="URL to redirect after login"),
) -> Response:
    """Validate API key and set session cookie.

    Args:
        request: Incoming HTTP request.
        api_key: The API key submitted by the user.
        next: URL to redirect to after successful login.

    Returns:
        Redirect response to next URL or 403 page if invalid.
    """
    settings = get_settings()

    if not hmac.compare_digest(api_key, settings.api_key):
        logger.warning("Failed login attempt")
        return templates.TemplateResponse(
            request=request,
            name="403.html",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Generate session token and set cookie
    session_token = generate_session_token(settings.api_key)
    safe_next = get_safe_redirect_url(next, default="/login")

    redirect_response = RedirectResponse(
        url=safe_next, status_code=status.HTTP_302_FOUND
    )
    redirect_response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=not settings.is_development,
        samesite="lax",
        max_age=86400 * 7,  # 7 days
    )

    logger.info("Successful login", extra={"redirect_to": safe_next})
    return redirect_response


@router.post("/logout")
async def logout(
    next: str = Query(default="/login", description="URL to redirect after logout"),
) -> RedirectResponse:
    """Clear session cookie and logout.

    Args:
        next: URL to redirect to after logout.

    Returns:
        Redirect response with cleared cookie.
    """
    safe_next = get_safe_redirect_url(next, default="/login")
    redirect_response = RedirectResponse(
        url=safe_next, status_code=status.HTTP_302_FOUND
    )
    redirect_response.delete_cookie(key=COOKIE_NAME)
    logger.info("User logged out")
    return redirect_response
