"""Authentication routes for cookie-based browser access."""

import logging

from fastapi import APIRouter, Form, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import get_settings
from app.middleware.cookie_auth import COOKIE_NAME, generate_session_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# Minimal inline HTML for login form (no separate template file)
LOGIN_FORM_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Login - Euler RAG</title>
    <style>
        body {{ font-family: system-ui, sans-serif; display: flex;
        justify-content: center; align-items: center;
        height: 100vh; margin: 0; background: #f5f5f5; }}
        .login-box {{ background: white; padding: 2rem; border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        width: 300px; }}
        h1 {{ margin: 0 0 1rem; font-size: 1.5rem; color: #333; }}
        input {{ width: 100%; padding: 0.75rem; margin-bottom: 1rem;
        border: 1px solid #ddd; border-radius: 4px;
        box-sizing: border-box; }}
        button {{ width: 100%; padding: 0.75rem; background: #007bff;
        color: white; border: none; border-radius: 4px;
        cursor: pointer; font-size: 1rem; }}
        button:hover {{ background: #0056b3; }}
        .error {{ color: #dc3545; margin-bottom: 1rem; font-size: 0.9rem; }}
    </style>
</head>
<body>
    <div class="login-box">
        <h1>Euler RAG</h1>
        {error}
        <form method="post" action="/auth">
            <input type="hidden" name="next" value="{next_url}">
            <input type="password" name="api_key"
            placeholder="Enter API Key" required autofocus>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
"""


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    next: str = Query(default="/", description="URL to redirect after login"),
    error: str = Query(default="", description="Error message to display"),
) -> HTMLResponse:
    """Display login form.

    Args:
        request: Incoming HTTP request.
        next: URL to redirect to after successful login.
        error: Optional error message to display.

    Returns:
        HTML login form.
    """
    error_html = f'<p class="error">{error}</p>' if error else ""
    html_content = LOGIN_FORM_HTML.format(error=error_html, next_url=next)
    return HTMLResponse(content=html_content)


@router.post("/auth")
async def authenticate(
    response: Response,
    api_key: str = Form(..., description="API key for authentication"),
    next: str = Form(default="/", description="URL to redirect after login"),
) -> RedirectResponse:
    """Validate API key and set session cookie.

    Args:
        response: HTTP response object for setting cookies.
        api_key: The API key submitted by the user.
        next: URL to redirect to after successful login.

    Returns:
        Redirect response to next URL or back to login with error.
    """
    settings = get_settings()

    if api_key != settings.api_key:
        logger.warning("Failed login attempt")
        return RedirectResponse(
            url=f"/login?next={next}&error=Invalid API key",
            status_code=status.HTTP_302_FOUND,
        )

    # Generate session token and set cookie
    session_token = generate_session_token(settings.api_key)

    redirect_response = RedirectResponse(url=next, status_code=status.HTTP_302_FOUND)
    redirect_response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=not settings.is_development,
        samesite="lax",
        max_age=86400 * 7,  # 7 days
    )

    logger.info("Successful login", extra={"redirect_to": next})
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
    redirect_response = RedirectResponse(url=next, status_code=status.HTTP_302_FOUND)
    redirect_response.delete_cookie(key=COOKIE_NAME)
    logger.info("User logged out")
    return redirect_response
