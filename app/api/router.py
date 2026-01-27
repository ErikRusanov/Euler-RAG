"""API router factory with core endpoints."""

import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.middleware.auth import APIKeyMiddleware
from app.utils.db import db_manager

logger = logging.getLogger(__name__)


def create_public_router() -> APIRouter:
    """Create router with public endpoints (require cookie auth).

    Includes admin panel routes and root redirect.

    Returns:
        APIRouter with admin routes.
    """
    from fastapi.responses import RedirectResponse

    from app.api.admin import router as admin_router

    router = APIRouter()

    # Root redirect to admin panel
    @router.get("/")
    async def root():
        """Redirect root to admin panel."""
        return RedirectResponse(url="/admin", status_code=302)

    # Include admin routes
    router.include_router(admin_router)

    return router


def create_auth_router() -> APIRouter:
    """Create router with authentication endpoints.

    These endpoints handle cookie-based browser authentication.

    Returns:
        APIRouter with auth endpoints (login, logout).
    """
    from app.api.auth import router as auth_router

    return auth_router


def create_protected_router() -> APIRouter:
    """Create router with protected endpoints (API key required).

    All routes are mounted under /api prefix and require X-API-KEY header.

    Returns:
        APIRouter with protected API endpoints including health checks.
    """
    from app.api.documents import router as documents_router

    router = APIRouter(prefix=APIKeyMiddleware.PROTECTED_PREFIX)

    @router.get("/health", tags=["Health"], status_code=status.HTTP_200_OK)
    async def health_check() -> dict:
        """Health check endpoint - basic application health.

        Returns:
            Health status response.
        """
        return {"status": "healthy", "service": "euler-rag"}

    @router.get(
        "/health/db",
        tags=["Health"],
        status_code=status.HTTP_200_OK,
        response_model=None,
    )
    async def health_check_db() -> JSONResponse:
        """Deep health check - includes database connectivity check.

        Returns:
            Health status with database connectivity information.
        """
        try:
            is_healthy = await db_manager.verify_connection()
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "healthy",
                    "database": "connected" if is_healthy else "disconnected",
                },
            )
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "unhealthy",
                    "database": "disconnected",
                    "error": str(e),
                },
            )

    router.include_router(documents_router)

    return router
