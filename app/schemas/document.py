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
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None
    url: Optional[str] = None

    model_config = {"from_attributes": True}


class DocumentUpdate(BaseModel):
    """Schema for updating document fields."""

    filename: Optional[str] = None
    status: Optional[DocumentStatus] = None
    progress: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    processed_at: Optional[datetime] = None
