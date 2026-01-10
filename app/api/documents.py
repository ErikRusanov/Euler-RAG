"""Documents API endpoints."""

import logging

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService
from app.utils.db import get_db_session
from app.utils.s3 import S3Storage, get_s3_storage

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
    return await service.upload_pdf(
        s3=s3,
        file_data=file.file,
        filename=file.filename or "document.pdf",
        content_type=file.content_type or "",
    )


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def list_documents() -> JSONResponse:
    """List all documents (stub)."""
    logger.info("GET /documents called (stub)")
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"message": "Not yet implemented", "status": "stub"},
    )


@router.get("/{document_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_document(document_id: int) -> JSONResponse:
    """Get document by ID (stub)."""
    logger.info(f"GET /documents/{document_id} called (stub)")
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"message": "Not yet implemented", "document_id": document_id},
    )


@router.patch("/{document_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def update_document(document_id: int) -> JSONResponse:
    """Update document by ID (stub)."""
    logger.info(f"PATCH /documents/{document_id} called (stub)")
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"message": "Not yet implemented", "document_id": document_id},
    )


@router.delete("/{document_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def delete_document(document_id: int) -> JSONResponse:
    """Delete document by ID (stub)."""
    logger.info(f"DELETE /documents/{document_id} called (stub)")
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"message": "Not yet implemented", "document_id": document_id},
    )
