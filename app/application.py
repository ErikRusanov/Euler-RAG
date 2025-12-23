"""FastAPI application factory."""

from fastapi import APIRouter, FastAPI

from app.config import settings
from app.utils.db import close_db, init_db

# Create main router
router = APIRouter()


@router.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Euler RAG API", "version": settings.API_VERSION}


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.API_TITLE,
        description="RAG service for solving problems using subject-specific notations",
        version=settings.API_VERSION,
        debug=settings.DEBUG,
    )

    # Setup routes
    app.include_router(router)

    # Initialize database connection on startup
    @app.on_event("startup")
    async def startup_event():
        await init_db()

    # Close database connections on shutdown
    @app.on_event("shutdown")
    async def shutdown_event():
        await close_db()

    return app
