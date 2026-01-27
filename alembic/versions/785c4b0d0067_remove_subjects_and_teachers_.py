"""remove_subjects_and_teachers_functionality

Revision ID: 785c4b0d0067
Revises: a1b2c3d4e5f6
Create Date: 2026-01-27 12:31:35.121393

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "785c4b0d0067"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop FK constraints from solve_requests
    op.drop_constraint(
        "solve_requests_matched_subject_id_fkey", "solve_requests", type_="foreignkey"
    )
    op.drop_constraint(
        "solve_requests_matched_teacher_id_fkey", "solve_requests", type_="foreignkey"
    )

    # Drop indexes from solve_requests
    op.drop_index("ix_solve_requests_matched_subject_id", table_name="solve_requests")
    op.drop_index("ix_solve_requests_matched_teacher_id", table_name="solve_requests")

    # Drop columns from solve_requests
    op.drop_column("solve_requests", "matched_subject_id")
    op.drop_column("solve_requests", "matched_teacher_id")

    # Drop FK constraints from documents
    op.drop_constraint("documents_subject_id_fkey", "documents", type_="foreignkey")
    op.drop_constraint("documents_teacher_id_fkey", "documents", type_="foreignkey")

    # Drop indexes from documents
    op.drop_index("ix_documents_subject_id", table_name="documents")
    op.drop_index("ix_documents_teacher_id", table_name="documents")

    # Drop columns from documents
    op.drop_column("documents", "subject_id")
    op.drop_column("documents", "teacher_id")

    # Drop teachers table (and its index)
    op.drop_index("ix_teachers_name", table_name="teachers")
    op.drop_table("teachers")

    # Drop subjects table (and its indexes)
    op.drop_index("ix_subjects_name", table_name="subjects")
    op.drop_index("ix_subjects_semester", table_name="subjects")
    op.drop_table("subjects")


def downgrade() -> None:
    # Recreate subjects table
    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "semester", name="uq_subjects_name_semester"),
    )
    op.create_index("ix_subjects_name", "subjects", ["name"])
    op.create_index("ix_subjects_semester", "subjects", ["semester"])

    # Recreate teachers table
    op.create_table(
        "teachers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_teachers_name", "teachers", ["name"])

    # Restore columns in documents
    op.add_column("documents", sa.Column("subject_id", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("teacher_id", sa.Integer(), nullable=True))
    op.create_index("ix_documents_subject_id", "documents", ["subject_id"])
    op.create_index("ix_documents_teacher_id", "documents", ["teacher_id"])
    op.create_foreign_key(
        "documents_subject_id_fkey", "documents", "subjects", ["subject_id"], ["id"]
    )
    op.create_foreign_key(
        "documents_teacher_id_fkey", "documents", "teachers", ["teacher_id"], ["id"]
    )

    # Restore columns in solve_requests
    op.add_column(
        "solve_requests", sa.Column("matched_subject_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "solve_requests", sa.Column("matched_teacher_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        "ix_solve_requests_matched_subject_id", "solve_requests", ["matched_subject_id"]
    )
    op.create_index(
        "ix_solve_requests_matched_teacher_id", "solve_requests", ["matched_teacher_id"]
    )
    op.create_foreign_key(
        "solve_requests_matched_subject_id_fkey",
        "solve_requests",
        "subjects",
        ["matched_subject_id"],
        ["id"],
    )
    op.create_foreign_key(
        "solve_requests_matched_teacher_id_fkey",
        "solve_requests",
        "teachers",
        ["matched_teacher_id"],
        ["id"],
    )
