from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship

class LeaveType(db.Model):
    """
    Bảng danh mục các loại nghỉ phép.
    Ví dụ: Nghỉ phép năm, Nghỉ ốm, Nghỉ chế độ, Nghỉ không lương.
    """
    __tablename__ = 'leave_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    is_paid = db.Column(db.Boolean, default=True) # Nghỉ có được hưởng lương không?

    # Quan hệ ngược lại với các đơn xin nghỉ
    requests = relationship('LeaveRequest', backref='leave_type', lazy='dynamic')

    def __repr__(self):
        return f"<LeaveType {self.name}>"

class LeaveRequest(BaseModel):
    """
    Bảng quản lý đơn xin nghỉ phép của nhân viên.
    Kế thừa BaseModel (id, created_at, updated_at, is_deleted).
    """
    __tablename__ = 'leave_requests'

    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'), nullable=False)
    
    # Khoảng thời gian nghỉ
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    
    reason = db.Column(db.Text)
    
    # Trạng thái đơn: Pending (Chờ), Approved (Duyệt), Rejected (Từ chối)
    status = db.Column(
        db.Enum('pending', 'approved', 'rejected', name='leave_status_enum'), 
        default='pending',
        server_default='pending'
    )
    
    # Người duyệt đơn (Thường là Manager hoặc HR)
    approved_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    # Relationships
    # Liên kết với thông tin nhân viên xin nghỉ
    employee = relationship('Employee', foreign_keys=[employee_id], backref='my_leave_requests')
    # Liên kết với thông tin người duyệt
    approver = relationship('Employee', foreign_keys=[approved_by], backref='approved_leaves')

    def __repr__(self):
        return f"<LeaveRequest Emp:{self.employee_id} From:{self.from_date} To:{self.to_date}>"