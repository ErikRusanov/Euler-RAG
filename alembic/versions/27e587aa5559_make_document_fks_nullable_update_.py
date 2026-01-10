"""make_document_fks_nullable_update_defaults

Revision ID: 27e587aa5559
Revises: 698c31130684
Create Date: 2026-01-10 22:51:36.729301

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "27e587aa5559"
down_revision: Union[str, None] = "698c31130684"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make foreign keys nullable
    op.alter_column(
        "documents", "subject_id", existing_type=sa.INTEGER(), nullable=True
    )
    op.alter_column(
        "documents", "teacher_id", existing_type=sa.INTEGER(), nullable=True
    )
    # Update progress default and make non-nullable
    op.execute(
        'UPDATE documents SET progress = \'{"page": 0, "total": 0}\' '
        "WHERE progress IS NULL"
    )
    op.alter_column(
        "documents",
        "progress",
        existing_type=sa.dialects.postgresql.JSONB(),
        nullable=False,
        server_default=sa.text('\'{"page": 0, "total": 0}\'::jsonb'),
    )


def downgrade() -> None:
    # Revert progress to nullable without default
    op.alter_column(
        "documents",
        "progress",
        existing_type=sa.dialects.postgresql.JSONB(),
        nullable=True,
        server_default=None,
    )
    # Revert foreign keys to non-nullable (will fail if NULL values exist)
    op.alter_column(
        "documents", "teacher_id", existing_type=sa.INTEGER(), nullable=False
    )
    op.alter_column(
        "documents", "subject_id", existing_type=sa.INTEGER(), nullable=False
    )
