from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship
class HistoryLog(BaseModel):
    """
    Model lưu lịch sử thay đổi / sự kiện hệ thống.
    Dùng cho timeline nhân viên và audit.
    """
    __tablename__ = 'history_logs'

    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    action = db.Column(db.String(100), nullable=False)

    entity_type = db.Column(db.String(50), nullable=True)

    entity_id = db.Column(db.Integer, nullable=True)

    description = db.Column(db.Text, nullable=True)

    performed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    employee = relationship(
        "Employee",
        back_populates="history_logs"
    )
    def __repr__(self):
        return f"<HistoryLog {self.action} - Entity:{self.entity_type}:{self.entity_id}>"
    @staticmethod
    def append(employee_id, action, entity_type=None, entity_id=None, description=None, performed_by=None):
        log = HistoryLog(
            employee_id=employee_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            performed_by=performed_by
        )
        db.session.add(log)
        return log