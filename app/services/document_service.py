"""Document service providing business logic for Document model operations.

This service extends BaseService to provide CRUD operations for Document model.
All filtering by status, subject_id, teacher_id is handled through inherited
find() method.
"""

from app.models.document import Document
from app.services.base import BaseService


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

        # Create
        document = await service.create(
            subject_id=1,
            teacher_id=2,
            filename="lecture.pdf",
            s3_key="documents/lecture.pdf",
            status=DocumentStatus.UPLOADED
        )

        # Find by filters
        ready_docs = await service.find(status=DocumentStatus.READY)
        subject_docs = await service.find(subject_id=1)

        # Update with progress
        updated = await service.update(
            document.id,
            status=DocumentStatus.PROCESSING,
            progress={"pages": 10, "total": 50}
        )

    Attributes:
        model: Document model class
        db: Database session for operations
    """

    model = Document
