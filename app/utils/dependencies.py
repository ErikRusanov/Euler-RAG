"""Dependency injection functions for FastAPI routes.

Uses descriptor pattern to automatically create dependency functions
for all services, eliminating code duplication.
"""

from typing import Any, Type, TypeVar

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.document_service import DocumentService
from app.utils.db import get_db_session

T = TypeVar("T")


class ServiceDependency:
    """Descriptor that creates a dependency injection function for a service.

    Caches the dependency function to ensure the same function object is returned
    each time, enabling proper use of FastAPI's dependency_overrides.
    """

    def __init__(self, service_class: Type[T]) -> None:
        """Initialize service dependency descriptor.

        Args:
            service_class: The service class to create instances of.
        """
        self.service_class = service_class
        self._cached_func: Any = None

    def __get__(self, instance: Any, owner: type) -> Any:
        """Create and return cached dependency function when accessed."""
        if self._cached_func is None:

            def dependency_func(
                db: AsyncSession = Depends(get_db_session),
            ) -> T:
                """Get service instance for dependency injection."""
                return self.service_class(db)

            self._cached_func = dependency_func
        return self._cached_func


class ServiceDependencies:
    """Container for all service dependency injection functions."""

    document = ServiceDependency(DocumentService)


# Create singleton instance for easy access
dependencies = ServiceDependencies()
