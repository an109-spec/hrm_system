from __future__ import annotations

from app.models import Attendance, HistoryLog, Notification, OvertimeRequest, Employee
from app.models.base import db


def reset_overtime_request_flow(*, overtime_request: OvertimeRequest, actor_user_id: int | None = None, source: str = "system") -> dict:
    employee = Employee.query.get(overtime_request.employee_id)
    user_id = employee.user_id if employee else None

    same_day_requests = OvertimeRequest.query.filter_by(
        employee_id=overtime_request.employee_id,
        overtime_date=overtime_request.overtime_date,
    ).all()
    request_ids = [row.id for row in same_day_requests]

    if user_id:
        Notification.query.filter(
            Notification.user_id == user_id,
            Notification.type == "overtime",
        ).delete(synchronize_session=False)

    attendance = Attendance.query.filter_by(
        employee_id=overtime_request.employee_id,
        date=overtime_request.overtime_date,
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
                f"Reset OT flow from {source} | date={overtime_request.overtime_date.isoformat()} "
                f"| deleted_requests={len(request_ids)}"
            ),
            performed_by=actor_user_id,
        )
    )
    db.session.commit()
    return {"success": True, "deleted_requests": len(request_ids), "overtime_date": overtime_request.overtime_date.isoformat()}