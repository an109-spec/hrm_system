from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Attendance,
    AttendanceStatus,
    Employee,
    Holiday,
    OvertimeRequest,
    LeaveRequest,
)
from app.common.exceptions import ValidationError

from app.modules.attendance.constants import (
    REGULAR_START, 
    REGULAR_END,
    LUNCH_START, 
    LUNCH_END, 
    OT_CHECKIN_OPEN, 
    OT_END_LIMIT, 
    MIN_OT_HOURS, 
    GRACE_PERIOD_MINUTES, 
    HALF_DAY_THRESHOLD, 
    REGULAR_DAY_RATE, 
    WEEKEND_RATE, 
    HOLIDAY_RATE, 
    OT_NORMAL_DAY_RATE, 
    OT_WEEKEND_RATE, 
    OT_HOLIDAY_RATE,
)

from app.modules.attendance.dto import AttendanceStateDTO
from app.common.constants import AttendanceConstants

class AttendanceService:
    # =========================
    # ACTIONS (giữ nguyên)
    # =========================
    ACTION_CHECK_IN = "check_in"
    ACTION_CHECK_OUT = "check_out"
    ACTION_CHECK_IN_OT = "check_in_overtime"
    ACTION_CHECK_OUT_OT = "check_out_overtime"
    ACTION_HOLIDAY_WORK_PROMPT = "holiday_work_prompt"
    ACTION_WEEKEND_WORK_PROMPT = "weekend_work_prompt"
    ACTION_EARLY_CHECKOUT_PROMPT = "early_checkout_prompt"
    ACTION_OFFER_OVERTIME = "offer_overtime"
    ACTION_ALREADY_RECORDED = "already_recorded"
    ACTION_OVERTIME_REQUEST_CREATED = "overtime_request_created"
    ACTION_COMPLETE_WITHOUT_OT = "complete_without_overtime"
    ACTION_HOLIDAY_OFF = "holiday_off"
    ACTION_WEEKEND_OFF = "weekend_off"
    ACTION_OVERTIME_DECISION_RECORDED = "overtime_decision_recorded"

    # =========================
    # STATE MACHINE
    # =========================
    @staticmethod
    def compute_attendance_state(
        now: datetime,
        attendance: Attendance | None,
        ot_request: OvertimeRequest | None = None,
    ) -> AttendanceStateDTO:

        current_time = now.time()

        # =========================================================
        # NOT EXISTS
        # =========================================================
        if not attendance:
            return AttendanceStateDTO(
                state=Attendance.ShiftStatus.NOT_STARTED,
                button_enabled=True,
                button_text="🔳 XÁC THỰC CHẤM CÔNG",
                can_scan=True,
                message="Bạn chưa bắt đầu ngày làm việc.",
            )

        raw_state = Attendance.ShiftStatus.normalize(attendance.shift_status)

        # =========================================================
        # FINAL STATES
        # =========================================================
        if raw_state == Attendance.ShiftStatus.COMPLETED:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="✅ ĐÃ HOÀN THÀNH NGÀY CÔNG",
                can_scan=False,
                message="Ngày công đã hoàn tất.",
            )

        if raw_state == Attendance.ShiftStatus.HOLIDAY_OFF:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="🎉 NGHỈ LỄ",
                can_scan=False,
                message="Hôm nay là ngày nghỉ lễ.",
            )

        if raw_state == Attendance.ShiftStatus.WEEKEND_OFF:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="🛌 NGHỈ CUỐI TUẦN",
                can_scan=False,
                message="Hôm nay là ngày nghỉ cuối tuần.",
            )

        if raw_state == Attendance.ShiftStatus.LEAVE:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="📋 NGHỈ PHÉP",
                can_scan=False,
                message="Bạn đang nghỉ phép.",
            )

        if raw_state == Attendance.ShiftStatus.ABSENT:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="❌ VẮNG MẶT",
                can_scan=False,
                message="Bạn bị ghi nhận vắng mặt.",
            )

        # =========================================================
        # NOT STARTED
        # =========================================================
        if raw_state == Attendance.ShiftStatus.NOT_STARTED:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=True,
                button_text="🔳 XÁC THỰC CHẤM CÔNG",
                can_scan=True,
                message="Vui lòng check-in để bắt đầu.",
            )

        # =========================================================
        # WORKING REGULAR
        # =========================================================
        if raw_state == Attendance.ShiftStatus.WORKING_REGULAR:

            if LUNCH_START <= current_time < LUNCH_END:
                return AttendanceStateDTO(
                    state="lunch_break",
                    button_enabled=False,
                    button_text="🍽️ NGHỈ TRƯA",
                    can_scan=False,
                    message="Đang nghỉ trưa.",
                )

            if current_time < REGULAR_END:
                return AttendanceStateDTO(
                    state=raw_state,
                    button_enabled=True,
                    button_text="🔳 ĐANG LÀM VIỆC",
                    can_scan=True,
                    message="Đang trong ca làm việc.",
                )

            return AttendanceStateDTO(
                state=Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED,
                button_enabled=True,
                button_text="🔳 XÁC NHẬN CHECKOUT",
                can_scan=True,
                message="Hết giờ làm, vui lòng checkout.",
            )

        # =========================================================
        # CHECKOUT REQUIRED
        # =========================================================
        if raw_state == Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=True,
                button_text="🔳 CHECKOUT CA CHÍNH",
                can_scan=True,
                message="Bạn chưa checkout.",
            )

        # =========================================================
        # DONE REGULAR
        # =========================================================
        if raw_state == Attendance.ShiftStatus.REGULAR_DONE:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=True,
                button_text="🕒 ĐĂNG KÝ TĂNG CA",
                can_scan=False,
                message="Đã xong ca chính.",
            )

        # =========================================================
        # OT PENDING
        # =========================================================
        if raw_state == Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION:

            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="⏳ CHỜ DUYỆT OT",
                can_scan=False,
                overtime_status=(ot_request.status.upper() if ot_request else "PENDING"),
                message="Đang chờ duyệt tăng ca.",
            )

        # =========================================================
        # PRE OT REST
        # =========================================================
        if raw_state == Attendance.ShiftStatus.PRE_OT_REST:

            if current_time < OT_CHECKIN_OPEN:
                return AttendanceStateDTO(
                    state=raw_state,
                    button_enabled=False,
                    button_text="⏳ CHỜ OT",
                    can_scan=False,
                    overtime_status="APPROVED",
                    message="Chưa đến giờ OT.",
                )

            return AttendanceStateDTO(
                state=Attendance.ShiftStatus.OT_CHECKIN_REQUIRED,
                button_enabled=True,
                button_text="🔳 CHECKIN OT",
                can_scan=True,
                overtime_status="APPROVED",
                message="Đến giờ OT.",
            )

        # =========================================================
        # OT WORKING
        # =========================================================
        if raw_state == Attendance.ShiftStatus.WORKING_OVERTIME:

            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=True,
                button_text="🔳 KẾT THÚC OT",
                can_scan=True,
                overtime_status="APPROVED",
                message="Đang làm OT.",
            )

        # =========================================================
        # FALLBACK
        # =========================================================
        return AttendanceStateDTO(
            state="unknown",
            button_enabled=False,
            button_text="⚠️ UNKNOWN",
            can_scan=False,
            message=f"Invalid state: {raw_state}",
        )

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
        today = now_dt.date()

        # =========================
        # CHECK EXISTING
        # =========================
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=today
        ).first()

        if record:
            return record

        # =========================
        # VALIDATE EMPLOYEE
        # =========================
        employee = Employee.query.get(employee_id)
        if not employee:
            raise ValidationError("Nhân viên không tồn tại")

        if not employee.is_attendance_required:
            raise ValidationError("Nhân viên không thuộc đối tượng chấm công")

        from app.common.constants import WorkingStatus

        if employee.working_status == WorkingStatus.RESIGNED:
            raise ValidationError("Nhân viên không còn hoạt động")

        # =========================
        # TIME FLAGS
        # =========================
        today = now_dt.date()

        is_weekend = today.weekday() >= 5
        is_holiday = Holiday.query.filter_by(date=today).first() is not None

        leave_request = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "approved",
            LeaveRequest.from_date <= today,
            LeaveRequest.to_date >= today,
        ).first()

        # =========================
        # PRIORITY RULE (IMPORTANT)
        # leave > holiday > weekend > normal
        # =========================
        if leave_request:
            shift_status = Attendance.ShiftStatus.LEAVE
            attendance_type = Attendance.Type.LEAVE_APPROVED

        elif is_holiday:
            shift_status = Attendance.ShiftStatus.HOLIDAY_OFF
            attendance_type = Attendance.Type.HOLIDAY

        elif is_weekend:
            shift_status = Attendance.ShiftStatus.WEEKEND_OFF
            attendance_type = Attendance.Type.WEEKEND

        else:
            shift_status = Attendance.ShiftStatus.NOT_STARTED
            attendance_type = Attendance.Type.NORMAL

        # =========================
        # CREATE RECORD
        # =========================
        record = Attendance(
            employee_id=employee_id,
            date=today,
            working_hours=Decimal("0.00"),
            regular_hours=Decimal("0.00"),
            overtime_hours=Decimal("0.00"),
            is_half_day=False,
            late_minutes=0,
            is_weekend=is_weekend,
            is_holiday=is_holiday,
        )

        record.set_shift_status(shift_status)
        record.set_attendance_type(attendance_type)

        db.session.add(record)

        # =========================
        # SAFE COMMIT
        # =========================
        try:
            db.session.commit()

        except IntegrityError:
            db.session.rollback()
            return Attendance.query.filter_by(
                employee_id=employee_id,
                date=today
            ).first()

        return record

    @staticmethod
    def normalize_status(status_name: str | None) -> str | None:
        if not status_name:
            return None

        normalized = AttendanceConstants.normalize(status_name)

        if not AttendanceConstants.is_valid(normalized):
            return None

        return normalized
    @staticmethod
    def get_status(status_name: str | None) -> AttendanceStatus | None:
        normalized = AttendanceService.normalize_status(status_name)

        if not normalized:
            return None

        return AttendanceStatus.query.filter_by(
            status_name=normalized
        ).first()
    @staticmethod
    def _get_holiday(target_date: date) -> Holiday | None:
        holiday = Holiday.query.filter(
            Holiday.date == target_date
        ).first()

        if holiday:
            return holiday
        recurring_holiday = (
            Holiday.query
            .filter(Holiday.is_recurring.is_(True))
            .filter(
                db.extract("month", Holiday.date)
                == target_date.month
            )
            .filter(
                db.extract("day", Holiday.date)
                == target_date.day
            )
            .first()
        )
        return recurring_holiday
    @staticmethod
    def _is_holiday(target_date: date) -> bool:
        return (
            AttendanceService._get_holiday(target_date)
            is not None
        )
    
    @staticmethod
    def _get_day_rate(
        attendance_type: str | None
    ) -> Decimal:

        normalized_type = Attendance.Type.normalize(
            attendance_type
        )
        if normalized_type == Attendance.Type.NORMAL:
            return REGULAR_DAY_RATE
        if normalized_type == Attendance.Type.WEEKEND:
            return WEEKEND_RATE
        if normalized_type == Attendance.Type.HOLIDAY:
            return HOLIDAY_RATE
        if normalized_type == Attendance.Type.LEAVE_APPROVED:
            return REGULAR_DAY_RATE
        if normalized_type in {
            Attendance.Type.ABSENT,
            Attendance.Type.ABSENT_UNEXCUSED,
            Attendance.Type.ABNORMAL_REJECTED,
        }:
            return Decimal("0.0")
        return REGULAR_DAY_RATE

    @staticmethod
    def _resolve_attendance_type(
        *,
        is_holiday: bool = False,
        is_weekend: bool = False,
        is_leave: bool = False,
        is_absent: bool = False,
        is_abnormal: bool = False,
    ) -> str:

        if is_leave:
            return Attendance.Type.LEAVE_APPROVED

        if is_absent:
            return Attendance.Type.ABSENT

        if is_abnormal:
            return Attendance.Type.ABNORMAL

        if is_holiday:
            return Attendance.Type.HOLIDAY

        if is_weekend:
            return Attendance.Type.WEEKEND

        return Attendance.Type.NORMAL

    @staticmethod
    def calculate_regular_work_units(
        attendance: Attendance
    ) -> WorkUnitResult:

        if not attendance.check_in or not attendance.check_out:
            return WorkUnitResult(
                units=Decimal("0.00"),
                is_half_day=False,
                worked_hours=Decimal("0.00"),
            )

        normalized_type = Attendance.Type.normalize(
            attendance.attendance_type
        )

        if normalized_type in {
            Attendance.Type.ABSENT,
            Attendance.Type.ABSENT_UNEXCUSED,
            Attendance.Type.ABNORMAL_REJECTED,
        }:
            return WorkUnitResult(
                units=Decimal("0.00"),
                is_half_day=False,
                worked_hours=Decimal("0.00"),
            )

        if normalized_type == Attendance.Type.LEAVE_APPROVED:
            return WorkUnitResult(
                units=Decimal("1.00"),
                is_half_day=False,
                worked_hours=Decimal("8.00"),
            )

        raw_hours = attendance.regular_hours or Decimal("0.00")

        late_minutes = attendance.late_minutes or 0

        half_day_minutes = (
            (
                AttendanceService.HALF_DAY_THRESHOLD.hour * 60
                + AttendanceService.HALF_DAY_THRESHOLD.minute
            )
            - (
                AttendanceService.REGULAR_START.hour * 60
                + AttendanceService.REGULAR_START.minute
            )
        )

        is_half_day = late_minutes >= half_day_minutes

        if raw_hours < Decimal("2.00"):
            return WorkUnitResult(
                units=Decimal("0.00"),
                is_half_day=is_half_day,
                worked_hours=raw_hours,
            )

        if is_half_day or raw_hours < Decimal("4.00"):
            return WorkUnitResult(
                units=Decimal("0.50"),
                is_half_day=True,
                worked_hours=raw_hours,
            )

        return WorkUnitResult(
            units=Decimal("1.00"),
            is_half_day=False,
            worked_hours=raw_hours,
        )

    @staticmethod
    def calculate_regular_hours(
        attendance: Attendance
    ) -> Decimal:

        result = AttendanceService.calculate_regular_work_units(
            attendance
        )

        return result.worked_hours
    @staticmethod
    def recalculate_hours(attendance: Attendance) -> Decimal:
        result = AttendanceService.calculate_regular_work_units(attendance)
        return result.worked_hours

    @staticmethod
    def calculate_overtime_hours_raw(
        overtime_check_in: datetime,
        overtime_check_out: datetime
    ) -> Decimal:

        if not overtime_check_in or not overtime_check_out:
            return Decimal("0.00")

        tz = overtime_check_in.tzinfo
        day = overtime_check_in.date()

        ot_start = datetime.combine(
            day,
            OT_CHECKIN_OPEN
        ).replace(tzinfo=tz)

        ot_end = datetime.combine(
            day,
            OT_END_LIMIT
        ).replace(tzinfo=tz)

        actual_start = max(
            ot_start,
            overtime_check_in
        )

        actual_end = min(
            ot_end,
            overtime_check_out
        )

        if actual_end <= actual_start:
            return Decimal("0.00")

        diff = actual_end - actual_start

        hours = diff.total_seconds() / 3600

        return Decimal(str(round(hours, 4)))

    @staticmethod
    def calculate_overtime_hours(
        overtime_check_in: datetime, overtime_check_out: datetime
    ) -> Decimal:
        return AttendanceService.calculate_overtime_hours_raw(overtime_check_in, overtime_check_out)

    @staticmethod
    def finalize_attendance(
        record: Attendance,
        finalize_status: bool = True
    ) -> None:

        # =====================================================
        # 1. PURE CALCULATION (NO STATE LOGIC)
        # =====================================================
        regular_hours = Decimal(str(record.regular_hours or 0))
        overtime_hours = Decimal(str(record.overtime_hours or 0))

        record.working_hours = (
            regular_hours + overtime_hours
        ).quantize(Decimal("0.01"))

        # =====================================================
        # 2. CLASSIFICATION LAYER (ATTENDANCE TYPE ONLY)
        # =====================================================
        base_type = AttendanceService._resolve_attendance_type(
            is_weekend=bool(record.is_weekend),
            is_holiday=bool(record.is_holiday),
        )

        # half-day override rule (business rule, nhưng OK ở layer này)
        if (
            record.is_half_day
            and base_type == Attendance.Type.NORMAL
        ):
            record.set_attendance_type(Attendance.Type.ABNORMAL)
        else:
            record.set_attendance_type(base_type)

        # =====================================================
        # 3. STATE MACHINE LAYER (ONLY IF EXPLICITLY REQUESTED)
        # =====================================================
        if finalize_status:

            current_state = Attendance.ShiftStatus.normalize(
                record.shift_status
            )

            # ❗ CHỈ allow finalize từ các state hợp lệ
            allowed_finalize_states = {
                Attendance.ShiftStatus.REGULAR_DONE,
                Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                Attendance.ShiftStatus.WORKING_OVERTIME,
                Attendance.ShiftStatus.PRE_OT_REST,
            }

            # nếu state không hợp lệ → KHÔNG override
            if current_state in allowed_finalize_states:
                record.set_shift_status(
                    Attendance.ShiftStatus.COMPLETED
                )

    @staticmethod
    def auto_complete_stale_records(
        reference_date: date | None = None
    ) -> int:

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

            # =====================================================
            # 1. SAFETY GUARD: SKIP IF MANUALLY COMPLETED
            # =====================================================
            if record.shift_status == Attendance.ShiftStatus.COMPLETED:
                continue

            # =====================================================
            # 2. ONLY FILL MISSING REGULAR CHECKOUT
            # =====================================================
            if (
                not record.check_out
                and record.check_in
                and record.shift_status in {
                    Attendance.ShiftStatus.WORKING_REGULAR,
                    Attendance.ShiftStatus.REGULAR_DONE,
                    Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                }
            ):
                record.check_out = datetime.combine(
                    record.date,
                    REGULAR_END
                )

                result = AttendanceService.calculate_regular_work_units(record)

                record.regular_hours = result.worked_hours.quantize(
                    Decimal("0.01")
                )

                record.is_half_day = result.is_half_day

                record.late_minutes = record.late_minutes or 0

            # =====================================================
            # 3. ONLY FILL MISSING OT CHECKOUT (SAFE MODE)
            # =====================================================
            if (
                record.overtime_check_in
                and not record.overtime_check_out
                and record.shift_status in {
                    Attendance.ShiftStatus.WORKING_OVERTIME,
                    Attendance.ShiftStatus.PRE_OT_REST,
                }
            ):
                record.overtime_check_out = datetime.combine(
                    record.date,
                    OT_END_LIMIT
                )

                raw_ot = AttendanceService.calculate_overtime_hours_raw(
                    record.overtime_check_in,
                    record.overtime_check_out,
                )

                multiplier = AttendanceService._day_multiplier(
                    bool(record.is_holiday),
                    bool(record.is_weekend)
                )

                record.overtime_hours = (
                    raw_ot * multiplier
                ).quantize(Decimal("0.01"))

            # =====================================================
            # 4. FINALIZE = PURE DERIVED ONLY (NO STATE CHANGE LOGIC)
            # =====================================================
            AttendanceService.finalize_attendance(record)

            count += 1

        if count > 0:
            db.session.commit()

        return count

    @staticmethod
    def build_attendance_payload(record: Attendance) -> dict | None:
        if not record:
            return None
        return {
            "date": record.date.isoformat() if record.date else None,
            "check_in": record.check_in.isoformat() if record.check_in else None,
            "check_out": record.check_out.isoformat() if record.check_out else None,
            "overtime_check_in": record.overtime_check_in.isoformat() if record.overtime_check_in else None,
            "overtime_check_out": record.overtime_check_out.isoformat() if record.overtime_check_out else None,
            "regular_hours": str(record.regular_hours or 0),
            "overtime_hours": str(record.overtime_hours or 0),
            "working_hours": str(record.working_hours or 0),
            "regular_hours_raw": str(
                AttendanceService.calculate_regular_hours(record)
            ),
            "overtime_hours_raw": str(
                AttendanceService.calculate_overtime_hours(
                    record.overtime_check_in,
                    record.overtime_check_out
                ) if record.overtime_check_in and record.overtime_check_out else Decimal("0.00")
            ),
            "day_multiplier": str(
                AttendanceService._day_multiplier(
                    bool(record.is_holiday),
                    bool(record.is_weekend)
                )
            ),
            "shift_status": Attendance.ShiftStatus.normalize(record.shift_status),
            "attendance_type": Attendance.Type.normalize(record.attendance_type),
            "late_minutes": record.late_minutes,
            "is_half_day": record.is_half_day,
            "is_weekend": record.is_weekend,
            "is_holiday": record.is_holiday,
        }
    @staticmethod
    def get_today(employee_id: int, sim_time_str: str | None = None) -> Attendance | None:
        now_dt = AttendanceService.parse_time(sim_time_str or session.get("simulated_now"))
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date()
        ).first()
        if record:
            record.shift_status = Attendance.ShiftStatus.normalize(record.shift_status)
        return record

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
        today = now_dt.date()
        if not month or not year:
            return (
                Attendance.query.filter(
                    Attendance.employee_id == employee_id,
                    Attendance.date <= today,
                )
                .order_by(Attendance.date.desc())
                .limit(limit)
                .all()
            )
        if month < 1 or month > 12:
            raise ValidationError("Tháng không hợp lệ")
        last_day = monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end = date(year, month, last_day)
        effective_end = (
            month_end
            if (year, month) < (today.year, today.month)
            else min(month_end, today)
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
            end = min(leave.to_date, effective_end)
            cur = start
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
                record = attendance_by_date[current]
                history.append(record)
            else:
                is_weekend = current.weekday() >= 5
                is_holiday = current in holiday_dates
                is_leave = current in leave_dates
                if is_leave:
                    shift_status = Attendance.ShiftStatus.LEAVE
                    attendance_type = Attendance.Type.LEAVE_APPROVED
                elif is_holiday:
                    shift_status = Attendance.ShiftStatus.HOLIDAY_OFF
                    attendance_type = Attendance.Type.HOLIDAY
                elif is_weekend:
                    shift_status = Attendance.ShiftStatus.WEEKEND_OFF
                    attendance_type = Attendance.Type.WEEKEND
                else:
                    shift_status = Attendance.ShiftStatus.ABSENT
                    attendance_type = Attendance.Type.ABSENT
                history.append(
                    SimpleNamespace(
                        id=None,
                        date=current,
                        check_in=None,
                        check_out=None,
                        overtime_check_in=None,
                        overtime_check_out=None,
                        regular_hours=Decimal("0.00"),
                        overtime_hours=Decimal("0.00"),
                        working_hours=Decimal("0.00"),
                        shift_status=Attendance.ShiftStatus.normalize(shift_status),
                        attendance_type=attendance_type,
                        late_minutes=0,
                        is_half_day=False,
                        is_weekend=is_weekend,
                        is_holiday=is_holiday,
                    )
                )
            current = current.fromordinal(current.toordinal() - 1)
        return history

    @staticmethod
    def delete_attendance(
        employee_id: int,
        date_str: str
    ) -> date | None:
        try:
            target_date = datetime.fromisoformat(date_str).date()
        except (TypeError, ValueError):
            raise ValidationError("Ngày không hợp lệ. Dùng YYYY-MM-DD")

        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=target_date
        ).first()

        if not record:
            raise ValidationError("Không tìm thấy dữ liệu chấm công")

        employee = Employee.query.get(employee_id)

        overtime_requests = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == target_date,
        ).all()

        for ot in overtime_requests:
            db.session.delete(ot)

        if employee and employee.user_id:
            notifications = Notification.query.filter(
                Notification.user_id == employee.user_id,
                Notification.is_deleted.is_(False),
                Notification.type.in_(["attendance", "overtime"]),
                db.func.date(Notification.created_at) == target_date,
            ).all()

            for n in notifications:
                n.is_deleted = True

        db.session.delete(record)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        last_record = (
            Attendance.query
            .filter_by(employee_id=employee_id)
            .order_by(Attendance.date.desc())
            .first()
        )

        return last_record.date if last_record else None

    @staticmethod
    def delete_notification_cascade(notification_id: int, user_id: int) -> dict:
        noti = Notification.query.filter_by(
            id=notification_id,
            user_id=user_id,
        ).first()
        if not noti:
            raise ValidationError("Không tìm thấy thông báo")
        noti.is_deleted = True
        cascaded = []
        if noti.type == "overtime":
            target_date = (
                noti.created_at.date()
                if noti.created_at
                else None
            )
            if target_date:
                employee = Employee.query.filter_by(
                    user_id=user_id
                ).first()
                if employee:
                    ot_req = OvertimeRequest.query.filter(
                        OvertimeRequest.employee_id == employee.id,
                        OvertimeRequest.overtime_date == target_date,
                        OvertimeRequest.is_deleted.is_(False),
                    ).first()
                    if ot_req:
                        ot_req.is_deleted = True
                        cascaded.append(
                            f"OT request #{ot_req.id}"
                        )
                    att = Attendance.query.filter_by(
                        employee_id=employee.id,
                        date=target_date,
                    ).first()
                    if att:
                        att.overtime_hours = Decimal("0.00")
                        att.overtime_check_in = None
                        att.overtime_check_out = None
                        att.overtime_request_id = None
                        regular_hours = Decimal(
                            str(att.regular_hours or 0)
                        )
                        att.working_hours = (
                            regular_hours
                        ).quantize(Decimal("0.01"))
                        if att.check_in and att.check_out:
                            att.set_shift_status(
                                Attendance.ShiftStatus.REGULAR_DONE
                            )
                        elif att.check_in:
                            att.set_shift_status(
                                Attendance.ShiftStatus.WORKING_REGULAR
                            )
                        else:
                            att.set_shift_status(
                                Attendance.ShiftStatus.NOT_STARTED
                            )
                        cascaded.append(
                            f"Attendance overtime reset ({target_date})"
                        )
        db.session.commit()
        return {
            "deleted": True,
            "cascaded": cascaded,
        }

    @staticmethod
    def process_employee_action(
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:

        today = current_time.date()

        attendance = Attendance.query.filter_by(
            employee_id=employee_id,
            date=today,
        ).first()

        # =====================================================
        # 1. CHƯA CÓ RECORD -> NOT_STARTED FLOW
        # =====================================================
        if not attendance:
            return AttendanceService._handle_not_started(
                employee_id,
                payload,
                current_time,
            )

        # normalize state (single source of truth)
        shift_status = Attendance.ShiftStatus.normalize(
            attendance.shift_status
        )

        # =====================================================
        # 2. COMPLETED -> IMMUTABLE END STATE
        # =====================================================
        if shift_status == Attendance.ShiftStatus.COMPLETED:
            return {
                "type": "success",
                "action": AttendanceService.ACTION_ALREADY_RECORDED,
                "attendance_state": shift_status,
                "message": "Ngày công đã hoàn tất",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        # =====================================================
        # 3. OFFDAY STATES -> IMMUTABLE (KHÔNG AUTO CHECKIN)
        # =====================================================
        OFFDAY_STATES = {
            Attendance.ShiftStatus.HOLIDAY_OFF,
            Attendance.ShiftStatus.WEEKEND_OFF,
            Attendance.ShiftStatus.LEAVE,
            Attendance.ShiftStatus.ABSENT,
        }

        if shift_status in OFFDAY_STATES:
            return AttendanceService._handle_offday_logic(
                employee_id=employee_id,
                payload=payload,
                today=today,
            )

        # =====================================================
        # 4. CHƯA CHECK-IN -> NOT_STARTED FLOW
        # =====================================================
        if not attendance.check_in:
            return AttendanceService._handle_not_started(
                employee_id,
                payload,
                current_time,
            )

        # =====================================================
        # 5. CA CHÍNH (WORKING REGULAR FLOW)
        # =====================================================
        REGULAR_STATES = {
            Attendance.ShiftStatus.WORKING_REGULAR,
            Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED,
        }

        if shift_status in REGULAR_STATES:
            return AttendanceService._handle_working(
                attendance,
                employee_id,
                payload,
                current_time,
            )

        # =====================================================
        # 6. SAU CHECKOUT CA CHÍNH (IMPORTANT FIX)
        # =====================================================
        # ❗ KHÔNG ĐƯỢC finalize ở đây
        # ❗ LUÔN đi qua OT decision machine
        AFTER_REGULAR_STATES = {
            Attendance.ShiftStatus.REGULAR_DONE,
            Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
            Attendance.ShiftStatus.PRE_OT_REST,
            Attendance.ShiftStatus.OT_CHECKIN_REQUIRED,
            Attendance.ShiftStatus.WORKING_OVERTIME,
        }

        if shift_status in AFTER_REGULAR_STATES:
            return AttendanceService._handle_after_checkout(
                attendance,
                employee_id,
                payload,
                current_time,
            )

        # =====================================================
        # 7. FALLBACK SAFETY
        # =====================================================
        return {
            "type": "error",
            "attendance_state": shift_status,
            "message": f"Trạng thái không hợp lệ: {shift_status}",
            "attendance": AttendanceService.build_attendance_payload(attendance),
        }
        
    @staticmethod
    def _handle_not_started(
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:
        target_date = current_time.date()
        offday_response = AttendanceService._handle_offday_logic(
            employee_id=employee_id,
            payload=payload,
            target_date=target_date,
        )
        if offday_response and not offday_response.get("pass_through", False):
            return offday_response
        return AttendanceService._handle_checkin(
            employee_id=employee_id,
            payload=payload,
            current_time=current_time,
        )
    @staticmethod
    def _handle_checkin(
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:

        confirm_work = bool(
            payload.get("confirm_work_on_offday")
        ) or bool(
            payload.get("overtime_confirmed")
        )

        result = AttendanceService.check_in(
            employee_id=employee_id,
            current_time=current_time,
            confirm_work=confirm_work,
        )

        response_type = (
            "warning"
            if result.get("action") in {
                AttendanceService.ACTION_HOLIDAY_WORK_PROMPT,
                AttendanceService.ACTION_WEEKEND_WORK_PROMPT,
            }
            else "success"
        )

        return {
            "type": response_type,
            "status_code": 200,
            **result,
        }

    @staticmethod
    def _handle_working(
        attendance: Attendance,
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:

        today = current_time.date()

        end_of_day = datetime.combine(
            today,
            REGULAR_END,
        )

        lunch_start = datetime.combine(
            today,
            LUNCH_START,
        )

        lunch_end = datetime.combine(
            today,
            LUNCH_END,
        )

        early_checkout_confirmed = bool(
            payload.get("early_checkout_confirmed")
        )

        if lunch_start <= current_time < lunch_end:

            return {
                "type": "info",
                "action": "lunch_break",
                "attendance_state": attendance.shift_status,
                "message": "Đang trong giờ nghỉ trưa (12:00–13:00)",
                "attendance": AttendanceService.build_attendance_payload(
                    attendance
                ),
            }

        if current_time >= end_of_day:

            return AttendanceService.check_out_regular(
                employee_id=employee_id,
                current_time=current_time,
                early_checkout=False,
            )

        if not early_checkout_confirmed:

            early_minutes = int(
                (
                    end_of_day - current_time
                ).total_seconds() // 60
            )

            return {
                "type": "warning",
                "action": AttendanceService.ACTION_EARLY_CHECKOUT_PROMPT,
                "attendance_state": attendance.shift_status,
                "message": (
                    f"Bạn có muốn tan ca sớm không? "
                    f"(sớm {early_minutes} phút)"
                ),
                "requires_confirmation": True,
                "flags": {
                    "early_minutes": early_minutes,
                },
                "attendance": AttendanceService.build_attendance_payload(
                    attendance
                ),
            }

        return AttendanceService.check_out_regular(
            employee_id=employee_id,
            current_time=current_time,
            early_checkout=True,
        )

    @staticmethod
    def _handle_after_checkout(
        attendance: Attendance,
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:

        sim_time = current_time.isoformat()
        state = Attendance.ShiftStatus.normalize(attendance.shift_status)

        overtime_decision = str(
            payload.get("overtime_decision") or ""
        ).strip().lower()

        # =========================================================
        # 1. REGULAR_DONE → MUST ALWAYS GO THROUGH OT DECISION
        # =========================================================
        if state == Attendance.ShiftStatus.REGULAR_DONE:

            # ❌ KHÔNG được auto COMPLETED khi chưa quyết định OT

            # Nếu chưa có decision → hỏi OT
            if overtime_decision not in {"yes", "no"}:
                return {
                    "type": "warning",
                    "action": AttendanceService.ACTION_OFFER_OVERTIME,
                    "attendance_state": Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                    "message": "Bạn có muốn đăng ký tăng ca không?",
                    "requires_overtime_decision": True,
                    "next_event": "offer_overtime",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            # User từ chối OT
            if overtime_decision == "no":
                attendance.set_shift_status(
                    Attendance.ShiftStatus.COMPLETED
                )
                AttendanceService.finalize_attendance(
                    attendance,
                    finalize_status=True,
                )
                db.session.commit()

                return {
                    "type": "success",
                    "action": AttendanceService.ACTION_COMPLETE_WITHOUT_OT,
                    "attendance_state": Attendance.ShiftStatus.COMPLETED,
                    "message": "Đã hoàn thành ngày làm việc.",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            # User đồng ý OT → tạo request
            return AttendanceService._create_ot_request_pending(
                attendance,
                employee_id,
                current_time,
            )

        # =========================================================
        # 2. PENDING OT DECISION STATE
        # =========================================================
        if state == Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION:

            approved_ot = AttendanceService._get_approved_ot(
                employee_id,
                current_time.date(),
            )

            if approved_ot:
                attendance.set_shift_status(
                    Attendance.ShiftStatus.PRE_OT_REST
                )
                db.session.commit()

                return {
                    "type": "info",
                    "action": "ot_approved_wait",
                    "attendance_state": Attendance.ShiftStatus.PRE_OT_REST,
                    "overtime_status": "APPROVED",
                    "message": "Yêu cầu tăng ca đã được phê duyệt.",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            pending_ot = OvertimeRequest.query.filter(
                OvertimeRequest.employee_id == employee_id,
                OvertimeRequest.overtime_date == current_time.date(),
                OvertimeRequest.is_deleted.is_(False),
                OvertimeRequest.status.in_([
                    "pending",
                    "pending_hr",
                    "pending_admin",
                ]),
            ).first()

            if pending_ot:
                return {
                    "type": "info",
                    "action": "ot_pending_approval",
                    "attendance_state": state,
                    "overtime_status": "PENDING",
                    "message": "Đang chờ duyệt tăng ca",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            # fallback: vẫn KHÔNG finalize nếu chưa rõ OT state
            return {
                "type": "warning",
                "action": AttendanceService.ACTION_OFFER_OVERTIME,
                "attendance_state": state,
                "message": "Chưa có quyết định tăng ca",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        # =========================================================
        # 3. PRE OT REST → OT FLOW
        # =========================================================
        if state == Attendance.ShiftStatus.PRE_OT_REST:

            approved_ot = AttendanceService._get_approved_ot(
                employee_id,
                current_time.date(),
            )

            if not approved_ot:
                attendance.set_shift_status(
                    Attendance.ShiftStatus.COMPLETED
                )
                AttendanceService.finalize_attendance(
                    attendance,
                    finalize_status=True,
                )
                db.session.commit()

                return {
                    "type": "warning",
                    "action": AttendanceService.ACTION_COMPLETE_WITHOUT_OT,
                    "attendance_state": Attendance.ShiftStatus.COMPLETED,
                    "message": "Không còn OT hợp lệ → kết thúc ngày công",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            if attendance.overtime_check_in:
                attendance.set_shift_status(
                    Attendance.ShiftStatus.WORKING_OVERTIME
                )
                db.session.commit()

                return {
                    "type": "info",
                    "action": "working_overtime",
                    "attendance_state": Attendance.ShiftStatus.WORKING_OVERTIME,
                    "message": "Đang trong ca tăng ca",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            if current_time.time() < AttendanceService.OT_CHECKIN_OPEN:
                return {
                    "type": "info",
                    "action": "pre_ot_rest",
                    "attendance_state": state,
                    "message": "Chờ tới giờ OT",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            return AttendanceService.check_in_overtime(
                employee_id,
                sim_time,
            )

        # =========================================================
        # 4. WORKING OT
        # =========================================================
        if state == Attendance.ShiftStatus.WORKING_OVERTIME:

            if not attendance.overtime_check_out:
                return AttendanceService.check_out_overtime(
                    employee_id,
                    sim_time,
                )

            attendance.set_shift_status(
                Attendance.ShiftStatus.COMPLETED
            )

            AttendanceService.finalize_attendance(
                attendance,
                finalize_status=True,
            )
            db.session.commit()

            return {
                "type": "success",
                "action": AttendanceService.ACTION_ALREADY_RECORDED,
                "attendance_state": Attendance.ShiftStatus.COMPLETED,
                "message": "Đã hoàn thành tăng ca",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        # =========================================================
        # 5. COMPLETED
        # =========================================================
        if state == Attendance.ShiftStatus.COMPLETED:
            return {
                "type": "success",
                "action": AttendanceService.ACTION_ALREADY_RECORDED,
                "attendance_state": state,
                "message": "Ngày công đã hoàn tất",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        return {
            "type": "info",
            "action": AttendanceService.ACTION_ALREADY_RECORDED,
            "attendance_state": state,
            "message": f"Trạng thái hiện tại: {state}",
            "attendance": AttendanceService.build_attendance_payload(attendance),
        }
    
    @staticmethod
    def _create_ot_request_pending(
        attendance: Attendance,
        employee_id: int,
        current_time: datetime,
    ) -> dict:
        today = current_time.date()
        existing = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == today,
            OvertimeRequest.is_deleted.is_(False),
        ).first()
        if not existing:
            is_holiday = AttendanceService._is_holiday(today)
            is_weekend = today.weekday() >= 5
            multiplier = Decimal(
                str(
                    AttendanceService._day_multiplier(
                        is_holiday,
                        is_weekend,
                    )
                )
            )
            ot_req = OvertimeRequest(
                employee_id=employee_id,
                overtime_date=today,
                status="pending",
                requested_hours=Decimal("3.00"),
                overtime_hours=Decimal("0.00"),
                is_holiday_ot=is_holiday,
                holiday_multiplier=multiplier,
                request_type="after_shift",
                reason="Đăng ký tăng ca sau giờ hành chính",
            )
            db.session.add(ot_req)
            db.session.flush()  # lấy id ngay
            attendance.overtime_request_id = ot_req.id
        else:
            attendance.overtime_request_id = existing.id
        attendance.set_shift_status(
            Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION
        )
        db.session.commit()
        return {
            "type": "success",
            "action": AttendanceService.ACTION_OVERTIME_REQUEST_CREATED,
            "attendance_state": Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
            "overtime_status": "PENDING",
            "message": "Đã gửi yêu cầu tăng ca. Vui lòng chờ phê duyệt.",
            "attendance": AttendanceService.build_attendance_payload(attendance),
        }

    @staticmethod
    def _get_approved_ot(employee_id: int, target_date: date) -> OvertimeRequest | None:
        return OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == target_date,
            OvertimeRequest.is_deleted.is_(False),
            OvertimeRequest.status == "approved",
        ).first()

    @staticmethod
    def handle_ot_approved(
        ot_request: OvertimeRequest,
    ) -> None:
        attendance = Attendance.query.filter_by(
            employee_id=ot_request.employee_id,
            date=ot_request.overtime_date,
        ).first()
        if attendance:
            attendance.shift_status = Attendance.ShiftStatus.normalize(
                attendance.shift_status
            )
            if attendance.shift_status in {
                Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                Attendance.ShiftStatus.REGULAR_DONE,
            }:
                attendance.set_shift_status(
                    Attendance.ShiftStatus.PRE_OT_REST
                )
        employee = Employee.query.get(
            ot_request.employee_id
        )
        if employee and employee.user_id:
            db.session.add(
                Notification(
                    user_id=employee.user_id,
                    title="Yêu cầu tăng ca đã được duyệt",
                    content=(
                        f"Yêu cầu tăng ca ngày "
                        f"{ot_request.overtime_date.strftime('%d/%m/%Y')} "
                        f"đã được phê duyệt. "
                        f"Bạn có thể xác thực để bắt đầu tăng ca."
                    ),
                    type="overtime",
                    link="/employee/attendance",
                )
            )
        db.session.commit()

    @staticmethod
    def handle_ot_rejected(
        ot_request: OvertimeRequest,
        reason: str = "",
    ) -> None:
        attendance = Attendance.query.filter_by(
            employee_id=ot_request.employee_id,
            date=ot_request.overtime_date,
        ).first()
        if attendance:
            attendance.shift_status = Attendance.ShiftStatus.normalize(
                attendance.shift_status
            )
            if attendance.shift_status in {
                Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                Attendance.ShiftStatus.REGULAR_DONE,
                Attendance.ShiftStatus.PRE_OT_REST,
                Attendance.ShiftStatus.WORKING_OVERTIME,
            }:
                attendance.overtime_check_in = None
                attendance.overtime_check_out = None
                attendance.overtime_hours = Decimal("0.00")
                attendance.overtime_request_id = None
                AttendanceService.finalize_attendance(
                    attendance,
                    finalize_status=True,
                )
        employee = Employee.query.get(
            ot_request.employee_id
        )
        if employee and employee.user_id:
            reason_str = (
                f" Lý do: {reason}"
                if reason
                else ""
            )
            db.session.add(
                Notification(
                    user_id=employee.user_id,
                    title="Yêu cầu tăng ca bị từ chối",
                    content=(
                        f"Yêu cầu tăng ca ngày "
                        f"{ot_request.overtime_date.strftime('%d/%m/%Y')} "
                        f"đã bị từ chối."
                        f"{reason_str}"
                    ),
                    type="overtime",
                    link="/employee/attendance",
                )
            )
        db.session.commit()

    @staticmethod
    def _handle_offday_logic(
        employee_id: int,
        payload: dict,
        today: date,
    ) -> dict:

        is_holiday = AttendanceService._is_holiday(today)
        is_weekend = today.weekday() >= 5

        # =====================================================
        # CASE 1: USER DECLINE WORK ON OFFDAY
        # =====================================================
        if bool(payload.get("decline_offday_work")) and (is_holiday or is_weekend):

            record = AttendanceService.get_or_create_today(
                employee_id=employee_id,
                now_dt=datetime.combine(today, time.min),
            )

            # =================================================
            # 1. SET IMMUTABLE OFFDAY STATE
            # =================================================
            record.is_holiday = is_holiday
            record.is_weekend = is_weekend

            attendance_type = (
                Attendance.Type.HOLIDAY
                if is_holiday
                else Attendance.Type.WEEKEND
            )

            shift_status = (
                Attendance.ShiftStatus.HOLIDAY_OFF
                if is_holiday
                else Attendance.ShiftStatus.WEEKEND_OFF
            )

            record.set_attendance_type(attendance_type)
            record.set_shift_status(shift_status)

            # =================================================
            # 2. LOCK SEMANTIC (IMPORTANT FIX)
            # =================================================
            record.check_in = None
            record.check_out = None
            record.overtime_check_in = None
            record.overtime_check_out = None

            record.regular_hours = Decimal("0.00")
            record.overtime_hours = Decimal("0.00")
            record.working_hours = Decimal("0.00")

            # =================================================
            # 3. FINALIZE (OK BUT NO LATER OVERRIDE)
            # =================================================
            AttendanceService.finalize_attendance(
                record,
                finalize_status=True,
            )

            db.session.commit()

            return {
                "type": "info",
                "status_code": 200,
                "action": (
                    AttendanceService.ACTION_HOLIDAY_OFF
                    if is_holiday
                    else AttendanceService.ACTION_WEEKEND_OFF
                ),
                "attendance_state": Attendance.ShiftStatus.normalize(
                    record.shift_status
                ),
                "message": (
                    "Đã ghi nhận nghỉ lễ hôm nay."
                    if is_holiday
                    else "Đã ghi nhận nghỉ cuối tuần hôm nay."
                ),
                "attendance": AttendanceService.build_attendance_payload(record),

                # =================================================
                # 🔥 CRITICAL: LOCK FLAG FOR OUTER LAYER
                # =================================================
                "final": True,
                "locked_state": True,
            }

        # =====================================================
        # CASE 2: NOT OFFDAY FLOW
        # =====================================================
        return {
            "pass_through": True
        }

    @staticmethod
    def check_in(
        employee_id: int,
        sim_time_str: str | None,
        confirm_work_on_offday: bool = False,
    ) -> dict:
        employee = Employee.query.get(employee_id)

        if employee and employee.is_attendance_required is False:
            raise ValidationError(
                "Nhân sự này không áp dụng chấm công bắt buộc."
            )

        now_dt = AttendanceService.parse_time(sim_time_str)

        record = AttendanceService.get_or_create_today(
            employee_id,
            now_dt,
        )

        # =====================================================
        # 1. NORMALIZE SHIFT STATE (GATE ENTRY)
        # =====================================================
        normalized_shift = Attendance.ShiftStatus.normalize(
            record.shift_status
        )

        OFFDAY_STATES = {
            Attendance.ShiftStatus.HOLIDAY_OFF,
            Attendance.ShiftStatus.WEEKEND_OFF,
        }

        # =====================================================
        # 2. OFFDAY HARD GATE (FIX CRITICAL BUG)
        # =====================================================
        if normalized_shift in OFFDAY_STATES and not confirm_work_on_offday:
            return {
                "action": (
                    AttendanceService.ACTION_HOLIDAY_WORK_PROMPT
                    if normalized_shift == Attendance.ShiftStatus.HOLIDAY_OFF
                    else AttendanceService.ACTION_WEEKEND_WORK_PROMPT
                ),
                "requires_confirmation": True,
                "attendance_state": normalized_shift,
                "message": (
                    "Hôm nay là ngày nghỉ lễ. Bạn có muốn đi làm không?"
                    if normalized_shift == Attendance.ShiftStatus.HOLIDAY_OFF
                    else "Hôm nay là ngày nghỉ cuối tuần. Bạn có muốn đi làm không?"
                ),
            }

        # =====================================================
        # 3. OVERRIDE OFFDAY → WORKING MODE (ONLY WHEN CONFIRMED)
        # =====================================================
        if normalized_shift in OFFDAY_STATES and confirm_work_on_offday:
            record.check_in = None
            record.check_out = None
            record.overtime_check_in = None
            record.overtime_check_out = None
            record.regular_hours = Decimal("0.00")
            record.overtime_hours = Decimal("0.00")
            record.working_hours = Decimal("0.00")

            record.set_shift_status(
                Attendance.ShiftStatus.WORKING_REGULAR
            )

        # =====================================================
        # 4. DUPLICATE CHECK-IN GUARD
        # =====================================================
        elif record.check_in:
            raise ValidationError("Bạn đã check-in hôm nay.")

        # =====================================================
        # 5. WORKDAY INFO
        # =====================================================
        is_weekend = now_dt.weekday() >= 5
        is_holiday = AttendanceService._is_holiday(now_dt.date())

        # =====================================================
        # 6. NORMAL WORK FLOW ENTRY
        # =====================================================
        record.is_weekend = is_weekend
        record.is_holiday = is_holiday

        record.set_attendance_type(
            AttendanceService._resolve_attendance_type(
                is_holiday=is_holiday,
                is_weekend=is_weekend,
            )
        )

        record.check_in = now_dt

        record.set_shift_status(
            Attendance.ShiftStatus.WORKING_REGULAR
        )

        # =====================================================
        # 7. LATE / HALF DAY CALCULATION
        # =====================================================
        shift_start_dt = datetime.combine(
            now_dt.date(),
            REGULAR_START,
        )

        late_minutes = max(
            0,
            int((now_dt - shift_start_dt).total_seconds() / 60)
        )

        record.late_minutes = late_minutes

        half_day_minutes = (
            (
                AttendanceService.HALF_DAY_THRESHOLD.hour * 60
                + AttendanceService.HALF_DAY_THRESHOLD.minute
            )
            - (
                AttendanceService.REGULAR_START.hour * 60
                + AttendanceService.REGULAR_START.minute
            )
        )

        record.is_half_day = late_minutes >= half_day_minutes

        # =====================================================
        # 8. STATUS CLASSIFICATION
        # =====================================================
        if record.is_half_day:
            status_name = "HALF_DAY"
        elif late_minutes > 0:
            status_name = "LATE"
        else:
            status_name = "PRESENT"

        db_status = AttendanceService.get_status(status_name)
        if db_status:
            record.status_id = db_status.id

        # =====================================================
        # 9. ABNORMAL FLAG
        # =====================================================
        if (
            not is_weekend
            and not is_holiday
            and record.is_half_day
        ):
            record.set_attendance_type(
                Attendance.Type.ABNORMAL
            )

        # =====================================================
        # 10. SAVE
        # =====================================================
        db.session.commit()

        # =====================================================
        # 11. RESPONSE BUILD
        # =====================================================
        msg = (
            f"Check-in thành công lúc {now_dt.strftime('%H:%M:%S')}"
        )

        resp_type = "success"

        multiplier = AttendanceService._day_multiplier(
            is_holiday,
            is_weekend,
        )

        if is_holiday:
            msg += f" (Ngày lễ — công x{multiplier.normalize()})"
        elif is_weekend and multiplier > 1:
            msg += f" (Cuối tuần — công x{multiplier.normalize()})"

        if record.is_half_day:
            msg += f". Đi muộn {late_minutes} phút — tính nửa ngày công."
            resp_type = "warning"
        elif late_minutes > 0:
            msg += f". Đi muộn {late_minutes} phút."
            resp_type = "warning"

        return {
            "action": AttendanceService.ACTION_CHECK_IN,
            "type": resp_type,
            "message": msg,
            "attendance_state": record.shift_status,
            "attendance": AttendanceService.build_attendance_payload(record),
        }

    @staticmethod
    def check_out_regular(
        employee_id: int,
        sim_time_str: str | None,
        early_checkout: bool = False,
        current_time: datetime | None = None,
    ) -> dict:
        now_dt = current_time or AttendanceService.parse_time(
            sim_time_str
        )
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date(),
        ).first()
        if not record or not record.check_in:
            raise ValidationError("Bạn chưa check-in.")
        if record.check_out:
            raise ValidationError(
                "Bạn đã check-out ca chính."
            )
        record.check_out = now_dt
        work_result = (
            AttendanceService.calculate_regular_work_units(
                record
            )
        )
        raw_regular_hours = Decimal(
            str(work_result.worked_hours)
        )
        if (
            work_result.is_half_day
            and not record.is_weekend
            and not record.is_holiday
        ):
            raw_regular_hours = (
                raw_regular_hours * Decimal("0.5")
            ).quantize(Decimal("0.0001"))
        multiplier = AttendanceService._day_multiplier(
            bool(record.is_holiday),
            bool(record.is_weekend),
        )
        record.regular_hours = (
            raw_regular_hours * multiplier
        ).quantize(Decimal("0.01"))
        record.is_half_day = work_result.is_half_day
        if (
            record.is_half_day
            and not record.is_weekend
            and not record.is_holiday
        ):
            record.set_attendance_type(
                Attendance.Type.ABNORMAL
            )
        record.set_shift_status(
            Attendance.ShiftStatus.REGULAR_DONE
        )
        AttendanceService.finalize_attendance(
            record,
            finalize_status=False,
        )
        multiplier_label = (
            f" (x{multiplier.normalize()})"
            if multiplier > 1
            else ""
        )
        if early_checkout:
            early_minutes = 0
            if current_time:
                end_of_day = datetime.combine(
                    current_time.date(),
                    REGULAR_END,
                )
                early_minutes = max(
                    0,
                    int(
                        (
                            end_of_day - current_time
                        ).total_seconds() // 60
                    ),
                )
            record.set_shift_status(
                Attendance.ShiftStatus.COMPLETED
            )
            AttendanceService.finalize_attendance(
                record,
                finalize_status=True,
            )
            db.session.commit()
            return {
                "type": "warning",
                "action": (
                    AttendanceService.ACTION_CHECK_OUT
                ),
                "message": (
                    f"Check-out lúc "
                    f"{now_dt.strftime('%H:%M:%S')}. "
                    f"Về sớm {early_minutes} phút."
                ),
                "attendance_state": (
                    record.shift_status
                ),
                "status_key": "early_leave",
                "regular_hours": str(
                    record.regular_hours
                ),
                "overtime_hours": str(
                    record.overtime_hours or 0
                ),
                "working_hours": str(
                    record.working_hours
                ),
                "attendance": (
                    AttendanceService.build_attendance_payload(
                        record
                    )
                ),
                "next_event": None,
                "requires_overtime_decision": False,
            }
        db.session.commit()
        return {
            "type": "success",
            "action": (
                AttendanceService.ACTION_CHECK_OUT
            ),
            "message": (
                f"Check-out ca chính thành công. "
                f"Công thường: "
                f"{record.regular_hours}h"
                f"{multiplier_label}"
                + (
                    " (áp dụng nửa ngày công "
                    "do đi muộn quá mức)"
                    if (
                        record.is_half_day
                        and not record.is_weekend
                        and not record.is_holiday
                    )
                    else ""
                )
            ),
            "attendance_state": (
                record.shift_status
            ),
            "regular_hours": str(
                record.regular_hours
            ),
            "overtime_hours": str(
                record.overtime_hours or 0
            ),
            "working_hours": str(
                record.working_hours
            ),
            "attendance": (
                AttendanceService.build_attendance_payload(
                    record
                )
            ),
            "next_event": "offer_overtime",
            "requires_overtime_decision": True,
        }

    @staticmethod
    def check_in_overtime(
        employee_id: int,
        sim_time_str: str | None,
    ) -> dict:
        now_dt = AttendanceService.parse_time(
            sim_time_str
        )
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date(),
        ).first()
        if not record or not record.check_out:
            raise ValidationError(
                "Bạn phải hoàn tất ca chính trước khi OT."
            )
        approved_ot = AttendanceService._get_approved_ot(
            employee_id,
            now_dt.date(),
        )
        if not approved_ot:
            raise ValidationError(
                "❌ Yêu cầu tăng ca chưa được phê duyệt."
            )
        if record.overtime_check_in:
            raise ValidationError(
                "Bạn đã check-in OT rồi."
            )
        normalized_shift = (
            Attendance.ShiftStatus.normalize(
                record.shift_status
            )
        )
        allowed_states = {
            Attendance.ShiftStatus.PRE_OT_REST,
            Attendance.ShiftStatus.OT_CHECKIN_REQUIRED,
            Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
        }
        if normalized_shift not in allowed_states:
            raise ValidationError(
                "Không thể bắt đầu tăng ca ở trạng thái hiện tại."
            )
        record.overtime_check_in = now_dt
        record.overtime_status = "APPROVED"
        record.overtime_request_id = approved_ot.id
        if now_dt.time() < OT_CHECKIN_OPEN:
            record.set_shift_status(
                Attendance.ShiftStatus.PRE_OT_REST
            )
            msg = (
                f"Đã xác thực tăng ca lúc "
                f"{now_dt.strftime('%H:%M:%S')}. "
                f"Công OT sẽ bắt đầu tính từ 19:00."
            )
        else:
            record.set_shift_status(
                Attendance.ShiftStatus.WORKING_OVERTIME
            )
            msg = (
                f"✅ Check-in tăng ca thành công lúc "
                f"{now_dt.strftime('%H:%M:%S')}."
            )
        db.session.commit()
        return {
            "type": "success",
            "action": (
                AttendanceService.ACTION_CHECK_IN_OT
            ),
            "message": msg,
            "attendance_state": (
                record.shift_status
            ),
            "overtime_status": "APPROVED",
            "attendance": (
                AttendanceService.build_attendance_payload(
                    record
                )
            ),
        }

    @staticmethod
    def check_out_overtime(
        employee_id: int,
        sim_time_str: str | None,
    ) -> dict:
        now_dt = AttendanceService.parse_time(
            sim_time_str
        )
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date(),
        ).first()
        if not record or not record.overtime_check_in:
            raise ValidationError(
                "Bạn chưa check-in tăng ca."
            )
        if record.overtime_check_out:
            raise ValidationError(
                "Bạn đã check-out OT rồi."
            )
        normalized_shift = (
            Attendance.ShiftStatus.normalize(
                record.shift_status
            )
        )
        if normalized_shift not in {
            Attendance.ShiftStatus.WORKING_OVERTIME,
            Attendance.ShiftStatus.PRE_OT_REST,
        }:
            raise ValidationError(
                "Không thể kết thúc OT ở trạng thái hiện tại."
            )
        approved_ot = AttendanceService._get_approved_ot(
            employee_id,
            now_dt.date(),
        )
        if not approved_ot:
            raise ValidationError(
                "Yêu cầu tăng ca không tồn tại hoặc chưa được duyệt."
            )
        ot_end_dt = datetime.combine(
            now_dt.date(),
            OT_END_LIMIT,
        )
        record.overtime_check_out = min(
            now_dt,
            ot_end_dt,
        )
        raw_ot = (
            AttendanceService.calculate_overtime_hours_raw(
                record.overtime_check_in,
                record.overtime_check_out,
            )
        )
        multiplier = Decimal(
            str(
                approved_ot.holiday_multiplier
                or AttendanceService._day_multiplier(
                    bool(record.is_holiday),
                    bool(record.is_weekend),
                )
            )
        )
        if raw_ot < AttendanceService.MIN_OT_HOURS:
            raw_ot = Decimal("0.00")
        record.overtime_hours = (
            raw_ot * multiplier
        ).quantize(Decimal("0.01"))
        AttendanceService.finalize_attendance(
            record,
            finalize_status=True,
        )
        db.session.commit()
        multiplier_label = (
            f" (x{multiplier.normalize()})"
            if multiplier > 1
            else ""
        )
        return {
            "type": "success",
            "action": (
                AttendanceService.ACTION_CHECK_OUT_OT
            ),
            "message": (
                "✅ Đã hoàn thành tăng ca. "
                f"OT: {record.overtime_hours}h"
                f"{multiplier_label}"
            ),
            "attendance_state": (
                record.shift_status
            ),
            "regular_hours": str(
                record.regular_hours
            ),
            "overtime_hours": str(
                record.overtime_hours
            ),
            "working_hours": str(
                record.working_hours
            ),
            "overtime_check_in": (
                record.overtime_check_in.isoformat()
                if record.overtime_check_in
                else None
            ),
            "overtime_check_out": (
                record.overtime_check_out.isoformat()
                if record.overtime_check_out
                else None
            ),
            "attendance": (
                AttendanceService.build_attendance_payload(
                    record
                )
            ),
        }