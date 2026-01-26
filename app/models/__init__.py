"""Data models package."""

from app.exceptions import (
    DatabaseConnectionError,
    InvalidFilterError,
    ModelError,
    RecordNotFoundError,
)
from app.models.base import BaseModel
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_line import DocumentLine
from app.models.solve_request import SolveRequest, SolveRequestStatus
from app.models.subject import Subject
from app.models.teacher import Teacher

__all__ = [
    "BaseModel",
    "ModelError",
    "RecordNotFoundError",
    "DatabaseConnectionError",
    "InvalidFilterError",
    "Subject",
    "Teacher",
    "Document",
    "DocumentStatus",
    "DocumentLine",
    "DocumentChunk",
    "SolveRequest",
    "SolveRequestStatus",
]
