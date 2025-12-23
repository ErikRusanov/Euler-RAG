"""Tests for application configuration."""

from app.config import Settings


class TestSettings:
    """Tests for Settings class - проверяем только важную логику."""

    def test_settings_loads_from_env(self, monkeypatch):
        """Проверяем, что Settings читает переменные окружения."""
        monkeypatch.setenv("API_TITLE", "Test API")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("PORT", "9000")

        test_settings = Settings()
        assert test_settings.API_TITLE == "Test API"
        assert test_settings.DEBUG is True
        assert test_settings.PORT == 9000

    def test_settings_debug_parses_boolean(self, monkeypatch):
        """Проверяем парсинг булевых значений из строк."""
        monkeypatch.setenv("DEBUG", "True")
        assert Settings().DEBUG is True

        monkeypatch.setenv("DEBUG", "false")
        assert Settings().DEBUG is False

    def test_settings_port_parses_integer(self, monkeypatch):
        """Проверяем парсинг порта из строки в число."""
        monkeypatch.setenv("PORT", "8080")
        test_settings = Settings()
        assert test_settings.PORT == 8080
        assert isinstance(test_settings.PORT, int)
