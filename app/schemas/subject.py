"""Subject schemas for API request/response models."""

from pydantic import BaseModel, Field


class SubjectCreate(BaseModel):
    """Schema for creating a subject.

    Attributes:
        name: Name of the subject.
        semester: Semester number (1-12).
    """

    name: str = Field(..., min_length=1, max_length=255)
    semester: int = Field(..., ge=1, le=12)


class SubjectResponse(BaseModel):
    """Response schema for subject.

    Attributes:
        id: Subject ID.
        name: Subject name.
        semester: Semester number.
    """

    id: int
    name: str
    semester: int

    model_config = {"from_attributes": True}
