"""Teacher model representing academic instructors."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Teacher(BaseModel):
    """Teacher model for storing academic instructors.

    Represents a teacher/instructor who teaches courses.
    Multiple teachers can have the same name (no unique constraint).

    Attributes:
        name: Full name of the teacher (e.g., "Dr. Smith", "Professor Johnson")
        created_at: Timestamp when record was created (inherited)
        updated_at: Timestamp when record was last updated (inherited)

    Example:
        teacher = await Teacher.create(
            db,
            name="Dr. Alexander Smith"
        )
    """

    __tablename__ = "teachers"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    def __repr__(self) -> str:
        """String representation of the teacher."""
        return f"Teacher(id={self.id}, name={self.name!r})"
