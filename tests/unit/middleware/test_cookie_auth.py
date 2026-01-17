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

    def test_requires_cookie_auth_empty_by_default(self):
        """No paths require cookie auth by default (empty whitelist)."""
        assert CookieAuthMiddleware.requires_cookie_auth("/") is False
        assert CookieAuthMiddleware.requires_cookie_auth("/docs") is False
        assert CookieAuthMiddleware.requires_cookie_auth("/some-path") is False
        assert CookieAuthMiddleware.requires_cookie_auth("/api/documents") is False

    def test_requires_cookie_auth_with_protected_paths(self):
        """Paths in PROTECTED_PATHS require cookie auth."""
        original = CookieAuthMiddleware.PROTECTED_PATHS.copy()
        try:
            CookieAuthMiddleware.PROTECTED_PATHS.add("/admin")
            assert CookieAuthMiddleware.requires_cookie_auth("/admin") is True
            assert CookieAuthMiddleware.requires_cookie_auth("/other") is False
        finally:
            CookieAuthMiddleware.PROTECTED_PATHS = original

    def test_requires_cookie_auth_with_protected_prefixes(self):
        """Paths starting with PROTECTED_PREFIXES require cookie auth."""
        original = CookieAuthMiddleware.PROTECTED_PREFIXES
        try:
            CookieAuthMiddleware.PROTECTED_PREFIXES = ("/admin/",)
            assert CookieAuthMiddleware.requires_cookie_auth("/admin/dashboard") is True
            assert CookieAuthMiddleware.requires_cookie_auth("/admin/users") is True
            assert CookieAuthMiddleware.requires_cookie_auth("/other") is False
        finally:
            CookieAuthMiddleware.PROTECTED_PREFIXES = original


class TestCookieConstants:
    """Tests for cookie auth constants."""

    def test_cookie_name_defined(self):
        """Cookie name constant is defined."""
        assert COOKIE_NAME == "euler_session"

    def test_session_message_defined(self):
        """Session message constant is defined."""
        assert SESSION_MESSAGE == "euler_rag_session_valid"
