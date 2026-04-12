from app.models.base import BaseModel
from app.extensions.db import db
from sqlalchemy.orm import relationship

class AllowanceType(db.Model):
    """
    Bảng danh mục các loại phụ cấp trong công ty.
    Ví dụ: Phụ cấp ăn trưa, điện thoại, gửi xe.
    """
    __tablename__ = 'allowance_types'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    
    # Số tiền mặc định cho loại phụ cấp này
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Đánh dấu có tính thuế TNCN hay không
    is_taxable = db.Column(db.Boolean, default=True, server_default='true')

    # Relationship tới danh sách nhân viên đang hưởng loại này
    employee_links = relationship('EmployeeAllowance', backref='allowance_type', lazy='dynamic')

    def __repr__(self):
        return f"<AllowanceType {self.name} - {self.amount}>"

class EmployeeAllowance(BaseModel):
    """
    Bảng liên kết Nhân viên và Phụ cấp.
    Xác định nhân viên cụ thể được hưởng phụ cấp gì và bao nhiêu.
    """
    __tablename__ = 'employee_allowances'

    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    allowance_id = db.Column(db.Integer, db.ForeignKey('allowance_types.id'), nullable=False)
    
    # Số tiền thực tế (Nếu không nhập sẽ lấy từ AllowanceType.amount)
    amount = db.Column(db.Numeric(15, 2), nullable=True)
    
    # Trạng thái: Còn áp dụng cho nhân viên này hay không
    status = db.Column(db.Boolean, default=True, server_default='true')

    # Relationships
    employee = relationship('Employee', backref=db.backref('allowances', lazy='dynamic'))

    def __repr__(self):
        return f"<EmployeeAllowance Emp:{self.employee_id} Type:{self.allowance_id}>"

    @property
    def final_amount(self):
        """Hàm helper lấy số tiền thực tế hoặc số tiền mặc định"""
        if self.amount is not None:
            return self.amount
        return self.allowance_type.amount