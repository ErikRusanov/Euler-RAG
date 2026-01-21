"""Teacher service providing business logic for Teacher model operations.

This service extends BaseService to provide CRUD operations for Teacher model.
All filtering by name is handled through inherited find() method.
"""

import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.exceptions import DatabaseConnectionError
from app.models.document import Document
from app.models.teacher import Teacher
from app.services.base import BaseService

logger = logging.getLogger(__name__)


class TeacherService(BaseService[Teacher]):
    """Service for managing Teacher entities.

    Provides CRUD operations through BaseService inheritance:
    - create(name): Create new teacher
    - get_by_id(id): Get teacher by ID
    - get_by_id_or_fail(id): Get teacher or raise error
    - get_all(limit, offset): Get all teachers with pagination
    - find(name=...): Find teachers by filters
    - count(name=...): Count teachers
    - update(id, **kwargs): Update teacher
    - delete(id): Delete teacher
    - get_with_documents(): Get only teachers that have documents

    Usage:
        service = TeacherService(db_session)

        # Create
        teacher = await service.create(name="Dr. Alexander Smith")

        # Find by filters
        teachers = await service.find(name="Dr. Alexander Smith")

        # Get only teachers with documents (for filters)
        teachers_with_docs = await service.get_with_documents()

    Attributes:
        model: Teacher model class
        db: Database session for operations
    """

    model = Teacher

    async def get_with_documents(self) -> List[Teacher]:
        """Get only teachers that have at least one document.

        Optimized query using DISTINCT to avoid loading all teachers.
        Only returns teachers that are referenced by documents.

        Returns:
            List of Teacher instances that have documents.

        Raises:
            DatabaseConnectionError: If database operation fails.
        """
        try:
            stmt = (
                select(Teacher)
                .join(Document, Teacher.id == Document.teacher_id)
                .distinct()
                .order_by(Teacher.name)
            )
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except (DBAPIError, SQLAlchemyError) as e:
            logger.error(
                "Failed to get teachers with documents",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise DatabaseConnectionError(
                f"Database error during get_with_documents: {str(e)}"
            ) from e

    async def search(self, search: str = "", limit: int = 10) -> List[Teacher]:
        """Search teachers by name with limit.

        Args:
            search: Search term to filter by name (case-insensitive).
            limit: Maximum number of results to return.

        Returns:
            List of matching Teacher instances ordered by name.

        Raises:
            DatabaseConnectionError: If database operation fails.
        """
        try:
            stmt = select(Teacher).order_by(Teacher.name).limit(limit)
            if search:
                stmt = stmt.where(Teacher.name.ilike(f"%{search}%"))
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except (DBAPIError, SQLAlchemyError) as e:
            logger.error(
                "Failed to search teachers",
                extra={"search": search, "error": str(e)},
                exc_info=True,
            )
            raise DatabaseConnectionError(
                f"Database error during search: {str(e)}"
            ) from e
