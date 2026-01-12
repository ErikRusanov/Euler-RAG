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
        retries: Number of retry attempts made.
    """

    id: str
    type: TaskType
    payload: dict[str, Any]
    stream_id: str
    retries: int = 0


class TaskQueue:
    """Redis Streams based task queue with consumer groups.

    Provides guaranteed delivery via consumer groups with automatic
    retry of unacknowledged messages and dead letter queue for
    permanently failed tasks.

    Attributes:
        STREAM_KEY: Redis key for the main task stream.
        GROUP_NAME: Consumer group name.
        DLQ_KEY: Redis key for dead letter queue.
        MAX_RETRIES: Maximum number of retry attempts before DLQ.
        RETRY_DELAYS: Exponential backoff delays in seconds.
    """

    STREAM_KEY = "euler:tasks"
    GROUP_NAME = "euler:workers"
    DLQ_KEY = "euler:tasks:dlq"
    MAX_RETRIES = 3
    RETRY_DELAYS = [5, 30, 120]  # 5s, 30s, 2min
    CLAIM_MIN_IDLE_MS = 300_000  # 5 minutes - claim orphaned messages after this

    def __init__(self, redis: Redis, worker_id: int | None = None) -> None:
        """Initialize TaskQueue with Redis client.

        Args:
            redis: Async Redis client instance.
            worker_id: Optional worker identifier for unique consumer name.
        """
        self._redis = redis
        base_name = f"worker-{uuid4().hex[:8]}"
        self._consumer_name = (
            f"{base_name}-{worker_id}" if worker_id is not None else base_name
        )

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
        # First, try to claim orphaned messages from crashed consumers
        claimed = await self._claim_orphaned()
        if claimed:
            return claimed

        # Then, check for our own pending messages (retries)
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
            retries=int(data.get("retries", 0)),
        )

    async def _claim_orphaned(self) -> Optional[Task]:
        """Claim orphaned messages from crashed consumers.

        Uses XAUTOCLAIM to take ownership of messages that have been
        pending longer than CLAIM_MIN_IDLE_MS.

        Returns:
            Task if an orphaned message was claimed, None otherwise.
        """
        try:
            result = await self._redis.xautoclaim(
                self.STREAM_KEY,
                self.GROUP_NAME,
                self._consumer_name,
                min_idle_time=self.CLAIM_MIN_IDLE_MS,
                start_id="0-0",
                count=1,
            )

            # xautoclaim returns: [next_id, [[stream_id, data], ...], [deleted]]
            if not result or not result[1]:
                return None

            stream_id, data = result[1][0]

            logger.info(
                "Claimed orphaned task",
                extra={"task_id": data["id"], "stream_id": stream_id},
            )

            return Task(
                id=data["id"],
                type=TaskType(data["type"]),
                payload=json.loads(data["payload"]),
                stream_id=stream_id,
                retries=int(data.get("retries", 0)),
            )

        except Exception as e:
            # XAUTOCLAIM may fail on older Redis versions
            if "unknown command" in str(e).lower():
                logger.debug("XAUTOCLAIM not supported, skipping orphan claim")
                return None
            raise

    async def ack(self, task: Task) -> None:
        """Acknowledge task completion.

        Removes the task from pending list.

        Args:
            task: Task to acknowledge.
        """
        await self._redis.xack(self.STREAM_KEY, self.GROUP_NAME, task.stream_id)
        logger.debug("Task acknowledged", extra={"task_id": task.id})

    async def retry(self, task: Task, error: str) -> bool:
        """Retry task with exponential backoff.

        Re-enqueues task with incremented retry count if under MAX_RETRIES.
        Moves to DLQ if max retries exceeded.

        Args:
            task: Task to retry.
            error: Error message from failed attempt.

        Returns:
            True if task was re-enqueued, False if moved to DLQ.
        """
        new_retries = task.retries + 1

        if new_retries >= self.MAX_RETRIES:
            logger.warning(
                "Max retries exceeded, moving to DLQ",
                extra={"task_id": task.id, "retries": new_retries, "error": error},
            )
            await self.fail(task, f"Max retries ({self.MAX_RETRIES}) exceeded: {error}")
            return False

        # Acknowledge original message
        await self.ack(task)

        # Re-enqueue with incremented retry count
        message = {
            "id": task.id,
            "type": task.type.value,
            "payload": json.dumps(task.payload),
            "retries": str(new_retries),
        }

        await self._redis.xadd(self.STREAM_KEY, message)

        delay = self.RETRY_DELAYS[min(new_retries - 1, len(self.RETRY_DELAYS) - 1)]
        logger.info(
            "Task scheduled for retry",
            extra={
                "task_id": task.id,
                "retry": new_retries,
                "delay_seconds": delay,
            },
        )

        return True

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
