"""add embedding column to document_chunks

Revision ID: 7c69cc9f8407
Revises: f9c8b2749dfa
Create Date: 2026-01-31 22:43:48.598670

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c69cc9f8407"
down_revision: Union[str, None] = "f9c8b2749dfa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add embedding column and HNSW index to document_chunks table."""
    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN embedding vector(1024)
    """
    )

    op.execute(
        """
        CREATE INDEX idx_chunk_embedding_cosine
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 200)
    """
    )


def downgrade() -> None:
    """Remove embedding column and index from document_chunks table."""
    op.execute("DROP INDEX IF EXISTS idx_chunk_embedding_cosine")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
