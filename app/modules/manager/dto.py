from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ApproveLeaveDTO:
    leave_id: int
    note: Optional[str] = None


@dataclass
class RejectLeaveDTO:
    leave_id: int
    note: Optional[str] = None


@dataclass
class ReminderDTO:
    employee_ids: List[int]
    message: Optional[str] = None
