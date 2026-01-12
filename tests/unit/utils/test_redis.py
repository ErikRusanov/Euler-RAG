"""Unit tests for Redis connection manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionException

from app.exceptions import RedisConnectionError


class TestRedisManager:
    """Tests for RedisManager class."""

    @pytest.mark.asyncio
    async def test_init_client_creates_client(self):
        """init_client creates Redis client instance."""
        with patch("app.utils.redis.Redis") as MockRedis:
            from app.utils.redis import RedisManager

            mock_client = MagicMock()
            MockRedis.from_url.return_value = mock_client

            with patch("app.utils.redis.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    redis_url="redis://localhost:6379/0"
                )

                manager = RedisManager()
                client = manager.init_client()

                assert client is mock_client
                assert manager._client is mock_client
                MockRedis.from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_client_caches_instance(self):
        """init_client returns cached client on subsequent calls."""
        with patch("app.utils.redis.Redis") as MockRedis:
            from app.utils.redis import RedisManager

            mock_client = MagicMock()
            MockRedis.from_url.return_value = mock_client

            with patch("app.utils.redis.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    redis_url="redis://localhost:6379/0"
                )

                manager = RedisManager()
                client1 = manager.init_client()
                client2 = manager.init_client()

                assert client1 is client2
                assert MockRedis.from_url.call_count == 1

    @pytest.mark.asyncio
    async def test_verify_connection_success(self):
        """verify_connection returns True on successful PING."""
        with patch("app.utils.redis.Redis"):
            from app.utils.redis import RedisManager

            manager = RedisManager()
            mock_client = AsyncMock()
            mock_client.ping.return_value = True
            manager._client = mock_client

            result = await manager.verify_connection()

            assert result is True
            mock_client.ping.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_verify_connection_failure(self):
        """verify_connection raises RedisConnectionError on failure."""
        with patch("app.utils.redis.Redis"):
            from app.utils.redis import RedisManager

            manager = RedisManager()
            mock_client = AsyncMock()
            mock_client.ping.side_effect = RedisConnectionException(
                "Connection refused"
            )
            manager._client = mock_client

            with pytest.raises(RedisConnectionError):
                await manager.verify_connection()

    @pytest.mark.asyncio
    async def test_close_clears_client(self):
        """close disposes client and clears state."""
        with patch("app.utils.redis.Redis"):
            from app.utils.redis import RedisManager

            manager = RedisManager()
            mock_client = AsyncMock()
            manager._client = mock_client

            await manager.close()

            assert manager._client is None
            mock_client.aclose.assert_awaited_once()


class TestRedisHelperFunctions:
    """Tests for Redis helper functions."""

    @pytest.mark.asyncio
    async def test_init_redis_creates_and_verifies(self):
        """init_redis creates and verifies Redis client."""
        with patch("app.utils.redis.redis_manager") as mock_manager:
            from app.utils.redis import init_redis

            mock_manager.init_client.return_value = MagicMock()
            mock_manager.verify_connection = AsyncMock(return_value=True)

            await init_redis()

            mock_manager.init_client.assert_called_once()
            mock_manager.verify_connection.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_redis_client_raises_if_not_initialized(self):
        """get_redis_client raises if client not initialized."""
        with patch("app.utils.redis.redis_manager") as mock_manager:
            from app.utils.redis import get_redis_client

            mock_manager._client = None

            with pytest.raises(RedisConnectionError):
                get_redis_client()

    @pytest.mark.asyncio
    async def test_close_redis_cleans_up(self):
        """close_redis cleans up manager state."""
        with patch("app.utils.redis.redis_manager") as mock_manager:
            from app.utils.redis import close_redis

            mock_manager.close = AsyncMock()

            await close_redis()

            mock_manager.close.assert_awaited_once()
