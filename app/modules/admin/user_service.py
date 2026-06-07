from __future__ import annotations
from sqlalchemy import or_, func

from app.constants.common import RoleName
from app.extensions.db import db
from app.models import (
    Contract,
    Role,
    User,
)
from app.modules.history.service import HistoryService
from .contract_service import Admin_Service
class User_Service: 
    @staticmethod
    def _check_user_duplicates(username: str, email: str):
        """Kiểm tra sự tồn tại của username hoặc email"""
        if User.query.filter_by(username=username).first():
            raise ValueError(f"Tên đăng nhập '{username}' đã tồn tại")
        if User.query.filter_by(email=email).first():
            raise ValueError(f"Email '{email}' đã tồn tại")

    @staticmethod
    def _resolve_employee_role() -> Role:
        """
        Lấy role Employee từ database dựa trên hằng số cấu hình.
        """
        role = Role.query.filter(func.lower(Role.name) == RoleName.EMPLOYEE.lower()).first()
        if not role:
            raise ValueError(f"Chưa cấu hình role '{RoleName.EMPLOYEE}' trong hệ thống. Vui lòng kiểm tra database.")
        return role

    @staticmethod
    def create_user_for_pending_employee(employee_id: int, user_data: dict, current_user_id: int) -> User:
        """
        Tạo tài khoản cho nhân viên đang chờ (pending) và thiết lập liên kết 2 chiều.
        Điều kiện: Nhân viên phải có hợp đồng 'active' và chưa hết hạn.
        """
        # 1. Lấy thông tin nhân viên (đảm bảo nhân viên này chưa có tài khoản)
        employee = Admin_Service.get_pending_employee_detail(employee_id)

        # 2. KIỂM TRA HỢP ĐỒNG (Bổ sung mới)
        # Tìm hợp đồng đang có trạng thái 'active'
        active_contract = Contract.query.filter_by(
            employee_id=employee.id, 
            status='active'
        ).first()

        # Kiểm tra: Phải có hợp đồng tồn tại VÀ không được quá hạn
        if not active_contract:
            raise ValueError(f"Nhân viên {employee.full_name} chưa có hợp đồng lao động. Vui lòng tạo hợp đồng trước.")
        
        if active_contract.is_expired:
            raise ValueError(f"Hợp đồng của nhân viên {employee.full_name} đã hết hạn. Vui lòng gia hạn hợp đồng.")

        # 3. Validate thông tin tài khoản
        username = user_data.get("username")
        email = user_data.get("email")
        password = user_data.get("password")
        role_id = user_data.get("role_id")

        if not username or not email or not password or not role_id:
            raise ValueError("Thông tin tài khoản không đầy đủ (username, email, password, role_id)")

        # Kiểm tra trùng lặp
        if User.query.filter(or_(User.username == username, User.email == email)).first():
            raise ValueError("Username hoặc Email đã tồn tại trong hệ thống")

        # Kiểm tra Role hợp lệ
        role = Role.query.get(role_id)
        if not role:
            raise ValueError(f"Role ID {role_id} không tồn tại")

        # 4. Tạo User
        new_user = User(
            username=username,
            email=email,
            role_id=role_id
        )
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.flush() # Flush để lấy new_user.id trước khi commit

            # 5. Liên kết User với Employee
            employee.user = new_user 

            # 6. Ghi log lịch sử
            HistoryService.log_event(
                action="CREATE_ACCOUNT",
                employee_id=employee.id,
                entity_type="User",
                entity_id=new_user.id,
                description=f"Tạo tài khoản hệ thống cho nhân viên: {employee.full_name} (HĐ: {active_contract.contract_code}, Role: {role.name})",
                performed_by=current_user_id
            )

            db.session.commit()
            return new_user
            
        except Exception as e:
            db.session.rollback()
            raise e

    '''
    PHÂN QUYỀN 
    '''
    @staticmethod
    def assign_role_to_user(user_id: int, role_name: str, performed_by: int = None) -> User:
        """
        Gán vai trò sử dụng RoleName để đảm bảo tính đồng bộ.
        """
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"Không tìm thấy người dùng có ID: {user_id}")
        valid_roles = [RoleName.ADMIN, RoleName.HR, RoleName.MANAGER, RoleName.EMPLOYEE]
        if role_name not in valid_roles:
            raise ValueError(f"Vai trò '{role_name}' không hợp lệ. Chỉ chấp nhận: {', '.join(valid_roles)}")
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            raise ValueError(f"Vai trò '{role_name}' chưa được khởi tạo trong database")
        if user.role_id == role.id:
            return user
        old_role_name = user.role.name if user.role else "None"
        user.role_id = role.id
        db.session.commit()
        employee_id = user.employee_profile.id if user.employee_profile else None
        HistoryService.log_event(
            action="UPDATE_ROLE",
            employee_id=employee_id,
            entity_type="USER",
            entity_id=user.id,
            description=f"Thay đổi vai trò từ '{old_role_name}' sang '{role_name}'",
            performed_by=performed_by
        )
        return user

    @staticmethod
    def get_all_roles():
        return Role.query.all()
    

    
 