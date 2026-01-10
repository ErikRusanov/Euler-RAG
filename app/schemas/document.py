"""Document schemas for API request/response models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    """Response schema for document."""

    id: int
    filename: str
    s3_key: str
    status: DocumentStatus
    progress: dict[str, Any]

    model_config = {"from_attributes": True}


class DocumentUpdate(BaseModel):
    """Schema for updating document fields."""

    subject_id: Optional[int] = None
    teacher_id: Optional[int] = None
    filename: Optional[str] = None
    status: Optional[DocumentStatus] = None
    progress: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    processed_at: Optional[datetime] = None
