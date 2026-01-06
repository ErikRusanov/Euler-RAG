"""Base model class with CRUD operations and timestamp tracking."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlalchemy import DateTime, Integer, func, select
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.models.exceptions import (
    DatabaseConnectionError,
    InvalidFilterError,
    RecordNotFoundError,
)
from app.utils.db import Base

T = TypeVar("T", bound="BaseModel")


class BaseModel(Base):
    """Abstract base class with async CRUD operations for SQLAlchemy models.

    Provides common functionality for all models:
    - Primary key (id)
    - Timestamps (created_at, updated_at)
    - CRUD operations (create, read, update, delete)
    - Query helpers

    Usage:
        class User(BaseModel):
            __tablename__ = "users"

            name: Mapped[str] = mapped_column(String(100))
            email: Mapped[str] = mapped_column(String(100), unique=True)
    """

    __abstract__ = True  # This is an abstract base class

    # Primary key - all models will have an id column
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Timestamps - automatically managed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @classmethod
    async def create(cls: Type[T], db: AsyncSession, **kwargs: Any) -> T:
        """Create a new record in the database.

        Args:
            db: Database session
            **kwargs: Model attributes

        Returns:
            Created model instance

        Raises:
            DatabaseConnectionError: If database operation fails
            IntegrityError: If unique constraint is violated
        """
        try:
            instance = cls(**kwargs)
            db.add(instance)
            await db.flush()  # Flush to get the ID without committing
            await db.refresh(instance)  # Refresh to get server defaults
            return instance
        except IntegrityError as e:
            await db.rollback()
            raise DatabaseConnectionError(f"Integrity constraint violation: {str(e)}")
        except DBAPIError as e:
            await db.rollback()
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        except SQLAlchemyError as e:
            await db.rollback()
            raise DatabaseConnectionError(f"Database error during create: {str(e)}")

    @classmethod
    async def get_by_id(cls: Type[T], db: AsyncSession, record_id: int) -> Optional[T]:
        """Retrieve a record by its primary key ID.

        Args:
            db: Database session
            record_id: Primary key ID

        Returns:
            Model instance or None if not found

        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            result = await db.execute(select(cls).where(cls.id == record_id))
            return result.scalar_one_or_none()
        except DBAPIError as e:
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(f"Database error during get: {str(e)}")

    @classmethod
    async def get_by_id_or_fail(cls: Type[T], db: AsyncSession, record_id: int) -> T:
        """Retrieve a record by ID or raise exception if not found.

        Args:
            db: Database session
            record_id: Primary key ID

        Returns:
            Model instance

        Raises:
            RecordNotFoundError: If record not found
            DatabaseConnectionError: If database operation fails
        """
        record = await cls.get_by_id(db, record_id)
        if record is None:
            raise RecordNotFoundError(cls.__name__, record_id)
        return record

    @classmethod
    async def get_all(
        cls: Type[T],
        db: AsyncSession,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[T]:
        """Retrieve all records from the table with optional pagination.

        Args:
            db: Database session
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of model instances

        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            query = select(cls)
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())
        except DBAPIError as e:
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(f"Database error during get_all: {str(e)}")

    @classmethod
    async def find(cls: Type[T], db: AsyncSession, **filters: Any) -> List[T]:
        """Find records matching the given filters.

        Args:
            db: Database session
            **filters: Field-value pairs to filter by

        Returns:
            List of matching model instances

        Raises:
            InvalidFilterError: If invalid filter key provided
            DatabaseConnectionError: If database operation fails
        """
        try:
            query = select(cls)
            for key, value in filters.items():
                if not hasattr(cls, key):
                    raise InvalidFilterError(
                        f"Invalid filter key '{key}' for model {cls.__name__}"
                    )
                query = query.where(getattr(cls, key) == value)
            result = await db.execute(query)
            return list(result.scalars().all())
        except InvalidFilterError:
            raise
        except DBAPIError as e:
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(f"Database error during find: {str(e)}")

    @classmethod
    async def count(cls: Type[T], db: AsyncSession, **filters: Any) -> int:
        """Count records matching the given filters.

        Args:
            db: Database session
            **filters: Field-value pairs to filter by

        Returns:
            Number of matching records

        Raises:
            InvalidFilterError: If invalid filter key provided
            DatabaseConnectionError: If database operation fails
        """
        try:
            query = select(func.count(cls.id))
            for key, value in filters.items():
                if not hasattr(cls, key):
                    raise InvalidFilterError(
                        f"Invalid filter key '{key}' for model {cls.__name__}"
                    )
                query = query.where(getattr(cls, key) == value)
            result = await db.execute(query)
            return result.scalar_one()
        except InvalidFilterError:
            raise
        except DBAPIError as e:
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(f"Database error during count: {str(e)}")

    async def update(self: T, db: AsyncSession, **kwargs: Any) -> T:
        """Update the current record with new values.

        Args:
            db: Database session
            **kwargs: Attributes to update

        Returns:
            Updated model instance

        Raises:
            InvalidFilterError: If invalid attribute provided
            DatabaseConnectionError: If database operation fails
        """
        try:
            for key, value in kwargs.items():
                if not hasattr(self, key):
                    raise InvalidFilterError(
                        f"Invalid attribute '{key}' for model {self.__class__.__name__}"
                    )
                setattr(self, key, value)
            await db.flush()
            await db.refresh(self)
            return self
        except InvalidFilterError:
            raise
        except DBAPIError as e:
            await db.rollback()
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        except SQLAlchemyError as e:
            await db.rollback()
            raise DatabaseConnectionError(f"Database error during update: {str(e)}")

    async def delete(self: T, db: AsyncSession) -> None:
        """Delete the current record from the database.

        Args:
            db: Database session

        Raises:
            DatabaseConnectionError: If database operation fails
        """
        try:
            await db.delete(self)
            await db.flush()
        except DBAPIError as e:
            await db.rollback()
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        except SQLAlchemyError as e:
            await db.rollback()
            raise DatabaseConnectionError(f"Database error during delete: {str(e)}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary.

        Returns:
            Dictionary representation of the model
        """
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }

    def __repr__(self) -> str:
        """String representation of the model."""
        attrs = ", ".join(
            f"{key}={repr(value)}"
            for key, value in self.to_dict().items()
            if key != "id"
        )
        return f"{self.__class__.__name__}(id={self.id}, {attrs})"
