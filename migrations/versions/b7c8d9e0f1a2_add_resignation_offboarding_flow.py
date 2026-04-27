"""add resignation offboarding flow

Revision ID: b7c8d9e0f1a2
Revises: 4f2b6f9f8a1a
Create Date: 2026-04-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c8d9e0f1a2'
down_revision = '4f2b6f9f8a1a'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE working_status RENAME TO working_status_old")
    new_enum = sa.Enum(
        'active',
        'probation',
        'on_leave',
        'pending_resignation',
        'resigned',
        'inactive',
        'terminated',
        'retired',
        name='working_status'
    )
    new_enum.create(op.get_bind(), checkfirst=True)
    op.execute("""
        ALTER TABLE employees
        ALTER COLUMN working_status DROP DEFAULT,
        ALTER COLUMN working_status TYPE working_status
        USING (
            CASE
                WHEN working_status::text = 'working' THEN 'active'
                ELSE working_status::text
            END
        )::working_status,
        ALTER COLUMN working_status SET DEFAULT 'active'
    """)
    op.execute("DROP TYPE working_status_old")

    op.create_table(
        'resignation_requests',
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('manager_id', sa.Integer(), nullable=True),
        sa.Column('handover_employee_id', sa.Integer(), nullable=True),
        sa.Column('request_type', sa.String(length=30), nullable=False, server_default='employee'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='pending_manager'),
        sa.Column('expected_last_day', sa.Date(), nullable=False),
        sa.Column('reason_category', sa.String(length=30), nullable=False),
        sa.Column('reason_text', sa.Text(), nullable=True),
        sa.Column('extra_note', sa.Text(), nullable=True),
        sa.Column('attachment_url', sa.String(length=255), nullable=True),
        sa.Column('manager_note', sa.Text(), nullable=True),
        sa.Column('hr_note', sa.Text(), nullable=True),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('final_payroll_note', sa.Text(), nullable=True),
        sa.Column('final_attendance_note', sa.Text(), nullable=True),
        sa.Column('leave_balance_note', sa.Text(), nullable=True),
        sa.Column('insurance_note', sa.Text(), nullable=True),
        sa.Column('asset_handover_note', sa.Text(), nullable=True),
        sa.Column('reviewed_by_manager_id', sa.Integer(), nullable=True),
        sa.Column('processed_by_hr_id', sa.Integer(), nullable=True),
        sa.Column('approved_by_admin_id', sa.Integer(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['approved_by_admin_id'], ['users.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['handover_employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['manager_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['processed_by_hr_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reviewed_by_manager_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resignation_requests_employee_id'), 'resignation_requests', ['employee_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_resignation_requests_employee_id'), table_name='resignation_requests')
    op.drop_table('resignation_requests')

    op.execute("ALTER TYPE working_status RENAME TO working_status_new")
    old_enum = sa.Enum('working', 'on_leave', 'resigned', name='working_status')
    old_enum.create(op.get_bind(), checkfirst=True)
    op.execute("""
        ALTER TABLE employees
        ALTER COLUMN working_status DROP DEFAULT,
        ALTER COLUMN working_status TYPE working_status
        USING (
            CASE
                WHEN working_status::text = 'active' THEN 'working'
                WHEN working_status::text IN ('probation','pending_resignation','inactive','terminated','retired') THEN 'resigned'
                ELSE working_status::text
            END
        )::working_status,
        ALTER COLUMN working_status SET DEFAULT 'working'
    """)
    op.execute("DROP TYPE working_status_new")