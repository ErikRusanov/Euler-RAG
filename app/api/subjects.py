"""Subjects API endpoints."""

from fastapi import APIRouter, Depends, Query
from fastapi import status as http_status

from app.exceptions import DatabaseConnectionError, DuplicateRecordError
from app.schemas.subject import SubjectCreate, SubjectResponse
from app.services.subject_service import SubjectService
from app.utils.dependencies import dependencies

router = APIRouter(
    prefix="/subjects",
    tags=["Subjects"],
)


@router.get("")
async def search_subjects(
    search: str = Query(default="", description="Search term for subject name"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    service: SubjectService = Depends(dependencies.subject),
) -> list[SubjectResponse]:
    """Search subjects by name.

    Args:
        search: Search term to filter by name (case-insensitive).
        limit: Maximum number of results to return.
        service: SubjectService instance.

    Returns:
        List of matching subjects ordered by name and semester.
    """
    subjects = await service.search(search=search, limit=limit)
    return [SubjectResponse.model_validate(s) for s in subjects]


@router.post("", status_code=http_status.HTTP_201_CREATED)
async def create_subject(
    data: SubjectCreate,
    service: SubjectService = Depends(dependencies.subject),
) -> SubjectResponse:
    """Create a new subject.

    Args:
        data: Subject creation data.
        service: SubjectService instance.

    Returns:
        Created subject.

    Raises:
        DuplicateRecordError: If subject with same name and semester exists.
    """
    try:
        subject = await service.create(**data.model_dump())
        return SubjectResponse.model_validate(subject)
    except DatabaseConnectionError as e:
        if "integrity" in str(e).lower() or "constraint" in str(e).lower():
            raise DuplicateRecordError(
                model_name="Subject",
                detail=f"Subject '{data.name}' for semester {data.semester} "
                "already exists",
            ) from e
        raise
