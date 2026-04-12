from app.extensions.db import db

# Import Base trước
from app.models.base import BaseModel

# Import các bảng danh mục/độc lập
from app.models.role import Role
from app.models.system import SystemSetting
from app.models.leave import LeaveType
from app.models.allowance import AllowanceType
from app.models.attendance import AttendanceStatus

# Import các bảng có mối quan hệ phức tạp
from app.models.user import User
from app.models.position import Position
from app.models.department import Department
from app.models.employee import Employee

# Import các bảng nghiệp vụ phụ thuộc vào Employee
from app.models.attendance import Attendance
from app.models.leave import LeaveRequest
from app.models.leave_usage import EmployeeLeaveUsage
from app.models.contract import Contract
from app.models.allowance import EmployeeAllowance
from app.models.salary import Salary
from app.models.notification import Notification

# Danh sách Export để dễ dàng quản lý
__all__ = [
    'db',
    'BaseModel',
    'Role',
    'User',
    'Employee',
    'Department',
    'Position',
    'AttendanceStatus',
    'Attendance',
    'LeaveType',
    'LeaveRequest',
    'EmployeeLeaveUsage',
    'Contract',
    'AllowanceType',
    'EmployeeAllowance',
    'Salary',
    'Notification',
    'SystemSetting'
]