"""Centralized exception handlers for FastAPI application."""

import logging
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import (
    DatabaseConnectionError,
    InvalidFileTypeError,
    ModelError,
    RecordNotFoundError,
    RelatedRecordNotFoundError,
    S3OperationError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExceptionConfig:
    """Configuration for exception handler behavior."""

    status_code: int
    error_name: str
    log_level: str = "warning"
    include_detail: bool = True


# Exception type to configuration mapping
EXCEPTION_CONFIGS: dict[type[Exception], ExceptionConfig] = {
    RecordNotFoundError: ExceptionConfig(
        status_code=status.HTTP_404_NOT_FOUND,
        error_name="Not Found",
    ),
    RelatedRecordNotFoundError: ExceptionConfig(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_name="Bad Request",
    ),
    DatabaseConnectionError: ExceptionConfig(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        error_name="Service Unavailable",
        log_level="error",
        include_detail=False,
    ),
    ModelError: ExceptionConfig(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_name="Bad Request",
        log_level="error",
    ),
    InvalidFileTypeError: ExceptionConfig(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_name="Invalid File Type",
    ),
    S3OperationError: ExceptionConfig(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_name="Storage Error",
        log_level="error",
        include_detail=False,
    ),
}


def _log_exception(exc: Exception, config: ExceptionConfig) -> None:
    """Log exception with appropriate level."""
    log_func: Callable[..., None] = getattr(logger, config.log_level)
    log_func(f"{type(exc).__name__}: {exc}")


def _build_response_content(exc: Exception, config: ExceptionConfig) -> dict[str, Any]:
    """Build response content based on exception type."""
    content: dict[str, Any] = {"error": config.error_name}

    # Add message based on config and exception type
    if isinstance(exc, DatabaseConnectionError):
        content["message"] = "Database connection error. Please try again later."
    elif isinstance(exc, S3OperationError):
        content["message"] = "Failed to process file in storage"
    elif config.include_detail:
        content["message"] = str(exc)

    # Add exception-specific attributes
    if isinstance(exc, RecordNotFoundError):
        content["model"] = exc.model_name
        content["record_id"] = exc.record_id
    elif isinstance(exc, RelatedRecordNotFoundError):
        content["field"] = exc.field
        content["record_id"] = exc.record_id
    elif isinstance(exc, InvalidFileTypeError):
        content["allowed_types"] = exc.allowed_types
        content["received_type"] = exc.received_type

    return content


def _create_handler(
    config: ExceptionConfig,
) -> Callable[[Request, Exception], JSONResponse]:
    """Create exception handler function for given config."""

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        _log_exception(exc, config)
        content = _build_response_content(exc, config)
        return JSONResponse(status_code=config.status_code, content=content)

    return handler


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


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


async def not_found_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> Response:
    """Handle 404 Not Found with content negotiation.

    Returns HTML template for browsers, JSON for API clients.

    Args:
        request: FastAPI request object.
        exc: HTTP exception.

    Returns:
        TemplateResponse or JSONResponse based on Accept header.
    """
    from app.utils.templates import templates

    logger.warning(f"404 Not Found: {request.url.path}")

    accept_header = request.headers.get("accept", "")

    if "text/html" in accept_header:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "Not Found",
            "message": f"The requested resource was not found: {request.url.path}",
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application.

    Args:
        app: FastAPI application instance.
    """
    # Register configured exception handlers
    for exc_type, config in EXCEPTION_CONFIGS.items():
        app.add_exception_handler(exc_type, _create_handler(config))

    # Register special handlers
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(404, not_found_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
