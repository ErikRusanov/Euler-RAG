"""Document schemas for API request/response models."""

from typing import Any

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
