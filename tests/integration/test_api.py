"""Integration tests for API endpoints and middleware."""

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.config import Settings


@pytest.fixture
async def api_client(app, settings: Settings):
    """Create async test client for API testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, settings


class TestAPIKeyMiddleware:
    """Tests for API key authentication middleware."""

    @pytest.mark.asyncio
    async def test_public_endpoints_accessible_without_key(self, api_client):
        """Public endpoints are accessible without API key."""
        client, _ = api_client

        for path in ["/", "/health", "/docs", "/openapi.json"]:
            response = await client.get(path)
            assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_protected_endpoint_requires_key(self, api_client):
        """Protected endpoints require API key."""
        client, _ = api_client

        response = await client.post("/documents")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["error"] == "Unauthorized"

    @pytest.mark.asyncio
    async def test_protected_endpoint_rejects_invalid_key(self, api_client):
        """Protected endpoints reject invalid API key."""
        client, _ = api_client

        response = await client.post("/documents", headers={"X-API-KEY": "invalid-key"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_protected_endpoint_accepts_valid_key(self, api_client):
        """Protected endpoints accept valid API key."""
        client, settings = api_client

        response = await client.post(
            "/documents", headers={"X-API-KEY": settings.api_key}
        )

        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_api_key_header_case_insensitive(self, api_client):
        """API key header is case-insensitive."""
        client, settings = api_client

        response = await client.post(
            "/documents", headers={"x-api-key": settings.api_key}
        )

        assert response.status_code != status.HTTP_401_UNAUTHORIZED


class TestDocumentsAPI:
    """Tests for documents API endpoints."""

    @pytest.mark.asyncio
    async def test_create_document_stub_response(self, api_client):
        """POST /documents returns stub response."""
        client, settings = api_client

        response = await client.post(
            "/documents", headers={"X-API-KEY": settings.api_key}
        )

        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
        data = response.json()
        assert "message" in data

    @pytest.mark.asyncio
    async def test_list_documents_stub_response(self, api_client):
        """GET /documents returns stub response."""
        client, settings = api_client

        response = await client.get(
            "/documents", headers={"X-API-KEY": settings.api_key}
        )

        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED

    @pytest.mark.asyncio
    async def test_get_document_by_id_stub_response(self, api_client):
        """GET /documents/{id} returns stub response."""
        client, settings = api_client

        response = await client.get(
            "/documents/123", headers={"X-API-KEY": settings.api_key}
        )

        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED

    @pytest.mark.asyncio
    async def test_update_document_stub_response(self, api_client):
        """PATCH /documents/{id} returns stub response with document_id."""
        client, settings = api_client

        response = await client.patch(
            "/documents/123", headers={"X-API-KEY": settings.api_key}
        )

        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
        data = response.json()
        assert data["document_id"] == 123

    @pytest.mark.asyncio
    async def test_delete_document_stub_response(self, api_client):
        """DELETE /documents/{id} returns stub response."""
        client, settings = api_client

        response = await client.delete(
            "/documents/123", headers={"X-API-KEY": settings.api_key}
        )

        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_status(self, api_client):
        """Health endpoint returns healthy status."""
        client, _ = api_client

        response = await client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
