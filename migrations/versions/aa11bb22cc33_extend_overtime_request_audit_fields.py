"""extend overtime request audit fields

Revision ID: aa11bb22cc33
Revises: f1a2b3c4d5e6
Create Date: 2026-04-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "aa11bb22cc33"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in [col["name"] for col in inspector.get_columns(table_name)]


def _has_fk(table_name: str, fk_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(table_name))


def upgrade():
    with op.batch_alter_table("overtime_requests", schema=None) as batch_op:
        if not _has_column("overtime_requests", "requested_hours"):
            batch_op.add_column(sa.Column("requested_hours", sa.Numeric(precision=5, scale=2), nullable=True))
        if not _has_column("overtime_requests", "approved_hours"):
            batch_op.add_column(sa.Column("approved_hours", sa.Numeric(precision=5, scale=2), nullable=True))
        if not _has_column("overtime_requests", "start_ot_time"):
            batch_op.add_column(sa.Column("start_ot_time", sa.DateTime(timezone=True), nullable=True))
        if not _has_column("overtime_requests", "end_ot_time"):
            batch_op.add_column(sa.Column("end_ot_time", sa.DateTime(timezone=True), nullable=True))
        if not _has_column("overtime_requests", "approved_by"):
            batch_op.add_column(sa.Column("approved_by", sa.Integer(), nullable=True))
        if not _has_column("overtime_requests", "approved_at"):
            batch_op.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))

    if not _has_fk("overtime_requests", "fk_overtime_requests_approved_by_employees"):
        op.create_foreign_key(
            "fk_overtime_requests_approved_by_employees",
            "overtime_requests",
            "employees",
            ["approved_by"],
            ["id"],
        )


def downgrade():
    if _has_fk("overtime_requests", "fk_overtime_requests_approved_by_employees"):
        op.drop_constraint("fk_overtime_requests_approved_by_employees", "overtime_requests", type_="foreignkey")
    with op.batch_alter_table("overtime_requests", schema=None) as batch_op:
        if _has_column("overtime_requests", "approved_at"):
            batch_op.drop_column("approved_at")
        if _has_column("overtime_requests", "approved_by"):
            batch_op.drop_column("approved_by")
        if _has_column("overtime_requests", "end_ot_time"):
            batch_op.drop_column("end_ot_time")
        if _has_column("overtime_requests", "start_ot_time"):
            batch_op.drop_column("start_ot_time")
        if _has_column("overtime_requests", "approved_hours"):
            batch_op.drop_column("approved_hours")
        if _has_column("overtime_requests", "requested_hours"):
            batch_op.drop_column("requested_hours")