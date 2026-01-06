"""Subject service providing business logic for Subject model operations.

This service extends BaseService to provide CRUD operations for Subject model.
All filtering by name and semester is handled through inherited find() method.
"""

from app.models.subject import Subject
from app.services.base import BaseService


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

    Usage:
        service = SubjectService(db_session)

        # Create
        subject = await service.create(name="Mathematics", semester=1)

        # Find by filters
        subjects = await service.find(name="Mathematics", semester=1)

        # Update
        updated = await service.update(subject.id, semester=2)

    Attributes:
        model: Subject model class
        db: Database session for operations
    """

    model = Subject
