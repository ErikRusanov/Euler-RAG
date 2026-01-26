"""FastAPI application factory with production-ready configuration."""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles

from app.api.router import (
    create_auth_router,
    create_protected_router,
    create_public_router,
)
from app.config import Settings, get_settings
from app.middleware.auth import APIKeyMiddleware
from app.middleware.cookie_auth import CookieAuthMiddleware
from app.utils.db import close_db, init_db
from app.utils.exception_handlers import register_exception_handlers
from app.utils.mathpix import close_mathpix, init_mathpix
from app.utils.redis import close_redis, init_redis
from app.utils.s3 import close_s3, init_s3
from app.workers import worker_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle.

    Tracks initialized resources and ensures proper cleanup on startup failure
    to prevent connection pool exhaustion.

    Args:
        app: FastAPI application instance.

    Yields:
        None while application is running.
    """
    settings = get_settings()
    logger.info(
        f"Starting Euler RAG API v{settings.api_version} "
        f"[{settings.environment}] debug={settings.debug}"
    )

    # Track what was initialized for cleanup on failure
    db_initialized = False
    s3_initialized = False
    redis_initialized = False
    mathpix_initialized = False
    workers_started = False

    try:
        await init_db()
        db_initialized = True

        init_s3()
        s3_initialized = True

        await init_redis()
        redis_initialized = True

        # Initialize Mathpix OCR client (optional, may be None if not configured)
        init_mathpix()
        mathpix_initialized = True

        await worker_manager.start()
        workers_started = True

        logger.info("Application startup complete")
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")

        # Cleanup in reverse order of initialization
        if workers_started:
            try:
                await worker_manager.stop()
            except Exception as cleanup_error:
                logger.error(
                    "Error stopping workers during cleanup",
                    extra={"error": str(cleanup_error)},
                    exc_info=True,
                )

        if mathpix_initialized:
            try:
                close_mathpix()
            except Exception as cleanup_error:
                logger.error(
                    "Error closing Mathpix during cleanup",
                    extra={"error": str(cleanup_error)},
                    exc_info=True,
                )

        if redis_initialized:
            try:
                await close_redis()
            except Exception as cleanup_error:
                logger.error(
                    "Error closing Redis during cleanup",
                    extra={"error": str(cleanup_error)},
                    exc_info=True,
                )

        if s3_initialized:
            try:
                close_s3()
            except Exception as cleanup_error:
                logger.error(
                    "Error closing S3 during cleanup",
                    extra={"error": str(cleanup_error)},
                    exc_info=True,
                )

        if db_initialized:
            try:
                await close_db()
            except Exception as cleanup_error:
                logger.error(
                    "Error closing DB during cleanup",
                    extra={"error": str(cleanup_error)},
                    exc_info=True,
                )

        raise

    yield

    logger.info("Shutting down application...")
    await worker_manager.stop()
    close_mathpix()
    await close_redis()
    close_s3()
    await close_db()
    logger.info("Application shutdown complete")


def _setup_cors(app: FastAPI, settings: Settings) -> None:
    """Configure CORS middleware based on environment."""
    if settings.is_development:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        origins = settings.cors_origins
        if not origins:
            logger.warning(
                "CORS origins not configured for production, "
                "all cross-origin requests will be blocked"
            )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
            allow_headers=["*"],
        )


def _setup_request_middleware(app: FastAPI) -> None:
    """Configure request processing middleware."""

    @app.middleware("http")
    async def add_process_time_header(
        request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Add X-Process-Time header to all responses."""
        start_time = time.time()
        response = await call_next(request)
        response.headers["X-Process-Time"] = f"{time.time() - start_time:.4f}"
        return response

    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Log incoming requests and responses."""
        extra = {
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else None,
        }
        logger.info(f"Request: {request.method} {request.url.path}", extra=extra)

        response = await call_next(request)

        extra["status_code"] = response.status_code
        logger.info(
            f"Response: {request.method} {request.url.path} - {response.status_code}",
            extra=extra,
        )
        return response


def _setup_openapi(app: FastAPI) -> None:
    """Configure custom OpenAPI schema with API key security."""

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        schema["components"]["securitySchemes"] = {
            "APIKeyHeader": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-KEY",
            }
        }

        for path, methods in schema["paths"].items():
            if path.startswith(APIKeyMiddleware.PROTECTED_PREFIX):
                for method in methods.values():
                    if isinstance(method, dict):
                        method["security"] = [{"APIKeyHeader": []}]

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        description=(
            "RAG service for solving mathematical problems using "
            "subject-specific notations and conventions"
        ),
        version=settings.api_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        swagger_ui_parameters={"persistAuthorization": True},
    )

    # Setup in order: middleware → exception handlers → routes → openapi
    # Note: Middleware executes in reverse order (last added runs first)
    app.add_middleware(CookieAuthMiddleware)
    app.add_middleware(APIKeyMiddleware)
    _setup_cors(app, settings)
    _setup_request_middleware(app)

    register_exception_handlers(app)

    # Mount static files (CSS, JS, images)
    from app.utils.templates import STATIC_DIR

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Mount auth routes (login, logout) - excluded from cookie auth
    app.include_router(create_auth_router())
    # Mount public routes (require cookie auth) at root
    app.include_router(create_public_router())
    # Mount protected routes (require API key header) under /api prefix
    app.include_router(create_protected_router())

    _setup_openapi(app)

    logger.info("FastAPI application created successfully")
    return app
