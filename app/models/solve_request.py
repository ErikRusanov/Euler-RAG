"""SolveRequest model representing question solving requests."""

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SolveRequestStatus(str, enum.Enum):
    """Solve request processing status enumeration.

    Attributes:
        PENDING: Request is waiting to be processed
        PROCESSING: Request is currently being processed
        READY: Request has been successfully processed
        ERROR: Request processing failed with an error
    """

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class SolveRequest(BaseModel):
    """SolveRequest model for storing question solving requests.

    Represents a user's question that needs to be answered using RAG.
    Tracks processing status and generated answers.

    Attributes:
        question: The question text from the user
        subject_filter: Optional subject filter for context search
        answer: Generated answer text (nullable)
        chunks_used: JSONB field storing retrieved chunks information
        used_rag: Boolean flag indicating if RAG was used
        verified: Boolean flag indicating if answer was verified
        status: Current processing status (enum)
        error: Error message if processing failed (nullable)
        created_at: Timestamp when record was created (inherited)
        updated_at: Timestamp when record was last updated (inherited)
        processed_at: Timestamp when processing was completed (nullable)

    Example:
        solve_request = await SolveRequest.create(
            db,
            question="What is calculus?",
            subject_filter="Mathematics",
            status=SolveRequestStatus.PENDING
        )
    """

    __tablename__ = "solve_requests"

    # Request content
    question: Mapped[str] = mapped_column(Text, nullable=False)
    subject_filter: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default=None, index=True
    )

    # Answer and context
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    chunks_used: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB, nullable=True, default=None
    )

    # Processing flags
    used_rag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Status tracking
    status: Mapped[SolveRequestStatus] = mapped_column(
        Enum(SolveRequestStatus, native_enum=False, length=20),
        nullable=False,
        index=True,
        default=SolveRequestStatus.PENDING,
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    # Processing timestamp
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    def __repr__(self) -> str:
        """String representation of the solve request."""
        question_preview = (
            self.question[:50] + "..." if len(self.question) > 50 else self.question
        )
        return (
            f"SolveRequest(id={self.id}, status={self.status.value}, "
            f"question={question_preview!r})"
        )
