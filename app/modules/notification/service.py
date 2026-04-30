# app/modules/notification/service.py

from __future__ import annotations
from datetime import datetime
from app.extensions.db import db
from app.models.notification import Notification
from app.models.overtime_request import OvertimeRequest
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.history import HistoryLog
from app.common.exceptions import ValidationError
from .dto import NotificationDTO


class NotificationService:
    """
    Notification Service

    Sửa lớn:
    KHÔNG được chỉ delete notification đơn thuần

    Rule mới:
    nếu notification thuộc overtime
    -> phải xử lý luôn overtime request liên quan
    """

    # =========================================================
    # CREATE NOTIFICATION
    # =========================================================

    @staticmethod
    def create(dto: NotificationDTO):
        notification = Notification(
            user_id=dto.user_id,
            title=dto.title,
            content=dto.content,
            type=dto.type,  # attendance / overtime / payroll / system
            link=dto.link,
            is_read=dto.is_read,
        )

        db.session.add(notification)
        db.session.commit()

        return notification

    # =========================================================
    # GET USER NOTIFICATIONS
    # =========================================================

    @staticmethod
    def get_by_user(
        user_id: int,
        limit: int = 20,
        only_unread: bool = False,
    ):
        query = Notification.query.filter_by(
            user_id=user_id
        )

        if only_unread:
            query = query.filter_by(
                is_read=False
            )

        return (
            query.order_by(
                Notification.created_at.desc()
            )
            .limit(limit)
            .all()
        )

    # =========================================================
    # MARK AS READ
    # =========================================================

    @staticmethod
    def mark_as_read(
        notification_id: int,
        user_id: int,
    ):
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=user_id,
            is_deleted=False,
        ).first()

        if not notification:
            raise ValidationError(
                "Notification not found"
            )

        notification.is_read = True
        db.session.commit()

        return notification

    # =========================================================
    # MARK ALL AS READ
    # =========================================================

    @staticmethod
    def mark_all_as_read(user_id: int):
        Notification.query.filter_by(
            user_id=user_id,
            is_read=False,
        ).update(
            {"is_read": True}
        )

        db.session.commit()

        return True

    # =========================================================
    # DELETE NOTIFICATION
    # =========================================================

    @staticmethod
    def delete(
        notification_id: int,
        user_id: int,
    ):
        """
        Sửa lớn tại đây:

        KHÔNG chỉ xóa notification.

        Nếu notification là overtime:
            -> xóa luôn overtime request liên quan

        Vì:
        notification overtime thường đại diện cho
        một yêu cầu tăng ca đang tồn tại.
        """

        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=user_id,
        ).first()

        if not notification:
            raise ValidationError("Notification not found")
        employee = Employee.query.filter_by(user_id=user_id, is_deleted=False).first()
        if not employee:
            raise ValidationError("Employee profile not found")

        now_ts = datetime.utcnow()
        try:
            overtime_request = None
            attendance = None
            overtime_request_id = getattr(notification, "overtime_request_id", None)
            attendance_id = getattr(notification, "attendance_id", None)

            if overtime_request_id:
                overtime_request = OvertimeRequest.query.filter_by(
                    id=overtime_request_id,
                    employee_id=employee.id,
                    is_deleted=False,
                ).first()
            if attendance_id:
                attendance = Attendance.query.filter_by(
                    id=attendance_id,
                    employee_id=employee.id,
                    is_deleted=False,
                ).first()

            notification.is_deleted = True
            if hasattr(notification, "deleted_at"):
                setattr(notification, "deleted_at", now_ts)

            if overtime_request:
                overtime_request.is_deleted = True
                if hasattr(overtime_request, "deleted_at"):
                    setattr(overtime_request, "deleted_at", now_ts)

            if attendance and overtime_request:
                attendance.overtime_hours = 0

            db.session.add(
                HistoryLog(
                    employee_id=employee.id,
                    action="NOTIFICATION_CASCADE_DELETE",
                    entity_type="notification",
                    entity_id=notification.id,
                    description=(
                        f"OT cascade delete | notification_id={notification.id} "
                        f"| overtime_request_id={overtime_request.id if overtime_request else None} "
                        f"| attendance_id={attendance.id if attendance else None}"
                    ),
                    performed_by=user_id,
                )
            )
            db.session.commit()

            return True

        except Exception:
            db.session.rollback()
            raise

    # =========================================================
    # COUNT UNREAD (badge UI 🔴)
    # =========================================================

    @staticmethod
    def count_unread(user_id: int):
        return Notification.query.filter_by(
            user_id=user_id,
            is_read=False,
        ).count()