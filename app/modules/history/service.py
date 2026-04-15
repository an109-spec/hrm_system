from app.models.history import HistoryLog
from app.models.employee import Employee
from app.common.exceptions import NotFoundError
from app.extensions.db import db


class HistoryService:

    @staticmethod
    def get_employee_timeline(employee_id: int):
        emp = Employee.query.get(employee_id)
        if not emp:
            raise NotFoundError("Employee not found")

        logs = (
            HistoryLog.query
            .filter_by(employee_id=employee_id)
            .order_by(HistoryLog.created_at.desc())
            .all()
        )

        return {
            "employee_id": employee_id,
            "employee_name": emp.full_name,
            "timeline": [
                {
                    "id": log.id,
                    "action": log.action,
                    "entity_type": log.entity_type,
                    "entity_id": log.entity_id,
                    "description": log.description,
                    "performed_by": log.performed_by,
                    "created_at": log.created_at.isoformat() if log.created_at else None
                }
                for log in logs
            ]
        }

    @staticmethod
    def log_event(
        action: str,
        employee_id: int = None,
        entity_type: str = None,
        entity_id: int = None,
        description: str = None,
        performed_by: int = None
    ):
        """
        Ghi log hệ thống (dùng chung toàn project)
        """
        log = HistoryLog(
            action=action,
            employee_id=employee_id,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            performed_by=performed_by
        )

        db.session.add(log)
        db.session.commit()

        return log