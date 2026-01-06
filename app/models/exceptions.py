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
