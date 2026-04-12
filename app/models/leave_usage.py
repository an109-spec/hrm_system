from app.models.base import db
from sqlalchemy.orm import relationship

class EmployeeLeaveUsage(db.Model):
    """
    Bảng quản lý hạn mức ngày phép của nhân viên theo từng năm.
    Dùng để kiểm soát việc nhân viên còn phép để xin nghỉ hay không.
    """
    __tablename__ = 'employee_leave_usage'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    
    total_days = db.Column(db.Integer, default=12) # Tổng phép được cấp
    used_days = db.Column(db.Integer, default=0) # Phép đã dùng
    remaining_days = db.Column(db.Integer, default=12) # Phép còn lại

    # Ràng buộc: Mỗi nhân viên chỉ có 1 dòng theo dõi phép cho mỗi năm
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'year', name='uq_employee_year_leave'),
    )

    # Relationship
    employee = relationship('Employee', backref=db.backref('leave_usage', lazy='dynamic'))

    def __repr__(self):
        return f"<LeaveUsage Emp:{self.employee_id} Year:{self.year} Remaining:{self.remaining_days}>"

    def update_balance(self):
        """Hàm tự động tính toán lại số ngày còn lại"""
        self.remaining_days = self.total_days - self.used_days