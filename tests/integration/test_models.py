"""Integration tests for model-specific constraints and behavior.

Tests unique constraints and relationships that are specific to each model.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.solve_request import SolveRequest, SolveRequestStatus


class TestDocumentConstraints:
    """Tests for Document model unique constraints."""

    @pytest.mark.asyncio
    async def test_s3_key_must_be_unique(self, db_session: AsyncSession):
        """Duplicate s3_key raises error."""
        doc1 = Document(
            filename="doc.pdf",
            s3_key="documents/unique.pdf",
            status=DocumentStatus.UPLOADED,
        )
        db_session.add(doc1)
        await db_session.flush()
        await db_session.commit()

        with pytest.raises(IntegrityError):
            doc2 = Document(
                filename="other.pdf",
                s3_key="documents/unique.pdf",
                status=DocumentStatus.UPLOADED,
            )
            db_session.add(doc2)
            await db_session.flush()
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_stores_jsonb_progress(self, db_session: AsyncSession):
        """Document stores JSONB progress field correctly."""
        progress = {"pages": 10, "chunks": 25}
        doc = Document(
            filename="doc.pdf",
            s3_key="documents/doc.pdf",
            status=DocumentStatus.PROCESSING,
            progress=progress,
        )
        db_session.add(doc)
        await db_session.flush()
        await db_session.commit()

        result = await db_session.execute(select(Document).where(Document.id == doc.id))
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.progress == progress
        assert found.progress["pages"] == 10


class TestSolveRequestModel:
    """Tests for SolveRequest model behavior."""

    @pytest.mark.asyncio
    async def test_stores_jsonb_chunks_used(self, db_session: AsyncSession):
        """SolveRequest stores JSONB chunks_used field correctly."""
        chunks = [{"chunk_id": "abc", "text": "Example", "score": 0.95}]

        request = SolveRequest(
            question="What is X?",
            answer="X is...",
            chunks_used=chunks,
            used_rag=True,
            status=SolveRequestStatus.READY,
        )
        db_session.add(request)
        await db_session.flush()
        await db_session.commit()

        result = await db_session.execute(
            select(SolveRequest).where(SolveRequest.id == request.id)
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.chunks_used == chunks
        assert found.chunks_used[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_default_flags(self, db_session: AsyncSession):
        """SolveRequest has correct default values for flags."""
        request = SolveRequest(
            question="Test?",
            status=SolveRequestStatus.PENDING,
        )
        db_session.add(request)
        await db_session.flush()
        await db_session.refresh(request)
        await db_session.commit()

        assert request.used_rag is False
        assert request.verified is False
        assert request.answer is None
