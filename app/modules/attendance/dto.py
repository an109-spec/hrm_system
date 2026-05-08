from dataclasses import dataclass
from datetime import date, time
from typing import Optional
from decimal import Decimal

@dataclass
class AttendanceDTO:
    employee_id: int
    date: date
    check_in: Optional[time] = None
    check_out: Optional[time] = None


@dataclass
class AttendanceResponseDTO:
    id: int
    date: str
    check_in: str
    check_out: str
    working_hours: float
    status: str

@dataclass
class AttendanceStateDTO:
    state: str
    button_enabled: bool
    button_text: str
    can_scan: bool
    message: Optional[str] = None
    overtime_status: Optional[str] = None


@dataclass
class WorkUnitDTO:
    units: Decimal
    is_half_day: bool
    worked_hours: Decimal