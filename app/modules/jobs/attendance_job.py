# app/modules/jobs/attendance_job.py

from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal

from app.extensions.db import db
from app.models import (
    Attendance,
    Employee,
    OvertimeRequest,
    Notification,  # nếu chưa có model này thì phải tạo
)
from app.common.exceptions import ValidationError
from app.modules.attendance.service import AttendanceService

class AttendanceJob:
    """
    Server-side scheduled jobs cho attendance

    KHÔNG được phụ thuộc frontend popup.

    Phải chạy bằng:
    APScheduler / Celery / Cron / Background Job

    Bao gồm:
    - 17h nhắc checkout ca chính
    - 19h nhắc bắt đầu OT
    - 22h nhắc checkout OT
    - daily finalize attendance
    """

    # =========================================================
    # INTERNAL HELPER
    # =========================================================

    @staticmethod
    def _create_notification(
        employee_id: int,
        title: str,
        content: str,
        notification_type: str = "attendance",
    ):
        """
        Tạo notification trong DB
        """
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

    # =========================================================
    # 17:00 CHECKOUT NOTIFICATION
    # =========================================================

    @staticmethod
    def run_17h_notification():
        """
        17:00:
        Nhắc nhân viên chưa checkout ca chính

        Điều kiện:
        - có check_in
        - chưa check_out
        """

        today = date.today()

        records = Attendance.query.filter(
            Attendance.date == today,
            Attendance.check_in.isnot(None),
            Attendance.check_out.is_(None),
        ).all()

        for record in records:
            record.shift_status = "regular_checkout_required"
            AttendanceJob._create_notification(
                employee_id=record.employee_id,
                title="Nhắc nhở checkout",
                content=(
                    "Đã 17:00, vui lòng checkout ca làm việc "
                    "để hoàn tất ngày công."
                ),
            )

        db.session.commit()

        return {
            "message": f"Đã gửi {len(records)} thông báo checkout 17h"
        }

    # =========================================================
    # 19:00 OT START NOTIFICATION
    # =========================================================

    @staticmethod
    def run_19h_ot_notification():
        """
        19:00:
        Nhắc nhân viên có đơn OT approved bắt đầu tăng ca

        Điều kiện:
        - đơn OT approved
        - attendance đã checkout ca chính
        - chưa overtime_check_in
        """

        today = date.today()

        approved_requests = OvertimeRequest.query.filter_by(
            overtime_date=today,
            status="approved",
        ).all()

        count = 0

        for request in approved_requests:
            attendance = Attendance.query.filter_by(
                employee_id=request.employee_id,
                date=today,
            ).first()

            if not attendance:
                continue

            if not attendance.check_out:
                continue

            if attendance.overtime_check_in:
                continue
            attendance.shift_status = "ot_checkin_required"
            AttendanceJob._create_notification(
                employee_id=request.employee_id,
                title="Nhắc bắt đầu tăng ca",
                content=(
                    "Đã 19:00. Bạn có đơn tăng ca đã được duyệt. "
                    "Vui lòng check-in OT."
                ),
                notification_type="overtime",
            )

            count += 1

        db.session.commit()

        return {
            "message": f"Đã gửi {count} thông báo bắt đầu OT lúc 19h"
        }

    # =========================================================
    # 22:00 OT CHECKOUT NOTIFICATION
    # =========================================================

    @staticmethod
    def run_22h_ot_checkout_notification():
        """
        22:00:
        Nhắc nhân viên đang OT phải checkout

        Điều kiện:
        - đã overtime_check_in
        - chưa overtime_check_out
        """

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
                content=(
                    "Đã 22:00. Vui lòng checkout OT để hoàn tất "
                    "ghi nhận tăng ca hôm nay."
                ),
                notification_type="overtime",
            )

        db.session.commit()

        return {
            "message": (
                f"Đã gửi {len(records)} thông báo checkout OT lúc 22h"
            )
        }
    @staticmethod
    def run_22h_ot_auto_close():
        """
        22:00+:
        Tự động đóng OT cho các bản ghi đang mở.
        """
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
            raw_overtime_hours = AttendanceService.calculate_overtime_hours(
                record.overtime_check_in,
                record.overtime_check_out,
            )
            overtime_multiplier = Decimal(str(approved_ot.holiday_multiplier or 1))
            record.overtime_hours = (raw_overtime_hours * overtime_multiplier).quantize(Decimal("0.01"))
            current_regular_hours = Decimal(str(record.regular_hours or 0)).quantize(Decimal("0.01"))
            record.working_hours = (current_regular_hours + record.overtime_hours).quantize(Decimal("0.01"))
            if record.overtime_hours > 0 and record.attendance_type != "holiday":
                record.attendance_type = "overtime"
            record.shift_status = "completed"
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
    # DAILY FINALIZE
    # =========================================================

    @staticmethod
    def run_daily():
        """
        Job tổng cuối ngày

        Có thể chạy lúc 23:30:
        - finalize attendance
        - khóa dữ liệu ngày công
        - auto absent nếu chưa check-in
        - sync payroll
        """

        today = date.today()

        employees = Employee.query.filter_by(
            is_active=True
        ).all()

        processed = 0

        for employee in employees:
            attendance = Attendance.query.filter_by(
                employee_id=employee.id,
                date=today,
            ).first()

            # chưa có attendance → có thể auto absent
            if not attendance:
                continue

            # nếu cần:
            # gọi AttendanceService.finalize_attendance()

            processed += 1

        db.session.commit()

        return {
            "message": (
                f"Daily attendance finalize hoàn tất: "
                f"{processed} records processed"
            )
        }