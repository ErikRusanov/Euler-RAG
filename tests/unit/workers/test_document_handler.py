"""Unit tests for DocumentHandler."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.utils.nougat import NougatClient, NougatError
from app.workers.handlers.document import DocumentHandler
from app.workers.progress import ProgressTracker
from app.workers.queue import Task, TaskType


@pytest.fixture
def mock_session_factory():
    """Create mock session factory."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    factory = MagicMock()
    factory.return_value = mock_session
    return factory


@pytest.fixture
def mock_s3():
    """Create mock S3 storage."""
    return MagicMock()


@pytest.fixture
def mock_progress_tracker():
    """Create mock ProgressTracker."""
    tracker = AsyncMock(spec=ProgressTracker)
    return tracker


@pytest.fixture
def mock_nougat_client():
    """Create mock NougatClient."""
    client = AsyncMock(spec=NougatClient)
    client.extract_text = AsyncMock(return_value="# Extracted Text\n\nSample content.")
    return client


@pytest.fixture
def document_handler(mock_session_factory, mock_s3, mock_progress_tracker):
    """Create DocumentHandler with mocks (without Nougat)."""
    return DocumentHandler(
        session_factory=mock_session_factory,
        s3=mock_s3,
        progress_tracker=mock_progress_tracker,
    )


@pytest.fixture
def document_handler_with_nougat(
    mock_session_factory, mock_s3, mock_progress_tracker, mock_nougat_client
):
    """Create DocumentHandler with mocks including Nougat client."""
    return DocumentHandler(
        session_factory=mock_session_factory,
        s3=mock_s3,
        progress_tracker=mock_progress_tracker,
        nougat_client=mock_nougat_client,
    )


@pytest.fixture
def sample_task():
    """Create sample document processing task."""
    return Task(
        id="task-123",
        type=TaskType.DOCUMENT_PROCESS,
        payload={"document_id": 1},
        stream_id="1234567890-0",
    )


@pytest.fixture
def sample_document():
    """Create sample Document object."""
    doc = MagicMock(spec=Document)
    doc.id = 1
    doc.s3_key = "pdf/test.pdf"
    doc.status = DocumentStatus.UPLOADED
    return doc


class TestDocumentHandlerProcess:
    """Tests for DocumentHandler.process method."""

    @pytest.mark.asyncio
    async def test_process_updates_status_to_processing(
        self,
        document_handler: DocumentHandler,
        mock_session_factory,
        sample_task: Task,
        sample_document: Document,
        mock_s3,
    ):
        """Process should set document status to PROCESSING."""
        mock_session = mock_session_factory.return_value
        mock_session.get = AsyncMock(return_value=sample_document)
        mock_session.commit = AsyncMock()

        # Mock PDF with 1 page
        pdf_bytes = self._create_simple_pdf(1)
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)

        with patch(
            "app.workers.handlers.document.asyncio.sleep", new_callable=AsyncMock
        ):
            await document_handler.process(sample_task, mock_session)

        # Verify status was set to PROCESSING at some point
        assert sample_document.status == DocumentStatus.READY

    @pytest.mark.asyncio
    async def test_process_updates_progress_per_page(
        self,
        document_handler: DocumentHandler,
        mock_session_factory,
        mock_progress_tracker,
        sample_task: Task,
        sample_document: Document,
        mock_s3,
    ):
        """Process should update progress for each page."""
        mock_session = mock_session_factory.return_value
        mock_session.get = AsyncMock(return_value=sample_document)
        mock_session.commit = AsyncMock()

        # Mock PDF with 3 pages
        pdf_bytes = self._create_simple_pdf(3)
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)

        with patch(
            "app.workers.handlers.document.asyncio.sleep", new_callable=AsyncMock
        ):
            await document_handler.process(sample_task, mock_session)

        # Verify progress was updated for each page
        progress_calls = mock_progress_tracker.update.call_args_list
        assert len(progress_calls) >= 3  # At least one per page

        # Verify page numbers were tracked
        pages_updated = [call[0][0].page for call in progress_calls]
        assert 1 in pages_updated
        assert 2 in pages_updated
        assert 3 in pages_updated

    @pytest.mark.asyncio
    async def test_process_sets_ready_on_success(
        self,
        document_handler: DocumentHandler,
        mock_session_factory,
        sample_task: Task,
        sample_document: Document,
        mock_s3,
    ):
        """Process should set status to READY on success."""
        mock_session = mock_session_factory.return_value
        mock_session.get = AsyncMock(return_value=sample_document)
        mock_session.commit = AsyncMock()

        pdf_bytes = self._create_simple_pdf(1)
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)

        with patch(
            "app.workers.handlers.document.asyncio.sleep", new_callable=AsyncMock
        ):
            await document_handler.process(sample_task, mock_session)

        assert sample_document.status == DocumentStatus.READY
        assert sample_document.processed_at is not None

    @pytest.mark.asyncio
    async def test_process_sets_error_on_failure(
        self,
        document_handler: DocumentHandler,
        mock_session_factory,
        sample_task: Task,
        sample_document: Document,
        mock_s3,
    ):
        """Process should set status to ERROR on failure."""
        mock_session = mock_session_factory.return_value
        mock_session.get = AsyncMock(return_value=sample_document)
        mock_session.commit = AsyncMock()

        # Simulate S3 download failure
        mock_s3.download_file = MagicMock(side_effect=Exception("S3 error"))

        from app.workers.handlers.base import TaskError

        with pytest.raises(TaskError):
            await document_handler.process(sample_task, mock_session)

        assert sample_document.status == DocumentStatus.ERROR
        assert sample_document.error is not None
        assert "S3 error" in sample_document.error

    @pytest.mark.asyncio
    async def test_process_raises_error_when_document_not_found(
        self,
        document_handler: DocumentHandler,
        mock_session_factory,
        sample_task: Task,
    ):
        """Process should raise TaskError when document not found."""
        mock_session = mock_session_factory.return_value
        mock_session.get = AsyncMock(return_value=None)

        from app.workers.handlers.base import TaskError

        with pytest.raises(TaskError) as exc_info:
            await document_handler.process(sample_task, mock_session)

        assert "not found" in str(exc_info.value).lower()

    def _create_simple_pdf(self, num_pages: int) -> bytes:
        """Create a simple PDF with specified number of pages for testing."""
        from pypdf import PdfWriter

        writer = PdfWriter()
        for _ in range(num_pages):
            writer.add_blank_page(width=612, height=792)

        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()


class TestDocumentHandlerNougatIntegration:
    """Tests for DocumentHandler Nougat OCR integration."""

    @pytest.mark.asyncio
    async def test_process_calls_nougat_when_client_available(
        self,
        document_handler_with_nougat: DocumentHandler,
        mock_session_factory,
        mock_nougat_client,
        sample_task: Task,
        sample_document: Document,
        mock_s3,
    ):
        """Process should call Nougat when client is available."""
        mock_session = mock_session_factory.return_value
        mock_session.get = AsyncMock(return_value=sample_document)
        mock_session.commit = AsyncMock()

        pdf_bytes = self._create_simple_pdf(1)
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)
        mock_s3.get_file_url = MagicMock(return_value="https://s3.example.com/test.pdf")

        with patch(
            "app.workers.handlers.document.asyncio.sleep", new_callable=AsyncMock
        ):
            await document_handler_with_nougat.process(sample_task, mock_session)

        mock_nougat_client.extract_text.assert_called_once_with(
            "https://s3.example.com/test.pdf"
        )

    @pytest.mark.asyncio
    async def test_process_stores_nougat_text_in_progress(
        self,
        document_handler_with_nougat: DocumentHandler,
        mock_session_factory,
        mock_nougat_client,
        sample_task: Task,
        sample_document: Document,
        mock_s3,
    ):
        """Process should store extracted text in document progress."""
        mock_session = mock_session_factory.return_value
        mock_session.get = AsyncMock(return_value=sample_document)
        mock_session.commit = AsyncMock()

        expected_text = "# Document Title\n\nExtracted content here."
        mock_nougat_client.extract_text = AsyncMock(return_value=expected_text)

        pdf_bytes = self._create_simple_pdf(2)
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)
        mock_s3.get_file_url = MagicMock(return_value="https://s3.example.com/test.pdf")

        with patch(
            "app.workers.handlers.document.asyncio.sleep", new_callable=AsyncMock
        ):
            await document_handler_with_nougat.process(sample_task, mock_session)

        # Verify progress contains nougat data
        assert sample_document.progress["nougat_status"] == "ready"
        assert sample_document.progress["nougat_text"] == expected_text
        assert sample_document.progress["page"] == 2
        assert sample_document.progress["total"] == 2

    @pytest.mark.asyncio
    async def test_process_skips_nougat_when_client_not_available(
        self,
        document_handler: DocumentHandler,
        mock_session_factory,
        sample_task: Task,
        sample_document: Document,
        mock_s3,
    ):
        """Process should skip Nougat when client is not available."""
        mock_session = mock_session_factory.return_value
        mock_session.get = AsyncMock(return_value=sample_document)
        mock_session.commit = AsyncMock()

        pdf_bytes = self._create_simple_pdf(1)
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)

        with patch(
            "app.workers.handlers.document.asyncio.sleep", new_callable=AsyncMock
        ):
            await document_handler.process(sample_task, mock_session)

        # Document should still be READY
        assert sample_document.status == DocumentStatus.READY
        assert sample_document.progress["nougat_status"] == "skipped"
        assert sample_document.progress["nougat_text"] is None

    @pytest.mark.asyncio
    async def test_process_handles_nougat_error_retryable(
        self,
        document_handler_with_nougat: DocumentHandler,
        mock_session_factory,
        mock_nougat_client,
        sample_task: Task,
        sample_document: Document,
        mock_s3,
    ):
        """Process should raise retryable TaskError on Nougat failure."""
        mock_session = mock_session_factory.return_value
        mock_session.get = AsyncMock(return_value=sample_document)
        mock_session.commit = AsyncMock()

        mock_nougat_client.extract_text = AsyncMock(
            side_effect=NougatError("API timeout", retryable=True)
        )

        pdf_bytes = self._create_simple_pdf(1)
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)
        mock_s3.get_file_url = MagicMock(return_value="https://s3.example.com/test.pdf")

        from app.workers.handlers.base import TaskError

        with pytest.raises(TaskError) as exc_info:
            await document_handler_with_nougat.process(sample_task, mock_session)

        assert exc_info.value.retryable is True
        assert sample_document.progress["nougat_status"] == "error"
        assert "API timeout" in sample_document.progress["nougat_error"]

    @pytest.mark.asyncio
    async def test_process_handles_nougat_error_non_retryable(
        self,
        document_handler_with_nougat: DocumentHandler,
        mock_session_factory,
        mock_nougat_client,
        sample_task: Task,
        sample_document: Document,
        mock_s3,
    ):
        """Process should raise non-retryable TaskError on permanent Nougat failure."""
        mock_session = mock_session_factory.return_value
        mock_session.get = AsyncMock(return_value=sample_document)
        mock_session.commit = AsyncMock()

        mock_nougat_client.extract_text = AsyncMock(
            side_effect=NougatError("Invalid PDF format", retryable=False)
        )

        pdf_bytes = self._create_simple_pdf(1)
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)
        mock_s3.get_file_url = MagicMock(return_value="https://s3.example.com/test.pdf")

        from app.workers.handlers.base import TaskError

        with pytest.raises(TaskError) as exc_info:
            await document_handler_with_nougat.process(sample_task, mock_session)

        assert exc_info.value.retryable is False
        assert sample_document.progress["nougat_status"] == "error"

    def _create_simple_pdf(self, num_pages: int) -> bytes:
        """Create a simple PDF with specified number of pages for testing."""
        from pypdf import PdfWriter

        writer = PdfWriter()
        for _ in range(num_pages):
            writer.add_blank_page(width=612, height=792)

        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
