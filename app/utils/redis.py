"""Redis connection manager with proper lifecycle management."""

import logging
from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionException

from app.config import get_settings
from app.exceptions import RedisConnectionError

logger = logging.getLogger(__name__)


class RedisManager:
    """Redis manager handling client lifecycle.

    This class encapsulates Redis connection management and provides
    lazy initialization with proper cleanup.
    """

    def __init__(self) -> None:
        """Initialize Redis manager with None client."""
        self._client: Optional[Redis] = None

    def init_client(self) -> Redis:
        """Initialize and return Redis client.

        Creates client only once and reuses it for subsequent calls.
        Uses connection URL from settings.

        Returns:
            Initialized Redis client instance.
        """
        if self._client is not None:
            return self._client

        settings = get_settings()

        self._client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

        logger.info(
            "Redis client initialized",
            extra={
                "host": settings.redis_host,
                "port": settings.redis_port,
                "db": settings.redis_db,
            },
        )

        return self._client

    async def verify_connection(self) -> bool:
        """Verify Redis connection is working.

        Returns:
            True if connection is successful.

        Raises:
            RedisConnectionError: If connection fails.
        """
        try:
            client = self.init_client()
            await client.ping()
            logger.info("Redis connection verified successfully")
            return True
        except RedisConnectionException as e:
            logger.error(f"Redis connection verification failed: {e}")
            raise RedisConnectionError(f"Failed to connect to Redis: {e}") from e

    async def close(self) -> None:
        """Close Redis client and clean up.

        Should be called during application shutdown.
        """
        if self._client is not None:
            await self._client.aclose()
            logger.info("Redis client closed")
            self._client = None

    @property
    def client(self) -> Redis:
        """Get client instance, initializing if needed."""
        return self.init_client()


# Global Redis manager instance
redis_manager = RedisManager()


async def init_redis() -> None:
    """Initialize Redis connection.

    Creates client instance and verifies connection.

    Raises:
        RedisConnectionError: If Redis connection fails.
    """
    logger.info("Initializing Redis connection...")
    redis_manager.init_client()
    await redis_manager.verify_connection()
    logger.info("Redis initialized successfully")


def get_redis_client() -> Redis:
    """Get Redis client instance.

    Returns:
        Initialized Redis client instance.

    Raises:
        RedisConnectionError: If client is not initialized.
    """
    if redis_manager._client is None:
        raise RedisConnectionError("Redis client is not initialized")
    return redis_manager._client


async def close_redis() -> None:
    """Close Redis connection.

    Cleans up Redis manager state.
    """
    logger.info("Closing Redis connection...")
    await redis_manager.close()
    logger.info("Redis connection closed")
