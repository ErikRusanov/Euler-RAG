"""Integration tests for Redis connection with real Redis server."""

import pytest

from app.config import get_settings


@pytest.fixture(scope="module")
def redis_settings():
    """Get settings with Redis configuration."""
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
async def redis_client(redis_settings):
    """Create real Redis client for integration tests.

    Yields:
        Redis client instance connected to test Redis.

    Skips if Redis is not available.
    """
    from redis.asyncio import Redis
    from redis.exceptions import ConnectionError as RedisConnectionException

    client = Redis.from_url(
        redis_settings.redis_url,
        decode_responses=True,
    )

    try:
        await client.ping()
    except RedisConnectionException:
        pytest.skip("Redis server not available")

    yield client

    # Cleanup: clear test keys
    await client.flushdb()
    await client.aclose()


class TestRedisRealConnection:
    """Integration tests with real Redis connection."""

    @pytest.mark.asyncio
    async def test_redis_real_connection(self, redis_client):
        """Test: Real PING to Redis server works."""
        result = await redis_client.ping()

        assert result is True

    @pytest.mark.asyncio
    async def test_redis_set_get_operations(self, redis_client):
        """Test: Basic set/get operations work correctly."""
        test_key = "test:integration:key"
        test_value = "test_value_123"

        # Set value
        await redis_client.set(test_key, test_value)

        # Get value
        result = await redis_client.get(test_key)

        assert result == test_value

        # Cleanup
        await redis_client.delete(test_key)
