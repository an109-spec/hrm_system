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
    PROBATION = "probation"#thử việc
    PERMANENT = "permanent"# chính thức
    INTERN = "intern" #thực tập sinh
    CONTRACT = "contract"

class LeaveStatus:
    PENDING = "pending" # đang chờ duyệt
    APPROVED = "approved" # đã duyệt
    REJECTED = "rejected" # bị từ chối

class AttendanceStatus:
    PRESENT = "PRESENT" #Có mặt / Đi làm
    LATE = "LATE"#Đi muộn
    ABSENT = "ABSENT"#Vắng mặt
    LEAVE = "LEAVE"#Nghỉ phép

class SalaryStatus:
    PENDING = "pending"
    APPROVED = "approved"#Đã duyệt
    PAID = "paid"#Đã thanh toán lương

# Các cấu hình hệ thống mặc định (System Settings)
DEFAULT_SETTINGS = {
    "STANDARD_WORKING_DAYS": 22,
    "CHECK_IN_TIME": "08:00:00",
    "CHECK_OUT_TIME": "17:00:00",
    "LATE_THRESHOLD_MINS": 0
}
class AttendanceConstants:
    VALID_STATUSES = {
        "not_started",
        "working_regular",
        "regular_done",
        "working_overtime",
        "completed",
        "leave",
        "absent",
        "holiday_off",
        "weekend_off",
    }

    @staticmethod
    def normalize(value: str | None) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def is_valid(value: str) -> bool:
        return value in AttendanceConstants.VALID_STATUSES