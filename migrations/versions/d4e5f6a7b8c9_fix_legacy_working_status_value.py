"""Fix legacy employees.working_status value 'working' -> 'active'.

Revision ID: d4e5f6a7b8c9
Revises: 779ee223a0da
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = '779ee223a0da'
branch_labels = None
depends_on = None

def _get_enum_labels(bind, enum_name: str) -> list[str]:
    rows = bind.execute(
        sa.text(
            """
            SELECT e.enumlabel
            FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            WHERE t.typname = :enum_name
            ORDER BY e.enumsortorder
            """
        ),
        {"enum_name": enum_name},
    ).fetchall()
    return [r[0] for r in rows]

def upgrade():
    bind = op.get_bind()
    labels = _get_enum_labels(bind, 'working_status')

    # If enum is missing or already migrated, keep data-fix idempotent.
    if not labels:
        return

    desired_labels = (
        'active',
        'probation',
        'on_leave',
        'pending_resignation',
        'resigned',
        'inactive',
        'terminated',
        'retired',
    )

    # Some environments were stamped/merged without running the enum migration,
    # so 'active' does not exist yet and direct UPDATE would fail.
    if 'active' not in labels:
        op.execute("ALTER TYPE working_status RENAME TO working_status_old")

        new_enum = sa.Enum(*desired_labels, name='working_status')
        new_enum.create(bind, checkfirst=True)

        op.execute(
            """
            ALTER TABLE employees
            ALTER COLUMN working_status DROP DEFAULT,
            ALTER COLUMN working_status TYPE working_status
            USING (
                CASE
                    WHEN working_status::text = 'working' THEN 'active'
                    WHEN working_status::text IN ('on_leave', 'resigned') THEN working_status::text
                    ELSE 'resigned'
                END
            )::working_status,
            ALTER COLUMN working_status SET DEFAULT 'active'
            """
        )
        op.execute("DROP TYPE working_status_old")
        return

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