"""SolveRequest service for question solving request operations.

This service extends BaseService to provide CRUD operations for SolveRequest
model. All filtering is handled through inherited find() method.
"""

from app.models.solve_request import SolveRequest
from app.services.base import BaseService


class SolveRequestService(BaseService[SolveRequest]):
    """Service for managing SolveRequest entities.

    Provides CRUD operations through BaseService inheritance:
    - create(**kwargs): Create new solve request
    - get_by_id(id): Get request by ID
    - get_by_id_or_fail(id): Get request or raise error
    - get_all(limit, offset): Get all requests with pagination
    - find(...): Find requests by filters (status, subject_filter, etc.)
    - count(...): Count requests
    - update(id, **kwargs): Update request
    - delete(id): Delete request

    Usage:
        service = SolveRequestService(db_session)

        # Create
        request = await service.create(
            question="What is calculus?",
            subject_filter="Mathematics",
            status=SolveRequestStatus.PENDING
        )

        # Find by filters
        ready_requests = await service.find(status=SolveRequestStatus.READY)
        rag_requests = await service.find(used_rag=True)

        # Update with answer
        updated = await service.update(
            request.id,
            answer="Calculus is...",
            chunks_used=[...],
            used_rag=True,
            status=SolveRequestStatus.READY
        )

    Attributes:
        model: SolveRequest model class
        db: Database session for operations
    """

    model = SolveRequest
