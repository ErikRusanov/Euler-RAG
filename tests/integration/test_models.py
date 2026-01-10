"""Integration tests for model-specific constraints and behavior.

Tests unique constraints and relationships that are specific to each model.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DatabaseConnectionError
from app.models.document import Document, DocumentStatus
from app.models.solve_request import SolveRequest, SolveRequestStatus
from app.models.subject import Subject
from app.models.teacher import Teacher


class TestSubjectConstraints:
    """Tests for Subject model unique constraints."""

    @pytest.mark.asyncio
    async def test_unique_name_semester_constraint(self, db_session: AsyncSession):
        """Duplicate (name, semester) pair raises error."""
        await Subject.create(db_session, name="Math", semester=1)
        await db_session.commit()

        with pytest.raises(DatabaseConnectionError):
            await Subject.create(db_session, name="Math", semester=1)
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_same_name_different_semester_allowed(self, db_session: AsyncSession):
        """Same name in different semesters is allowed."""
        subject1 = await Subject.create(db_session, name="Physics", semester=1)
        subject2 = await Subject.create(db_session, name="Physics", semester=2)
        await db_session.commit()

        assert subject1.id != subject2.id
        assert subject1.semester != subject2.semester


class TestDocumentConstraints:
    """Tests for Document model unique constraints."""

    @pytest.mark.asyncio
    async def test_s3_key_must_be_unique(self, db_session: AsyncSession):
        """Duplicate s3_key raises error."""
        subject = await Subject.create(db_session, name="Math", semester=1)
        teacher = await Teacher.create(db_session, name="Dr. Smith")
        await db_session.commit()

        await Document.create(
            db_session,
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="doc.pdf",
            s3_key="documents/unique.pdf",
            status=DocumentStatus.UPLOADED,
        )
        await db_session.commit()

        with pytest.raises(DatabaseConnectionError):
            await Document.create(
                db_session,
                subject_id=subject.id,
                teacher_id=teacher.id,
                filename="other.pdf",
                s3_key="documents/unique.pdf",
                status=DocumentStatus.UPLOADED,
            )
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_stores_jsonb_progress(self, db_session: AsyncSession):
        """Document stores JSONB progress field correctly."""
        subject = await Subject.create(db_session, name="Physics", semester=1)
        teacher = await Teacher.create(db_session, name="Dr. Johnson")
        await db_session.commit()

        progress = {"pages": 10, "chunks": 25}
        doc = await Document.create(
            db_session,
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="doc.pdf",
            s3_key="documents/doc.pdf",
            status=DocumentStatus.PROCESSING,
            progress=progress,
        )
        await db_session.commit()

        found = await Document.get_by_id(db_session, doc.id)
        assert found.progress == progress
        assert found.progress["pages"] == 10


class TestSolveRequestModel:
    """Tests for SolveRequest model behavior."""

    @pytest.mark.asyncio
    async def test_stores_jsonb_chunks_used(self, db_session: AsyncSession):
        """SolveRequest stores JSONB chunks_used field correctly."""
        chunks = [{"chunk_id": "abc", "text": "Example", "score": 0.95}]

        request = await SolveRequest.create(
            db_session,
            question="What is X?",
            answer="X is...",
            chunks_used=chunks,
            used_rag=True,
            status=SolveRequestStatus.READY,
        )
        await db_session.commit()

        found = await SolveRequest.get_by_id(db_session, request.id)
        assert found.chunks_used == chunks
        assert found.chunks_used[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_default_flags(self, db_session: AsyncSession):
        """SolveRequest has correct default values for flags."""
        request = await SolveRequest.create(
            db_session,
            question="Test?",
            status=SolveRequestStatus.PENDING,
        )
        await db_session.commit()

        assert request.used_rag is False
        assert request.verified is False
        assert request.answer is None


class TestTeacherModel:
    """Tests for Teacher model behavior."""

    @pytest.mark.asyncio
    async def test_duplicate_names_allowed(self, db_session: AsyncSession):
        """Multiple teachers can have the same name."""
        teacher1 = await Teacher.create(db_session, name="Dr. Smith")
        teacher2 = await Teacher.create(db_session, name="Dr. Smith")
        await db_session.commit()

        assert teacher1.id != teacher2.id
        assert teacher1.name == teacher2.name
