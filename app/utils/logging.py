"""Logging configuration for the application.

This module provides structured logging configuration for production-ready
applications with proper formatting and log levels.
"""

import logging
import sys
from typing import Any, Dict

from app.config import get_settings


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging with JSON-like output.

    Includes additional context fields like timestamp, level, module, etc.
    """

    # Standard LogRecord attributes that should not be included as extra fields
    _STANDARD_ATTRS = {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "stack_info",
        "getMessage",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structured information.

        Args:
            record: Log record to format

        Returns:
            Formatted log string
        """
        # Base log data
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields (user-provided attributes not in standard LogRecord)
        for key, value in record.__dict__.items():
            if key not in self._STANDARD_ATTRS and not key.startswith("_"):
                log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Format as key=value pairs for easy parsing
        formatted_parts = [f'{key}="{value}"' for key, value in log_data.items()]
        return " ".join(formatted_parts)


def setup_logging() -> None:
    """Setup application logging configuration.

    Configures root logger with appropriate handlers, formatters,
    and log levels based on application settings.
    """
    settings = get_settings()

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.log_level)

    # Use structured formatter in production, simple formatter in development
    if settings.is_production:
        formatter = StructuredFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Configure third-party loggers to be less verbose
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.INFO)

    # Log configuration
    root_logger.info(
        "Logging configured",
        extra={
            "log_level": settings.log_level,
            "environment": settings.environment,
        },
    )


def get_logger(name: str) -> logging.Logger:
    """Get logger instance for a specific module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Application started")
    """
    return logging.getLogger(name)
