"""Integration tests for document processing worker.

Tests the full flow from enqueueing a task to processing completion
with progress updates and status changes.
"""

import io
from unittest.mock import AsyncMock, MagicMock

import pytest
from pypdf import PdfWriter
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_line import DocumentLine
from app.workers.handlers.document import DocumentHandler
from app.workers.progress import Progress, ProgressTracker
from app.workers.queue import TaskQueue, TaskType


def create_test_pdf(num_pages: int) -> bytes:
    """Create a simple PDF with specified number of pages for testing."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)

    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
async def redis_client(test_settings) -> Redis:
    """Create Redis client for integration tests.

    Requires Redis to be running.
    """
    client = Redis.from_url(
        test_settings.redis_url,
        decode_responses=True,
    )

    # Verify connection
    try:
        await client.ping()
    except Exception:
        pytest.skip("Redis not available for integration tests")

    # Cleanup before test to remove stale state
    keys = await client.keys("euler:*")
    if keys:
        await client.delete(*keys)

    yield client

    # Cleanup after test
    keys = await client.keys("euler:*")
    if keys:
        await client.delete(*keys)
    await client.aclose()


@pytest.fixture
def task_queue(redis_client: Redis) -> TaskQueue:
    """Create TaskQueue with real Redis."""
    return TaskQueue(redis_client)


@pytest.fixture
def progress_tracker(redis_client: Redis) -> ProgressTracker:
    """Create ProgressTracker with real Redis."""
    return ProgressTracker(redis_client)


class TestTaskQueueIntegration:
    """Integration tests for TaskQueue with real Redis."""

    @pytest.mark.asyncio
    async def test_enqueue_and_dequeue_task(self, task_queue: TaskQueue):
        """Test full enqueue and dequeue cycle."""
        await task_queue.setup()

        # Enqueue task
        task_id = await task_queue.enqueue(
            TaskType.DOCUMENT_PROCESS,
            {"document_id": 123},
        )

        assert task_id is not None

        # Dequeue task
        task = await task_queue.dequeue(block_ms=1000)

        assert task is not None
        assert task.type == TaskType.DOCUMENT_PROCESS
        assert task.payload == {"document_id": 123}

        # Acknowledge
        await task_queue.ack(task)

    @pytest.mark.asyncio
    async def test_dequeue_returns_none_when_empty(self, task_queue: TaskQueue):
        """Test dequeue returns None when no tasks."""
        await task_queue.setup()

        task = await task_queue.dequeue(block_ms=100)

        assert task is None


class TestProgressTrackerIntegration:
    """Integration tests for ProgressTracker with real Redis."""

    @pytest.mark.asyncio
    async def test_update_and_get_progress(self, progress_tracker: ProgressTracker):
        """Test storing and retrieving progress."""
        progress = Progress(
            document_id=1,
            page=5,
            total=10,
            status="processing",
            message="Working...",
        )

        await progress_tracker.update(progress)

        retrieved = await progress_tracker.get(1)

        assert retrieved is not None
        assert retrieved.document_id == 1
        assert retrieved.page == 5
        assert retrieved.total == 10
        assert retrieved.status == "processing"

    @pytest.mark.asyncio
    async def test_clear_removes_progress(self, progress_tracker: ProgressTracker):
        """Test clearing progress data."""
        progress = Progress(
            document_id=99,
            page=1,
            total=1,
            status="done",
        )

        await progress_tracker.update(progress)
        await progress_tracker.clear(99)

        retrieved = await progress_tracker.get(99)

        assert retrieved is None


class TestDocumentProcessingFlow:
    """Integration tests for document processing end-to-end flow."""

    @pytest.mark.asyncio
    async def test_document_processing_full_flow(
        self,
        db_session: AsyncSession,
        redis_client: Redis,
        progress_tracker: ProgressTracker,
    ):
        """Test complete document processing flow with Mathpix and chunking.

        1. Create document in DB
        2. Process document (with mocked S3 and Mathpix)
        3. Verify lines are saved
        4. Verify chunks are created and saved
        5. Verify progress updates
        6. Verify final status
        """
        # 1. Create document
        pdf_bytes = create_test_pdf(2)  # 2 pages

        document = Document(
            filename="test.pdf",
            s3_key="pdf/test.pdf",
            status=DocumentStatus.UPLOADED,
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        document_id = document.id

        # 2. Mock S3 and Mathpix
        mock_s3 = MagicMock()
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)
        mock_s3.get_file_url = MagicMock(return_value="https://example.com/test.pdf")

        # Mock Mathpix response with sample lines
        mock_mathpix = MagicMock()
        mock_mathpix.extract_lines = AsyncMock(
            return_value={
                "pages": [
                    {
                        "page": 1,
                        "lines": [
                            {
                                "text": "\\section{Introduction}",
                                "type": "header",
                                "font_size": 14,
                            },
                            {
                                "text": "This is a test document.",
                                "type": "text",
                                "font_size": 12,
                            },
                            {
                                "text": "\\begin{theorem}",
                                "type": "text",
                                "font_size": 12,
                            },
                            {
                                "text": "For all x, x^2 >= 0",
                                "type": "math",
                                "font_size": 12,
                            },
                            {
                                "text": "\\end{theorem}",
                                "type": "text",
                                "font_size": 12,
                            },
                        ],
                    },
                    {
                        "page": 2,
                        "lines": [
                            {
                                "text": "More content on page 2",
                                "type": "text",
                                "font_size": 12,
                            },
                        ],
                    },
                ]
            }
        )

        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_factory = async_sessionmaker(
            bind=db_session.get_bind(),
            expire_on_commit=False,
            autoflush=False,
        )

        handler = DocumentHandler(
            session_factory=session_factory,
            s3=mock_s3,
            progress_tracker=progress_tracker,
            mathpix_client=mock_mathpix,
        )

        # 3. Create and process task
        from app.workers.queue import Task

        task = Task(
            id="test-task-123",
            type=TaskType.DOCUMENT_PROCESS,
            payload={"document_id": document_id},
            stream_id="0-0",
        )

        await handler.process(task, db_session)
        await db_session.commit()

        # 4. Verify document lines were saved
        result = await db_session.execute(
            select(DocumentLine).where(DocumentLine.document_id == document_id)
        )
        lines = list(result.scalars().all())
        assert len(lines) == 6  # 5 lines on page 1, 1 line on page 2
        assert all(line.document_id == document_id for line in lines)
        assert lines[0].text == "\\section{Introduction}"
        assert lines[0].line_type == "section_header"

        # 5. Verify chunks were created and saved
        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        chunks = list(result.scalars().all())
        assert len(chunks) > 0
        assert all(chunk.document_id == document_id for chunk in chunks)
        # Verify chunk indices are sequential
        chunk_indices = sorted([chunk.chunk_index for chunk in chunks])
        assert chunk_indices == list(range(len(chunks)))

        # 6. Verify progress was updated
        progress = await progress_tracker.get(document_id)
        assert progress is not None
        assert progress.status == "ready"
        assert progress.page == 2
        assert progress.total == 2

        # 7. Verify final document status
        await db_session.refresh(document)
        assert document.status == DocumentStatus.READY
        assert document.processed_at is not None
        assert document.error is None

    @pytest.mark.asyncio
    async def test_document_processing_handles_errors(
        self,
        db_session: AsyncSession,
        progress_tracker: ProgressTracker,
    ):
        """Test error handling during document processing."""
        document = Document(
            filename="error.pdf",
            s3_key="pdf/error.pdf",
            status=DocumentStatus.UPLOADED,
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        document_id = document.id

        # Mock S3 to raise error
        mock_s3 = MagicMock()
        mock_s3.download_file = MagicMock(side_effect=Exception("S3 download failed"))

        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_factory = async_sessionmaker(
            bind=db_session.get_bind(),
            expire_on_commit=False,
            autoflush=False,
        )

        handler = DocumentHandler(
            session_factory=session_factory,
            s3=mock_s3,
            progress_tracker=progress_tracker,
        )

        from app.workers.handlers.base import TaskError
        from app.workers.queue import Task

        task = Task(
            id="test-task-error",
            type=TaskType.DOCUMENT_PROCESS,
            payload={"document_id": document_id},
            stream_id="0-0",
        )

        # Process should raise TaskError
        with pytest.raises(TaskError):
            await handler.process(task, db_session)

        await db_session.commit()

        # Verify error status
        await db_session.refresh(document)
        assert document.status == DocumentStatus.ERROR
        assert document.error is not None
        assert "S3 download failed" in document.error

        # Verify error progress update
        progress = await progress_tracker.get(document_id)
        assert progress is not None
        assert progress.status == "error"

    @pytest.mark.asyncio
    async def test_document_processing_handles_mathpix_error(
        self,
        db_session: AsyncSession,
        progress_tracker: ProgressTracker,
    ):
        """Test error handling when Mathpix fails."""
        pdf_bytes = create_test_pdf(1)

        document = Document(
            filename="mathpix_error.pdf",
            s3_key="pdf/mathpix_error.pdf",
            status=DocumentStatus.UPLOADED,
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        document_id = document.id

        # Mock S3
        mock_s3 = MagicMock()
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)
        mock_s3.get_file_url = MagicMock(return_value="https://example.com/test.pdf")

        # Mock Mathpix to raise error
        from app.exceptions import MathpixError

        mock_mathpix = MagicMock()
        mock_mathpix.extract_lines = AsyncMock(
            side_effect=MathpixError("Mathpix API error", retryable=True)
        )

        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_factory = async_sessionmaker(
            bind=db_session.get_bind(),
            expire_on_commit=False,
            autoflush=False,
        )

        handler = DocumentHandler(
            session_factory=session_factory,
            s3=mock_s3,
            progress_tracker=progress_tracker,
            mathpix_client=mock_mathpix,
        )

        from app.workers.handlers.base import TaskError
        from app.workers.queue import Task

        task = Task(
            id="test-task-mathpix-error",
            type=TaskType.DOCUMENT_PROCESS,
            payload={"document_id": document_id},
            stream_id="0-0",
        )

        # Process should raise TaskError
        with pytest.raises(TaskError) as exc_info:
            await handler.process(task, db_session)

        assert exc_info.value.retryable is True
        assert "Mathpix" in str(exc_info.value)

        await db_session.commit()

        # Verify error status
        await db_session.refresh(document)
        assert document.status == DocumentStatus.ERROR
        assert document.error is not None

    @pytest.mark.asyncio
    async def test_document_processing_requires_mathpix_client(
        self,
        db_session: AsyncSession,
        progress_tracker: ProgressTracker,
    ):
        """Test that processing fails if Mathpix client is not configured."""
        pdf_bytes = create_test_pdf(1)

        document = Document(
            filename="no_client.pdf",
            s3_key="pdf/no_client.pdf",
            status=DocumentStatus.UPLOADED,
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        document_id = document.id

        # Mock S3
        mock_s3 = MagicMock()
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)

        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_factory = async_sessionmaker(
            bind=db_session.get_bind(),
            expire_on_commit=False,
            autoflush=False,
        )

        # Handler without Mathpix client
        handler = DocumentHandler(
            session_factory=session_factory,
            s3=mock_s3,
            progress_tracker=progress_tracker,
            mathpix_client=None,
        )

        from app.workers.handlers.base import TaskError
        from app.workers.queue import Task

        task = Task(
            id="test-task-no-client",
            type=TaskType.DOCUMENT_PROCESS,
            payload={"document_id": document_id},
            stream_id="0-0",
        )

        # Process should raise TaskError
        with pytest.raises(TaskError) as exc_info:
            await handler.process(task, db_session)

        assert exc_info.value.retryable is False
        assert "Mathpix client not configured" in str(exc_info.value)

        await db_session.commit()

        # Verify error status
        await db_session.refresh(document)
        assert document.status == DocumentStatus.ERROR

    @pytest.mark.asyncio
    async def test_document_processing_with_embeddings(
        self,
        db_session: AsyncSession,
        redis_client: Redis,
        progress_tracker: ProgressTracker,
    ):
        """Test document processing generates embeddings for chunks.

        1. Create document in DB
        2. Process document with mocked S3, Mathpix, and EmbeddingService
        3. Verify chunks have embeddings attached
        """
        # 1. Create document
        pdf_bytes = create_test_pdf(1)

        document = Document(
            filename="embed_test.pdf",
            s3_key="pdf/embed_test.pdf",
            status=DocumentStatus.UPLOADED,
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        document_id = document.id

        # 2. Mock dependencies
        mock_s3 = MagicMock()
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)
        mock_s3.get_file_url = MagicMock(return_value="https://example.com/test.pdf")

        mock_mathpix = MagicMock()
        mock_mathpix.extract_lines = AsyncMock(
            return_value={
                "pages": [
                    {
                        "page": 1,
                        "lines": [
                            {"text": "Introduction", "type": "header", "font_size": 14},
                            {
                                "text": "Some text content",
                                "type": "text",
                                "font_size": 12,
                            },
                        ],
                    },
                ]
            }
        )

        # Mock EmbeddingService - returns 1024-dim vectors
        mock_embedding_service = MagicMock()
        mock_embedding_service.generate_embeddings_batch = AsyncMock(
            return_value=[[0.1] * 1024]  # One chunk = one embedding
        )

        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_factory = async_sessionmaker(
            bind=db_session.get_bind(),
            expire_on_commit=False,
            autoflush=False,
        )

        handler = DocumentHandler(
            session_factory=session_factory,
            s3=mock_s3,
            progress_tracker=progress_tracker,
            mathpix_client=mock_mathpix,
            embedding_service=mock_embedding_service,
        )

        # 3. Process task
        from app.workers.queue import Task

        task = Task(
            id="test-embed-task",
            type=TaskType.DOCUMENT_PROCESS,
            payload={"document_id": document_id},
            stream_id="0-0",
        )

        await handler.process(task, db_session)
        await db_session.commit()

        # 4. Verify chunks have embeddings
        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        chunks = list(result.scalars().all())

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 1024

        # Verify embedding service was called
        mock_embedding_service.generate_embeddings_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_document_processing_embedding_api_failure(
        self,
        db_session: AsyncSession,
        progress_tracker: ProgressTracker,
    ):
        """Test error handling when embedding API fails."""
        pdf_bytes = create_test_pdf(1)

        document = Document(
            filename="embed_fail.pdf",
            s3_key="pdf/embed_fail.pdf",
            status=DocumentStatus.UPLOADED,
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        document_id = document.id

        mock_s3 = MagicMock()
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)
        mock_s3.get_file_url = MagicMock(return_value="https://example.com/test.pdf")

        mock_mathpix = MagicMock()
        mock_mathpix.extract_lines = AsyncMock(
            return_value={
                "pages": [
                    {
                        "page": 1,
                        "lines": [
                            {"text": "Some content", "type": "text", "font_size": 12},
                        ],
                    },
                ]
            }
        )

        # Mock EmbeddingService that fails
        mock_embedding_service = MagicMock()
        mock_embedding_service.generate_embeddings_batch = AsyncMock(
            side_effect=Exception("OpenRouter API error")
        )

        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_factory = async_sessionmaker(
            bind=db_session.get_bind(),
            expire_on_commit=False,
            autoflush=False,
        )

        handler = DocumentHandler(
            session_factory=session_factory,
            s3=mock_s3,
            progress_tracker=progress_tracker,
            mathpix_client=mock_mathpix,
            embedding_service=mock_embedding_service,
        )

        from app.workers.handlers.base import TaskError
        from app.workers.queue import Task

        task = Task(
            id="test-embed-fail-task",
            type=TaskType.DOCUMENT_PROCESS,
            payload={"document_id": document_id},
            stream_id="0-0",
        )

        # Process should raise TaskError
        with pytest.raises(TaskError) as exc_info:
            await handler.process(task, db_session)

        assert exc_info.value.retryable is True
        assert "Embedding generation failed" in str(exc_info.value)

        await db_session.commit()

        # Verify error status
        await db_session.refresh(document)
        assert document.status == DocumentStatus.ERROR

    @pytest.mark.asyncio
    async def test_document_processing_without_embedding_service(
        self,
        db_session: AsyncSession,
        redis_client: Redis,
        progress_tracker: ProgressTracker,
    ):
        """Test document processing works without embedding service (optional).

        This ensures backward compatibility - documents can be processed
        without generating embeddings if service is not configured.
        """
        pdf_bytes = create_test_pdf(1)

        document = Document(
            filename="no_embed.pdf",
            s3_key="pdf/no_embed.pdf",
            status=DocumentStatus.UPLOADED,
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        document_id = document.id

        mock_s3 = MagicMock()
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)
        mock_s3.get_file_url = MagicMock(return_value="https://example.com/test.pdf")

        mock_mathpix = MagicMock()
        mock_mathpix.extract_lines = AsyncMock(
            return_value={
                "pages": [
                    {
                        "page": 1,
                        "lines": [
                            {"text": "Content", "type": "text", "font_size": 12},
                        ],
                    },
                ]
            }
        )

        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_factory = async_sessionmaker(
            bind=db_session.get_bind(),
            expire_on_commit=False,
            autoflush=False,
        )

        # Handler without embedding service
        handler = DocumentHandler(
            session_factory=session_factory,
            s3=mock_s3,
            progress_tracker=progress_tracker,
            mathpix_client=mock_mathpix,
            embedding_service=None,
        )

        from app.workers.queue import Task

        task = Task(
            id="test-no-embed-task",
            type=TaskType.DOCUMENT_PROCESS,
            payload={"document_id": document_id},
            stream_id="0-0",
        )

        await handler.process(task, db_session)
        await db_session.commit()

        # Verify chunks created but without embeddings
        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        chunks = list(result.scalars().all())

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.embedding is None

        # Verify document status is still READY
        await db_session.refresh(document)
        assert document.status == DocumentStatus.READY
