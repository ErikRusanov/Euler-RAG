"""Teacher schemas for API request/response models."""

from pydantic import BaseModel, Field


class TeacherCreate(BaseModel):
    """Schema for creating a teacher.

    Attributes:
        name: Name of the teacher.
    """

    name: str = Field(..., min_length=1, max_length=255)


class TeacherResponse(BaseModel):
    """Response schema for teacher.

    Attributes:
        id: Teacher ID.
        name: Teacher name.
    """

    id: int
    name: str

    model_config = {"from_attributes": True}
