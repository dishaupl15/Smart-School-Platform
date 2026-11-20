"""Allow repeat transfers to a previously attended class in the same year.

Revision ID: 20261118_0006
Revises: 20261118_0005
Create Date: 2026-11-18
"""

import sqlalchemy as sa
from alembic import op

revision = "20261118_0006"
down_revision = "20261118_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("student_enrollments") as batch_op:
        batch_op.drop_constraint("uq_student_enrollments_identity", type_="unique")


def downgrade() -> None:
    with op.batch_alter_table("student_enrollments") as batch_op:
        batch_op.create_unique_constraint(
            "uq_student_enrollments_identity",
            ["student_id", "class_id", "academic_year"],
        )
