from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

@dataclass
class AttendanceDTO:
    employee_id: int
    date: date                           # Kiểu ngày thuần túy phục vụ truy vấn DB (YYYY-MM-DD)
    check_in: Optional[datetime] = None  # Luôn lưu Datetime có múi giờ (Aware Datetime)
    check_out: Optional[datetime] = None
    overtime_check_in: Optional[datetime] = None
    overtime_check_out: Optional[datetime] = None

    @classmethod
    def create_from_sim(cls, employee_id: int, sim_time: datetime):
        """
        Factory method giúp khởi tạo nhanh DTO từ hàm get_current_time() của file giả lập.
        Đảm bảo tách date và gán datetime có múi giờ chính xác.
        """
        aware_time = sim_time.astimezone(VN_TIMEZONE)
        return cls(
            employee_id=employee_id,
            date=aware_time.date(),
            check_in=aware_time
        )

@dataclass
class AttendanceResponseDTO:
    id: int
    employee_id: int
    date: str                        # Định dạng chuỗi "YYYY-MM-DD"
    attendance_type: str
    shift_status: str
    status: str
    
    check_in: Optional[str]
    check_out: Optional[str]
    overtime_check_in: Optional[str]
    overtime_check_out: Optional[str]
    
    regular_hours: Decimal
    overtime_hours: Decimal
    working_hours: Decimal
    is_half_day: bool
    is_weekend: bool
    is_holiday: bool
    overtime_status: Optional[str] = None

    @staticmethod
    def format_sim_time(dt: Optional[datetime]) -> Optional[str]:
        """Chuyển đổi datetime giả lập có múi giờ thành chuỗi hiển thị trên giao diện"""
        if not dt:
            return None
        return dt.astimezone(VN_TIMEZONE).strftime("%H:%M:%S")

@dataclass
class AttendanceStateDTO:
    state: str
    button_enabled: bool
    button_text: str
    can_scan: bool
    message: Optional[str] = None
    overtime_status: Optional[str] = None
    requires_confirmation: bool = False
    requires_overtime_decision: bool = False
    locked_state: bool = False

@dataclass
class WorkUnitDTO:
    units: Decimal
    is_half_day: bool
    worked_hours: Decimal
    late_minutes: int = 0
    early_leave_minutes: int = 0