"""Unit tests for TaskQueue with Redis Streams."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.workers.queue import Task, TaskQueue, TaskType


@pytest.fixture
def mock_redis() -> MagicMock:
    """Create mock Redis client."""
    return MagicMock()


@pytest.fixture
def task_queue(mock_redis: MagicMock) -> TaskQueue:
    """Create TaskQueue with mock Redis."""
    return TaskQueue(mock_redis)


class TestTaskQueueEnqueue:
    """Tests for TaskQueue.enqueue method."""

    @pytest.mark.asyncio
    async def test_enqueue_returns_task_id(
        self, task_queue: TaskQueue, mock_redis: MagicMock
    ):
        """Enqueue should return a unique task ID."""
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")

        task_id = await task_queue.enqueue(
            TaskType.DOCUMENT_PROCESS, {"document_id": 1}
        )

        assert task_id is not None
        assert isinstance(task_id, str)
        assert len(task_id) == 32  # hex UUID

    @pytest.mark.asyncio
    async def test_enqueue_adds_to_stream(
        self, task_queue: TaskQueue, mock_redis: MagicMock
    ):
        """Enqueue should add message to Redis stream."""
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")

        await task_queue.enqueue(TaskType.DOCUMENT_PROCESS, {"document_id": 42})

        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == TaskQueue.STREAM_KEY
        message = call_args[0][1]
        assert message["type"] == TaskType.DOCUMENT_PROCESS.value
        assert json.loads(message["payload"]) == {"document_id": 42}


class TestTaskQueueDequeue:
    """Tests for TaskQueue.dequeue method."""

    @pytest.mark.asyncio
    async def test_dequeue_returns_task(
        self, task_queue: TaskQueue, mock_redis: MagicMock
    ):
        """Dequeue should return a Task object."""
        stream_id = "1234567890-0"
        task_data = {
            "id": "abc123",
            "type": TaskType.DOCUMENT_PROCESS.value,
            "payload": json.dumps({"document_id": 1}),
            "retries": "0",
        }
        # First call (pending) returns empty, second call (new) returns task
        mock_redis.xreadgroup = AsyncMock(
            side_effect=[
                [],  # No pending messages
                [[TaskQueue.STREAM_KEY, [(stream_id, task_data)]]],  # New message
            ]
        )

        task = await task_queue.dequeue(block_ms=100)

        assert task is not None
        assert isinstance(task, Task)
        assert task.id == "abc123"
        assert task.type == TaskType.DOCUMENT_PROCESS
        assert task.payload == {"document_id": 1}
        assert task.stream_id == stream_id

    @pytest.mark.asyncio
    async def test_dequeue_returns_none_on_timeout(
        self, task_queue: TaskQueue, mock_redis: MagicMock
    ):
        """Dequeue should return None when no tasks available."""
        mock_redis.xreadgroup = AsyncMock(return_value=[])

        task = await task_queue.dequeue(block_ms=100)

        assert task is None


class TestTaskQueueAck:
    """Tests for TaskQueue.ack method."""

    @pytest.mark.asyncio
    async def test_ack_removes_from_pending(
        self, task_queue: TaskQueue, mock_redis: MagicMock
    ):
        """Ack should acknowledge message in Redis stream."""
        mock_redis.xack = AsyncMock(return_value=1)

        task = Task(
            id="abc123",
            type=TaskType.DOCUMENT_PROCESS,
            payload={"document_id": 1},
            stream_id="1234567890-0",
        )

        await task_queue.ack(task)

        mock_redis.xack.assert_called_once_with(
            TaskQueue.STREAM_KEY, TaskQueue.GROUP_NAME, task.stream_id
        )


class TestTaskQueueFail:
    """Tests for TaskQueue.fail method."""

    @pytest.mark.asyncio
    async def test_fail_moves_to_dlq(
        self, task_queue: TaskQueue, mock_redis: MagicMock
    ):
        """Fail should move task to dead letter queue."""
        mock_redis.xadd = AsyncMock()
        mock_redis.xack = AsyncMock()

        task = Task(
            id="abc123",
            type=TaskType.DOCUMENT_PROCESS,
            payload={"document_id": 1},
            stream_id="1234567890-0",
        )

        await task_queue.fail(task, "Processing failed")

        # Should add to DLQ
        dlq_call = mock_redis.xadd.call_args
        assert dlq_call[0][0] == TaskQueue.DLQ_KEY

        # Should acknowledge original message
        mock_redis.xack.assert_called_once()
