"""Tests for application factory and endpoints."""

from fastapi.testclient import TestClient

from app.application import create_app


class TestApplication:
    """Тесты приложения - проверяем только поведение."""

    def test_create_app_includes_routes(self):
        """Проверяем, что роуты подключены."""
        app = create_app()
        routes = [route.path for route in app.routes]
        assert "/" in routes
        assert "/health" in routes

    def test_health_endpoint(self, client: TestClient):
        """Проверяем, что health endpoint работает."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
