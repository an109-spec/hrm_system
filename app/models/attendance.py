from app.models.base import BaseModel, db

class AttendanceStatus(db.Model):
    """
    Bảng danh mục trạng thái chấm công.
    Ví dụ: 1-PRESENT (1.0), 2-LATE (0.5), 3-ABSENT (0), 4-LEAVE (1.0)
    """
    __tablename__ = 'attendance_status'

    id = db.Column(db.Integer, primary_key=True)
    status_name = db.Column(db.String(20), nullable=False) # PRESENT, LATE, ABSENT, LEAVE
    multiplier = db.Column(db.Float, default=1.0) # Hệ số công
    description = db.Column(db.String(255)) # Mô tả chi tiết quy định

    def __repr__(self):
        return f"<AttendanceStatus {self.status_name}>"

class Attendance(BaseModel):
    """
    Bảng lưu dữ liệu chấm công chi tiết hàng ngày của nhân viên.
    Kế thừa BaseModel để có id, created_at, updated_at.
    """
    __tablename__ = 'attendance'

    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True) # Ngày chấm công
    
    # Thời gian vào/ra thực tế
    check_in = db.Column(db.DateTime(timezone=True), nullable=True)
    check_out = db.Column(db.DateTime(timezone=True), nullable=True)
    
    working_hours = db.Column(db.Numeric(4, 2), default=0)
    regular_hours = db.Column(db.Numeric(4, 2), default=0)
    overtime_hours = db.Column(db.Numeric(4, 2), default=0)
    attendance_type = db.Column(db.String(20), default="normal")  # normal / overtime / holiday
    # Liên kết tới trạng thái chấm công
    status_id = db.Column(db.Integer, db.ForeignKey('attendance_status.id'), nullable=True)

    # Ràng buộc: Một nhân viên chỉ có 1 dòng chấm công cho mỗi ngày
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'date', name='uq_employee_date_attendance'),
    )

    # Relationship để lấy nhanh tên trạng thái
    status = db.relationship('AttendanceStatus', backref='attendances')

    def __repr__(self):
        return f"<Attendance Emp:{self.employee_id} Date:{self.date}>"