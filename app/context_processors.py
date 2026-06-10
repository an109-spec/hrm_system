"""
app/context_processors.py
Context processor inject các biến dùng chung vào toàn bộ template HRM.
"""
from flask import session

from app.utils.time import get_current_time


def register_context_processors(app):
    """Đăng ký tất cả context processor vào app."""

    @app.context_processor
    def inject_globals():
        """Truyền các biến dùng chung ra toàn bộ template HRM."""
        from app.models import User, Notification, Employee

        current_user         = None
        current_employee     = None
        avatar_url           = None
        header_notifications = []
        unread_notifications = 0
        now     = get_current_time()
        user_id = session.get("user_id")

        try:
            normalized_user_id = int(user_id) if user_id is not None else None
        except (TypeError, ValueError):
            normalized_user_id = None

        if normalized_user_id:
            current_user = User.query.get(normalized_user_id)
            if current_user:
                current_employee = Employee.query.filter_by(
                    user_id=current_user.id
                ).first()

                if current_employee and current_employee.avatar:
                    version    = int((current_employee.updated_at or now).timestamp())
                    avatar_url = f"{current_employee.avatar}?v={version}"

                header_notifications = (
                    Notification.query
                    .filter_by(user_id=current_user.id)
                    .order_by(Notification.created_at.desc())
                    .limit(5)
                    .all()
                )
                unread_notifications = Notification.query.filter_by(
                    user_id=current_user.id, is_read=False
                ).count()

        return {
            "current_year":         now.year,
            "current_user":         current_user,
            "current_employee":     current_employee,
            "avatar_url":           avatar_url,
            "header_notifications": header_notifications,
            "unread_notifications": unread_notifications,
            "system_name":          "HRM System",
        }