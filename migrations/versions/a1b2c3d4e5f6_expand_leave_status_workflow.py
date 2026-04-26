"""expand leave status workflow

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-04-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('leave_requests'):
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

    old_enum = sa.Enum('pending', 'approved', 'rejected', name='leave_status_enum')
    op.execute(
        sa.text(
            "UPDATE leave_requests SET status='pending' WHERE status IN ('pending_hr','pending_admin','supplement_requested','cancelled','complaint')"
        )
    )
    with op.batch_alter_table('leave_requests', schema=None) as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=sa.Enum(name='leave_status_enum'),
            type_=old_enum,
            existing_nullable=True,
            existing_server_default='pending',
            server_default='pending',
        )