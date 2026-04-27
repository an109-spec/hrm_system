"""fix postgres leave_status_enum values

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-04-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6f7a8b9c0d1'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


NEW_VALUES = (
    'pending_hr',
    'pending_admin',
    'supplement_requested',
    'cancelled',
    'complaint',
)


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == 'postgresql'


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('leave_requests'):
        return

    if _is_postgresql():
        for value in NEW_VALUES:
            op.execute(sa.text(f"ALTER TYPE leave_status_enum ADD VALUE IF NOT EXISTS '{value}'"))
        return

    leave_status_enum = sa.Enum(
        'pending',
        'pending_hr',
        'pending_admin',
        'approved',
        'rejected',
        'supplement_requested',
        'cancelled',
        'complaint',
        name='leave_status_enum',
    )
    with op.batch_alter_table('leave_requests', schema=None) as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=sa.Enum(name='leave_status_enum'),
            type_=leave_status_enum,
            existing_nullable=True,
            existing_server_default='pending',
            server_default='pending',
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('leave_requests'):
        return

    op.execute(
        sa.text(
            "UPDATE leave_requests "
            "SET status='pending' "
            "WHERE status IN ('pending_hr','pending_admin','supplement_requested','cancelled','complaint')"
        )
    )

    old_enum = sa.Enum('pending', 'approved', 'rejected', name='leave_status_enum')
    with op.batch_alter_table('leave_requests', schema=None) as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=sa.Enum(name='leave_status_enum'),
            type_=old_enum,
            existing_nullable=True,
            existing_server_default='pending',
            server_default='pending',
        )