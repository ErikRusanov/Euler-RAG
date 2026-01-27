"""Document processing handler.

Handles PDF document processing tasks including downloading from S3,
extracting lines via Mathpix OCR, chunking content, and tracking progress.
"""

import asyncio
import io
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.exceptions import MathpixError
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_line import DocumentLine
from app.services.chunking_service import ChunkingService
from app.utils.mathpix import MathpixClient
from app.utils.s3 import S3Storage
from app.workers.handlers.base import BaseTaskHandler, TaskError
from app.workers.progress import Progress, ProgressTracker
from app.workers.queue import Task

logger = logging.getLogger(__name__)

# Timeout for Mathpix API call (10 minutes - PDF processing can be slow)
MATHPIX_TIMEOUT_SECONDS = 600


class DocumentHandler(BaseTaskHandler):
    """Handles document processing tasks.

    Downloads PDF from S3, extracts lines via Mathpix OCR, chunks content
    using ChunkingService, and updates progress in Redis. Stores extracted
    lines and chunks in database for future embedding.

    Attributes:
        TIMEOUT_SECONDS: Extended timeout for PDF processing.
    """

    TIMEOUT_SECONDS = 600  # 10 minutes for PDF processing

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        s3: S3Storage,
        progress_tracker: ProgressTracker,
        mathpix_client: Optional[MathpixClient] = None,
        chunking_service: Optional[ChunkingService] = None,
    ) -> None:
        """Initialize DocumentHandler.

        Args:
            session_factory: Factory for creating database sessions.
            s3: S3 storage client for file operations.
            progress_tracker: Progress tracker for real-time updates.
            mathpix_client: Optional Mathpix OCR client for line extraction.
            chunking_service: Optional chunking service for content splitting.
        """
        super().__init__(session_factory)
        self._s3 = s3
        self._progress = progress_tracker
        self._mathpix = mathpix_client
        self._chunking_service = chunking_service or ChunkingService()

    async def process(self, task: Task, db: AsyncSession) -> None:
        """Process document task.

        Downloads PDF, extracts lines via Mathpix OCR, saves lines to database,
        chunks content, saves chunks to database, and updates progress.
        Sets final status on completion or error.

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

            del pdf_bytes

            logger.info(
                "Processing document",
                extra={
                    "document_id": document_id,
                    "total_pages": total_pages,
                },
            )

            # Extract lines via Mathpix OCR if client is available
            if self._mathpix:
                await self._extract_lines_with_mathpix(
                    document, document_id, total_pages, db
                )
            else:
                logger.warning(
                    "Mathpix client not configured, skipping OCR",
                    extra={"document_id": document_id},
                )
                await self._progress.update(
                    Progress(
                        document_id=document_id,
                        page=0,
                        total=total_pages,
                        status="error",
                        message="Mathpix client not configured",
                    )
                )
                raise TaskError("Mathpix client not configured", retryable=False)

            # Chunk and save chunks
            await self._chunk_and_save(document_id, total_pages, db)

            # Mark as ready
            document.status = DocumentStatus.READY
            document.processed_at = datetime.now(timezone.utc)
            document.error = None

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
        except TaskError as e:
            # Set document status to ERROR before re-raising
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

    async def _extract_lines_with_mathpix(
        self,
        document: Document,
        document_id: int,
        total_pages: int,
        db: AsyncSession,
    ) -> None:
        """Extract lines from PDF using Mathpix OCR and save to database.

        Args:
            document: Document model instance.
            document_id: Document ID for logging.
            total_pages: Total pages in the document.
            db: Database session.

        Raises:
            TaskError: If Mathpix extraction fails.
        """
        # Get public URL for the PDF
        pdf_url = self._s3.get_file_url(document.s3_key)

        logger.info(
            "Starting Mathpix line extraction",
            extra={
                "document_id": document_id,
                "pdf_url": pdf_url,
            },
        )

        await self._progress.update(
            Progress(
                document_id=document_id,
                page=0,
                total=total_pages,
                status="processing",
                message="Extracting lines with Mathpix...",
            )
        )

        try:
            # Call Mathpix API with timeout
            lines_data = await asyncio.wait_for(
                self._mathpix.extract_lines(pdf_url),
                timeout=MATHPIX_TIMEOUT_SECONDS,
            )

            logger.info(
                "Mathpix line extraction complete",
                extra={
                    "document_id": document_id,
                    "num_pages": len(lines_data.get("pages", [])),
                },
            )

            # Convert Mathpix response to DocumentLine objects
            await self._progress.update(
                Progress(
                    document_id=document_id,
                    page=0,
                    total=total_pages,
                    status="processing",
                    message="Saving lines to database...",
                )
            )

            document_lines = self._convert_mathpix_lines_to_models(
                document_id, lines_data
            )

            # Save lines to database in bulk
            db.add_all(document_lines)
            await db.flush()

            logger.info(
                "Document lines saved",
                extra={
                    "document_id": document_id,
                    "num_lines": len(document_lines),
                },
            )

        except asyncio.TimeoutError:
            logger.error(
                "Mathpix OCR timeout",
                extra={"document_id": document_id},
            )
            raise TaskError("Mathpix OCR timeout", retryable=True)

        except asyncio.CancelledError:
            raise

        except MathpixError as e:
            logger.error(
                "Mathpix OCR failed",
                extra={
                    "document_id": document_id,
                    "error": str(e),
                    "retryable": e.retryable,
                },
            )
            raise TaskError(f"Mathpix OCR failed: {e}", retryable=e.retryable)

    def _convert_mathpix_lines_to_models(
        self, document_id: int, lines_data: dict[str, Any]
    ) -> List[DocumentLine]:
        """Convert Mathpix API response to DocumentLine objects.

        Args:
            document_id: Document ID for the lines.
            lines_data: Mathpix API response with pages and lines.

        Returns:
            List of DocumentLine objects.
        """
        document_lines: List[DocumentLine] = []
        pages = lines_data.get("pages", [])

        for page_data in pages:
            page_number = page_data.get("page", 1)
            lines = page_data.get("lines", [])

            for line_num, line_data in enumerate(lines, start=1):
                # Extract text (required)
                text = line_data.get("text", "").strip()
                if not text:
                    continue  # Skip empty lines

                # Extract line type (default to 'text')
                line_type_raw = line_data.get("type", "text")
                # Map Mathpix types to our line_type field
                if line_type_raw in ["math", "formula"]:
                    line_type = "math"
                elif line_type_raw in ["header", "title"]:
                    line_type = "section_header"
                else:
                    line_type = "text"

                # Extract metadata
                font_size = line_data.get("font_size")
                is_printed = not line_data.get("is_handwritten", False)
                is_handwritten = line_data.get("is_handwritten", False)
                confidence = line_data.get("confidence")

                # Extract region coordinates if available
                region = None
                if "region" in line_data:
                    region = line_data["region"]
                elif all(
                    key in line_data
                    for key in ["top_left_x", "top_left_y", "width", "height"]
                ):
                    region = {
                        "top_left_x": line_data.get("top_left_x"),
                        "top_left_y": line_data.get("top_left_y"),
                        "width": line_data.get("width"),
                        "height": line_data.get("height"),
                    }

                # Store full line data in raw_metadata for debugging
                raw_metadata = line_data.copy()

                document_line = DocumentLine(
                    document_id=document_id,
                    page_number=page_number,
                    line_number=line_num,
                    text=text,
                    line_type=line_type,
                    font_size=font_size,
                    is_printed=is_printed,
                    is_handwritten=is_handwritten,
                    confidence=confidence,
                    region=region,
                    raw_metadata=raw_metadata,
                )
                document_lines.append(document_line)

        return document_lines

    async def _chunk_and_save(
        self, document_id: int, total_pages: int, db: AsyncSession
    ) -> None:
        """Chunk document lines and save chunks to database.

        Loads saved DocumentLine objects, chunks them using ChunkingService
        (in thread pool to avoid blocking), and saves chunks to database.

        Args:
            document_id: Document ID.
            total_pages: Total pages in document.
            db: Database session.

        Raises:
            TaskError: If chunking or saving fails.
        """
        logger.info(
            "Starting document chunking",
            extra={"document_id": document_id},
        )

        await self._progress.update(
            Progress(
                document_id=document_id,
                page=0,
                total=total_pages,
                status="processing",
                message="Loading document lines...",
            )
        )

        # Load all document lines from database
        result = await db.execute(
            select(DocumentLine)
            .where(DocumentLine.document_id == document_id)
            .order_by(DocumentLine.page_number, DocumentLine.line_number)
        )
        lines = list(result.scalars().all())

        if not lines:
            logger.warning(
                "No document lines found for chunking",
                extra={"document_id": document_id},
            )
            return

        logger.info(
            "Loaded document lines for chunking",
            extra={"document_id": document_id, "num_lines": len(lines)},
        )

        # Update progress
        await self._progress.update(
            Progress(
                document_id=document_id,
                page=0,
                total=total_pages,
                status="processing",
                message="Chunking document...",
            )
        )

        # Chunk in thread pool (CPU-bound operation)
        try:
            chunks_data = await asyncio.to_thread(
                self._chunking_service.chunk_document_lines, lines
            )
        except Exception as e:
            logger.error(
                "Chunking failed",
                extra={"document_id": document_id, "error": str(e)},
                exc_info=True,
            )
            raise TaskError(f"Chunking failed: {e}", retryable=False)

        logger.info(
            "Document chunking complete",
            extra={
                "document_id": document_id,
                "num_chunks": len(chunks_data),
            },
        )

        # Update progress
        await self._progress.update(
            Progress(
                document_id=document_id,
                page=0,
                total=total_pages,
                status="processing",
                message="Saving chunks to database...",
            )
        )

        # Convert chunk dictionaries to DocumentChunk objects
        document_chunks = self._convert_chunks_to_models(document_id, chunks_data)

        # Save chunks to database in bulk
        db.add_all(document_chunks)
        await db.flush()

        logger.info(
            "Document chunks saved",
            extra={
                "document_id": document_id,
                "num_chunks": len(document_chunks),
            },
        )

    def _convert_chunks_to_models(
        self, document_id: int, chunks_data: List[dict[str, Any]]
    ) -> List[DocumentChunk]:
        """Convert chunk dictionaries to DocumentChunk objects.

        Args:
            document_id: Document ID for the chunks.
            chunks_data: List of chunk dictionaries from ChunkingService.

        Returns:
            List of DocumentChunk objects.
        """
        document_chunks: List[DocumentChunk] = []

        for chunk_index, chunk_data in enumerate(chunks_data):
            # Extract section_path and map to section_title
            section_path = chunk_data.get("section_path", "")
            section_title = section_path if section_path else None

            document_chunk = DocumentChunk(
                document_id=document_id,
                text=chunk_data["text"],
                chunk_index=chunk_index,
                start_page=chunk_data["start_page"],
                end_page=chunk_data["end_page"],
                start_line_id=chunk_data.get("start_line_id"),
                end_line_id=chunk_data.get("end_line_id"),
                chunk_type=chunk_data.get("chunk_type"),
                section_title=section_title,
                token_count=chunk_data.get("token_count"),
            )
            document_chunks.append(document_chunk)

        return document_chunks

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
