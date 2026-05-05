# app/models/attendance.py

from app.models.base import BaseModel, db

class AttendanceShiftStatus:
    """
    Danh sách trạng thái luồng chấm công chuẩn.

    Đây là nguồn sự thật cho `Attendance.shift_status`. Các service/routes/jobs/UI
    nên dùng các constant này thay vì hard-code string rải rác.
    """

    NOT_STARTED = "not_started"
    WORKING_REGULAR = "working_regular"
    REGULAR_DONE = "regular_done"
    REGULAR_DONE_PENDING_OT_DECISION = "regular_done_pending_ot_decision"
    PRE_OT_REST = "pre_ot_rest"
    WORKING_OVERTIME = "working_overtime"
    COMPLETED = "completed"
    HOLIDAY_OFF = "holiday_off"
    WEEKEND_OFF = "weekend_off"
    ABSENT = "absent"
    LEAVE = "leave"

    # Trạng thái nhắc việc hệ thống đang được jobs hiện tại sử dụng.
    # Vẫn giữ trong danh sách hợp lệ để refactor từng bước không làm vỡ dữ liệu cũ.
    REGULAR_CHECKOUT_REQUIRED = "regular_checkout_required"
    OT_CHECKIN_REQUIRED = "ot_checkin_required"

    ACTIVE_STATUSES = frozenset({
        WORKING_REGULAR,
        REGULAR_DONE_PENDING_OT_DECISION,
        PRE_OT_REST,
        WORKING_OVERTIME,
        REGULAR_CHECKOUT_REQUIRED,
        OT_CHECKIN_REQUIRED,
    })

    TERMINAL_STATUSES = frozenset({
        COMPLETED,
        HOLIDAY_OFF,
        WEEKEND_OFF,
        ABSENT,
        LEAVE,
    })

    VALID_STATUSES = frozenset({
        NOT_STARTED,
        WORKING_REGULAR,
        REGULAR_DONE,
        REGULAR_DONE_PENDING_OT_DECISION,
        PRE_OT_REST,
        WORKING_OVERTIME,
        COMPLETED,
        HOLIDAY_OFF,
        WEEKEND_OFF,
        ABSENT,
        LEAVE,
        REGULAR_CHECKOUT_REQUIRED,
        OT_CHECKIN_REQUIRED,
    })

    LABELS = {
        NOT_STARTED: "Chưa chấm công",
        WORKING_REGULAR: "Đang làm ca chính",
        REGULAR_DONE: "Hoàn thành ca chính",
        REGULAR_DONE_PENDING_OT_DECISION: "Chờ xác nhận tăng ca",
        PRE_OT_REST: "Nghỉ trước tăng ca",
        WORKING_OVERTIME: "Đang tăng ca",
        COMPLETED: "Hoàn tất ngày công",
        HOLIDAY_OFF: "Nghỉ lễ",
        WEEKEND_OFF: "Nghỉ cuối tuần",
        ABSENT: "Vắng mặt",
        LEAVE: "Nghỉ phép",
        REGULAR_CHECKOUT_REQUIRED: "Cần checkout ca chính",
        OT_CHECKIN_REQUIRED: "Cần check-in tăng ca",
    }

    # Alias để đọc được dữ liệu/trạng thái cũ trong code hiện tại.
    LEGACY_ALIASES = {
        "working": WORKING_REGULAR,
        "late": WORKING_REGULAR,
        "half_day": WORKING_REGULAR,
        "checked_out_regular": REGULAR_DONE,
        "regular_completed": REGULAR_DONE,
        "pre_overtime_rest": PRE_OT_REST,
        "pre_ot_rest_verified": PRE_OT_REST,
        "pre_ot_rest_pending_checkin": PRE_OT_REST,
        "ot_unverified": OT_CHECKIN_REQUIRED,
        "overtime_working": WORKING_OVERTIME,
        "early_leave": COMPLETED,
        "done": COMPLETED,
    }

    @classmethod
    def normalize(cls, status: str | None) -> str:
        status_key = (status or cls.NOT_STARTED).strip().lower()
        return cls.LEGACY_ALIASES.get(status_key, status_key)

    @classmethod
    def is_valid(cls, status: str | None) -> bool:
        return cls.normalize(status) in cls.VALID_STATUSES

    @classmethod
    def label(cls, status: str | None) -> str:
        return cls.LABELS.get(cls.normalize(status), "Không xác định")


class AttendanceType:
    """
    Danh sách loại ngày/cách ghi nhận công chuẩn cho `Attendance.attendance_type`.
    """

    NORMAL = "normal"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    OVERTIME = "overtime"
    ABSENT = "absent"
    LEAVE = "leave"

    # Các loại phục vụ vận hành/admin hiện có trong hệ thống.
    LOCKED = "locked"
    ABNORMAL = "abnormal"
    ABNORMAL_REJECTED = "abnormal_rejected"
    ABSENT_UNEXCUSED = "absent_unexcused"
    LEAVE_APPROVED = "leave_approved"

    VALID_TYPES = frozenset({
        NORMAL,
        WEEKEND,
        HOLIDAY,
        OVERTIME,
        ABSENT,
        LEAVE,
        LOCKED,
        ABNORMAL,
        ABNORMAL_REJECTED,
        ABSENT_UNEXCUSED,
        LEAVE_APPROVED,
    })

    LABELS = {
        NORMAL: "Ngày thường",
        WEEKEND: "Cuối tuần",
        HOLIDAY: "Ngày lễ",
        OVERTIME: "Có tăng ca",
        ABSENT: "Vắng mặt",
        LEAVE: "Nghỉ phép",
        LOCKED: "Đã khóa công",
        ABNORMAL: "Bất thường",
        ABNORMAL_REJECTED: "Bất thường bị từ chối",
        ABSENT_UNEXCUSED: "Vắng không phép",
        LEAVE_APPROVED: "Nghỉ phép đã duyệt",
    }

    LEGACY_ALIASES = {
        "late": NORMAL,
        "early": NORMAL,
        "late_early": NORMAL,
        "checked_out": NORMAL,
    }

    @classmethod
    def normalize(cls, attendance_type: str | None) -> str:
        type_key = (attendance_type or cls.NORMAL).strip().lower()
        return cls.LEGACY_ALIASES.get(type_key, type_key)

    @classmethod
    def is_valid(cls, attendance_type: str | None) -> bool:
        return cls.normalize(attendance_type) in cls.VALID_TYPES

    @classmethod
    def label(cls, attendance_type: str | None) -> str:
        return cls.LABELS.get(cls.normalize(attendance_type), "Không xác định")

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
    __tablename__ = "attendance"
    ShiftStatus = AttendanceShiftStatus
    Type = AttendanceType
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

    shift_status = db.Column(
        db.String(64),
        default=AttendanceShiftStatus.NOT_STARTED,
        nullable=False
    )
    attendance_type = db.Column(
        db.String(20),
        default=AttendanceType.NORMAL,
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
    # STATUS / TYPE HELPERS
    # =====================================================

    @property
    def normalized_shift_status(self) -> str:
        return AttendanceShiftStatus.normalize(self.shift_status)

    @property
    def shift_status_label(self) -> str:
        return AttendanceShiftStatus.label(self.shift_status)

    @property
    def normalized_attendance_type(self) -> str:
        return AttendanceType.normalize(self.attendance_type)

    @property
    def attendance_type_label(self) -> str:
        return AttendanceType.label(self.attendance_type)

    @property
    def is_flow_active(self) -> bool:
        return self.normalized_shift_status in AttendanceShiftStatus.ACTIVE_STATUSES

    @property
    def is_flow_terminal(self) -> bool:
        return self.normalized_shift_status in AttendanceShiftStatus.TERMINAL_STATUSES

    def set_shift_status(self, status: str) -> None:
        normalized_status = AttendanceShiftStatus.normalize(status)
        if not AttendanceShiftStatus.is_valid(normalized_status):
            raise ValueError(f"Invalid attendance shift_status: {status}")
        self.shift_status = normalized_status

    def set_attendance_type(self, attendance_type: str) -> None:
        normalized_type = AttendanceType.normalize(attendance_type)
        if not AttendanceType.is_valid(normalized_type):
            raise ValueError(f"Invalid attendance_type: {attendance_type}")
        self.attendance_type = normalized_type

    def to_dict(self):
        data = super().to_dict()
        data["shift_status"] = self.normalized_shift_status
        data["shift_status_label"] = self.shift_status_label
        data["attendance_type"] = self.normalized_attendance_type
        data["attendance_type_label"] = self.attendance_type_label
        data["is_flow_active"] = self.is_flow_active
        data["is_flow_terminal"] = self.is_flow_terminal
        return data
    def __repr__(self):
        return f"<Attendance Emp:{self.employee_id} Date:{self.date}>"