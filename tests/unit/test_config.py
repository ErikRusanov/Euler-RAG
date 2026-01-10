"""Unit tests for application configuration."""

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


class TestSettings:
    """Tests for Settings validation."""

    def test_settings_loads_from_env(self, monkeypatch):
        """Settings loads values from environment variables."""
        monkeypatch.setenv("API_TITLE", "Test API")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("PORT", "9000")

        test_settings = Settings()

        assert test_settings.api_title == "Test API"
        assert test_settings.debug is True
        assert test_settings.port == 9000

    def test_port_validation_rejects_invalid(self, monkeypatch):
        """Invalid port values are rejected."""
        monkeypatch.setenv("PORT", "70000")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("port",) for error in errors)

    def test_environment_validation(self, monkeypatch):
        """Environment field accepts only valid values."""
        monkeypatch.setenv("ENVIRONMENT", "invalid")

        with pytest.raises(ValidationError):
            Settings()

    def test_database_url_property(self, monkeypatch):
        """database_url property constructs correct async URL."""
        monkeypatch.setenv("DB_USER", "testuser")
        monkeypatch.setenv("DB_PASSWORD", "testpass")
        monkeypatch.setenv("DB_HOST", "testhost")
        monkeypatch.setenv("DB_PORT", "5433")
        monkeypatch.setenv("DB_NAME", "testdb")

        settings = Settings()

        expected_url = "postgresql+asyncpg://testuser:testpass@testhost:5433/testdb"
        assert settings.database_url == expected_url

    def test_production_requires_password(self, monkeypatch):
        """Empty password is rejected in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DB_PASSWORD", "")
        monkeypatch.setenv("API_KEY", "production-api-key-with-32-chars-minimum-length")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert any("password" in error["msg"].lower() for error in errors)

    def test_production_requires_long_api_key(self, monkeypatch):
        """API key must be at least 32 characters in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DB_PASSWORD", "secure-password")
        monkeypatch.setenv("API_KEY", "short-key")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert any(
            "32 characters" in error["msg"] and error["loc"] == ("api_key",)
            for error in errors
        )

    def test_api_key_must_not_be_empty(self, monkeypatch):
        """API key must not be empty."""
        monkeypatch.setenv("API_KEY", "")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("api_key",) for error in errors)

    def test_get_settings_caches_result(self):
        """get_settings returns cached instance."""
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2
