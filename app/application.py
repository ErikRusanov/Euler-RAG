"""FastAPI application factory with production-ready configuration."""

import logging
import time
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import APIRouter, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.exceptions import (
    DatabaseConnectionError,
    ModelError,
    RecordNotFoundError,
)
from app.utils.db import close_db, db_manager, init_db

logger = logging.getLogger(__name__)


def create_router() -> APIRouter:
    """Create and configure API router with all endpoints.

    Returns:
        Configured APIRouter instance.
    """
    router = APIRouter()

    @router.get("/", tags=["General"])
    async def root():
        """Root endpoint - API information."""
        settings = get_settings()
        return {
            "message": "Euler RAG API",
            "version": settings.api_version,
            "environment": settings.environment,
            "status": "operational",
        }

    @router.get("/health", tags=["Health"], status_code=status.HTTP_200_OK)
    async def health_check():
        """Health check endpoint - basic application health."""
        return {
            "status": "healthy",
            "service": "euler-rag",
        }

    @router.get("/health/db", tags=["Health"], status_code=status.HTTP_200_OK)
    async def health_check_db():
        """Deep health check - includes database connectivity check."""
        try:
            is_healthy = await db_manager.verify_connection()
            return {
                "status": "healthy",
                "database": "connected" if is_healthy else "disconnected",
            }
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


def setup_middleware(app: FastAPI) -> None:
    """Configure application middleware.

    Args:
        app: FastAPI application instance.
    """
    settings = get_settings()

    # CORS middleware
    if settings.is_development:
        # Allow all origins in development
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # Restrict origins in production (should be configured via env vars)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
            allow_headers=["*"],
        )

    # Request timing middleware
    @app.middleware("http")
    async def add_process_time_header(
        request: Request, call_next: Callable
    ) -> Response:
        """Add X-Process-Time header to all responses."""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    # Logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable) -> Response:
        """Log all incoming requests and responses."""
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            },
        )
        response = await call_next(request)
        logger.info(
            f"Response: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
            },
        )
        return response


def setup_exception_handlers(app: FastAPI) -> None:
    """Configure application exception handlers.

    Args:
        app: FastAPI application instance.
    """

    @app.exception_handler(RecordNotFoundError)
    async def record_not_found_handler(
        request: Request, exc: RecordNotFoundError
    ) -> JSONResponse:
        """Handle RecordNotFoundError exceptions."""
        logger.warning(f"Record not found: {exc}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "Not Found",
                "message": str(exc),
                "model": exc.model_name,
                "record_id": exc.record_id,
            },
        )

    @app.exception_handler(DatabaseConnectionError)
    async def database_connection_handler(
        request: Request, exc: DatabaseConnectionError
    ) -> JSONResponse:
        """Handle DatabaseConnectionError exceptions."""
        logger.error(f"Database error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "Service Unavailable",
                "message": "Database connection error. Please try again later.",
            },
        )

    @app.exception_handler(ModelError)
    async def model_error_handler(request: Request, exc: ModelError) -> JSONResponse:
        """Handle generic ModelError exceptions."""
        logger.error(f"Model error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Bad Request",
                "message": str(exc),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle request validation errors."""
        logger.warning(f"Validation error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation Error",
                "message": "Invalid request data",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle all unhandled exceptions."""
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later.",
            },
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events.

    Args:
        app: FastAPI application instance.

    Yields:
        None: Application is running.
    """
    settings = get_settings()
    logger.info(f"Starting Euler RAG API v{settings.api_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # Startup
    try:
        await init_db()
        logger.info("Application startup complete")
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down application...")
    await close_db()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        description="RAG service for solving mathematical problems using subject-specific notations and conventions",
        version=settings.api_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
    )

    # Setup middleware
    setup_middleware(app)

    # Setup exception handlers
    setup_exception_handlers(app)

    # Setup routes
    router = create_router()
    app.include_router(router)

    logger.info("FastAPI application created successfully")

    return app
