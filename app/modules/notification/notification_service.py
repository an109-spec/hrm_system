from __future__ import annotations
from app.common.exceptions import NotFoundError
from app.extensions.db import db
from app.models import Notification
from app.modules.notification.dto import NotificationDTO
from app.utils.time import VN_TIMEZONE

class NotificationService:

    @staticmethod
    def get_notifications(user_id: int, limit: int = 50) -> list[dict]:
        rows = Notification.query.filter_by(
            user_id=user_id,
            is_deleted=False
        ).order_by(Notification.created_at.desc()).limit(limit).all()
        result = []
        for noti in rows:
            created_at = noti.created_at
            if created_at:
                localized_dt = (
                    created_at.replace(tzinfo=VN_TIMEZONE) 
                    if created_at.tzinfo is None 
                    else created_at.astimezone(VN_TIMEZONE)
                )
                received_at_iso = localized_dt.isoformat()
            else:
                received_at_iso = None
            result.append({
                "id": noti.id,
                "type": noti.type,
                "title": noti.title,
                "content": noti.content,
                "link": noti.link,
                "is_read": noti.is_read,
                "received_at": received_at_iso, 
            })
        return result

    @staticmethod
    def _format_date(dt):
        """Helper nội bộ: Định dạng thời gian cho các method trong class này"""
        if not dt:
            return None
        localized_dt = dt.replace(tzinfo=VN_TIMEZONE) if dt.tzinfo is None else dt.astimezone(VN_TIMEZONE)
        return localized_dt.isoformat()

    @staticmethod
    def notification_detail(user_id: int, noti_id: int) -> dict:
        """Lấy chi tiết và đánh dấu đã đọc một thông báo"""
        noti = Notification.query.filter_by(
            id=noti_id,
            user_id=user_id,
            is_deleted=False
        ).first()

        if not noti:
            raise NotFoundError("Không tìm thấy thông báo")

        # Đánh dấu đã đọc
        if not noti.is_read:
            noti.mark_as_read()
            db.session.commit()

        return {
            "id": noti.id,
            "type": noti.type,
            "title": noti.title,
            "content": noti.content,
            "link": noti.link,
            "is_read": noti.is_read,
            "received_at": NotificationService._format_date(noti.created_at),
        }

    @staticmethod
    def mark_all_as_read(user_id: int) -> int:
        """Đánh dấu tất cả thông báo của user là đã đọc và trả về số lượng dòng đã cập nhật"""
        updated_count = Notification.query.filter_by(
            user_id=user_id, 
            is_read=False, 
            is_deleted=False
        ).update(
            {"is_read": True}, 
            synchronize_session=False
        )
        db.session.commit()
        return updated_count

    @staticmethod
    def create(dto: NotificationDTO) -> Notification:
        notification = Notification(
            user_id=dto.user_id,
            title=dto.title,
            content=dto.content,
            type=dto.type,
            link=dto.link,
            is_read=dto.is_read
        )
        db.session.add(notification)
        db.session.flush() 
        return notification


