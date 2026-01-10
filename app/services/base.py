"""Base service class with transaction management for database operations."""

import logging
from typing import Any, Generic, List, Optional, TypeVar

from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    DatabaseConnectionError,
    InvalidFilterError,
    RecordNotFoundError,
)
from app.models.base import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseService(Generic[T]):
    """Base service class managing database transactions for model operations.

    This service wraps BaseModel methods and provides automatic transaction
    management:
    - Write operations (create, update, delete) automatically commit
    - Read operations (get_by_id, get_all, find, count) don't commit
    - All errors trigger automatic rollback

    Usage:
        class UserService(BaseService[User]):
            model = User

        service = UserService(db_session)
        user = await service.create(name="John", email="john@example.com")
        # Transaction is automatically committed

    Attributes:
        db: Database session for operations
        model: Model class this service manages
    """

    model: type[T]

    def __init__(self, db: AsyncSession) -> None:
        """Initialize service with database session.

        Args:
            db: Database session for operations
        """
        self.db = db

    async def create(self, **kwargs: Any) -> T:
        """Create a new record and commit transaction.

        Args:
            **kwargs: Model attributes

        Returns:
            Created model instance

        Raises:
            DatabaseConnectionError: If database operation fails
            IntegrityError: If unique constraint is violated
        """
        try:
            instance = await self.model.create(self.db, **kwargs)
            await self.db.commit()
            logger.debug(
                f"Created {self.model.__name__}",
                extra={"model": self.model.__name__, "id": instance.id},
            )
            return instance
        except (IntegrityError, DBAPIError, SQLAlchemyError) as e:
            await self.db.rollback()
            logger.error(
                f"Failed to create {self.model.__name__}",
                extra={"model": self.model.__name__, "error": str(e)},
                exc_info=True,
            )
            if isinstance(e, IntegrityError):
                raise DatabaseConnectionError(
                    f"Integrity constraint violation: {str(e)}"
                ) from e
            raise DatabaseConnectionError(
                f"Database error during create: {str(e)}"
            ) from e

    async def get_by_id(self, record_id: int) -> Optional[T]:
        """Retrieve a record by its primary key ID.

        This is a read operation and does not commit the transaction.

        Args:
            record_id: Primary key ID

        Returns:
            Model instance or None if not found

        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            return await self.model.get_by_id(self.db, record_id)
        except (DBAPIError, SQLAlchemyError) as e:
            logger.error(
                f"Failed to get {self.model.__name__} by id",
                extra={"model": self.model.__name__, "id": record_id, "error": str(e)},
                exc_info=True,
            )
            raise DatabaseConnectionError(f"Database error during get: {str(e)}") from e

    async def get_by_id_or_fail(self, record_id: int) -> T:
        """Retrieve a record by ID or raise exception if not found.

        This is a read operation and does not commit the transaction.

        Args:
            record_id: Primary key ID

        Returns:
            Model instance

        Raises:
            RecordNotFoundError: If record not found
            DatabaseConnectionError: If database operation fails
        """
        try:
            return await self.model.get_by_id_or_fail(self.db, record_id)
        except RecordNotFoundError:
            raise
        except (DBAPIError, SQLAlchemyError) as e:
            logger.error(
                f"Failed to get {self.model.__name__} by id",
                extra={"model": self.model.__name__, "id": record_id, "error": str(e)},
                exc_info=True,
            )
            raise DatabaseConnectionError(f"Database error during get: {str(e)}") from e

    async def get_all(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> List[T]:
        """Retrieve all records with optional pagination.

        This is a read operation and does not commit the transaction.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of model instances

        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            return await self.model.get_all(self.db, limit=limit, offset=offset)
        except (DBAPIError, SQLAlchemyError) as e:
            logger.error(
                f"Failed to get all {self.model.__name__}",
                extra={"model": self.model.__name__, "error": str(e)},
                exc_info=True,
            )
            raise DatabaseConnectionError(
                f"Database error during get_all: {str(e)}"
            ) from e

    async def find(self, **filters: Any) -> List[T]:
        """Find records matching the given filters.

        This is a read operation and does not commit the transaction.

        Args:
            **filters: Field-value pairs to filter by

        Returns:
            List of matching model instances

        Raises:
            InvalidFilterError: If invalid filter key provided
            DatabaseConnectionError: If database operation fails
        """
        try:
            return await self.model.find(self.db, **filters)
        except InvalidFilterError:
            raise
        except (DBAPIError, SQLAlchemyError) as e:
            logger.error(
                f"Failed to find {self.model.__name__}",
                extra={
                    "model": self.model.__name__,
                    "filters": filters,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise DatabaseConnectionError(
                f"Database error during find: {str(e)}"
            ) from e

    async def count(self, **filters: Any) -> int:
        """Count records matching the given filters.

        This is a read operation and does not commit the transaction.

        Args:
            **filters: Field-value pairs to filter by

        Returns:
            Number of matching records

        Raises:
            InvalidFilterError: If invalid filter key provided
            DatabaseConnectionError: If database operation fails
        """
        try:
            return await self.model.count(self.db, **filters)
        except InvalidFilterError:
            raise
        except (DBAPIError, SQLAlchemyError) as e:
            logger.error(
                f"Failed to count {self.model.__name__}",
                extra={
                    "model": self.model.__name__,
                    "filters": filters,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise DatabaseConnectionError(
                f"Database error during count: {str(e)}"
            ) from e

    async def update(self, record_id: int, **kwargs: Any) -> T:
        """Update a record and commit transaction.

        Args:
            record_id: Primary key ID of record to update
            **kwargs: Attributes to update

        Returns:
            Updated model instance

        Raises:
            RecordNotFoundError: If record not found
            InvalidFilterError: If invalid attribute provided
            DatabaseConnectionError: If database operation fails
        """
        try:
            record = await self.model.get_by_id_or_fail(self.db, record_id)
            updated_record = await record.update(self.db, **kwargs)
            await self.db.commit()
            logger.debug(
                f"Updated {self.model.__name__}",
                extra={"model": self.model.__name__, "id": record_id},
            )
            return updated_record
        except (RecordNotFoundError, InvalidFilterError):
            await self.db.rollback()
            raise
        except (IntegrityError, DBAPIError, SQLAlchemyError) as e:
            await self.db.rollback()
            logger.error(
                f"Failed to update {self.model.__name__}",
                extra={
                    "model": self.model.__name__,
                    "id": record_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            if isinstance(e, IntegrityError):
                raise DatabaseConnectionError(
                    f"Integrity constraint violation: {str(e)}"
                ) from e
            raise DatabaseConnectionError(
                f"Database error during update: {str(e)}"
            ) from e

    async def delete(self, record_id: int) -> None:
        """Delete a record and commit transaction.

        Args:
            record_id: Primary key ID of record to delete

        Raises:
            RecordNotFoundError: If record not found
            DatabaseConnectionError: If database operation fails
        """
        try:
            record = await self.model.get_by_id_or_fail(self.db, record_id)
            await record.delete(self.db)
            await self.db.commit()
            logger.debug(
                f"Deleted {self.model.__name__}",
                extra={"model": self.model.__name__, "id": record_id},
            )
        except RecordNotFoundError:
            await self.db.rollback()
            raise
        except (DBAPIError, SQLAlchemyError) as e:
            await self.db.rollback()
            logger.error(
                f"Failed to delete {self.model.__name__}",
                extra={
                    "model": self.model.__name__,
                    "id": record_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise DatabaseConnectionError(
                f"Database error during delete: {str(e)}"
            ) from e
