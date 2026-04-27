"""merge multiple heads

Revision ID: 779ee223a0da
Revises: a1b2c3d4e5f6, b7c8d9e0f1a2
Create Date: 2026-04-27 09:36:10.395774

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '779ee223a0da'
down_revision = ('a1b2c3d4e5f6', 'b7c8d9e0f1a2')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
