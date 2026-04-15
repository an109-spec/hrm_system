from datetime import datetime, timedelta, timezone
from app.extensions.db import db
from app.models.notification import Notification
from app.models.otp import OTPCode


class NotificationJob:

    @staticmethod
    def cleanup_old_notifications(days: int = 30):
        """
        Xoá notification cũ hơn N ngày (soft cleanup logic)
        """
        threshold = datetime.now(timezone.utc) - timedelta(days=days)

        Notification.query.filter(
            Notification.created_at < threshold
        ).delete()

        db.session.commit()

    @staticmethod
    def cleanup_expired_otp():
        """
        Xoá OTP hết hạn
        """
        now = datetime.now(timezone.utc)

        OTPCode.query.filter(
            OTPCode.expired_at < now
        ).delete()

        db.session.commit()