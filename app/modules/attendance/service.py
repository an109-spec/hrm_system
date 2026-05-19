from __future__ import annotations

from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from types import SimpleNamespace
from app.extensions import db
from app.models import (
    Attendance,
    AttendanceStatus,
    Employee,
    Holiday,
    OvertimeRequest,
    LeaveRequest,
    Notification,
)
from app.utils.time import get_current_time
from app.common.exceptions import ValidationError
from app.modules.attendance.dto import AttendanceStateDTO, WorkUnitDTO
from app.constants import WorkingStatus
from app.constants import AttendanceConstants, VN_TIMEZONE, OvertimeConfig, WorkConfig

class AttendanceService:
    @staticmethod
    def get_or_create_today(
        employee_id: int,
        now_dt: datetime,
    ) -> Attendance:
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=VN_TIMEZONE)
        else:
            now_dt = now_dt.astimezone(VN_TIMEZONE)

        today = now_dt.date()

        # =====================================================
        # EXISTING RECORD CHECK
        # =====================================================
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=today,
        ).first()

        if record:
            return record

        # =====================================================
        # EMPLOYEE VALIDATION
        # =====================================================
        employee = Employee.query.get(employee_id)

        if not employee:
            raise ValidationError("Nhân viên không tồn tại")

        if not employee.is_attendance_required:
            raise ValidationError(
                "Nhân viên không thuộc đối tượng chấm công"
            )

        if (employee.working_status or "").strip().lower() == WorkingStatus.RESIGNED:
            raise ValidationError("Nhân viên không còn hoạt động")

        # =====================================================
        # DAY FLAGS
        # =====================================================
        is_weekend = today.weekday() >= 5

        holiday = AttendanceService._get_holiday(today)

        is_holiday = holiday is not None

        leave_request = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "approved",
            LeaveRequest.from_date <= today,
            LeaveRequest.to_date >= today,
        ).first()

        # =====================================================
        # PRIORITY ENGINE
        # leave > holiday > weekend > normal
        # =====================================================
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

        # =====================================================
        # CREATE RECORD
        # =====================================================
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

        # =====================================================
        # CONTEXT FLAGS
        # =====================================================
        record.is_leave_day = bool(leave_request)

        record.is_offday = (
            is_weekend
            or is_holiday
            or bool(leave_request)
        )
        db.session.add(record)
        try:
            db.session.commit()

        except IntegrityError:
            db.session.rollback()

            return Attendance.query.filter_by(
                employee_id=employee_id,
                date=today,
            ).first()
        return record

    @staticmethod
    def get_status(
        status_name: str | None,
    ) -> AttendanceStatus | None:

        normalized = Attendance.ShiftStatus.normalize(
            status_name
        )

        if not Attendance.ShiftStatus.is_valid(normalized):
            return None

        return AttendanceStatus.query.filter_by(
            status_name=normalized
        ).first()
    
    @staticmethod
    def _get_holiday(target_date: date) -> Holiday | None:

        holiday = Holiday.query.filter(
            Holiday.date == target_date,
            Holiday.is_recurring.is_(False),
            Holiday.is_active.is_(True),
        ).first()

        if holiday:
            return holiday

        return Holiday.query.filter(
            Holiday.is_recurring.is_(True),
            Holiday.is_active.is_(True),
            db.extract("month", Holiday.date) == target_date.month,
            db.extract("day", Holiday.date) == target_date.day,
        ).first()

    @staticmethod
    def resolve_attendance_type(
        *,
        is_holiday: bool = False,
        is_weekend: bool = False,
        is_leave: bool = False,
        is_absent: bool = False,
        is_abnormal: bool = False,
    ) -> str:

        mapping = (
            (is_leave, "leave"),
            (is_absent, "absent"),
            (is_abnormal, "abnormal"),
            (is_holiday, "holiday"),
            (is_weekend, "weekend"),
        )

        for condition, attendance_type in mapping:
            if condition:
                return attendance_type

        return "normal"

    @staticmethod
    def calculate_overtime_hours(
        overtime_check_in: datetime | None,
        overtime_check_out: datetime | None,
    ) -> Decimal:

        if not overtime_check_in or not overtime_check_out:
            return Decimal("0.00")

        if overtime_check_in.tzinfo is None:
            overtime_check_in = overtime_check_in.replace(
                tzinfo=VN_TIMEZONE
            )

        if overtime_check_out.tzinfo is None:
            overtime_check_out = overtime_check_out.replace(
                tzinfo=VN_TIMEZONE
            )

        overtime_check_in = overtime_check_in.astimezone(
            VN_TIMEZONE
        )

        overtime_check_out = overtime_check_out.astimezone(
            VN_TIMEZONE
        )

        day = overtime_check_in.date()

        ot_start = datetime.combine(
            day,
            WorkConfig.OT_START,
            tzinfo=VN_TIMEZONE,
        )

        ot_end = datetime.combine(
            day,
            WorkConfig.OT_END,
            tzinfo=VN_TIMEZONE,
        )

        actual_start = max(
            ot_start,
            overtime_check_in,
        )

        actual_end = min(
            ot_end,
            overtime_check_out,
        )

        if actual_end <= actual_start:
            return Decimal("0.00")

        hours = (
            actual_end - actual_start
        ).total_seconds() / 3600

        return Decimal(
            str(round(hours, 4))
        )
    
    @staticmethod
    def finalize_attendance(
        record: Attendance,
        finalize_status: bool = True
    ) -> None:
        regular_hours = Decimal(str(record.regular_hours or 0))
        overtime_hours = Decimal(str(record.overtime_hours or 0)) 

        record.working_hours = (
            regular_hours + overtime_hours
        ).quantize(Decimal("0.01"))
        base_type = AttendanceService._resolve_attendance_type(
            is_weekend=bool(record.is_weekend),
            is_holiday=bool(record.is_holiday),
        )
        if record.is_half_day and base_type == Attendance.Type.NORMAL:
            record.set_attendance_type(Attendance.Type.ABNORMAL)
        else:
            record.set_attendance_type(base_type)
        record.dto_snapshot = {
            "working_hours": str(record.working_hours),
            "regular_hours": str(regular_hours),
            "overtime_hours": str(overtime_hours),
            "attendance_type": record.attendance_type,
            "shift_status": record.shift_status,
        }
        if finalize_status:

            current_state = Attendance.ShiftStatus.normalize(
                record.shift_status
            )
            FINALIZABLE_STATES = {
                Attendance.ShiftStatus.REGULAR_DONE,
                Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                Attendance.ShiftStatus.WORKING_OVERTIME,
                Attendance.ShiftStatus.PRE_OT_REST,
            }
            if current_state in FINALIZABLE_STATES:

                record.set_shift_status(
                    Attendance.ShiftStatus.COMPLETED
                )
                record.is_finalized = True
                record.finalized_at = get_current_time()
        if getattr(record, "is_finalized", False):
            record._mutation_locked = True

    @staticmethod
    def auto_complete_stale_records(
        reference_date: date | None = None
    ) -> int:
        now_dt = get_current_time()
        today = reference_date or now_dt.date()
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
            if (
                Attendance.ShiftStatus.normalize(record.shift_status)
                == Attendance.ShiftStatus.COMPLETED
            ):
                continue
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
                    WorkConfig.WORKDAY_END,
                    tzinfo=VN_TIMEZONE,
                )
                result = AttendanceService.calculate_regular_work_units(
                    record
                )
                record.regular_hours = (
                    result.worked_hours.quantize(
                        Decimal("0.01")
                    )
                )
                record.is_half_day = result.is_half_day
                record.late_minutes = record.late_minutes or 0
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
                    WorkConfig.OT_END,
                    tzinfo=VN_TIMEZONE,
                )
                raw_ot = (
                    AttendanceService.calculate_overtime_hours_raw(
                        record.overtime_check_in,
                        record.overtime_check_out,
                    )
                )
                multiplier = AttendanceService._day_multiplier(
                    bool(record.is_holiday),
                    bool(record.is_weekend),
                )
                record.overtime_hours = (
                    raw_ot * multiplier
                ).quantize(Decimal("0.01"))
            AttendanceService.finalize_attendance(record)
            count += 1
        if count > 0:
            db.session.commit()
        return count

    @staticmethod
    def _to_iso(dt: datetime | None) -> str | None:
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=VN_TIMEZONE)
        return dt.astimezone(VN_TIMEZONE).isoformat()

    @staticmethod
    def build_attendance_payload(record: Attendance) -> dict | None:
        if not record:
            return None
        shift_status = Attendance.ShiftStatus.normalize(
            record.shift_status
        )
        attendance_type = Attendance.Type.normalize(
            record.attendance_type
        )
        regular_raw = AttendanceService.calculate_regular_hours(record)
        overtime_raw = AttendanceService.calculate_overtime_hours(
            record.overtime_check_in,
            record.overtime_check_out
        )
        multiplier = AttendanceService._day_multiplier(
            bool(record.is_holiday),
            bool(record.is_weekend),
        )
        return {
            "date": (
                record.date.isoformat()
                if record.date else None
            ),
            "check_in": AttendanceService._to_iso(record.check_in),
            "check_out": AttendanceService._to_iso(record.check_out),
            "overtime_check_in":
                AttendanceService._to_iso(
                    record.overtime_check_in
                ),
            "overtime_check_out":
                AttendanceService._to_iso(
                    record.overtime_check_out
                ),
            "regular_hours": str(record.regular_hours or 0),
            "overtime_hours": str(record.overtime_hours or 0),
            "working_hours": str(record.working_hours or 0),
            "regular_hours_raw": str(regular_raw),
            "overtime_hours_raw": str(overtime_raw),
            "day_multiplier": str(multiplier),
            "shift_status": shift_status,
            "attendance_type": attendance_type,
            "late_minutes": record.late_minutes or 0,
            "is_half_day": bool(record.is_half_day),
            "is_weekend": bool(record.is_weekend),
            "is_holiday": bool(record.is_holiday),
        }
    
    @staticmethod
    def get_today(
        employee_id: int,
        now_dt: datetime | None = None
    ) -> Attendance | None:
        if now_dt is None:
            now_dt = get_current_time()
            
        target_date = now_dt.date()
        
        # 1. Thử tìm bản ghi đúng ngày hôm nay trước
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=target_date
        ).first()
        
        # 2. LOGIC CA ĐÊM: Nếu không thấy bản ghi hôm nay VÀ đang là sáng sớm (0h - 5h)
        if not record and now_dt.hour < 5:
            yesterday = target_date - timedelta(days=1)
            # Tìm bản ghi ngày hôm qua
            prev_record = Attendance.query.filter_by(
                employee_id=employee_id,
                date=yesterday
            ).first()
            
            # Nếu ngày hôm qua đang dở dang (đang WORKING_OVERTIME hoặc chưa COMPLETED)
            if prev_record:
                status = Attendance.ShiftStatus.normalize(prev_record.shift_status)
                if status in [Attendance.ShiftStatus.WORKING_REGULAR, 
                            Attendance.ShiftStatus.WORKING_OVERTIME,
                            Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED]:
                    record = prev_record

        if record:
            record._normalized_shift_status = (
                Attendance.ShiftStatus.normalize(record.shift_status)
            )
        return record

    @staticmethod
    def get_history(
        employee_id: int,
        limit: int = 10,
        month: int | None = None,
        year: int | None = None,
        now_dt: datetime | None = None,
    ):
        if now_dt is None:
            now_dt = get_current_time()
        today = now_dt.date()
        if not month or not year:
            return (
                Attendance.query.filter(
                    Attendance.employee_id == employee_id,
                    Attendance.date <= today,
                )
                .order_by(
                    Attendance.date.desc()
                )
                .limit(limit)
                .all()
            )
        if month < 1 or month > 12:
            raise ValidationError(
                "Tháng không hợp lệ"
            )
        from calendar import monthrange
        last_day = monthrange(
            year,
            month,
        )[1]
        month_start = date(
            year,
            month,
            1,
        )
        month_end = date(
            year,
            month,
            last_day,
        )
        effective_end = (
            month_end
            if (
                year,
                month,
            ) < (
                today.year,
                today.month,
            )
            else min(
                month_end,
                today,
            )
        )
        if effective_end < month_start:
            return []
        attendance_rows = Attendance.query.filter(
            Attendance.employee_id == employee_id,
            Attendance.date >= month_start,
            Attendance.date <= effective_end,
        ).all()
        attendance_by_date = {
            r.date: r
            for r in attendance_rows
        }
        leave_rows = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "approved",
            LeaveRequest.is_deleted.is_(False),
            LeaveRequest.from_date <= effective_end,
            LeaveRequest.to_date >= month_start,
        ).all()
        leave_dates = set()
        for leave in leave_rows:
            start = max(
                leave.from_date,
                month_start,
            )
            end = min(
                leave.to_date,
                effective_end,
            )
            cur = start
            while cur <= end:
                leave_dates.add(cur)
                cur = cur.fromordinal(
                    cur.toordinal() + 1
                )
        fixed_holidays = Holiday.query.filter(
            Holiday.is_recurring.is_(False),
            Holiday.is_active.is_(True),
            Holiday.date >= month_start,
            Holiday.date <= effective_end,
        ).all()
        recurring_holidays = Holiday.query.filter(
            Holiday.is_recurring.is_(True),
            Holiday.is_active.is_(True),
        ).all()
        holiday_dates = {
            h.date
            for h in fixed_holidays
        }
        for h in recurring_holidays:
            try:
                hd = date(
                    year,
                    month,
                    h.date.day,
                )
                if (
                    month_start
                    <= hd
                    <= effective_end
                ):
                    holiday_dates.add(hd)
            except ValueError:
                continue
        history = []
        current = effective_end
        while current >= month_start:
            if current in attendance_by_date:
                history.append(
                    attendance_by_date[current]
                )
            else:
                is_weekend = (
                    current.weekday() >= 5
                )
                is_holiday = (
                    current in holiday_dates
                )
                is_leave = (
                    current in leave_dates
                )
                if is_leave:
                    shift_status = (
                        Attendance.ShiftStatus.LEAVE
                    )
                    attendance_type = (
                        Attendance.Type.LEAVE_APPROVED
                    )
                elif is_holiday:
                    shift_status = (
                        Attendance.ShiftStatus.HOLIDAY_OFF
                    )
                    attendance_type = (
                        Attendance.Type.HOLIDAY
                    )
                elif is_weekend:
                    shift_status = (
                        Attendance.ShiftStatus.WEEKEND_OFF
                    )
                    attendance_type = (
                        Attendance.Type.WEEKEND
                    )
                else:
                    shift_status = (
                        Attendance.ShiftStatus.ABSENT
                    )
                    attendance_type = (
                        Attendance.Type.ABSENT
                    )
                history.append(
                    SimpleNamespace(
                        id=None,
                        date=current,
                        check_in=None,
                        check_out=None,
                        overtime_check_in=None,
                        overtime_check_out=None,
                        regular_hours=Decimal(
                            "0.00"
                        ),
                        overtime_hours=Decimal(
                            "0.00"
                        ),
                        working_hours=Decimal(
                            "0.00"
                        ),
                        shift_status=(
                            Attendance.ShiftStatus.normalize(
                                shift_status
                            )
                        ),
                        attendance_type=(
                            attendance_type
                        ),
                        late_minutes=0,
                        is_half_day=False,
                        is_weekend=is_weekend,
                        is_holiday=is_holiday,
                    )
                )
            current = current.fromordinal(
                current.toordinal() - 1
            )
        return history
    
    @staticmethod
    def delete_attendance(
        employee_id: int,
        date_str: str
    ) -> date | None:
        from app.utils.time import _normalize
        try:
            parsed_dt = _normalize(date_str)
            if not parsed_dt:
                raise ValueError
            target_date = parsed_dt.date()
        except (TypeError, ValueError):
            raise ValidationError("Ngày không hợp lệ. Định dạng yêu cầu: YYYY-MM-DD")
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=target_date,
        ).first()
        if not record:
            raise ValidationError(f"Không tìm thấy dữ liệu chấm công ngày {target_date}")
        OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == target_date,
        ).delete(synchronize_session=False) 
        employee = Employee.query.get(employee_id)
        if employee and employee.user_id:
            Notification.query.filter(
                Notification.user_id == employee.user_id,
                Notification.type.in_(["attendance", "overtime"]),
                db.func.date(Notification.created_at) >= target_date,
                db.func.date(Notification.created_at) <= target_date + timedelta(days=1)
            ).update({"is_deleted": True}, synchronize_session=False)
        db.session.delete(record)
        db.session.commit()
        last_record = (
            Attendance.query
            .filter_by(employee_id=employee_id)
            .order_by(Attendance.date.desc())
            .first()
        )
        return last_record.date if last_record else None

    @staticmethod
    def delete_notification_cascade(
        notification_id: int,
        user_id: int,
    ) -> dict:
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
                    ot_requests = OvertimeRequest.query.filter(
                        OvertimeRequest.employee_id == employee.id,
                        OvertimeRequest.overtime_date == target_date,
                        OvertimeRequest.is_deleted.is_(False),
                    ).all()
                    for ot in ot_requests:
                        ot.is_deleted = True
                        cascaded.append(
                            f"OT request #{ot.id}"
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
                            if att.is_holiday:
                                att.set_shift_status(
                                    Attendance.ShiftStatus.HOLIDAY_OFF
                                )
                            elif att.is_weekend:
                                att.set_shift_status(
                                    Attendance.ShiftStatus.WEEKEND_OFF
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
            "notification_id": notification_id,
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
        # 0. NOT STARTED (NO RECORD)
        # =====================================================
        if not attendance:
            return AttendanceService._handle_not_started(
                employee_id,
                payload,
                current_time,
            )

        # =====================================================
        # 1. NORMALIZE STATE (SINGLE SOURCE OF TRUTH)
        # =====================================================
        shift_status = Attendance.ShiftStatus.normalize(
            attendance.shift_status
        )

        attendance.shift_status = shift_status  # sync runtime

        # =====================================================
        # 2. IMMUTABLE FINAL STATE
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
        # 3. OFFDAY HARD GATE (PRIORITY HIGHEST)
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
        # 4. NOT CHECKED-IN YET (NORMAL WORK ENTRY)
        # =====================================================
        if attendance.check_in is None:
            return AttendanceService._handle_not_started(
                employee_id,
                payload,
                current_time,
            )

        # =====================================================
        # 5. REGULAR SHIFT FLOW (WORKING)
        # =====================================================
        if shift_status in {
            Attendance.ShiftStatus.WORKING_REGULAR,
            Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED,
        }:
            return AttendanceService._handle_working(
                attendance,
                employee_id,
                payload,
                current_time,
            )

        # =====================================================
        # 6. POST REGULAR SHIFT → OT MACHINE (ONLY PATH)
        # =====================================================
        POST_REGULAR_STATES = {
            Attendance.ShiftStatus.REGULAR_DONE,
            Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
            Attendance.ShiftStatus.PRE_OT_REST,
            Attendance.ShiftStatus.OT_CHECKIN_REQUIRED,
            Attendance.ShiftStatus.WORKING_OVERTIME,
        }

        if shift_status in POST_REGULAR_STATES:
            return AttendanceService._handle_after_checkout(
                attendance,
                employee_id,
                payload,
                current_time,
            )

        # =====================================================
        # 7. FALLBACK (INVALID STATE SAFETY NET)
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
            WorkConfig.WORKDAY_END,
            tzinfo=VN_TIMEZONE,
        )

        lunch_start = datetime.combine(
            today,
            WorkConfig.LUNCH_START,
            tzinfo=VN_TIMEZONE,
        )

        lunch_end = datetime.combine(
            today,
            WorkConfig.LUNCH_END,
            tzinfo=VN_TIMEZONE,
        )

        state = Attendance.ShiftStatus.normalize(
            attendance.shift_status
        )

        early_checkout_confirmed = bool(
            payload.get("early_checkout_confirmed")
        )
        if state not in {
            Attendance.ShiftStatus.WORKING_REGULAR,
            Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED,
        }:
            return {
                "type": "error",
                "action": "invalid_state",
                "attendance_state": state,
                "message": f"Không hợp lệ để xử lý WORKING: {state}",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }
        if lunch_start <= current_time < lunch_end:
            return {
                "type": "info",
                "action": "lunch_break",
                "attendance_state": state,
                "message": "Đang trong giờ nghỉ trưa (12:00–13:00)",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }
        if current_time >= end_of_day:
            return AttendanceService.check_out_regular(
                employee_id=employee_id,
                current_time=current_time,
                early_checkout=False,
            )
        early_minutes = int(
            (end_of_day - current_time).total_seconds() // 60
        )
        if not early_checkout_confirmed:
            return {
                "type": "warning",
                "action": AttendanceService.ACTION_EARLY_CHECKOUT_PROMPT,
                "attendance_state": state,
                "message": (
                    f"Bạn có muốn tan ca sớm không? "
                    f"(sớm {early_minutes} phút)"
                ),
                "requires_confirmation": True,
                "flags": {
                    "early_minutes": early_minutes,
                },
                "attendance": AttendanceService.build_attendance_payload(attendance),
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

        state = Attendance.ShiftStatus.normalize(
            attendance.shift_status
        )

        overtime_decision = str(
            payload.get("overtime_decision") or ""
        ).strip().lower()

        # =========================================================
        # 0. NORMALIZE CURRENT TIME (TIMEZONE SAFE)
        # =========================================================
        if current_time.tzinfo is None:
            current_time = current_time.replace(
                tzinfo=VN_TIMEZONE
            )
        else:
            current_time = current_time.astimezone(
                VN_TIMEZONE
            )

        # =========================================================
        # 1. OT CONTEXT
        # =========================================================
        ot_request = AttendanceService._get_ot_request(
            employee_id,
            current_time.date(),
        )

        ot_status = (
            ot_request.status if ot_request else None
        )

        # =========================================================
        # 2. REGULAR DONE
        # =========================================================
        if state == Attendance.ShiftStatus.REGULAR_DONE:

            if overtime_decision not in {"yes", "no"}:
                return {
                    "type": "warning",
                    "action": AttendanceService.ACTION_OFFER_OVERTIME,
                    "attendance_state": Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                    "overtime_status": ot_status or "NONE",
                    "message": "Bạn có muốn đăng ký tăng ca không?",
                    "requires_overtime_decision": True,
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

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
                    "overtime_status": "REJECTED",
                    "message": "Đã hoàn thành ngày làm việc.",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            return AttendanceService._create_ot_request_pending(
                attendance,
                employee_id,
                current_time,
            )

        # =========================================================
        # 3. PENDING OT DECISION
        # =========================================================
        if state == Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION:

            if ot_status == "approved":

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

            if ot_status in {
                "pending",
                "pending_hr",
                "pending_admin",
            }:
                return {
                    "type": "info",
                    "action": "ot_pending_approval",
                    "attendance_state": state,
                    "overtime_status": "PENDING",
                    "message": "Đang chờ duyệt tăng ca",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            return {
                "type": "warning",
                "action": AttendanceService.ACTION_OFFER_OVERTIME,
                "attendance_state": state,
                "overtime_status": ot_status or "NONE",
                "message": "Chưa có quyết định tăng ca",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        # =========================================================
        # 4. PRE OT REST
        # =========================================================
        if state == Attendance.ShiftStatus.PRE_OT_REST:

            if ot_status != "approved":

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
                    "overtime_status": ot_status,
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
                    "overtime_status": "APPROVED",
                    "message": "Đang trong ca tăng ca",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            ot_open_dt = datetime.combine(
                current_time.date(),
                AttendanceService.OT_CHECKIN_OPEN,
                tzinfo=VN_TIMEZONE,
            )

            if current_time < ot_open_dt:
                return {
                    "type": "info",
                    "action": "pre_ot_rest",
                    "attendance_state": state,
                    "overtime_status": "APPROVED",
                    "message": "Chờ tới giờ OT",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            return AttendanceService.check_in_overtime(
                employee_id,
                current_time,
            )

        # =========================================================
        # 5. WORKING OT
        # =========================================================
        if state == Attendance.ShiftStatus.WORKING_OVERTIME:

            if not attendance.overtime_check_out:

                return AttendanceService.check_out_overtime(
                    employee_id,
                    current_time,
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
                "overtime_status": "DONE",
                "message": "Đã hoàn thành tăng ca",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        # =========================================================
        # 6. SAFE FALLBACK
        # =========================================================
        return {
            "type": "success",
            "action": AttendanceService.ACTION_ALREADY_RECORDED,
            "attendance_state": state,
            "overtime_status": ot_status,
            "message": "Ngày công đã hoàn tất",
            "attendance": AttendanceService.build_attendance_payload(attendance),
        }
    @staticmethod
    def _create_ot_request_pending(
        attendance: Attendance,
        employee_id: int,
        current_time: datetime,
    ) -> dict:

        current_time = current_time.astimezone(VN_TIMEZONE)

        today = current_time.date()

        # =====================================================
        # 1. EXISTING REQUEST CHECK (SOURCE OF TRUTH)
        # =====================================================
        existing = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == today,
            OvertimeRequest.is_deleted.is_(False),
        ).first()

        # =====================================================
        # 2. IF NOT EXISTS → CREATE NEW REQUEST
        # =====================================================
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

                status=OvertimeRequest.Status.PENDING,

                requested_hours=Decimal("3.00"),
                overtime_hours=Decimal("0.00"),

                is_holiday_ot=is_holiday,
                holiday_multiplier=multiplier,

                request_type=OvertimeRequest.RequestType.AFTER_SHIFT,
                reason="Đăng ký tăng ca sau giờ hành chính",
            )

            db.session.add(ot_req)
            db.session.flush()

            attendance.overtime_request_id = ot_req.id

            current_ot_status = ot_req.status

        else:
            attendance.overtime_request_id = existing.id

            current_ot_status = existing.status

        # =====================================================
        # 3. SHIFT STATE UPDATE
        # =====================================================
        attendance.set_shift_status(
            Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION
        )

        # =====================================================
        # 4. TYPE ALIGNMENT
        # =====================================================
        if attendance.is_holiday:
            attendance.set_attendance_type(
                Attendance.Type.HOLIDAY
            )

        elif attendance.is_weekend:
            attendance.set_attendance_type(
                Attendance.Type.WEEKEND
            )

        db.session.commit()

        # =====================================================
        # 5. RESPONSE DTO
        # =====================================================
        return {
            "type": "success",

            "action":
                AttendanceService.ACTION_OVERTIME_REQUEST_CREATED,

            "attendance_state":
                Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,

            "overtime_status": current_ot_status,

            "message":
                "Đã gửi yêu cầu tăng ca. Vui lòng chờ phê duyệt.",

            "attendance":
                AttendanceService.build_attendance_payload(
                    attendance
                ),
        }
    
    @staticmethod
    def _get_approved_ot(employee_id: int, target_date: date) -> OvertimeRequest | None:
        valid_approved_statuses = {
            OvertimeRequest.Status.APPROVED,
            OvertimeRequest.Status.APPROVED_HR,
            OvertimeRequest.Status.APPROVED_ADMIN,
        }
        return OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == target_date,
            OvertimeRequest.is_deleted.is_(False),
            OvertimeRequest.status.in_(valid_approved_statuses),
        ).first()

    @staticmethod
    def handle_ot_approved(
        ot_request: OvertimeRequest,
    ) -> None:
        current_time = (
            get_current_time()
            .astimezone(VN_TIMEZONE)
        )
        attendance = Attendance.query.filter_by(
            employee_id=ot_request.employee_id,
            date=ot_request.overtime_date,
        ).first()
        if attendance:
            current_state = (
                Attendance.ShiftStatus.normalize(
                    attendance.shift_status
                )
            )
            allowed_states = {
                Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                Attendance.ShiftStatus.REGULAR_DONE,
            }
            if current_state in allowed_states:
                attendance.set_shift_status(
                    Attendance.ShiftStatus.PRE_OT_REST
                )
        ot_request.status = (
            OvertimeRequest.Status.APPROVED
        )
        employee = Employee.query.get(
            ot_request.employee_id
        )
        if employee and employee.user_id:
            db.session.add(
                Notification(
                    user_id=employee.user_id,
                    type=Notification.Type.OVERTIME,
                    title="Yêu cầu tăng ca đã được duyệt",
                    content=(
                        f"Yêu cầu tăng ca ngày "
                        f"{ot_request.overtime_date.strftime('%d/%m/%Y')} "
                        f"đã được phê duyệt. "
                        f"Bạn có thể xác thực để bắt đầu tăng ca."
                    ),
                    link="/employee/attendance",
                    created_at=current_time,
                )
            )
        db.session.commit()

    @staticmethod
    def handle_ot_rejected(
        ot_request: OvertimeRequest,
        reason: str = "",
    ) -> None:

        current_time = (
            get_current_time()
            .astimezone(VN_TIMEZONE)
        )

        # =====================================================
        # 1. LOAD ATTENDANCE (SOURCE OF TRUTH)
        # =====================================================
        attendance = Attendance.query.filter_by(
            employee_id=ot_request.employee_id,
            date=ot_request.overtime_date,
        ).first()

        # =====================================================
        # 2. SAFE RESET OT STATE
        # =====================================================
        if attendance:

            current_state = (
                Attendance.ShiftStatus.normalize(
                    attendance.shift_status
                )
            )

            allowed_states = {
                Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                Attendance.ShiftStatus.REGULAR_DONE,
                Attendance.ShiftStatus.PRE_OT_REST,
                Attendance.ShiftStatus.WORKING_OVERTIME,
            }

            if current_state in allowed_states:

                attendance.overtime_check_in = None
                attendance.overtime_check_out = None

                attendance.overtime_hours = Decimal(
                    "0.00"
                )

                attendance.overtime_request_id = None

                # =============================================
                # IMPORTANT:
                # DO NOT MODIFY PAYROLL HOURS HERE
                # =============================================

                attendance.set_shift_status(
                    Attendance.ShiftStatus.REGULAR_DONE
                )

        # =====================================================
        # 3. UPDATE OT REQUEST STATUS
        # =====================================================
        ot_request.status = (
            OvertimeRequest.Status.REJECTED
        )

        # =====================================================
        # 4. ATTENDANCE TYPE SYNC
        # =====================================================
        if attendance:

            if attendance.is_holiday:

                attendance.set_attendance_type(
                    Attendance.Type.HOLIDAY
                )

            elif attendance.is_weekend:

                attendance.set_attendance_type(
                    Attendance.Type.WEEKEND
                )

            else:

                attendance.set_attendance_type(
                    Attendance.Type.NORMAL
                )

        # =====================================================
        # 5. CREATE NOTIFICATION
        # =====================================================
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

                    type=Notification.Type.OVERTIME,

                    title="Yêu cầu tăng ca bị từ chối",

                    content=(
                        f"Yêu cầu tăng ca ngày "
                        f"{ot_request.overtime_date.strftime('%d/%m/%Y')} "
                        f"đã bị từ chối."
                        f"{reason_str}"
                    ),

                    link="/employee/attendance",

                    # =========================================
                    # TIME ENGINE SYNC FIX
                    # =========================================
                    created_at=current_time,
                )
            )
        db.session.commit()

    @staticmethod
    def _handle_offday_logic(
        employee_id: int,
        payload: dict,
        today: date,
    ) -> dict:

        current_time = (
            get_current_time()
            .astimezone(VN_TIMEZONE)
        )

        # =====================================================
        # 0. BASE CONTEXT
        # =====================================================
        is_holiday = AttendanceService._is_holiday(today)

        is_weekend = today.weekday() >= 5

        employee = Employee.query.get(employee_id)

        # =====================================================
        # 1. ELIGIBILITY GATE
        # =====================================================
        if (
            employee
            and employee.is_attendance_required is False
        ):
            return {
                "type": "info",
                "action": "attendance_not_required",
                "attendance_state": "EXEMPT",
                "message": (
                    "Nhân sự này không bắt buộc chấm công."
                ),
                "pass_through": False,
            }

        # =====================================================
        # 2. LEAVE OVERRIDE CHECK
        # =====================================================
        leave = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,

            LeaveRequest.from_date <= today,
            LeaveRequest.to_date >= today,

            LeaveRequest.status == "approved",

            LeaveRequest.is_deleted.is_(False),
        ).first()

        if leave:

            record = AttendanceService.get_or_create_today(
                employee_id=employee_id,
                now_dt=current_time,
            )

            record.set_attendance_type(
                Attendance.Type.LEAVE
            )

            record.set_shift_status(
                Attendance.ShiftStatus.LEAVE
            )

            # =================================================
            # HARD RESET
            # =================================================
            record.check_in = None
            record.check_out = None

            record.overtime_check_in = None
            record.overtime_check_out = None

            record.regular_hours = Decimal("0.00")

            record.overtime_hours = Decimal("0.00")

            record.working_hours = Decimal("0.00")

            AttendanceService.finalize_attendance(
                record,
                finalize_status=True,
            )

            db.session.commit()

            return {
                "type": "info",
                "action": "leave_day",

                "attendance_state": (
                    Attendance.ShiftStatus.LEAVE
                ),

                "message": (
                    "Hôm nay là ngày nghỉ phép đã được duyệt."
                ),

                "attendance": (
                    AttendanceService
                    .build_attendance_payload(record)
                ),

                "final": True,
                "locked_state": True,
            }

        # =====================================================
        # 3. OFFDAY DECLINE FLOW
        # =====================================================
        if (
            bool(payload.get("decline_offday_work"))
            and (is_holiday or is_weekend)
        ):

            record = AttendanceService.get_or_create_today(
                employee_id=employee_id,
                now_dt=current_time,
            )

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

            record.set_attendance_type(
                attendance_type
            )

            record.set_shift_status(
                shift_status
            )

            # =================================================
            # HARD LOCK
            # =================================================
            record.check_in = None
            record.check_out = None

            record.overtime_check_in = None
            record.overtime_check_out = None

            record.regular_hours = Decimal("0.00")

            record.overtime_hours = Decimal("0.00")

            record.working_hours = Decimal("0.00")

            AttendanceService.finalize_attendance(
                record,
                finalize_status=True,
            )

            db.session.commit()

            return {
                "type": "info",

                "status_code": 200,

                "action": (
                    AttendanceService
                    .ACTION_HOLIDAY_OFF
                    if is_holiday
                    else AttendanceService
                    .ACTION_WEEKEND_OFF
                ),

                "attendance_state": (
                    Attendance.ShiftStatus.normalize(
                        record.shift_status
                    )
                ),

                "message": (
                    "Đã ghi nhận nghỉ lễ hôm nay."
                    if is_holiday
                    else "Đã ghi nhận nghỉ cuối tuần hôm nay."
                ),

                "attendance": (
                    AttendanceService
                    .build_attendance_payload(record)
                ),

                "final": True,
                "locked_state": True,
            }

        # =====================================================
        # 4. PASS THROUGH
        # =====================================================
        return {
            "pass_through": True
        }

    @staticmethod
    def check_in(
        employee_id: int,
        current_time: datetime,
        confirm_work: bool = False,
    ) -> dict:

        # =====================================================
        # 0. NORMALIZE CURRENT TIME
        # =====================================================
        now_dt = current_time.astimezone(
            VN_TIMEZONE
        )

        employee = Employee.query.get(employee_id)

        if (
            employee
            and employee.is_attendance_required is False
        ):
            raise ValidationError(
                "Nhân sự này không áp dụng chấm công bắt buộc."
            )

        record = AttendanceService.get_or_create_today(
            employee_id,
            now_dt,
        )

        # =====================================================
        # 1. SOURCE OF TRUTH
        # =====================================================
        normalized_shift = (
            Attendance.ShiftStatus.normalize(
                record.shift_status
            )
        )

        OFFDAY_STATES = {
            Attendance.ShiftStatus.HOLIDAY_OFF,
            Attendance.ShiftStatus.WEEKEND_OFF,
        }

        # =====================================================
        # 2. OFFDAY CONFIRM GATE
        # =====================================================
        if (
            normalized_shift in OFFDAY_STATES
            and not confirm_work
        ):
            return {
                "action": (
                    AttendanceService
                    .ACTION_HOLIDAY_WORK_PROMPT
                    if (
                        normalized_shift
                        == Attendance.ShiftStatus.HOLIDAY_OFF
                    )
                    else AttendanceService
                    .ACTION_WEEKEND_WORK_PROMPT
                ),

                "requires_confirmation": True,

                "attendance_state": normalized_shift,

                "message": (
                    "Hôm nay là ngày nghỉ lễ. "
                    "Bạn có muốn đi làm không?"
                    if (
                        normalized_shift
                        == Attendance.ShiftStatus.HOLIDAY_OFF
                    )
                    else (
                        "Hôm nay là ngày nghỉ cuối tuần. "
                        "Bạn có muốn đi làm không?"
                    )
                ),
            }

        # =====================================================
        # 3. OFFDAY OVERRIDE
        # =====================================================
        if (
            normalized_shift in OFFDAY_STATES
            and confirm_work
        ):

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
        # 4. DUPLICATE CHECK
        # =====================================================
        if record.check_in:
            raise ValidationError(
                "Bạn đã check-in hôm nay."
            )

        # =====================================================
        # 5. STORED CONTEXT
        # =====================================================
        is_weekend = bool(record.is_weekend)

        is_holiday = bool(record.is_holiday)

        # =====================================================
        # 6. CHECK-IN EXECUTION
        # =====================================================
        record.check_in = now_dt

        record.set_shift_status(
            Attendance.ShiftStatus.WORKING_REGULAR
        )

        # =====================================================
        # 7. LATE / HALF DAY
        # =====================================================
        shift_start_dt = datetime.combine(
            now_dt.date(),
            WorkConfig.WORKDAY_START,
            tzinfo=VN_TIMEZONE,
        )

        late_minutes = max(
            0,
            int(
                (
                    now_dt - shift_start_dt
                ).total_seconds() / 60
            )
        )

        record.late_minutes = late_minutes

        half_day_minutes = (
            (
                AttendanceService
                .HALF_DAY_THRESHOLD.hour * 60
                + AttendanceService
                .HALF_DAY_THRESHOLD.minute
            )
            - (
                AttendanceService
                .REGULAR_START.hour * 60
                + AttendanceService
                .REGULAR_START.minute
            )
        )

        record.is_half_day = (
            late_minutes >= half_day_minutes
        )

        # =====================================================
        # 8. STATUS CLASSIFICATION
        # =====================================================
        if record.is_half_day:
            status_name = "HALF_DAY"

        elif late_minutes > 0:
            status_name = "LATE"

        else:
            status_name = "PRESENT"

        db_status = AttendanceService.get_status(
            status_name
        )

        if db_status:
            record.status_id = db_status.id

        # =====================================================
        # 9. ATTENDANCE TYPE
        # =====================================================
        if (
            record.is_half_day
            and not is_weekend
            and not is_holiday
        ):
            record.set_attendance_type(
                Attendance.Type.ABNORMAL
            )

        # =====================================================
        # 10. SAVE
        # =====================================================
        db.session.commit()

        # =====================================================
        # 11. RESPONSE
        # =====================================================
        msg = (
            "Check-in thành công lúc "
            f"{now_dt.strftime('%H:%M:%S')}"
        )

        resp_type = "success"

        multiplier = (
            AttendanceService._day_multiplier(
                is_holiday,
                is_weekend,
            )
        )

        if is_holiday:

            msg += (
                f" (Ngày lễ — công x"
                f"{multiplier.normalize()})"
            )

        elif (
            is_weekend
            and multiplier > 1
        ):

            msg += (
                f" (Cuối tuần — công x"
                f"{multiplier.normalize()})"
            )

        if record.is_half_day:

            msg += (
                f". Đi muộn {late_minutes} phút "
                f"— tính nửa ngày công."
            )

            resp_type = "warning"

        elif late_minutes > 0:

            msg += (
                f". Đi muộn {late_minutes} phút."
            )

            resp_type = "warning"

        return {
            "action": AttendanceService.ACTION_CHECK_IN,

            "type": resp_type,

            "message": msg,

            "attendance_state": (
                Attendance.ShiftStatus.normalize(
                    record.shift_status
                )
            ),

            "attendance": (
                AttendanceService
                .build_attendance_payload(record)
            ),
        }

    @staticmethod
    def check_out_regular(
        employee_id: int,
        current_time: datetime,
        early_checkout: bool = False,
    ) -> dict:

        # =====================================================
        # 0. NORMALIZE CURRENT TIME
        # =====================================================
        now_dt = current_time.astimezone(
            VN_TIMEZONE
        )

        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date(),
        ).first()

        if not record or not record.check_in:
            raise ValidationError(
                "Bạn chưa check-in."
            )

        if record.check_out:
            raise ValidationError(
                "Bạn đã check-out ca chính."
            )

        # =====================================================
        # 1. SET CHECKOUT TIME
        # =====================================================
        record.check_out = now_dt

        # =====================================================
        # 2. CALCULATE RAW WORK
        # =====================================================
        work_result = (
            AttendanceService
            .calculate_regular_work_units(record)
        )

        raw_regular_hours = Decimal(
            str(work_result.worked_hours)
        )

        # =====================================================
        # 3. HALF DAY RULE
        # =====================================================
        if work_result.is_half_day:

            raw_regular_hours = (
                raw_regular_hours
                * Decimal("0.5")
            ).quantize(
                Decimal("0.0001")
            )

        # =====================================================
        # 4. APPLY MULTIPLIER
        # =====================================================
        multiplier = (
            AttendanceService._day_multiplier(
                bool(record.is_holiday),
                bool(record.is_weekend),
            )
        )

        record.regular_hours = (
            raw_regular_hours * multiplier
        ).quantize(
            Decimal("0.01")
        )

        # =====================================================
        # 5. ABNORMAL TYPE
        # =====================================================
        if (
            work_result.is_half_day
            and not record.is_weekend
            and not record.is_holiday
        ):

            record.set_attendance_type(
                Attendance.Type.ABNORMAL
            )

        # =====================================================
        # 6. SHIFT STATE
        # =====================================================
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

        # =====================================================
        # 7. EARLY CHECKOUT FLOW
        # =====================================================
        if early_checkout:

            end_of_day = datetime.combine(
                now_dt.date(),
                WorkConfig.WORKDAY_END,
                tzinfo=VN_TIMEZONE,
            )

            early_minutes = max(
                0,
                int(
                    (
                        end_of_day - now_dt
                    ).total_seconds() // 60
                )
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
                    AttendanceService
                    .ACTION_CHECK_OUT
                ),

                "message": (
                    f"Check-out lúc "
                    f"{now_dt.strftime('%H:%M:%S')}. "
                    f"Về sớm {early_minutes} phút."
                ),

                "attendance_state": (
                    Attendance.ShiftStatus.normalize(
                        record.shift_status
                    )
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
                    AttendanceService
                    .build_attendance_payload(record)
                ),

                "next_event": None,

                "requires_overtime_decision": False,
            }

        # =====================================================
        # 8. NORMAL CHECKOUT FLOW
        # =====================================================
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
                        work_result.is_half_day
                        and not record.is_weekend
                        and not record.is_holiday
                    )
                    else ""
                )
            ),

            "attendance_state": (
                Attendance.ShiftStatus.normalize(
                    record.shift_status
                )
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
                AttendanceService
                .build_attendance_payload(record)
            ),

            "next_event": "offer_overtime",

            "requires_overtime_decision": True,
        }

    @staticmethod
    def check_in_overtime(
        employee_id: int,
        sim_time_str: str | None,
    ) -> dict:

        # =====================================================
        # 0. TIME SOURCE (SIMULATION / REAL CLOCK)
        # =====================================================
        now_dt = AttendanceService.parse_time(sim_time_str)

        if not now_dt:
            raise ValidationError(
                "Không xác định được thời gian tăng ca."
            )

        # =====================================================
        # 1. LOAD ATTENDANCE (SOURCE OF TRUTH)
        # =====================================================
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date(),
        ).first()

        if not record:
            raise ValidationError(
                "Không tìm thấy dữ liệu chấm công hôm nay."
            )

        if not record.check_in:
            raise ValidationError(
                "Bạn chưa check-in ca chính."
            )

        if not record.check_out:
            raise ValidationError(
                "Bạn phải hoàn tất ca chính trước khi OT."
            )

        # =====================================================
        # 2. OT REQUEST VALIDATION
        # =====================================================
        approved_ot = AttendanceService._get_approved_ot(
            employee_id,
            now_dt.date(),
        )

        if not approved_ot:
            raise ValidationError(
                "Yêu cầu tăng ca chưa được phê duyệt."
            )

        valid_ot_statuses = {
            OvertimeRequest.Status.APPROVED,
            OvertimeRequest.Status.APPROVED_HR,
            OvertimeRequest.Status.APPROVED_ADMIN,
        }

        if approved_ot.status not in valid_ot_statuses:
            raise ValidationError(
                "Trạng thái OT không hợp lệ."
            )

        # =====================================================
        # 3. DUPLICATE GUARD
        # =====================================================
        if record.overtime_check_in:
            raise ValidationError(
                "Bạn đã check-in OT rồi."
            )

        # =====================================================
        # 4. STATE MACHINE VALIDATION
        # =====================================================
        normalized_shift = Attendance.ShiftStatus.normalize(
            record.shift_status
        )

        allowed_states = {
            Attendance.ShiftStatus.PRE_OT_REST,
            Attendance.ShiftStatus.OT_CHECKIN_REQUIRED,
        }

        if normalized_shift not in allowed_states:
            raise ValidationError(
                "Không thể bắt đầu tăng ca ở trạng thái hiện tại."
            )

        # =====================================================
        # 5. TIME WINDOW VALIDATION
        # =====================================================
        ot_open_dt = datetime.combine(
            now_dt.date(),
            WorkConfig.OT_START,
            tzinfo=now_dt.tzinfo,
        )

        if now_dt < record.check_out:
            raise ValidationError(
                "Thời gian OT không hợp lệ."
            )

        # =====================================================
        # 6. OT CHECK-IN EXECUTION
        # =====================================================
        record.overtime_check_in = now_dt
        record.overtime_request_id = approved_ot.id

        # =====================================================
        # 7. SHIFT TRANSITION
        # =====================================================
        if now_dt < ot_open_dt:

            record.set_shift_status(
                Attendance.ShiftStatus.PRE_OT_REST
            )

            msg = (
                f"Đã xác thực tăng ca lúc "
                f"{now_dt.strftime('%H:%M:%S')}. "
                f"Công OT sẽ bắt đầu từ "
                f"{WorkConfig.OT_START.strftime('%H:%M:%S')}."
            )

        else:

            record.set_shift_status(
                Attendance.ShiftStatus.WORKING_OVERTIME
            )

            msg = (
                f"Check-in tăng ca thành công lúc "
                f"{now_dt.strftime('%H:%M:%S')}."
            )

        # =====================================================
        # 8. DTO / STATE SYNC
        # =====================================================
        record.overtime_status = approved_ot.status

        db.session.commit()

        # =====================================================
        # 9. RESPONSE
        # =====================================================
        return {
            "type": "success",
            "action": AttendanceService.ACTION_CHECK_IN_OT,
            "message": msg,

            "attendance_state": (
                Attendance.ShiftStatus.normalize(
                    record.shift_status
                )
            ),

            "overtime_status": approved_ot.status,

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

        # =====================================================
        # 0. TIME SOURCE (SIMULATION / REAL CLOCK)
        # =====================================================
        now_dt = AttendanceService.parse_time(sim_time_str)

        if not now_dt:
            raise ValidationError(
                "Không xác định được thời gian OT."
            )

        # =====================================================
        # 1. LOAD ATTENDANCE
        # =====================================================
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date(),
        ).first()

        if not record:
            raise ValidationError(
                "Không tìm thấy dữ liệu chấm công."
            )

        # =====================================================
        # 2. VALIDATION GATE
        # =====================================================
        if not record.overtime_check_in:
            raise ValidationError(
                "Bạn chưa check-in tăng ca."
            )

        if record.overtime_check_out:
            raise ValidationError(
                "Bạn đã check-out OT rồi."
            )

        normalized_shift = Attendance.ShiftStatus.normalize(
            record.shift_status
        )

        allowed_states = {
            Attendance.ShiftStatus.WORKING_OVERTIME,
            Attendance.ShiftStatus.PRE_OT_REST,
        }

        if normalized_shift not in allowed_states:
            raise ValidationError(
                "Không thể kết thúc OT ở trạng thái hiện tại."
            )

        # =====================================================
        # 3. APPROVED OT VALIDATION
        # =====================================================
        approved_ot = AttendanceService._get_approved_ot(
            employee_id,
            now_dt.date(),
        )

        if not approved_ot:
            raise ValidationError(
                "Yêu cầu tăng ca không tồn tại hoặc chưa được duyệt."
            )

        valid_ot_statuses = {
            OvertimeRequest.Status.APPROVED,
            OvertimeRequest.Status.APPROVED_HR,
            OvertimeRequest.Status.APPROVED_ADMIN,
        }

        if approved_ot.status not in valid_ot_statuses:
            raise ValidationError(
                "Trạng thái OT không hợp lệ."
            )

        # =====================================================
        # 4. TIME PARADOX PROTECTION
        # =====================================================
        if now_dt < record.overtime_check_in:
            raise ValidationError(
                "Thời gian OT không hợp lệ."
            )

        # =====================================================
        # 5. STRICT OT END LIMIT (TIMEZONE SAFE)
        # =====================================================
        ot_end_dt = datetime.combine(
            now_dt.date(),
            WorkConfig.OT_END,
            tzinfo=now_dt.tzinfo,
        )

        final_ot_time = min(
            now_dt,
            ot_end_dt,
        )

        record.overtime_check_out = final_ot_time

        # =====================================================
        # 6. RAW OT CALCULATION
        # =====================================================
        raw_ot = AttendanceService.calculate_overtime_hours_raw(
            record.overtime_check_in,
            record.overtime_check_out,
        )

        if raw_ot < AttendanceService.MIN_OT_HOURS:
            raw_ot = Decimal("0.00")

        # =====================================================
        # 7. OT MULTIPLIER
        # =====================================================
        multiplier = Decimal(
            str(
                approved_ot.holiday_multiplier
                or AttendanceService._day_multiplier(
                    bool(record.is_holiday),
                    bool(record.is_weekend),
                )
            )
        )

        record.overtime_hours = (
            raw_ot * multiplier
        ).quantize(Decimal("0.01"))

        # =====================================================
        # 8. FINALIZE ATTENDANCE
        # =====================================================
        AttendanceService.finalize_attendance(
            record,
            finalize_status=True,
        )

        # =====================================================
        # 9. TYPE CONSISTENCY
        # =====================================================
        if record.is_holiday:
            record.set_attendance_type(
                Attendance.Type.HOLIDAY
            )

        elif record.is_weekend:
            record.set_attendance_type(
                Attendance.Type.WEEKEND
            )

        # =====================================================
        # 10. STATE + DTO SYNC
        # =====================================================
        record.set_shift_status(
            Attendance.ShiftStatus.COMPLETED
        )

        record.overtime_status = approved_ot.status

        db.session.commit()

        multiplier_label = (
            f" (x{multiplier.normalize()})"
            if multiplier > 1
            else ""
        )

        # =====================================================
        # 11. RESPONSE
        # =====================================================
        return {
            "type": "success",

            "action": AttendanceService.ACTION_CHECK_OUT_OT,

            "message": (
                "Đã hoàn thành tăng ca. "
                f"OT: {record.overtime_hours}h"
                f"{multiplier_label}"
            ),

            "attendance_state": (
                Attendance.ShiftStatus.normalize(
                    record.shift_status
                )
            ),

            "overtime_status": approved_ot.status,

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
    
    @staticmethod
    def process_overtime_reset_from_notification(user_id: int, employee_id: int, noti_id: int) -> dict:
        noti = Notification.query.filter_by(id=noti_id, user_id=user_id, is_deleted=False).first()
        if not noti:
            raise ValueError("Không tìm thấy dữ liệu thông báo hợp lệ")
        anchor_time = noti.created_at or noti.updated_at
        row = (
            OvertimeRequest.query.filter_by(employee_id=employee_id)
            .filter(OvertimeRequest.created_at <= anchor_time)
            .order_by(OvertimeRequest.created_at.desc())
            .first()
        )
        if not row:
            if not noti.is_deleted:
                noti.is_deleted = True
                db.session.commit()
            return {
                "success": True,  
                "already_deleted": True,
                "message": "Đơn yêu cầu tăng ca liên quan đã được xóa từ trước."
            }
        from app.modules import reset_overtime_request_flow 
        result = reset_overtime_request_flow(
            overtime_request=row,
            actor_user_id=user_id,
            source="employee",
            anchor_notification_id=noti.id
        )
        return result