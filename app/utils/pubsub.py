"""Redis pub/sub service for real-time messaging."""

import json
import logging
from typing import Any, AsyncIterator

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class PubSubService:
    """Redis pub/sub service for publishing and subscribing to channels.

    Provides a clean interface for Redis pub/sub operations with automatic
    JSON serialization/deserialization.
    """

    def __init__(self, redis: Redis) -> None:
        """Initialize PubSubService with Redis client.

        Args:
            redis: Async Redis client instance.
        """
        self._redis = redis

    async def publish(self, channel: str, data: dict[str, Any]) -> None:
        """Publish data to a Redis channel.

        Args:
            channel: Channel name to publish to.
            data: Dictionary data to publish (will be JSON serialized).
        """
        message = json.dumps(data)
        await self._redis.publish(channel, message)
        logger.debug("Published message to channel", extra={"channel": channel})

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to a Redis channel and yield messages.

        Args:
            channel: Channel name to subscribe to.

        Yields:
            Dictionary data from published messages.
        """
        pubsub = self._redis.pubsub()

        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    yield data
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
