from app.models.employee import Employee
from app.models.history import HistoryLog
from app.common.exceptions import NotFoundError


class ProfileService:

    @staticmethod
    def get_full_profile(employee_id):
        emp = Employee.query.get(employee_id)
        if not emp:
            raise NotFoundError("Employee not found")

        return {
            "basic": {
                "full_name": emp.full_name,
                "dob": str(emp.dob),
                "age": emp.age,
                "phone": emp.phone,
                "address": emp.address,
            },
            "job": {
                "department": emp.department.name if emp.department else None,
                "position": emp.position.job_title if emp.position else None,
                "manager": emp.manager.full_name if emp.manager else None,
                "hire_date": str(emp.hire_date),
                "employment_type": emp.employment_type,
            },
            "system": {
                "created_at": str(emp.created_at),
                "updated_at": str(emp.updated_at),
                "is_deleted": emp.is_deleted,
            }
        }

    @staticmethod
    def get_history(employee_id):
        logs = HistoryLog.query.filter_by(employee_id=employee_id).all()

        return [
            {
                "action": log.action,
                "entity": log.entity_type,
                "description": log.description,
                "time": str(log.created_at)
            }
            for log in logs
        ]