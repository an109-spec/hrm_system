from __future__ import annotations
from datetime import date
from sqlalchemy import func, or_
from app.extensions.db import db
from app.models import (
    Employee,
    HistoryLog,
    Role,
    Salary,
    User,
)
from app.modules.hr.dto import (
    CreateEmployeeDTO,
    EmployeeFilterDTO,
    UpdateEmployeeDTO,
)

class HR_Manager_Service:

    @staticmethod
    def get_employees(filters: EmployeeFilterDTO) -> list[dict]:
        query = Employee.query.filter_by(is_deleted=False)

        if filters.search:
            search_term = f"%{filters.search.strip()}%"
            query = query.join(User, Employee.user_id == User.id, isouter=True).filter(
                or_(
                    Employee.full_name.ilike(search_term),
                    Employee.phone.ilike(search_term),
                    User.email.ilike(search_term),
                )
            )

        if filters.department_id:
            query = query.filter(Employee.department_id == filters.department_id)

        if filters.position_id:
            query = query.filter(Employee.position_id == filters.position_id)

        if filters.working_status:
            query = query.filter(Employee.working_status == filters.working_status)

        employees = query.order_by(Employee.created_at.desc()).all()
        return [HR_Manager_Service._format_employee(emp) for emp in employees]

    @staticmethod
    def get_employee_detail(employee_id: int) -> dict:
        employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first()
        if not employee:
            raise ValueError("Không tìm thấy nhân viên")

        contract = HR_Manager_Service._latest_contract(employee.id)
        manager = employee.manager

        payload = {
            "id": employee.id,
            "employee_code": f"EMP{employee.id:05d}",
            "avatar": employee.avatar,
            "full_name": employee.full_name,
            "age": employee.age,
            "gender": employee.gender,
            "phone": employee.phone,
            "email": employee.user.email if employee.user else None,
            "address": employee.address,
            "department": employee.department.name if employee.department else None,
            "department_id": employee.department_id,
            "position": employee.position.job_title if employee.position else None,
            "position_id": employee.position_id,
            "manager": manager.full_name if manager else None,
            "manager_id": employee.manager_id,
            "hire_date": employee.hire_date.isoformat() if employee.hire_date else None,
            "employment_type": employee.employment_type,
            "working_status": employee.working_status,
            "is_attendance_required": HR_Manager_Service._is_attendance_required(employee),
            "account": {
                "username": employee.user.username if employee.user else None,
                "email": employee.user.email if employee.user else None,
                "is_active": bool(employee.user and employee.user.is_active),
            },
            "contract": {
                "id": contract.id if contract else None,
                "contract_code": contract.contract_code if contract else None,
                "basic_salary": float(contract.basic_salary) if contract else None,
                "start_date": contract.start_date.isoformat() if contract else None,
                "end_date": contract.end_date.isoformat() if contract and contract.end_date else None,
                "status": contract.status if contract else None,
            },
        }
        return payload

   
    @staticmethod
    def _resolve_employee_role() -> Role:
        role = Role.query.filter(func.lower(Role.name) == "employee").first()
        if role:
            return role
        raise ValueError("Chưa cấu hình role Employee trong hệ thống")

    @staticmethod
    def create_employee(data: CreateEmployeeDTO) -> Employee:
        if not data.full_name.strip():
            raise ValueError("Họ tên là bắt buộc")
        if data.gender not in HR_Manager_Service.VALID_GENDERS:
            raise ValueError("Giới tính không hợp lệ")
        if data.employment_type not in HR_Manager_Service.VALID_EMPLOYMENT_TYPES:
            raise ValueError("Loại nhân sự không hợp lệ")

        dob = HRService._parse_date(data.dob, "Ngày sinh")
        hire_date = HRService._parse_date(data.hire_date, "Ngày vào làm")

        if data.phone and Employee.query.filter_by(phone=data.phone).first():
            raise ValueError("Số điện thoại đã tồn tại")

        user = None
        if data.create_account:
            if not data.username or not data.email or not data.password:
                raise ValueError("Thiếu thông tin tài khoản (username/email/password)")
            if User.query.filter_by(username=data.username).first():
                raise ValueError("Username đã tồn tại")
            if User.query.filter_by(email=data.email).first():
                raise ValueError("Email đã tồn tại")

            role = HRService._resolve_employee_role()
            user = User(
                username=data.username.strip(),
                email=data.email.strip(),
                role_id=role.id,
                is_active=True,
            )
            user.set_password(data.password)
            db.session.add(user)
            db.session.flush()

        employee = Employee(
            user_id=user.id if user else None,
            full_name=data.full_name.strip(),
            dob=dob or date(2000, 1, 1),
            gender=data.gender,
            phone=(data.phone or "").strip() or None,
            address=data.address,
            department_id=data.department_id,
            position_id=data.position_id,
            manager_id=data.manager_id,
            hire_date=hire_date,
            employment_type=data.employment_type,
            working_status=data.working_status or "active",
        )

        db.session.add(employee)
        db.session.commit()
        return employee

    @staticmethod
    def update_employee(employee_id: int, data: UpdateEmployeeDTO) -> Employee:
        employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first()
        if not employee:
            raise ValueError("Không tìm thấy nhân viên")

        if data.full_name is not None:
            employee.full_name = data.full_name.strip()

        if data.phone is not None:
            phone = data.phone.strip() or None
            if phone:
                exists = Employee.query.filter(Employee.phone == phone, Employee.id != employee.id).first()
                if exists:
                    raise ValueError("Số điện thoại đã tồn tại")
            employee.phone = phone

        if data.address is not None:
            employee.address = data.address

        if data.department_id is not None:
            employee.department_id = data.department_id

        if data.position_id is not None:
            employee.position_id = data.position_id

        if data.manager_id is not None:
            employee.manager_id = data.manager_id

        if data.working_status is not None:
            if data.working_status not in HRService.VALID_WORKING_STATUSES:
                raise ValueError("Trạng thái làm việc không hợp lệ")
            employee.working_status = data.working_status

        db.session.commit()
        return employee

    

    @staticmethod
    def _append_audit_log(*, salary: Salary, action: str, description: str, user_id: int | None) -> None:
        db.session.add(
            HistoryLog(
                employee_id=salary.employee_id,
                action=action,
                entity_type="salary",
                entity_id=salary.id,
                description=description,
                performed_by=user_id,
            )
        )
    @staticmethod
    def _ensure_hr_employee(user_id: int | None) -> Employee:
        if not user_id:
            raise ValueError("Không xác định được tài khoản HR")

        employee = Employee.query.filter_by(user_id=user_id, is_deleted=False).first()
        if not employee:
            raise ValueError("Không tìm thấy hồ sơ nhân sự")
        return employee
    

   