from functools import wraps
from flask import g
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.common.exceptions import UnauthorizedError, ForbiddenError
from app.models.user import User
from app.extensions.db import db


# =========================
# 🔐 AUTH REQUIRED
# =========================
def auth_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()

        user = db.session.get(User, user_id)

        if not user or not user.is_active:
            raise UnauthorizedError("Tài khoản không tồn tại hoặc đã bị khóa")

        # ✅ dùng relationship (tối ưu hơn query)
        employee = user.employee_profile

        if employee and employee.working_status == 'resigned':
            raise UnauthorizedError("Nhân viên đã nghỉ việc không thể truy cập")

        # ✅ cache vào g (rất chuẩn)
        g.user = user
        g.employee = employee

        return fn(*args, **kwargs)

    return wrapper


# =========================
# 🔐 ROLE REQUIRED
# =========================
def role_required(*role_names):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = getattr(g, "user", None)

            if not user or not user.role:
                raise ForbiddenError("Không xác định được quyền người dùng")

            if user.role.name not in role_names:
                raise ForbiddenError("Bạn không có quyền truy cập")

            return fn(*args, **kwargs)

        return wrapper
    return decorator


# =========================
# 🔐 SELF OR HR
# =========================
def self_or_hr_required(employee_id_key='employee_id'):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = getattr(g, "user", None)

            if not user or not user.role:
                raise ForbiddenError("Không xác định được quyền")

            target_employee_id = kwargs.get(employee_id_key)

            # ✅ Admin / HR bypass
            if user.role.name in ['Admin', 'HR']:
                return func(*args, **kwargs)

            current_employee = getattr(g, "employee", None)

            if current_employee and str(current_employee.id) == str(target_employee_id):
                return func(*args, **kwargs)

            raise ForbiddenError("Bạn không thể xem thông tin của người khác")

        return wrapper
    return decorator