from dataclasses import dataclass
from datetime import date


@dataclass
class LeaveRequestDTO:
    employee_id: int
    leave_type_id: int
    from_date: date
    to_date: date
    reason: str
    approved_by: int | None = None