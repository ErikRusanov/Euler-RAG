"""FastAPI application factory with production-ready configuration."""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api.router import create_api_router
from app.config import Settings, get_settings
from app.middleware import APIKeyMiddleware
from app.utils.db import close_db, init_db
from app.utils.exception_handlers import register_exception_handlers
from app.utils.s3 import close_s3, init_s3

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle.

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

    try:
        await init_db()
        init_s3()
        logger.info("Application startup complete")
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")
        raise

    yield

    logger.info("Shutting down application...")
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
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[],
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

        public_paths = APIKeyMiddleware.public_paths()
        for path, methods in schema["paths"].items():
            if path not in public_paths:
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
    app.add_middleware(APIKeyMiddleware)
    _setup_cors(app, settings)
    _setup_request_middleware(app)

    register_exception_handlers(app)

    app.include_router(create_api_router())

    _setup_openapi(app)

    logger.info("FastAPI application created successfully")
    return app
