from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import or_, func

from app.extensions.db import db
from app.models import Contract, Department, Employee, Position, Role, User
from app.modules.hr.dto import (
    AccountStatusDTO,
    CreateContractDTO,
    CreateEmployeeDTO,
    EmployeeFilterDTO,
    UpdateEmployeeDTO,
)


class HRService:
    VALID_WORKING_STATUSES = {"working", "on_leave", "resigned"}
    VALID_EMPLOYMENT_TYPES = {"probation", "permanent", "intern", "contract"}
    VALID_GENDERS = {"male", "female", "other"}

    @staticmethod
    def _parse_date(raw: str | None, field_name: str) -> date | None:
        if raw in (None, ""):
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"{field_name} không đúng định dạng YYYY-MM-DD") from exc

    @staticmethod
    def _format_employee(employee: Employee) -> dict:
        account = employee.user
        return {
            "id": employee.id,
            "employee_code": f"EMP{employee.id:05d}",
            "full_name": employee.full_name,
            "email": account.email if account else None,
            "phone": employee.phone,
            "department": employee.department.name if employee.department else None,
            "department_id": employee.department_id,
            "position": employee.position.job_title if employee.position else None,
            "position_id": employee.position_id,
            "username": account.username if account else None,
            "working_status": employee.working_status,
            "account_status": "active" if account and account.is_active else "inactive",
        }

    @staticmethod
    def _latest_contract(employee_id: int) -> Contract | None:
        return (
            Contract.query.filter_by(employee_id=employee_id)
            .order_by(Contract.start_date.desc(), Contract.created_at.desc())
            .first()
        )

    @staticmethod
    def get_filter_meta() -> dict:
        departments = Department.query.filter_by(is_deleted=False).order_by(Department.name.asc()).all()
        positions = Position.query.filter_by(is_deleted=False).order_by(Position.job_title.asc()).all()
        managers = (
            Employee.query.filter_by(is_deleted=False)
            .join(Position, Employee.position_id == Position.id, isouter=True)
            .order_by(Employee.full_name.asc())
            .all()
        )
        return {
            "departments": [{"id": d.id, "name": d.name} for d in departments],
            "positions": [{"id": p.id, "name": p.job_title} for p in positions],
            "managers": [{"id": m.id, "name": m.full_name} for m in managers],
        }

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
        return [HRService._format_employee(emp) for emp in employees]

    @staticmethod
    def get_employee_detail(employee_id: int) -> dict:
        employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first()
        if not employee:
            raise ValueError("Không tìm thấy nhân viên")

        contract = HRService._latest_contract(employee.id)
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
        if data.gender not in HRService.VALID_GENDERS:
            raise ValueError("Giới tính không hợp lệ")
        if data.employment_type not in HRService.VALID_EMPLOYMENT_TYPES:
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
            working_status=data.working_status or "working",
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
    def _generate_contract_code() -> str:
        year = datetime.utcnow().year
        prefix = f"HD{year}"
        latest_code = (
            Contract.query.filter(Contract.contract_code.like(f"{prefix}-%"))
            .order_by(Contract.id.desc())
            .with_entities(Contract.contract_code)
            .first()
        )
        seq = 1
        if latest_code and latest_code[0]:
            try:
                seq = int(str(latest_code[0]).split("-")[-1]) + 1
            except ValueError:
                seq = 1
        return f"{prefix}-{seq:03d}"

    @staticmethod
    def create_contract(data: CreateContractDTO) -> Contract:
        employee = Employee.query.filter_by(id=data.employee_id, is_deleted=False).first()
        if not employee:
            raise ValueError("Không tìm thấy nhân viên để tạo hợp đồng")

        start_date = HRService._parse_date(data.start_date, "Ngày bắt đầu")
        end_date = HRService._parse_date(data.end_date, "Ngày kết thúc")
        if not start_date:
            raise ValueError("Ngày bắt đầu là bắt buộc")
        if end_date and end_date < start_date:
            raise ValueError("Ngày kết thúc phải sau ngày bắt đầu")

        contract = Contract(
            employee_id=data.employee_id,
            contract_code=HRService._generate_contract_code(),
            basic_salary=Decimal(str(data.basic_salary or 0)),
            start_date=start_date,
            end_date=end_date,
            status="active",
        )

        if hasattr(contract, "note"):
            setattr(contract, "note", data.note)
        if data.contract_type and hasattr(contract, "contract_type"):
            setattr(contract, "contract_type", data.contract_type)

        db.session.add(contract)
        db.session.commit()
        return contract

    @staticmethod
    def update_account_status(data: AccountStatusDTO) -> User:
        employee = Employee.query.filter_by(id=data.employee_id, is_deleted=False).first()
        if not employee or not employee.user:
            raise ValueError("Nhân viên chưa có tài khoản đăng nhập")

        employee.user.is_active = data.is_active
        db.session.commit()
        return employee.user
