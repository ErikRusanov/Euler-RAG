"""FastAPI application factory."""

from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.API_TITLE,
        description="RAG service for solving problems using subject-specific notations",
        version=settings.API_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # Setup routes
    app.include_router(router)

    return app
