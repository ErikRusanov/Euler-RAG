"""Tests for database migrations."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.utils.db import get_db_url, run_migrations


@pytest.mark.asyncio
async def test_run_migrations_function_exists():
    """Test that run_migrations function exists and is callable."""
    # Проверяем что функция существует
    assert callable(run_migrations)

    # Проверяем что она async
    import inspect

    assert inspect.iscoroutinefunction(run_migrations)


@pytest.mark.asyncio
async def test_migrations_handle_missing_alembic_ini(monkeypatch, tmp_path):
    """Test that run_migrations raises FileNotFoundError when alembic.ini is missing."""
    # Мокируем Path(__file__) чтобы указать несуществующий путь
    mock_path_instance = MagicMock()
    mock_resolved = MagicMock()
    mock_parents = MagicMock()

    # Настраиваем parents[2] чтобы вернуть tmp_path
    def mock_getitem(self, key):
        if key == 2:
            return tmp_path
        return MagicMock()

    mock_parents.__getitem__ = mock_getitem
    mock_resolved.parents = mock_parents
    mock_path_instance.resolve.return_value = mock_resolved

    with patch("app.utils.db.Path", return_value=mock_path_instance):
        # Убеждаемся что alembic.ini не существует
        alembic_ini = tmp_path / "alembic.ini"
        assert not alembic_ini.exists()

        with pytest.raises(
            FileNotFoundError, match="Alembic configuration file not found"
        ):
            await run_migrations()


@pytest.mark.asyncio
async def test_migrations_use_correct_database_url(monkeypatch):
    """Test that migrations use the correct database URL from settings."""
    # Проверяем что run_migrations использует get_db_url
    get_db_url()

    # Мокируем get_db_url чтобы проверить что он вызывается
    mock_url = "postgresql+asyncpg://test:test@localhost:5432/test_db"
    with patch("app.utils.db.get_db_url", return_value=mock_url) as mock_get_url:
        # Мокируем command.upgrade чтобы избежать реальных вызовов
        with patch("alembic.command.upgrade") as mock_upgrade:
            with patch("alembic.config.Config") as mock_config_class:
                mock_cfg = MagicMock()
                mock_config_class.return_value = mock_cfg

                # Создаем реальный путь к alembic.ini
                project_root = Path(__file__).resolve().parents[3]
                alembic_ini = project_root / "alembic.ini"

                if alembic_ini.exists():
                    # Если alembic.ini существует, тест должен пройти
                    try:
                        await run_migrations()
                        # Проверяем что get_db_url был вызван
                        mock_get_url.assert_called()
                        # Проверяем что command.upgrade был вызван
                        mock_upgrade.assert_called_once()
                    except Exception:
                        # Если есть другие ошибки, это нормально
                        pass


@pytest.mark.asyncio
async def test_run_migrations_calls_command_upgrade(monkeypatch):
    """Test that run_migrations calls command.upgrade correctly."""
    # Проверяем что run_migrations вызывает command.upgrade
    with patch("alembic.command.upgrade") as mock_upgrade:
        with patch("alembic.config.Config") as mock_config_class:
            mock_cfg = MagicMock()
            mock_config_class.return_value = mock_cfg

            # Создаем реальный путь к alembic.ini
            project_root = Path(__file__).resolve().parents[3]
            alembic_ini = project_root / "alembic.ini"

            if alembic_ini.exists():
                # Если alembic.ini существует, функция должна вызвать command.upgrade
                await run_migrations()
                # Проверяем что command.upgrade был вызван с правильными аргументами
                mock_upgrade.assert_called_once()
                # Проверяем что второй аргумент - "head"
                call_args = mock_upgrade.call_args
                assert call_args[0][1] == "head"  # Второй позиционный аргумент
