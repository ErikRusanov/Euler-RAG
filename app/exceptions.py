"""Application exceptions."""


class AppError(Exception):
    """Base exception for application errors."""


class ModelError(AppError):
    """Base exception for model/database operations."""


class RecordNotFoundError(ModelError):
    """Raised when a record is not found in the database."""

    def __init__(self, model_name: str, record_id: int):
        self.model_name = model_name
        self.record_id = record_id
        super().__init__(f"{model_name} with id={record_id} not found")


class RelatedRecordNotFoundError(ModelError):
    """Raised when a related record (FK) is not found."""

    def __init__(self, field: str, record_id: int):
        self.field = field
        self.record_id = record_id
        super().__init__(f"Related record for '{field}' with id={record_id} not found")


class DatabaseConnectionError(ModelError):
    """Raised when database connection fails."""


class InvalidFilterError(ModelError):
    """Raised when invalid filter is provided."""


class S3ConnectionError(AppError):
    """Raised when S3 connection fails."""


class S3OperationError(AppError):
    """Raised when S3 operation fails."""


class InvalidFileTypeError(AppError):
    """Raised when uploaded file type is not allowed."""

    def __init__(self, allowed_types: list[str], received_type: str):
        self.allowed_types = allowed_types
        self.received_type = received_type
        super().__init__(
            f"Invalid file type '{received_type}'. Allowed: {', '.join(allowed_types)}"
        )


class RedisConnectionError(AppError):
    """Raised when Redis connection fails."""


class RedisOperationError(AppError):
    """Raised when Redis operation fails."""


class TaskEnqueueError(AppError):
    """Raised when task enqueueing to Redis fails.

    This exception is raised when a background task cannot be enqueued,
    indicating that the requested operation could not be scheduled.
    """

    def __init__(self, task_type: str, resource_id: int, original_error: str):
        """Initialize TaskEnqueueError.

        Args:
            task_type: Type of task that failed to enqueue.
            resource_id: ID of the resource the task was for.
            original_error: Original error message from the queue.
        """
        self.task_type = task_type
        self.resource_id = resource_id
        self.original_error = original_error
        super().__init__(
            f"Failed to enqueue {task_type} task for resource {resource_id}: "
            f"{original_error}"
        )
