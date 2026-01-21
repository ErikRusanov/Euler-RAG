"""Admin panel routes for browser-based document management."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse, StreamingResponse

from app.exceptions import RecordNotFoundError
from app.models.document import DocumentStatus
from app.services.document_service import DocumentService
from app.services.subject_service import SubjectService
from app.services.teacher_service import TeacherService
from app.utils.api_helpers import get_pagination_context, get_progress_tracker
from app.utils.dependencies import dependencies
from app.utils.templates import templates
from app.workers.progress import ProgressTracker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


@router.get("/admin/documents")
async def admin_documents(
    request: Request,
    document_service: DocumentService = Depends(dependencies.document),
    subject_service: SubjectService = Depends(dependencies.subject),
    teacher_service: TeacherService = Depends(dependencies.teacher),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    subject_id: Optional[int] = Query(default=None),
    teacher_id: Optional[int] = Query(default=None),
) -> Response:
    """Display documents list with filters and pagination.

    Args:
        request: FastAPI request object.
        document_service: DocumentService instance.
        subject_service: SubjectService instance.
        teacher_service: TeacherService instance.
        page: Current page number.
        page_size: Number of items per page.
        status_filter: Filter by document status.
        subject_id: Filter by subject ID.
        teacher_id: Filter by teacher ID.

    Returns:
        Rendered documents template.
    """
    # Convert status string to enum
    status_enum = None
    if status_filter:
        try:
            status_enum = DocumentStatus(status_filter)
        except ValueError:
            logger.warning(f"Invalid status filter: {status_filter}")

    # Get documents with relationships
    skip = (page - 1) * page_size
    documents, total = await document_service.list_with_relationships(
        skip=skip,
        limit=page_size,
        status=status_enum,
        subject_id=subject_id,
        teacher_id=teacher_id,
    )

    # Get filter options - only load subjects/teachers that have documents
    # This avoids loading 10K+ objects when most are unused
    subjects = await subject_service.get_with_documents()
    teachers = await teacher_service.get_with_documents()

    # Build context
    context = {
        "request": request,
        "active_tab": "documents",
        "documents": documents,
        "subjects": subjects,
        "teachers": teachers,
        "current_filters": {
            "status": status_filter,
            "subject_id": subject_id,
            "teacher_id": teacher_id,
        },
        "pagination": get_pagination_context(page, page_size, total),
    }

    return templates.TemplateResponse(
        request=request,
        name="admin/documents.html",
        context=context,
    )


@router.get("/admin/teachers")
async def admin_teachers(request: Request) -> Response:
    """Display coming soon page for teachers tab.

    Args:
        request: FastAPI request object.

    Returns:
        Rendered coming soon template.
    """
    return templates.TemplateResponse(
        request=request,
        name="admin/coming_soon.html",
        context={"request": request, "active_tab": "teachers", "tab_name": "Teachers"},
    )


@router.get("/admin/subjects")
async def admin_subjects(request: Request) -> Response:
    """Display coming soon page for subjects tab.

    Args:
        request: FastAPI request object.

    Returns:
        Rendered coming soon template.
    """
    return templates.TemplateResponse(
        request=request,
        name="admin/coming_soon.html",
        context={"request": request, "active_tab": "subjects", "tab_name": "Subjects"},
    )


@router.get("/admin/solutions")
async def admin_solutions(request: Request) -> Response:
    """Display coming soon page for solutions tab.

    Args:
        request: FastAPI request object.

    Returns:
        Rendered coming soon template.
    """
    return templates.TemplateResponse(
        request=request,
        name="admin/coming_soon.html",
        context={
            "request": request,
            "active_tab": "solutions",
            "tab_name": "Solutions",
        },
    )


@router.get("/admin")
async def admin_root() -> RedirectResponse:
    """Redirect /admin to /admin/documents.

    Returns:
        Redirect response to documents tab.
    """
    return RedirectResponse(url="/admin/documents", status_code=status.HTTP_302_FOUND)


@router.get("/admin/api/documents/{document_id}/progress")
async def stream_document_progress(
    document_id: int,
    document_service: DocumentService = Depends(dependencies.document),
    progress_tracker: ProgressTracker = Depends(get_progress_tracker),
) -> StreamingResponse:
    """Stream document processing progress via Server-Sent Events.

    Args:
        document_id: Document ID to track progress for.
        document_service: DocumentService instance.
        progress_tracker: ProgressTracker instance.

    Returns:
        StreamingResponse with text/event-stream content type.
    """

    async def event_generator():
        # Check document status from database
        # If document is already processing, send status update immediately
        try:
            document = await document_service.get_by_id(document_id)
            if document and document.status == DocumentStatus.PROCESSING:
                # Send status update to change UI from "pending" to "processing"
                status_update = {
                    "document_id": document_id,
                    "status": "processing",
                    "page": 0,
                    "total": 0,
                    "message": "Processing started",
                }
                yield f"data: {json.dumps(status_update)}\n\n"
        except Exception as e:
            logger.warning(
                f"Failed to check document status for {document_id}: {e}",
                exc_info=True,
            )

        # Send current progress if available
        current = await progress_tracker.get(document_id)
        if current:
            yield f"data: {json.dumps(current.to_dict())}\n\n"

        # Subscribe to updates
        async for progress in progress_tracker.subscribe(document_id):
            yield f"data: {json.dumps(progress.to_dict())}\n\n"
            if progress.status == "ready":
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/admin/api/documents/{document_id}/progress/current")
async def get_current_progress(
    document_id: int,
    progress_tracker: ProgressTracker = Depends(get_progress_tracker),
) -> Response:
    """Get current progress for a document from Redis.

    Args:
        document_id: Document ID to get progress for.
        progress_tracker: ProgressTracker instance.

    Returns:
        JSON response with progress data or 404 if not found.

    Raises:
        RecordNotFoundError: If progress not found in Redis.
    """
    progress = await progress_tracker.get(document_id)
    if not progress:
        raise RecordNotFoundError("Progress", document_id)

    return Response(
        content=json.dumps(progress.to_dict()),
        media_type="application/json",
    )
