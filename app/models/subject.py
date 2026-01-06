"""Subject model representing academic subjects."""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Subject(BaseModel):
    """Subject model for storing academic subjects with semester information.

    Represents an academic subject taught in a specific semester.
    Each combination of name and semester must be unique.

    Attributes:
        name: Name of the subject (e.g., "Mathematics", "Physics")
        semester: Semester number when the subject is taught
        created_at: Timestamp when record was created (inherited)
        updated_at: Timestamp when record was last updated (inherited)

    Example:
        subject = await Subject.create(
            db,
            name="Linear Algebra",
            semester=3
        )
    """

    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    semester: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Unique constraint on (name, semester) combination
    __table_args__ = (
        UniqueConstraint("name", "semester", name="uq_subject_name_semester"),
    )

    def __repr__(self) -> str:
        """String representation of the subject."""
        return f"Subject(id={self.id}, name={self.name!r}, semester={self.semester})"
