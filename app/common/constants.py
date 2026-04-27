# app/common/constants.py

class RoleName:
    ADMIN = "Admin"
    HR = "HR"
    MANAGER = "Manager"
    EMPLOYEE = "Employee"

class WorkingStatus:
    WORKING = "active"
    ON_LEAVE = "on_leave"
    RESIGNED = "resigned"

class EmploymentType:
    PROBATION = "probation"
    PERMANENT = "permanent"
    INTERN = "intern"
    CONTRACT = "contract"

class LeaveStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class AttendanceStatus:
    PRESENT = "PRESENT"
    LATE = "LATE"
    ABSENT = "ABSENT"
    LEAVE = "LEAVE"

class SalaryStatus:
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"

# Các cấu hình hệ thống mặc định (System Settings)
DEFAULT_SETTINGS = {
    "STANDARD_WORKING_DAYS": 22,
    "CHECK_IN_TIME": "08:00:00",
    "CHECK_OUT_TIME": "17:30:00",
    "LATE_THRESHOLD_MINS": 15
}