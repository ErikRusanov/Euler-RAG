"""Base model class with timestamp tracking."""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.db import Base


class BaseModel(Base):
    """Abstract base class for SQLAlchemy models.

    Provides common functionality for all models:
    - Primary key (id)
    - Timestamps (created_at, updated_at)
    - Helper methods (to_dict, __repr__)

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
