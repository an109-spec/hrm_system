from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship


class OvertimeRequest(BaseModel):
    __tablename__ = "overtime_requests"

    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    overtime_date = db.Column(db.Date, nullable=False, index=True)
    overtime_hours = db.Column(db.Numeric(5, 2), nullable=0)
#Số giờ tăng ca thực tế (Dạng số thập phân, tối đa 5 chữ số, 2 số sau dấu phẩy).
    requested_hours = db.Column(db.Numeric(5, 2), nullable=True)
#requested_hours: Số giờ đăng ký (Dự kiến).
    approved_hours = db.Column(db.Numeric(5, 2), nullable=True)
#approved_hours: Số giờ được phê duyệt chính thức.
    start_ot_time = db.Column(db.DateTime(timezone=True), nullable=True)
    end_ot_time = db.Column(db.DateTime(timezone=True), nullable=True)
    reason = db.Column(db.Text, nullable=False)#reason: Lý do tăng ca (Bắt buộc).
    note = db.Column(db.Text, nullable=True)
    is_holiday_ot = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("false"))
#Đánh dấu có phải tăng ca vào ngày lễ hay không (Đúng/Sai).
    holiday_multiplier = db.Column(db.Numeric(4, 2), nullable=False, default=1, server_default="1.00")
    status = db.Column(# Trạng thái đơn (Mặc định là pending_manager - Đang chờ quản lý duyệt).
        db.String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

#Ghi chú hoặc phản hồi từ quản lý.
    hr_decision_by = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)
    hr_decision_at = db.Column(db.DateTime(timezone=True), nullable=True)
    hr_note = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)#ID người phê duyệt cuối cùng.
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)#Thời điểm phê duyệt cuối cùng.
    rejection_reason = db.Column(db.Text, nullable=True)#Lý do từ chối (nếu đơn bị bác bỏ).
    employee = relationship("Employee", foreign_keys=[employee_id])

    def __repr__(self):
        return f"<OvertimeRequest {self.id} Emp:{self.employee_id} {self.status}>"