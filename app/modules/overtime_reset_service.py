from __future__ import annotations

from sqlalchemy import or_

from app.models import Attendance, HistoryLog, Notification, OvertimeRequest, Employee
from app.models.base import db


def reset_overtime_request_flow(*, overtime_request: OvertimeRequest, actor_user_id: int | None = None, source: str = "system") -> dict:
    overtime_date = overtime_request.overtime_date
    employee = Employee.query.get(overtime_request.employee_id)
    user_id = employee.user_id if employee else None

    same_day_requests = OvertimeRequest.query.filter_by(
        employee_id=overtime_request.employee_id,
        overtime_date=overtime_date,
    ).all()
    request_ids = [row.id for row in same_day_requests]

    deleted_notifications = 0
    if user_id:
        date_token = overtime_date.strftime("%d/%m/%Y")
        notification_query = Notification.query.filter(
            Notification.user_id == user_id,
            Notification.is_deleted.is_(False),
            or_(
                Notification.type == "overtime",
                Notification.content.ilike(f"%OT%"),
                Notification.title.ilike(f"%OT%"),
            ),
            Notification.content.ilike(f"%{date_token}%"),
        )
        deleted_notifications = notification_query.count()
        notification_query.delete(synchronize_session=False)

    attendance = Attendance.query.filter_by(
        employee_id=overtime_request.employee_id,
        date=overtime_date,
    ).first()
    if attendance:
        attendance.overtime_hours = 0
        if attendance.attendance_type in {"overtime", "holiday"}:
            attendance.attendance_type = "normal"

    if request_ids:
        OvertimeRequest.query.filter(OvertimeRequest.id.in_(request_ids)).delete(synchronize_session=False)

    db.session.add(
        HistoryLog(
            employee_id=overtime_request.employee_id,
            action="OVERTIME_RESET_FOR_TEST",
            entity_type="overtime_request",
            entity_id=overtime_request.id,
            description=(
                f"Reset OT flow from {source} | date={overtime_date.isoformat()} "
                f"| deleted_requests={len(request_ids)}"
            ),
            performed_by=actor_user_id,
        )
    )
    db.session.commit()
    return {
        "success": True,
        "deleted_requests": len(request_ids),
        "deleted_notifications": deleted_notifications,
        "overtime_date": overtime_date.isoformat(),
    }