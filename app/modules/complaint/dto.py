from dataclasses import dataclass
from typing import Optional, List

@dataclass
class CreateComplaintDTO:
    employee_id: int
    type: str
    title: str
    description: str
    salary_id: Optional[int] = None
    leave_request_id: Optional[int] = None
    priority: str = "normal"

@dataclass
class UpdateComplaintStatusDTO:
    complaint_id: int
    status: str
    handled_by: int

@dataclass
class SendMessageDTO:
    complaint_id: int
    sender_id: int
    message: str