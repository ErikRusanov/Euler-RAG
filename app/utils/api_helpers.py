"""API helper functions for routes."""

from urllib.parse import urlparse

from fastapi import Request

from app.utils.redis import get_redis_client
from app.workers.progress import ProgressTracker


def get_pagination_context(page: int, page_size: int, total: int) -> dict:
    """Calculate pagination metadata.

    Args:
        page: Current page number (1-indexed).
        page_size: Items per page.
        total: Total number of items.

    Returns:
        Dictionary with pagination metadata.
    """
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    start = (page - 1) * page_size + 1 if total > 0 else 0
    end = min(page * page_size, total)

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "start": start,
        "end": end,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


def get_progress_tracker() -> ProgressTracker:
    """Get ProgressTracker instance for dependency injection.

    Returns:
        ProgressTracker instance with Redis client.
    """
    redis = get_redis_client()
    return ProgressTracker(redis)


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


def is_same_origin(request: Request) -> bool:
    """Check if request Origin/Referer matches the host.

    Provides CSRF protection by verifying requests come from same origin.

    Args:
        request: Incoming HTTP request.

    Returns:
        True if request is from same origin, False otherwise.
    """
    host = request.headers.get("host", "")
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")

    if origin:
        parsed = urlparse(origin)
        return parsed.netloc == host

    if referer:
        parsed = urlparse(referer)
        return parsed.netloc == host

    return False
