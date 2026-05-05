# app/modules/jobs/attendance_job.py

from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal

from app.extensions.db import db
from app.models import Attendance, Employee, OvertimeRequest, Notification
from app.modules.attendance.service import AttendanceService

class AttendanceJob:

    @staticmethod
    def _create_notification(
        employee_id: int,
        title: str,
        content: str,
        notification_type: str = "attendance",
    ):
        employee = Employee.query.get(employee_id)
        if not employee or not employee.user_id:
            return
        notification = Notification(
            user_id=employee.user_id,
            title=title,
            content=content,
            type=notification_type,
            is_read=False,
        )

        db.session.add(notification)
    @staticmethod
    def run_17h_notification():
        today = date.today()

        records = Attendance.query.filter(
            Attendance.date == today,
            Attendance.check_in.isnot(None),
            Attendance.check_out.is_(None),
        ).all()

        for record in records:
            record.set_shift_status(Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED)
            AttendanceJob._create_notification(
                employee_id=record.employee_id,
                title="Nhắc nhở checkout",
                content="Đã 17:00, vui lòng checkout ca làm việc để hoàn tất ngày công.",
            )

        db.session.commit()
        return {"message": f"Đã gửi {len(records)} thông báo checkout 17h"}
    @staticmethod
    def run_19h_ot_notification():
        today = date.today()

        approved_requests = OvertimeRequest.query.filter_by(
            overtime_date=today,
            status="approved",
        ).all()

        count = 0

        for request in approved_requests:
            attendance = Attendance.query.filter_by(employee_id=request.employee_id, date=today).first()
            if (
                not attendance
                or not attendance.check_out
                or attendance.overtime_check_in
                or Attendance.ShiftStatus.normalize(attendance.shift_status) in Attendance.ShiftStatus.TERMINAL_STATUSES
            ):
                continue

            attendance.set_shift_status(Attendance.ShiftStatus.OT_CHECKIN_REQUIRED)
            AttendanceJob._create_notification(
                employee_id=request.employee_id,
                title="Nhắc bắt đầu tăng ca",
                content="Đã 19:00. Bạn có đơn tăng ca đã được duyệt. Vui lòng check-in OT.",
                notification_type="overtime",
            )

            count += 1

        db.session.commit()

        return {"message": f"Đã gửi {count} thông báo bắt đầu OT lúc 19h"}

    @staticmethod
    def run_22h_ot_checkout_notification():
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

    @staticmethod
    def run_22h_ot_auto_close():
        today = date.today()
        ot_cutoff = datetime.combine(today, time(22, 0, 0))

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
            raw_overtime_hours = AttendanceService.calculate_overtime_hours(record.overtime_check_in, record.overtime_check_out)
            overtime_multiplier = Decimal(str(approved_ot.holiday_multiplier or 1))
            record.overtime_hours = (raw_overtime_hours * overtime_multiplier).quantize(Decimal("0.01"))
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

    @staticmethod
    def run_daily():
        today = date.today()
        employees = Employee.query.filter_by(is_active=True).all()

        processed = 0
        auto_absent = 0
        auto_completed = 0
        for employee in employees:
            if employee.is_attendance_required is False:
                continue

            attendance = Attendance.query.filter_by(employee_id=employee.id, date=today).first()
            if not attendance:
                attendance = Attendance(
                    employee_id=employee.id,
                    date=today,
                    is_weekend=(today.weekday() >= 5),
                    is_holiday=AttendanceService._is_holiday(today),
                    working_hours=Decimal("0.00"),
                    regular_hours=Decimal("0.00"),
                    overtime_hours=Decimal("0.00"),
                )
                attendance.set_shift_status(Attendance.ShiftStatus.ABSENT)
                attendance.set_attendance_type(Attendance.Type.ABSENT)
                db.session.add(attendance)
                auto_absent += 1
                processed += 1
                continue
            if attendance.check_in and not attendance.check_out:
                attendance.check_out = datetime.combine(today, AttendanceService.REGULAR_END)
                attendance.regular_hours = AttendanceService.calculate_regular_hours(attendance.check_in, attendance.check_out)

            if attendance.overtime_check_in and not attendance.overtime_check_out:
                attendance.overtime_check_out = datetime.combine(today, AttendanceService.OT_END)
                attendance.overtime_hours = AttendanceService.calculate_overtime_hours(attendance.overtime_check_in, attendance.overtime_check_out)
            AttendanceService.finalize_attendance(attendance, finalize_status=True)
            auto_completed += 1

            processed += 1

        db.session.commit()

        return {
            "message": f"Daily attendance finalize hoàn tất: {processed} records processed",
            "auto_absent": auto_absent,
            "auto_completed": auto_completed,
        }