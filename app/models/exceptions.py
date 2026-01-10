"""Model-related exceptions."""


class ModelError(Exception):
    """Base exception for model operations."""


class RecordNotFoundError(ModelError):
    """Raised when a record is not found in the database."""

    def __init__(self, model_name: str, record_id: int):
        self.model_name = model_name
        self.record_id = record_id
        super().__init__(f"{model_name} with id={record_id} not found")


class DatabaseConnectionError(ModelError):
    """Raised when database connection fails."""


class InvalidFilterError(ModelError):
    """Raised when invalid filter is provided."""


class S3ConnectionError(Exception):
    """Raised when S3 connection fails."""


class S3OperationError(Exception):
    """Raised when S3 operation fails."""


class InvalidFileTypeError(Exception):
    """Raised when uploaded file type is not allowed."""

    def __init__(self, allowed_types: list[str], received_type: str):
        self.allowed_types = allowed_types
        self.received_type = received_type
        super().__init__(
            f"Invalid file type '{received_type}'. Allowed: {', '.join(allowed_types)}"
        )


class RelatedRecordNotFoundError(ModelError):
    """Raised when a related record (FK) is not found."""

    def __init__(self, field: str, record_id: int):
        self.field = field
        self.record_id = record_id
        super().__init__(f"Related record for '{field}' with id={record_id} not found")
