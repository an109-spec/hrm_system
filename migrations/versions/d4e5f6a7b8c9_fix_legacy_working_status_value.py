"""Fix legacy employees.working_status value 'working' -> 'active'.

Revision ID: d4e5f6a7b8c9
Revises: 779ee223a0da
Create Date: 2026-04-27
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = '779ee223a0da'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE employees
        SET working_status = 'active'
        WHERE CAST(working_status AS VARCHAR) = 'working'
        """
    )


def downgrade():
    # Irreversible data fix: keep current values unchanged.
    pass