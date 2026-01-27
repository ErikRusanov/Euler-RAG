"""Unit tests for documents API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.application import create_app
from app.config import Settings
from app.models.document import Document, DocumentStatus


@pytest.fixture
def mock_document():
    """Create a mock document with UPLOADED status."""
    doc = MagicMock(spec=Document)
    doc.id = 1
    doc.filename = "test.pdf"
    doc.s3_key = "pdf/test.pdf"
    doc.status = DocumentStatus.UPLOADED
    doc.progress = {"page": 0, "total": 0}
    doc.error = None
    doc.processed_at = None
    doc.created_at = MagicMock()
    doc.updated_at = MagicMock()
    return doc


@pytest.fixture
def mock_updated_document(mock_document):
    """Create a mock document with PENDING status after update."""
    doc = MagicMock(spec=Document)
    doc.id = mock_document.id
    doc.filename = mock_document.filename
    doc.s3_key = mock_document.s3_key
    doc.status = DocumentStatus.PENDING
    doc.progress = {"page": 0, "total": 0}
    doc.error = None
    doc.processed_at = None
    doc.created_at = mock_document.created_at
    doc.updated_at = mock_document.updated_at
    return doc


class TestUpdateDocumentEnqueueFailure:
    """Tests for document update endpoint when task enqueue fails."""

    @pytest.mark.asyncio
    async def test_update_document_enqueue_failure_returns_503(
        self, settings: Settings, mock_document, mock_updated_document
    ):
        """PATCH /api/documents/{id} returns 503 when task enqueue fails.

        When changing status from UPLOADED to PENDING, the endpoint should:
        1. Update the document status to PENDING
        2. Attempt to enqueue the processing task
        3. If enqueue fails, rollback status to UPLOADED and return 503
        """
        with patch("app.application.init_db", new_callable=AsyncMock):
            with patch("app.application.close_db", new_callable=AsyncMock):
                with patch("app.application.init_s3"):
                    with patch("app.application.close_s3"):
                        app = create_app()

                        # Mock service
                        mock_service = MagicMock()
                        mock_service.get_by_id_or_fail = AsyncMock(
                            return_value=mock_document
                        )
                        mock_service.update = AsyncMock(
                            return_value=mock_updated_document
                        )

                        # Mock TaskQueue.enqueue to fail
                        with patch("app.api.documents.TaskQueue") as mock_queue_class:
                            mock_queue = MagicMock()
                            mock_queue_class.return_value = mock_queue
                            mock_queue.enqueue = AsyncMock(
                                side_effect=Exception("Redis connection failed")
                            )

                            # Override dependencies
                            from app.utils.dependencies import dependencies

                            def override_document_service():
                                return mock_service

                            app.dependency_overrides[dependencies.document] = (
                                override_document_service
                            )

                            transport = ASGITransport(app=app)
                            async with AsyncClient(
                                transport=transport, base_url="http://test"
                            ) as client:
                                response = await client.patch(
                                    "/api/documents/1",
                                    json={"status": "pending"},
                                    headers={"X-API-KEY": settings.api_key},
                                )

                                # Should return 503 Service Unavailable,
                                # not 200 OK
                                assert (
                                    response.status_code
                                    == status.HTTP_503_SERVICE_UNAVAILABLE
                                )
                                data = response.json()
                                assert data["error"] == "Service Unavailable"

                            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_document_enqueue_failure_rolls_back_status(
        self, settings: Settings, mock_document, mock_updated_document
    ):
        """Verify status is rolled back to UPLOADED when enqueue fails.

        The document status should be reverted to UPLOADED if task
        enqueueing fails, preventing documents from being stuck in PENDING.
        """
        with patch("app.application.init_db", new_callable=AsyncMock):
            with patch("app.application.close_db", new_callable=AsyncMock):
                with patch("app.application.init_s3"):
                    with patch("app.application.close_s3"):
                        app = create_app()

                        # Mock service
                        mock_service = MagicMock()
                        mock_service.get_by_id_or_fail = AsyncMock(
                            return_value=mock_document
                        )
                        mock_service.update = AsyncMock(
                            return_value=mock_updated_document
                        )

                        with patch("app.api.documents.TaskQueue") as mock_queue_class:
                            mock_queue = MagicMock()
                            mock_queue_class.return_value = mock_queue
                            mock_queue.enqueue = AsyncMock(
                                side_effect=Exception("Redis connection failed")
                            )

                            # Override dependencies
                            from app.utils.dependencies import dependencies

                            def override_document_service():
                                return mock_service

                            app.dependency_overrides[dependencies.document] = (
                                override_document_service
                            )

                            transport = ASGITransport(app=app)
                            async with AsyncClient(
                                transport=transport, base_url="http://test"
                            ) as client:
                                await client.patch(
                                    "/api/documents/1",
                                    json={"status": "pending"},
                                    headers={"X-API-KEY": settings.api_key},
                                )

                                # Verify update was called twice:
                                # 1. To set status to PENDING
                                # 2. To rollback status to UPLOADED
                                calls = mock_service.update.call_args_list
                                assert len(calls) >= 2

                                # Second call should rollback to UPLOADED
                                rollback_call = calls[1]
                                assert (
                                    rollback_call.kwargs.get("status")
                                    == DocumentStatus.UPLOADED
                                )

                            app.dependency_overrides.clear()
