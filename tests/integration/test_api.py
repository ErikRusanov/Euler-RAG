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
        """Protected endpoints under /api require API key."""
        client, _ = api_client

        response = await client.get("/api/documents")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["error"] == "Unauthorized"

    @pytest.mark.asyncio
    async def test_protected_endpoint_rejects_invalid_key(self, api_client):
        """Protected endpoints reject invalid API key."""
        client, _ = api_client

        response = await client.get(
            "/api/documents", headers={"X-API-KEY": "invalid-key"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_protected_endpoint_accepts_valid_key(self, api_client):
        """Protected endpoints accept valid API key."""
        client, settings = api_client

        # Use GET /api/documents (stub) to avoid S3 dependency
        response = await client.get(
            "/api/documents", headers={"X-API-KEY": settings.api_key}
        )

        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_api_key_header_case_insensitive(self, api_client):
        """API key header is case-insensitive."""
        client, settings = api_client

        # Use GET /api/documents (stub) to avoid S3 dependency
        response = await client.get(
            "/api/documents", headers={"x-api-key": settings.api_key}
        )

        assert response.status_code != status.HTTP_401_UNAUTHORIZED


class TestDocumentsAPI:
    """Tests for documents API endpoints (stubs only)."""

    @pytest.mark.asyncio
    async def test_list_documents_stub_response(self, api_client):
        """GET /api/documents returns stub response."""
        client, settings = api_client

        response = await client.get(
            "/api/documents", headers={"X-API-KEY": settings.api_key}
        )

        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED

    @pytest.mark.asyncio
    async def test_get_document_by_id_not_found(self, api_client):
        """GET /api/documents/{id} returns 404 for non-existent document."""
        client, settings = api_client

        response = await client.get(
            "/api/documents/123", headers={"X-API-KEY": settings.api_key}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["error"] == "Not Found"
        assert data["model"] == "Document"
        assert data["record_id"] == 123


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
