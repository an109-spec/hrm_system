from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ApproveLeaveDTO:
    leave_id: int
    note: Optional[str] = None  # Ghi chú khi phê duyệt (Không bắt buộc)

@dataclass
class RejectLeaveDTO:
    leave_id: int
    note: str  # Bắt buộc phải nhập lý do khi từ chối đơn để minh bạch dữ liệu

@dataclass
class ReminderDTO:
    employee_ids: List[int] = field(default_factory=list)
    message: Optional[str] = None