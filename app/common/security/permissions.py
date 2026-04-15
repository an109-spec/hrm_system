from functools import wraps
from flask import g

from app.common.exceptions import ForbiddenError
from app.models.salary import Salary
from app.models.complaint import Complaint


# =========================
# 👤 SELF OR ADMIN/HR
# =========================
def is_self_or_hr(employee_id):
    user = g.user

    if user.role.name in ['Admin', 'HR']:
        return True

    if g.employee and g.employee.id == int(employee_id):
        return True

    return False


# =========================
# 👨‍💼 MANAGER SCOPE
# =========================
def is_manager_of(employee_id):
    current_employee = g.employee

    if not current_employee:
        return False

    # lấy danh sách nhân viên dưới quyền
    sub_ids = [e.id for e in current_employee.subordinates]

    return int(employee_id) in sub_ids


def manager_or_hr_required(employee_id_key='employee_id'):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = g.user
            target_employee_id = kwargs.get(employee_id_key)

            if user.role.name in ['Admin', 'HR']:
                return func(*args, **kwargs)

            if is_manager_of(target_employee_id):
                return func(*args, **kwargs)

            raise ForbiddenError("Bạn không có quyền truy cập nhân viên này")

        return wrapper
    return decorator


# =========================
# 💰 SALARY PERMISSION
# =========================
def salary_owner_or_hr_required(salary_id_key='salary_id'):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = g.user
            salary_id = kwargs.get(salary_id_key)

            salary = Salary.query.get(salary_id)
            if not salary:
                raise ForbiddenError("Không tìm thấy phiếu lương")

            if user.role.name in ['Admin', 'HR']:
                return func(*args, **kwargs)

            if g.employee and salary.employee_id == g.employee.id:
                return func(*args, **kwargs)

            raise ForbiddenError("Bạn không có quyền xem phiếu lương này")

        return wrapper
    return decorator


# =========================
# 📩 COMPLAINT PERMISSION
# =========================
def complaint_owner_or_hr_required(complaint_id_key='complaint_id'):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = g.user
            complaint_id = kwargs.get(complaint_id_key)

            complaint = Complaint.query.get(complaint_id)
            if not complaint:
                raise ForbiddenError("Không tìm thấy khiếu nại")

            if user.role.name in ['Admin', 'HR']:
                return func(*args, **kwargs)

            if g.employee and complaint.employee_id == g.employee.id:
                return func(*args, **kwargs)

            raise ForbiddenError("Bạn không có quyền truy cập khiếu nại này")

        return wrapper
    return decorator


# =========================
# 🔐 ACTION-BASED PERMISSION (ADVANCED)
# =========================
def permission_required(permission_name):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = g.user
            role = user.role.name

            role_permissions = {
                "Admin": ["*"],

                "HR": [
                    "employee:view",
                    "employee:update",
                    "salary:view",
                    "salary:handle",
                    "complaint:handle",
                    "leave:approve"
                ],

                "Manager": [
                    "employee:view_team",
                    "leave:approve"
                ],

                "Employee": [
                    "profile:view",
                    "salary:view_self",
                    "complaint:create"
                ]
            }

            permissions = role_permissions.get(role, [])

            if "*" in permissions or permission_name in permissions:
                return func(*args, **kwargs)

            raise ForbiddenError("Bạn không có quyền thực hiện hành động này")

        return wrapper
    return decorator