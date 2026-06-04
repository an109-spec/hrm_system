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
    
    # Các trường tùy chọn
    document_url: Optional[str] = None
    subtype: Optional[str] = None
    relation: Optional[str] = None
    
    # Giá trị khởi tạo
    requested_days: int = 0
    
    def __post_init__(self):
        # 1. Kiểm tra logic ngày tháng
        if self.to_date < self.from_date:
            raise ValueError("Ngày kết thúc không được nhỏ hơn ngày bắt đầu.")
        
        # 2. Kiểm tra ngày trong tương lai (tùy nghiệp vụ)
        # if self.from_date < date.today():
        #     raise ValueError("Ngày bắt đầu không được là ngày quá khứ.")

        # 3. Tính số ngày thực tế
        self.requested_days = holiday.calculate_actual_leave_days(self.from_date, self.to_date)