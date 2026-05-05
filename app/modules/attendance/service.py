from datetime import datetime, time
from decimal import Decimal

from flask import session

from app.extensions import db
from app.models import Attendance, AttendanceStatus, Employee, Holiday, OvertimeRequest
from app.common.exceptions import ValidationError


class AttendanceService:

    REGULAR_START = time(8, 0, 0)
    REGULAR_END = time(17, 0, 0)

    LUNCH_START = time(12, 0, 0)
    LUNCH_END = time(13, 0, 0)

    HALF_DAY_THRESHOLD = time(9, 0, 0)

    OT_START = time(19, 0, 0)
    OT_END = time(22, 0, 0)

    ACTION_CHECK_IN = "check_in"
    ACTION_CHECK_OUT = "check_out"
    ACTION_CHECK_IN_OT = "check_in_overtime"
    ACTION_CHECK_OUT_OT = "check_out_overtime"
    ACTION_HOLIDAY_WORK_PROMPT = "holiday_work_prompt"
    ACTION_WEEKEND_WORK_PROMPT = "weekend_work_prompt"
    ACTION_EARLY_CHECKOUT_PROMPT = "early_checkout_prompt"
    ACTION_OFFER_OVERTIME = "offer_overtime"
    ACTION_ALREADY_RECORDED = "already_recorded"
    ACTION_OVERTIME_DECISION_RECORDED = "overtime_decision_recorded"
    ACTION_HOLIDAY_OFF = "holiday_off"
    ACTION_WEEKEND_OFF = "weekend_off"
    
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
        record = Attendance.query.filter_by(employee_id=employee_id, date=now_dt.date()).first()

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
        db.session.flush()

        return record

    @staticmethod
    def get_status(status_name: str):
        return AttendanceStatus.query.filter_by(status_name=status_name).first()

    @staticmethod
    def _is_holiday(target_date):
        exact_holiday = Holiday.query.filter_by(date=target_date).first()
        if exact_holiday:
            return True

        recurring_holiday = (
            Holiday.query.filter_by(is_recurring=True)
            .filter(db.extract("month", Holiday.date) == target_date.month)
            .filter(db.extract("day", Holiday.date) == target_date.day)
            .first()
        )
        return bool(recurring_holiday)


    @staticmethod
    def calculate_regular_hours(check_in: datetime, check_out: datetime) -> Decimal:
        if not check_in or not check_out:
            return Decimal("0.00")

        day = check_in.date()

        shift_start = datetime.combine(day, AttendanceService.REGULAR_START)
        shift_end = datetime.combine(day, AttendanceService.REGULAR_END)

        lunch_start = datetime.combine(day, AttendanceService.LUNCH_START)
        lunch_end = datetime.combine(day, AttendanceService.LUNCH_END)

        actual_end = min(check_out, shift_end)
        actual_start = shift_start if check_in < shift_start else check_in
        if actual_end <= actual_start:
            return Decimal("0.00")

        late_minutes = max(0, int((check_in - shift_start).total_seconds() / 60))
        total_seconds = (actual_end - actual_start).total_seconds()

        # trừ nghỉ trưa nếu overlap
        overlap_start = max(actual_start, lunch_start)
        overlap_end = min(actual_end, lunch_end)
        lunch_seconds = (overlap_end - overlap_start).total_seconds() if overlap_end > overlap_start else 0

        hours = (total_seconds - lunch_seconds) / 3600
        if late_minutes >= 60:
            return Decimal(str(round(max(0, min(hours, 4)), 3)))

        return Decimal(str(round(max(0, hours), 3)))
    @staticmethod
    def recalculate_hours(check_in: datetime, check_out: datetime) -> Decimal:
        return AttendanceService.calculate_regular_hours(check_in, check_out)

    @staticmethod
    def calculate_overtime_hours(overtime_check_in: datetime, overtime_check_out: datetime) -> Decimal:

        if not overtime_check_in or not overtime_check_out:
            return Decimal("0.00")
        if overtime_check_in.tzinfo is not None:
            overtime_check_in = overtime_check_in.replace(tzinfo=None)
        if overtime_check_out.tzinfo is not None:
            overtime_check_out = overtime_check_out.replace(tzinfo=None)

        day = overtime_check_in.date()

        ot_start = datetime.combine(day, AttendanceService.OT_START)
        ot_end = datetime.combine(day, AttendanceService.OT_END)

        actual_start = max(ot_start, overtime_check_in)
        actual_end = min(ot_end, overtime_check_out)

        if actual_end <= actual_start:
            return Decimal("0.00")

        hours = (actual_end - actual_start).total_seconds() / 3600

        return Decimal(str(round(hours, 2)))
    @staticmethod
    def _resolve_attendance_type(is_weekend: bool, is_holiday: bool, has_overtime: bool = False) -> str:
        if is_holiday:
            return Attendance.Type.HOLIDAY
        if has_overtime:
            return Attendance.Type.OVERTIME
        if is_weekend:
            return Attendance.Type.WEEKEND
        return Attendance.Type.NORMAL

    @staticmethod
    def process_employee_action(employee_id: int, payload: dict, current_time: datetime) -> dict:
        today = current_time.date()
        sim_time_str = current_time.isoformat()
        attendance = Attendance.query.filter_by(employee_id=employee_id, date=today).first()

        if attendance and attendance.check_out:
            approved_ot_request = OvertimeRequest.query.filter(
                OvertimeRequest.employee_id == employee_id,
                OvertimeRequest.overtime_date == today,
                OvertimeRequest.is_deleted.is_(False),
                OvertimeRequest.status == "approved",
            ).order_by(OvertimeRequest.updated_at.desc()).first()

            overtime_decision = str(payload.get("overtime_decision") or "").strip().lower()
            if attendance.shift_status == Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION:
                if overtime_decision not in {"yes", "no"}:
                    return {
                        "type": "warning",
                        "status_code": 202,
                        "action": AttendanceService.ACTION_OFFER_OVERTIME,
                        "state": Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                        "message": "Bạn có muốn tăng ca hôm nay không?",
                        "flags": {"requires_overtime_decision": True},
                    }
                attendance.set_shift_status(
                    Attendance.ShiftStatus.PRE_OT_REST if overtime_decision == "yes" else Attendance.ShiftStatus.COMPLETED
                )
                db.session.commit()
                return {
                    "type": "success",
                    "status_code": 200,
                    "action": AttendanceService.ACTION_OVERTIME_DECISION_RECORDED,
                    "state": attendance.shift_status,
                    "message": "Đã ghi nhận lựa chọn tăng ca." if overtime_decision == "yes" else "Đã ghi nhận không tăng ca hôm nay.",
                    "flags": {},
                }
            if approved_ot_request:
                if not attendance.overtime_check_in:
                    result = AttendanceService.check_in_overtime(employee_id, sim_time_str)
                    return {"type": "success", "status_code": 200, **result, "state": result.get("attendance_state"), "flags": {}}
                if not attendance.overtime_check_out:
                    result = AttendanceService.check_out_overtime(employee_id, sim_time_str)
                    return {"type": "success", "status_code": 200, **result, "state": result.get("attendance_state"), "flags": {}}

            return {
                "type": "success",
                "status_code": 200,
                "action": AttendanceService.ACTION_ALREADY_RECORDED,
                "state": attendance.shift_status,
                "message": "QR hợp lệ. Hôm nay bạn đã hoàn thành chấm công trước đó.",
                "flags": {},
            }

        if attendance and attendance.check_in and not attendance.check_out:
            end_of_day = datetime.combine(today, AttendanceService.REGULAR_END)
            early_checkout_confirmed = bool(payload.get("early_checkout_confirmed"))
            if current_time < end_of_day and not early_checkout_confirmed:
                early_minutes_preview = int((end_of_day - current_time).total_seconds() // 60)
                return {
                    "type": "warning",
                    "status_code": 200,
                    "action": AttendanceService.ACTION_EARLY_CHECKOUT_PROMPT,
                    "state": attendance.shift_status,
                    "message": f"Bạn có muốn tan ca nghỉ sớm không? (sớm {early_minutes_preview} phút)",
                    "flags": {"early_minutes": early_minutes_preview},
                }

            result = AttendanceService.check_out_regular(employee_id, sim_time_str)
            if attendance.shift_status != Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION:
                attendance.set_shift_status(Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION)
                db.session.commit()
            result["attendance_state"] = Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION
            return {
                "type": "success",
                "status_code": 200,
                **result,
                "state": Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                "flags": {"next_event": AttendanceService.ACTION_OFFER_OVERTIME, "requires_overtime_decision": True},
            }

        confirm_work_on_offday = bool(payload.get("confirm_work_on_offday")) or bool(payload.get("overtime_confirmed"))
        if bool(payload.get("decline_offday_work")):
            today_holiday = AttendanceService._is_holiday(today)
            is_weekend = today.weekday() >= 5
            if today_holiday or is_weekend:
                return {
                    "type": "info",
                    "status_code": 200,
                    "action": AttendanceService.ACTION_HOLIDAY_OFF if today_holiday else AttendanceService.ACTION_WEEKEND_OFF,
                    "state": Attendance.ShiftStatus.HOLIDAY_OFF if today_holiday else Attendance.ShiftStatus.WEEKEND_OFF,
                    "message": "Đã ghi nhận nghỉ lễ hôm nay." if today_holiday else "Đã ghi nhận nghỉ cuối tuần hôm nay.",
                    "flags": {},
                }

        result = AttendanceService.check_in(employee_id, sim_time_str, confirm_work_on_offday)
        response_type = "warning" if result.get("action") in {
            AttendanceService.ACTION_HOLIDAY_WORK_PROMPT,
            AttendanceService.ACTION_WEEKEND_WORK_PROMPT,
        } else "success"
        return {"type": response_type, "status_code": 200, **result, "state": result.get("attendance_state"), "flags": {}}
    @staticmethod
    def check_in(employee_id: int, sim_time_str: str | None, confirm_work_on_offday: bool = False):
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
                "action": AttendanceService.ACTION_HOLIDAY_WORK_PROMPT if is_holiday else AttendanceService.ACTION_WEEKEND_WORK_PROMPT,
                "requires_confirmation": True,
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "message": (
                    "Hôm nay là ngày nghỉ lễ, bạn đang được nghỉ phép. Bạn có muốn đi làm ngày lễ không?"
                    if is_holiday
                    else "Hôm nay là ngày nghỉ cuối tuần. Bạn có muốn đi làm không?"
                )
            }

        record.is_weekend = is_weekend
        record.is_holiday = is_holiday
        record.set_attendance_type(AttendanceService._resolve_attendance_type(is_weekend, is_holiday, False))
        record.check_in = now_dt
        record.set_shift_status(Attendance.ShiftStatus.WORKING_REGULAR)
        late_minutes = max(0, int((now_dt - datetime.combine(now_dt.date(), AttendanceService.REGULAR_START)).total_seconds() / 60))
        record.late_minutes = late_minutes

        record.is_half_day = late_minutes >= 60

        status_name = "LATE" if late_minutes > 0 else "PRESENT"
        status = AttendanceService.get_status(status_name)

        if status:
            record.status_id = status.id

        db.session.commit()

        return {
            "action": AttendanceService.ACTION_CHECK_IN,
            "message": f"Check-in thành công lúc {now_dt.strftime('%H:%M:%S')}",
            "attendance_state": record.shift_status,
            "check_in": record.check_in.isoformat() if record.check_in else None,
        }

    @staticmethod
    def check_out_regular(employee_id: int, sim_time_str: str | None):
        now_dt = AttendanceService.parse_time(sim_time_str)

        record = Attendance.query.filter_by(employee_id=employee_id, date=now_dt.date()).first()
        if not record or not record.check_in:
            raise ValidationError("Bạn chưa check-in.")

        if record.check_out:
            raise ValidationError("Bạn đã check-out ca chính.")

        record.check_out = now_dt
        record.regular_hours = AttendanceService.calculate_regular_hours(record.check_in, record.check_out)
        record.set_shift_status(Attendance.ShiftStatus.REGULAR_DONE)
        AttendanceService.finalize_attendance(record, finalize_status=False)

        db.session.commit()

        return {
            "action": AttendanceService.ACTION_CHECK_OUT,
            "message": f"Check-out ca chính thành công. Công thường: {record.regular_hours}h",
            "attendance_state": record.shift_status,
            "check_in": record.check_in.isoformat() if record.check_in else None,
            "check_out": record.check_out.isoformat() if record.check_out else None,
            "regular_hours": str(record.regular_hours or 0),
            "overtime_hours": str(record.overtime_hours or 0),
            "working_hours": str(record.working_hours or 0),
        }

    # =========================================================
    # CHECK IN OT
    # =========================================================

    @staticmethod
    def check_in_overtime(employee_id: int, sim_time_str: str | None):
        now_dt = AttendanceService.parse_time(sim_time_str)

        record = Attendance.query.filter_by(employee_id=employee_id, date=now_dt.date()).first()

        if not record or not record.check_out:
            raise ValidationError("Bạn phải hoàn tất ca chính trước khi OT.")
        if record.check_out.time() < AttendanceService.REGULAR_END:
            raise ValidationError("Bạn chỉ có thể bắt đầu OT sau khi checkout ca chính từ 17:00.")

        approved_ot_request = OvertimeRequest.query.filter_by(
            employee_id=employee_id,
            overtime_date=now_dt.date(),
            is_deleted=False,
        ).filter(OvertimeRequest.status == "approved").first()
        if not approved_ot_request:
            raise ValidationError("Bạn chưa có đơn OT đã được HR/Admin duyệt cho hôm nay.")
        if record.overtime_check_in:
            raise ValidationError("Bạn đã check-in OT.")

        record.overtime_check_in = now_dt
        if now_dt.time() < AttendanceService.OT_START:
            record.set_shift_status(Attendance.ShiftStatus.PRE_OT_REST)
        else:
            record.set_shift_status(Attendance.ShiftStatus.WORKING_OVERTIME)

        db.session.commit()

        return {
            "action": AttendanceService.ACTION_CHECK_IN_OT,
            "message": f"Check-in OT lúc {now_dt.strftime('%H:%M:%S')}",
            "attendance_state": record.shift_status,
            "overtime_check_in": record.overtime_check_in.isoformat() if record.overtime_check_in else None,
        }

    @staticmethod
    def check_out_overtime(employee_id: int, sim_time_str: str | None):
        now_dt = AttendanceService.parse_time(sim_time_str)

        record = Attendance.query.filter_by(employee_id=employee_id, date=now_dt.date()).first()

        if not record or not record.overtime_check_in:
            raise ValidationError("Bạn chưa check-in OT.")

        if record.overtime_check_out:
            raise ValidationError("Bạn đã check-out OT.")

        record.overtime_check_out = now_dt
        record.overtime_hours = AttendanceService.calculate_overtime_hours(record.overtime_check_in, record.overtime_check_out)
        AttendanceService.finalize_attendance(record, finalize_status=True)

        db.session.commit()

        return {
            "action": AttendanceService.ACTION_CHECK_OUT_OT,
            "message": f"Check-out OT thành công. Tăng ca: {record.overtime_hours}h",
            "attendance_state": record.shift_status,
            "overtime_hours": str(record.overtime_hours or 0),
            "overtime_check_in": record.overtime_check_in.isoformat() if record.overtime_check_in else None,
            "overtime_check_out": record.overtime_check_out.isoformat() if record.overtime_check_out else None,
            "working_hours": str(record.working_hours or 0),
        }

    @staticmethod
    def finalize_attendance(record: Attendance, finalize_status: bool = True):
        regular_hours = Decimal(str(record.regular_hours or 0))
        overtime_hours = Decimal(str(record.overtime_hours or 0))
        total = regular_hours + overtime_hours
        record.working_hours = total.quantize(Decimal("0.01"))

        has_overtime = overtime_hours > 0
        record.set_attendance_type(
            AttendanceService._resolve_attendance_type(
                bool(record.is_weekend),
                bool(record.is_holiday),
                has_overtime,
            )
        )
        if finalize_status:
            record.set_shift_status(Attendance.ShiftStatus.COMPLETED)
    @staticmethod
    def get_today(employee_id: int, sim_time_str: str = None):
        sim_time_str = sim_time_str or session.get("simulated_now")
        now_dt = AttendanceService.parse_time(sim_time_str)

        return Attendance.query.filter_by(employee_id=employee_id, date=now_dt.date()).first()

    @staticmethod
    def get_history(employee_id: int, sim_time_str=None, limit=10):
        sim_time_str = sim_time_str or session.get("simulated_now")
        now_dt = AttendanceService.parse_time(sim_time_str)

        return Attendance.query.filter(
            Attendance.employee_id == employee_id,
            Attendance.date <= now_dt.date()
        ).order_by(Attendance.date.desc()).limit(limit).all()

    @staticmethod
    def delete_attendance(employee_id: int, date_str: str):
        try:
            target_date = datetime.fromisoformat(date_str).date()
        except (TypeError, ValueError):
            raise ValidationError("Ngày không hợp lệ. Dùng định dạng YYYY-MM-DD")

        record = Attendance.query.filter_by(employee_id=employee_id, date=target_date).first()

        if not record:
            raise ValidationError("Không tìm thấy dữ liệu chấm công trong ngày đã chọn")
        from app.models import Employee, Notification

        employee = Employee.query.filter_by(id=employee_id).first()
        related_notifications = []
        if employee and employee.user_id:
            related_notifications = (
                Notification.query.filter(
                    Notification.user_id == employee.user_id,
                    Notification.is_deleted.is_(False),
                    Notification.type.in_(["attendance", "overtime"]),
                    db.func.date(Notification.created_at) == target_date,
                ).all()
            )

        for notification in related_notifications:
            notification.is_deleted = True

        db.session.delete(record)
        db.session.commit()

        last_record = Attendance.query.filter_by(employee_id=employee_id).order_by(Attendance.date.desc()).first()
        return last_record.date if last_record else None