"""Worker manager handling task processing lifecycle.

Manages background task processing, starting workers on application
startup and handling graceful shutdown.
"""

import asyncio
import logging

from app.config import get_settings
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

    Starts multiple concurrent worker coroutines on application startup
    and handles graceful shutdown on SIGTERM/SIGINT.

    Usage:
        manager = WorkerManager()
        await manager.start()  # Start processing
        # ... application runs ...
        await manager.stop()   # Graceful shutdown

    Attributes:
        concurrency: Number of concurrent worker tasks (from settings).
    """

    def __init__(self) -> None:
        """Initialize WorkerManager with empty state."""
        settings = get_settings()
        self._concurrency = settings.worker_concurrency
        self._queues: list[TaskQueue] = []
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._handlers: dict[TaskType, BaseTaskHandler] = {}

    async def start(self) -> None:
        """Start the worker processing loop.

        Initializes task queues (one per worker), handlers, and begins processing.
        """
        redis = get_redis_client()

        # Create queue for setup (consumer group creation)
        setup_queue = TaskQueue(redis)
        await setup_queue.setup()

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

        # Start multiple concurrent worker tasks, each with its own queue
        for i in range(self._concurrency):
            queue = TaskQueue(redis, worker_id=i)
            self._queues.append(queue)
            task = asyncio.create_task(self._run(queue), name=f"worker-{i}")
            self._tasks.append(task)

        logger.info(
            "Worker manager started",
            extra={
                "concurrency": self._concurrency,
                "handlers": list(self._handlers.keys()),
            },
        )

    async def stop(self) -> None:
        """Stop the worker gracefully.

        Signals all worker loops to stop and waits for current
        tasks to complete.
        """
        logger.info(
            "Stopping worker manager...",
            extra={"active_tasks": len(self._tasks)},
        )
        self._running = False

        # Cancel all worker tasks
        for task in self._tasks:
            task.cancel()

        # Wait for all tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()
            self._queues.clear()

        logger.info("Worker manager stopped")

    async def _run(self, queue: TaskQueue) -> None:
        """Main processing loop for a single worker.

        Args:
            queue: TaskQueue instance with unique consumer name for this worker.
        """
        while self._running:
            try:
                task = await queue.dequeue(block_ms=5000)

                if task is None:
                    continue

                handler = self._handlers.get(task.type)
                if not handler:
                    logger.error(
                        "No handler for task type",
                        extra={"type": task.type},
                    )
                    await queue.fail(task, f"Unknown task type: {task.type}")
                    continue

                try:
                    await handler.execute(task)
                    await queue.ack(task)
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
                        await queue.retry(task, str(e))
                    else:
                        await queue.fail(task, str(e))

                except Exception as e:
                    logger.exception(
                        "Unexpected task error",
                        extra={"task_id": task.id, "error": str(e)},
                    )
                    await queue.fail(task, str(e))

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Unexpected error in worker loop")
                await asyncio.sleep(1)  # Prevent tight loop on errors


# Global worker manager instance
worker_manager = WorkerManager()
