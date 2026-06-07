from app.constants.common import RoleName
from app.models.history import HistoryLog
from app.models.employee import Employee
from app.common.exceptions import NotFoundError
from app.extensions.db import db


class HistoryService:

    @staticmethod
    def get_personal_timeline(user_id: int):
        """
        Dùng chung cho mọi Role (Admin, HR, Manager, Employee).
        Mỗi tài khoản chỉ xem được lịch sử của 'Employee' được gắn với 'user_id' đó.
        """
        # 1. Tìm Employee link với User đang đăng nhập
        emp = Employee.query.filter_by(user_id=user_id).first()
        if not emp:
            # Nếu tài khoản là Admin/Manager nhưng chưa được tạo profile Employee,
            # bạn có thể trả về lỗi hoặc log rỗng tùy vào nghiệp vụ của bạn.
            raise NotFoundError("Tài khoản này chưa có hồ sơ nhân viên để hiển thị lịch sử.")
        logs = (
            HistoryLog.query
            .filter_by(employee_id=emp.id)
            .order_by(HistoryLog.created_at.desc())
            .all()
        )
        return {
            "employee_id": emp.id,
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
    def get_system_logs(current_user, page=1, per_page=20, employee_name=None, action_type=None, from_date=None, to_date=None):
        """
        Dành riêng cho Admin/HR để xem toàn bộ lịch sử hệ thống.
        """
        allowed_roles = [RoleName.ADMIN, RoleName.HR]
        if not current_user.role or current_user.role.name not in allowed_roles:
            raise PermissionError("Bạn không có quyền truy cập lịch sử toàn hệ thống.")
        query = HistoryLog.query.join(Employee, HistoryLog.employee_id == Employee.id)
        if employee_name:
            query = query.filter(Employee.full_name.ilike(f'%{employee_name}%'))
        if action_type:
            query = query.filter(HistoryLog.action == action_type)
        if from_date:
            query = query.filter(HistoryLog.created_at >= from_date)
        if to_date:
            query = query.filter(HistoryLog.created_at <= to_date)
        pagination = query.order_by(HistoryLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return {
            "total_items": pagination.total,
            "total_pages": pagination.pages,
            "current_page": pagination.page,
            "logs": [
                {
                    "id": log.id,
                    "employee_name": log.employee.full_name if log.employee else "N/A",
                    "action": log.action,
                    "description": log.description,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                    "performed_by": log.performed_by
                }
                for log in pagination.items
            ]
        }

    @staticmethod
    def get_manager_subordinates_timeline(current_user, page=1, per_page=20):
        """
        Dành cho Manager: Xem lịch sử của tất cả cấp dưới trực tiếp.
        """
        manager_profile = Employee.query.filter_by(user_id=current_user.id).first()
        if not manager_profile:
            raise NotFoundError("Không tìm thấy hồ sơ nhân viên của bạn.")
        logs = (
            HistoryLog.query
            .join(Employee, HistoryLog.employee_id == Employee.id)
            .filter(Employee.manager_id == manager_profile.id)
            .order_by(HistoryLog.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
        return {
            "total_items": logs.total,
            "current_page": logs.page,
            "total_pages": logs.pages,
            "timeline": [
                {
                    "id": log.id,
                    "employee_name": log.employee.full_name, # Lấy tên từ quan hệ relationship
                    "action": log.action,
                    "description": log.description,
                    "performed_by": log.performed_by,
                    "created_at": log.created_at.isoformat() if log.created_at else None
                }
                for log in logs.items
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
        Ghi log hệ thống bằng cách gọi phương thức append từ Model HistoryLog
        """
        log = HistoryLog.append(
            employee_id=employee_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            performed_by=performed_by
        )
        return log