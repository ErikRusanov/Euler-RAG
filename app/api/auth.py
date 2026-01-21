"""Authentication routes for cookie-based browser access."""

import hmac
import logging

from fastapi import APIRouter, Form, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.middleware.cookie_auth import COOKIE_NAME, generate_session_token
from app.utils.api_helpers import get_safe_redirect_url, is_same_origin
from app.utils.templates import templates

logger = logging.getLogger(__name__)


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
    if not is_same_origin(request):
        logger.warning("CSRF check failed on /auth")
        return templates.TemplateResponse(
            request=request,
            name="403.html",
            status_code=status.HTTP_403_FORBIDDEN,
        )

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
    # Set session token cookie (httpOnly for security)
    # API key is automatically injected by APIKeyMiddleware for /api requests
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
    request: Request,
    next: str = Query(default="/login", description="URL to redirect after logout"),
) -> Response:
    """Clear session cookie and logout.

    Args:
        request: Incoming HTTP request.
        next: URL to redirect to after logout.

    Returns:
        Redirect response with cleared cookie or 403 if CSRF check fails.
    """
    if not is_same_origin(request):
        logger.warning("CSRF check failed on /logout")
        return templates.TemplateResponse(
            request=request,
            name="403.html",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    safe_next = get_safe_redirect_url(next, default="/login")
    redirect_response = RedirectResponse(
        url=safe_next, status_code=status.HTTP_302_FOUND
    )
    redirect_response.delete_cookie(key=COOKIE_NAME)
    logger.info("User logged out")
    return redirect_response
