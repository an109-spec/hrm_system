from functools import wraps
from flask import g, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from app.common.exceptions import UnauthorizedError, ForbiddenError
from app.models.user import User
from app.models.employee import Employee

def auth_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or not user.is_active:
            raise UnauthorizedError("Tài khoản không tồn tại hoặc đã bị khóa")

        employee = Employee.query.filter_by(user_id=user.id).first()
        if employee and employee.working_status == 'resigned':
            raise UnauthorizedError("Nhân viên đã nghỉ việc không thể truy cập")

        g.user = user
        g.employee = employee 
        return fn(*args, **kwargs)
    return wrapper

def role_required(*role_names):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = getattr(g, "user", None)
            if not user or user.role.name not in role_names:
                raise ForbiddenError("Bạn không có quyền truy cập")
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# BÊ HÀM NÀY TỪ PERMISSION SANG VÀ SỬA DÙNG JWT/G.USER
def self_or_hr_required(employee_id_key='employee_id'):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = getattr(g, "user", None)
            target_employee_id = kwargs.get(employee_id_key)
            
            # Admin và HR được xem tất cả
            if user.role.name in ['Admin', 'HR']:
                return func(*args, **kwargs)
            
            # Nhân viên thường chỉ được xem của chính mình
            current_employee = getattr(g, "employee", None)
            if current_employee and current_employee.id == int(target_employee_id):
                return func(*args, **kwargs)
            
            raise ForbiddenError("Bạn không thể xem thông tin của người khác")
        return wrapper
    return decorator