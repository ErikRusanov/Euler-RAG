"""Base task handler with common functionality.

Provides abstract base class for task handlers with timeout management,
error handling, and database session management.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.workers.queue import Task

logger = logging.getLogger(__name__)


class TaskError(Exception):
    """Raised when task processing fails.

    Attributes:
        message: Error description.
        retryable: Whether the task can be retried.
    """

    def __init__(self, message: str, retryable: bool = True) -> None:
        """Initialize TaskError.

        Args:
            message: Error description.
            retryable: Whether the task can be retried.
        """
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class BaseTaskHandler(ABC):
    """Abstract base class for task handlers.

    Provides common functionality for task processing including
    timeout management, error handling, and database session lifecycle.

    Attributes:
        TIMEOUT_SECONDS: Maximum time for task processing.
    """

    TIMEOUT_SECONDS: int = 300  # 5 minutes default

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize handler with session factory.

        Args:
            session_factory: Factory for creating database sessions.
        """
        self._session_factory = session_factory

    @abstractmethod
    async def process(self, task: Task, db: AsyncSession) -> None:
        """Process the task.

        Must be implemented by subclasses to define task-specific logic.

        Args:
            task: Task to process.
            db: Database session for operations.
        """

    @abstractmethod
    async def update_status(
        self,
        db: AsyncSession,
        record_id: int,
        status: str,
        error: str | None = None,
        **extra_fields: Any,
    ) -> None:
        """Update record status in database.

        Must be implemented by subclasses.

        Args:
            db: Database session.
            record_id: ID of record to update.
            status: New status value.
            error: Optional error message.
            **extra_fields: Additional fields to update.
        """

    async def execute(self, task: Task) -> None:
        """Execute task with timeout and error handling.

        Creates database session, handles timeouts, and manages
        transaction commit/rollback.

        Args:
            task: Task to execute.

        Raises:
            TaskError: If task processing fails.
        """
        async with self._session_factory() as db:
            try:
                await asyncio.wait_for(
                    self.process(task, db),
                    timeout=self.TIMEOUT_SECONDS,
                )
                await db.commit()

            except asyncio.TimeoutError:
                await db.rollback()
                raise TaskError(
                    f"Task timed out after {self.TIMEOUT_SECONDS}s",
                    retryable=True,
                )
            except TaskError:
                await db.rollback()
                raise
            except Exception as e:
                await db.rollback()
                logger.exception(
                    "Unexpected error in task",
                    extra={"task_id": task.id},
                )
                raise TaskError(str(e), retryable=False)
