from __future__ import annotations
from datetime import datetime

from sqlalchemy import or_

from app.models import Attendance, HistoryLog, Notification, OvertimeRequest, Employee
from app.models.base import db


def reset_overtime_request_flow(*, overtime_request: OvertimeRequest, actor_user_id: int | None = None, source: str = "system", anchor_notification_id: int | None = None) -> dict:
    overtime_date = overtime_request.overtime_date
    employee = Employee.query.get(overtime_request.employee_id)
    user_id = employee.user_id if employee else None
    now_ts = datetime.utcnow()
    same_day_requests = OvertimeRequest.query.filter_by(
        employee_id=overtime_request.employee_id,
        overtime_date=overtime_date,
        is_deleted=False,
    ).all()
    request_ids = [row.id for row in same_day_requests]

    notification_ids: set[int] = set()
    if anchor_notification_id is not None:
        notification_ids.add(anchor_notification_id)
    if user_id and request_ids:
        for req_id in request_ids:
            exact_tokens = (
                f"overtime_request:{req_id}",
                f"/overtime/{req_id}",
                f"/attendance/overtime/{req_id}",
            )
            linked = Notification.query.filter(
                Notification.user_id == user_id,
                Notification.is_deleted.is_(False),
                or_(*[Notification.link == token for token in exact_tokens]),
            ).all()
            for row in linked:
                notification_ids.add(row.id)

    deleted_notifications = 0
    for notification_id in notification_ids:
        noti = Notification.query.filter_by(id=notification_id, is_deleted=False).first()
        if not noti:
            continue
        noti.is_deleted = True
        if hasattr(noti, "deleted_at"):
            setattr(noti, "deleted_at", now_ts)
        deleted_notifications += 1

    attendance = Attendance.query.filter_by(
        employee_id=overtime_request.employee_id,
        date=overtime_date,
    ).first()
    before_attendance = {
        "attendance_type": attendance.attendance_type if attendance else None,
        "overtime_hours": str(attendance.overtime_hours) if attendance else None,
    }
    if attendance:
        attendance.overtime_hours = 0
        is_weekend = overtime_date.weekday() >= 5
        has_approved_payroll = False
        if attendance.attendance_type in {"overtime", "normal"} and not is_weekend and not has_approved_payroll:
            attendance.attendance_type = "normal"

    deleted_requests = 0
    for row in same_day_requests:
        row.is_deleted = True
        if hasattr(row, "deleted_at"):
            setattr(row, "deleted_at", now_ts)
        deleted_requests += 1

    after_attendance = {
        "attendance_type": attendance.attendance_type if attendance else None,
        "overtime_hours": str(attendance.overtime_hours) if attendance else None,
    }
    db.session.add(
        HistoryLog(
            employee_id=overtime_request.employee_id,
            action="OT_RESET",
            entity_type="overtime_request",
            entity_id=overtime_request.id,
            description=(
                f"Reset OT flow from {source} | reason=OT_RESET | date={overtime_date.isoformat()} "
                f"| old_attendance={before_attendance} | new_attendance={after_attendance} "
                f"| soft_deleted_requests={deleted_requests} | soft_deleted_notifications={deleted_notifications}"
            ),
            performed_by=actor_user_id,
        )
    )
    db.session.commit()
    return {
        "success": True,
        "deleted_requests": deleted_requests,
        "deleted_notifications": deleted_notifications,
        "overtime_date": overtime_date.isoformat(),
    }