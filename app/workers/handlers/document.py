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
            # Add timeout to allow cancellation during shutdown
            try:
                pdf_bytes = await asyncio.wait_for(
                    asyncio.to_thread(self._s3.download_file, document.s3_key),
                    timeout=120.0,  # Max 2 minutes for S3 download
                )
            except asyncio.TimeoutError:
                raise TaskError("S3 download timeout", retryable=True)
            except asyncio.CancelledError:
                # Propagate cancellation immediately
                raise

            # Parse PDF in thread (CPU-bound operation)
            try:
                total_pages = await asyncio.wait_for(
                    asyncio.to_thread(self._count_pdf_pages, pdf_bytes),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                raise TaskError("PDF parsing timeout", retryable=True)
            except asyncio.CancelledError:
                raise

            logger.info(
                "Processing document",
                extra={
                    "document_id": document_id,
                    "total_pages": total_pages,
                },
            )

            # Process each page
            for page_num in range(1, total_pages + 1):
                current_task = asyncio.current_task()
                if current_task and current_task.cancelled():
                    raise asyncio.CancelledError()

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
                # Use sleep with cancellation check
                try:
                    await asyncio.sleep(PAGE_PROCESSING_DELAY_SECONDS)
                except asyncio.CancelledError:
                    raise

            # Mark as ready
            document.status = DocumentStatus.READY
            document.processed_at = datetime.now(timezone.utc)
            document.error = None
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

        except asyncio.CancelledError:
            raise
        except TaskError:
            raise
        except Exception as e:
            document.status = DocumentStatus.ERROR
            document.error = str(e)

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

    @staticmethod
    def _count_pdf_pages(pdf_bytes: bytes) -> int:
        """Count pages in PDF file.

        This is a CPU-bound operation, should be called via asyncio.to_thread().

        Args:
            pdf_bytes: PDF file content as bytes.

        Returns:
            Number of pages in the PDF.
        """
        pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
        return len(pdf_reader.pages)

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
