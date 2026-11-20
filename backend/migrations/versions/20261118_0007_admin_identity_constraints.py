"""Add normalized uniqueness constraints for school admin records.

Revision ID: 20261118_0007
Revises: 20261118_0006
Create Date: 2026-11-18
"""

import sqlalchemy as sa
from alembic import op

revision = "20261118_0007"
down_revision = "20261118_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_academic_classes_identity_no_section",
        "academic_classes",
        ["school_id", "academic_year", "grade_number"],
        unique=True,
        postgresql_where=sa.text("section IS NULL"),
        sqlite_where=sa.text("section IS NULL"),
    )
    op.create_index(
        "uq_subjects_school_code_lower",
        "subjects",
        ["school_id", sa.text("lower(code)")],
        unique=True,
    )
    op.create_index(
        "uq_subjects_school_name_lower",
        "subjects",
        ["school_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "uq_users_school_username_lower",
        "users",
        ["school_id", sa.text("lower(username)")],
        unique=True,
        postgresql_where=sa.text("school_id IS NOT NULL AND username IS NOT NULL"),
        sqlite_where=sa.text("school_id IS NOT NULL AND username IS NOT NULL"),
    )
    op.create_index(
        "uq_users_school_email_lower",
        "users",
        ["school_id", sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("school_id IS NOT NULL AND email IS NOT NULL"),
        sqlite_where=sa.text("school_id IS NOT NULL AND email IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_school_email_lower", table_name="users")
    op.drop_index("uq_users_school_username_lower", table_name="users")
    op.drop_index("uq_subjects_school_name_lower", table_name="subjects")
    op.drop_index("uq_subjects_school_code_lower", table_name="subjects")
    op.drop_index(
        "uq_academic_classes_identity_no_section",
        table_name="academic_classes",
    )
