"""Integration tests for DocumentLine model."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.document_line import DocumentLine


class TestDocumentLineConstraints:
    """Tests for DocumentLine model unique constraints."""

    @pytest.mark.asyncio
    async def test_unique_document_page_line_constraint(self, db_session: AsyncSession):
        """Duplicate (document_id, page_number, line_number) raises error."""
        document = Document(
            filename="test.pdf",
            s3_key="documents/test.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        # Create first line
        line1 = DocumentLine(
            document_id=document.id,
            page_number=1,
            line_number=1,
            text="First line",
            line_type="text",
        )
        db_session.add(line1)
        await db_session.flush()
        await db_session.commit()

        # Attempt to create duplicate line
        with pytest.raises(IntegrityError):
            line2 = DocumentLine(
                document_id=document.id,
                page_number=1,
                line_number=1,
                text="Different text",
                line_type="text",
            )
            db_session.add(line2)
            await db_session.flush()
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_same_line_different_page_allowed(self, db_session: AsyncSession):
        """Same line number on different pages is allowed."""
        document = Document(
            filename="test.pdf",
            s3_key="documents/test2.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        # Create lines with same line_number but different pages
        line1 = DocumentLine(
            document_id=document.id,
            page_number=1,
            line_number=5,
            text="Line on page 1",
            line_type="text",
        )
        line2 = DocumentLine(
            document_id=document.id,
            page_number=2,
            line_number=5,
            text="Line on page 2",
            line_type="text",
        )
        db_session.add(line1)
        db_session.add(line2)
        await db_session.flush()
        await db_session.commit()

        assert line1.id != line2.id
        assert line1.page_number != line2.page_number

    @pytest.mark.asyncio
    async def test_cascade_delete_on_document(self, db_session: AsyncSession):
        """Deleting document cascades to delete all its lines."""
        document = Document(
            filename="test.pdf",
            s3_key="documents/test3.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        # Create multiple lines
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
            line_number=2,
            text="Line 2",
            line_type="math",
        )
        db_session.add(line1)
        db_session.add(line2)
        await db_session.flush()
        await db_session.commit()

        line1_id = line1.id
        line2_id = line2.id

        # Delete document
        await db_session.delete(document)
        await db_session.commit()

        # Verify lines are deleted
        result = await db_session.execute(
            select(DocumentLine).where(DocumentLine.id.in_([line1_id, line2_id]))
        )
        remaining_lines = result.scalars().all()
        assert len(remaining_lines) == 0


class TestDocumentLineJSONBFields:
    """Tests for DocumentLine JSONB field storage."""

    @pytest.mark.asyncio
    async def test_stores_region_jsonb(self, db_session: AsyncSession):
        """DocumentLine stores JSONB region field correctly."""
        document = Document(
            filename="test.pdf",
            s3_key="documents/test4.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        region_data = {
            "top_left_x": 100,
            "top_left_y": 200,
            "width": 300,
            "height": 50,
        }
        line = DocumentLine(
            document_id=document.id,
            page_number=1,
            line_number=1,
            text="Test line",
            line_type="text",
            region=region_data,
        )
        db_session.add(line)
        await db_session.flush()
        await db_session.commit()

        # Retrieve and verify
        result = await db_session.execute(
            select(DocumentLine).where(DocumentLine.id == line.id)
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.region == region_data
        assert found.region["top_left_x"] == 100

    @pytest.mark.asyncio
    async def test_stores_raw_metadata_jsonb(self, db_session: AsyncSession):
        """DocumentLine stores JSONB raw_metadata field correctly."""
        document = Document(
            filename="test.pdf",
            s3_key="documents/test5.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        metadata = {
            "language": "ru",
            "detected_font": "Times New Roman",
            "style": "italic",
        }
        line = DocumentLine(
            document_id=document.id,
            page_number=1,
            line_number=1,
            text="Test line",
            line_type="text",
            raw_metadata=metadata,
        )
        db_session.add(line)
        await db_session.flush()
        await db_session.commit()

        # Retrieve and verify
        result = await db_session.execute(
            select(DocumentLine).where(DocumentLine.id == line.id)
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.raw_metadata == metadata
        assert found.raw_metadata["language"] == "ru"


class TestDocumentLineMetadata:
    """Tests for DocumentLine metadata fields."""

    @pytest.mark.asyncio
    async def test_default_boolean_values(self, db_session: AsyncSession):
        """DocumentLine has correct default values for boolean fields."""
        document = Document(
            filename="test.pdf",
            s3_key="documents/test6.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        line = DocumentLine(
            document_id=document.id,
            page_number=1,
            line_number=1,
            text="Test line",
            line_type="text",
        )
        db_session.add(line)
        await db_session.flush()
        await db_session.refresh(line)
        await db_session.commit()

        assert line.is_printed is True
        assert line.is_handwritten is False

    @pytest.mark.asyncio
    async def test_stores_all_mathpix_fields(self, db_session: AsyncSession):
        """DocumentLine stores all Mathpix metadata fields correctly."""
        document = Document(
            filename="test.pdf",
            s3_key="documents/test7.pdf",
            status=DocumentStatus.PROCESSING,
        )
        db_session.add(document)
        await db_session.flush()
        await db_session.commit()

        line = DocumentLine(
            document_id=document.id,
            page_number=2,
            line_number=15,
            text="\\int_{0}^{\\infty} e^{-x} dx = 1",
            line_type="math",
            font_size=12,
            is_printed=True,
            is_handwritten=False,
            confidence=0.98,
            region={"top_left_x": 100, "top_left_y": 200, "width": 300, "height": 50},
            raw_metadata={"language": "en", "style": "normal"},
        )
        db_session.add(line)
        await db_session.flush()
        await db_session.commit()

        # Retrieve and verify all fields
        result = await db_session.execute(
            select(DocumentLine).where(DocumentLine.id == line.id)
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.page_number == 2
        assert found.line_number == 15
        assert found.line_type == "math"
        assert found.font_size == 12
        assert found.confidence == 0.98
        assert found.is_printed is True
        assert found.is_handwritten is False
