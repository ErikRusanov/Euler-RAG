"""Base model class with CRUD operations."""

from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exceptions import (
    DatabaseConnectionError,
    InvalidFilterError,
    RecordNotFoundError,
)

T = TypeVar("T", bound="BaseModel")


class BaseModel:
    """Abstract base class with async CRUD operations for SQLAlchemy models."""

    @classmethod
    async def create(cls: Type[T], db: AsyncSession, **kwargs: Any) -> T:
        """Create a new record in the database."""
        try:
            instance = cls(**kwargs)
            db.add(instance)
            await db.flush()
            return instance
        except DBAPIError as e:
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(f"Database error during create: {str(e)}")

    @classmethod
    async def get_by_id(cls: Type[T], db: AsyncSession, record_id: int) -> Optional[T]:
        """Retrieve a record by its primary key ID."""
        try:
            result = await db.execute(select(cls).where(cls.id == record_id))
            return result.scalar_one_or_none()
        except DBAPIError as e:
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(f"Database error during get: {str(e)}")

    @classmethod
    async def get_by_id_or_fail(cls: Type[T], db: AsyncSession, record_id: int) -> T:
        """Retrieve a record by ID or raise exception if not found."""
        record = await cls.get_by_id(db, record_id)
        if record is None:
            raise RecordNotFoundError(cls.__name__, record_id)
        return record

    @classmethod
    async def get_all(
        cls: Type[T], db: AsyncSession, limit: Optional[int] = None
    ) -> List[T]:
        """Retrieve all records from the table."""
        try:
            query = select(cls)
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
        """Find records matching the given filters."""
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

    async def update(self: T, db: AsyncSession, **kwargs: Any) -> T:
        """Update the current record with new values."""
        try:
            for key, value in kwargs.items():
                if not hasattr(self, key):
                    raise InvalidFilterError(
                        f"Invalid attribute '{key}' for model {self.__class__.__name__}"
                    )
                setattr(self, key, value)
            await db.flush()
            return self
        except InvalidFilterError:
            raise
        except DBAPIError as e:
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(f"Database error during update: {str(e)}")

    async def delete(self: T, db: AsyncSession) -> None:
        """Delete the current record from the database."""
        try:
            await db.delete(self)
            await db.flush()
        except DBAPIError as e:
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(f"Database error during delete: {str(e)}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
