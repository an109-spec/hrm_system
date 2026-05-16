from app.models.employee import Employee
from app.models.history import HistoryLog
from app.common.exceptions import NotFoundError
from app.extensions.db import db
from app.utils.time import get_current_time


class ProfileService:

    @staticmethod
    def get_full_profile(employee_id):
        emp = db.session.get(Employee, employee_id)
        if not emp:
            raise NotFoundError("Employee not found")

        return {
            "basic": {
                "full_name": emp.full_name,
                "dob": emp.dob.strftime("%d/%m/%Y") if emp.dob else None,
                "age": emp.age,
                "phone": emp.phone,
                "address": emp.address,
            },
            "job": {
                "department": emp.department.name if emp.department else None,
                "position": emp.position.job_title if emp.position else None,
                "manager": emp.manager.full_name if emp.manager else None,
                "hire_date": emp.hire_date.strftime("%d/%m/%Y") if emp.hire_date else None,
                "employment_type": emp.employment_type,
            },
            "system": {
                "created_at": emp.created_at.strftime("%d/%m/%Y %H:%M") if emp.created_at else None,
                "updated_at": emp.updated_at.strftime("%d/%m/%Y %H:%M") if emp.updated_at else None,
                "is_deleted": emp.is_deleted,
            }
        }

    @staticmethod
    def get_history(employee_id):
        logs = HistoryLog.query.filter_by(
            employee_id=employee_id,
            is_deleted=False
        ).order_by(HistoryLog.created_at.desc()).all()

        return [
            {
                "action": log.action,
                "entity": log.entity_type,
                "description": log.description,
                "time": log.created_at.strftime("%d/%m/%Y %H:%M") if log.created_at else None
            }
            for log in logs
        ]