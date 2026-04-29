from datetime import datetime, timedelta, timezone
from app.extensions.db import db
from app.models.notification import Notification
from app.models.otp import OTPCode
from app.models import OvertimeRequest, Employee

class NotificationJob:
    @staticmethod
    def push_overtime_shift_notifications(now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        local_now = now.replace(tzinfo=None)
        hhmm = local_now.strftime("%H:%M")
        today = local_now.date()
        if hhmm not in {"19:00", "22:00"}:
            return
        approved_rows = OvertimeRequest.query.filter(
            OvertimeRequest.overtime_date == today,
            OvertimeRequest.status == "approved",
            OvertimeRequest.is_deleted.is_(False),
        ).all()
        for row in approved_rows:
            employee = Employee.query.get(row.employee_id)
            if not employee or not employee.user_id:
                continue
            title = "🔔 Bắt đầu ca tăng ca" if hhmm == "19:00" else "🔔 Kết thúc ca tăng ca"
            content = (
                "Ca tăng ca đã bắt đầu. Vui lòng check-in để bắt đầu OT."
                if hhmm == "19:00"
                else "Ca tăng ca đã kết thúc. Vui lòng check-out để hoàn tất chấm công."
            )
            exists = Notification.query.filter_by(user_id=employee.user_id, title=title, type="overtime").filter(
                Notification.created_at >= datetime.combine(today, datetime.min.time())
            ).first()
            if exists:
                continue
            db.session.add(Notification(user_id=employee.user_id, title=title, content=content, type="overtime", link="/employee/attendance"))
        db.session.commit()
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