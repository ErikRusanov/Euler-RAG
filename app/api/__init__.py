"""API endpoints package."""

from app.api.router import (
    create_auth_router,
    create_protected_router,
    create_public_router,
)

__all__ = ["create_auth_router", "create_protected_router", "create_public_router"]
