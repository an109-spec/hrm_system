from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship

class Salary(BaseModel):
    """
    Bảng Bảng lương tháng của nhân viên.
    Tổng hợp dữ liệu từ Contracts, Attendance và Allowances.
    """
    __tablename__ = 'salaries'

    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    # Thời gian chốt lương
    month = db.Column(db.Integer, nullable=False) # 1-12
    year = db.Column(db.Integer, nullable=False)
    
    # Các thành phần lương (Sử dụng Numeric để tính toán chính xác)
    basic_salary = db.Column(db.Numeric(15, 2), nullable=False) # Lương gốc từ hợp đồng
    standard_work_days = db.Column(db.Integer, default=22) # Công chuẩn của tháng
    total_work_days = db.Column(db.Numeric(5, 2), default=0) # Công thực tế (từ Attendance)
    
    total_allowance = db.Column(db.Numeric(15, 2), default=0) # Tổng phụ cấp
    bonus = db.Column(db.Numeric(15, 2), default=0) # Thưởng
    penalty = db.Column(db.Numeric(15, 2), default=0) # Phạt
    
    # Lương thực nhận (Net Salary)
    net_salary = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Trạng thái: pending, approved, paid
    status = db.Column(db.String(20), default='pending', server_default='pending')
    
    note = db.Column(db.Text)

    # Ràng buộc: Mỗi nhân viên chỉ có 1 bản ghi lương duy nhất cho mỗi tháng/năm
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'month', 'year', name='uq_employee_month_year_salary'),
    )

    # Relationship
    # Liên kết với nhân viên để lấy thông tin họ tên khi in phiếu lương
    employee = relationship('Employee', backref=db.backref('salaries', lazy='dynamic'))

    def __repr__(self):
        return f"<Salary Emp:{self.employee_id} - {self.month}/{self.year} - Net:{self.net_salary}>"

    def calculate_net_salary(self):
        """
        Hàm helper gợi ý cho logic tính lương:
        Lương = (Lương cơ bản / Công chuẩn * Công thực tế) + Phụ cấp + Thưởng - Phạt
        """
        if self.standard_work_days > 0:
            actual_basic = (self.basic_salary / self.standard_work_days) * self.total_work_days
            self.net_salary = actual_basic + self.total_allowance + self.bonus - self.penalty
            return self.net_salary
        return 0