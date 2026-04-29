"""add holiday ot fields to overtime request

Revision ID: 7c3b2a1f9d10
Revises: bbccddeeff00
Create Date: 2026-04-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7c3b2a1f9d10"
down_revision = "bbccddeeff00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "overtime_requests",
        sa.Column("is_holiday_ot", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "overtime_requests",
        sa.Column("holiday_multiplier", sa.Numeric(4, 2), nullable=False, server_default="1.00"),
    )


def downgrade() -> None:
    op.drop_column("overtime_requests", "holiday_multiplier")
    op.drop_column("overtime_requests", "is_holiday_ot")
