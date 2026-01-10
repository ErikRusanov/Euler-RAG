"""Documents API endpoints."""

import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_document():
    """Create a new document (stub).

    This is a stub endpoint that will be implemented later.

    Returns:
        Stub response indicating endpoint is not yet implemented.
    """
    logger.info("POST /documents called (stub)")
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "message": (
                "Document creation endpoint is not yet implemented. " "This is a stub."
            ),
            "status": "stub",
        },
    )


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def list_documents():
    """List all documents (stub).

    This is a stub endpoint that will be implemented later.

    Returns:
        Stub response indicating endpoint is not yet implemented.
    """
    logger.info("GET /documents called (stub)")
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "message": (
                "Document listing endpoint is not yet implemented. " "This is a stub."
            ),
            "status": "stub",
        },
    )


@router.get("/{document_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_document(document_id: int):
    """Get document by ID (stub).

    This is a stub endpoint that will be implemented later.

    Args:
        document_id: Document ID.

    Returns:
        Stub response indicating endpoint is not yet implemented.
    """
    logger.info(f"GET /documents/{document_id} called (stub)")
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "message": (
                f"Document retrieval endpoint is not yet implemented. "
                f"This is a stub for document {document_id}."
            ),
            "status": "stub",
            "document_id": document_id,
        },
    )


@router.patch("/{document_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def update_document(document_id: int):
    """Update document by ID (stub).

    This is a stub endpoint that will be implemented later.

    Args:
        document_id: Document ID.

    Returns:
        Stub response indicating endpoint is not yet implemented.
    """
    logger.info(f"PATCH /documents/{document_id} called (stub)")
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "message": (
                f"Document update endpoint is not yet implemented. "
                f"This is a stub for document {document_id}."
            ),
            "status": "stub",
            "document_id": document_id,
        },
    )


@router.delete("/{document_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def delete_document(document_id: int):
    """Delete document by ID (stub).

    This is a stub endpoint that will be implemented later.

    Args:
        document_id: Document ID.

    Returns:
        Stub response indicating endpoint is not yet implemented.
    """
    logger.info(f"DELETE /documents/{document_id} called (stub)")
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "message": (
                f"Document deletion endpoint is not yet implemented. "
                f"This is a stub for document {document_id}."
            ),
            "status": "stub",
            "document_id": document_id,
        },
    )
