from app.models.base import BaseModel
from app.extensions.db import db
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import relationship

# ENUM
gender_enum = ENUM(
    'male',
    'female',
    'other',
    name='gender_type',
    create_type=True
)

employment_enum = ENUM(
    'probation',
    'permanent',
    'intern',
    'contract',
    name='employment_type',
    create_type=True
)

working_status_enum = ENUM(
    'active',
    'probation',
    'on_leave',
    'pending_resignation',
    'resigned',
    'inactive',
    'terminated',
    'retired',
    name='working_status',
    create_type=True
)


class Employee(BaseModel):
    """
    Model Nhân viên - Trung tâm của hệ thống HRM.
    """

    __tablename__ = 'employees'

    # =========================
    # ACCOUNT
    # =========================
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        unique=True,
        nullable=True
    )

    # =========================
    # PERSONAL INFO
    # =========================
    full_name = db.Column(db.String(100), nullable=False)

    avatar = db.Column(db.String(255), nullable=True)

    dob = db.Column(db.Date, nullable=False)

    gender = db.Column(
        gender_enum,
        nullable=False
    )

    address = db.Column(db.Text)

    province_id = db.Column(db.String(20), nullable=True)
    district_id = db.Column(db.String(20), nullable=True)
    ward_id = db.Column(db.String(20), nullable=True)

    address_detail = db.Column(
        db.String(255),
        nullable=True
    )

    phone = db.Column(
        db.String(20),
        unique=True
    )

    # =========================
    # ORGANIZATION
    # =========================
    department_id = db.Column(
        db.Integer,
        db.ForeignKey('departments.id'),
        nullable=True
    )

    position_id = db.Column(
        db.Integer,
        db.ForeignKey('positions.id'),
        nullable=True
    )

    manager_id = db.Column(
        db.Integer,
        db.ForeignKey('employees.id'),
        nullable=True
    )

    # =========================
    # WORK STATUS
    # =========================
    hire_date = db.Column(
        db.Date,
        nullable=True
    )

    employment_type = db.Column(
        employment_enum,
        default='probation',
        server_default='probation'
    )

    working_status = db.Column(
        working_status_enum,
        default='active',
        server_default='active'
    )

    is_attendance_required = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default='true'
    )

    # =========================
    # RELATIONSHIPS
    # =========================

    # User
    user = relationship(
        'User',
        back_populates='employee_profile'
    )

    # Department
    department = relationship(
        'Department',
        backref='employees'
    )

    # Position
    position = relationship(
        'Position',
        backref='employees'
    )

    # Manager / Subordinates
    subordinates = relationship(
        'Employee',
        backref=db.backref(
            'manager',
            remote_side='Employee.id'
        )
    )
    complaints = relationship(
        'Complaint',
        foreign_keys='Complaint.employee_id',
        back_populates='employee',
        lazy='dynamic'
    )
    attendance_records = relationship(
        'Attendance',
        backref='employee',
        lazy='dynamic'
    )

    # Salary
    salary_records = relationship(
        'Salary',
        back_populates='employee',
        lazy='dynamic'
    )

    # Contracts
    contracts = relationship(
        'Contract',
        back_populates='employee',
        lazy='dynamic'
    )

    # Leave Requests
    leave_requests = relationship(
        'LeaveRequest',
        foreign_keys='LeaveRequest.employee_id',
        back_populates='employee',
        lazy='dynamic'
    )

    # Overtime Requests
    overtime_requests = relationship(
        'OvertimeRequest',
        back_populates='employee',
        lazy='dynamic'
    )

    history_logs = relationship(
        'HistoryLog',
        back_populates='employee',
        lazy='dynamic'
    )

    dependents = relationship(
        'Dependent',
        back_populates='employee',
        lazy='dynamic'
    )
    def __repr__(self):
        return f"<Employee {self.full_name} - {self.phone}>"

    @property
    def age(self):
        from datetime import date

        if self.dob:
            today = date.today()

            return (
                today.year
                - self.dob.year
                - (
                    (today.month, today.day)
                    < (self.dob.month, self.dob.day)
                )
            )

        return None