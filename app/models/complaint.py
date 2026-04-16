from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship


class Complaint(BaseModel):
    """
    Model quản lý khiếu nại của nhân viên.
    """
    __tablename__ = 'complaints'

    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)

    # Liên kết optional
    salary_id = db.Column(db.Integer, db.ForeignKey('salaries.id'), nullable=True)
    leave_request_id = db.Column(db.Integer, db.ForeignKey('leave_requests.id'), nullable=True)

    # Phân loại
    type = db.Column(db.String(50), nullable=False)

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)

    status = db.Column(
        db.Enum('pending', 'in_progress', 'resolved', 'rejected', name='complaint_status_enum'),
        default='pending',
        server_default='pending'
    )

    priority = db.Column(
        db.Enum('low', 'normal', 'high', 'urgent', name='complaint_priority_enum'),
        default='normal',
        server_default='normal'
    )

    # Người xử lý
    handled_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # ======================
    # RELATIONSHIPS
    # ======================

    employee = relationship('Employee', foreign_keys=[employee_id], backref='complaints')
    handler = relationship('Employee', foreign_keys=[handled_by])

    messages = relationship(
        'ComplaintMessage',
        backref='complaint',
        lazy='dynamic',
        cascade="all, delete-orphan"
    )

    # ✅ FIX CHUẨN (KHÔNG LỖI)
    attachments = relationship(
        'FileUpload',
        backref='complaint',
        lazy='dynamic',
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Complaint {self.id} - {self.type} - {self.status}>"
    
class ComplaintMessage(BaseModel):
    __tablename__ = 'complaint_messages'

    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)

    message = db.Column(db.Text, nullable=False)

    sender = relationship('Employee')

    def __repr__(self):
        return f"<ComplaintMessage {self.id} - Complaint:{self.complaint_id}>"