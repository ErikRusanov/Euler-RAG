"""Integration tests for document processing worker.

Tests the full flow from enqueueing a task to processing completion
with progress updates and status changes.
"""

import asyncio
import io
from unittest.mock import MagicMock, patch

import pytest
from pypdf import PdfWriter
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
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
        """Test complete document processing flow.

        1. Create document in DB
        2. Enqueue processing task
        3. Process document (with mocked S3 and reduced delay)
        4. Verify progress updates
        5. Verify final status
        """
        # 1. Create document with required relationships
        from app.models.subject import Subject
        from app.models.teacher import Teacher

        pdf_bytes = create_test_pdf(2)  # 2 pages

        # Create subject and teacher required by document
        subject = Subject(name="Test Subject", semester=1)
        db_session.add(subject)
        await db_session.flush()

        teacher = Teacher(name="Test Teacher")
        db_session.add(teacher)
        await db_session.flush()

        document = Document(
            filename="test.pdf",
            s3_key="pdf/test.pdf",
            status=DocumentStatus.UPLOADED,
            subject_id=subject.id,
            teacher_id=teacher.id,
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        document_id = document.id

        # 2. Mock S3 and create handler
        mock_s3 = MagicMock()
        mock_s3.download_file = MagicMock(return_value=pdf_bytes)

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

        # 3. Create and process task (with reduced delay for testing)
        from app.workers.queue import Task

        task = Task(
            id="test-task-123",
            type=TaskType.DOCUMENT_PROCESS,
            payload={"document_id": document_id},
            stream_id="0-0",
        )

        # Patch the sleep to speed up test
        with patch("app.workers.handlers.document.PAGE_PROCESSING_DELAY_SECONDS", 0.1):
            with patch(
                "app.workers.handlers.document.asyncio.sleep", new=asyncio.sleep
            ):
                await handler.process(task, db_session)
                await db_session.commit()

        # 4. Verify progress was updated
        progress = await progress_tracker.get(document_id)
        assert progress is not None
        assert progress.status == "ready"
        assert progress.page == 2
        assert progress.total == 2

        # 5. Verify final document status
        await db_session.refresh(document)
        assert document.status == DocumentStatus.READY
        assert document.processed_at is not None
        # Nougat is skipped when no client is provided
        assert document.progress == {
            "page": 2,
            "total": 2,
            "nougat_status": "skipped",
            "nougat_text": None,
        }

    @pytest.mark.asyncio
    async def test_document_processing_handles_errors(
        self,
        db_session: AsyncSession,
        progress_tracker: ProgressTracker,
    ):
        """Test error handling during document processing."""
        # Create document with required relationships
        from app.models.subject import Subject
        from app.models.teacher import Teacher

        # Create subject and teacher required by document
        subject = Subject(name="Error Test Subject", semester=2)
        db_session.add(subject)
        await db_session.flush()

        teacher = Teacher(name="Error Test Teacher")
        db_session.add(teacher)
        await db_session.flush()

        document = Document(
            filename="error.pdf",
            s3_key="pdf/error.pdf",
            status=DocumentStatus.UPLOADED,
            subject_id=subject.id,
            teacher_id=teacher.id,
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
