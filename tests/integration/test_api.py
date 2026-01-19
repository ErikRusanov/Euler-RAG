"""Integration tests for API endpoints and middleware."""

import json

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from app.config import Settings
from app.middleware.cookie_auth import COOKIE_NAME, generate_session_token
from app.workers.progress import Progress, ProgressTracker


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
    async def test_nonexistent_public_path_returns_404(self, api_client):
        """Non-existent public paths return 404 (no redirect to login)."""
        client, _ = api_client

        # Use Accept: application/json to get JSON response
        response = await client.get(
            "/some-nonexistent-page",
            headers={"Accept": "application/json"},
            follow_redirects=False,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_login_page_accessible_without_cookie(self, api_client):
        """Login page is accessible without authentication."""
        client, _ = api_client

        response = await client.get("/login")

        assert response.status_code == status.HTTP_200_OK
        assert "Euler RAG" in response.text

    @pytest.mark.asyncio
    async def test_docs_requires_cookie_auth(self, api_client):
        """Documentation endpoints require cookie authentication."""
        client, _ = api_client

        response = await client.get("/docs", follow_redirects=False)

        assert response.status_code == status.HTTP_302_FOUND
        assert "/login" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_docs_accessible_with_cookie(self, authenticated_client):
        """Documentation endpoints accessible with valid session cookie."""
        client, _ = authenticated_client

        response = await client.get("/docs")

        assert response.status_code == status.HTTP_200_OK


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
            headers={"Origin": "http://test"},
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
            headers={"Origin": "http://test"},
            follow_redirects=False,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "403" in response.text
        assert "Access Forbidden" in response.text

    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self, authenticated_client):
        """POST /logout clears session cookie."""
        client, _ = authenticated_client

        response = await client.post(
            "/logout", headers={"Origin": "http://test"}, follow_redirects=False
        )

        assert response.status_code == status.HTTP_302_FOUND
        # Cookie should be deleted (set to empty or with max-age=0)
        assert COOKIE_NAME in response.headers.get("set-cookie", "")

    @pytest.mark.asyncio
    async def test_auth_rejects_external_redirect_url(self, api_client):
        """POST /auth rejects external URLs in next parameter."""
        client, settings = api_client

        response = await client.post(
            "/auth",
            data={"api_key": settings.api_key, "next": "https://evil.com/phish"},
            headers={"Origin": "http://test"},
            follow_redirects=False,
        )

        assert response.status_code == status.HTTP_302_FOUND
        assert response.headers["location"] == "/login"

    @pytest.mark.asyncio
    async def test_logout_rejects_external_redirect_url(self, authenticated_client):
        """POST /logout rejects external URLs in next parameter."""
        client, _ = authenticated_client

        response = await client.post(
            "/logout?next=https://evil.com",
            headers={"Origin": "http://test"},
            follow_redirects=False,
        )

        assert response.status_code == status.HTTP_302_FOUND
        assert response.headers["location"] == "/login"

    @pytest.mark.asyncio
    async def test_auth_rejects_csrf_attack(self, api_client):
        """POST /auth without Origin header returns 403."""
        client, settings = api_client

        response = await client.post(
            "/auth",
            data={"api_key": settings.api_key, "next": "/"},
            follow_redirects=False,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_logout_rejects_csrf_attack(self, authenticated_client):
        """POST /logout without Origin header returns 403."""
        client, _ = authenticated_client

        response = await client.post("/logout", follow_redirects=False)

        assert response.status_code == status.HTTP_403_FORBIDDEN


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
    """Tests for health check endpoint under /api (protected)."""

    @pytest.mark.asyncio
    async def test_health_requires_api_key(self, api_client):
        """Health endpoint requires API key authentication."""
        client, _ = api_client

        response = await client.get("/api/health")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_health_returns_status(self, api_client):
        """Health endpoint returns healthy status with valid API key."""
        client, settings = api_client

        response = await client.get(
            "/api/health", headers={"X-API-KEY": settings.api_key}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "euler-rag"


class TestNotFoundHandler:
    """Tests for 404 Not Found handler."""

    @pytest.mark.asyncio
    async def test_not_found_returns_json_for_api_requests(self, api_client):
        """404 returns JSON response for API requests."""
        client, _ = api_client

        response = await client.get(
            "/nonexistent-path",
            headers={"Accept": "application/json"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["error"] == "Not Found"
        assert "message" in data

    @pytest.mark.asyncio
    async def test_not_found_returns_html_for_browser_requests(self, api_client):
        """404 returns HTML template for browser requests."""
        client, _ = api_client

        response = await client.get(
            "/nonexistent-path",
            headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "text/html" in response.headers["content-type"]
        assert "404" in response.text
        assert "Page Not Found" in response.text

    @pytest.mark.asyncio
    async def test_not_found_defaults_to_json(self, api_client):
        """404 defaults to JSON when no Accept header."""
        client, _ = api_client

        response = await client.get("/nonexistent-path")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["error"] == "Not Found"


@pytest.fixture
async def redis_client(test_settings) -> Redis:
    """Create Redis client for integration tests.

    Requires Redis to be running.
    """
    client = Redis.from_url(
        test_settings.redis_url,
        decode_responses=True,
    )

    # Verify connection
    try:
        await client.ping()
    except Exception:
        pytest.skip("Redis not available for integration tests")

    # Cleanup before test to remove stale state
    keys = await client.keys("euler:*")
    if keys:
        await client.delete(*keys)

    yield client

    # Cleanup after test
    keys = await client.keys("euler:*")
    if keys:
        await client.delete(*keys)
    await client.aclose()


@pytest.fixture
def progress_tracker(redis_client: Redis) -> ProgressTracker:
    """Create ProgressTracker with real Redis."""
    return ProgressTracker(redis_client)


@pytest.fixture
def app_with_redis(app, redis_client: Redis):
    """App fixture with Redis dependency override."""
    from app.utils.api_helpers import get_progress_tracker
    from app.workers.progress import ProgressTracker

    # Override get_progress_tracker to use real Redis
    def override_get_progress_tracker() -> ProgressTracker:
        return ProgressTracker(redis_client)

    app.dependency_overrides[get_progress_tracker] = override_get_progress_tracker
    yield app
    app.dependency_overrides.pop(get_progress_tracker, None)


@pytest.fixture
async def authenticated_client_with_redis(app_with_redis, settings: Settings):
    """Create authenticated client with Redis support."""
    transport = ASGITransport(app=app_with_redis)
    session_token = generate_session_token(settings.api_key)
    cookies = {COOKIE_NAME: session_token}
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=cookies
    ) as client:
        yield client, settings


class TestDocumentProgressAPI:
    """Tests for document progress tracking endpoints."""

    @pytest.mark.asyncio
    async def test_sse_endpoint_returns_event_stream(
        self, authenticated_client_with_redis, progress_tracker: ProgressTracker
    ):
        """SSE endpoint returns text/event-stream content type."""
        client, _ = authenticated_client_with_redis

        response = await client.get(
            "/admin/api/documents/1/progress",
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_sse_endpoint_sends_current_progress_on_connect(
        self, authenticated_client_with_redis, progress_tracker: ProgressTracker
    ):
        """SSE endpoint sends current progress from Redis when available."""
        client, _ = authenticated_client_with_redis
        document_id = 42

        # Set current progress in Redis
        progress = Progress(
            document_id=document_id,
            page=5,
            total=10,
            status="processing",
            message="Processing page 5/10",
        )
        await progress_tracker.update(progress)

        # Connect to SSE endpoint
        async with client.stream(
            "GET", f"/admin/api/documents/{document_id}/progress"
        ) as response:
            assert response.status_code == status.HTTP_200_OK

            # Read first event (should be current progress)
            events = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])  # Remove "data: " prefix
                    events.append(data)
                    break  # Just check first event

            assert len(events) > 0
            assert events[0]["document_id"] == document_id
            assert events[0]["page"] == 5
            assert events[0]["total"] == 10
            assert events[0]["status"] == "processing"

    @pytest.mark.asyncio
    async def test_sse_endpoint_streams_progress_updates(
        self, authenticated_client_with_redis, progress_tracker: ProgressTracker
    ):
        """SSE endpoint streams progress updates from Redis pub/sub."""
        client, _ = authenticated_client_with_redis
        document_id = 99

        # Start SSE connection
        async with client.stream(
            "GET", f"/admin/api/documents/{document_id}/progress"
        ) as response:
            assert response.status_code == status.HTTP_200_OK

            # Publish progress update in background
            import asyncio

            async def publish_update():
                await asyncio.sleep(0.1)  # Small delay to ensure subscription is ready
                progress = Progress(
                    document_id=document_id,
                    page=3,
                    total=7,
                    status="processing",
                    message="Processing page 3/7",
                )
                await progress_tracker.update(progress)

            # Start publishing task
            publish_task = asyncio.create_task(publish_update())

            # Read events
            events = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    events.append(data)
                    if len(events) >= 2:  # Got initial + update
                        break

            await publish_task

            # Should have received at least the published update
            assert len(events) >= 1
            update_event = events[-1]
            assert update_event["document_id"] == document_id
            assert update_event["page"] == 3
            assert update_event["total"] == 7

    @pytest.mark.asyncio
    async def test_sse_endpoint_closes_on_ready_status(
        self, authenticated_client_with_redis, progress_tracker: ProgressTracker
    ):
        """SSE endpoint closes connection when status becomes ready."""
        client, _ = authenticated_client_with_redis
        document_id = 123

        # Start SSE connection
        async with client.stream(
            "GET", f"/admin/api/documents/{document_id}/progress"
        ) as response:
            assert response.status_code == status.HTTP_200_OK

            # Publish ready status
            import asyncio

            async def publish_ready():
                await asyncio.sleep(0.1)
                progress = Progress(
                    document_id=document_id,
                    page=10,
                    total=10,
                    status="ready",
                    message="Processing complete",
                )
                await progress_tracker.update(progress)

            publish_task = asyncio.create_task(publish_ready())

            # Read events until connection closes
            events = []
            try:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        events.append(data)
                        if data.get("status") == "ready":
                            break
            except Exception:
                pass  # Connection may close

            await publish_task

            # Should have received ready event
            ready_events = [e for e in events if e.get("status") == "ready"]
            assert len(ready_events) > 0

    @pytest.mark.asyncio
    async def test_get_current_progress_returns_progress_when_exists(
        self, authenticated_client_with_redis, progress_tracker: ProgressTracker
    ):
        """GET /admin/api/documents/{id}/progress/current returns progress."""
        client, _ = authenticated_client_with_redis
        document_id = 456

        # Set progress in Redis
        progress = Progress(
            document_id=document_id,
            page=7,
            total=15,
            status="processing",
            message="Processing page 7/15",
        )
        await progress_tracker.update(progress)

        # Get current progress
        response = await client.get(
            f"/admin/api/documents/{document_id}/progress/current"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["document_id"] == document_id
        assert data["page"] == 7
        assert data["total"] == 15
        assert data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_get_current_progress_returns_404_when_not_exists(
        self, authenticated_client_with_redis
    ):
        """GET /admin/api/documents/{id}/progress/current returns 404."""
        client, _ = authenticated_client_with_redis
        document_id = 999

        response = await client.get(
            f"/admin/api/documents/{document_id}/progress/current"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
