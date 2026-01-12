"""Unit tests for application factory."""

from app.application import create_app


class TestApplication:
    """Tests for application creation."""

    def test_create_app_includes_routes(self):
        """Routes are registered correctly."""
        app = create_app()
        routes = [route.path for route in app.routes]

        assert "/" in routes
        assert "/health" in routes
        # Documents routes are under /api prefix (protected)
        assert "/api/documents" in routes
