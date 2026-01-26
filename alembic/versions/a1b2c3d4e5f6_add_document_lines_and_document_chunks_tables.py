"""add document_lines and document_chunks tables

Revision ID: a1b2c3d4e5f6
Revises: 27e587aa5559
Create Date: 2026-01-26 21:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "27e587aa5559"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create document_lines and document_chunks tables."""
    # Create document_lines table
    op.create_table(
        "document_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("line_type", sa.String(length=50), nullable=False),
        sa.Column("font_size", sa.Integer(), nullable=True),
        sa.Column("is_printed", sa.Boolean(), nullable=False),
        sa.Column("is_handwritten", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("region", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "raw_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_lines_document_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_lines"),
        sa.UniqueConstraint(
            "document_id",
            "page_number",
            "line_number",
            name="uq_document_lines_document_page_line",
        ),
    )
    op.create_index(
        "ix_document_lines_document_id", "document_lines", ["document_id"], unique=False
    )
    op.create_index(
        "ix_document_lines_page_number", "document_lines", ["page_number"], unique=False
    )
    op.create_index(
        "ix_document_lines_line_type", "document_lines", ["line_type"], unique=False
    )

    # Create document_chunks table
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("end_page", sa.Integer(), nullable=False),
        sa.Column("start_line_id", sa.Integer(), nullable=True),
        sa.Column("end_line_id", sa.Integer(), nullable=True),
        sa.Column("chunk_type", sa.String(length=50), nullable=True),
        sa.Column("section_title", sa.String(length=500), nullable=True),
        sa.Column("qdrant_point_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_chunks_document_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["start_line_id"],
            ["document_lines.id"],
            name="fk_document_chunks_start_line_id",
        ),
        sa.ForeignKeyConstraint(
            ["end_line_id"],
            ["document_lines.id"],
            name="fk_document_chunks_end_line_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_chunks"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_chunk_index",
        ),
        sa.UniqueConstraint("qdrant_point_id", name="uq_document_chunks_qdrant_point"),
    )
    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_chunks_chunk_index",
        "document_chunks",
        ["chunk_index"],
        unique=False,
    )
    op.create_index(
        "ix_document_chunks_chunk_type", "document_chunks", ["chunk_type"], unique=False
    )


def downgrade() -> None:
    """Drop document_lines and document_chunks tables."""
    # Drop document_chunks first due to foreign key dependency on document_lines
    op.drop_index("ix_document_chunks_chunk_type", table_name="document_chunks")
    op.drop_index("ix_document_chunks_chunk_index", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")

    # Drop document_lines
    op.drop_index("ix_document_lines_line_type", table_name="document_lines")
    op.drop_index("ix_document_lines_page_number", table_name="document_lines")
    op.drop_index("ix_document_lines_document_id", table_name="document_lines")
    op.drop_table("document_lines")
