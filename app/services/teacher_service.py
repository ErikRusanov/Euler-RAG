"""Teacher service providing business logic for Teacher model operations.

This service extends BaseService to provide CRUD operations for Teacher model.
All filtering by name is handled through inherited find() method.
"""

from app.models.teacher import Teacher
from app.services.base import BaseService


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

    Usage:
        service = TeacherService(db_session)

        # Create
        teacher = await service.create(name="Dr. Alexander Smith")

        # Find by filters
        teachers = await service.find(name="Dr. Alexander Smith")

        # Update
        updated = await service.update(teacher.id, name="Professor Smith")

    Attributes:
        model: Teacher model class
        db: Database session for operations
    """

    model = Teacher
