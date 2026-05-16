from dataclasses import dataclass
from datetime import date
from typing import Optional
from app.utils import holiday
@dataclass
class LeaveRequestDTO:
    employee_id: int
    leave_type_id: int
    from_date: date
    to_date: date
    reason: str
    
    document_url: Optional[str] = None
    
    subtype: Optional[str] = None
    
    relation: Optional[str] = None
    
    approved_by: Optional[int] = None
    requested_days: int = 0
    def __post_init__(self):
        self.requested_days = holiday.calculate_actual_leave_days(self.from_date, self.to_date)