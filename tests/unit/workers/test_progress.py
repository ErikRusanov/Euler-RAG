"""Unit tests for ProgressTracker."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.workers.progress import Progress, ProgressTracker


@pytest.fixture
def mock_redis() -> MagicMock:
    """Create mock Redis client."""
    return MagicMock()


@pytest.fixture
def progress_tracker(mock_redis: MagicMock) -> ProgressTracker:
    """Create ProgressTracker with mock Redis."""
    return ProgressTracker(mock_redis)


class TestProgressTrackerUpdate:
    """Tests for ProgressTracker.update method."""

    @pytest.mark.asyncio
    async def test_update_stores_progress(
        self, progress_tracker: ProgressTracker, mock_redis: MagicMock
    ):
        """Update should store progress in Redis with TTL."""
        mock_redis.setex = AsyncMock()
        mock_redis.publish = AsyncMock()

        progress = Progress(
            document_id=1,
            page=5,
            total=10,
            status="processing",
            message="Parsing page 5/10",
        )

        await progress_tracker.update(progress)

        # Verify setex was called with correct key and TTL
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert f"{ProgressTracker.KEY_PREFIX}1" in call_args[0][0]
        assert call_args[0][1] == ProgressTracker.TTL_SECONDS

        # Verify data structure
        stored_data = json.loads(call_args[0][2])
        assert stored_data["document_id"] == 1
        assert stored_data["page"] == 5
        assert stored_data["total"] == 10
        assert stored_data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_update_publishes_to_channel(
        self, progress_tracker: ProgressTracker, mock_redis: MagicMock
    ):
        """Update should publish progress to Redis channel."""
        mock_redis.setex = AsyncMock()
        mock_redis.publish = AsyncMock()

        progress = Progress(
            document_id=42,
            page=1,
            total=5,
            status="processing",
        )

        await progress_tracker.update(progress)

        mock_redis.publish.assert_called_once()
        channel = mock_redis.publish.call_args[0][0]
        assert f"{ProgressTracker.CHANNEL_PREFIX}42" == channel


class TestProgressTrackerGet:
    """Tests for ProgressTracker.get method."""

    @pytest.mark.asyncio
    async def test_get_returns_current_progress(
        self, progress_tracker: ProgressTracker, mock_redis: MagicMock
    ):
        """Get should return Progress object from Redis."""
        stored_data = json.dumps(
            {
                "document_id": 1,
                "page": 3,
                "total": 10,
                "status": "processing",
                "message": "Working...",
            }
        )
        mock_redis.get = AsyncMock(return_value=stored_data)

        progress = await progress_tracker.get(1)

        assert progress is not None
        assert progress.document_id == 1
        assert progress.page == 3
        assert progress.total == 10
        assert progress.status == "processing"
        assert progress.message == "Working..."

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_exists(
        self, progress_tracker: ProgressTracker, mock_redis: MagicMock
    ):
        """Get should return None when no progress stored."""
        mock_redis.get = AsyncMock(return_value=None)

        progress = await progress_tracker.get(999)

        assert progress is None


class TestProgressTrackerClear:
    """Tests for ProgressTracker.clear method."""

    @pytest.mark.asyncio
    async def test_clear_deletes_progress(
        self, progress_tracker: ProgressTracker, mock_redis: MagicMock
    ):
        """Clear should delete progress from Redis."""
        mock_redis.delete = AsyncMock()

        await progress_tracker.clear(1)

        mock_redis.delete.assert_called_once_with(f"{ProgressTracker.KEY_PREFIX}1")
