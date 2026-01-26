"""Integration tests for DocumentChunk model."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_line import DocumentLine
from app.models.subject import Subject
from app.models.teacher import Teacher


class TestDocumentChunkConstraints:
    """Tests for DocumentChunk model unique constraints."""

    @pytest.mark.asyncio
    async def test_unique_document_chunk_index_constraint(
        self, db_session: AsyncSession
    ):
        """Duplicate (document_id, chunk_index) raises error."""
        subject = Subject(name="Math", semester=1)
        teacher = Teacher(name="Dr. Smith")
        db_session.add(subject)
        db_session.add(teacher)
        await db_session.flush()

        document = Document(
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="test.pdf",
            s3_key="documents/test.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        # Create first chunk
        chunk1 = DocumentChunk(
            document_id=document.id,
            text="First chunk",
            chunk_index=0,
            start_page=1,
            end_page=1,
        )
        db_session.add(chunk1)
        await db_session.flush()
        await db_session.commit()

        # Attempt to create duplicate chunk with same index
        with pytest.raises(IntegrityError):
            chunk2 = DocumentChunk(
                document_id=document.id,
                text="Different text",
                chunk_index=0,
                start_page=2,
                end_page=2,
            )
            db_session.add(chunk2)
            await db_session.flush()
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_different_chunk_indices_allowed(self, db_session: AsyncSession):
        """Different chunk indices for same document are allowed."""
        subject = Subject(name="Physics", semester=1)
        teacher = Teacher(name="Dr. Johnson")
        db_session.add(subject)
        db_session.add(teacher)
        await db_session.flush()

        document = Document(
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="test.pdf",
            s3_key="documents/test2.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        # Create multiple chunks with different indices
        chunk1 = DocumentChunk(
            document_id=document.id,
            text="Chunk 0",
            chunk_index=0,
            start_page=1,
            end_page=1,
        )
        chunk2 = DocumentChunk(
            document_id=document.id,
            text="Chunk 1",
            chunk_index=1,
            start_page=2,
            end_page=2,
        )
        db_session.add(chunk1)
        db_session.add(chunk2)
        await db_session.flush()
        await db_session.commit()

        assert chunk1.id != chunk2.id
        assert chunk1.chunk_index != chunk2.chunk_index

    @pytest.mark.asyncio
    async def test_cascade_delete_on_document(self, db_session: AsyncSession):
        """Deleting document cascades to delete all its chunks."""
        subject = Subject(name="Chemistry", semester=2)
        teacher = Teacher(name="Dr. Brown")
        db_session.add(subject)
        db_session.add(teacher)
        await db_session.flush()

        document = Document(
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="test.pdf",
            s3_key="documents/test3.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        # Create multiple chunks
        chunk1 = DocumentChunk(
            document_id=document.id,
            text="Chunk 0",
            chunk_index=0,
            start_page=1,
            end_page=1,
        )
        chunk2 = DocumentChunk(
            document_id=document.id,
            text="Chunk 1",
            chunk_index=1,
            start_page=2,
            end_page=2,
        )
        db_session.add(chunk1)
        db_session.add(chunk2)
        await db_session.flush()
        await db_session.commit()

        chunk1_id = chunk1.id
        chunk2_id = chunk2.id

        # Delete document
        await db_session.delete(document)
        await db_session.commit()

        # Verify chunks are deleted
        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.id.in_([chunk1_id, chunk2_id]))
        )
        remaining_chunks = result.scalars().all()
        assert len(remaining_chunks) == 0


class TestDocumentChunkLineReferences:
    """Tests for DocumentChunk foreign key relationships to DocumentLine."""

    @pytest.mark.asyncio
    async def test_references_document_lines(self, db_session: AsyncSession):
        """DocumentChunk can reference start and end document lines."""
        subject = Subject(name="Math", semester=1)
        teacher = Teacher(name="Dr. Smith")
        db_session.add(subject)
        db_session.add(teacher)
        await db_session.flush()

        document = Document(
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="test.pdf",
            s3_key="documents/test4.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        # Create document lines
        line1 = DocumentLine(
            document_id=document.id,
            page_number=1,
            line_number=1,
            text="Line 1",
            line_type="text",
        )
        line2 = DocumentLine(
            document_id=document.id,
            page_number=1,
            line_number=5,
            text="Line 5",
            line_type="text",
        )
        db_session.add(line1)
        db_session.add(line2)
        await db_session.flush()
        await db_session.commit()

        # Create chunk referencing these lines
        chunk = DocumentChunk(
            document_id=document.id,
            text="Lines 1-5",
            chunk_index=0,
            start_page=1,
            end_page=1,
            start_line_id=line1.id,
            end_line_id=line2.id,
        )
        db_session.add(chunk)
        await db_session.flush()
        await db_session.commit()

        # Retrieve and verify
        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk.id)
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.start_line_id == line1.id
        assert found.end_line_id == line2.id

    @pytest.mark.asyncio
    async def test_nullable_line_references(self, db_session: AsyncSession):
        """DocumentChunk allows null line references."""
        subject = Subject(name="Physics", semester=2)
        teacher = Teacher(name="Dr. Johnson")
        db_session.add(subject)
        db_session.add(teacher)
        await db_session.flush()

        document = Document(
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="test.pdf",
            s3_key="documents/test5.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        # Create chunk without line references
        chunk = DocumentChunk(
            document_id=document.id,
            text="Chunk without line refs",
            chunk_index=0,
            start_page=1,
            end_page=1,
            start_line_id=None,
            end_line_id=None,
        )
        db_session.add(chunk)
        await db_session.flush()
        await db_session.commit()

        # Retrieve and verify
        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk.id)
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.start_line_id is None
        assert found.end_line_id is None


class TestDocumentChunkFields:
    """Tests for DocumentChunk field storage and classification."""

    @pytest.mark.asyncio
    async def test_stores_chunk_type(self, db_session: AsyncSession):
        """DocumentChunk stores chunk_type classification correctly."""
        subject = Subject(name="Math", semester=3)
        teacher = Teacher(name="Dr. Lee")
        db_session.add(subject)
        db_session.add(teacher)
        await db_session.flush()

        document = Document(
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="test.pdf",
            s3_key="documents/test6.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        chunk = DocumentChunk(
            document_id=document.id,
            text="Theorem 1: ...",
            chunk_index=0,
            start_page=1,
            end_page=1,
            chunk_type="theorem",
            section_title="Linear Algebra",
        )
        db_session.add(chunk)
        await db_session.flush()
        await db_session.commit()

        # Retrieve and verify
        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk.id)
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.chunk_type == "theorem"
        assert found.section_title == "Linear Algebra"

    @pytest.mark.asyncio
    async def test_stores_qdrant_point_id(self, db_session: AsyncSession):
        """DocumentChunk stores Qdrant point UUID correctly."""
        subject = Subject(name="Physics", semester=1)
        teacher = Teacher(name="Dr. Smith")
        db_session.add(subject)
        db_session.add(teacher)
        await db_session.flush()

        document = Document(
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="test.pdf",
            s3_key="documents/test7.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        point_id = uuid.uuid4()
        chunk = DocumentChunk(
            document_id=document.id,
            text="Test chunk",
            chunk_index=0,
            start_page=1,
            end_page=1,
            qdrant_point_id=point_id,
            token_count=150,
        )
        db_session.add(chunk)
        await db_session.flush()
        await db_session.commit()

        # Retrieve and verify
        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk.id)
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.qdrant_point_id == point_id
        assert found.token_count == 150

    @pytest.mark.asyncio
    async def test_unique_qdrant_point_id(self, db_session: AsyncSession):
        """Duplicate qdrant_point_id raises error."""
        subject = Subject(name="Math", semester=1)
        teacher = Teacher(name="Dr. Brown")
        db_session.add(subject)
        db_session.add(teacher)
        await db_session.flush()

        document = Document(
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="test.pdf",
            s3_key="documents/test8.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        point_id = uuid.uuid4()

        # Create first chunk with point_id
        chunk1 = DocumentChunk(
            document_id=document.id,
            text="First chunk",
            chunk_index=0,
            start_page=1,
            end_page=1,
            qdrant_point_id=point_id,
        )
        db_session.add(chunk1)
        await db_session.flush()
        await db_session.commit()

        # Attempt to create second chunk with same point_id
        with pytest.raises(IntegrityError):
            chunk2 = DocumentChunk(
                document_id=document.id,
                text="Second chunk",
                chunk_index=1,
                start_page=2,
                end_page=2,
                qdrant_point_id=point_id,
            )
            db_session.add(chunk2)
            await db_session.flush()
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_stores_page_range(self, db_session: AsyncSession):
        """DocumentChunk stores page range correctly."""
        subject = Subject(name="Chemistry", semester=2)
        teacher = Teacher(name="Dr. Wilson")
        db_session.add(subject)
        db_session.add(teacher)
        await db_session.flush()

        document = Document(
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="test.pdf",
            s3_key="documents/test9.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        # Chunk spanning multiple pages
        chunk = DocumentChunk(
            document_id=document.id,
            text="Multi-page content",
            chunk_index=0,
            start_page=5,
            end_page=7,
            chunk_type="proof",
        )
        db_session.add(chunk)
        await db_session.flush()
        await db_session.commit()

        # Retrieve and verify
        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk.id)
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.start_page == 5
        assert found.end_page == 7
        assert found.chunk_type == "proof"
