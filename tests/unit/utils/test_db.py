"""Tests for database connection and manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from app.utils.db import DatabaseManager, db_manager, get_db_session, init_db


@pytest.mark.asyncio
async def test_database_manager_init_engine():
    """Test that DatabaseManager.init_engine creates engine instance."""
    manager = DatabaseManager()
    engine = manager.init_engine()

    assert engine is not None
    assert hasattr(engine, "connect")
    assert manager._engine is engine  # Should be cached


@pytest.mark.asyncio
async def test_database_manager_init_engine_caches():
    """Test that DatabaseManager.init_engine caches engine instance."""
    manager = DatabaseManager()

    engine1 = manager.init_engine()
    engine2 = manager.init_engine()

    assert engine1 is engine2  # Same instance


@pytest.mark.asyncio
async def test_database_manager_verify_connection_success(test_settings):
    """Test that DatabaseManager.verify_connection works correctly."""
    manager = DatabaseManager()

    # Mock the connection to avoid requiring actual database
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
async def test_database_manager_verify_connection_failure():
    """Test that DatabaseManager.verify_connection raises on failure."""
    manager = DatabaseManager()

    # Mock engine to raise error
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
async def test_database_manager_close():
    """Test that DatabaseManager.close disposes engine."""
    manager = DatabaseManager()

    # Initialize engine
    manager.init_engine()
    assert manager._engine is not None

    # Close manager
    await manager.close()
    assert manager._engine is None
    assert manager._session_factory is None


@pytest.mark.asyncio
async def test_get_db_session_yields_session():
    """Test that get_db_session yields working session."""
    session_created = False

    async for session in get_db_session():
        session_created = True
        assert session is not None
        assert hasattr(session, "execute")
        assert hasattr(session, "commit")
        break

    assert session_created is True


@pytest.mark.asyncio
async def test_get_db_session_commits_on_success():
    """Test that get_db_session auto-commits on success."""

    with patch("app.utils.db.db_manager.init_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None

        mock_session_factory = MagicMock()
        mock_session_factory.return_value = mock_context
        mock_factory.return_value = mock_session_factory

        async for _ in get_db_session():
            pass  # Normal execution

        # Should commit and close
        mock_session.commit.assert_awaited_once()
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_session_rollbacks_on_error():
    """Test that get_db_session auto-rollbacks on error."""
    # Create mock session
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()

    # Create proper async context manager mock
    class MockSessionContext:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Create mock session factory that returns our context manager
    mock_session_factory = MagicMock(return_value=MockSessionContext())

    with patch.object(
        db_manager, "init_session_factory", return_value=mock_session_factory
    ):
        try:
            gen = get_db_session()
            await gen.__anext__()
            # Simulate an error during request processing
            await gen.athrow(ValueError("Test error"))
        except (StopAsyncIteration, ValueError):
            pass

        # Should rollback (commit should not be called due to exception)
        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_init_db_success():
    """Test that init_db initializes database successfully."""
    with patch(
        "app.utils.db.db_manager.verify_connection", new_callable=AsyncMock
    ) as mock_verify:
        mock_verify.return_value = True

        # Should not raise exception
        await init_db()

        mock_verify.assert_awaited_once()


@pytest.mark.asyncio
async def test_init_db_raises_on_failure():
    """Test that init_db raises exception on connection failure."""
    with patch(
        "app.utils.db.db_manager.verify_connection", new_callable=AsyncMock
    ) as mock_verify:
        mock_verify.side_effect = OperationalError("connection failed", None, None)

        # Should raise exception (no longer calls sys.exit)
        with pytest.raises(OperationalError):
            await init_db()
