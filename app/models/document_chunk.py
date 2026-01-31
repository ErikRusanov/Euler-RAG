"""DocumentChunk model representing logical chunks for embedding."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.document_line import DocumentLine

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.utils.vector_types import Vector


class DocumentChunk(BaseModel):
    """DocumentChunk model for storing logical chunks for embedding.

    Represents a semantically coherent chunk of text from a document,
    created by grouping document lines based on structure (theorems, proofs, etc).
    These chunks are used for RAG embeddings in Qdrant.

    Attributes:
        document_id: Foreign key to documents table
        text: Full text content of the chunk
        chunk_index: Sequential index within the document (0-indexed)
        start_page: First page number included in this chunk
        end_page: Last page number included in this chunk
        start_line_id: Foreign key to first document_line in chunk (nullable)
        end_line_id: Foreign key to last document_line in chunk (nullable)
        chunk_type: Classification of chunk content (
            'theorem', 'proof', 'definition', 'example', 'mixed'
        )
        section_title: Title of the section this chunk belongs to (nullable)
        qdrant_point_id: UUID of the corresponding point in Qdrant (nullable)
        token_count: Number of tokens in the chunk (nullable)
        created_at: Timestamp when record was created (inherited)
        updated_at: Timestamp when record was last updated (inherited)

    Example:
        chunk = DocumentChunk(
            document_id=1,
            text="Theorem 1: For all real numbers x...",
            chunk_index=0,
            start_page=5,
            end_page=5,
            start_line_id=42,
            end_line_id=58,
            chunk_type="theorem",
            section_title="Linear Algebra",
            token_count=245
        )
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_chunk_index",
        ),
    )

    # Foreign key to document
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Content
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Source tracking
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False)
    start_line_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("document_lines.id"), nullable=True
    )
    end_line_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("document_lines.id"), nullable=True
    )

    # Classification
    chunk_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )
    section_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # For future embedding
    qdrant_point_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, unique=True
    )
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Vector embedding for RAG
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(1024), nullable=True
    )

    # Relationships (lazy='noload' for optimized queries)
    document: Mapped["Document"] = relationship(
        "Document", lazy="noload", foreign_keys=[document_id]
    )
    start_line: Mapped[Optional["DocumentLine"]] = relationship(
        "DocumentLine",
        lazy="noload",
        foreign_keys=[start_line_id],
    )
    end_line: Mapped[Optional["DocumentLine"]] = relationship(
        "DocumentLine",
        lazy="noload",
        foreign_keys=[end_line_id],
    )

    def __repr__(self) -> str:
        """String representation of the document chunk."""
        return (
            f"DocumentChunk(id={self.id}, document_id={self.document_id}, "
            f"chunk_index={self.chunk_index}, type={self.chunk_type!r}, "
            f"pages={self.start_page}-{self.end_page}, "
            f"text={self.text[:50]!r}...)"
        )
