"""add ess overtime and complaint columns

Revision ID: f1a2b3c4d5e6
Revises: c3d9f7a1b2e4
Create Date: 2026-04-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "c3d9f7a1b2e4"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in [col["name"] for col in inspector.get_columns(table_name)]


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade():
    # complaints: new fields for notification-linked complaint flow
    with op.batch_alter_table("complaints", schema=None) as batch_op:
        if not _has_column("complaints", "user_id"):
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        if not _has_column("complaints", "notification_id"):
            batch_op.add_column(sa.Column("notification_id", sa.Integer(), nullable=True))
        if not _has_column("complaints", "admin_reply"):
            batch_op.add_column(sa.Column("admin_reply", sa.Text(), nullable=True))
        if not _has_column("complaints", "closed_by_employee"):
            batch_op.add_column(sa.Column("closed_by_employee", sa.Boolean(), nullable=False, server_default=sa.false()))
        if not _has_column("complaints", "closed_at"):
            batch_op.add_column(sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))

    if not _has_column("complaints", "user_id"):
        pass
    else:
        if not _has_index("complaints", "ix_complaints_user_id"):
            op.create_index("ix_complaints_user_id", "complaints", ["user_id"], unique=False)
        op.create_foreign_key("fk_complaints_user_id_users", "complaints", "users", ["user_id"], ["id"])

    if _has_column("complaints", "notification_id"):
        if not _has_index("complaints", "ix_complaints_notification_id"):
            op.create_index("ix_complaints_notification_id", "complaints", ["notification_id"], unique=False)
        op.create_foreign_key("fk_complaints_notification_id_notifications", "complaints", "notifications", ["notification_id"], ["id"])

    # dependents: optional note field
    with op.batch_alter_table("dependents", schema=None) as batch_op:
        if not _has_column("dependents", "note"):
            batch_op.add_column(sa.Column("note", sa.Text(), nullable=True))

    # overtime request table
    if not _has_table("overtime_requests"):
        op.create_table(
            "overtime_requests",
            sa.Column("employee_id", sa.Integer(), nullable=False),
            sa.Column("overtime_date", sa.Date(), nullable=False),
            sa.Column("overtime_hours", sa.Numeric(precision=5, scale=2), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_manager"),
            sa.Column("manager_decision_by", sa.Integer(), nullable=True),
            sa.Column("manager_decision_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("manager_note", sa.Text(), nullable=True),
            sa.Column("hr_decision_by", sa.Integer(), nullable=True),
            sa.Column("hr_decision_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("hr_note", sa.Text(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("is_deleted", sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
            sa.ForeignKeyConstraint(["manager_decision_by"], ["employees.id"]),
            sa.ForeignKeyConstraint(["hr_decision_by"], ["employees.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_overtime_requests_employee_id", "overtime_requests", ["employee_id"], unique=False)
        op.create_index("ix_overtime_requests_overtime_date", "overtime_requests", ["overtime_date"], unique=False)
        op.create_index("ix_overtime_requests_is_deleted", "overtime_requests", ["is_deleted"], unique=False)


def downgrade():
    if _has_table("overtime_requests"):
        op.drop_index("ix_overtime_requests_is_deleted", table_name="overtime_requests")
        op.drop_index("ix_overtime_requests_overtime_date", table_name="overtime_requests")
        op.drop_index("ix_overtime_requests_employee_id", table_name="overtime_requests")
        op.drop_table("overtime_requests")

    if _has_column("dependents", "note"):
        with op.batch_alter_table("dependents", schema=None) as batch_op:
            batch_op.drop_column("note")

    if _has_column("complaints", "notification_id"):
        op.drop_constraint("fk_complaints_notification_id_notifications", "complaints", type_="foreignkey")
        op.drop_index("ix_complaints_notification_id", table_name="complaints")
    if _has_column("complaints", "user_id"):
        op.drop_constraint("fk_complaints_user_id_users", "complaints", type_="foreignkey")
        op.drop_index("ix_complaints_user_id", table_name="complaints")

    with op.batch_alter_table("complaints", schema=None) as batch_op:
        if _has_column("complaints", "closed_at"):
            batch_op.drop_column("closed_at")
        if _has_column("complaints", "closed_by_employee"):
            batch_op.drop_column("closed_by_employee")
        if _has_column("complaints", "admin_reply"):
            batch_op.drop_column("admin_reply")
        if _has_column("complaints", "notification_id"):
            batch_op.drop_column("notification_id")
        if _has_column("complaints", "user_id"):
            batch_op.drop_column("user_id")