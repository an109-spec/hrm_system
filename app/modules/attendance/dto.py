from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from typing import Optional


# =====================================================
# INPUT DTO
# =====================================================
@dataclass
class AttendanceDTO:

    employee_id: int

    date: date

    check_in: Optional[datetime] = None

    check_out: Optional[datetime] = None

    overtime_check_in: Optional[datetime] = None

    overtime_check_out: Optional[datetime] = None


# =====================================================
# API RESPONSE DTO
# =====================================================
@dataclass
class AttendanceResponseDTO:

    id: int

    employee_id: int

    date: str

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


# =====================================================
# STATE MACHINE DTO
# =====================================================
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


# =====================================================
# WORK UNIT DTO
# =====================================================
@dataclass
class WorkUnitDTO:

    units: Decimal

    is_half_day: bool

    worked_hours: Decimal

    late_minutes: int = 0

    early_leave_minutes: int = 0