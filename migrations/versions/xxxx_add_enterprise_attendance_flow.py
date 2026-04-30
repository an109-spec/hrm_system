# migrations/versions/xxxx_add_enterprise_attendance_flow.py

"""add enterprise attendance flow

Revision ID: add_enterprise_attendance_flow
Revises: 7c3b2a1f9d10
Create Date: 2026-04-30

"""

from alembic import op
import sqlalchemy as sa


# sửa đúng revision trước đó của bạn
revision = "add_enterprise_attendance_flow"
down_revision = "7c3b2a1f9d10"
branch_labels = None
depends_on = None


def upgrade():
    # =========================================
    # overtime check
    # =========================================

    op.add_column(
        "attendance",
        sa.Column(
            "overtime_check_in",
            sa.DateTime(timezone=True),
            nullable=True
        )
    )

    op.add_column(
        "attendance",
        sa.Column(
            "overtime_check_out",
            sa.DateTime(timezone=True),
            nullable=True
        )
    )

    # =========================================
    # day type
    # =========================================

    op.add_column(
        "attendance",
        sa.Column(
            "is_weekend",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false")
        )
    )

    op.add_column(
        "attendance",
        sa.Column(
            "is_holiday",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false")
        )
    )

    # =========================================
    # late + half day
    # =========================================

    op.add_column(
        "attendance",
        sa.Column(
            "late_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0"
        )
    )

    op.add_column(
        "attendance",
        sa.Column(
            "is_half_day",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false")
        )
    )

    # =========================================
    # shift status
    # =========================================

    op.add_column(
        "attendance",
        sa.Column(
            "shift_status",
            sa.String(length=30),
            nullable=False,
            server_default="not_started"
        )
    )

    # =========================================
    # expand numeric precision
    # =========================================

    op.alter_column(
        "attendance",
        "working_hours",
        existing_type=sa.Numeric(4, 2),
        type_=sa.Numeric(6, 2),
        existing_nullable=True
    )

    op.alter_column(
        "attendance",
        "regular_hours",
        existing_type=sa.Numeric(4, 2),
        type_=sa.Numeric(6, 2),
        existing_nullable=True
    )

    op.alter_column(
        "attendance",
        "overtime_hours",
        existing_type=sa.Numeric(4, 2),
        type_=sa.Numeric(6, 2),
        existing_nullable=True
    )


def downgrade():
    op.drop_column("attendance", "shift_status")
    op.drop_column("attendance", "is_half_day")
    op.drop_column("attendance", "late_minutes")
    op.drop_column("attendance", "is_holiday")
    op.drop_column("attendance", "is_weekend")
    op.drop_column("attendance", "overtime_check_out")
    op.drop_column("attendance", "overtime_check_in")