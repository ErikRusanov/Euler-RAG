"""Progress tracking via Redis for real-time updates.

Provides real-time progress tracking for long-running tasks with
Redis pub/sub for instant notifications to connected clients.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


@dataclass
class Progress:
    """Document processing progress data.

    Attributes:
        document_id: ID of the document being processed.
        page: Current page number being processed.
        total: Total number of pages in the document.
        status: Current processing status string.
        message: Optional human-readable status message.
    """

    document_id: int
    page: int
    total: int
    status: str
    message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert progress to dictionary for JSON serialization."""
        return {
            "document_id": self.document_id,
            "page": self.page,
            "total": self.total,
            "status": self.status,
            "message": self.message,
        }


class ProgressTracker:
    """Tracks processing progress in Redis.

    Uses Redis for fast writes and pub/sub for real-time notifications.
    Progress data is stored with TTL for automatic cleanup.

    Attributes:
        KEY_PREFIX: Redis key prefix for progress data.
        CHANNEL_PREFIX: Redis pub/sub channel prefix.
        TTL_SECONDS: Time-to-live for progress data.
    """

    KEY_PREFIX = "euler:progress:"
    CHANNEL_PREFIX = "euler:progress:updates:"
    TTL_SECONDS = 3600  # 1 hour

    def __init__(self, redis: Redis) -> None:
        """Initialize ProgressTracker with Redis client.

        Args:
            redis: Async Redis client instance.
        """
        self._redis = redis

    async def update(self, progress: Progress) -> None:
        """Update progress and publish notification.

        Stores current progress in Redis and publishes to channel
        for real-time subscribers.

        Args:
            progress: Progress data to store.
        """
        key = f"{self.KEY_PREFIX}{progress.document_id}"
        channel = f"{self.CHANNEL_PREFIX}{progress.document_id}"

        data = json.dumps(progress.to_dict())

        await self._redis.setex(key, self.TTL_SECONDS, data)
        await self._redis.publish(channel, data)

        logger.debug(
            "Progress updated",
            extra={
                "document_id": progress.document_id,
                "page": progress.page,
                "total": progress.total,
            },
        )

    async def get(self, document_id: int) -> Optional[Progress]:
        """Get current progress for a document.

        Args:
            document_id: Document ID to get progress for.

        Returns:
            Progress object or None if not found.
        """
        key = f"{self.KEY_PREFIX}{document_id}"
        data = await self._redis.get(key)

        if not data:
            return None

        parsed = json.loads(data)
        return Progress(**parsed)

    async def subscribe(self, document_id: int) -> AsyncIterator[Progress]:
        """Subscribe to progress updates for a document.

        Yields Progress objects as they are published.
        Used by SSE endpoint to stream updates to frontend.

        Args:
            document_id: Document ID to subscribe to.

        Yields:
            Progress objects as they are published.
        """
        channel = f"{self.CHANNEL_PREFIX}{document_id}"
        pubsub = self._redis.pubsub()

        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    yield Progress(**data)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def clear(self, document_id: int) -> None:
        """Clear progress data after processing complete.

        Args:
            document_id: Document ID to clear progress for.
        """
        key = f"{self.KEY_PREFIX}{document_id}"
        await self._redis.delete(key)
        logger.debug("Progress cleared", extra={"document_id": document_id})
