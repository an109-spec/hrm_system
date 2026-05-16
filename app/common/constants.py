from datetime import time, date
from decimal import Decimal
import importlib
from app.models import (
    Holiday,
)
from app.extensions.db import db
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

class AttendanceConstants:
    # 1. Danh sách trạng thái (Giữ nguyên của Duy An)
    VALID_STATUSES = {
        "not_started",
        "working_regular",
        "regular_done",
        "regular_done_pending_ot_decision",
        "pre_ot_rest",
        "working_overtime",
        "regular_checkout_required",
        "ot_checkin_required",
        "completed",
        "leave",
        "absent",
        "holiday_off",
        "weekend_off",
    }

    # 2. Quy tắc đi muộn (Move từ ngoài vào trong class)
    LATE_RULES = [
        {"min": 60, "penalty": 0, "label": "Nửa ngày công", "type": "half_day"},
        {"min": 31, "penalty": 100000, "label": "Phạt 100.000đ", "type": "money"},
        {"min": 15, "penalty": 50000, "label": "Phạt 50.000đ", "type": "money"},
        {"min": 1,  "penalty": 20000, "label": "Phạt 20.000đ", "type": "money"},
    ]

    @staticmethod
    def normalize(value: str | None) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def is_valid(value: str) -> bool:
        return AttendanceConstants.normalize(value) in AttendanceConstants.VALID_STATUSES

    @staticmethod
    def get_late_penalty(late_minutes: int) -> dict:
        """Tính toán tiền phạt và trạng thái nghỉ dựa trên số phút đi muộn"""
        if late_minutes <= 0:
            return {"penalty_amount": 0, "message": "", "is_half_day": False}
            
        for rule in AttendanceConstants.LATE_RULES:
            if late_minutes >= rule["min"]:
                return {
                    "penalty_amount": rule["penalty"],
                    "message": f" • {rule['label']}",
                    "is_half_day": (rule["type"] == "half_day")
                }
        return {"penalty_amount": 0, "message": "", "is_half_day": False}
    
class WorkConfig:
    CHECKIN_START = time(6, 0, 0)            # bắt đầu được ghi nhận công
    WORKDAY_START = time(8, 0, 0)            # giờ vào làm chính thức
    LATE_THRESHOLD = time(9, 0, 0)           # sau giờ này: đi trễ nặng / half-day

    LUNCH_START = time(12, 0, 0)
    LUNCH_END = time(13, 0, 0)

    WORKDAY_END = time(17, 0, 0)             # tan ca

    OT_START = time(18, 0, 0)                # mở OT / bắt đầu OT window
    OT_END = time(22, 0, 0)                  # kết thúc OT
    STANDARD_WORKING_DAYS = 22         # Số ngày công tiêu chuẩn trong tháng
    LATE_THRESHOLD_MINS = 0            # Số phút đi muộn cho phép (nếu có)

LEAVE_TYPE_CONFIGS = {
    "ANNUAL": {"name": "Nghỉ phép năm", "is_paid": True, "default_days": 12},
    "SICK": {"name": "Nghỉ ốm", "is_paid": True, "default_days": 5},
    "UNPAID": {"name": "Nghỉ không lương", "is_paid": False, "default_days": 0},
    "HOLIDAY": {"name": "Nghỉ lễ", "is_paid": True, "default_days": 0},
    "PERSONAL": {"name": "Nghỉ việc riêng", "is_paid": True, "default_days": 3},
    "MATERNITY": {"name": "Nghỉ thai sản", "is_paid": True, "default_days": 180},
}

VN_FIXED_PUBLIC_HOLIDAYS = {
    "01-01": "Tết Dương lịch",
    "04-30": "Ngày Giải phóng miền Nam",
    "05-01": "Quốc tế Lao động",
    "09-02": "Quốc khánh",
}

VN_LUNAR_PUBLIC_HOLIDAYS = (
    (1, 1, "Tết Nguyên đán (Mùng 1)"),
    (1, 2, "Tết Nguyên đán (Mùng 2)"),
    (1, 3, "Tết Nguyên đán (Mùng 3)"),
    (1, 4, "Tết Nguyên Đán"),
    (1, 5, "Tết Nguyên Đán"),
    (3, 10, "Giỗ Tổ Hùng Vương"),
)
# Cấu hình hiển thị Badge cho các loại đơn từ (Nghỉ phép, Tăng ca, Khiếu nại)
STATUS_BADGE_CONFIG = {
    "pending": {
        "icon": "bi-hourglass-split", 
        "label": "Chờ Manager duyệt", 
        "class": "bg-warning text-dark"
    },
    "pending_hr": {
        "icon": "bi-file-earmark-medical", 
        "label": "Chờ HR duyệt", 
        "class": "bg-info text-dark"
    },
    "approved": {
        "icon": "bi-check-circle-fill", 
        "label": "Đã duyệt", 
        "class": "bg-success"
    },
    "rejected": {
        "icon": "bi-x-circle-fill", 
        "label": "Từ chối", 
        "class": "bg-danger"
    },
    "supplement_requested": {
        "icon": "bi-paperclip", 
        "label": "Yêu cầu bổ sung", 
        "class": "bg-secondary"
    },
    "cancelled": {
        "icon": "bi-slash-circle", 
        "label": "Đã hủy", 
        "class": "bg-dark"
    },
    "complaint": {
        "icon": "bi-megaphone", 
        "label": "Khiếu nại", 
        "class": "bg-primary"
    }
}

def _resolve_lunar_date_class():
    spec = importlib.util.find_spec("lunardate")
    if spec is None:
        return None
    module = importlib.import_module("lunardate")
    return getattr(module, "LunarDate", None)

LUNAR_DATE_CLASS = _resolve_lunar_date_class()

def _build_lunar_public_holidays_for_year(year: int) -> dict[str, str]:
    if LUNAR_DATE_CLASS is None:
        return {}
    lookup: dict[str, str] = {}
    for lunar_month, lunar_day, holiday_name in VN_LUNAR_PUBLIC_HOLIDAYS:
        try:
            lunar_date_obj = LUNAR_DATE_CLASS(year, lunar_month, lunar_day)
            solar_date = lunar_date_obj.toSolarDate()
            lookup[solar_date.strftime("%m-%d")] = holiday_name
        except Exception:
            continue
    return lookup

class OvertimeConfig:
    MULTIPLIERS = {
        "holiday": Decimal("3.00"),
        "weekend": Decimal("2.00"),
        "after_shift": Decimal("1.50"), 
        "normal": Decimal("1.00")
    }
    OFFICIAL_PAY_START_TIME = time(19, 0, 0)
    @staticmethod
    def apply_multiplier(hours: Decimal, type_key: str) -> Decimal:
        multiplier = OvertimeConfig.MULTIPLIERS.get(type_key, Decimal("1.0"))
        return (hours * multiplier).quantize(Decimal("0.01"))

    @staticmethod
    def _get_holiday_for_date(target_date: date) -> Holiday | dict | None:
        exact_holiday = Holiday.query.filter_by(date=target_date).first()
        if exact_holiday:
            return exact_holiday

        recurring_holiday = (
            Holiday.query.filter(
                Holiday.is_recurring.is_(True),
                db.extract("month", Holiday.date) == target_date.month,
                db.extract("day", Holiday.date) == target_date.day,
            )
            .order_by(Holiday.id.asc())
            .first()
        )
        if recurring_holiday:
            return recurring_holiday

        fixed_name = VN_FIXED_PUBLIC_HOLIDAYS.get(target_date.strftime("%m-%d"))
        if fixed_name:
            return {"name": fixed_name, "is_paid": True}

        lunar_lookup = _build_lunar_public_holidays_for_year(target_date.year)
        lunar_name = lunar_lookup.get(target_date.strftime("%m-%d"))
        if lunar_name:
            return {"name": lunar_name, "is_paid": True}
        return None
    
    _LUNAR_HOLIDAY_CACHE = {} # Cache để lưu ngày lễ âm lịch theo năm

    @classmethod
    def get_lunar_holidays(cls, year: int):
        if year not in cls._LUNAR_HOLIDAY_CACHE:
            cls._LUNAR_HOLIDAY_CACHE[year] = _build_lunar_public_holidays_for_year(year)
        return cls._LUNAR_HOLIDAY_CACHE[year]    