"""add overtime columns to attendance

Revision ID: 4f2b6f9f8a1a
Revises: 0e8242241019
Create Date: 2026-04-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f2b6f9f8a1a'
down_revision = '0e8242241019'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('attendance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('regular_hours', sa.Numeric(precision=4, scale=2), nullable=True))
        batch_op.add_column(sa.Column('overtime_hours', sa.Numeric(precision=4, scale=2), nullable=True))
        batch_op.add_column(sa.Column('attendance_type', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('attendance', schema=None) as batch_op:
        batch_op.drop_column('attendance_type')
        batch_op.drop_column('overtime_hours')
        batch_op.drop_column('regular_hours')