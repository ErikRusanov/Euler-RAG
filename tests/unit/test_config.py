"""Tests for application configuration."""

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


class TestSettings:
    """Tests for Settings class with Pydantic validation."""

    def test_settings_loads_from_env(self, monkeypatch):
        """Test that Settings loads values from environment variables."""
        monkeypatch.setenv("API_TITLE", "Test API")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("PORT", "9000")

        test_settings = Settings()
        assert test_settings.api_title == "Test API"
        assert test_settings.debug is True
        assert test_settings.port == 9000

    def test_settings_debug_parses_boolean(self, monkeypatch):
        """Test that DEBUG correctly parses boolean values from strings."""
        monkeypatch.setenv("DEBUG", "True")
        assert Settings().debug is True

        monkeypatch.setenv("DEBUG", "false")
        assert Settings().debug is False

    def test_settings_port_parses_integer(self, monkeypatch):
        """Test that PORT is parsed as integer with correct type."""
        monkeypatch.setenv("PORT", "8080")
        test_settings = Settings()
        assert test_settings.port == 8080
        assert isinstance(test_settings.port, int)

    def test_settings_port_validation(self, monkeypatch):
        """Test that invalid port values are rejected."""
        monkeypatch.setenv("PORT", "70000")  # Invalid port (> 65535)

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("port",) for error in errors)

    def test_settings_environment_validation(self, monkeypatch):
        """Test that environment field accepts only valid values."""
        # Valid values
        for env in ["development", "staging", "production"]:
            monkeypatch.setenv("ENVIRONMENT", env)
            settings = Settings()
            assert settings.environment == env

        # Invalid value
        monkeypatch.setenv("ENVIRONMENT", "invalid")
        with pytest.raises(ValidationError):
            Settings()

    def test_settings_database_url_property(self, monkeypatch):
        """Test that database_url property constructs correct URL."""
        monkeypatch.setenv("DB_USER", "testuser")
        monkeypatch.setenv("DB_PASSWORD", "testpass")
        monkeypatch.setenv("DB_HOST", "testhost")
        monkeypatch.setenv("DB_PORT", "5433")
        monkeypatch.setenv("DB_NAME", "testdb")

        settings = Settings()
        expected_url = "postgresql+asyncpg://testuser:testpass@testhost:5433/testdb"
        assert settings.database_url == expected_url

    def test_settings_database_url_sync_property(self, monkeypatch):
        """Test that database_url_sync property constructs correct sync URL."""
        monkeypatch.setenv("DB_USER", "testuser")
        monkeypatch.setenv("DB_PASSWORD", "testpass")
        monkeypatch.setenv("DB_HOST", "testhost")
        monkeypatch.setenv("DB_PORT", "5433")
        monkeypatch.setenv("DB_NAME", "testdb")

        settings = Settings()
        expected_url = "postgresql://testuser:testpass@testhost:5433/testdb"
        assert settings.database_url_sync == expected_url

    def test_settings_production_password_validation(self, monkeypatch):
        """Test that empty password is rejected in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DB_PASSWORD", "")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert any("password" in error["msg"].lower() for error in errors)

    def test_settings_is_production_property(self, monkeypatch):
        """Test is_production property."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        settings = Settings()
        assert settings.is_production is True
        assert settings.is_development is False

    def test_settings_is_development_property(self, monkeypatch):
        """Test is_development property."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        settings = Settings()
        assert settings.is_development is True
        assert settings.is_production is False

    def test_get_settings_returns_cached_instance(self):
        """Test that get_settings returns cached instance."""
        get_settings.cache_clear()  # Clear cache first

        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the same instance due to lru_cache
        assert settings1 is settings2

    def test_settings_default_values(self):
        """Test that default values are applied correctly."""
        # Clear all environment variables
        import os

        for key in list(os.environ.keys()):
            if key.startswith(("API_", "DB_", "DEBUG", "HOST", "PORT", "LOG_")):
                os.environ.pop(key, None)

        settings = Settings()

        assert settings.api_title == "Euler RAG"
        assert settings.api_version == "0.1.0"
        assert settings.debug is False
        assert settings.environment == "development"
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.db_host == "localhost"
        assert settings.db_port == 5432
