from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship


class OvertimeRequest(BaseModel):
    __tablename__ = "overtime_requests"

    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    overtime_date = db.Column(db.Date, nullable=False, index=True)
    overtime_hours = db.Column(db.Numeric(5, 2), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    note = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.String(30),
        nullable=False,
        default="pending_manager",
        server_default="pending_manager",
    )
    manager_decision_by = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)
    manager_decision_at = db.Column(db.DateTime(timezone=True), nullable=True)
    manager_note = db.Column(db.Text, nullable=True)

    hr_decision_by = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)
    hr_decision_at = db.Column(db.DateTime(timezone=True), nullable=True)
    hr_note = db.Column(db.Text, nullable=True)

    rejection_reason = db.Column(db.Text, nullable=True)
    employee = relationship("Employee", foreign_keys=[employee_id])

    def __repr__(self):
        return f"<OvertimeRequest {self.id} Emp:{self.employee_id} {self.status}>"