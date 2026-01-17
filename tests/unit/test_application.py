"""Unit tests for application factory."""

from app.application import create_app


class TestApplication:
    """Tests for application creation."""

    def test_create_app_includes_routes(self):
        """Routes are registered correctly."""
        app = create_app()
        routes = [route.path for route in app.routes]

        # Auth routes
        assert "/login" in routes
        # API routes (protected)
        assert "/api/health" in routes
        assert "/api/documents" in routes
