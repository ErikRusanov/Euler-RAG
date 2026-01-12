"""Documents API endpoints."""

import logging

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentStatus
from app.schemas.document import DocumentResponse, DocumentUpdate
from app.services.document_service import DocumentService
from app.utils.db import get_db_session
from app.utils.redis import get_redis_client
from app.utils.s3 import S3Storage, get_s3_storage
from app.workers.queue import TaskQueue, TaskType

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_document(
    file: UploadFile,
    db: AsyncSession = Depends(get_db_session),
    s3: S3Storage = Depends(get_s3_storage),
) -> DocumentResponse:
    """Upload a PDF document."""
    service = DocumentService(db)
    document = await service.upload_pdf(
        s3=s3,
        file_data=file.file,
        filename=file.filename or "document.pdf",
        content_type=file.content_type or "",
    )

    response = DocumentResponse.model_validate(document)
    response.url = s3.get_file_url(document.s3_key)
    return response


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def list_documents() -> JSONResponse:
    """List all documents (stub)."""
    logger.info("GET /documents called (stub)")
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"message": "Not yet implemented", "status": "stub"},
    )


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db_session),
    s3: S3Storage = Depends(get_s3_storage),
) -> DocumentResponse:
    """Get document by ID.

    Args:
        document_id: Document ID to retrieve.
        db: Database session.
        s3: S3 storage instance.

    Returns:
        Document details with presigned download URL.

    Raises:
        RecordNotFoundError: If document with given ID does not exist.
    """
    service = DocumentService(db)
    document = await service.get_by_id_or_fail(document_id)
    url = s3.get_file_url(document.s3_key)

    response = DocumentResponse.model_validate(document)
    response.url = url
    return response


@router.patch("/{document_id}")
async def update_document(
    document_id: int,
    data: DocumentUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    """Update document fields."""
    service = DocumentService(db)

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

    return DocumentResponse.model_validate(updated_document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db_session),
    s3: S3Storage = Depends(get_s3_storage),
) -> None:
    """Delete document and its file from storage."""
    service = DocumentService(db)
    await service.delete_with_file(s3, document_id)
