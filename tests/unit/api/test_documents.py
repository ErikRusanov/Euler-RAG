"""Tests for documents API endpoints."""

import pytest
from fastapi import status
from httpx import AsyncClient


class TestDocumentsAPI:
    """Test suite for documents API endpoints."""

    @pytest.mark.asyncio
    async def test_create_document_requires_api_key(self, async_client: AsyncClient):
        """Test: POST /documents should require API key."""
        # Act
        response = await async_client.post("/documents")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_create_document_with_valid_api_key(
        self, async_client: AsyncClient, settings
    ):
        """Test: POST /documents should accept valid API key."""
        # Act
        response = await async_client.post(
            "/documents",
            headers={"X-API-KEY": settings.api_key},
        )

        # Assert
        # For now it's a stub, so we expect 501 Not Implemented or similar
        # But definitely not 401 Unauthorized
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_create_document_stub_response(
        self, async_client: AsyncClient, settings
    ):
        """Test: POST /documents stub should return appropriate response."""
        # Act
        response = await async_client.post(
            "/documents",
            headers={"X-API-KEY": settings.api_key},
        )

        # Assert
        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
        data = response.json()
        assert "message" in data
        assert (
            "stub" in data["message"].lower()
            or "implemented" in data["message"].lower()
        )

    @pytest.mark.asyncio
    async def test_list_documents_requires_api_key(self, async_client: AsyncClient):
        """Test: GET /documents should require API key."""
        # Act
        response = await async_client.get("/documents")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_list_documents_with_valid_api_key(
        self, async_client: AsyncClient, settings
    ):
        """Test: GET /documents should accept valid API key."""
        # Act
        response = await async_client.get(
            "/documents",
            headers={"X-API-KEY": settings.api_key},
        )

        # Assert
        # For now it's a stub, so we expect 501 Not Implemented
        # But definitely not 401 Unauthorized
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_document_by_id_requires_api_key(self, async_client: AsyncClient):
        """Test: GET /documents/{id} should require API key."""
        # Act
        response = await async_client.get("/documents/123")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_document_by_id_with_valid_api_key(
        self, async_client: AsyncClient, settings
    ):
        """Test: GET /documents/{id} should accept valid API key."""
        # Act
        response = await async_client.get(
            "/documents/123",
            headers={"X-API-KEY": settings.api_key},
        )

        # Assert
        # For now it's a stub, so we expect 501 Not Implemented
        # But definitely not 401 Unauthorized
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_update_document_requires_api_key(self, async_client: AsyncClient):
        """Test: PATCH /documents/{id} should require API key."""
        # Act
        response = await async_client.patch("/documents/123")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_update_document_with_valid_api_key(
        self, async_client: AsyncClient, settings
    ):
        """Test: PATCH /documents/{id} should accept valid API key."""
        # Act
        response = await async_client.patch(
            "/documents/123",
            headers={"X-API-KEY": settings.api_key},
        )

        # Assert
        # For now it's a stub, so we expect 501 Not Implemented
        # But definitely not 401 Unauthorized
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_update_document_stub_response(
        self, async_client: AsyncClient, settings
    ):
        """Test: PATCH /documents/{id} stub should return appropriate response."""
        # Act
        response = await async_client.patch(
            "/documents/123",
            headers={"X-API-KEY": settings.api_key},
        )

        # Assert
        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
        data = response.json()
        assert "message" in data
        assert (
            "stub" in data["message"].lower()
            or "implemented" in data["message"].lower()
        )
        assert data["document_id"] == 123

    @pytest.mark.asyncio
    async def test_delete_document_requires_api_key(self, async_client: AsyncClient):
        """Test: DELETE /documents/{id} should require API key."""
        # Act
        response = await async_client.delete("/documents/123")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_delete_document_with_valid_api_key(
        self, async_client: AsyncClient, settings
    ):
        """Test: DELETE /documents/{id} should accept valid API key."""
        # Act
        response = await async_client.delete(
            "/documents/123",
            headers={"X-API-KEY": settings.api_key},
        )

        # Assert
        # For now it's a stub, so we expect 501 Not Implemented
        # But definitely not 401 Unauthorized
        assert response.status_code != status.HTTP_401_UNAUTHORIZED
