"""Integration tests for model-specific constraints and behavior.

Tests unique constraints and relationships that are specific to each model.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.solve_request import SolveRequest, SolveRequestStatus
from app.models.subject import Subject
from app.models.teacher import Teacher


class TestSubjectConstraints:
    """Tests for Subject model unique constraints."""

    @pytest.mark.asyncio
    async def test_unique_name_semester_constraint(self, db_session: AsyncSession):
        """Duplicate (name, semester) pair raises error."""
        subject = Subject(name="Math", semester=1)
        db_session.add(subject)
        await db_session.flush()
        await db_session.commit()

        with pytest.raises(IntegrityError):
            duplicate = Subject(name="Math", semester=1)
            db_session.add(duplicate)
            await db_session.flush()
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_same_name_different_semester_allowed(self, db_session: AsyncSession):
        """Same name in different semesters is allowed."""
        subject1 = Subject(name="Physics", semester=1)
        subject2 = Subject(name="Physics", semester=2)
        db_session.add(subject1)
        db_session.add(subject2)
        await db_session.flush()
        await db_session.commit()

        assert subject1.id != subject2.id
        assert subject1.semester != subject2.semester


class TestDocumentConstraints:
    """Tests for Document model unique constraints."""

    @pytest.mark.asyncio
    async def test_s3_key_must_be_unique(self, db_session: AsyncSession):
        """Duplicate s3_key raises error."""
        subject = Subject(name="Math", semester=1)
        teacher = Teacher(name="Dr. Smith")
        db_session.add(subject)
        db_session.add(teacher)
        await db_session.flush()
        await db_session.commit()

        doc1 = Document(
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="doc.pdf",
            s3_key="documents/unique.pdf",
            status=DocumentStatus.UPLOADED,
        )
        db_session.add(doc1)
        await db_session.flush()
        await db_session.commit()

        with pytest.raises(IntegrityError):
            doc2 = Document(
                subject_id=subject.id,
                teacher_id=teacher.id,
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
        subject = Subject(name="Physics", semester=1)
        teacher = Teacher(name="Dr. Johnson")
        db_session.add(subject)
        db_session.add(teacher)
        await db_session.flush()
        await db_session.commit()

        progress = {"pages": 10, "chunks": 25}
        doc = Document(
            subject_id=subject.id,
            teacher_id=teacher.id,
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


class TestTeacherModel:
    """Tests for Teacher model behavior."""

    @pytest.mark.asyncio
    async def test_duplicate_names_allowed(self, db_session: AsyncSession):
        """Multiple teachers can have the same name."""
        teacher1 = Teacher(name="Dr. Smith")
        teacher2 = Teacher(name="Dr. Smith")
        db_session.add(teacher1)
        db_session.add(teacher2)
        await db_session.flush()
        await db_session.commit()

        assert teacher1.id != teacher2.id
        assert teacher1.name == teacher2.name
