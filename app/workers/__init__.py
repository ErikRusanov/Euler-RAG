"""Background worker package for async task processing.

Provides Redis Streams based task queue, progress tracking,
and handlers for document processing.
"""

from app.workers.handlers import BaseTaskHandler, DocumentHandler, TaskError
from app.workers.manager import WorkerManager, worker_manager
from app.workers.progress import Progress, ProgressTracker
from app.workers.queue import Task, TaskQueue, TaskType

__all__ = [
    # Queue
    "Task",
    "TaskQueue",
    "TaskType",
    # Progress
    "Progress",
    "ProgressTracker",
    # Handlers
    "BaseTaskHandler",
    "TaskError",
    "DocumentHandler",
    # Manager
    "WorkerManager",
    "worker_manager",
]
