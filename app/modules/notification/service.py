from app.extensions.db import db
from app.models.notification import Notification
from .dto import NotificationDTO


class NotificationService:

    # =========================
    # CREATE NOTIFICATION
    # =========================
    @staticmethod
    def create(dto: NotificationDTO):
        notification = Notification(
            user_id=dto.user_id,
            title=dto.title,
            content=dto.content,
            type=dto.type,
            link=dto.link,
            is_read=dto.is_read
        )

        db.session.add(notification)
        db.session.commit()

        return notification

    # =========================
    # GET USER NOTIFICATIONS
    # =========================
    @staticmethod
    def get_by_user(user_id: int, limit: int = 20, only_unread: bool = False):
        query = Notification.query.filter_by(user_id=user_id)

        if only_unread:
            query = query.filter_by(is_read=False)

        return (
            query.order_by(Notification.created_at.desc())
            .limit(limit)
            .all()
        )

    # =========================
    # MARK AS READ
    # =========================
    @staticmethod
    def mark_as_read(notification_id: int, user_id: int):
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=user_id
        ).first()

        if not notification:
            raise ValueError("Notification not found")

        notification.is_read = True
        db.session.commit()

        return notification

    # =========================
    # MARK ALL AS READ
    # =========================
    @staticmethod
    def mark_all_as_read(user_id: int):
        Notification.query.filter_by(
            user_id=user_id,
            is_read=False
        ).update({"is_read": True})

        db.session.commit()

        return True

    # =========================
    # DELETE NOTIFICATION
    # =========================
    @staticmethod
    def delete(notification_id: int, user_id: int):
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=user_id
        ).first()

        if not notification:
            raise ValueError("Notification not found")

        db.session.delete(notification)
        db.session.commit()

        return True

    # =========================
    # COUNT UNREAD (for badge UI 🔴)
    # =========================
    @staticmethod
    def count_unread(user_id: int):
        return Notification.query.filter_by(
            user_id=user_id,
            is_read=False
        ).count()