"""Teachers API endpoints."""

from fastapi import APIRouter, Depends, Query
from fastapi import status as http_status

from app.schemas.teacher import TeacherCreate, TeacherResponse
from app.services.teacher_service import TeacherService
from app.utils.dependencies import dependencies

router = APIRouter(
    prefix="/teachers",
    tags=["Teachers"],
)


@router.get("")
async def search_teachers(
    search: str = Query(default="", description="Search term for teacher name"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    service: TeacherService = Depends(dependencies.teacher),
) -> list[TeacherResponse]:
    """Search teachers by name.

    Args:
        search: Search term to filter by name (case-insensitive).
        limit: Maximum number of results to return.
        service: TeacherService instance.

    Returns:
        List of matching teachers ordered by name.
    """
    teachers = await service.search(search=search, limit=limit)
    return [TeacherResponse.model_validate(t) for t in teachers]


@router.post("", status_code=http_status.HTTP_201_CREATED)
async def create_teacher(
    data: TeacherCreate,
    service: TeacherService = Depends(dependencies.teacher),
) -> TeacherResponse:
    """Create a new teacher.

    Args:
        data: Teacher creation data.
        service: TeacherService instance.

    Returns:
        Created teacher.
    """
    teacher = await service.create(**data.model_dump())
    return TeacherResponse.model_validate(teacher)
