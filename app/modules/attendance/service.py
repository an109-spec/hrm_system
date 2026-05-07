# app/modules/attendance/service.py
from __future__ import annotations

from datetime import datetime, time, date
from calendar import monthrange
from types import SimpleNamespace
from decimal import Decimal

from flask import session

from app.extensions import db
from app.models import Attendance, AttendanceStatus, Employee, Holiday, OvertimeRequest, LeaveRequest
from app.common.exceptions import ValidationError

# Hệ số công ngày lễ / cuối tuần (theo spec: x3)
HOLIDAY_MULTIPLIER = Decimal("3.00")
WEEKEND_MULTIPLIER = Decimal("3.00")


class AttendanceService:
    # =========================================================
    # CONFIG
    # =========================================================
    MIN_OT_REST_MINUTES = 30
    REGULAR_START    = time(8,  0, 0)
    REGULAR_END      = time(17, 0, 0)
    LUNCH_START      = time(12, 0, 0)
    LUNCH_END        = time(13, 0, 0)
    HALF_DAY_THRESHOLD = time(9, 0, 0)
    OT_START         = time(19, 0, 0)
    OT_END           = time(22, 0, 0)
    OT_EARLY_CHECKIN = time(18, 30, 0)

    # =========================================================
    # ACTION CONSTANTS
    # =========================================================
    ACTION_CHECK_IN                   = "check_in"
    ACTION_CHECK_OUT                  = "check_out"
    ACTION_CHECK_IN_OT                = "check_in_overtime"
    ACTION_CHECK_OUT_OT               = "check_out_overtime"
    ACTION_HOLIDAY_WORK_PROMPT        = "holiday_work_prompt"
    ACTION_WEEKEND_WORK_PROMPT        = "weekend_work_prompt"
    ACTION_EARLY_CHECKOUT_PROMPT      = "early_checkout_prompt"
    ACTION_OFFER_OVERTIME             = "offer_overtime"
    ACTION_ALREADY_RECORDED           = "already_recorded"
    ACTION_OVERTIME_REQUEST_CREATED   = "overtime_request_created"
    ACTION_COMPLETE_WITHOUT_OT        = "complete_without_overtime"
    ACTION_HOLIDAY_OFF                = "holiday_off"
    ACTION_WEEKEND_OFF                = "weekend_off"
    ACTION_OVERTIME_DECISION_RECORDED = "overtime_decision_recorded"

    # =========================================================
    # HELPERS
    # =========================================================

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
        db.session.flush()
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
        """Trả về hệ số nhân công theo loại ngày."""
        if is_holiday:
            return HOLIDAY_MULTIPLIER
        if is_weekend:
            return WEEKEND_MULTIPLIER
        return Decimal("1.00")

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

    # =========================================================
    # HOUR CALCULATIONS
    # =========================================================

    @staticmethod
    def calculate_regular_hours_raw(check_in: datetime, check_out: datetime) -> Decimal:
        """
        Tính công ca chính CHƯA nhân hệ số.
        - Bắt đầu: max(check_in, 08:00)  → check-in sớm vẫn tính từ 8h
        - Kết thúc: min(check_out, 17:00) → check-out muộn vẫn chỉ tính đến 17h
        - Trừ nghỉ trưa 12:00–13:00 nếu overlap
        """
        if not check_in or not check_out:
            return Decimal("0.00")

        day        = check_in.date()
        shift_start = datetime.combine(day, AttendanceService.REGULAR_START)
        shift_end   = datetime.combine(day, AttendanceService.REGULAR_END)
        lunch_start = datetime.combine(day, AttendanceService.LUNCH_START)
        lunch_end   = datetime.combine(day, AttendanceService.LUNCH_END)

        actual_start = max(check_in, shift_start)   # check-in sớm → tính từ 8h
        actual_end   = min(check_out, shift_end)     # check-out muộn → chỉ đến 17h

        if actual_end <= actual_start:
            return Decimal("0.00")

        total_seconds = (actual_end - actual_start).total_seconds()

        # Trừ nghỉ trưa
        overlap_start = max(actual_start, lunch_start)
        overlap_end   = min(actual_end,   lunch_end)
        lunch_seconds = (
            (overlap_end - overlap_start).total_seconds()
            if overlap_end > overlap_start
            else 0
        )

        hours = (total_seconds - lunch_seconds) / 3600
        return Decimal(str(round(max(0, hours), 3)))

    @staticmethod
    def calculate_regular_hours(check_in: datetime, check_out: datetime) -> Decimal:
        """Alias để tương thích — trả về công RAW (chưa nhân hệ số)."""
        return AttendanceService.calculate_regular_hours_raw(check_in, check_out)

    @staticmethod
    def recalculate_hours(check_in: datetime, check_out: datetime) -> Decimal:
        return AttendanceService.calculate_regular_hours_raw(check_in, check_out)

    @staticmethod
    def calculate_overtime_hours_raw(
        overtime_check_in: datetime, overtime_check_out: datetime
    ) -> Decimal:
        """
        Tính công OT CHƯA nhân hệ số.
        - Chỉ tính trong khung 19:00–22:00
        - check-in trước 19h → tính từ 19h
        - check-out sau 22h → chỉ tính đến 22h
        """
        if not overtime_check_in or not overtime_check_out:
            return Decimal("0.00")
        if overtime_check_in.tzinfo is not None:
            overtime_check_in  = overtime_check_in.replace(tzinfo=None)
        if overtime_check_out.tzinfo is not None:
            overtime_check_out = overtime_check_out.replace(tzinfo=None)

        day      = overtime_check_in.date()
        ot_start = datetime.combine(day, AttendanceService.OT_START)
        ot_end   = datetime.combine(day, AttendanceService.OT_END)

        actual_start = max(ot_start, overtime_check_in)
        actual_end   = min(ot_end,   overtime_check_out)

        if actual_end <= actual_start:
            return Decimal("0.00")

        hours = (actual_end - actual_start).total_seconds() / 3600
        return Decimal(str(round(hours, 2)))

    @staticmethod
    def calculate_overtime_hours(
        overtime_check_in: datetime, overtime_check_out: datetime
    ) -> Decimal:
        """Alias để tương thích."""
        return AttendanceService.calculate_overtime_hours_raw(overtime_check_in, overtime_check_out)

    # =========================================================
    # FINALIZE
    # =========================================================

    @staticmethod
    def finalize_attendance(record: Attendance, finalize_status: bool = True) -> None:
        """
        Tính lại working_hours = regular_hours + overtime_hours.
        regular_hours và overtime_hours đã bao gồm hệ số nhân (được set khi checkout).
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

    # =========================================================
    # BUILD PAYLOAD
    # =========================================================

    @staticmethod
    def build_attendance_payload(record: Attendance) -> dict | None:
        if not record:
            return None
        multiplier = float(
            AttendanceService._day_multiplier(
                bool(record.is_holiday), bool(record.is_weekend)
            )
        )
        return {
            "date":               record.date.isoformat() if record.date else None,
            "check_in":           record.check_in.isoformat()           if record.check_in           else None,
            "check_out":          record.check_out.isoformat()          if record.check_out          else None,
            "overtime_check_in":  record.overtime_check_in.isoformat()  if record.overtime_check_in  else None,
            "overtime_check_out": record.overtime_check_out.isoformat() if record.overtime_check_out else None,
            "regular_hours":      str(record.regular_hours  or 0),
            "overtime_hours":     str(record.overtime_hours or 0),
            "working_hours":      str(record.working_hours  or 0),
            "shift_status":       record.shift_status,
            "attendance_type":    record.attendance_type,
            "late_minutes":       record.late_minutes,
            "is_half_day":        record.is_half_day,
            "is_weekend":         record.is_weekend,
            "is_holiday":         record.is_holiday,
            "day_multiplier":     multiplier,   # ← frontend dùng để hiển thị "x3"
        }

    # =========================================================
    # QUERY HELPERS
    # =========================================================

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
        """
        Truy vấn lịch sử chấm công theo tháng.
        
        - Nếu không có month/year: trả về `limit` bản ghi gần nhất
        - Nếu có month/year: trả về ĐẦY ĐỦ tất cả ngày trong tháng với các trạng thái:
        * Ngày có bản ghi chấm công → dùng bản ghi
        * Ngày có đơn nghỉ phép đã duyệt → LEAVE
        * Ngày là lễ → HOLIDAY_OFF (🎉)
        * Ngày cuối tuần → WEEKEND_OFF (🛌)
        * Ngày khác → ABSENT (vắng mặt ❌)
        """
        from calendar import monthrange
        
        sim_time_str = sim_time_str or session.get("simulated_now")
        now_dt = AttendanceService.parse_time(sim_time_str)
        
        # ─────── TRƯỜNG HỢP 1: Không chỉ định tháng/năm ───────
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

        # ─────── TRƯỜNG HỢP 2: Có chỉ định tháng/năm ───────
        
        # Validate tháng
        if month < 1 or month > 12:
            raise ValidationError("Tháng không hợp lệ")

        # Xác định phạm vi ngày
        last_day = monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end = date(year, month, last_day)
        
        # Chỉ hiển thị đến hôm nay nếu tháng hiện tại
        effective_end = (
            month_end 
            if (year, month) < (now_dt.year, now_dt.month) 
            else min(month_end, now_dt.date())
        )

        if effective_end < month_start:
            return []

        # ─────── 1. Lấy bản ghi chấm công có sẵn ───────
        attendance_rows = (
            Attendance.query.filter(
                Attendance.employee_id == employee_id,
                Attendance.date >= month_start,
                Attendance.date <= effective_end,
            )
            .all()
        )
        attendance_by_date = {row.date: row for row in attendance_rows}

        # ─────── 2. Lấy danh sách ngày nghỉ phép đã duyệt ───────
        leave_rows = (
            LeaveRequest.query.filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status == "approved",
                LeaveRequest.is_deleted.is_(False),  # 🔥 QUAN TRỌNG: chỉ lấy đơn chưa xóa
                LeaveRequest.from_date <= effective_end,
                LeaveRequest.to_date >= month_start,
            )
            .all()
        )
        leave_dates = set()
        for leave in leave_rows:
            start = max(leave.from_date, month_start)
            end = min(leave.to_date, effective_end)
            current = start
            while current <= end:
                leave_dates.add(current)
                current = current.fromordinal(current.toordinal() + 1)

        # ─────── 3. Lấy danh sách ngày lễ ───────
        fixed_holidays = Holiday.query.filter(
            Holiday.is_recurring.is_(False),
            Holiday.date >= month_start,
            Holiday.date <= effective_end,
        ).all()
        recurring_holidays = Holiday.query.filter_by(is_recurring=True).all()
        holiday_dates = {h.date for h in fixed_holidays}
        
        for holiday in recurring_holidays:
            try:
                recurring_date = date(year, month, holiday.date.day)
            except ValueError:
                continue
            if month_start <= recurring_date <= effective_end:
                holiday_dates.add(recurring_date)

        # ─────── 4. Xây dựng lịch sử đầy đủ từng ngày ───────
        history = []
        current = effective_end
        
        while current >= month_start:
            if current in attendance_by_date:
                # ✅ Có bản ghi chấm công → dùng bản ghi
                history.append(attendance_by_date[current])
            else:
                # ❌ Không có bản ghi → xác định trạng thái mặc định
                is_weekend = current.weekday() >= 5  # Thứ 6, 7
                is_holiday = current in holiday_dates
                is_leave = current in leave_dates
                
                # ⚡ Ưu tiên: leave > holiday > weekend > absent
                if is_leave:
                    shift_status = Attendance.ShiftStatus.LEAVE
                    attendance_type = Attendance.Type.LEAVE
                elif is_holiday:
                    shift_status = Attendance.ShiftStatus.HOLIDAY_OFF
                    attendance_type = Attendance.Type.HOLIDAY
                elif is_weekend:
                    shift_status = Attendance.ShiftStatus.WEEKEND_OFF
                    attendance_type = Attendance.Type.WEEKEND
                else:
                    shift_status = Attendance.ShiftStatus.ABSENT
                    attendance_type = Attendance.Type.ABSENT
                
                # Tạo object giả lập (không lưu DB)
                history.append(SimpleNamespace(
                    id=None,
                    date=current,
                    check_in=None,
                    check_out=None,
                    regular_hours=Decimal("0.00"),
                    overtime_hours=Decimal("0.00"),
                    working_hours=Decimal("0.00"),  # 🔥 THÊM FIELD NÀY
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

        from app.models import Employee, Notification

        employee = Employee.query.get(employee_id)
        if employee and employee.user_id:
            notilist = (
                Notification.query.filter(
                    Notification.user_id == employee.user_id,
                    Notification.is_deleted.is_(False),
                    Notification.type.in_(["attendance", "overtime"]),
                    db.func.date(Notification.created_at) == target_date,
                ).all()
            )
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

    # =========================================================
    # MAIN ENTRY POINT
    # =========================================================

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
                "type": "success",
                "action": AttendanceService.ACTION_ALREADY_RECORDED,
                "attendance_state": attendance.shift_status,
                "message": "Ngày công đã hoàn tất",
                "attendance": AttendanceService.build_attendance_payload(attendance),
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

    # =========================================================
    # PHASE 1 — CHƯA CHECK-IN
    # =========================================================

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

    # =========================================================
    # PHASE 2 — ĐANG LÀM CA CHÍNH
    # =========================================================

    @staticmethod
    def _handle_working(
        attendance: Attendance,
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:
        today       = current_time.date()
        end_of_day  = datetime.combine(today, AttendanceService.REGULAR_END)
        lunch_start = datetime.combine(today, AttendanceService.LUNCH_START)
        lunch_end   = datetime.combine(today, AttendanceService.LUNCH_END)
        grace_end   = datetime.combine(today, time(17, 5, 0))

        early_checkout_confirmed = bool(payload.get("early_checkout_confirmed"))

        if lunch_start <= current_time <= lunch_end:
            return {
                "type": "info",
                "action": "lunch_break",
                "attendance_state": attendance.shift_status,
                "message": "Đang trong giờ nghỉ trưa (12:00–13:00)",
            }

        if end_of_day <= current_time <= grace_end:
            return AttendanceService.check_out_regular(
                employee_id, current_time.isoformat(),
                early_checkout=False, current_time=current_time,
            )

        if current_time < end_of_day and not early_checkout_confirmed:
            early_minutes = int((end_of_day - current_time).total_seconds() // 60)
            return {
                "type": "warning",
                "action": AttendanceService.ACTION_EARLY_CHECKOUT_PROMPT,
                "attendance_state": attendance.shift_status,
                "message": f"Bạn có muốn tan ca sớm không? (sớm {early_minutes} phút)",
                "requires_confirmation": True,
                "flags": {"early_minutes": early_minutes},
            }

        return AttendanceService.check_out_regular(
            employee_id, current_time.isoformat(),
            early_checkout=early_checkout_confirmed, current_time=current_time,
        )

    # =========================================================
    # PHASE 3 — SAU CHECK-OUT CA CHÍNH
    # =========================================================

    @staticmethod
    def _handle_after_checkout(
        attendance: Attendance,
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:
        sim_time = current_time.isoformat()
        overtime_decision = str(payload.get("overtime_decision") or "").lower()

        # REGULAR_DONE
        if attendance.shift_status == Attendance.ShiftStatus.REGULAR_DONE:
            if attendance.check_out and attendance.check_out.time() < AttendanceService.REGULAR_END:
                attendance.set_shift_status(Attendance.ShiftStatus.COMPLETED)
                AttendanceService.finalize_attendance(attendance, finalize_status=True)
                db.session.commit()
                return {
                    "type": "success",
                    "action": AttendanceService.ACTION_COMPLETE_WITHOUT_OT,
                    "attendance_state": attendance.shift_status,
                    "message": "Đã hoàn tất ngày công (về sớm).",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            if overtime_decision not in {"yes", "no"}:
                return {
                    "type": "warning",
                    "action": AttendanceService.ACTION_OFFER_OVERTIME,
                    "message": "Bạn có muốn đăng ký tăng ca không?",
                    "attendance_state": attendance.shift_status,
                    "next_event": "offer_overtime",
                    "requires_overtime_decision": True,
                }

            if overtime_decision == "no":
                attendance.set_shift_status(Attendance.ShiftStatus.COMPLETED)
                AttendanceService.finalize_attendance(attendance, finalize_status=True)
                db.session.commit()
                return {
                    "type": "success",
                    "action": AttendanceService.ACTION_COMPLETE_WITHOUT_OT,
                    "attendance_state": attendance.shift_status,
                    "message": "Đã hoàn tất ngày công, không đăng ký tăng ca.",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            return AttendanceService._create_ot_request_pending(
                attendance, employee_id, current_time
            )

        # REGULAR_DONE_PENDING_OT_DECISION
        if attendance.shift_status == Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION:
            approved_ot = AttendanceService._get_approved_ot(employee_id, current_time.date())
            if approved_ot:
                if current_time.time() >= AttendanceService.OT_EARLY_CHECKIN:
                    return AttendanceService.check_in_overtime(employee_id, sim_time)
                return {
                    "type": "info",
                    "action": "ot_approved_wait",
                    "attendance_state": attendance.shift_status,
                    "overtime_status": "APPROVED",
                    "message": "OT đã được duyệt. Vui lòng check-in OT từ 18:30.",
                }

            pending_ot = OvertimeRequest.query.filter(
                OvertimeRequest.employee_id == employee_id,
                OvertimeRequest.overtime_date == current_time.date(),
                OvertimeRequest.is_deleted.is_(False),
                OvertimeRequest.status.in_(["pending", "pending_hr", "pending_admin"]),
            ).first()
            if pending_ot:
                return {
                    "type": "info",
                    "action": "ot_pending_approval",
                    "attendance_state": attendance.shift_status,
                    "overtime_status": "PENDING",
                    "message": "Đang chờ duyệt tăng ca.",
                }

            attendance.set_shift_status(Attendance.ShiftStatus.COMPLETED)
            AttendanceService.finalize_attendance(attendance, finalize_status=True)
            db.session.commit()
            return {
                "type": "warning",
                "action": AttendanceService.ACTION_COMPLETE_WITHOUT_OT,
                "attendance_state": attendance.shift_status,
                "message": "Đơn tăng ca bị từ chối. Đã hoàn tất ngày công.",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        # PRE_OT_REST
        if attendance.shift_status == Attendance.ShiftStatus.PRE_OT_REST:
            approved_ot = AttendanceService._get_approved_ot(employee_id, current_time.date())
            if not approved_ot:
                return {
                    "type": "warning",
                    "action": "overtime_not_approved",
                    "attendance_state": attendance.shift_status,
                    "message": "Đơn tăng ca không còn hợp lệ hoặc chưa được duyệt.",
                }
            if not attendance.overtime_check_in:
                return AttendanceService.check_in_overtime(employee_id, sim_time)
            if current_time.time() >= AttendanceService.OT_START:
                attendance.set_shift_status(Attendance.ShiftStatus.WORKING_OVERTIME)
                db.session.commit()
            return {
                "type": "info",
                "action": "pre_ot_rest",
                "attendance_state": attendance.shift_status,
                "message": "Đã xác thực chấm công tăng ca. Đang nghỉ ngơi trước tăng ca.",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        # WORKING_OVERTIME
        if attendance.shift_status == Attendance.ShiftStatus.WORKING_OVERTIME:
            if not attendance.overtime_check_out:
                return AttendanceService.check_out_overtime(employee_id, sim_time)

        # COMPLETED
        if attendance.shift_status == Attendance.ShiftStatus.COMPLETED:
            return {
                "type": "success",
                "action": AttendanceService.ACTION_ALREADY_RECORDED,
                "attendance_state": attendance.shift_status,
                "message": "Ngày công đã hoàn tất.",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        return {
            "type": "info",
            "action": AttendanceService.ACTION_ALREADY_RECORDED,
            "attendance_state": attendance.shift_status,
            "message": "Trạng thái: " + Attendance.ShiftStatus.label(attendance.shift_status),
            "attendance": AttendanceService.build_attendance_payload(attendance),
        }

    # =========================================================
    # OT REQUEST CREATION
    # =========================================================

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
            "type": "success",
            "action": AttendanceService.ACTION_OVERTIME_REQUEST_CREATED,
            "attendance_state": attendance.shift_status,
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

    # =========================================================
    # OFFDAY LOGIC
    # =========================================================

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
                    "type": "info",
                    "status_code": 200,
                    "action": (
                        AttendanceService.ACTION_HOLIDAY_OFF if is_holiday
                        else AttendanceService.ACTION_WEEKEND_OFF
                    ),
                    "attendance_state": record.shift_status,
                    "message": (
                        "Đã ghi nhận nghỉ lễ hôm nay." if is_holiday
                        else "Đã ghi nhận nghỉ cuối tuần hôm nay."
                    ),
                    "attendance": AttendanceService.build_attendance_payload(record),
                }

        return {"pass_through": True, "debug": {"is_weekend": is_weekend, "is_holiday": is_holiday}}

    # =========================================================
    # CHECK-IN CA CHÍNH
    # =========================================================

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
                "action": (
                    AttendanceService.ACTION_HOLIDAY_WORK_PROMPT if is_holiday
                    else AttendanceService.ACTION_WEEKEND_WORK_PROMPT
                ),
                "requires_confirmation": True,
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "message": (
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

        # Tính đi muộn: so với 8:00
        late_minutes = max(
            0,
            int(
                (now_dt - datetime.combine(now_dt.date(), AttendanceService.REGULAR_START))
                .total_seconds() / 60
            ),
        )
        record.late_minutes = late_minutes
        record.is_half_day  = late_minutes >= 60   # đi muộn ≥ 60 phút → nửa ngày

        # Gán DB status
        if record.is_half_day:
            status_name = "HALF_DAY"
        elif late_minutes > 0:
            status_name = "LATE"
        else:
            status_name = "PRESENT"
        db_status = AttendanceService.get_status(status_name)
        if db_status:
            record.status_id = db_status.id

        # Ngày thường + đi muộn nhiều → ABNORMAL
        if not record.is_weekend and not record.is_holiday and record.is_half_day:
            record.set_attendance_type(Attendance.Type.ABNORMAL)

        db.session.commit()

        msg = f"Check-in thành công lúc {now_dt.strftime('%H:%M:%S')}"
        resp_type = "success"
        if is_holiday:
            msg += " (Ngày lễ — công sẽ nhân x3)"
        elif is_weekend:
            msg += " (Cuối tuần — công sẽ nhân x3)"
        if record.is_half_day:
            msg += f". Đi muộn {late_minutes} phút, tính nửa ngày công."
            resp_type = "warning"
        elif late_minutes > 0:
            msg += f". Đi muộn {late_minutes} phút."
            resp_type = "warning"

        return {
            "action":           AttendanceService.ACTION_CHECK_IN,
            "type":             resp_type,
            "message":          msg,
            "attendance_state": record.shift_status,
            "attendance":       AttendanceService.build_attendance_payload(record),
        }

    # =========================================================
    # CHECK-OUT CA CHÍNH
    # =========================================================

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

        # Tính công RAW (chưa nhân hệ số)
        raw_regular = AttendanceService.calculate_regular_hours_raw(
            record.check_in, record.check_out
        )

        # Áp hệ số ngày lễ / cuối tuần
        multiplier = AttendanceService._day_multiplier(
            bool(record.is_holiday), bool(record.is_weekend)
        )
        record.regular_hours = (raw_regular * multiplier).quantize(Decimal("0.01"))

        record.set_shift_status(Attendance.ShiftStatus.REGULAR_DONE)
        AttendanceService.finalize_attendance(record, finalize_status=False)
        db.session.commit()

        early_minutes = 0
        if early_checkout and current_time:
            end_of_day    = datetime.combine(current_time.date(), AttendanceService.REGULAR_END)
            early_minutes = max(0, int((end_of_day - current_time).total_seconds() // 60))

        # Thông điệp hiển thị công
        multiplier_label = f" (x{int(multiplier)})" if multiplier > 1 else ""
        if early_checkout:
            record.set_shift_status(Attendance.ShiftStatus.COMPLETED)
            AttendanceService.finalize_attendance(record, finalize_status=True)
            db.session.commit()
            return {
                "type":             "warning",
                "action":           AttendanceService.ACTION_CHECK_OUT,
                "message":          f"Check-out lúc {(current_time or now_dt).strftime('%H:%M:%S')}. Về sớm {early_minutes} phút.",
                "attendance_state": record.shift_status,
                "status_key":       "early_leave",
                "regular_hours":    str(record.regular_hours),
                "overtime_hours":   str(record.overtime_hours or 0),
                "working_hours":    str(record.working_hours),
                "attendance":       AttendanceService.build_attendance_payload(record),
                "next_event":       None,
                "requires_overtime_decision": False,
            }

        return {
            "type":             "success",
            "action":           AttendanceService.ACTION_CHECK_OUT,
            "message":          f"Check-out ca chính thành công. Công thường: {record.regular_hours}h{multiplier_label}",
            "attendance_state": record.shift_status,
            "regular_hours":    str(record.regular_hours),
            "overtime_hours":   str(record.overtime_hours or 0),
            "working_hours":    str(record.working_hours),
            "attendance":       AttendanceService.build_attendance_payload(record),
            "next_event":       "offer_overtime",
            "requires_overtime_decision": True,
        }

    # =========================================================
    # CHECK-IN OT
    # =========================================================

    @staticmethod
    def check_in_overtime(employee_id: int, sim_time_str: str | None) -> dict:
        now_dt = AttendanceService.parse_time(sim_time_str)
        record = Attendance.query.filter_by(
            employee_id=employee_id, date=now_dt.date()
        ).first()

        if not record or not record.check_out:
            raise ValidationError("Bạn phải hoàn tất ca chính trước khi OT.")

        if now_dt.time() < AttendanceService.OT_EARLY_CHECKIN:
            raise ValidationError(
                f"Chưa đến giờ xác thực OT. Vui lòng quay lại từ "
                f"{AttendanceService.OT_EARLY_CHECKIN.strftime('%H:%M')}."
            )

        approved_ot = AttendanceService._get_approved_ot(employee_id, now_dt.date())
        if not approved_ot:
            raise ValidationError("Bạn chưa có đơn OT đã được HR/Admin duyệt cho hôm nay.")

        if record.overtime_check_in:
            raise ValidationError("Bạn đã check-in OT.")

        record.overtime_check_in   = now_dt
        record.overtime_status     = "APPROVED"
        record.overtime_request_id = approved_ot.id

        if now_dt.time() < AttendanceService.OT_START:
            record.set_shift_status(Attendance.ShiftStatus.PRE_OT_REST)
            msg = "Đã xác thực chấm công tăng ca. Trạng thái: Nghỉ ngơi trước tăng ca."
        else:
            record.set_shift_status(Attendance.ShiftStatus.WORKING_OVERTIME)
            msg = f"Check-in OT lúc {now_dt.strftime('%H:%M:%S')}. Bắt đầu tăng ca."

        db.session.commit()

        return {
            "type":             "success",
            "action":           AttendanceService.ACTION_CHECK_IN_OT,
            "message":          msg,
            "attendance_state": record.shift_status,
            "overtime_status":  "APPROVED",
            "attendance":       AttendanceService.build_attendance_payload(record),
        }

    # =========================================================
    # CHECK-OUT OT
    # =========================================================

    @staticmethod
    def check_out_overtime(employee_id: int, sim_time_str: str | None) -> dict:
        now_dt = AttendanceService.parse_time(sim_time_str)
        record = Attendance.query.filter_by(
            employee_id=employee_id, date=now_dt.date()
        ).first()

        if not record or not record.overtime_check_in:
            raise ValidationError("Bạn chưa check-in OT.")
        if record.overtime_check_out:
            raise ValidationError("Bạn đã check-out OT.")

        ot_end_dt             = datetime.combine(now_dt.date(), AttendanceService.OT_END)
        record.overtime_check_out = min(now_dt, ot_end_dt)

        # Tính OT raw, sau đó nhân multiplier từ approved OT request
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
            "type":              "success",
            "action":            AttendanceService.ACTION_CHECK_OUT_OT,
            "message":           f"Check-out OT thành công. Tăng ca: {record.overtime_hours}h{multiplier_label}",
            "attendance_state":  record.shift_status,
            "regular_hours":     str(record.regular_hours),
            "overtime_hours":    str(record.overtime_hours),
            "working_hours":     str(record.working_hours),
            "overtime_check_in":  record.overtime_check_in.isoformat()  if record.overtime_check_in  else None,
            "overtime_check_out": record.overtime_check_out.isoformat() if record.overtime_check_out else None,
            "attendance":        AttendanceService.build_attendance_payload(record),
        }