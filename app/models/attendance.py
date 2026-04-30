# app/models/attendance.py

from app.models.base import BaseModel, db


class AttendanceStatus(db.Model):
    """
    Bảng danh mục trạng thái chấm công.
    Ví dụ:
    1 - PRESENT
    2 - LATE
    3 - ABSENT
    4 - LEAVE
    """

    __tablename__ = "attendance_status"

    id = db.Column(db.Integer, primary_key=True)

    status_name = db.Column(
        db.String(20),
        nullable=False
    )  # PRESENT / LATE / ABSENT / LEAVE

    multiplier = db.Column(
        db.Float,
        default=1.0
    )  # hệ số công

    description = db.Column(
        db.String(255),
        nullable=True
    )

    def __repr__(self):
        return f"<AttendanceStatus {self.status_name}>"


class Attendance(BaseModel):
    """
    Bảng lưu dữ liệu chấm công theo ngày.

    Luồng chuẩn:

    - check_in ca chính
    - check_out ca chính
    - nghỉ trước OT
    - overtime_check_in
    - overtime_check_out

    Phân biệt:
    - ngày thường
    - cuối tuần
    - ngày lễ

    Có xử lý:
    - đi muộn
    - nửa ngày công
    - OT
    """

    __tablename__ = "attendance"

    # =====================================================
    # FK
    # =====================================================

    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False,
        index=True
    )

    status_id = db.Column(
        db.Integer,
        db.ForeignKey("attendance_status.id"),
        nullable=True
    )

    # =====================================================
    # BASIC INFO
    # =====================================================

    date = db.Column(
        db.Date,
        nullable=False,
        index=True
    )

    # =====================================================
    # REGULAR SHIFT
    # =====================================================

    # check-in ca chính
    check_in = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    # check-out ca chính
    check_out = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    # =====================================================
    # OVERTIME SHIFT
    # =====================================================

    # check-in OT (19h+)
    overtime_check_in = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    # check-out OT (22h)
    overtime_check_out = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    # =====================================================
    # HOURS
    # =====================================================

    # tổng công
    working_hours = db.Column(
        db.Numeric(6, 2),
        default=0
    )

    # công chuẩn
    regular_hours = db.Column(
        db.Numeric(6, 2),
        default=0
    )

    # công tăng ca
    overtime_hours = db.Column(
        db.Numeric(6, 2),
        default=0
    )

    # =====================================================
    # DAY TYPE
    # =====================================================

    is_weekend = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    is_holiday = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    # =====================================================
    # LATE / HALF DAY
    # =====================================================

    # số phút đi muộn
    late_minutes = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    # đi muộn > 60 phút => nửa ngày công
    is_half_day = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    # =====================================================
    # FLOW STATUS
    # =====================================================

    """
    shift_status:

    not_started
    working_regular
    checked_out_regular
    pre_overtime_rest
    working_overtime
    completed
    absent
    leave
    """

    shift_status = db.Column(
        db.String(30),
        default="not_started",
        nullable=False
    )

    """
    attendance_type:

    normal
    weekend
    holiday
    """

    attendance_type = db.Column(
        db.String(20),
        default="normal",
        nullable=False
    )

    # =====================================================
    # UNIQUE
    # =====================================================

    __table_args__ = (
        db.UniqueConstraint(
            "employee_id",
            "date",
            name="uq_employee_date_attendance"
        ),
    )

    # =====================================================
    # RELATIONSHIP
    # =====================================================

    status = db.relationship(
        "AttendanceStatus",
        backref="attendances"
    )

    # =====================================================
    # DEBUG
    # =====================================================

    def __repr__(self):
        return f"<Attendance Emp:{self.employee_id} Date:{self.date}>"