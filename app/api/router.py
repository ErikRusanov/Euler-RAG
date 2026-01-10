"""API router factory with core endpoints."""

import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.utils.db import db_manager

logger = logging.getLogger(__name__)


def create_health_router() -> APIRouter:
    """Create router with health check endpoints.

    Returns:
        APIRouter with health endpoints.
    """
    router = APIRouter(tags=["Health"])

    @router.get("/", tags=["General"])
    async def root() -> dict:
        """Root endpoint - API information."""
        settings = get_settings()
        return {
            "message": "Euler RAG API",
            "version": settings.api_version,
            "environment": settings.environment,
            "status": "operational",
        }

    @router.get("/health", status_code=status.HTTP_200_OK)
    async def health_check() -> dict:
        """Health check endpoint - basic application health."""
        return {"status": "healthy", "service": "euler-rag"}

    @router.get("/health/db", status_code=status.HTTP_200_OK, response_model=None)
    async def health_check_db() -> JSONResponse:
        """Deep health check - includes database connectivity check."""
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

    return router


def create_api_router() -> APIRouter:
    """Create and configure main API router with all endpoints.

    Returns:
        Configured APIRouter instance with all routes.
    """
    from app.api.documents import router as documents_router

    router = APIRouter()

    # Include health/core routes
    router.include_router(create_health_router())

    # Include feature routers
    router.include_router(documents_router)

    return router
