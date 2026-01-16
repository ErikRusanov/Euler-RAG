"""Unit tests for cookie-based authentication middleware."""

from app.middleware.cookie_auth import (
    COOKIE_NAME,
    SESSION_MESSAGE,
    CookieAuthMiddleware,
    generate_session_token,
    verify_session_token,
)


class TestSessionToken:
    """Tests for session token generation and verification."""

    def test_generate_session_token_returns_hex_string(self):
        """generate_session_token returns a hex-encoded string."""
        api_key = "test-api-key"

        token = generate_session_token(api_key)

        assert isinstance(token, str)
        assert len(token) == 64  # SHA256 hex digest is 64 chars
        assert all(c in "0123456789abcdef" for c in token)

    def test_generate_session_token_deterministic(self):
        """generate_session_token returns same token for same key."""
        api_key = "test-api-key"

        token1 = generate_session_token(api_key)
        token2 = generate_session_token(api_key)

        assert token1 == token2

    def test_generate_session_token_different_for_different_keys(self):
        """generate_session_token returns different tokens for different keys."""
        token1 = generate_session_token("key1")
        token2 = generate_session_token("key2")

        assert token1 != token2

    def test_verify_session_token_valid(self):
        """verify_session_token returns True for valid token."""
        api_key = "test-api-key"
        token = generate_session_token(api_key)

        result = verify_session_token(token, api_key)

        assert result is True

    def test_verify_session_token_invalid(self):
        """verify_session_token returns False for invalid token."""
        api_key = "test-api-key"

        result = verify_session_token("invalid-token", api_key)

        assert result is False

    def test_verify_session_token_wrong_key(self):
        """verify_session_token returns False when key doesn't match."""
        token = generate_session_token("original-key")

        result = verify_session_token(token, "different-key")

        assert result is False

    def test_verify_session_token_empty_token(self):
        """verify_session_token returns False for empty token."""
        result = verify_session_token("", "test-api-key")

        assert result is False


class TestCookieAuthMiddlewarePaths:
    """Tests for CookieAuthMiddleware path classification."""

    def test_is_excluded_path_login(self):
        """Login path is excluded from cookie auth."""
        assert CookieAuthMiddleware.is_excluded_path("/login") is True

    def test_is_excluded_path_auth(self):
        """Auth path is excluded from cookie auth."""
        assert CookieAuthMiddleware.is_excluded_path("/auth") is True

    def test_is_excluded_path_logout(self):
        """Logout path is excluded from cookie auth."""
        assert CookieAuthMiddleware.is_excluded_path("/logout") is True

    def test_is_excluded_path_other(self):
        """Other paths are not excluded."""
        assert CookieAuthMiddleware.is_excluded_path("/") is False
        assert CookieAuthMiddleware.is_excluded_path("/health") is False
        assert CookieAuthMiddleware.is_excluded_path("/docs") is False

    def test_is_public_path_root(self):
        """Root path is public."""
        assert CookieAuthMiddleware.is_public_path("/") is True

    def test_is_public_path_health(self):
        """Health paths are public."""
        assert CookieAuthMiddleware.is_public_path("/health") is True
        assert CookieAuthMiddleware.is_public_path("/health/db") is True

    def test_is_public_path_docs(self):
        """Docs paths are public."""
        assert CookieAuthMiddleware.is_public_path("/docs") is True
        assert CookieAuthMiddleware.is_public_path("/openapi.json") is True

    def test_is_public_path_api_routes(self):
        """API routes are not public (they're protected)."""
        assert CookieAuthMiddleware.is_public_path("/api/documents") is False
        assert CookieAuthMiddleware.is_public_path("/api/health") is False


class TestCookieConstants:
    """Tests for cookie auth constants."""

    def test_cookie_name_defined(self):
        """Cookie name constant is defined."""
        assert COOKIE_NAME == "euler_session"

    def test_session_message_defined(self):
        """Session message constant is defined."""
        assert SESSION_MESSAGE == "euler_rag_session_valid"
