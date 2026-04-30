# app/modules/notification/service.py

from __future__ import annotations

from app.extensions.db import db
from app.models.notification import Notification
from app.models.overtime_request import OvertimeRequest
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
            raise ValidationError(
                "Notification not found"
            )

        try:
            # =====================================
            # CASE: OVERTIME NOTIFICATION
            # =====================================
            if notification.type == "overtime":
                """
                Cách liên kết phổ biến:
                notification.link

                Ví dụ:
                /employee/overtime/12

                hoặc:
                overtime_request:12
                """

                overtime_request = None

                if notification.link:
                    # CASE 1:
                    # link dạng overtime_request:12
                    if "overtime_request:" in notification.link:
                        try:
                            request_id = int(
                                notification.link.split(":")[-1]
                            )

                            overtime_request = (
                                OvertimeRequest.query.filter_by(
                                    id=request_id,
                                    employee_id=user_id
                                ).first()
                            )
                        except Exception:
                            pass

                    # CASE 2:
                    # link dạng URL /overtime/12
                    elif "/overtime/" in notification.link:
                        try:
                            request_id = int(
                                notification.link.rstrip("/")
                                .split("/")[-1]
                            )

                            overtime_request = (
                                OvertimeRequest.query.filter_by(
                                    id=request_id,
                                    employee_id=user_id
                                ).first()
                            )
                        except Exception:
                            pass

                # nếu tìm thấy request → xóa luôn
                if overtime_request:
                    db.session.delete(
                        overtime_request
                    )

            # =====================================
            # DELETE NOTIFICATION
            # =====================================
            db.session.delete(notification)
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