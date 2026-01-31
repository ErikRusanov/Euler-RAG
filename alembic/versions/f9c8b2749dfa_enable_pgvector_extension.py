"""enable pgvector extension

Revision ID: f9c8b2749dfa
Revises: 785c4b0d0067
Create Date: 2026-01-31 22:43:32.542821

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9c8b2749dfa"
down_revision: Union[str, None] = "785c4b0d0067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable pgvector extension for vector similarity search."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Disable pgvector extension."""
    op.execute("DROP EXTENSION IF EXISTS vector")
