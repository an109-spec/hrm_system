from __future__ import annotations
from datetime import date, datetime, timedelta
from sqlalchemy import or_
from app.constants.employee import WorkingStatus, EmploymentType
from app.extensions.db import db
from app.models import (
    Contract,
    Employee,
    User,
)
from app.common.exceptions import ValidationError, NotFoundError
from app.modules.history.service import HistoryService
from .contract_service import Admin_Service
class Employee_service:
    @staticmethod
    def reset_employee_password(user_id: int, new_password: str, actor_id: int) -> None:
        # 1. Tìm User
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError(f"Không tìm thấy tài khoản với ID {user_id}")
        clean_password = (new_password or "").strip()
        if len(clean_password) < 8:
            raise ValidationError("Mật khẩu mới tối thiểu 8 ký tự")
        user.set_password(clean_password)
        user.failed_login_attempts = 0
        user.locked_at = None
        user.lock_reason = None
        employee_id = user.employee_profile.id if user.employee_profile else None
        HistoryService.log_event(
            action="RESET_PASSWORD",
            employee_id=employee_id,
            entity_type="user",
            entity_id=user.id,
            description="Admin đã reset mật khẩu cho tài khoản",
            performed_by=actor_id
        )
        db.session.commit()

    @staticmethod
    def lock_user_account(user_id: int, reason: str, performed_by: int) -> User:
        """Khóa tài khoản người dùng"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError(f"Không tìm thấy người dùng có ID: {user_id}")
        if not user.is_active:
            return user # Đã khóa rồi thì không cần làm gì thêm
        # Cập nhật trạng thái
        user.is_active = False
        user.locked_at = datetime.now()
        user.locked_by = performed_by
        user.lock_reason = reason
        try:
            db.session.commit()
            HistoryService.log_event(
                action="LOCK_USER",
                employee_id=user.employee_profile.id if user.employee_profile else None,
                entity_type="USER",
                entity_id=user.id,
                description=f"Khóa tài khoản bởi Admin ID {performed_by}. Lý do: {reason}",
                performed_by=performed_by
            )
            return user
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def unlock_user_account(user_id: int, performed_by: int) -> User:
        """Mở khóa tài khoản người dùng"""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundError(f"Không tìm thấy người dùng có ID: {user_id}")
        # Reset trạng thái
        user.is_active = True
        user.locked_at = None
        user.locked_by = None
        user.lock_reason = None
        user.failed_login_attempts = 0 # Reset cả số lần đăng nhập sai nếu cần
        try:
            db.session.commit()
            HistoryService.log_event(
                action="UNLOCK_USER",
                employee_id=user.employee_profile.id if user.employee_profile else None,
                entity_type="USER",
                entity_id=user.id,
                description=f"Mở khóa tài khoản bởi Admin ID {performed_by}",
                performed_by=performed_by
            )
            return user
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_inactive_employee_filter():
        return or_(
            Employee.working_status == WorkingStatus.RESIGNED,
            Employee.user.has(
                or_(
                    User.is_active == False,
                    User.locked_at != None  

                )
            )
        )

    @staticmethod
    def get_employee_summary(
        department_id: int = None,
        position_id: int = None,
        working_status: str = None,
        employment_type: str = None,
        today: date = None
    ) -> dict[str, int]:
        current_date = today or get_current_time().date()
        contract_cutoff = current_date + timedelta(days=30)
        base_query = Employee.query.filter(Employee.is_deleted.is_(False))
        if department_id:
            base_query = base_query.filter(Employee.department_id == department_id)
        if position_id:
            base_query = base_query.filter(Employee.position_id == position_id)
        filtered_query = base_query
        if working_status:
            filtered_query = filtered_query.filter(Employee.working_status == working_status)
        if employment_type:
            filtered_query = filtered_query.filter(Employee.employment_type == employment_type)
        total = filtered_query.count()
        working = filtered_query.filter(Employee.working_status == WorkingStatus.ACTIVE).count()
        probation = filtered_query.filter(Employee.employment_type == EmploymentType.PROBATION).count()
        inactive = filtered_query.filter(Admin_Service.get_inactive_employee_filter()).count()
        contract_query = Contract.query.join(Employee).filter(
            Employee.is_deleted.is_(False),
            Contract.status == 'active',
            Contract.end_date.isnot(None),
            Contract.end_date >= current_date,
            Contract.end_date <= contract_cutoff,
        )
        if department_id:
            contract_query = contract_query.filter(Employee.department_id == department_id)
        if position_id:
            contract_query = contract_query.filter(Employee.position_id == position_id)
        return {
            "total": total,
            "working": working,
            "probation": probation,
            "inactive": inactive,
            "expiring_contract": contract_query.count(),

        }