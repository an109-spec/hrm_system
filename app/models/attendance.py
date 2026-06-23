from app.models.base import BaseModel, db

class AttendanceShiftStatus:
    NOT_STARTED = "not_started" #Chưa vào ca
    WORKING_REGULAR = "working_regular" #Đang làm việc chính thức
    REGULAR_DONE = "regular_done"#Đã hoàn thành giờ hành chính
    REGULAR_DONE_PENDING_OT_DECISION = "regular_done_pending_ot_decision"#Xong giờ hành chính - Đang chờ quyết định tăng ca
    PRE_OT_REST = "pre_ot_rest"#Nghỉ giải lao trước khi tăng ca
    WORKING_OVERTIME = "working_overtime"#Đang làm tăng ca
    COMPLETED = "completed"#Hoàn thành ngày công
    HOLIDAY_OFF = "holiday_off"#Nghỉ lễ
    WEEKEND_OFF = "weekend_off"#Nghỉ cuối tuần
    ABSENT = "absent"#Vắng mặt
    LEAVE = "leave"

    REGULAR_CHECKOUT_REQUIRED = "regular_checkout_required"#Nhân viên đã hết giờ làm việc chính thức nhưng quên chưa bấm check-out. Hệ thống nhắc nhở phải hoàn tất ca này trước khi thực hiện các hành động khác
    OT_CHECKIN_REQUIRED = "ot_checkin_required"#Nhân viên đã được duyệt tăng ca hoặc đã hết giờ hành chính, nhưng cần phải thực hiện một thao tác bấm "Check-in OT" để hệ thống bắt đầu tính giờ làm thêm

    ACTIVE_STATUSES = frozenset({#nhóm Trạng thái đang hoạt động
        WORKING_REGULAR,
        REGULAR_DONE_PENDING_OT_DECISION,
        PRE_OT_REST,
        WORKING_OVERTIME,
        REGULAR_CHECKOUT_REQUIRED,
        OT_CHECKIN_REQUIRED,
    })

    TERMINAL_STATUSES = frozenset({ #nhóm Trạng thái kết thúc
        COMPLETED,
        HOLIDAY_OFF,
        WEEKEND_OFF,
        ABSENT,
        LEAVE,
    })
#Nếu status thuộc TERMINAL_STATUSES, nên khóa tất cả các nút như "Xác thực chấm công" hay "Tăng ca"
    VALID_STATUSES = frozenset({#nhóm trạng thái hợp lệ
        NOT_STARTED,#Chưa vào ca
        WORKING_REGULAR,#Đang làm việc chính thức
        REGULAR_DONE,#Đã hoàn thành giờ hành chính
        REGULAR_DONE_PENDING_OT_DECISION,#Xong giờ hành chính - Đang chờ quyết định tăng ca
        PRE_OT_REST,#Nghỉ giải lao trước khi tăng ca
        WORKING_OVERTIME,#Đang làm tăng ca
        COMPLETED,#Hoàn thành ngày công
        HOLIDAY_OFF,
        WEEKEND_OFF,
        ABSENT,
        LEAVE,
        REGULAR_CHECKOUT_REQUIRED,
#Nhân viên đã hết giờ làm việc chính thức nhưng quên chưa bấm check-out. Hệ thống nhắc nhở phải hoàn tất ca này trước khi thực hiện các hành động khác
        OT_CHECKIN_REQUIRED,
#Nhân viên đã được duyệt tăng ca hoặc đã hết giờ hành chính, nhưng cần phải thực hiện một thao tác bấm "Check-in OT" để hệ thống bắt đầu tính giờ làm thêm
#Dùng để kiểm tra dữ liệu đầu vào. Bất kỳ trạng thái nào không nằm trong tập hợp này khi lưu vào Database hoặc trả về Frontend đều bị coi là lỗi dữ liệu
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
#Chuyển đổi các giá trị cũ (Legacy), các chuỗi có khoảng trắng hoặc viết hoa/thường lộn xộn về một chuẩn duy nhất. 
# Nếu dữ liệu rỗng (None), nó tự động đưa về trạng thái mặc định là "Chưa bắt đầu".
    @classmethod
    def is_valid(cls, status: str | None) -> bool:
        return cls.normalize(status) in cls.VALID_STATUSES
#Kiểm tra xem một trạng thái (sau khi đã chuẩn hóa) 
# có nằm trong danh sách các trạng thái được hệ thống cho phép hay không.
    @classmethod
    def label(cls, status: str | None) -> str:
        return cls.LABELS.get(cls.normalize(status), "Không xác định")


class AttendanceType:
    NORMAL = "normal"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    OVERTIME = "overtime"#Làm việc tăng ca
    ABSENT = "absent"#Vắng mặt
    LEAVE = "leave"
    LOCKED = "locked"#Dữ liệu đã khóa (Bản ghi đã chốt công, không được sửa đổi).
    ABNORMAL = "abnormal"#Bất thường bị từ chối
    ABNORMAL_REJECTED = "abnormal_rejected"
    ABSENT_UNEXCUSED = "absent_unexcused"#Vắng mặt không lý do
    LEAVE_APPROVED = "leave_approved"#Nghỉ phép đã duyệt

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
        "late_early": NORMAL,#Vi phạm cả hai nhưng vẫn là ngày làm việc thường.
        "checked_out": NORMAL,#Đã đăng xuất thành công ngày làm việc thường
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
    __tablename__ = "attendance_status"

    id = db.Column(db.Integer, primary_key=True)

    status_name = db.Column(
        db.String(20),
        nullable=False
    )

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

    date = db.Column(
        db.Date,
        nullable=False,
        index=True
    )
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
    overtime_check_in = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    # check-out OT (22h)
    overtime_check_out = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

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
    # LATE / EARLY / HALF DAY
    # =====================================================

    # số phút đi muộn
    late_minutes = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    # số phút về sớm
    early_leave_minutes = db.Column(
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