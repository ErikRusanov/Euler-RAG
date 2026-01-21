"""Document service providing business logic for Document model operations.

This service extends BaseService to provide CRUD operations for Document model.
All filtering by status, subject_id, teacher_id is handled through inherited
find() method.
"""

import logging
from typing import Any, BinaryIO, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.exceptions import InvalidFileTypeError, RelatedRecordNotFoundError
from app.models.document import Document
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.services.base import BaseService
from app.utils.s3 import S3Storage

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = ["application/pdf"]
PDF_FOLDER = "pdf"


class DocumentService(BaseService[Document]):
    """Service for managing Document entities.

    Provides CRUD operations through BaseService inheritance:
    - create(**kwargs): Create new document
    - get_by_id(id): Get document by ID
    - get_by_id_or_fail(id): Get document or raise error
    - get_all(limit, offset): Get all documents with pagination
    - find(status=..., subject_id=..., teacher_id=...): Find documents by filters
    - count(status=..., subject_id=..., teacher_id=...): Count documents
    - update(id, **kwargs): Update document
    - delete(id): Delete document

    Usage:
        service = DocumentService(db_session)

        # Upload PDF
        document = await service.upload_pdf(s3, file, "lecture.pdf", "application/pdf")

        # Find by filters
        ready_docs = await service.find(status=DocumentStatus.READY)

    Attributes:
        model: Document model class
        db: Database session for operations
    """

    model = Document

    async def upload_pdf(
        self,
        s3: S3Storage,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
    ) -> Document:
        """Upload PDF file to S3 and create document record.

        Args:
            s3: S3 storage instance.
            file_data: File binary data.
            filename: Original filename.
            content_type: File MIME type.

        Returns:
            Created Document instance.

        Raises:
            InvalidFileTypeError: If file is not a PDF.
            S3OperationError: If S3 upload fails.
            DatabaseConnectionError: If database operation fails.
        """
        if content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(
                "Invalid file type upload attempt",
                extra={"content_type": content_type, "original_filename": filename},
            )
            raise InvalidFileTypeError(ALLOWED_CONTENT_TYPES, content_type)

        s3_key = s3.upload_file(
            file_data, filename, folder=PDF_FOLDER, content_type=content_type
        )
        document = await self.create(filename=filename, s3_key=s3_key)

        logger.info(
            "Document uploaded successfully",
            extra={"document_id": document.id, "s3_key": s3_key},
        )
        return document

    async def delete_with_file(self, s3: S3Storage, document_id: int) -> None:
        """Delete document record and its file from S3.

        Args:
            s3: S3 storage instance.
            document_id: Document ID to delete.

        Raises:
            RecordNotFoundError: If document not found.
            S3OperationError: If S3 deletion fails.
            DatabaseConnectionError: If database operation fails.
        """
        document = await self.get_by_id_or_fail(document_id)
        s3_key = document.s3_key

        s3.delete_file(s3_key)
        await self.delete(document_id)

        logger.info(
            "Document deleted successfully",
            extra={"document_id": document_id, "s3_key": s3_key},
        )

    async def update_document(
        self,
        document_id: int,
        subject_id: Optional[int] = None,
        teacher_id: Optional[int] = None,
        **kwargs: Any,
    ) -> Document:
        """Update document with FK validation.

        Args:
            document_id: Document ID to update.
            subject_id: Optional subject ID (validated if provided).
            teacher_id: Optional teacher ID (validated if provided).
            **kwargs: Other fields to update.

        Returns:
            Updated Document instance.

        Raises:
            RecordNotFoundError: If document not found.
            RelatedRecordNotFoundError: If subject/teacher not found.
            DatabaseConnectionError: If database operation fails.
        """
        if subject_id is not None:
            result = await self.db.execute(
                select(Subject).where(Subject.id == subject_id)
            )
            subject = result.scalar_one_or_none()
            if not subject:
                raise RelatedRecordNotFoundError("subject_id", subject_id)
            kwargs["subject_id"] = subject_id

        if teacher_id is not None:
            result = await self.db.execute(
                select(Teacher).where(Teacher.id == teacher_id)
            )
            teacher = result.scalar_one_or_none()
            if not teacher:
                raise RelatedRecordNotFoundError("teacher_id", teacher_id)
            kwargs["teacher_id"] = teacher_id

        return await self.update(document_id, **kwargs)

    async def get_with_relationships(self, document_id: int) -> Optional[Document]:
        """Get a document by ID with eager-loaded relationships.

        Args:
            document_id: Document ID to retrieve.

        Returns:
            Document with loaded subject and teacher, or None if not found.

        Raises:
            DatabaseConnectionError: If database operation fails.
        """
        stmt = (
            select(Document)
            .options(selectinload(Document.subject), selectinload(Document.teacher))
            .where(Document.id == document_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_relationships(
        self,
        skip: int = 0,
        limit: int = 20,
        status: Optional[Any] = None,
        subject_id: Optional[int] = None,
        teacher_id: Optional[int] = None,
    ) -> tuple[list[Document], int]:
        """Get documents with eager-loaded relationships.

        Optimized query that loads subject and teacher in a single query
        using selectinload to prevent N+1 query problems.

        Args:
            skip: Number of records to skip for pagination.
            limit: Maximum number of records to return.
            status: Filter by document status.
            subject_id: Filter by subject ID.
            teacher_id: Filter by teacher ID.

        Returns:
            Tuple of (documents list, total count).

        Raises:
            DatabaseConnectionError: If database operation fails.
        """
        # Build base query with eager loading
        stmt = (
            select(Document)
            .options(selectinload(Document.subject), selectinload(Document.teacher))
            .order_by(Document.created_at.desc())
        )

        # Apply filters
        if status is not None:
            stmt = stmt.where(Document.status == status)
        if subject_id is not None:
            stmt = stmt.where(Document.subject_id == subject_id)
        if teacher_id is not None:
            stmt = stmt.where(Document.teacher_id == teacher_id)

        # Get total count
        count_stmt = select(func.count()).select_from(Document)
        if status is not None:
            count_stmt = count_stmt.where(Document.status == status)
        if subject_id is not None:
            count_stmt = count_stmt.where(Document.subject_id == subject_id)
        if teacher_id is not None:
            count_stmt = count_stmt.where(Document.teacher_id == teacher_id)

        total = await self.db.scalar(count_stmt)

        # Apply pagination
        stmt = stmt.offset(skip).limit(limit)

        # Execute query
        result = await self.db.execute(stmt)
        documents = list(result.scalars().all())

        return documents, total or 0
