from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship
import json
class Salary(BaseModel):
    """
    Bảng Bảng lương tháng của nhân viên.
    Tổng hợp và LƯU TRỮ TĨNH dữ liệu từ Contracts, Attendance, Allowances, Dependents tại thời điểm chốt.
    """
    __tablename__ = 'salaries'

    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    # Thời gian chốt lương
    month = db.Column(db.Integer, nullable=False) # 1-12
    year = db.Column(db.Integer, nullable=False)
    
    # Các thành phần thu nhập gốc và ngày công
    basic_salary = db.Column(db.Numeric(15, 2), nullable=False) # Lương gốc từ hợp đồng
    standard_work_days = db.Column(db.Integer, default=22)      # Công chuẩn của tháng
    total_work_days = db.Column(db.Numeric(5, 2), default=0)    # Công thực tế (từ Attendance)
    
    # Chi tiết các khoản phụ cấp và thu nhập bổ sung (Lưu tĩnh từ EmployeeAllowance)
    total_allowance = db.Column(db.Numeric(15, 2), default=0)    # Tổng phụ cấp gộp
    lunch_allowance = db.Column(db.Numeric(15, 2), default=0)    # Phụ cấp ăn trưa
    responsibility_allowance = db.Column(db.Numeric(15, 2), default=0) # Phụ cấp trách nhiệm
    bonus = db.Column(db.Numeric(15, 2), default=0)              # Thưởng hiệu suất/lễ
    overtime_salary = db.Column(db.Numeric(15, 2), default=0)    # Tiền làm thêm giờ (OT)
    
    # Các khoản giảm trừ và thuế khấu trừ (Lưu tĩnh sau khi chạy logic tính)
    penalty = db.Column(db.Numeric(15, 2), default=0)            # Tiền phạt đi muộn/vi phạm
    insurance = db.Column(db.Numeric(15, 2), default=0)          # Tiền bảo hiểm khấu trừ (BHXH, BHYT, BHTN)
    tax = db.Column(db.Numeric(15, 2), default=0)                # Thuế thu nhập cá nhân (PIT) khấu trừ
    
    # Lịch sử giảm trừ gia cảnh (Lưu tĩnh từ bảng Dependent tại thời điểm chốt)
    number_of_dependents = db.Column(db.Integer, default=0)      # Số người phụ thuộc lúc chốt lương
    family_deduction = db.Column(db.Numeric(15, 2), default=0)    # Tổng tiền giảm trừ gia cảnh được áp dụng
    
    # Lương thực nhận cuối cùng (Net Salary)
    net_salary = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Trạng thái: pending, approved, paid
    status = db.Column(db.String(20), default='pending', server_default='pending')
    
    note = db.Column(db.Text)

    @property
    def note_data(self) -> dict:
        """
        Getter: Tự động chuyển string từ DB sang dict để dùng trong logic tính toán.
        Sử dụng: salary.note_data.get("key")
        """
        try:
            return json.loads(self.note) if self.note else {}
        except (TypeError, ValueError):
            return {}

    @note_data.setter
    def note_data(self, value: dict):
        """
        Setter: Tự động chuyển dict sang string khi gán vào note.
        Sử dụng: salary.note_data = {"new": "data"}
        """
        self.note = json.dumps(value, ensure_ascii=False)

    # Ràng buộc: Mỗi nhân viên chỉ có 1 bản ghi lương duy nhất cho mỗi tháng/năm
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'month', 'year', name='uq_employee_month_year_salary'),
    )

    # Relationship
    # Liên kết với nhân viên để lấy thông tin họ tên khi in phiếu lương
    employee = relationship('Employee', back_populates='salary_records')

    def __repr__(self):
        return f"<Salary Emp:{self.employee_id} - {self.month}/{self.year} - Net:{self.net_salary}>"

    def calculate_net_salary(self):
        """
        Hàm nâng cấp tính toán và cập nhật Thực lĩnh (Net Salary) dựa trên các thành phần tĩnh.
        Công thức chuẩn doanh nghiệp: 
        Net = (Lương cơ bản / Công chuẩn * Công thực tế) + Tổng phụ cấp + Thưởng + Tăng ca - Phạt - Bảo hiểm - Thuế
        """
        if self.standard_work_days > 0:
            # 1. Tính lương theo ngày công thực tế
            actual_basic = (self.basic_salary / self.standard_work_days) * self.total_work_days
            
            # 2. Tự động đồng bộ total_allowance nếu chưa được tính gộp từ trước
            if not self.total_allowance or self.total_allowance == 0:
                self.total_allowance = (self.lunch_allowance or 0) + (self.responsibility_allowance or 0)

            # 3. Tính tổng thu nhập Gross
            gross_salary = (
                actual_basic 
                + self.total_allowance 
                + (self.bonus or 0) 
                + (self.overtime_salary or 0)
            )
            
            # 4. Trừ đi các khoản giảm trừ bắt buộc để ra Net lương thực nhận
            self.net_salary = gross_salary - (self.penalty or 0) - (self.insurance or 0) - (self.tax or 0)
            return self.net_salary
            
        return 0