"""add attendance required flag to employee

Revision ID: c3d9f7a1b2e4
Revises: 9b2d7f7b4c10
Create Date: 2026-04-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d9f7a1b2e4'
down_revision = '9b2d7f7b4c10'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'is_attendance_required',
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )

    op.execute(
        """
        UPDATE employees AS e
        SET is_attendance_required = false
        FROM users AS u
        JOIN roles AS r ON r.id = u.role_id
        WHERE e.user_id = u.id
          AND lower(r.name) IN ('admin', 'hr')
        """
    )


def downgrade():
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.drop_column('is_attendance_required')