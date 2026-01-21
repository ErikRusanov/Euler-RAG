"""Subject service providing business logic for Subject model operations.

This service extends BaseService to provide CRUD operations for Subject model.
All filtering by name and semester is handled through inherited find() method.
"""

import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.exceptions import DatabaseConnectionError
from app.models.document import Document
from app.models.subject import Subject
from app.services.base import BaseService

logger = logging.getLogger(__name__)


class SubjectService(BaseService[Subject]):
    """Service for managing Subject entities.

    Provides CRUD operations through BaseService inheritance:
    - create(name, semester): Create new subject
    - get_by_id(id): Get subject by ID
    - get_by_id_or_fail(id): Get subject or raise error
    - get_all(limit, offset): Get all subjects with pagination
    - find(name=..., semester=...): Find subjects by filters
    - count(name=..., semester=...): Count subjects
    - update(id, **kwargs): Update subject
    - delete(id): Delete subject
    - get_with_documents(): Get only subjects that have documents

    Usage:
        service = SubjectService(db_session)

        # Create
        subject = await service.create(name="Mathematics", semester=1)

        # Find by filters
        subjects = await service.find(name="Mathematics", semester=1)

        # Get only subjects with documents (for filters)
        subjects_with_docs = await service.get_with_documents()

    Attributes:
        model: Subject model class
        db: Database session for operations
    """

    model = Subject

    async def get_with_documents(self) -> List[Subject]:
        """Get only subjects that have at least one document.

        Optimized query using DISTINCT to avoid loading all subjects.
        Only returns subjects that are referenced by documents.

        Returns:
            List of Subject instances that have documents.

        Raises:
            DatabaseConnectionError: If database operation fails.
        """
        try:
            stmt = (
                select(Subject)
                .join(Document, Subject.id == Document.subject_id)
                .distinct()
                .order_by(Subject.name, Subject.semester)
            )
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except (DBAPIError, SQLAlchemyError) as e:
            logger.error(
                "Failed to get subjects with documents",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise DatabaseConnectionError(
                f"Database error during get_with_documents: {str(e)}"
            ) from e
