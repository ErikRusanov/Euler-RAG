"""Middleware components for the application."""

from app.middleware.auth import APIKeyMiddleware

__all__ = ["APIKeyMiddleware"]
