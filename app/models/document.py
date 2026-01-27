"""Document model representing uploaded files for processing."""

import enum
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class DocumentStatus(str, enum.Enum):
    """Document processing status enumeration.

    Attributes:
        PENDING: Document is waiting to be processed
        UPLOADED: Document has been uploaded to storage
        PROCESSING: Document is currently being processed
        READY: Document has been successfully processed and is ready
        ERROR: Document processing failed with an error
    """

    PENDING = "pending"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class Document(BaseModel):
    """Document model for storing uploaded files and their processing status.

    Represents a document (PDF, etc.) uploaded for processing. Tracks the
    processing status and progress.

    Attributes:
        filename: Original filename of the uploaded document
        s3_key: Unique S3 storage key for the document
        status: Current processing status (enum)
        progress: JSONB field storing processing progress details
        error: Error message if processing failed (nullable)
        created_at: Timestamp when record was created (inherited)
        updated_at: Timestamp when record was last updated (inherited)
        processed_at: Timestamp when processing was completed (nullable)

    Example:
        document = await Document.create(
            db,
            filename="lecture_notes.pdf",
            s3_key="documents/2024/lecture_notes_abc123.pdf",
            status=DocumentStatus.UPLOADED
        )
    """

    __tablename__ = "documents"

    # Document metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(
        String(512), nullable=False, unique=True, index=True
    )

    # Processing status and progress
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False, length=20),
        nullable=False,
        index=True,
        default=DocumentStatus.UPLOADED,
    )
    progress: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default={"page": 0, "total": 0}
    )

    # Error tracking
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    # Processing timestamp
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    def __repr__(self) -> str:
        """String representation of the document."""
        return (
            f"Document(id={self.id}, filename={self.filename!r}, "
            f"status={self.status.value}, s3_key={self.s3_key!r})"
        )
