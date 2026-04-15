from app.extensions.db import db
from app.models.employee import Employee
from app.models.user import User
from app.common.exceptions import NotFoundError, UnauthorizedError


class EmployeeService:

    @staticmethod
    def get_profile(user_id):
        user = User.query.get(user_id)
        if not user or not user.employee_profile:
            raise NotFoundError("Employee not found")

        emp = user.employee_profile

        return {
            "id": emp.id,
            "full_name": emp.full_name,
            "phone": emp.phone,
            "address": emp.address,
            "email": user.email,
            "position": emp.position.job_title if emp.position else None,
            "department": emp.department.name if emp.department else None,
        }

    @staticmethod
    def update_profile(user_id, dto):
        user = User.query.get(user_id)
        emp = user.employee_profile

        emp.full_name = dto.full_name
        emp.phone = dto.phone
        emp.address = dto.address

        db.session.commit()
        return emp.to_dict()

    @staticmethod
    def change_password(user_id, dto):
        user = User.query.get(user_id)

        if not user.check_password(dto.current_password):
            raise UnauthorizedError("Wrong current password")

        user.set_password(dto.new_password)
        db.session.commit()

        return {"message": "Password updated successfully"}