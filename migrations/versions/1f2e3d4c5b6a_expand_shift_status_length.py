"""expand attendance.shift_status length

Revision ID: 1f2e3d4c5b6a
Revises: add_enterprise_attendance_flow
Create Date: 2026-05-02 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1f2e3d4c5b6a"
down_revision = "add_enterprise_attendance_flow"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "attendance",
        "shift_status",
        existing_type=sa.String(length=30),
        type_=sa.String(length=64),
        existing_nullable=False,
        existing_server_default="not_started",
    )


def downgrade():
    op.alter_column(
        "attendance",
        "shift_status",
        existing_type=sa.String(length=64),
        type_=sa.String(length=30),
        existing_nullable=False,
        existing_server_default="not_started",
    )