from __future__ import annotations
from typing import Any
from flask import abort
from sqlalchemy.orm import load_only, joinedload
from app.constants.common import RoleName
from app.extensions.db import db
from app.models import (
    Department,
    Employee,
    Position,
    Role,
    User,
)
from app.common.exceptions import ValidationError, NotFoundError, ConflictError
from app.modules.history.service import HistoryService
from .contract_service import Admin_Service
class Dept_Pos_Service: 

    @staticmethod
    def get_department_options():
        return [{"id": d.id, "label": d.name} for d in Department.query.filter_by(is_deleted=False, status=True).order_by(Department.name.asc()).all()]
    @staticmethod
    def get_position_options():
        return [{"id": p.id, "label": p.job_title} for p in Position.query.filter_by(is_deleted=False, status='active').order_by(Position.job_title.asc()).all()]
    @staticmethod
    def get_employees_by_filter(department_id: int = None, position_id: int = None):
        """
        Lấy danh sách nhân viên tối ưu: Chỉ lấy các cột cần thiết và join để lấy tên Phòng ban/Chức danh
        """
        query = Employee.query.options(
            load_only(
                Employee.id,
                Employee.full_name,
                Employee.phone,
                Employee.department_id,
                Employee.position_id,
                Employee.employment_type,
                Employee.working_status
            ),
            joinedload(Employee.department).load_only("name"),
            joinedload(Employee.position).load_only("job_title")
        ).filter_by(is_deleted=False)
        if department_id:
            query = query.filter(Employee.department_id == department_id)
        if position_id:
            query = query.filter(Employee.position_id == position_id)
        return query.all()

    @staticmethod
    def count_employees_by_department(department_id: int) -> int:
        """Đếm số lượng nhân viên hiện có trong một phòng ban"""
        return Employee.query.filter_by(
            department_id=department_id, 
            is_deleted=False
        ).count()

    @staticmethod
    def get_department_manager(department_id: int) -> Employee | None:
        """Lấy thông tin Quản lý (Manager) của một phòng ban"""
        dept = Department.query.get(department_id)
        if not dept or not dept.manager_id:
            return None
        return Employee.query.filter_by(id=dept.manager_id, is_deleted=False).first()
    
    @staticmethod
    def employee_filter_metadata() -> dict[str, list[dict[str, Any]]]:
        """
        Lấy danh sách các dữ liệu dùng để render bộ lọc (filter) trên giao diện.
        Chỉ lấy các bản ghi đang hoạt động (active/not deleted).
        """
        return {
            "departments": [
                {"id": int(d.id), "name": d.name} 
                for d in Department.query.filter_by(is_deleted=False, status=True).order_by(Department.name.asc()).all()
            ],
            "positions": [
                {"id": int(p.id), "name": p.job_title} 
                for p in Position.query.filter_by(is_deleted=False, status='active').order_by(Position.job_title.asc()).all()
            ],
            "roles": [
                {"id": int(r.id), "name": r.name} 
                for r in Role.query.order_by(Role.name.asc()).all()
            ],
        }
    '''
    PHÒNG BAN/ CHỨC DANH
    '''
    @staticmethod
    def transfer_employee(employee_id: int, payload: dict[str, Any], actor_id: int) -> Employee:
        """
        Hàm cửa ngõ để thực hiện chuyển phòng ban/chức danh cho nhân viên.
        Đảm bảo tính nhất quán về validation và lưu vết lịch sử.
        """
        # 1. Tìm nhân viên
        employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first()
        if not employee:
            abort(404, description="Nhân viên không tồn tại")
        new_dept_id = payload.get("department_id")
        new_pos_id = payload.get("position_id")
        Admin_Service._validate_work_structure(
            department_id=new_dept_id, 
            position_id=new_pos_id
        )
        old_dept_name = employee.department.name if employee.department else "N/A"
        old_pos_title = employee.position.job_title if employee.position else "N/A"
        has_changed = False
        if new_dept_id is not None and new_dept_id != employee.department_id:
            employee.department_id = new_dept_id
            has_changed = True
        if new_pos_id is not None and new_pos_id != employee.position_id:
            employee.position_id = new_pos_id
            has_changed = True
        if not has_changed:
            return employee
        new_dept = Department.query.get(new_dept_id).name if new_dept_id else old_dept_name
        new_pos = Position.query.get(new_pos_id).job_title if new_pos_id else old_pos_title
        HistoryService.log_event(
            action="TRANSFER_EMPLOYEE",
            employee_id=employee.id,
            entity_type="employee",
            entity_id=employee.id,
            description=f"Điều chuyển: {old_dept_name}/{old_pos_title} -> {new_dept}/{new_pos}",
            performed_by=actor_id
        )

        db.session.commit()
        return employee

    '''
    TẠO PHÒNG BAN
    '''
    @staticmethod
    def _assign_role_logic(user_id: int, role_name: str, performed_by: int = None) -> User:
        """
        Logic thuần túy: Kiểm tra và gán Role.
        Thêm tham số performed_by để hàm cha (orchestrator) có dữ liệu ghi log.
        """
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"Không tìm thấy người dùng có ID: {user_id}")
        
        valid_roles = [RoleName.ADMIN, RoleName.HR, RoleName.MANAGER, RoleName.EMPLOYEE]
        if role_name not in valid_roles:
            raise ValueError(f"Vai trò '{role_name}' không hợp lệ.")
            
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            raise ValueError(f"Vai trò '{role_name}' chưa được khởi tạo.")
            
        if user.role_id == role.id:
            return user
            
        user.role_id = role.id
        return user
    @staticmethod
    def create_department(data: dict, actor_id: int = None) -> Department:
        name = data.get("name")
        if not name or not name.strip():
            raise ValidationError("Tên phòng ban là bắt buộc.")
        
        # 1. Kiểm tra tồn tại
        existing_dept = Department.query.filter_by(name=name.strip(), is_deleted=False).first()
        if existing_dept:
            raise ValidationError(f"Phòng ban '{name}' đã tồn tại.")

        # 2. Xử lý Manager
        manager_id = data.get("manager_id")
        is_role_updated = False
        
        if manager_id:
            employee = Employee.query.get(manager_id)
            if not employee:
                raise NotFoundError(f"Không tìm thấy nhân viên với ID {manager_id}")
            if not employee.user:
                raise ValidationError("Nhân viên chưa có tài khoản hệ thống.")
            
            current_role = employee.user.role.name if employee.user.role else None
            
            if current_role != RoleName.MANAGER:
                # Gọi hàm logic
                Dept_Pos_Service._assign_role_logic(
                    user_id=employee.user.id, 
                    role_name=RoleName.MANAGER, 
                    performed_by=actor_id
                )
                is_role_updated = True

        # 3. Tạo phòng ban
        try:
            new_dept = Department(
                name=name.strip(),
                description=data.get("description"),
                manager_id=manager_id,
                status=data.get("status", True)
            )
            db.session.add(new_dept)
            
            # 4. Ghi log (Chỉ ghi khi đã add vào session, chưa commit)
            if is_role_updated:
                HistoryService.log_event(
                    action="UPDATE_ROLE",
                    employee_id=employee.id,
                    entity_type="USER",
                    entity_id=employee.user.id,
                    description=f"Thăng cấp Manager khi tạo phòng ban {new_dept.name}",
                    performed_by=actor_id
                )
                
            # 5. Commit DUY NHẤT một lần
            db.session.commit()
            return new_dept
            
        except Exception as e:
            db.session.rollback() # Hoàn tác tất cả (bao gồm cả role vừa gán) nếu lỗi
            raise e

    @staticmethod
    def create_position(data: dict, actor_id: int = None) -> Position:
        """
        Tạo mới một chức danh công việc đơn giản.
        """
        job_title = data.get("job_title")
        # 1. Validation cơ bản
        if not job_title or not job_title.strip():
            raise ValidationError("Tên chức danh là bắt buộc.")
        # 2. Kiểm tra trùng lặp
        existing = Position.query.filter_by(job_title=job_title.strip(), is_deleted=False).first()
        if existing:
            raise ConflictError(f"Chức danh '{job_title}' đã tồn tại.")
        # 3. Tạo đối tượng và lưu vào Database
        try:
            new_position = Position(
                job_title=job_title.strip(),
                status=data.get("status", "active"),
                requirements=data.get("requirements") # Giữ lại trường này nếu cần mô tả
            )
            db.session.add(new_position)
            # 4. Ghi log
            HistoryService.log_event(
                action="CREATE_POSITION",
                entity_type="POSITION",
                entity_id=None, # Sẽ tự sinh sau khi commit hoặc flush
                description=f"Tạo mới chức danh: {new_position.job_title}",
                performed_by=actor_id
            )
            # 5. Commit duy nhất 1 lần
            db.session.commit()
            return new_position
        except Exception as e:
            db.session.rollback()
            raise e
        
    @staticmethod
    def assign_position_to_employee(employee_id: int, position_id: int, actor_id: int = None) -> Employee:
        """
        Gán chức danh cho nhân viên và ghi log lịch sử.
        Đảm bảo tính Atomic: Nếu gán lỗi hoặc log lỗi, dữ liệu sẽ rollback.
        """
        # 1. Tìm nhân viên
        employee = Employee.query.get(employee_id)
        if not employee:
            raise NotFoundError(f"Không tìm thấy nhân viên với ID {employee_id}")
        # 2. Tìm và kiểm tra chức danh 
        # Đảm bảo chức danh tồn tại, chưa bị xóa và đang ở trạng thái 'active'
        position = Position.query.filter_by(id=position_id, is_deleted=False, status='active').first()
        if not position:
            raise ValidationError(f"Chức danh ID {position_id} không tồn tại hoặc đã ngừng hoạt động.")
        # 3. Kiểm tra xem có cần cập nhật không (tránh cập nhật thừa)
        if employee.position_id == position.id:
            return employee
        # Lưu tên chức danh cũ để ghi log
        old_position_name = employee.position.job_title if employee.position else "Chưa có chức danh"
        # 4. Thực hiện cập nhật (Logic thuần túy)
        try:
            employee.position_id = position.id
            # 5. Ghi log
            HistoryService.log_event(
                action="UPDATE_POSITION",
                employee_id=employee.id,
                entity_type="EMPLOYEE",
                entity_id=employee.id,
                description=f"Thay đổi chức danh từ '{old_position_name}' sang '{position.job_title}'",
                performed_by=actor_id
            )
            db.session.commit()
            return employee
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def update_department_name(dept_id: int, new_name: str, actor_id: int) -> Department:
        """
        Cập nhật tên phòng ban. 
        Đảm bảo không thay đổi ID nên không ảnh hưởng đến nhân viên/quản lý.
        """
        # 1. Lấy phòng ban
        dept = Department.query.get(dept_id)
        if not dept:
            raise NotFoundError(f"Không tìm thấy phòng ban ID {dept_id}")

        # 2. Kiểm tra trùng lặp tên khác
        existing = Department.query.filter(
            Department.name == new_name.strip(), 
            Department.id != dept_id, 
            Department.is_deleted == False
        ).first()
        if existing:
            raise ConflictError(f"Tên phòng ban '{new_name}' đã tồn tại.")

        old_name = dept.name
        
        # 3. Cập nhật
        try:
            dept.name = new_name.strip()
            
            # 4. Ghi log
            HistoryService.log_event(
                action="UPDATE_DEPARTMENT",
                entity_type="DEPARTMENT",
                entity_id=dept.id,
                description=f"Đổi tên phòng ban: '{old_name}' -> '{new_name}'",
                performed_by=actor_id
            )
            db.session.commit()
            return dept
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update_position_title(pos_id: int, new_title: str, actor_id: int) -> Position:
        """
        Cập nhật tên chức danh.
        Không ảnh hưởng đến ID nên không làm mất liên kết với nhân viên.
        """
        pos = Position.query.get(pos_id)
        if not pos:
            raise NotFoundError(f"Không tìm thấy chức danh ID {pos_id}")

        # 1. Kiểm tra trùng lặp
        existing = Position.query.filter(
            Position.job_title == new_title.strip(), 
            Position.id != pos_id, 
            Position.is_deleted == False
        ).first()
        if existing:
            raise ConflictError(f"Chức danh '{new_title}' đã tồn tại.")

        old_title = pos.job_title

        # 2. Cập nhật
        try:
            pos.job_title = new_title.strip()
            
            # 3. Ghi log
            HistoryService.log_event(
                action="UPDATE_POSITION",
                entity_type="POSITION",
                entity_id=pos.id,
                description=f"Đổi tên chức danh: '{old_title}' -> '{new_title}'",
                performed_by=actor_id
            )
            db.session.commit()
            return pos
        except Exception as e:
            db.session.rollback()
            raise e