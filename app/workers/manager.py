"""Worker manager handling task processing lifecycle.

Manages background task processing, starting workers on application
startup and handling graceful shutdown.
"""

import asyncio
import logging
from typing import Optional

from app.utils.db import db_manager
from app.utils.redis import get_redis_client
from app.utils.s3 import get_s3_storage
from app.workers.handlers.base import BaseTaskHandler, TaskError
from app.workers.handlers.document import DocumentHandler
from app.workers.progress import ProgressTracker
from app.workers.queue import TaskQueue, TaskType

logger = logging.getLogger(__name__)


class WorkerManager:
    """Manages background task processing.

    Starts worker coroutines on application startup and handles
    graceful shutdown on SIGTERM/SIGINT.

    Usage:
        manager = WorkerManager()
        await manager.start()  # Start processing
        # ... application runs ...
        await manager.stop()   # Graceful shutdown
    """

    def __init__(self) -> None:
        """Initialize WorkerManager with empty state."""
        self._queue: Optional[TaskQueue] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._handlers: dict[TaskType, BaseTaskHandler] = {}

    async def start(self) -> None:
        """Start the worker processing loop.

        Initializes task queue, handlers, and begins processing.
        """
        redis = get_redis_client()
        self._queue = TaskQueue(redis)
        await self._queue.setup()

        # Initialize progress tracker
        progress_tracker = ProgressTracker(redis)

        # Initialize handlers with dependencies
        session_factory = db_manager.session_factory
        s3 = get_s3_storage()

        self._handlers = {
            TaskType.DOCUMENT_PROCESS: DocumentHandler(
                session_factory=session_factory,
                s3=s3,
                progress_tracker=progress_tracker,
            ),
        }

        self._running = True
        self._task = asyncio.create_task(self._run())

        logger.info(
            "Worker manager started",
            extra={"handlers": list(self._handlers.keys())},
        )

    async def stop(self) -> None:
        """Stop the worker gracefully.

        Signals the worker loop to stop and waits for current
        task to complete.
        """
        logger.info("Stopping worker manager...")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Worker manager stopped")

    async def _run(self) -> None:
        """Main processing loop.

        Continuously dequeues and processes tasks until stopped.
        """
        while self._running:
            try:
                task = await self._queue.dequeue(block_ms=5000)

                if task is None:
                    continue

                handler = self._handlers.get(task.type)
                if not handler:
                    logger.error(
                        "No handler for task type",
                        extra={"type": task.type},
                    )
                    await self._queue.fail(task, f"Unknown task type: {task.type}")
                    continue

                try:
                    await handler.execute(task)
                    await self._queue.ack(task)
                    logger.info(
                        "Task completed",
                        extra={"task_id": task.id, "type": task.type.value},
                    )

                except TaskError as e:
                    logger.warning(
                        "Task failed",
                        extra={
                            "task_id": task.id,
                            "error": str(e),
                            "retryable": e.retryable,
                        },
                    )
                    if e.retryable:
                        await self._queue.retry(task, str(e))
                    else:
                        await self._queue.fail(task, str(e))

                except Exception as e:
                    logger.exception(
                        "Unexpected task error",
                        extra={"task_id": task.id, "error": str(e)},
                    )
                    await self._queue.fail(task, str(e))

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Unexpected error in worker loop")
                await asyncio.sleep(1)  # Prevent tight loop on errors


# Global worker manager instance
worker_manager = WorkerManager()
