from __future__ import annotations
 
from datetime import datetime, date, time
from decimal import Decimal
 
from app.extensions.db import db
from app.models import Attendance, Employee, OvertimeRequest, Notification
from app.modules.attendance.service import AttendanceService
 
 
class AttendanceJob:
 
    # =========================================================
    # HELPER: tạo notification cho nhân viên
    # =========================================================
 
    @staticmethod
    def _create_notification(
        employee_id: int,
        title: str,
        content: str,
        notification_type: str = "attendance",
    ) -> None:
        employee = Employee.query.get(employee_id)
        if not employee or not employee.user_id:
            return
        db.session.add(
            Notification(
                user_id=employee.user_id,
                title=title,
                content=content,
                type=notification_type,
                is_read=False,
            )
        )
 
    # =========================================================
    # JOB 17:00 — Nhắc checkout ca chính
    # =========================================================
 
    @staticmethod
    def run_17h_notification() -> dict:
        today = date.today()
 
        records = Attendance.query.filter(
            Attendance.date == today,
            Attendance.check_in.isnot(None),
            Attendance.check_out.is_(None),
        ).all()
 
        for record in records:
            AttendanceJob._create_notification(
                employee_id=record.employee_id,
                title="Nhắc nhở checkout",
                content="Đã 17:00, vui lòng checkout ca làm việc để hoàn tất ngày công.",
            )
 
        db.session.commit()
        return {"message": f"Đã gửi {len(records)} thông báo checkout 17h"}
 
    # =========================================================
    # JOB 19:00 — Nhắc check-in OT
    # =========================================================
 
    @staticmethod
    def run_19h_ot_notification() -> dict:
        today = date.today()
 
        approved_requests = OvertimeRequest.query.filter_by(
            overtime_date=today,
            status="approved",
        ).all()
 
        count = 0
        for ot_req in approved_requests:
            attendance = Attendance.query.filter_by(
                employee_id=ot_req.employee_id, date=today
            ).first()
 
            # Bỏ qua nếu: chưa checkout ca chính, đã check-in OT, hoặc đã terminal
            if (
                not attendance
                or not attendance.check_out
                or attendance.overtime_check_in
                or Attendance.ShiftStatus.normalize(attendance.shift_status)
                in Attendance.ShiftStatus.TERMINAL_STATUSES
            ):
                continue
 
            AttendanceJob._create_notification(
                employee_id=ot_req.employee_id,
                title="Nhắc bắt đầu tăng ca",
                content="Đã 19:00. Bạn có đơn tăng ca đã được duyệt. Vui lòng check-in OT.",
                notification_type="overtime",
            )
            count += 1
 
        db.session.commit()
        return {"message": f"Đã gửi {count} thông báo bắt đầu OT lúc 19h"}
 
    # =========================================================
    # JOB 22:00 — Nhắc checkout OT
    # =========================================================
 
    @staticmethod
    def run_22h_ot_checkout_notification() -> dict:
        today = date.today()
 
        records = Attendance.query.filter(
            Attendance.date == today,
            Attendance.overtime_check_in.isnot(None),
            Attendance.overtime_check_out.is_(None),
        ).all()
 
        for record in records:
            AttendanceJob._create_notification(
                employee_id=record.employee_id,
                title="Nhắc checkout tăng ca",
                content="Đã 22:00. Vui lòng checkout OT để hoàn tất ghi nhận tăng ca hôm nay.",
                notification_type="overtime",
            )
 
        db.session.commit()
        return {"message": f"Đã gửi {len(records)} thông báo checkout OT lúc 22h"}
 
    # =========================================================
    # JOB 22:00 — Tự động chốt OT
    # =========================================================
 
    @staticmethod
    def run_22h_ot_auto_close() -> dict:
        today    = date.today()
        ot_cutoff = datetime.combine(today, AttendanceService.OT_END)
 
        records = Attendance.query.filter(
            Attendance.date == today,
            Attendance.overtime_check_in.isnot(None),
            Attendance.overtime_check_out.is_(None),
        ).all()
 
        closed = 0
        for record in records:
            approved_ot = OvertimeRequest.query.filter(
                OvertimeRequest.employee_id == record.employee_id,
                OvertimeRequest.overtime_date == today,
                OvertimeRequest.is_deleted.is_(False),
                OvertimeRequest.status == "approved",
            ).order_by(OvertimeRequest.updated_at.desc()).first()
 
            if not approved_ot:
                continue
 
            record.overtime_check_out = ot_cutoff
            raw_hours  = AttendanceService.calculate_overtime_hours(
                record.overtime_check_in, record.overtime_check_out
            )
            multiplier = Decimal(str(approved_ot.holiday_multiplier or 1))
            record.overtime_hours = (raw_hours * multiplier).quantize(Decimal("0.01"))
 
            # Gọi service để finalize (tính working_hours, set COMPLETED)
            AttendanceService.finalize_attendance(record, finalize_status=True)
 
            AttendanceJob._create_notification(
                employee_id=record.employee_id,
                title="Hệ thống đã tự động chốt tăng ca",
                content="Đã đến 22:00, hệ thống tự động checkout OT cho bạn.",
                notification_type="overtime",
            )
            closed += 1
 
        db.session.commit()
        return {"message": f"Đã tự động chốt {closed} bản ghi OT lúc 22h"}
 
    # =========================================================
    # JOB CUỐI NGÀY — Finalize toàn bộ
    # =========================================================
 
    @staticmethod
    def run_daily() -> dict:
        today = date.today()
 
        employees = Employee.query.filter_by(is_active=True).all()
 
        processed      = 0
        created_absent = 0
        auto_closed    = 0
 
        for employee in employees:
            # Bỏ qua nhân viên không cần chấm công
            if employee.is_attendance_required is False:
                continue
 
            attendance = Attendance.query.filter_by(
                employee_id=employee.id, date=today
            ).first()
 
            # ── Không có bản ghi → đánh dấu ABSENT ──────────────────────
            if not attendance:
                is_weekend = today.weekday() >= 5
                is_holiday = AttendanceService._is_holiday(today)
 
                new_record = Attendance(
                    employee_id=employee.id,
                    date=today,
                    is_weekend=is_weekend,
                    is_holiday=is_holiday,
                    working_hours=Decimal("0.00"),
                    regular_hours=Decimal("0.00"),
                    overtime_hours=Decimal("0.00"),
                )
 
                if is_holiday:
                    new_record.set_shift_status(Attendance.ShiftStatus.HOLIDAY_OFF)
                    new_record.set_attendance_type(Attendance.Type.HOLIDAY)
                elif is_weekend:
                    new_record.set_shift_status(Attendance.ShiftStatus.WEEKEND_OFF)
                    new_record.set_attendance_type(Attendance.Type.WEEKEND)
                else:
                    new_record.set_shift_status(Attendance.ShiftStatus.ABSENT)
                    new_record.set_attendance_type(Attendance.Type.ABSENT)
                    created_absent += 1
 
                db.session.add(new_record)
                processed += 1
                continue
 
            # ── Đã có bản ghi nhưng chưa terminal → finalize ─────────────
            normalized = Attendance.ShiftStatus.normalize(attendance.shift_status)
 
            if normalized in Attendance.ShiftStatus.TERMINAL_STATUSES:
                continue  # Đã hoàn tất, bỏ qua
 
            # Check-in nhưng chưa check-out
            if attendance.check_in and not attendance.check_out:
                attendance.check_out = datetime.combine(today, AttendanceService.REGULAR_END)
                attendance.regular_hours = AttendanceService.calculate_regular_hours(
                    attendance.check_in, attendance.check_out
                )
 
            # Check-in OT nhưng chưa check-out OT
            if attendance.overtime_check_in and not attendance.overtime_check_out:
                attendance.overtime_check_out = datetime.combine(today, AttendanceService.OT_END)
                raw_hours = AttendanceService.calculate_overtime_hours(
                    attendance.overtime_check_in, attendance.overtime_check_out
                )
                # Áp multiplier nếu có
                approved_ot = OvertimeRequest.query.filter(
                    OvertimeRequest.employee_id == employee.id,
                    OvertimeRequest.overtime_date == today,
                    OvertimeRequest.is_deleted.is_(False),
                    OvertimeRequest.status == "approved",
                ).order_by(OvertimeRequest.updated_at.desc()).first()
                multiplier = Decimal(str(approved_ot.holiday_multiplier or 1)) if approved_ot else Decimal("1")
                attendance.overtime_hours = (raw_hours * multiplier).quantize(Decimal("0.01"))
 
            # Finalize tất cả → COMPLETED
            AttendanceService.finalize_attendance(attendance, finalize_status=True)
            auto_closed += 1
            processed   += 1
 
        db.session.commit()
 
        return {
            "message":       "Daily attendance finalize hoàn tất",
            "processed":     processed,
            "created_absent": created_absent,
            "auto_closed":   auto_closed,
        }
 