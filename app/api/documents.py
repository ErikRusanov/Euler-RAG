"""Documents API endpoints."""

import logging

from fastapi import APIRouter, Depends, UploadFile
from fastapi import status as http_status

from app.exceptions import TaskEnqueueError
from app.models.document import DocumentStatus
from app.schemas.document import DocumentResponse, DocumentUpdate
from app.services.document_service import DocumentService
from app.utils.dependencies import dependencies
from app.utils.redis import get_redis_client
from app.utils.s3 import S3Storage, get_s3_storage
from app.workers.queue import TaskQueue, TaskType

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.post("", status_code=http_status.HTTP_201_CREATED)
async def create_document(
    file: UploadFile,
    service: DocumentService = Depends(dependencies.document),
    s3: S3Storage = Depends(get_s3_storage),
) -> DocumentResponse:
    """Upload a PDF document."""
    document = await service.upload_pdf(
        s3=s3,
        file_data=file.file,
        filename=file.filename or "document.pdf",
        content_type=file.content_type or "",
    )

    response = DocumentResponse.model_validate(document)
    response.url = s3.get_file_url(document.s3_key)
    return response


@router.get("")
async def list_documents(
    status: DocumentStatus | None = None,
    subject_id: int | None = None,
    teacher_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    service: DocumentService = Depends(dependencies.document),
) -> list[DocumentResponse]:
    """List documents with optional filters and pagination.

    Args:
        status: Filter by document processing status.
        subject_id: Filter by subject ID.
        teacher_id: Filter by teacher ID.
        limit: Maximum number of documents to return.
        offset: Number of documents to skip.
        service: DocumentService instance.

    Returns:
        List of documents matching the filters.
    """
    filters = {}
    if status is not None:
        filters["status"] = status
    if subject_id is not None:
        filters["subject_id"] = subject_id
    if teacher_id is not None:
        filters["teacher_id"] = teacher_id

    documents = await service.find(limit=limit, offset=offset, **filters)
    return [DocumentResponse.model_validate(doc) for doc in documents]


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    service: DocumentService = Depends(dependencies.document),
    s3: S3Storage = Depends(get_s3_storage),
) -> DocumentResponse:
    """Get document by ID with relationships.

    Args:
        document_id: Document ID to retrieve.
        service: DocumentService instance.
        s3: S3 storage instance.

    Returns:
        Document details with direct file URL and related entity names.

    Raises:
        RecordNotFoundError: If document with given ID does not exist.
    """
    from app.exceptions import RecordNotFoundError

    document = await service.get_with_relationships(document_id)
    if not document:
        raise RecordNotFoundError("Document", document_id)

    url = s3.get_file_url(document.s3_key)

    response = DocumentResponse.model_validate(document)
    response.url = url

    # Add related entity names if loaded
    if document.subject:
        response.subject_name = document.subject.name
        response.subject_semester = document.subject.semester
    if document.teacher:
        response.teacher_name = document.teacher.name

    return response


@router.patch("/{document_id}")
async def update_document(
    document_id: int,
    data: DocumentUpdate,
    service: DocumentService = Depends(dependencies.document),
) -> DocumentResponse:
    """Update document fields."""

    current_document = await service.get_by_id_or_fail(document_id)
    update_data = data.model_dump(exclude_unset=True)

    # Check if status is being changed from UPLOADED to PENDING
    new_status = update_data.get("status")
    should_enqueue = (
        current_document.status == DocumentStatus.UPLOADED
        and "status" in update_data
        and (
            new_status == DocumentStatus.PENDING
            or (
                isinstance(new_status, str)
                and new_status == DocumentStatus.PENDING.value
            )
        )
    )

    updated_document = await service.update_document(document_id, **update_data)

    if should_enqueue:
        try:
            queue = TaskQueue(get_redis_client())
            await queue.enqueue(TaskType.DOCUMENT_PROCESS, {"document_id": document_id})
        except Exception as e:
            logger.error(
                "Failed to enqueue document processing task",
                extra={"document_id": document_id, "error": str(e)},
                exc_info=True,
            )
            # Rollback status to UPLOADED to prevent document being stuck in PENDING
            await service.update_document(document_id, status=DocumentStatus.UPLOADED)
            raise TaskEnqueueError(
                task_type=TaskType.DOCUMENT_PROCESS.value,
                resource_id=document_id,
                original_error=str(e),
            )

    return DocumentResponse.model_validate(updated_document)


@router.delete("/{document_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    service: DocumentService = Depends(dependencies.document),
    s3: S3Storage = Depends(get_s3_storage),
) -> None:
    """Delete document and its file from storage."""
    await service.delete_with_file(s3, document_id)
