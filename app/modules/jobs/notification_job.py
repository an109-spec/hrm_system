from datetime import datetime, timedelta, timezone
from app.constants.attendance import WorkConfig
from app.extensions.db import db
from app.models.notification import Notification
from app.models.otp import OTPCode
from app.models import OvertimeRequest, Employee
from app.utils.time import VN_TIMEZONE, get_current_time

class NotificationJob:
    @staticmethod
    def push_overtime_shift_notifications():
        now = get_current_time().astimezone(VN_TIMEZONE)
        current_time = now.time().replace(second=0, microsecond=0)
        today = now.date()
        is_start_time = (current_time == WorkConfig.OT_START)
        is_end_time = (current_time == WorkConfig.OT_END)

        if not (is_start_time or is_end_time):
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
            if is_start_time:
                title = "🔔 Bắt đầu ca tăng ca"
                content = "Ca tăng ca đã bắt đầu. Vui lòng check-in để bắt đầu OT."
            else:
                title = "🔔 Kết thúc ca tăng ca"
                content = "Ca tăng ca đã kết thúc. Vui lòng check-out để hoàn tất chấm công."
            exists = Notification.query.filter(
                Notification.user_id == employee.user_id,
                Notification.title == title,
                Notification.type == "overtime",
                Notification.created_at >= datetime.combine(today, datetime.min.time())
            ).first()

            if exists:
                continue
            db.session.add(Notification(
                user_id=employee.user_id, 
                title=title, 
                content=content, 
                type="overtime", 
                link="/employee/attendance"
            ))
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