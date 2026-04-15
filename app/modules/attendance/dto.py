from dataclasses import dataclass
from datetime import date, time
from typing import Optional


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