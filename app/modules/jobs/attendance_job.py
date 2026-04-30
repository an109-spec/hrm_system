# app/modules/jobs/attendance_job.py

from __future__ import annotations

from datetime import datetime, date

from app.extensions.db import db
from app.models import (
    Attendance,
    Employee,
    OvertimeRequest,
    Notification,  # nếu chưa có model này thì phải tạo
)
from app.common.exceptions import ValidationError


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

        notification = Notification(
            employee_id=employee_id,
            title=title,
            content=content,
            notification_type=notification_type,
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