from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash
from app.constants.employee import WorkingStatus, EmploymentType
from app.extensions.db import db
from app.models import (
    Department,
    Employee,
    Position,
)
from app.common.exceptions import NotFoundError
from app.modules.history.service import HistoryService
from app.utils.time import _normalize
class Admin_Service: 
    @staticmethod
    def _parse_date(date_str: str | None, field_name: str) -> datetime.date | None:
        """
        Sử dụng utility _normalize có sẵn để xử lý input.
        """
        if not date_str:
            return None
        if hasattr(date_str, 'date'):
            return date_str.date()
        if hasattr(date_str, 'year'): 
            return date_str
        dt = _normalize(date_str)
        if dt is None:
            raise ValueError(f"{field_name} không hợp lệ. Vui lòng nhập đúng định dạng YYYY-MM-DD")
        return dt.date()

    @staticmethod
    def create_employee(data: dict, current_user_id: int) -> Employee:
        """
        Chỉ khởi tạo hồ sơ nhân viên (Shell creation).
        Thông tin công việc sẽ được cập nhật ở bước sau.
        """
        full_name = (data.get("full_name") or "").strip()
        if not full_name:
            raise ValueError("Họ tên là bắt buộc")
        
        dob = Admin_Service._parse_date(data.get("dob"), "Ngày sinh")
        if not dob:
            raise ValueError("Ngày sinh là bắt buộc")
        employee = Employee(
            full_name=full_name,
            dob=dob,
            gender=data.get("gender"),
            phone=(data.get("phone") or "").strip() or None,
            address=data.get("address"),
            hire_date=Admin_Service._parse_date(data.get("hire_date"), "Ngày vào làm"),
            # Mặc định trạng thái là mới tạo
            employment_type=data.get("employment_type", EmploymentType.PROBATION),
            working_status=WorkingStatus.ACTIVE
        )
        try:
            db.session.add(employee)
            db.session.flush() 
            HistoryService.log_event(
                action="CREATE_EMPLOYEE",
                employee_id=employee.id,
                entity_type="Employee",
                entity_id=employee.id,
                description=f"Khởi tạo hồ sơ nhân viên: {employee.full_name}",
                performed_by=current_user_id
            )
            db.session.commit()
            return employee
        except Exception as e:
            db.session.rollback()
            raise e


    '''
    GÁN PHÒNG BAN CHỨC DANH
    '''
    @staticmethod
    def _validate_work_structure(department_id=None, position_id=None):
        """
        Validation logic này phải khớp với logic của get_department_options
        và get_position_options để đảm bảo tính nhất quán.
        """
        # Kiểm tra Phòng ban (phải là đang hoạt động, chưa xóa)
        if department_id:
            dept = Department.query.filter_by(id=department_id, is_deleted=False, status=True).first()
            if not dept:
                raise ValueError(f"Phòng ban ID {department_id} không tồn tại hoặc đã ngừng hoạt động.")
        # Kiểm tra Chức danh (phải là đang hoạt động, chưa xóa)
        if position_id:
            pos = Position.query.filter_by(id=position_id, is_deleted=False, status='active').first()
            if not pos:
                raise ValueError(f"Chức danh ID {position_id} không tồn tại hoặc đã ngừng hoạt động.")

    @staticmethod
    def assign_work_info(employee_id: int, data: dict, current_user_id: int) -> Employee:
        employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first()
        if not employee: raise ValueError("Không tìm thấy nhân viên")
        Admin_Service._validate_work_structure(
            department_id=data.get("department_id"),
            position_id=data.get("position_id")
        )
        try:
            if "department_id" in data: employee.department_id = data["department_id"]
            if "position_id" in data: employee.position_id = data["position_id"]
            HistoryService.log_event(
                action="ASSIGN_WORK_INFO",
                employee_id=employee.id,
                entity_type="Employee",
                entity_id=employee.id,
                description=f"Gán PB/Chức danh: {employee.department.name if employee.department else 'N/A'} / {employee.position.job_title if employee.position else 'N/A'}",
                performed_by=current_user_id
            )
            db.session.commit()
            return employee
        except Exception as e:
            db.session.rollback()
            raise e
        
    @staticmethod
    def get_employees_pending_account():
        """
        Lấy danh sách nhân viên đã có thông tin công việc (PB, Chức danh)
        nhưng CHƯA có tài khoản (user_id là NULL).
        Đây là danh sách "hàng đợi" để bạn rà soát và tạo acc.
        """
        return Employee.query.filter(
            Employee.is_deleted.is_(False),
            Employee.department_id.isnot(None), # Phải có phòng ban
            Employee.position_id.isnot(None),   # Phải có chức danh
            Employee.user_id.is_(None)          # QUAN TRỌNG: Chỉ lấy người chưa có account
        ).all()
    
    @staticmethod
    def get_pending_employee_detail(employee_id: int) -> Employee:
        """
        Xem chi tiết nhân viên nhưng bắt buộc phải nằm trong nhóm 'pending'.
        Hàm này giúp đảm bảo bạn chỉ xem được hồ sơ của người chưa có tài khoản.
        """
        employee = Employee.query.options(
            joinedload(Employee.department), 
            joinedload(Employee.position)
        ).filter(
            Employee.id == employee_id,
            Employee.is_deleted.is_(False),
            Employee.department_id.isnot(None),
            Employee.position_id.isnot(None),
            Employee.user_id.is_(None)  # Ràng buộc: Phải chưa có tài khoản
        ).first()
        if not employee:
            raise NotFoundError(f"Không tìm thấy nhân viên ID {employee_id} trong danh sách chờ tạo tài khoản.")  
        return employee

    @staticmethod
    def update_pending_employee(employee_id: int, data: dict, current_user_id: int) -> Employee:
        """
        Chỉnh sửa hồ sơ cho nhân viên chưa có tài khoản.
        Kiểm tra trạng thái pending trước khi cho phép cập nhật.
        """
        # 1. Lấy nhân viên theo điều kiện pending
        employee = Admin_Service.get_pending_employee_detail(employee_id)
        # 2. Thực hiện cập nhật các trường được phép sửa
        if "full_name" in data and data["full_name"]:
            employee.full_name = data["full_name"].strip()
        if "dob" in data:
            employee.dob = Admin_Service._parse_date(data["dob"], "Ngày sinh")
        if "gender" in data:
            employee.gender = data["gender"]
        if "phone" in data:
            employee.phone = (data["phone"] or "").strip() or None
        if "address" in data:
            employee.address = data["address"]
        if "hire_date" in data:
            employee.hire_date = Admin_Service._parse_date(data["hire_date"], "Ngày vào làm")
        try:
            db.session.commit()
            HistoryService.log_event(
                action="UPDATE_PENDING_EMPLOYEE",
                employee_id=employee.id,
                entity_type="Employee",
                entity_id=employee.id,
                description=f"Chỉnh sửa hồ sơ nhân viên chờ: {employee.full_name}",
                performed_by=current_user_id
            )
            return employee
        except Exception as e:
            db.session.rollback()
            raise e
        
  