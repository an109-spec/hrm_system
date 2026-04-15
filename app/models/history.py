# app/models/history.py

from app.models.base import BaseModel, db

class HistoryLog(BaseModel):
    """
    Model lưu lịch sử thay đổi / sự kiện hệ thống.
    Dùng cho timeline nhân viên và audit.
    """
    __tablename__ = 'history_logs'

    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    action = db.Column(db.String(100), nullable=False)
    # 'CREATE_EMPLOYEE', 'UPDATE_PROFILE', 'CHECK_IN', 'APPROVE_LEAVE'

    entity_type = db.Column(db.String(50), nullable=True)
    # 'employee', 'salary', 'leave', 'attendance'

    entity_id = db.Column(db.Integer, nullable=True)

    description = db.Column(db.Text, nullable=True)

    performed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def __repr__(self):
        return f"<HistoryLog {self.action} - Entity:{self.entity_type}:{self.entity_id}>"