"""add leave extended fields and holidays

Revision ID: 9b2d7f7b4c10
Revises: 4f2b6f9f8a1a
Create Date: 2026-04-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b2d7f7b4c10'
down_revision = '4f2b6f9f8a1a'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    leave_request_columns = {col["name"] for col in inspector.get_columns("leave_requests")}
    with op.batch_alter_table('leave_requests', schema=None) as batch_op:
        if 'document_url' not in leave_request_columns:
            batch_op.add_column(sa.Column('document_url', sa.String(length=500), nullable=True))
        if 'subtype' not in leave_request_columns:
            batch_op.add_column(sa.Column('subtype', sa.String(length=50), nullable=True))
        if 'relation' not in leave_request_columns:
            batch_op.add_column(sa.Column('relation', sa.String(length=50), nullable=True))

    if not inspector.has_table("holidays"):
        op.create_table(
            'holidays',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('is_paid', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.PrimaryKeyConstraint('id')
        )

    holiday_indexes = {idx["name"] for idx in inspector.get_indexes("holidays")}
    index_name = op.f('ix_holidays_date')
    if index_name not in holiday_indexes:
        op.create_index(index_name, 'holidays', ['date'], unique=True)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("holidays"):
        holiday_indexes = {idx["name"] for idx in inspector.get_indexes("holidays")}
        index_name = op.f('ix_holidays_date')
        if index_name in holiday_indexes:
            op.drop_index(index_name, table_name='holidays')
        op.drop_table('holidays')

    leave_request_columns = {col["name"] for col in inspector.get_columns("leave_requests")}
    with op.batch_alter_table('leave_requests', schema=None) as batch_op:
        if 'relation' in leave_request_columns:
            batch_op.drop_column('relation')
        if 'subtype' in leave_request_columns:
            batch_op.drop_column('subtype')
        if 'document_url' in leave_request_columns:
            batch_op.drop_column('document_url')
