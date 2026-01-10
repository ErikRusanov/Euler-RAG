"""Unit tests for database connection manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from app.utils.db import DatabaseManager, db_manager, get_db_session, init_db


class TestDatabaseManager:
    """Tests for DatabaseManager class."""

    @pytest.mark.asyncio
    async def test_init_engine_creates_engine(self):
        """init_engine creates engine instance."""
        manager = DatabaseManager()

        engine = manager.init_engine()

        assert engine is not None
        assert hasattr(engine, "connect")
        assert manager._engine is engine

    @pytest.mark.asyncio
    async def test_init_engine_caches_instance(self):
        """init_engine returns cached engine on subsequent calls."""
        manager = DatabaseManager()

        engine1 = manager.init_engine()
        engine2 = manager.init_engine()

        assert engine1 is engine2

    @pytest.mark.asyncio
    async def test_verify_connection_success(self):
        """verify_connection returns True on successful connection."""
        manager = DatabaseManager()

        with patch.object(manager, "init_engine") as mock_init:
            mock_engine = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_conn
            mock_context.__aexit__.return_value = None
            mock_engine.connect.return_value = mock_context
            mock_init.return_value = mock_engine

            is_connected = await manager.verify_connection()

            assert is_connected is True
            mock_conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_verify_connection_raises_on_failure(self):
        """verify_connection raises on connection failure."""
        manager = DatabaseManager()

        with patch.object(manager, "init_engine") as mock_init:
            mock_engine = MagicMock()
            mock_context = AsyncMock()
            mock_context.__aenter__.side_effect = OperationalError(
                "connection failed", None, None
            )
            mock_engine.connect.return_value = mock_context
            mock_init.return_value = mock_engine

            with pytest.raises(OperationalError):
                await manager.verify_connection()

    @pytest.mark.asyncio
    async def test_close_disposes_engine(self):
        """close disposes engine and clears state."""
        manager = DatabaseManager()
        manager.init_engine()

        await manager.close()

        assert manager._engine is None
        assert manager._session_factory is None


class TestGetDbSession:
    """Tests for get_db_session dependency."""

    @pytest.mark.asyncio
    async def test_yields_session(self):
        """get_db_session yields working session."""
        session_created = False

        async for session in get_db_session():
            session_created = True
            assert session is not None
            assert hasattr(session, "execute")
            break

        assert session_created is True

    @pytest.mark.asyncio
    async def test_commits_on_success(self):
        """get_db_session commits on successful completion."""
        mock_session = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_session_factory = MagicMock(return_value=mock_context)

        with patch("app.utils.db.db_manager.init_session_factory") as mock_factory:
            mock_factory.return_value = mock_session_factory

            async for _ in get_db_session():
                pass

            mock_session.commit.assert_awaited_once()
            mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rollbacks_on_error(self):
        """get_db_session rolls back on error."""
        mock_session = AsyncMock()

        class MockSessionContext:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_session_factory = MagicMock(return_value=MockSessionContext())

        with patch.object(
            db_manager, "init_session_factory", return_value=mock_session_factory
        ):
            try:
                gen = get_db_session()
                await gen.__anext__()
                await gen.athrow(ValueError("Test error"))
            except (StopAsyncIteration, ValueError):
                pass

            mock_session.rollback.assert_awaited_once()


class TestInitDb:
    """Tests for init_db function."""

    @pytest.mark.asyncio
    async def test_success(self):
        """init_db succeeds when connection is verified."""
        with patch(
            "app.utils.db.db_manager.verify_connection", new_callable=AsyncMock
        ) as mock_verify:
            mock_verify.return_value = True

            await init_db()

            mock_verify.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_on_failure(self):
        """init_db raises on connection failure."""
        with patch(
            "app.utils.db.db_manager.verify_connection", new_callable=AsyncMock
        ) as mock_verify:
            mock_verify.side_effect = OperationalError("connection failed", None, None)

            with pytest.raises(OperationalError):
                await init_db()
