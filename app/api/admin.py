"""Admin panel routes for browser-based document management."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import RecordNotFoundError
from app.models.document import DocumentStatus
from app.services.document_service import DocumentService
from app.services.subject_service import SubjectService
from app.services.teacher_service import TeacherService
from app.utils.db import get_db_session
from app.utils.redis import get_redis_client
from app.utils.s3 import S3Storage, get_s3_storage
from app.utils.templates import templates
from app.workers.queue import TaskQueue, TaskType

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


def get_pagination_context(page: int, page_size: int, total: int) -> dict:
    """Calculate pagination metadata.

    Args:
        page: Current page number (1-indexed).
        page_size: Items per page.
        total: Total number of items.

    Returns:
        Dictionary with pagination metadata.
    """
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    start = (page - 1) * page_size + 1 if total > 0 else 0
    end = min(page * page_size, total)

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "start": start,
        "end": end,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


@router.get("/admin/documents")
async def admin_documents(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    subject_id: Optional[int] = Query(default=None),
    teacher_id: Optional[int] = Query(default=None),
) -> Response:
    """Display documents list with filters and pagination.

    Args:
        request: FastAPI request object.
        db: Database session.
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
    document_service = DocumentService(db)
    skip = (page - 1) * page_size
    documents, total = await document_service.list_with_relationships(
        skip=skip,
        limit=page_size,
        status=status_enum,
        subject_id=subject_id,
        teacher_id=teacher_id,
    )

    # Get filter options
    subject_service = SubjectService(db)
    teacher_service = TeacherService(db)
    subjects = await subject_service.get_all()
    teachers = await teacher_service.get_all()

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


@router.get("/admin/documents/{document_id}/download")
async def download_document_pdf(
    document_id: int,
    db: AsyncSession = Depends(get_db_session),
    s3: S3Storage = Depends(get_s3_storage),
) -> RedirectResponse:
    """Get presigned URL and redirect to PDF file.

    Args:
        document_id: Document ID to download.
        db: Database session.
        s3: S3 storage instance.

    Returns:
        Redirect to presigned S3 URL.
    """
    document_service = DocumentService(db)

    try:
        document = await document_service.get_by_id_or_fail(document_id)
        presigned_url = s3.get_file_url(document.s3_key)
        return RedirectResponse(url=presigned_url)
    except RecordNotFoundError:
        return RedirectResponse(url="/404", status_code=status.HTTP_404_NOT_FOUND)


@router.get("/admin/documents/{document_id}/view")
async def view_document_modal(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Return modal content for viewing document details.

    Args:
        request: FastAPI request object.
        document_id: Document ID to view.
        db: Database session.

    Returns:
        Rendered modal template.
    """
    document_service = DocumentService(db)

    try:
        # Get document by ID
        document = await document_service.get_by_id_or_fail(document_id)

        # Manually load relationships
        if document.subject_id:
            subject_service = SubjectService(db)
            document.subject = await subject_service.get_by_id(document.subject_id)
        if document.teacher_id:
            teacher_service = TeacherService(db)
            document.teacher = await teacher_service.get_by_id(document.teacher_id)

    except RecordNotFoundError:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/components/view_modal.html",
        context={"request": request, "document": document},
    )


@router.delete("/admin/documents/{document_id}/delete")
async def delete_document(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db_session),
    s3: S3Storage = Depends(get_s3_storage),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    subject_id: Optional[int] = Query(default=None),
    teacher_id: Optional[int] = Query(default=None),
) -> Response:
    """Delete a document and its file from S3.

    Args:
        request: FastAPI request object.
        document_id: Document ID to delete.
        db: Database session.
        s3: S3 storage instance.
        page: Current page number.
        page_size: Number of items per page.
        status_filter: Filter by document status.
        subject_id: Filter by subject ID.
        teacher_id: Filter by teacher ID.

    Returns:
        Redirect to documents list or error.
    """
    document_service = DocumentService(db)

    try:
        await document_service.delete_with_file(s3, document_id)
        logger.info(f"Document {document_id} deleted via admin panel")
    except RecordNotFoundError:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Return full documents content for HTMX swap
    return await admin_documents(
        request, db, page, page_size, status_filter, subject_id, teacher_id
    )


@router.post("/admin/documents/{document_id}/start")
async def start_processing(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    subject_id: Optional[int] = Query(default=None),
    teacher_id: Optional[int] = Query(default=None),
) -> Response:
    """Update document status to PENDING to start processing.

    Args:
        request: FastAPI request object.
        document_id: Document ID to start processing.
        db: Database session.
        page: Current page number.
        page_size: Number of items per page.
        status_filter: Filter by document status.
        subject_id: Filter by subject ID.
        teacher_id: Filter by teacher ID.

    Returns:
        Redirect to documents list or error.
    """
    document_service = DocumentService(db)

    try:
        # Update document status to PENDING
        await document_service.update_document(
            document_id, status=DocumentStatus.PENDING
        )
        logger.info(f"Document {document_id} processing started via admin panel")

        # Enqueue task for processing
        try:
            queue = TaskQueue(get_redis_client())
            await queue.enqueue(TaskType.DOCUMENT_PROCESS, {"document_id": document_id})
            logger.info(f"Document {document_id} enqueued for processing")
        except Exception as e:
            logger.error(
                "Failed to enqueue document processing task",
                extra={"document_id": document_id, "error": str(e)},
                exc_info=True,
            )
    except RecordNotFoundError:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Return full documents content for HTMX swap
    return await admin_documents(
        request, db, page, page_size, status_filter, subject_id, teacher_id
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
