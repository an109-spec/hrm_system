from app.models.base import BaseModel
from app.extensions.db import db
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import relationship

# Định nghĩa các ENUM Type để SQLAlchemy tự động tạo Type trong Postgres
gender_enum = ENUM('male', 'female', 'other', name='gender_type', create_type=True)
employment_enum = ENUM('probation', 'permanent', 'intern', 'contract', name='employment_type', create_type=True)
working_status_enum = ENUM('working', 'on_leave', 'resigned', name='working_status', create_type=True)

class Employee(BaseModel):
    """
    Model Nhân viên - Trung tâm của hệ thống HRM.
    Kế thừa từ BaseModel (id, created_at, updated_at, is_deleted).
    """
    __tablename__ = 'employees'

    # Liên kết 1-1 với tài khoản hệ thống
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=True)
    
    # Thông tin cá nhân
    full_name = db.Column(db.String(100), nullable=False)
    avatar = db.Column(db.String(255), nullable=True)
    dob = db.Column(db.Date, nullable=False)
    gender = db.Column(gender_enum, nullable=False)
    address = db.Column(db.Text) # Giữ lại làm backup hoặc địa chỉ cũ
    
    # --- THÊM MỚI ---
    province_id = db.Column(db.String(20), nullable=True)
    district_id = db.Column(db.String(20), nullable=True)
    ward_id = db.Column(db.String(20), nullable=True)
    address_detail = db.Column(db.String(255), nullable=True)
    # ----------------
    
    phone = db.Column(db.String(20), unique=True)
    
    # Tổ chức và Chức danh
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'), nullable=True)
    
    # Quản lý trực tiếp (Self-referencing Foreign Key)
    manager_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    
    # Trạng thái công việc
    hire_date = db.Column(db.Date, nullable=True)
    employment_type = db.Column(employment_enum, default='probation', server_default='probation')
    working_status = db.Column(working_status_enum, default='working', server_default='working')

    # Relationships
    # Mối quan hệ với người quản lý và nhân viên cấp dưới
    user = relationship('User', back_populates='employee_profile')
    subordinates = relationship('Employee', backref=db.backref('manager', remote_side='Employee.id'))
    
    # Các liên kết tới các bảng nghiệp vụ khác (sẽ định nghĩa sau)
    attendance_records = relationship('Attendance', backref='employee', lazy='dynamic')
    salary_records = relationship(
    'Salary',
    back_populates='employee',
    lazy='dynamic'
)
    contracts = relationship(
    'Contract',
    back_populates='employee',
    lazy='dynamic'
)
    leave_requests = relationship(
    'LeaveRequest',
    foreign_keys='LeaveRequest.employee_id',
    back_populates='employee',
    lazy='dynamic'
)

    def __repr__(self):
        return f"<Employee {self.full_name} - {self.phone}>"

    @property
    def age(self):
        """Tính tuổi nhân viên dựa trên ngày sinh"""
        from datetime import date
        if self.dob:
            today = date.today()
            return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
        return None