"""Tests for database connection."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from app.utils.db import get_db_engine, init_db, verify_db_connection


@pytest.mark.asyncio
async def test_get_db_engine_creates_engine():
    """Test that get_db_engine creates engine instance."""
    engine = await get_db_engine()
    assert engine is not None
    assert hasattr(engine, "connect")


@pytest.mark.asyncio
async def test_verify_db_connection_raises_on_failure():
    """Test that verify_db_connection raises exception when connection fails."""
    # Мокируем ошибку подключения
    with patch("app.utils.db.get_db_engine", new_callable=AsyncMock) as mock_get_engine:
        mock_engine = MagicMock()
        # Настраиваем connect() чтобы выбрасывал ошибку при входе в context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.side_effect = OperationalError(
            "connection failed", None, None
        )
        mock_engine.connect.return_value = mock_context
        mock_get_engine.return_value = mock_engine

        # Приложение должно завершиться с ошибкой при неверных credentials
        with pytest.raises(OperationalError):
            await verify_db_connection()


@pytest.mark.asyncio
async def test_init_db_exits_on_connection_failure():
    """Test that init_db exits application when connection fails."""
    with patch("app.utils.db.verify_db_connection") as mock_verify:
        mock_verify.side_effect = OperationalError("connection failed", None, None)

        # init_db должна завершить приложение при ошибке подключения
        with pytest.raises(SystemExit):
            await init_db()
