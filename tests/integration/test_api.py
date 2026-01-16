"""Integration tests for API endpoints and middleware."""

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.middleware.cookie_auth import COOKIE_NAME, generate_session_token


@pytest.fixture
async def api_client(app, settings: Settings):
    """Create async test client for API testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, settings


@pytest.fixture
async def authenticated_client(app, settings: Settings):
    """Create async test client with valid session cookie."""
    transport = ASGITransport(app=app)
    session_token = generate_session_token(settings.api_key)
    cookies = {COOKIE_NAME: session_token}
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=cookies
    ) as client:
        yield client, settings


class TestCookieAuthMiddleware:
    """Tests for cookie-based authentication middleware."""

    @pytest.mark.asyncio
    async def test_public_endpoints_redirect_without_cookie(self, api_client):
        """Public endpoints redirect to login without valid cookie."""
        client, _ = api_client

        response = await client.get("/", follow_redirects=False)

        assert response.status_code == status.HTTP_302_FOUND
        assert response.headers["location"] == "/login?next=/"

    @pytest.mark.asyncio
    async def test_public_endpoints_accessible_with_cookie(self, authenticated_client):
        """Public endpoints accessible with valid session cookie."""
        client, _ = authenticated_client

        response = await client.get("/")

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_health_endpoint_requires_cookie(self, api_client):
        """Health endpoint requires cookie authentication."""
        client, _ = api_client

        response = await client.get("/health", follow_redirects=False)

        assert response.status_code == status.HTTP_302_FOUND

    @pytest.mark.asyncio
    async def test_health_endpoint_accessible_with_cookie(self, authenticated_client):
        """Health endpoint accessible with valid cookie."""
        client, _ = authenticated_client

        response = await client.get("/health")

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_login_page_accessible_without_cookie(self, api_client):
        """Login page is accessible without authentication."""
        client, _ = api_client

        response = await client.get("/login")

        assert response.status_code == status.HTTP_200_OK
        assert "Euler RAG" in response.text

    @pytest.mark.asyncio
    async def test_invalid_cookie_redirects_to_login(self, app, settings):
        """Invalid session cookie redirects to login."""
        transport = ASGITransport(app=app)
        cookies = {COOKIE_NAME: "invalid-token"}
        async with AsyncClient(
            transport=transport, base_url="http://test", cookies=cookies
        ) as client:
            response = await client.get("/", follow_redirects=False)

            assert response.status_code == status.HTTP_302_FOUND
            assert "/login" in response.headers["location"]


class TestAuthRoutes:
    """Tests for authentication routes (login, logout)."""

    @pytest.mark.asyncio
    async def test_login_page_returns_html_form(self, api_client):
        """GET /login returns HTML login form."""
        client, _ = api_client

        response = await client.get("/login")

        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]
        assert '<form method="post" action="/auth">' in response.text
        assert 'name="api_key"' in response.text

    @pytest.mark.asyncio
    async def test_login_page_includes_next_url(self, api_client):
        """GET /login preserves next URL parameter."""
        client, _ = api_client

        response = await client.get("/login?next=/health")

        assert response.status_code == status.HTTP_200_OK
        assert 'value="/health"' in response.text

    @pytest.mark.asyncio
    async def test_auth_valid_key_sets_cookie_and_redirects(self, api_client):
        """POST /auth with valid key sets cookie and redirects."""
        client, settings = api_client

        response = await client.post(
            "/auth",
            data={"api_key": settings.api_key, "next": "/health"},
            follow_redirects=False,
        )

        assert response.status_code == status.HTTP_302_FOUND
        assert response.headers["location"] == "/health"
        assert COOKIE_NAME in response.cookies

    @pytest.mark.asyncio
    async def test_auth_invalid_key_returns_403(self, api_client):
        """POST /auth with invalid key returns 403 Forbidden page."""
        client, _ = api_client

        response = await client.post(
            "/auth",
            data={"api_key": "wrong-key", "next": "/"},
            follow_redirects=False,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "403" in response.text
        assert "Access Forbidden" in response.text

    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self, authenticated_client):
        """POST /logout clears session cookie."""
        client, _ = authenticated_client

        response = await client.post("/logout", follow_redirects=False)

        assert response.status_code == status.HTTP_302_FOUND
        # Cookie should be deleted (set to empty or with max-age=0)
        assert COOKIE_NAME in response.headers.get("set-cookie", "")


class TestAPIKeyMiddleware:
    """Tests for API key authentication middleware."""

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

        response = await client.get(
            "/api/documents", headers={"X-API-KEY": settings.api_key}
        )

        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_api_key_header_case_insensitive(self, api_client):
        """API key header is case-insensitive."""
        client, settings = api_client

        response = await client.get(
            "/api/documents", headers={"x-api-key": settings.api_key}
        )

        assert response.status_code != status.HTTP_401_UNAUTHORIZED


class TestDocumentsAPI:
    """Tests for documents API endpoints."""

    @pytest.mark.asyncio
    async def test_list_documents_empty(self, api_client):
        """GET /api/documents returns empty list when no documents."""
        client, settings = api_client

        response = await client.get(
            "/api/documents", headers={"X-API-KEY": settings.api_key}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_documents_with_filters_and_pagination(self, api_client):
        """GET /api/documents accepts filter and pagination query params."""
        client, settings = api_client

        response = await client.get(
            "/api/documents?status=ready&subject_id=1&teacher_id=2&limit=10&offset=0",
            headers={"X-API-KEY": settings.api_key},
        )

        assert response.status_code == status.HTTP_200_OK

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
    async def test_health_returns_status(self, authenticated_client):
        """Health endpoint returns healthy status."""
        client, _ = authenticated_client

        response = await client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
