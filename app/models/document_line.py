"""DocumentLine model representing raw Mathpix output line-by-line."""

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from app.models.document import Document

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class DocumentLine(BaseModel):
    """DocumentLine model for storing raw Mathpix OCR output line-by-line.

    Each line represents a single text or math element extracted from a PDF page
    by Mathpix API, with rich metadata for intelligent chunking.

    Attributes:
        document_id: Foreign key to documents table
        page_number: Page number in the PDF (1-indexed)
        line_number: Line number within the page (1-indexed)
        text: Extracted text content (LaTeX for math)
        line_type: Type of line ('text', 'math', 'section_header')
        font_size: Font size in points (nullable)
        is_printed: True if printed text, False if handwritten
        is_handwritten: True if handwritten text, False if printed
        confidence: OCR confidence score 0.0-1.0 (nullable)
        region: JSONB containing position {top_left_x, top_left_y, width, height}
        raw_metadata: JSONB containing additional Mathpix metadata
        created_at: Timestamp when record was created (inherited)
        updated_at: Timestamp when record was last updated (inherited)

    Example:
        line = DocumentLine(
            document_id=1,
            page_number=5,
            line_number=12,
            text="\\int_{0}^{\\infty} e^{-x} dx = 1",
            line_type="math",
            font_size=12,
            is_printed=True,
            is_handwritten=False,
            confidence=0.98,
            region={"top_left_x": 100, "top_left_y": 200, "width": 300, "height": 50}
        )
    """

    __tablename__ = "document_lines"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "page_number",
            "line_number",
            name="uq_document_lines_document_page_line",
        ),
    )

    # Foreign key to document
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Position in document
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Content
    text: Mapped[str] = mapped_column(Text, nullable=False)
    line_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'text', 'math', 'section_header'

    # Mathpix metadata
    font_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_printed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_handwritten: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Position and raw data (JSONB for flexible structure)
    region: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    raw_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Relationship to document (lazy='noload' for optimized queries)
    document: Mapped["Document"] = relationship(
        "Document", lazy="noload", foreign_keys=[document_id]
    )

    def __repr__(self) -> str:
        """String representation of the document line."""
        return (
            f"DocumentLine(id={self.id}, document_id={self.document_id}, "
            f"page={self.page_number}, line={self.line_number}, "
            f"type={self.line_type!r}, text={self.text[:50]!r}...)"
        )
