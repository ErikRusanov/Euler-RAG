"""Tests for API middleware components."""

import pytest
from fastapi import status
from httpx import AsyncClient


class TestAPIKeyMiddleware:
    """Test suite for API key authentication middleware."""

    @pytest.mark.asyncio
    async def test_root_endpoint_accessible_without_api_key(
        self, async_client: AsyncClient
    ):
        """Test: Root endpoint should be accessible without API key."""
        # Act
        response = await async_client.get("/")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.json()
        assert response.json()["message"] == "Euler RAG API"

    @pytest.mark.asyncio
    async def test_docs_endpoint_accessible_without_api_key(
        self, async_client: AsyncClient
    ):
        """Test: Docs endpoint should be accessible without API key."""
        # Act
        response = await async_client.get("/docs")

        # Assert
        # Docs are only enabled in development, so status should be 200
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_health_endpoint_accessible_without_api_key(
        self, async_client: AsyncClient
    ):
        """Test: Health endpoint should be accessible without API key."""
        # Act
        response = await async_client.get("/health")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_protected_endpoint_requires_api_key(self, async_client: AsyncClient):
        """Test: Protected endpoints should require API key."""
        # Act
        response = await async_client.post("/documents")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.json()
        assert response.json()["error"] == "Unauthorized"

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_invalid_api_key(
        self, async_client: AsyncClient
    ):
        """Test: Protected endpoints should reject invalid API key."""
        # Act
        response = await async_client.post(
            "/documents",
            headers={"X-API-KEY": "invalid-key"},
        )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.json()
        assert "Invalid API key" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_valid_api_key(
        self, async_client: AsyncClient, settings
    ):
        """Test: Protected endpoints should accept valid API key."""
        # Act
        response = await async_client.post(
            "/documents",
            headers={"X-API-KEY": settings.api_key},
        )

        # Assert
        # Should not return 401 (may return other status codes based on implementation)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_api_key_case_insensitive_header(
        self, async_client: AsyncClient, settings
    ):
        """Test: API key header should be case-insensitive."""
        # Act
        response = await async_client.post(
            "/documents",
            headers={"x-api-key": settings.api_key},  # lowercase
        )

        # Assert
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_requests_also_require_api_key(self, async_client: AsyncClient):
        """Test: GET requests to protected endpoints also require API key."""
        # Act
        response = await async_client.get("/documents")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_openapi_endpoint_accessible_without_api_key(
        self, async_client: AsyncClient
    ):
        """Test: OpenAPI JSON endpoint should be accessible without API key."""
        # Act
        response = await async_client.get("/openapi.json")

        # Assert
        assert response.status_code == status.HTTP_200_OK
