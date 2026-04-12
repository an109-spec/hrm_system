from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship

class Contract(BaseModel):
    """
    Model quản lý Hợp đồng lao động của nhân viên.
    Lưu trữ thông tin lương cơ bản và thời hạn hợp đồng.
    """
    __tablename__ = 'contracts'

    # Liên kết với nhân viên
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    # Mã hợp đồng (Ví dụ: HD2026/001) - Đánh index để tìm kiếm nhanh
    contract_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Lương cơ bản (Dùng Numeric để tính công chính xác)
    basic_salary = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Thời hạn hợp đồng
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True) # Trống nếu là hợp đồng vô thời hạn
    
    # Trạng thái: active, expired (hết hạn), terminated (chấm dứt trước hạn)
    status = db.Column(db.String(20), default='active', server_default='active')

    # Relationship
    # Liên kết ngược lại với Model Employee
    employee = relationship('Employee', back_populates='contracts')

    def __repr__(self):
        return f"<Contract {self.contract_code} - Emp:{self.employee_id}>"

    @property
    def is_expired(self):
        """Hàm helper kiểm tra hợp đồng đã quá hạn chưa"""
        from datetime import date
        if self.end_date and self.end_date < date.today():
            return True
        return False