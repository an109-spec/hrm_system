from __future__ import annotations

from datetime import datetime, time, date
from decimal import Decimal
from types import SimpleNamespace

from flask import session
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Attendance,
    AttendanceStatus,
    Employee,
    Holiday,
    Notification,
    OvertimeRequest,
    LeaveRequest,
)
from app.common.exceptions import ValidationError


# ══════════════════════════════════════════════════════════════════════════════
# TIME CONSTANTS  ← single source of truth, không được define lại ở routes
# ══════════════════════════════════════════════════════════════════════════════

REGULAR_START    = time(8,  0, 0)
REGULAR_END      = time(17, 0, 0)
LUNCH_START      = time(12, 0, 0)
LUNCH_END        = time(13, 0, 0)
LATE_THRESHOLD   = time(9,  0, 0)   # check-in sau giờ này → is_half_day
OT_CHECKIN_OPEN  = time(19, 0, 0)   # giờ hiệu lực OT (clamp khi tính công)
OT_END           = time(22, 0, 0)

# ══════════════════════════════════════════════════════════════════════════════
# MULTIPLIERS
# ══════════════════════════════════════════════════════════════════════════════

HOLIDAY_MULTIPLIER = Decimal("3.00")
WEEKEND_MULTIPLIER = Decimal("1.00")   # ← cuối tuần KHÔNG nhân hệ số
NORMAL_MULTIPLIER  = Decimal("1.00")


# ══════════════════════════════════════════════════════════════════════════════
# RESULT TYPE cho compute_attendance_state
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceStateResult:
    """Kết quả duy nhất từ compute_attendance_state() — mọi nơi đều dùng cái này."""

    def __init__(
        self,
        state: str,
        button_enabled: bool,
        button_text: str,
        can_scan: bool,
        message: str | None = None,
        overtime_status: str | None = None,
    ):
        self.state          = state
        self.button_enabled = button_enabled
        self.button_text    = button_text
        self.can_scan       = can_scan
        self.message        = message
        self.overtime_status = overtime_status

    def to_dict(self) -> dict:
        return {
            "attendance_state": self.state,
            "button_enabled":   self.button_enabled,
            "button_text":      self.button_text,
            "can_scan":         self.can_scan,
            "message":          self.message,
            "overtime_status":  self.overtime_status,
        }


# ══════════════════════════════════════════════════════════════════════════════
# AttendanceService
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceService:

    # ── config (re-export để backward compat) ─────────────────────────────
    REGULAR_START     = REGULAR_START
    REGULAR_END       = REGULAR_END
    LUNCH_START       = LUNCH_START
    LUNCH_END         = LUNCH_END
    LATE_THRESHOLD    = LATE_THRESHOLD
    OT_START          = OT_CHECKIN_OPEN   # alias
    OT_CHECKIN_OPEN   = OT_CHECKIN_OPEN
    OT_END            = OT_END
    OT_EARLY_CHECKIN  = OT_CHECKIN_OPEN   # alias — xóa magic 18:30 cũ
    MIN_OT_REST_MINUTES = 0               # không còn bắt buộc đợi 30p

    # ── action constants ───────────────────────────────────────────────────
    ACTION_CHECK_IN                   = "check_in"
    ACTION_CHECK_OUT                  = "check_out"
    ACTION_CHECK_IN_OT                = "check_in_overtime"
    ACTION_CHECK_OUT_OT               = "check_out_overtime"
    ACTION_HOLIDAY_WORK_PROMPT        = "holiday_work_prompt"
    ACTION_WEEKEND_WORK_PROMPT        = "weekend_work_prompt"
    ACTION_EARLY_CHECKOUT_PROMPT      = "early_checkout_prompt"
    ACTION_OFFER_OVERTIME             = "offer_overtime"
    ACTION_ALREADY_RECORDED          = "already_recorded"
    ACTION_OVERTIME_REQUEST_CREATED   = "overtime_request_created"
    ACTION_COMPLETE_WITHOUT_OT        = "complete_without_overtime"
    ACTION_HOLIDAY_OFF                = "holiday_off"
    ACTION_WEEKEND_OFF                = "weekend_off"
    ACTION_OVERTIME_DECISION_RECORDED = "overtime_decision_recorded"

    # ══════════════════════════════════════════════════════════════════════
    # COMPUTE_ATTENDANCE_STATE  ← single source of truth
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def compute_attendance_state(
        now: datetime,
        attendance: Attendance | None,
        ot_request: OvertimeRequest | None = None,
    ) -> AttendanceStateResult:
        """
        Tính trạng thái chấm công tại thời điểm `now`.
        Đây là HÀM DUY NHẤT được phép quyết định state — không tính lại ở routes.
        """
        current_time = now.time()

        # ── Nếu chưa có bản ghi ──────────────────────────────────────────
        if not attendance or not attendance.check_in:
            return AttendanceStateResult(
                state="not_started",
                button_enabled=True,
                button_text="🔳 XÁC THỰC CHẤM CÔNG",
                can_scan=True,
            )

        raw_state = Attendance.ShiftStatus.normalize(attendance.shift_status)

        # ── Terminal states ───────────────────────────────────────────────
        if raw_state == Attendance.ShiftStatus.COMPLETED:
            return AttendanceStateResult(
                state="completed",
                button_enabled=False,
                button_text="✅ ĐÃ HOÀN THÀNH CÔNG VIỆC",
                can_scan=False,
            )
        if raw_state == Attendance.ShiftStatus.HOLIDAY_OFF:
            return AttendanceStateResult(
                state="holiday_off",
                button_enabled=False,
                button_text="🎉 Đã ghi nhận nghỉ lễ",
                can_scan=False,
            )
        if raw_state == Attendance.ShiftStatus.WEEKEND_OFF:
            return AttendanceStateResult(
                state="weekend_off",
                button_enabled=False,
                button_text="🛌 Đã ghi nhận nghỉ cuối tuần",
                can_scan=False,
            )
        if raw_state == Attendance.ShiftStatus.LEAVE:
            return AttendanceStateResult(
                state="leave",
                button_enabled=False,
                button_text="📋 Đang nghỉ phép",
                can_scan=False,
            )
        if raw_state == Attendance.ShiftStatus.ABSENT:
            return AttendanceStateResult(
                state="absent",
                button_enabled=False,
                button_text="❌ Vắng mặt",
                can_scan=False,
            )

        # ── Đang làm ca chính ─────────────────────────────────────────────
        if raw_state == Attendance.ShiftStatus.WORKING_REGULAR:
            # Giờ nghỉ trưa → disable
            if LUNCH_START <= current_time < LUNCH_END:
                return AttendanceStateResult(
                    state="lunch_break",
                    button_enabled=False,
                    button_text="🍽️ ĐANG NGHỈ TRƯA",
                    can_scan=False,
                    message="Đang trong giờ nghỉ trưa (12:00–13:00)",
                )
            return AttendanceStateResult(
                state="working_regular",
                button_enabled=True,
                button_text="🔳 XÁC NHẬN HẾT CA HÀNH CHÍNH",
                can_scan=True,
            )

        # ── Đã check-out ca chính ─────────────────────────────────────────
        if raw_state == Attendance.ShiftStatus.REGULAR_DONE:
            return AttendanceStateResult(
                state="regular_done_pending_ot_decision",
                button_enabled=False,
                button_text="⏳ ĐANG CHỜ DUYỆT TĂNG CA",
                can_scan=False,
                message="Vui lòng xác nhận có muốn tăng ca không",
            )

        # ── Chờ duyệt OT ─────────────────────────────────────────────────
        if raw_state == Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION:
            ot_status = ot_request.status.upper() if ot_request else "PENDING"
            return AttendanceStateResult(
                state="regular_done_pending_ot_decision",
                button_enabled=False,
                button_text="⏳ ĐANG CHỜ DUYỆT OT",
                can_scan=False,
                overtime_status=ot_status,
                message="Đang chờ HR/Admin phê duyệt tăng ca",
            )

        # ── OT đã duyệt, nghỉ ngơi trước tăng ca ────────────────────────
        if raw_state == Attendance.ShiftStatus.PRE_OT_REST:
            if not attendance.overtime_check_in and current_time < OT_CHECKIN_OPEN:
                return AttendanceStateResult(
                    state="pre_ot_rest",
                    button_enabled=False,
                    button_text="⏳ ĐÃ XÁC THỰC - CHỜ ĐẾN 19:00",
                    can_scan=False,
                    message="OT đã được duyệt. Vui lòng nghỉ ngơi, đến 19:00 mới bắt đầu tăng ca.",
                    overtime_status="APPROVED",
                )
            if not attendance.overtime_check_in:
                return AttendanceStateResult(
                    state="pre_ot_rest",
                    button_enabled=True,
                    button_text="🔳 XÁC THỰC TĂNG CA",
                    can_scan=True,
                    message="Đã đến giờ tăng ca, vui lòng xác thực check-in OT.",
                    overtime_status="APPROVED",
                )
            return AttendanceStateResult(
                state="working_overtime",
                button_enabled=True,
                button_text="🔳 XÁC NHẬN KẾT THÚC TĂNG CA",
                can_scan=True,
                overtime_status="APPROVED",
            )

        # ── Đang tăng ca ─────────────────────────────────────────────────
        if raw_state == Attendance.ShiftStatus.WORKING_OVERTIME:
            return AttendanceStateResult(
                state="working_overtime",
                button_enabled=True,
                button_text="🔳 XÁC NHẬN KẾT THÚC TĂNG CA",
                can_scan=True,
                overtime_status="APPROVED",
            )

        # ── Fallback ──────────────────────────────────────────────────────
        return AttendanceStateResult(
            state=raw_state or "not_started",
            button_enabled=False,
            button_text="—",
            can_scan=False,
        )

    # ══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def parse_time(sim_time_str: str | None = None) -> datetime:
        if not sim_time_str:
            return datetime.now()
        now_dt = datetime.fromisoformat(sim_time_str.replace("Z", "+00:00"))
        if now_dt.tzinfo is not None:
            now_dt = now_dt.replace(tzinfo=None)
        return now_dt

    @staticmethod
    def get_or_create_today(employee_id: int, now_dt: datetime) -> Attendance:
        record = Attendance.query.filter_by(
            employee_id=employee_id, date=now_dt.date()
        ).first()
        if record:
            return record
        record = Attendance(
            employee_id=employee_id,
            date=now_dt.date(),
            shift_status=Attendance.ShiftStatus.NOT_STARTED,
            attendance_type=Attendance.Type.NORMAL,
            working_hours=Decimal("0.00"),
            regular_hours=Decimal("0.00"),
            overtime_hours=Decimal("0.00"),
            is_half_day=False,
            late_minutes=0,
            is_weekend=False,
            is_holiday=False,
        )
        db.session.add(record)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            record = Attendance.query.filter_by(
                employee_id=employee_id, date=now_dt.date()
            ).first()
        return record

    @staticmethod
    def get_status(status_name: str):
        return AttendanceStatus.query.filter_by(status_name=status_name).first()

    @staticmethod
    def _is_holiday(target_date: date) -> bool:
        if Holiday.query.filter_by(date=target_date).first():
            return True
        recurring = (
            Holiday.query.filter_by(is_recurring=True)
            .filter(db.extract("month", Holiday.date) == target_date.month)
            .filter(db.extract("day", Holiday.date) == target_date.day)
            .first()
        )
        return bool(recurring)

    @staticmethod
    def _day_multiplier(is_holiday: bool, is_weekend: bool) -> Decimal:
        if is_holiday:
            return HOLIDAY_MULTIPLIER
        if is_weekend:
            return WEEKEND_MULTIPLIER
        return NORMAL_MULTIPLIER

    @staticmethod
    def _resolve_attendance_type(
        is_weekend: bool, is_holiday: bool, has_overtime: bool = False
    ) -> str:
        if is_holiday:
            return Attendance.Type.HOLIDAY
        if has_overtime:
            return Attendance.Type.OVERTIME
        if is_weekend:
            return Attendance.Type.WEEKEND
        return Attendance.Type.NORMAL

    # ══════════════════════════════════════════════════════════════════════
    # HOUR CALCULATIONS
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def calculate_regular_hours_raw(check_in: datetime, check_out: datetime) -> Decimal:
        """
        Tính giờ công ca chính CHƯA nhân hệ số.
        - effective_start = max(check_in, 08:00)
        - effective_end   = min(check_out, 17:00)
        - Trừ overlap với 12:00–13:00
        Ví dụ: check_in=8:47 → effective_start=8:47; check_out=17:00
               raw = (17:00 - 8:47) - 1h trưa = 7h13m = 7.2167h
        """
        if not check_in or not check_out:
            return Decimal("0.00")

        day         = check_in.date()
        shift_start = datetime.combine(day, REGULAR_START)
        shift_end   = datetime.combine(day, REGULAR_END)
        lunch_start = datetime.combine(day, LUNCH_START)
        lunch_end   = datetime.combine(day, LUNCH_END)

        actual_start = max(check_in, shift_start)
        actual_end   = min(check_out, shift_end)

        if actual_end <= actual_start:
            return Decimal("0.00")

        total_seconds = (actual_end - actual_start).total_seconds()

        overlap_start = max(actual_start, lunch_start)
        overlap_end   = min(actual_end, lunch_end)
        lunch_seconds = (
            (overlap_end - overlap_start).total_seconds()
            if overlap_end > overlap_start
            else 0
        )

        hours = (total_seconds - lunch_seconds) / 3600
        return Decimal(str(round(max(0.0, hours), 4)))

    @staticmethod
    def calculate_regular_hours(check_in: datetime, check_out: datetime) -> Decimal:
        return AttendanceService.calculate_regular_hours_raw(check_in, check_out)

    @staticmethod
    def recalculate_hours(check_in: datetime, check_out: datetime) -> Decimal:
        return AttendanceService.calculate_regular_hours_raw(check_in, check_out)

    @staticmethod
    def calculate_overtime_hours_raw(
        overtime_check_in: datetime, overtime_check_out: datetime
    ) -> Decimal:
        """
        Tính giờ OT CHƯA nhân hệ số.
        - effective_start = max(ot_check_in, 19:00)   ← luôn clamp về 19:00
        - effective_end   = min(ot_check_out, 22:00)
        Không trừ khoảng nghỉ (17:00–19:00 không tính — nhưng đã bị clamp bởi effective_start).
        """
        if not overtime_check_in or not overtime_check_out:
            return Decimal("0.00")
        if overtime_check_in.tzinfo is not None:
            overtime_check_in = overtime_check_in.replace(tzinfo=None)
        if overtime_check_out.tzinfo is not None:
            overtime_check_out = overtime_check_out.replace(tzinfo=None)

        day      = overtime_check_in.date()
        ot_start = datetime.combine(day, OT_CHECKIN_OPEN)   # 19:00
        ot_end   = datetime.combine(day, OT_END)            # 22:00

        actual_start = max(ot_start, overtime_check_in)
        actual_end   = min(ot_end,   overtime_check_out)

        if actual_end <= actual_start:
            return Decimal("0.00")

        hours = (actual_end - actual_start).total_seconds() / 3600
        return Decimal(str(round(hours, 4)))

    @staticmethod
    def calculate_overtime_hours(
        overtime_check_in: datetime, overtime_check_out: datetime
    ) -> Decimal:
        return AttendanceService.calculate_overtime_hours_raw(overtime_check_in, overtime_check_out)

    # ══════════════════════════════════════════════════════════════════════
    # FINALIZE
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def finalize_attendance(record: Attendance, finalize_status: bool = True) -> None:
        """
        Tính lại working_hours = regular_hours + overtime_hours.
        Cả hai trường này ĐÃ bao gồm hệ số nhân (set tại thời điểm checkout).
        """
        regular_hours  = Decimal(str(record.regular_hours  or 0))
        overtime_hours = Decimal(str(record.overtime_hours or 0))
        record.working_hours = (regular_hours + overtime_hours).quantize(Decimal("0.01"))

        has_overtime = overtime_hours > 0
        base_type = AttendanceService._resolve_attendance_type(
            bool(record.is_weekend),
            bool(record.is_holiday),
            has_overtime,
        )
        if record.is_half_day and base_type == Attendance.Type.NORMAL:
            record.set_attendance_type(Attendance.Type.ABNORMAL)
        else:
            record.set_attendance_type(base_type)

        if finalize_status:
            record.set_shift_status(Attendance.ShiftStatus.COMPLETED)

    # ══════════════════════════════════════════════════════════════════════
    # AUTO-COMPLETE (gọi từ job scheduler hoặc khi load trang mới ngày)
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def auto_complete_stale_records(reference_date: date | None = None) -> int:
        """
        Tự động hoàn tất các bản ghi của ngày hôm qua trở về trước
        mà vẫn còn trạng thái chưa kết thúc.
        Trả về số bản ghi đã được xử lý.
        """
        from datetime import date as date_cls
        today = reference_date or date_cls.today()

        stale_statuses = [
            Attendance.ShiftStatus.WORKING_REGULAR,
            Attendance.ShiftStatus.REGULAR_DONE,
            Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
            Attendance.ShiftStatus.PRE_OT_REST,
            Attendance.ShiftStatus.WORKING_OVERTIME,
        ]

        stale_records = Attendance.query.filter(
            Attendance.date < today,
            Attendance.shift_status.in_(stale_statuses),
        ).all()

        count = 0
        for record in stale_records:
            # Nếu chưa checkout ca chính, dùng 17:00 của ngày đó
            if not record.check_out and record.check_in:
                record.check_out = datetime.combine(record.date, REGULAR_END)
                raw_regular = AttendanceService.calculate_regular_hours_raw(
                    record.check_in, record.check_out
                )
                multiplier = AttendanceService._day_multiplier(
                    bool(record.is_holiday), bool(record.is_weekend)
                )
                record.regular_hours = (raw_regular * multiplier).quantize(Decimal("0.01"))

            # Nếu đang OT nhưng chưa checkout OT, dùng 22:00
            if record.overtime_check_in and not record.overtime_check_out:
                record.overtime_check_out = datetime.combine(record.date, OT_END)
                approved_ot = AttendanceService._get_approved_ot(record.employee_id, record.date)
                raw_ot = AttendanceService.calculate_overtime_hours_raw(
                    record.overtime_check_in, record.overtime_check_out
                )
                multiplier = (
                    Decimal(str(approved_ot.holiday_multiplier or 1))
                    if approved_ot
                    else AttendanceService._day_multiplier(
                        bool(record.is_holiday), bool(record.is_weekend)
                    )
                )
                record.overtime_hours = (raw_ot * multiplier).quantize(Decimal("0.01"))

            AttendanceService.finalize_attendance(record, finalize_status=True)
            count += 1

        if count > 0:
            db.session.commit()

        return count

    # ══════════════════════════════════════════════════════════════════════
    # BUILD PAYLOAD
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def build_attendance_payload(record: Attendance) -> dict | None:
        if not record:
            return None
        multiplier = float(
            AttendanceService._day_multiplier(
                bool(record.is_holiday), bool(record.is_weekend)
            )
        )
        # Tính raw (chia ngược) để FE hiển thị đúng nếu cần
        multiplier_d = Decimal(str(multiplier))
        raw_regular  = (
            (Decimal(str(record.regular_hours)) / multiplier_d).quantize(Decimal("0.01"))
            if multiplier_d > 1 and record.regular_hours
            else Decimal(str(record.regular_hours or 0))
        )
        raw_overtime = (
            (Decimal(str(record.overtime_hours)) / multiplier_d).quantize(Decimal("0.01"))
            if multiplier_d > 1 and record.overtime_hours
            else Decimal(str(record.overtime_hours or 0))
        )

        return {
            "date":               record.date.isoformat() if record.date else None,
            "check_in":           record.check_in.isoformat()           if record.check_in           else None,
            "check_out":          record.check_out.isoformat()          if record.check_out          else None,
            "overtime_check_in":  record.overtime_check_in.isoformat()  if record.overtime_check_in  else None,
            "overtime_check_out": record.overtime_check_out.isoformat() if record.overtime_check_out else None,
            # Đã nhân hệ số (dùng để tính lương)
            "regular_hours":      str(record.regular_hours  or 0),
            "overtime_hours":     str(record.overtime_hours or 0),
            "working_hours":      str(record.working_hours  or 0),
            # Raw — dùng để hiển thị "X giờ Y phút" cho nhân viên
            "regular_hours_raw":  str(raw_regular),
            "overtime_hours_raw": str(raw_overtime),
            "shift_status":       record.shift_status,
            "attendance_type":    record.attendance_type,
            "late_minutes":       record.late_minutes,
            "is_half_day":        record.is_half_day,
            "is_weekend":         record.is_weekend,
            "is_holiday":         record.is_holiday,
            "day_multiplier":     multiplier,
        }

    # ══════════════════════════════════════════════════════════════════════
    # QUERY HELPERS
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def get_today(employee_id: int, sim_time_str: str | None = None) -> Attendance | None:
        sim_time_str = sim_time_str or session.get("simulated_now")
        now_dt = AttendanceService.parse_time(sim_time_str)
        return Attendance.query.filter_by(
            employee_id=employee_id, date=now_dt.date()
        ).first()

    @staticmethod
    def get_history(
        employee_id: int,
        sim_time_str: str | None = None,
        limit: int = 10,
        month: int | None = None,
        year: int | None = None,
    ):
        from calendar import monthrange

        sim_time_str = sim_time_str or session.get("simulated_now")
        now_dt = AttendanceService.parse_time(sim_time_str)

        if not month or not year:
            return (
                Attendance.query.filter(
                    Attendance.employee_id == employee_id,
                    Attendance.date <= now_dt.date(),
                )
                .order_by(Attendance.date.desc())
                .limit(limit)
                .all()
            )

        if month < 1 or month > 12:
            raise ValidationError("Tháng không hợp lệ")

        last_day    = monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end   = date(year, month, last_day)
        effective_end = (
            month_end
            if (year, month) < (now_dt.year, now_dt.month)
            else min(month_end, now_dt.date())
        )

        if effective_end < month_start:
            return []

        attendance_rows = Attendance.query.filter(
            Attendance.employee_id == employee_id,
            Attendance.date >= month_start,
            Attendance.date <= effective_end,
        ).all()
        attendance_by_date = {row.date: row for row in attendance_rows}

        leave_rows = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "approved",
            LeaveRequest.is_deleted.is_(False),
            LeaveRequest.from_date <= effective_end,
            LeaveRequest.to_date >= month_start,
        ).all()
        leave_dates = set()
        for leave in leave_rows:
            start = max(leave.from_date, month_start)
            end   = min(leave.to_date, effective_end)
            cur   = start
            while cur <= end:
                leave_dates.add(cur)
                cur = cur.fromordinal(cur.toordinal() + 1)

        fixed_holidays = Holiday.query.filter(
            Holiday.is_recurring.is_(False),
            Holiday.date >= month_start,
            Holiday.date <= effective_end,
        ).all()
        recurring_holidays = Holiday.query.filter_by(is_recurring=True).all()
        holiday_dates = {h.date for h in fixed_holidays}
        for h in recurring_holidays:
            try:
                hd = date(year, month, h.date.day)
            except ValueError:
                continue
            if month_start <= hd <= effective_end:
                holiday_dates.add(hd)

        history = []
        current = effective_end
        while current >= month_start:
            if current in attendance_by_date:
                history.append(attendance_by_date[current])
            else:
                is_weekend = current.weekday() >= 5
                is_holiday = current in holiday_dates
                is_leave   = current in leave_dates

                if is_leave:
                    shift_status   = Attendance.ShiftStatus.LEAVE
                    attendance_type = Attendance.Type.LEAVE
                elif is_holiday:
                    shift_status   = Attendance.ShiftStatus.HOLIDAY_OFF
                    attendance_type = Attendance.Type.HOLIDAY
                elif is_weekend:
                    shift_status   = Attendance.ShiftStatus.WEEKEND_OFF
                    attendance_type = Attendance.Type.WEEKEND
                else:
                    shift_status   = Attendance.ShiftStatus.ABSENT
                    attendance_type = Attendance.Type.ABSENT

                history.append(SimpleNamespace(
                    id=None,
                    date=current,
                    check_in=None,
                    check_out=None,
                    regular_hours=Decimal("0.00"),
                    overtime_hours=Decimal("0.00"),
                    working_hours=Decimal("0.00"),
                    shift_status=shift_status,
                    normalized_shift_status=shift_status,
                    attendance_type=attendance_type,
                    is_weekend=is_weekend,
                    is_holiday=is_holiday,
                    late_minutes=0,
                    is_half_day=False,
                ))
            current = current.fromordinal(current.toordinal() - 1)

        return history

    @staticmethod
    def delete_attendance(employee_id: int, date_str: str) -> date | None:
        try:
            target_date = datetime.fromisoformat(date_str).date()
        except (TypeError, ValueError):
            raise ValidationError("Ngày không hợp lệ. Dùng định dạng YYYY-MM-DD")

        record = Attendance.query.filter_by(
            employee_id=employee_id, date=target_date
        ).first()
        if not record:
            raise ValidationError("Không tìm thấy dữ liệu chấm công trong ngày đã chọn")

        employee = Employee.query.get(employee_id)
        if employee and employee.user_id:
            notilist = Notification.query.filter(
                Notification.user_id == employee.user_id,
                Notification.is_deleted.is_(False),
                Notification.type.in_(["attendance", "overtime"]),
                db.func.date(Notification.created_at) == target_date,
            ).all()
            for n in notilist:
                n.is_deleted = True

        db.session.delete(record)
        db.session.commit()

        last = (
            Attendance.query.filter_by(employee_id=employee_id)
            .order_by(Attendance.date.desc())
            .first()
        )
        return last.date if last else None

    # ══════════════════════════════════════════════════════════════════════
    # NOTIFICATION CASCADE DELETE
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def delete_notification_cascade(notification_id: int, user_id: int) -> dict:
        """
        Xóa notification và cascade theo type:
        - type=overtime  → xóa linked OT request, reset overtime trên attendance
        - type=attendance → chỉ xóa notification
        """
        noti = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if not noti:
            raise ValidationError("Không tìm thấy thông báo")

        noti.is_deleted = True
        cascaded = []

        if noti.type == "overtime":
            # Tìm OT request liên quan theo ngày tạo thông báo
            target_date = noti.created_at.date() if noti.created_at else None
            if target_date:
                employee = Employee.query.filter_by(user_id=user_id).first()
                if employee:
                    ot_req = OvertimeRequest.query.filter(
                        OvertimeRequest.employee_id == employee.id,
                        OvertimeRequest.overtime_date == target_date,
                        OvertimeRequest.is_deleted.is_(False),
                    ).first()
                    if ot_req:
                        ot_req.is_deleted = True
                        cascaded.append(f"OT request #{ot_req.id}")

                        # Reset overtime fields trên attendance
                        att = Attendance.query.filter_by(
                            employee_id=employee.id, date=target_date
                        ).first()
                        if att:
                            att.overtime_hours     = Decimal("0.00")
                            att.overtime_check_in  = None
                            att.overtime_check_out = None
                            att.overtime_request_id = None
                            if att.shift_status in (
                                Attendance.ShiftStatus.WORKING_OVERTIME,
                                Attendance.ShiftStatus.PRE_OT_REST,
                                Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                            ):
                                att.set_shift_status(Attendance.ShiftStatus.COMPLETED)
                                AttendanceService.finalize_attendance(att, finalize_status=True)
                            cascaded.append(f"Attendance overtime reset ({target_date})")

        db.session.commit()
        return {"deleted": True, "cascaded": cascaded}

    # ══════════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def process_employee_action(
        employee_id: int, payload: dict, current_time: datetime
    ) -> dict:
        today = current_time.date()

        attendance = Attendance.query.filter_by(
            employee_id=employee_id, date=today
        ).first()

        if attendance and attendance.shift_status == Attendance.ShiftStatus.COMPLETED:
            return {
                "type":             "success",
                "action":           AttendanceService.ACTION_ALREADY_RECORDED,
                "attendance_state": attendance.shift_status,
                "message":          "Ngày công đã hoàn tất",
                "attendance":       AttendanceService.build_attendance_payload(attendance),
            }

        if not attendance or not attendance.check_in:
            return AttendanceService._handle_not_started(
                employee_id, payload, current_time
            )

        if attendance.check_in and not attendance.check_out:
            return AttendanceService._handle_working(
                attendance, employee_id, payload, current_time
            )

        return AttendanceService._handle_after_checkout(
            attendance, employee_id, payload, current_time
        )

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 1 — CHƯA CHECK-IN
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _handle_not_started(
        employee_id: int, payload: dict, current_time: datetime
    ) -> dict:
        offday_response = AttendanceService._handle_offday_logic(
            employee_id, payload, current_time.date()
        )
        if offday_response and not offday_response.get("pass_through"):
            return offday_response
        return AttendanceService._handle_checkin(
            employee_id, payload, current_time.isoformat()
        )

    @staticmethod
    def _handle_checkin(
        employee_id: int, payload: dict, sim_time_str: str
    ) -> dict:
        confirm_work = bool(payload.get("confirm_work_on_offday")) or bool(
            payload.get("overtime_confirmed")
        )
        result = AttendanceService.check_in(employee_id, sim_time_str, confirm_work)
        response_type = (
            "warning"
            if result.get("action") in {
                AttendanceService.ACTION_HOLIDAY_WORK_PROMPT,
                AttendanceService.ACTION_WEEKEND_WORK_PROMPT,
            }
            else "success"
        )
        return {"type": response_type, "status_code": 200, **result}

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 2 — ĐANG LÀM CA CHÍNH
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _handle_working(
        attendance: Attendance,
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:
        today       = current_time.date()
        end_of_day  = datetime.combine(today, REGULAR_END)
        lunch_start = datetime.combine(today, LUNCH_START)
        lunch_end   = datetime.combine(today, LUNCH_END)

        early_checkout_confirmed = bool(payload.get("early_checkout_confirmed"))

        # Giờ nghỉ trưa → block
        if lunch_start <= current_time <= lunch_end:
            return {
                "type":             "info",
                "action":           "lunch_break",
                "attendance_state": attendance.shift_status,
                "message":          "Đang trong giờ nghỉ trưa (12:00–13:00)",
            }

        # Đúng giờ tan ca hoặc muộn hơn → checkout bình thường
        if current_time >= end_of_day:
            return AttendanceService.check_out_regular(
                employee_id, current_time.isoformat(),
                early_checkout=False, current_time=current_time,
            )

        # Còn trước 17:00 → hỏi về sớm
        if not early_checkout_confirmed:
            early_minutes = int((end_of_day - current_time).total_seconds() // 60)
            return {
                "type":                 "warning",
                "action":               AttendanceService.ACTION_EARLY_CHECKOUT_PROMPT,
                "attendance_state":     attendance.shift_status,
                "message":              f"Bạn có muốn tan ca sớm không? (sớm {early_minutes} phút)",
                "requires_confirmation": True,
                "flags":                {"early_minutes": early_minutes},
            }

        return AttendanceService.check_out_regular(
            employee_id, current_time.isoformat(),
            early_checkout=True, current_time=current_time,
        )

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 3 — SAU CHECK-OUT CA CHÍNH
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _handle_after_checkout(
        attendance: Attendance,
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:
        sim_time        = current_time.isoformat()
        overtime_decision = str(payload.get("overtime_decision") or "").lower()

        # ── REGULAR_DONE ──────────────────────────────────────────────────
        if attendance.shift_status == Attendance.ShiftStatus.REGULAR_DONE:
            # Về sớm → auto complete, không hỏi OT
            if attendance.check_out and attendance.check_out.time() < REGULAR_END:
                attendance.set_shift_status(Attendance.ShiftStatus.COMPLETED)
                AttendanceService.finalize_attendance(attendance, finalize_status=True)
                db.session.commit()
                return {
                    "type":             "success",
                    "action":           AttendanceService.ACTION_COMPLETE_WITHOUT_OT,
                    "attendance_state": attendance.shift_status,
                    "message":          "✅ Đã hoàn thành ngày làm việc.",
                    "attendance":       AttendanceService.build_attendance_payload(attendance),
                }

            if overtime_decision not in {"yes", "no"}:
                return {
                    "type":                          "warning",
                    "action":                        AttendanceService.ACTION_OFFER_OVERTIME,
                    "message":                       "Bạn có muốn đăng ký tăng ca không?",
                    "attendance_state":              attendance.shift_status,
                    "next_event":                    "offer_overtime",
                    "requires_overtime_decision":    True,
                }

            if overtime_decision == "no":
                attendance.set_shift_status(Attendance.ShiftStatus.COMPLETED)
                AttendanceService.finalize_attendance(attendance, finalize_status=True)
                db.session.commit()
                return {
                    "type":             "success",
                    "action":           AttendanceService.ACTION_COMPLETE_WITHOUT_OT,
                    "attendance_state": attendance.shift_status,
                    "message":          "✅ Đã hoàn thành ngày làm việc.",
                    "attendance":       AttendanceService.build_attendance_payload(attendance),
                }

            return AttendanceService._create_ot_request_pending(
                attendance, employee_id, current_time
            )

        # ── REGULAR_DONE_PENDING_OT_DECISION ──────────────────────────────
        if attendance.shift_status == Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION:
            approved_ot = AttendanceService._get_approved_ot(employee_id, current_time.date())
            if approved_ot:
                # OT approved: chuyển sang pre_ot_rest, chỉ cho check-in OT khi tới 19:00
                attendance.set_shift_status(Attendance.ShiftStatus.PRE_OT_REST)
                db.session.commit()
                return {
                    "type":             "info",
                    "action":           "ot_approved_wait",
                    "attendance_state": attendance.shift_status,
                    "overtime_status":  "APPROVED",
                    "message":          "✅ Yêu cầu tăng ca đã được phê duyệt.",
                    "attendance":       AttendanceService.build_attendance_payload(attendance),
                }

            pending_ot = OvertimeRequest.query.filter(
                OvertimeRequest.employee_id == employee_id,
                OvertimeRequest.overtime_date == current_time.date(),
                OvertimeRequest.is_deleted.is_(False),
                OvertimeRequest.status.in_(["pending", "pending_hr", "pending_admin"]),
            ).first()
            if pending_ot:
                return {
                    "type":             "info",
                    "action":           "ot_pending_approval",
                    "attendance_state": attendance.shift_status,
                    "overtime_status":  "PENDING",
                    "message":          "⏳ ĐANG CHỜ DUYỆT TĂNG CA",
                }

            # OT bị reject → complete
            attendance.set_shift_status(Attendance.ShiftStatus.COMPLETED)
            AttendanceService.finalize_attendance(attendance, finalize_status=True)
            db.session.commit()
            return {
                "type":             "warning",
                "action":           AttendanceService.ACTION_COMPLETE_WITHOUT_OT,
                "attendance_state": attendance.shift_status,
                "message":          "✅ Đã hoàn thành ngày làm việc.",
                "attendance":       AttendanceService.build_attendance_payload(attendance),
            }

        # ── PRE_OT_REST ────────────────────────────────────────────────────
        if attendance.shift_status == Attendance.ShiftStatus.PRE_OT_REST:
            approved_ot = AttendanceService._get_approved_ot(employee_id, current_time.date())
            if not approved_ot:
                attendance.set_shift_status(Attendance.ShiftStatus.COMPLETED)
                AttendanceService.finalize_attendance(attendance, finalize_status=True)
                db.session.commit()
                return {
                    "type":             "warning",
                    "action":           AttendanceService.ACTION_COMPLETE_WITHOUT_OT,
                    "attendance_state": attendance.shift_status,
                    "message":          "✅ Đã hoàn thành ngày làm việc.",
                    "attendance":       AttendanceService.build_attendance_payload(attendance),
                }

            # Đã check-in OT rồi nhưng state vẫn pre_ot_rest → cập nhật state
            if attendance.overtime_check_in:
                if current_time.time() >= OT_CHECKIN_OPEN:
                    attendance.set_shift_status(Attendance.ShiftStatus.WORKING_OVERTIME)
                    db.session.commit()
                    return {
                        "type":             "info",
                        "action":           "pre_ot_rest",
                        "attendance_state": Attendance.ShiftStatus.WORKING_OVERTIME,
                        "message":          "Đang tăng ca.",
                        "attendance":       AttendanceService.build_attendance_payload(attendance),
                    }
                return {
                    "type":             "info",
                    "action":           "pre_ot_rest",
                    "attendance_state": attendance.shift_status,
                    "message":          "Đã xác thực tăng ca. Công OT bắt đầu tính từ 19:00.",
                    "attendance":       AttendanceService.build_attendance_payload(attendance),
                }

            # Chưa check-in OT: chỉ cho scan từ 19:00 trở đi
            if current_time.time() < OT_CHECKIN_OPEN:
                return {
                    "type":             "info",
                    "action":           "pre_ot_rest",
                    "attendance_state": attendance.shift_status,
                    "overtime_status":  "APPROVED",
                    "message":          "Đang nghỉ trước tăng ca. Đến 19:00 sẽ mở xác thực check-in OT.",
                    "attendance":       AttendanceService.build_attendance_payload(attendance),
                }

            return AttendanceService.check_in_overtime(employee_id, sim_time)

        # ── WORKING_OVERTIME ──────────────────────────────────────────────
        if attendance.shift_status == Attendance.ShiftStatus.WORKING_OVERTIME:
            if not attendance.overtime_check_out:
                return AttendanceService.check_out_overtime(employee_id, sim_time)

        # ── COMPLETED ─────────────────────────────────────────────────────
        if attendance.shift_status == Attendance.ShiftStatus.COMPLETED:
            return {
                "type":             "success",
                "action":           AttendanceService.ACTION_ALREADY_RECORDED,
                "attendance_state": attendance.shift_status,
                "message":          "Ngày công đã hoàn tất.",
                "attendance":       AttendanceService.build_attendance_payload(attendance),
            }

        return {
            "type":             "info",
            "action":           AttendanceService.ACTION_ALREADY_RECORDED,
            "attendance_state": attendance.shift_status,
            "message":          "Trạng thái: " + str(attendance.shift_status),
            "attendance":       AttendanceService.build_attendance_payload(attendance),
        }

    # ══════════════════════════════════════════════════════════════════════
    # OT REQUEST CREATION
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _create_ot_request_pending(
        attendance: Attendance, employee_id: int, current_time: datetime
    ) -> dict:
        today = current_time.date()
        existing = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == today,
            OvertimeRequest.is_deleted.is_(False),
        ).first()

        if not existing:
            is_holiday  = AttendanceService._is_holiday(today)
            is_weekend  = today.weekday() >= 5
            multiplier  = AttendanceService._day_multiplier(is_holiday, is_weekend)
            ot_req = OvertimeRequest(
                employee_id=employee_id,
                overtime_date=today,
                status="pending",
                requested_hours=Decimal("3.00"),
                overtime_hours=Decimal("3.00"),
                is_holiday_ot=is_holiday,
                holiday_multiplier=multiplier,
                request_type="after_shift",
                reason="Đăng ký tăng ca sau giờ hành chính",
            )
            db.session.add(ot_req)

        attendance.set_shift_status(Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION)
        db.session.commit()

        return {
            "type":             "success",
            "action":           AttendanceService.ACTION_OVERTIME_REQUEST_CREATED,
            "attendance_state": attendance.shift_status,
            "overtime_status":  "PENDING",
            "message":          "Đã gửi yêu cầu tăng ca. Vui lòng chờ phê duyệt.",
            "attendance":       AttendanceService.build_attendance_payload(attendance),
        }

    @staticmethod
    def _get_approved_ot(employee_id: int, target_date: date) -> OvertimeRequest | None:
        return OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == target_date,
            OvertimeRequest.is_deleted.is_(False),
            OvertimeRequest.status == "approved",
        ).first()

    # ══════════════════════════════════════════════════════════════════════
    # OT APPROVAL / REJECTION (gọi từ HR/Admin routes)
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def handle_ot_approved(ot_request: OvertimeRequest) -> None:
        """
        Gọi sau khi HR/Admin approve OT request.
        - Chuyển attendance → PRE_OT_REST
        - Tạo notification cho employee
        """
        attendance = Attendance.query.filter_by(
            employee_id=ot_request.employee_id,
            date=ot_request.overtime_date,
        ).first()
        if attendance and attendance.shift_status in (
            Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
            Attendance.ShiftStatus.REGULAR_DONE,
        ):
            attendance.set_shift_status(Attendance.ShiftStatus.PRE_OT_REST)
            db.session.flush()

        # Tạo notification cho employee
        employee = Employee.query.get(ot_request.employee_id)
        if employee and employee.user_id:
            db.session.add(Notification(
                user_id=employee.user_id,
                title="Yêu cầu tăng ca đã được duyệt",
                content=(
                    f"Yêu cầu tăng ca ngày "
                    f"{ot_request.overtime_date.strftime('%d/%m/%Y')} "
                    f"đã được phê duyệt. Bạn có thể xác thực để bắt đầu tăng ca."
                ),
                type="overtime",
                link="/employee/attendance",
            ))

    @staticmethod
    def handle_ot_rejected(ot_request: OvertimeRequest, reason: str = "") -> None:
        """
        Gọi sau khi HR/Admin reject OT request.
        - Chuyển attendance → COMPLETED
        - Tạo notification cho employee
        """
        attendance = Attendance.query.filter_by(
            employee_id=ot_request.employee_id,
            date=ot_request.overtime_date,
        ).first()
        if attendance and attendance.shift_status in (
            Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
            Attendance.ShiftStatus.REGULAR_DONE,
            Attendance.ShiftStatus.PRE_OT_REST,
        ):
            AttendanceService.finalize_attendance(attendance, finalize_status=True)
            db.session.flush()

        # Tạo notification cho employee
        employee = Employee.query.get(ot_request.employee_id)
        if employee and employee.user_id:
            reason_str = f" Lý do: {reason}" if reason else ""
            db.session.add(Notification(
                user_id=employee.user_id,
                title="Yêu cầu tăng ca bị từ chối",
                content=(
                    f"Yêu cầu tăng ca ngày "
                    f"{ot_request.overtime_date.strftime('%d/%m/%Y')} "
                    f"đã bị từ chối.{reason_str}"
                ),
                type="overtime",
                link="/employee/attendance",
            ))

    # ══════════════════════════════════════════════════════════════════════
    # OFFDAY LOGIC
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _handle_offday_logic(employee_id: int, payload: dict, today: date) -> dict:
        is_holiday = AttendanceService._is_holiday(today)
        is_weekend = today.weekday() >= 5

        if bool(payload.get("decline_offday_work")):
            if is_holiday or is_weekend:
                record = AttendanceService.get_or_create_today(
                    employee_id=employee_id,
                    now_dt=datetime.combine(today, time.min),
                )
                record.is_holiday = is_holiday
                record.is_weekend = is_weekend
                record.set_attendance_type(
                    Attendance.Type.HOLIDAY if is_holiday else Attendance.Type.WEEKEND
                )
                record.set_shift_status(
                    Attendance.ShiftStatus.HOLIDAY_OFF if is_holiday
                    else Attendance.ShiftStatus.WEEKEND_OFF
                )
                db.session.commit()
                return {
                    "type":             "info",
                    "status_code":      200,
                    "action":           (
                        AttendanceService.ACTION_HOLIDAY_OFF if is_holiday
                        else AttendanceService.ACTION_WEEKEND_OFF
                    ),
                    "attendance_state": record.shift_status,
                    "message":          (
                        "Đã ghi nhận nghỉ lễ hôm nay." if is_holiday
                        else "Đã ghi nhận nghỉ cuối tuần hôm nay."
                    ),
                    "attendance":       AttendanceService.build_attendance_payload(record),
                }

        return {"pass_through": True}

    # ══════════════════════════════════════════════════════════════════════
    # CHECK-IN CA CHÍNH
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def check_in(
        employee_id: int,
        sim_time_str: str | None,
        confirm_work_on_offday: bool = False,
    ) -> dict:
        employee = Employee.query.get(employee_id)
        if employee and employee.is_attendance_required is False:
            raise ValidationError("Nhân sự này không áp dụng chấm công bắt buộc.")

        now_dt = AttendanceService.parse_time(sim_time_str)
        record = AttendanceService.get_or_create_today(employee_id, now_dt)

        if record.check_in:
            raise ValidationError("Bạn đã check-in hôm nay.")

        is_weekend = now_dt.weekday() >= 5
        is_holiday = AttendanceService._is_holiday(now_dt.date())

        if (is_weekend or is_holiday) and not confirm_work_on_offday:
            return {
                "action":               (
                    AttendanceService.ACTION_HOLIDAY_WORK_PROMPT if is_holiday
                    else AttendanceService.ACTION_WEEKEND_WORK_PROMPT
                ),
                "requires_confirmation": True,
                "is_weekend":            is_weekend,
                "is_holiday":            is_holiday,
                "message":               (
                    "Hôm nay là ngày nghỉ lễ. Bạn có muốn đi làm ngày lễ không?"
                    if is_holiday
                    else "Hôm nay là ngày nghỉ cuối tuần. Bạn có muốn đi làm không?"
                ),
            }

        record.is_weekend = is_weekend
        record.is_holiday = is_holiday
        record.set_attendance_type(
            AttendanceService._resolve_attendance_type(is_weekend, is_holiday, False)
        )
        record.check_in = now_dt
        record.set_shift_status(Attendance.ShiftStatus.WORKING_REGULAR)

        # ── Tính đi muộn ──────────────────────────────────────────────────
        # late_minutes = phút sau 8:00 (nếu đến trước 8:00 thì = 0)
        shift_start_dt = datetime.combine(now_dt.date(), REGULAR_START)
        late_minutes = max(
            0,
            int((now_dt - shift_start_dt).total_seconds() / 60),
        )
        record.late_minutes = late_minutes
        record.is_half_day  = late_minutes >= 60  # is_half_day là flag hiển thị

        if record.is_half_day:
            status_name = "HALF_DAY"
        elif late_minutes > 0:
            status_name = "LATE"
        else:
            status_name = "PRESENT"
        db_status = AttendanceService.get_status(status_name)
        if db_status:
            record.status_id = db_status.id

        if not record.is_weekend and not record.is_holiday and record.is_half_day:
            record.set_attendance_type(Attendance.Type.ABNORMAL)

        db.session.commit()

        msg        = f"Check-in thành công lúc {now_dt.strftime('%H:%M:%S')}"
        resp_type  = "success"
        multiplier = AttendanceService._day_multiplier(is_holiday, is_weekend)
        if is_holiday:
            msg += f" (Ngày lễ — công sẽ nhân x{int(multiplier)})"
        elif is_weekend and multiplier > 1:
            msg += f" (Cuối tuần — công sẽ nhân x{int(multiplier)})"
        if record.is_half_day:
            msg      += f". Đi muộn {late_minutes} phút — tính nửa ngày công."
            resp_type = "warning"
        elif late_minutes > 0:
            msg      += f". Đi muộn {late_minutes} phút."
            resp_type = "warning"

        return {
            "action":           AttendanceService.ACTION_CHECK_IN,
            "type":             resp_type,
            "message":          msg,
            "attendance_state": record.shift_status,
            "attendance":       AttendanceService.build_attendance_payload(record),
        }

    # ══════════════════════════════════════════════════════════════════════
    # CHECK-OUT CA CHÍNH
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def check_out_regular(
        employee_id: int,
        sim_time_str: str | None,
        early_checkout: bool = False,
        current_time: datetime | None = None,
    ) -> dict:
        now_dt = AttendanceService.parse_time(sim_time_str)
        record = Attendance.query.filter_by(
            employee_id=employee_id, date=now_dt.date()
        ).first()

        if not record or not record.check_in:
            raise ValidationError("Bạn chưa check-in.")
        if record.check_out:
            raise ValidationError("Bạn đã check-out ca chính.")

        record.check_out = now_dt

        # Tính công raw (chưa nhân hệ số) — dùng effective clamp
        raw_regular = AttendanceService.calculate_regular_hours_raw(
            record.check_in, record.check_out
        )

        # Nhân hệ số và lưu
        multiplier          = AttendanceService._day_multiplier(
            bool(record.is_holiday), bool(record.is_weekend)
        )
        regular_hours_raw = raw_regular
        if record.is_half_day and not record.is_weekend and not record.is_holiday:
            # Rule mới: đi muộn >60p thì lấy 1/2 công thực tế đã làm trong giờ hành chính.
            regular_hours_raw = (raw_regular * Decimal("0.5")).quantize(Decimal("0.0001"))

        record.regular_hours = (regular_hours_raw * multiplier).quantize(Decimal("0.01"))

        record.set_shift_status(Attendance.ShiftStatus.REGULAR_DONE)
        AttendanceService.finalize_attendance(record, finalize_status=False)
        db.session.commit()

        multiplier_label = f" (x{int(multiplier)})" if multiplier > 1 else ""

        if early_checkout:
            early_minutes = 0
            if current_time:
                end_of_day    = datetime.combine(current_time.date(), REGULAR_END)
                early_minutes = max(0, int((end_of_day - current_time).total_seconds() // 60))
            record.set_shift_status(Attendance.ShiftStatus.COMPLETED)
            AttendanceService.finalize_attendance(record, finalize_status=True)
            db.session.commit()
            return {
                "type":                          "warning",
                "action":                        AttendanceService.ACTION_CHECK_OUT,
                "message":                       f"Check-out lúc {(current_time or now_dt).strftime('%H:%M:%S')}. Về sớm {early_minutes} phút.",
                "attendance_state":              record.shift_status,
                "status_key":                    "early_leave",
                "regular_hours":                 str(record.regular_hours),
                "overtime_hours":                str(record.overtime_hours or 0),
                "working_hours":                 str(record.working_hours),
                "attendance":                    AttendanceService.build_attendance_payload(record),
                "next_event":                    None,
                "requires_overtime_decision":    False,
            }

        return {
            "type":                          "success",
            "action":                        AttendanceService.ACTION_CHECK_OUT,
            "message":                       (
                f"Check-out ca chính thành công. Công thường: {record.regular_hours}h{multiplier_label}" +
                (" (áp dụng nửa ngày công do đi muộn quá 60 phút)" if record.is_half_day and not record.is_weekend and not record.is_holiday else "")
            ),
            "attendance_state":              record.shift_status,
            "regular_hours":                 str(record.regular_hours),
            "overtime_hours":                str(record.overtime_hours or 0),
            "working_hours":                 str(record.working_hours),
            "attendance":                    AttendanceService.build_attendance_payload(record),
            "next_event":                    "offer_overtime",
            "requires_overtime_decision":    True,
        }

    # ══════════════════════════════════════════════════════════════════════
    # CHECK-IN OT
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def check_in_overtime(employee_id: int, sim_time_str: str | None) -> dict:
        now_dt = AttendanceService.parse_time(sim_time_str)
        record = Attendance.query.filter_by(
            employee_id=employee_id, date=now_dt.date()
        ).first()

        if not record or not record.check_out:
            raise ValidationError("Bạn phải hoàn tất ca chính trước khi OT.")

        approved_ot = AttendanceService._get_approved_ot(employee_id, now_dt.date())
        if not approved_ot:
            raise ValidationError("❌ Yêu cầu tăng ca chưa được phê duyệt.")

        if record.overtime_check_in:
            raise ValidationError("Bạn đã check-in OT rồi.")

        record.overtime_check_in    = now_dt
        record.overtime_status      = "APPROVED"
        record.overtime_request_id  = approved_ot.id

        # Nếu check-in trước 19:00 → PRE_OT_REST (chờ đến 19:00, công clamp từ 19:00)
        if now_dt.time() < OT_CHECKIN_OPEN:
            record.set_shift_status(Attendance.ShiftStatus.PRE_OT_REST)
            msg = (
                f"Đã xác thực tăng ca lúc {now_dt.strftime('%H:%M:%S')}. "
                f"Trạng thái: Nghỉ ngơi trước tăng ca — công OT bắt đầu tính từ 19:00."
            )
        else:
            record.set_shift_status(Attendance.ShiftStatus.WORKING_OVERTIME)
            msg = "✅ Check-in tăng ca thành công."

        db.session.commit()

        return {
            "type":             "success",
            "action":           AttendanceService.ACTION_CHECK_IN_OT,
            "message":          msg,
            "attendance_state": record.shift_status,
            "overtime_status":  "APPROVED",
            "attendance":       AttendanceService.build_attendance_payload(record),
        }

    # ══════════════════════════════════════════════════════════════════════
    # CHECK-OUT OT
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def check_out_overtime(employee_id: int, sim_time_str: str | None) -> dict:
        now_dt = AttendanceService.parse_time(sim_time_str)
        record = Attendance.query.filter_by(
            employee_id=employee_id, date=now_dt.date()
        ).first()

        if not record or not record.overtime_check_in:
            raise ValidationError("❌ Yêu cầu tăng ca chưa được phê duyệt.")
        if record.overtime_check_out:
            raise ValidationError("Bạn đã check-out OT rồi.")

        ot_end_dt             = datetime.combine(now_dt.date(), OT_END)
        record.overtime_check_out = min(now_dt, ot_end_dt)

        approved_ot = AttendanceService._get_approved_ot(employee_id, now_dt.date())
        raw_ot      = AttendanceService.calculate_overtime_hours_raw(
            record.overtime_check_in, record.overtime_check_out
        )
        multiplier = (
            Decimal(str(approved_ot.holiday_multiplier or 1))
            if approved_ot
            else AttendanceService._day_multiplier(
                bool(record.is_holiday), bool(record.is_weekend)
            )
        )
        record.overtime_hours = (raw_ot * multiplier).quantize(Decimal("0.01"))

        AttendanceService.finalize_attendance(record, finalize_status=True)
        db.session.commit()

        multiplier_label = f" (x{int(multiplier)})" if multiplier > 1 else ""
        return {
            "type":               "success",
            "action":             AttendanceService.ACTION_CHECK_OUT_OT,
            "message":            "✅ Đã hoàn thành tăng ca.",
            "attendance_state":   record.shift_status,
            "regular_hours":      str(record.regular_hours),
            "overtime_hours":     str(record.overtime_hours),
            "working_hours":      str(record.working_hours),
            "overtime_check_in":  record.overtime_check_in.isoformat()  if record.overtime_check_in  else None,
            "overtime_check_out": record.overtime_check_out.isoformat() if record.overtime_check_out else None,
            "attendance":         AttendanceService.build_attendance_payload(record),
        }