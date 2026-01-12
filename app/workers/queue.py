"""Task queue implementation using Redis Streams.

Provides reliable task queue with consumer groups, acknowledgement,
and dead letter queue for failed tasks.
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Supported task types for worker processing."""

    DOCUMENT_PROCESS = "document:process"


@dataclass
class Task:
    """Represents a task from the queue.

    Attributes:
        id: Unique task identifier.
        type: Task type enum value.
        payload: Task data dictionary.
        stream_id: Redis stream message ID for acknowledgement.
    """

    id: str
    type: TaskType
    payload: dict[str, Any]
    stream_id: str


class TaskQueue:
    """Redis Streams based task queue with consumer groups.

    Provides guaranteed delivery via consumer groups with automatic
    retry of unacknowledged messages and dead letter queue for
    permanently failed tasks.

    Attributes:
        STREAM_KEY: Redis key for the main task stream.
        GROUP_NAME: Consumer group name.
        DLQ_KEY: Redis key for dead letter queue.
    """

    STREAM_KEY = "euler:tasks"
    GROUP_NAME = "euler:workers"
    DLQ_KEY = "euler:tasks:dlq"

    def __init__(self, redis: Redis) -> None:
        """Initialize TaskQueue with Redis client.

        Args:
            redis: Async Redis client instance.
        """
        self._redis = redis
        self._consumer_name = f"worker-{uuid4().hex[:8]}"

    async def setup(self) -> None:
        """Create consumer group if it doesn't exist.

        Should be called once during worker startup.
        Handles edge cases like existing keys of wrong type.
        """
        try:
            # Check if key exists with wrong type and clean up
            key_type = await self._redis.type(self.STREAM_KEY)
            if key_type != "none" and key_type != "stream":
                logger.warning(
                    f"Removing stale key of wrong type: {key_type}",
                    extra={"key": self.STREAM_KEY},
                )
                await self._redis.delete(self.STREAM_KEY)

            await self._redis.xgroup_create(
                self.STREAM_KEY,
                self.GROUP_NAME,
                id="0",
                mkstream=True,
            )
            logger.info(
                "Created consumer group",
                extra={"group": self.GROUP_NAME, "stream": self.STREAM_KEY},
            )
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                raise
            logger.debug("Consumer group already exists")

    async def enqueue(self, task_type: TaskType, payload: dict[str, Any]) -> str:
        """Add task to the queue.

        Args:
            task_type: Type of task to process.
            payload: Task data dictionary.

        Returns:
            Unique task ID.
        """
        task_id = uuid4().hex
        message = {
            "id": task_id,
            "type": task_type.value,
            "payload": json.dumps(payload),
            "retries": "0",
        }

        await self._redis.xadd(self.STREAM_KEY, message)

        logger.info(
            "Task enqueued",
            extra={"task_id": task_id, "type": task_type.value},
        )
        return task_id

    async def dequeue(self, block_ms: int = 5000) -> Optional[Task]:
        """Fetch next task from the queue.

        First checks for pending (unacknowledged) messages, then reads
        new messages. Blocks until a task is available or timeout.

        Args:
            block_ms: Maximum time to block waiting for task in milliseconds.

        Returns:
            Task object or None if no tasks available within timeout.
        """
        try:
            return await self._dequeue_impl(block_ms)
        except Exception as e:
            # Handle missing consumer group (e.g., after Redis restart or cleanup)
            if "NOGROUP" in str(e):
                logger.warning("Consumer group missing, re-creating...")
                await self.setup()
                return await self._dequeue_impl(block_ms)
            raise

    async def _dequeue_impl(self, block_ms: int) -> Optional[Task]:
        """Internal dequeue implementation."""
        # First, check for pending messages (retries)
        pending = await self._redis.xreadgroup(
            self.GROUP_NAME,
            self._consumer_name,
            {self.STREAM_KEY: "0"},
            count=1,
        )

        if not pending or not pending[0][1]:
            # No pending, read new messages
            messages = await self._redis.xreadgroup(
                self.GROUP_NAME,
                self._consumer_name,
                {self.STREAM_KEY: ">"},
                count=1,
                block=block_ms,
            )
            if not messages or not messages[0][1]:
                return None
            pending = messages

        stream_id, data = pending[0][1][0]

        return Task(
            id=data["id"],
            type=TaskType(data["type"]),
            payload=json.loads(data["payload"]),
            stream_id=stream_id,
        )

    async def ack(self, task: Task) -> None:
        """Acknowledge task completion.

        Removes the task from pending list.

        Args:
            task: Task to acknowledge.
        """
        await self._redis.xack(self.STREAM_KEY, self.GROUP_NAME, task.stream_id)
        logger.debug("Task acknowledged", extra={"task_id": task.id})

    async def fail(self, task: Task, error: str) -> None:
        """Move task to dead letter queue.

        Called when task processing fails permanently.

        Args:
            task: Failed task.
            error: Error message describing the failure.
        """
        await self._redis.xadd(
            self.DLQ_KEY,
            {
                "original_id": task.id,
                "type": task.type.value,
                "payload": json.dumps(task.payload),
                "error": error,
            },
        )
        await self.ack(task)
        logger.error(
            "Task moved to DLQ",
            extra={"task_id": task.id, "error": error},
        )
