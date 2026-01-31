"""SQLAlchemy custom type for PostgreSQL pgvector extension."""

from typing import List, Optional

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    """PostgreSQL pgvector type for SQLAlchemy.

    Handles storage and retrieval of vector embeddings in PostgreSQL using
    the pgvector extension.

    Args:
        dim: Dimensionality of the vector (e.g., 1024 for text-embedding-3-large).
    """

    cache_ok = True

    def __init__(self, dim: int):
        """Initialize Vector type with specified dimensions.

        Args:
            dim: Number of dimensions in the vector.
        """
        self.dim = dim
        super().__init__()

    def get_col_spec(self, **kw) -> str:
        """Return the column specification for DDL.

        Returns:
            PostgreSQL vector type specification string.
        """
        return f"vector({self.dim})"

    def bind_processor(self, dialect):
        """Process Python values before sending to database.

        Args:
            dialect: SQLAlchemy dialect instance.

        Returns:
            Function that converts Python list to pgvector string format.
        """

        def process(value: Optional[List[float]]) -> Optional[str]:
            """Convert Python list to pgvector string format.

            Args:
                value: Python list of floats or None.

            Returns:
                String in pgvector format "[x,y,z,...]" or None.
            """
            if value is None:
                return None
            return f"[{','.join(str(v) for v in value)}]"

        return process

    def result_processor(self, dialect, coltype):
        """Process database values before returning to Python.

        Args:
            dialect: SQLAlchemy dialect instance.
            coltype: Column type from database.

        Returns:
            Function that converts pgvector string to Python list.
        """

        def process(value: Optional[str]) -> Optional[List[float]]:
            """Convert pgvector string format to Python list.

            Args:
                value: String in pgvector format "[x,y,z,...]" or None.

            Returns:
                Python list of floats or None.
            """
            if value is None:
                return None
            # Parse "[0.1,0.2,...]" format
            return [float(v) for v in value.strip("[]").split(",")]

        return process
