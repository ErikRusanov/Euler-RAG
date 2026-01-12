"""Document processing handler.

Handles PDF document processing tasks including downloading from S3,
parsing pages, and tracking progress.
"""

import asyncio
import io
import logging
from datetime import datetime, timezone
from typing import Any

from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.document import Document, DocumentStatus
from app.utils.s3 import S3Storage
from app.workers.handlers.base import BaseTaskHandler, TaskError
from app.workers.progress import Progress, ProgressTracker
from app.workers.queue import Task

logger = logging.getLogger(__name__)

# Delay per page to simulate processing (5 seconds)
PAGE_PROCESSING_DELAY_SECONDS = 5


class DocumentHandler(BaseTaskHandler):
    """Handles document processing tasks.

    Downloads PDF from S3, counts pages, simulates processing with
    5-second delay per page, and updates progress in Redis.

    Attributes:
        TIMEOUT_SECONDS: Extended timeout for PDF processing.
    """

    TIMEOUT_SECONDS = 600  # 10 minutes for PDF processing

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        s3: S3Storage,
        progress_tracker: ProgressTracker,
    ) -> None:
        """Initialize DocumentHandler.

        Args:
            session_factory: Factory for creating database sessions.
            s3: S3 storage client for file operations.
            progress_tracker: Progress tracker for real-time updates.
        """
        super().__init__(session_factory)
        self._s3 = s3
        self._progress = progress_tracker

    async def process(self, task: Task, db: AsyncSession) -> None:
        """Process document task.

        Downloads PDF, counts pages, processes each page with delay,
        and updates progress. Sets final status on completion or error.

        Args:
            task: Document processing task.
            db: Database session.

        Raises:
            TaskError: If document not found or processing fails.
        """
        document_id = task.payload["document_id"]

        # Fetch document
        document = await db.get(Document, document_id)
        if not document:
            raise TaskError(
                f"Document {document_id} not found",
                retryable=False,
            )

        # Set status to PROCESSING (flush to make visible in same transaction)
        document.status = DocumentStatus.PROCESSING
        await db.flush()

        try:
            # Download PDF from S3 (run in thread to avoid blocking event loop)
            pdf_bytes = await asyncio.to_thread(self._s3.download_file, document.s3_key)

            # Count pages
            pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
            total_pages = len(pdf_reader.pages)

            logger.info(
                "Processing document",
                extra={
                    "document_id": document_id,
                    "total_pages": total_pages,
                },
            )

            # Process each page
            for page_num in range(1, total_pages + 1):
                # Update progress
                await self._progress.update(
                    Progress(
                        document_id=document_id,
                        page=page_num,
                        total=total_pages,
                        status="processing",
                        message=f"Processing page {page_num}/{total_pages}",
                    )
                )

                # Simulate page processing (5 seconds delay)
                await asyncio.sleep(PAGE_PROCESSING_DELAY_SECONDS)

            # Mark as ready
            document.status = DocumentStatus.READY
            document.processed_at = datetime.now(timezone.utc)
            document.progress = {"page": total_pages, "total": total_pages}

            # Final progress update
            await self._progress.update(
                Progress(
                    document_id=document_id,
                    page=total_pages,
                    total=total_pages,
                    status="ready",
                    message="Processing complete",
                )
            )

            logger.info(
                "Document processing complete",
                extra={"document_id": document_id},
            )

        except TaskError:
            raise
        except Exception as e:
            # Set error status and commit before raising
            # (base handler will rollback, but we want error state persisted)
            document.status = DocumentStatus.ERROR
            document.error = str(e)
            await db.commit()

            # Update progress with error
            await self._progress.update(
                Progress(
                    document_id=document_id,
                    page=0,
                    total=0,
                    status="error",
                    message=str(e),
                )
            )

            raise TaskError(str(e), retryable=False)

    async def update_status(
        self,
        db: AsyncSession,
        record_id: int,
        status: str,
        error: str | None = None,
        **extra_fields: Any,
    ) -> None:
        """Update document status in database.

        Args:
            db: Database session.
            record_id: Document ID.
            status: New DocumentStatus value.
            error: Optional error message.
            **extra_fields: Additional fields to update.
        """
        document = await db.get(Document, record_id)
        if document:
            document.status = status
            document.error = error
            for key, value in extra_fields.items():
                setattr(document, key, value)
