from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship


class ResignationRequest(BaseModel):
    __tablename__ = "resignation_requests"

    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)
    handover_employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)

    request_type = db.Column(db.String(30), nullable=False, default="employee", server_default="employee")
    status = db.Column(db.String(30), nullable=False, default="pending_manager", server_default="pending_manager")

    expected_last_day = db.Column(db.Date, nullable=False)
    reason_category = db.Column(db.String(30), nullable=False)
    reason_text = db.Column(db.Text, nullable=True)
    extra_note = db.Column(db.Text, nullable=True)
    attachment_url = db.Column(db.String(255), nullable=True)

    manager_note = db.Column(db.Text, nullable=True)
    hr_note = db.Column(db.Text, nullable=True)
    admin_note = db.Column(db.Text, nullable=True)

    final_payroll_note = db.Column(db.Text, nullable=True)
    final_attendance_note = db.Column(db.Text, nullable=True)
    leave_balance_note = db.Column(db.Text, nullable=True)
    insurance_note = db.Column(db.Text, nullable=True)
    asset_handover_note = db.Column(db.Text, nullable=True)

    reviewed_by_manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    processed_by_hr_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    employee = relationship("Employee", foreign_keys=[employee_id], backref="resignation_requests")
    handover_employee = relationship("Employee", foreign_keys=[handover_employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "manager_id": self.manager_id,
            "request_type": self.request_type,
            "status": self.status,
            "expected_last_day": self.expected_last_day.isoformat() if self.expected_last_day else None,
            "reason_category": self.reason_category,
            "reason_text": self.reason_text,
            "extra_note": self.extra_note,
            "attachment_url": self.attachment_url,
            "handover_employee_id": self.handover_employee_id,
            "handover_employee_name": self.handover_employee.full_name if self.handover_employee else None,
            "manager_note": self.manager_note,
            "hr_note": self.hr_note,
            "admin_note": self.admin_note,
            "final_payroll_note": self.final_payroll_note,
            "final_attendance_note": self.final_attendance_note,
            "leave_balance_note": self.leave_balance_note,
            "insurance_note": self.insurance_note,
            "asset_handover_note": self.asset_handover_note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }