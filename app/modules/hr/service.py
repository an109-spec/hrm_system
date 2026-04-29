from __future__ import annotations

from datetime import date, datetime, timedelta
import os
import re
import uuid
import calendar
import csv
import io
import json
from decimal import Decimal
from sqlalchemy import and_, func, or_
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from app.extensions.db import db
from app.models import (
    Attendance,
    Complaint,
    Contract,
    Department,
    Employee,
    EmployeeAllowance,
    EmployeeLeaveUsage,
    HistoryLog,
    LeaveRequest,
    Position,
    Role,
    Salary,
    User,
    Dependent,
    OvertimeRequest,
    Notification,
)
from app.modules.hr.dto import (
    AccountStatusDTO,
    ContractFilterDTO,
    CreateContractDTO,
    CreateEmployeeDTO,
    EmployeeFilterDTO,
    ExtendContractDTO,
    TerminateContractDTO,
    UpdateContractDTO,
    UpdateEmployeeDTO,
    PayrollAdjustmentDTO,
    PayrollApprovalDTO,
    PayrollCalculationDTO,
    PayrollComplaintHandleDTO,
    PayrollExportDTO,
    PayrollFilterDTO,
    AttendanceAdjustmentDTO,
    AttendanceExportDTO,
    AttendanceFilterDTO,
    OvertimeApprovalDTO,
    AbnormalAttendanceResolveDTO,
    HRPasswordChangeDTO,
    HRProfileUpdateDTO,
    DependentDTO,
)
from app.modules.payroll_policy import PayrollPolicyService

class HRService:
    VALID_WORKING_STATUSES = {"active", "probation", "on_leave", "pending_resignation", "resigned", "inactive", "terminated", "retired"}
    VALID_EMPLOYMENT_TYPES = {"probation", "permanent", "intern", "contract"}
    VALID_GENDERS = {"male", "female", "other"}
    VALID_CONTRACT_TYPES = {"trial", "official", "internship", "seasonal"}
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
            "is_attendance_required": HRService._is_attendance_required(employee),
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
    def _contract_type_from_employee(employee: Employee | None) -> str:
        if not employee:
            return "official"
        mapping = {
            "probation": "trial",
            "permanent": "official",
            "intern": "internship",
            "contract": "seasonal",
        }
        return mapping.get((employee.employment_type or "").lower(), "official")

    @staticmethod
    def _status_and_days_left(contract: Contract, today: date | None = None) -> tuple[str, int | None]:
        current = today or date.today()

        if (contract.status or "").lower() == "terminated":
            days_left = (contract.end_date - current).days if contract.end_date else None
            return "terminated", days_left

        if not contract.end_date:
            return "active", None

        days_left = (contract.end_date - current).days
        if days_left < 0:
            return "expired", days_left
        if days_left < 30:
            return "expiring", days_left
        return "active", days_left

    @staticmethod
    def _status_label(status: str) -> str:
        labels = {
            "expiring": "Sắp hết hạn",
            "active": "Đang hiệu lực",
            "expired": "Đã hết hạn",
            "terminated": "Đã kết thúc",
        }
        return labels.get(status, status)

    @staticmethod
    def _contract_type_label(contract_type: str) -> str:
        labels = {
            "trial": "Thử việc",
            "official": "Chính thức",
            "internship": "Thực tập",
            "seasonal": "Thời vụ",
        }
        return labels.get(contract_type, contract_type)

    @staticmethod
    def _sum_allowance(employee_id: int) -> Decimal:
        rows = EmployeeAllowance.query.filter_by(employee_id=employee_id, status=True, is_deleted=False).all()
        total = Decimal("0")
        for row in rows:
            if row.final_amount is not None:
                total += Decimal(str(row.final_amount))
        return total

    @staticmethod
    def _is_attendance_required(employee: Employee) -> bool:
        return employee.is_attendance_required is not False

    @staticmethod
    def _attendance_required_employee_query(query):
        return query.filter(
            or_(
                Employee.is_attendance_required.is_(True),
                Employee.is_attendance_required.is_(None),
            )
        )


    @staticmethod
    def _serialize_contract(contract: Contract, *, today: date | None = None) -> dict:
        employee = contract.employee
        contract_type = getattr(contract, "contract_type", None) or HRService._contract_type_from_employee(employee)
        status, days_left = HRService._status_and_days_left(contract, today=today)
        allowance = HRService._sum_allowance(employee.id) if employee else Decimal("0")

        return {
            "id": contract.id,
            "contract_code": contract.contract_code,
            "employee_id": employee.id if employee else None,
            "employee_code": f"EMP{employee.id:05d}" if employee else "--",
            "employee_name": employee.full_name if employee else "--",
            "department": employee.department.name if employee and employee.department else "--",
            "position": employee.position.job_title if employee and employee.position else "--",
            "contract_type": contract_type,
            "contract_type_label": HRService._contract_type_label(contract_type),
            "start_date": contract.start_date.isoformat() if contract.start_date else None,
            "end_date": contract.end_date.isoformat() if contract.end_date else None,
            "contract_status": status,
            "contract_status_label": HRService._status_label(status),
            "days_left": days_left,
            "basic_salary": float(contract.basic_salary or 0),
            "allowance": float(allowance),
            "note": getattr(contract, "note", None),
        }

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
            "contract_statuses": [
                {"value": "all", "label": "Tất cả"},
                {"value": "expiring", "label": "Sắp hết hạn"},
                {"value": "active", "label": "Đang hiệu lực"},
                {"value": "expired", "label": "Đã hết hạn"},
            ],
            "contract_types": [
                {"value": "all", "label": "Tất cả"},
                {"value": "trial", "label": "Thử việc"},
                {"value": "official", "label": "Chính thức"},
                {"value": "internship", "label": "Thực tập"},
                {"value": "seasonal", "label": "Thời vụ"},
            ],
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
            "is_attendance_required": HRService._is_attendance_required(employee),
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
    def get_contracts(filters: ContractFilterDTO) -> dict:
        contracts = (
            Contract.query.join(Employee, Contract.employee_id == Employee.id)
            .filter(Employee.is_deleted.is_(False), Contract.is_deleted.is_(False))
            .order_by(Contract.start_date.desc(), Contract.id.desc())
            .all()
        )

        today = date.today()
        serialized = [HRService._serialize_contract(contract, today=today) for contract in contracts]

        if filters.search:
            keyword = filters.search.strip().lower()
            serialized = [
                row
                for row in serialized
                if keyword in (row.get("contract_code") or "").lower()
                or keyword in (row.get("employee_name") or "").lower()
                or keyword in (row.get("employee_code") or "").lower()
            ]

        contract_type = (filters.contract_type or "all").lower()
        if contract_type != "all":
            serialized = [row for row in serialized if (row.get("contract_type") or "").lower() == contract_type]

        contract_status = (filters.contract_status or "all").lower()
        if contract_status != "all":
            serialized = [row for row in serialized if (row.get("contract_status") or "").lower() == contract_status]

        summary = {
            "total": len(serialized),
            "expiring": sum(1 for row in serialized if row["contract_status"] == "expiring"),
            "active": sum(1 for row in serialized if row["contract_status"] == "active"),
            "expired": sum(1 for row in serialized if row["contract_status"] == "expired"),
        }
        return {"items": serialized, "summary": summary}

    @staticmethod
    def get_contract_detail(contract_id: int) -> dict:
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")
        return HRService._serialize_contract(contract)


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
    def _validate_contract_type(contract_type: str | None) -> str:
        resolved = (contract_type or "official").lower()
        if resolved not in HRService.VALID_CONTRACT_TYPES:
            raise ValueError("Loại hợp đồng không hợp lệ")
        return resolved

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

        active_contract = (
            Contract.query.filter_by(employee_id=data.employee_id, is_deleted=False)
            .filter(Contract.status == "active")
            .order_by(Contract.start_date.desc())
            .first()
        )
        if active_contract and (not active_contract.end_date or active_contract.end_date >= date.today()):
            raise ValueError("Nhân viên đang có hợp đồng hiệu lực. Vui lòng gia hạn/chỉnh sửa thay vì tạo mới")


        contract = Contract(
            employee_id=data.employee_id,
            contract_code=HRService._generate_contract_code(),
            basic_salary=Decimal(str(data.basic_salary or 0)),
            start_date=start_date,
            end_date=end_date,
            status="active",
        )

        contract_type = HRService._validate_contract_type(data.contract_type)
        if hasattr(contract, "contract_type"):
            setattr(contract, "contract_type", contract_type)

        if hasattr(contract, "note"):
            setattr(contract, "note", data.note)

        db.session.add(contract)
        db.session.commit()
        return contract

    @staticmethod
    def update_contract(contract_id: int, data: UpdateContractDTO) -> Contract:
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")

        if data.basic_salary is not None:
            contract.basic_salary = Decimal(str(data.basic_salary))

        if data.start_date is not None:
            parsed_start = HRService._parse_date(data.start_date, "Ngày bắt đầu")
            if parsed_start is None:
                raise ValueError("Ngày bắt đầu là bắt buộc")
            contract.start_date = parsed_start

        if data.end_date is not None:
            contract.end_date = HRService._parse_date(data.end_date, "Ngày kết thúc")

        if contract.end_date and contract.start_date and contract.end_date < contract.start_date:
            raise ValueError("Ngày kết thúc phải sau ngày bắt đầu")

        if data.contract_type is not None and hasattr(contract, "contract_type"):
            setattr(contract, "contract_type", HRService._validate_contract_type(data.contract_type))

        if data.note is not None and hasattr(contract, "note"):
            setattr(contract, "note", data.note)

        if contract.end_date and contract.end_date < date.today() and contract.status == "active":
            contract.status = "expired"
        elif contract.status != "terminated":
            contract.status = "active"

        db.session.commit()
        return contract

    @staticmethod
    def extend_contract(contract_id: int, data: ExtendContractDTO) -> Contract:
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")

        new_end_date = HRService._parse_date(data.end_date, "Ngày gia hạn")
        if not new_end_date:
            raise ValueError("Ngày gia hạn là bắt buộc")
        if new_end_date <= contract.start_date:
            raise ValueError("Ngày gia hạn phải sau ngày bắt đầu hợp đồng")

        contract.end_date = new_end_date
        contract.status = "active"
        if data.note is not None and hasattr(contract, "note"):
            setattr(contract, "note", data.note)

        db.session.commit()
        return contract

    @staticmethod
    def terminate_contract(contract_id: int, data: TerminateContractDTO) -> Contract:
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")

        terminate_date = HRService._parse_date(data.end_date, "Ngày kết thúc") or date.today()
        if terminate_date < contract.start_date:
            raise ValueError("Ngày kết thúc không thể trước ngày bắt đầu")

        contract.end_date = terminate_date
        contract.status = "terminated"
        if data.note is not None and hasattr(contract, "note"):
            setattr(contract, "note", data.note)

        db.session.commit()
        return contract

    @staticmethod
    def get_contract_reminders() -> dict:
        today = date.today()
        week_later = today + timedelta(days=7)
        month_later = today + timedelta(days=30)

        reminders: list[dict] = []

        latest_by_employee: dict[int, Contract] = {}
        all_contracts = (
            Contract.query.join(Employee, Contract.employee_id == Employee.id)
            .filter(Employee.is_deleted.is_(False), Contract.is_deleted.is_(False))
            .order_by(Contract.employee_id.asc(), Contract.start_date.desc(), Contract.id.desc())
            .all()
        )
        for contract in all_contracts:
            latest_by_employee.setdefault(contract.employee_id, contract)

        employees = Employee.query.filter_by(is_deleted=False).order_by(Employee.full_name.asc()).all()
        for employee in employees:
            contract = latest_by_employee.get(employee.id)
            if not contract:
                reminders.append(
                    {
                        "level": "critical",
                        "type": "missing_contract",
                        "employee_id": employee.id,
                        "employee_code": f"EMP{employee.id:05d}",
                        "employee_name": employee.full_name,
                        "message": "Nhân viên chưa có hợp đồng",
                    }
                )
                continue

            status, days_left = HRService._status_and_days_left(contract, today=today)
            if status == "expired":
                reminders.append(
                    {
                        "level": "critical",
                        "type": "expired",
                        "contract_id": contract.id,
                        "employee_id": employee.id,
                        "employee_code": f"EMP{employee.id:05d}",
                        "employee_name": employee.full_name,
                        "message": "Hợp đồng đã quá hạn, cần xử lý ngay",
                        "days_left": days_left,
                    }
                )
                continue

            if contract.end_date and contract.end_date <= week_later:
                reminders.append(
                    {
                        "level": "warning",
                        "type": "expiring_7_days",
                        "contract_id": contract.id,
                        "employee_id": employee.id,
                        "employee_code": f"EMP{employee.id:05d}",
                        "employee_name": employee.full_name,
                        "message": f"Hợp đồng còn {max(days_left or 0, 0)} ngày sẽ hết hạn",
                        "days_left": days_left,
                    }
                )
            elif contract.end_date and contract.end_date <= month_later:
                reminders.append(
                    {
                        "level": "warning",
                        "type": "expiring_30_days",
                        "contract_id": contract.id,
                        "employee_id": employee.id,
                        "employee_code": f"EMP{employee.id:05d}",
                        "employee_name": employee.full_name,
                        "message": "Hợp đồng còn dưới 30 ngày sẽ hết hạn",
                        "days_left": days_left,
                    }
                )
            elif contract.end_date:
                reminders.append(
                    {
                        "level": "info",
                        "type": "normal",
                        "contract_id": contract.id,
                        "employee_id": employee.id,
                        "employee_code": f"EMP{employee.id:05d}",
                        "employee_name": employee.full_name,
                        "message": "Hợp đồng đang hiệu lực bình thường",
                        "days_left": days_left,
                    }
                )

        reminders.sort(
            key=lambda item: (
                {"critical": 0, "warning": 1, "info": 2}.get(item["level"], 3),
                item.get("days_left") if item.get("days_left") is not None else 10_000,
            )
        )

        return {
            "items": reminders,
            "summary": {
                "critical": sum(1 for item in reminders if item["level"] == "critical"),
                "warning": sum(1 for item in reminders if item["level"] == "warning"),
                "info": sum(1 for item in reminders if item["level"] == "info"),
            },
        }


    @staticmethod
    def update_account_status(data: AccountStatusDTO) -> User:
        employee = Employee.query.filter_by(id=data.employee_id, is_deleted=False).first()
        if not employee or not employee.user:
            raise ValueError("Nhân viên chưa có tài khoản đăng nhập")

        employee.user.is_active = data.is_active
        db.session.commit()
        return employee.user

    PAYROLL_STATUSES = {"draft", "pending_approval", "approved", "finalized", "locked", "complaint"}

    @staticmethod
    def _month_range(month: int, year: int) -> tuple[date, date]:
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])
        return start, end

    @staticmethod
    def _decimal(value: object | None) -> Decimal:
        if value in (None, ""):
            return Decimal("0")
        return Decimal(str(value))

    @staticmethod
    def _salary_note_payload(salary: Salary) -> dict:
        try:
            payload = json.loads(salary.note) if salary.note else {}
            return payload if isinstance(payload, dict) else {}
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def _save_salary_note(salary: Salary, payload: dict) -> None:
        salary.note = json.dumps(payload, ensure_ascii=False)

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
    def _attendance_metrics(employee_id: int, month: int, year: int) -> dict:
        start, end = HRService._month_range(month, year)
        records = Attendance.query.filter(
            Attendance.employee_id == employee_id,
            Attendance.date >= start,
            Attendance.date <= end,
        ).all()

        total_work_days = Decimal("0")
        overtime_hours = Decimal("0")
        weighted_overtime_hours = Decimal("0")
        late_minutes = Decimal("0")
        early_minutes = Decimal("0")

        for item in records:
            multiplier = Decimal(str(item.status.multiplier if item.status else 1))
            if item.check_in or item.check_out:
                total_work_days += multiplier
            item_ot_hours = HRService._decimal(item.overtime_hours)
            overtime_hours += item_ot_hours
            weighted_overtime_hours += item_ot_hours * (Decimal("3") if item.attendance_type == "holiday" and item_ot_hours > 0 else Decimal("1"))

            if item.check_in:
                late_ref = item.check_in.replace(hour=8, minute=0, second=0, microsecond=0)
                if item.check_in > late_ref:
                    late_minutes += Decimal(str((item.check_in - late_ref).total_seconds() / 60))

            if item.check_out:
                early_ref = item.check_out.replace(hour=17, minute=0, second=0, microsecond=0)
                if item.check_out < early_ref:
                    early_minutes += Decimal(str((early_ref - item.check_out).total_seconds() / 60))

        leave_query = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "approved",
            LeaveRequest.from_date <= end,
            LeaveRequest.to_date >= start,
        ).all()

        leave_days = 0
        unpaid_leave_days = 0
        for leave in leave_query:
            overlap_start = max(start, leave.from_date)
            overlap_end = min(end, leave.to_date)
            days = (overlap_end - overlap_start).days + 1
            if days > 0:
                leave_days += days
                if leave.leave_type and not leave.leave_type.is_paid:
                    unpaid_leave_days += days

        return {
            "total_work_days": total_work_days,
            "overtime_hours": overtime_hours,
            "weighted_overtime_hours": weighted_overtime_hours,
            "late_minutes": late_minutes,
            "early_minutes": early_minutes,
            "leave_days": leave_days,
            "unpaid_leave_days": unpaid_leave_days,
        }

    @staticmethod
    def _payroll_status_label(status: str) -> str:
        labels = {
            "draft": "Nháp",
            "pending_approval": "Chờ duyệt",
            "approved": "Đã duyệt",
            "finalized": "Đã chốt",
            "locked": "Đã chốt",
            "complaint": "Khiếu nại",
        }
        return labels.get(status, status)

    @staticmethod
    def _compute_salary(employee: Employee, month: int, year: int) -> tuple[Salary, dict]:
        policy = PayrollPolicyService.get_policy()
        contract = (
            Contract.query.filter_by(employee_id=employee.id, is_deleted=False)
            .order_by(Contract.start_date.desc(), Contract.id.desc())
            .first()
        )
        if not contract:
            raise ValueError(f"{employee.full_name} chưa có hợp đồng")

        salary = Salary.query.filter_by(employee_id=employee.id, month=month, year=year).first()
        if not salary:
            salary = Salary(employee_id=employee.id, month=month, year=year, net_salary=0, status="draft")
            db.session.add(salary)

        standard_work_days = Decimal("22")
        base_salary = HRService._decimal(contract.basic_salary)
        attendance_required = HRService._is_attendance_required(employee)
        metrics = (
            HRService._attendance_metrics(employee.id, month, year)
            if attendance_required
            else {
                "total_work_days": standard_work_days,
                "overtime_hours": Decimal("0"),
                "weighted_overtime_hours": Decimal("0"),
                "late_minutes": Decimal("0"),
                "early_minutes": Decimal("0"),
                "leave_days": 0,
                "unpaid_leave_days": 0,
            }
        )
        total_allowance = HRService._sum_allowance(employee.id)
        overtime_amount = (
            (base_salary / standard_work_days / Decimal("8")) * metrics.get("weighted_overtime_hours", metrics["overtime_hours"])
            if attendance_required
            else Decimal("0")
        )

        late_penalty = Decimal("0")
        if attendance_required and metrics["late_minutes"] > 0:
            if metrics["late_minutes"] < 15:
                late_penalty = Decimal(str(policy["late_penalty"]["under_15"]))
            elif metrics["late_minutes"] <= 30:
                late_penalty = Decimal(str(policy["late_penalty"]["from_15_to_30"]))
            elif metrics["late_minutes"] > 60 and policy["late_penalty"]["over_60_half_day"]:
                late_penalty = base_salary / standard_work_days / Decimal("2")

        early_penalty = Decimal("30000") if attendance_required and metrics["early_minutes"] > 0 else Decimal("0")
        unpaid_leave_penalty = (
            (base_salary / standard_work_days) * Decimal(str(metrics["unpaid_leave_days"]))
            if attendance_required
            else Decimal("0")
        )

        note_payload = HRService._salary_note_payload(salary)
        manual_allowances = note_payload.get("manual_allowances", {})
        manual_deductions = note_payload.get("manual_deductions", {})

        manual_allowance_total = sum(HRService._decimal(v) for v in manual_allowances.values())
        manual_deduction_total = sum(HRService._decimal(v) for v in manual_deductions.values())
        attendance_income = (
            (base_salary / standard_work_days) * metrics["total_work_days"] + overtime_amount
            if attendance_required
            else base_salary
        )
        taxable_income = attendance_income + total_allowance + manual_allowance_total
        social_insurance = taxable_income * (Decimal(str(policy["insurance"]["social_percent"])) / Decimal("100"))
        health_insurance = taxable_income * (Decimal(str(policy["insurance"]["health_percent"])) / Decimal("100"))
        unemployment_insurance = taxable_income * (Decimal(str(policy["insurance"]["unemployment_percent"])) / Decimal("100"))

        tax_free_allowances = policy["tax_free_allowances"]
        tax_free_total = Decimal("0")
        for k, v in (manual_allowances or {}).items():
            cap = Decimal(str(tax_free_allowances.get(k, 0)))
            amount = HRService._decimal(v)
            tax_free_total += min(amount, cap) if cap > 0 else Decimal("0")
        taxable_income_after_tax_free = max(Decimal("0"), taxable_income - tax_free_total)

        dependent_count = PayrollPolicyService.dependent_count(employee.id)
        personal_deduction = Decimal(str(policy["deduction"]["personal"]))
        dependent_deduction = Decimal(str(policy["deduction"]["dependent_per_person"])) * Decimal(str(dependent_count))
        tax_base = max(
            Decimal("0"),
            taxable_income_after_tax_free
            - social_insurance
            - health_insurance
            - unemployment_insurance
            - personal_deduction
            - dependent_deduction,
        )
        personal_income_tax = PayrollPolicyService.tax_by_bracket(tax_base, policy["tax"]["brackets"])

        auto_penalty_total = late_penalty + early_penalty + unpaid_leave_penalty
        penalty_total = auto_penalty_total + manual_deduction_total

        gross_total = taxable_income
        net_salary = gross_total - social_insurance - health_insurance - unemployment_insurance - personal_income_tax - penalty_total

        salary.basic_salary = base_salary
        salary.standard_work_days = int(standard_work_days)
        salary.total_work_days = metrics["total_work_days"]
        salary.total_allowance = total_allowance + manual_allowance_total
        salary.bonus = overtime_amount
        salary.penalty = penalty_total
        salary.net_salary = net_salary
        if salary.status not in HRService.PAYROLL_STATUSES:
            salary.status = "draft"

        note_payload["breakdown"] = {
            "base_salary": float(base_salary),
            "attendance_required": attendance_required,
            "allowance": float(total_allowance),
            "manual_allowance": float(manual_allowance_total),
            "overtime_amount": float(overtime_amount),
            "late_penalty": float(late_penalty),
            "early_penalty": float(early_penalty),
            "number_of_dependents": dependent_count,
            "personal_deduction": float(personal_deduction),
            "dependent_deduction": float(dependent_deduction),
            "taxable_income_after_tax_free": float(taxable_income_after_tax_free),
            "manual_deduction": float(manual_deduction_total),
            "gross_total": float(gross_total),
            "net_salary": float(net_salary),
        }
        note_payload["metrics"] = {
            "leave_days": metrics["leave_days"],
            "overtime_hours": float(metrics["overtime_hours"]),
        }
        HRService._save_salary_note(salary, note_payload)

        return salary, {
            "employee": employee.full_name,
            "status": salary.status,
            "net_salary": float(net_salary),
        }

    @staticmethod
    def calculate_monthly_payroll(data: PayrollCalculationDTO, actor_user_id: int | None = None) -> dict:
        query = Employee.query.filter_by(is_deleted=False)
        if data.department_id:
            query = query.filter(Employee.department_id == data.department_id)

        employees = query.order_by(Employee.full_name.asc()).all()
        computed = []
        for employee in employees:
            try:
                salary, detail = HRService._compute_salary(employee, data.month, data.year)
                HRService._append_audit_log(
                    salary=salary,
                    action="CALCULATE_PAYROLL",
                    description=f"Tính lương tháng {data.month}/{data.year} cho {employee.full_name}",
                    user_id=actor_user_id,
                )
                computed.append({"employee_id": employee.id, **detail})
            except ValueError:
                continue

        db.session.commit()
        return {"processed": len(computed), "items": computed}

    @staticmethod
    def get_payroll_meta() -> dict:
        base_meta = HRService.get_filter_meta()
        base_meta["payroll_statuses"] = [
            {"value": "all", "label": "Tất cả"},
            {"value": "draft", "label": "Nháp"},
            {"value": "pending_approval", "label": "Chờ duyệt"},
            {"value": "approved", "label": "Đã duyệt"},
            {"value": "finalized", "label": "Đã chốt"},
            {"value": "locked", "label": "Đã chốt"},
            {"value": "complaint", "label": "Khiếu nại"},
        ]
        return base_meta

    @staticmethod
    def _serialize_payroll(salary: Salary) -> dict:
        note_payload = HRService._salary_note_payload(salary)
        breakdown = note_payload.get("breakdown", {})
        employee = salary.employee
        return {
            "id": salary.id,
            "employee_id": employee.id if employee else None,
            "employee_code": f"EMP{employee.id:05d}" if employee else "--",
            "employee_name": employee.full_name if employee else "--",
            "department": employee.department.name if employee and employee.department else "--",
            "position": employee.position.job_title if employee and employee.position else "--",
            "basic_salary": float(salary.basic_salary or 0),
            "total_work_days": float(salary.total_work_days or 0),
            "leave_days": note_payload.get("metrics", {}).get("leave_days", 0),
            "overtime_hours": note_payload.get("metrics", {}).get("overtime_hours", 0),
            "allowance": float(salary.total_allowance or 0),
            "penalty": float(salary.penalty or 0),
            "net_salary": float(salary.net_salary or 0),
            "status": salary.status,
            "status_label": HRService._payroll_status_label(salary.status or "draft"),
            "breakdown": breakdown,
        }

    @staticmethod
    def get_payroll_list(filters: PayrollFilterDTO) -> dict:
        month = filters.month or date.today().month
        year = filters.year or date.today().year
        query = Salary.query.join(Employee, Salary.employee_id == Employee.id).filter(
            Salary.month == month,
            Salary.year == year,
            Employee.is_deleted.is_(False),
        )

        if filters.department_id:
            query = query.filter(Employee.department_id == filters.department_id)

        if filters.status and filters.status != "all":
            query = query.filter(Salary.status == filters.status)

        salaries = query.order_by(Employee.full_name.asc()).all()
        rows = [HRService._serialize_payroll(item) for item in salaries]

        if filters.search:
            keyword = filters.search.lower().strip()
            rows = [
                row
                for row in rows
                if keyword in (row["employee_name"] or "").lower()
                or keyword in (row["employee_code"] or "").lower()
                or keyword in (row["department"] or "").lower()
            ]

        complaint_count = Complaint.query.filter(
            or_(Complaint.salary_id.in_([r["id"] for r in rows] or [0]), Complaint.type.ilike("%salary%")),
            Complaint.status.in_(["pending", "in_progress"]),
        ).count()

        summary = {
            "payroll_fund": sum(row["net_salary"] for row in rows),
            "pending_approval": sum(1 for row in rows if row["status"] == "pending_approval"),
            "complaint_count": complaint_count,
            "missing_payroll": max(Employee.query.filter_by(is_deleted=False).count() - len(rows), 0),
        }
        return {"items": rows, "summary": summary}

    @staticmethod
    def get_payroll_detail(salary_id: int) -> dict:
        salary = Salary.query.get(salary_id)
        if not salary:
            raise ValueError("Không tìm thấy bảng lương")

        payload = HRService._serialize_payroll(salary)
        note_payload = HRService._salary_note_payload(salary)
        payload["manual_allowances"] = note_payload.get("manual_allowances", {})
        payload["manual_deductions"] = note_payload.get("manual_deductions", {})
        payload["audit"] = HRService.payroll_audit_history(salary_id)
        return payload

    @staticmethod
    def update_allowance_deduction(
        salary_id: int,
        data: PayrollAdjustmentDTO,
        actor_user_id: int | None = None,
    ) -> dict:
        salary = Salary.query.get(salary_id)
        if not salary:
            raise ValueError("Không tìm thấy payroll")
        if salary.status in {"approved", "finalized", "locked"}:
            raise ValueError("Payroll đã được duyệt/chốt, không thể chỉnh sửa")

        payload = HRService._salary_note_payload(salary)
        payload["manual_allowances"] = {
            "fuel_allowance": data.fuel_allowance,
            "meal_allowance": data.meal_allowance,
            "responsibility_allowance": data.responsibility_allowance,
            "other_allowance": data.other_allowance,
        }
        payload["manual_deductions"] = {
            "late_penalty": data.late_penalty,
            "early_penalty": data.early_penalty,
            "unpaid_leave_penalty": data.unpaid_leave_penalty,
            "other_penalty": data.other_penalty,
        }
        payload["manual_note"] = data.note
        HRService._save_salary_note(salary, payload)

        HRService._compute_salary(salary.employee, salary.month, salary.year)
        HRService._append_audit_log(
            salary=salary,
            action="UPDATE_PAYROLL_ADJUSTMENT",
            description=f"Cập nhật phụ cấp/khấu trừ thủ công cho payroll #{salary.id}",
            user_id=actor_user_id,
        )
        db.session.commit()
        return HRService.get_payroll_detail(salary.id)

    @staticmethod
    def submit_payroll_approval(salary_id: int, actor_user_id: int | None = None) -> dict:
        salary = Salary.query.get(salary_id)
        if not salary:
            raise ValueError("Không tìm thấy payroll")
        if salary.status in {"approved", "finalized", "locked"}:
            raise ValueError("Payroll đã khóa chỉnh sửa")

        salary.status = "pending_approval"
        HRService._append_audit_log(
            salary=salary,
            action="SUBMIT_PAYROLL_APPROVAL",
            description=f"Gửi duyệt payroll #{salary.id}",
            user_id=actor_user_id,
        )
        db.session.commit()
        return {"id": salary.id, "status": salary.status}

    @staticmethod
    def approve_payroll_flow(
        salary_id: int,
        data: PayrollApprovalDTO,
        actor_user_id: int | None = None,
    ) -> dict:
        salary = Salary.query.get(salary_id)
        if not salary:
            raise ValueError("Không tìm thấy payroll")

        action = (data.action or "").lower()
        if action == "approve":
            salary.status = "approved"
        elif action == "finalize":
            salary.status = "locked"
        elif action == "reject":
            salary.status = "draft"
        else:
            raise ValueError("Action không hợp lệ")

        HRService._append_audit_log(
            salary=salary,
            action="APPROVE_PAYROLL_FLOW",
            description=f"Cập nhật trạng thái payroll #{salary.id} -> {salary.status}. {data.note or ''}".strip(),
            user_id=actor_user_id,
        )
        db.session.commit()
        return {"id": salary.id, "status": salary.status, "status_label": HRService._payroll_status_label(salary.status)}

    @staticmethod
    def export_payslip(data: PayrollExportDTO) -> tuple[io.BytesIO, str, str]:
        rows = HRService.get_payroll_list(
            PayrollFilterDTO(department_id=data.department_id, month=data.month, year=data.year, status="all")
        )["items"]

        if data.export_scope == "department" and data.department_id:
            rows = [row for row in rows if row.get("department") and row.get("department") != "--"]

        if data.export_format == "pdf":
            html_rows = "".join(
                f"<tr><td>{row['employee_code']}</td><td>{row['employee_name']}</td><td>{row['department']}</td><td>{row['net_salary']:,.0f}</td><td>{row['status_label']}</td></tr>"
                for row in rows
            )
            html = f"""
            <html><body><h2>Payroll {data.month}/{data.year}</h2>
            <table border='1' cellspacing='0' cellpadding='6'>
            <tr><th>Mã NV</th><th>Nhân viên</th><th>Phòng ban</th><th>Thực nhận</th><th>Trạng thái</th></tr>
            {html_rows}</table></body></html>
            """
            stream = io.BytesIO(html.encode("utf-8"))
            return stream, f"payroll_{data.month}_{data.year}.pdf", "application/pdf"

        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(["Mã NV", "Tên nhân viên", "Phòng ban", "Lương cơ bản", "Thực nhận", "Trạng thái"])
        for row in rows:
            writer.writerow([
                row["employee_code"],
                row["employee_name"],
                row["department"],
                row["basic_salary"],
                row["net_salary"],
                row["status_label"],
            ])

        output = io.BytesIO(stream.getvalue().encode("utf-8-sig"))
        return output, f"payroll_{data.month}_{data.year}.csv", "text/csv"

    @staticmethod
    def get_payroll_complaints(month: int | None = None, year: int | None = None) -> list[dict]:
        query = Complaint.query.join(Employee, Complaint.employee_id == Employee.id).filter(
            or_(Complaint.salary_id.isnot(None), Complaint.type.ilike("%salary%"))
        )
        if month and year:
            query = query.join(Salary, Complaint.salary_id == Salary.id, isouter=True).filter(
                or_(Salary.id.is_(None), and_(Salary.month == month, Salary.year == year))
            )

        complaints = query.order_by(Complaint.created_at.desc()).limit(100).all()
        return [
            {
                "id": item.id,
                "employee": item.employee.full_name if item.employee else "--",
                "salary_id": item.salary_id,
                "title": item.title,
                "description": item.description,
                "status": item.status,
                "priority": item.priority,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in complaints
        ]

    @staticmethod
    def handle_complaint(
        data: PayrollComplaintHandleDTO,
        handler_employee_id: int | None = None,
        actor_user_id: int | None = None,
    ) -> dict:
        complaint = Complaint.query.get(data.complaint_id)
        if not complaint:
            raise ValueError("Không tìm thấy khiếu nại")

        action = data.action.lower()
        if action not in {"in_progress", "resolved", "rejected"}:
            raise ValueError("Trạng thái xử lý khiếu nại không hợp lệ")

        complaint.status = action
        complaint.handled_by = handler_employee_id
        if action == "resolved":
            complaint.resolved_at = datetime.utcnow()

        if complaint.salary_id and data.payroll_status in HRService.PAYROLL_STATUSES:
            salary = Salary.query.get(complaint.salary_id)
            if salary:
                salary.status = data.payroll_status
                HRService._append_audit_log(
                    salary=salary,
                    action="HANDLE_PAYROLL_COMPLAINT",
                    description=f"Xử lý khiếu nại #{complaint.id}: {action}. {data.message or ''}".strip(),
                    user_id=actor_user_id,
                )

        db.session.commit()
        return {"id": complaint.id, "status": complaint.status}

    @staticmethod
    def payroll_audit_history(salary_id: int) -> list[dict]:
        logs = (
            HistoryLog.query.filter_by(entity_type="salary", entity_id=salary_id)
            .order_by(HistoryLog.created_at.desc())
            .all()
        )
        return [
            {
                "id": log.id,
                "action": log.action,
                "description": log.description,
                "performed_by": log.performed_by,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]

    ATTENDANCE_STATUS_LABELS = {
        "normal": "Bình thường",
        "late": "Đi muộn",
        "early": "Về sớm",
        "late_early": "Đi muộn / Về sớm",
        "leave_approved": "Nghỉ phép",
        "absent_unexcused": "Vắng không phép",
        "overtime": "Tăng ca",
        "abnormal": "Bất thường",
    }

    ATTENDANCE_STATUS_BADGES = {
        "normal": "badge-success",
        "late": "badge-warning",
        "early": "badge-warning",
        "late_early": "badge-warning",
        "leave_approved": "badge-info",
        "absent_unexcused": "badge-danger",
        "overtime": "badge-primary",
        "abnormal": "badge-danger",
    }

    @staticmethod
    def _attendance_status_label(status_key: str) -> str:
        return HRService.ATTENDANCE_STATUS_LABELS.get(status_key, status_key)

    @staticmethod
    def _attendance_status_badge(status_key: str) -> str:
        return HRService.ATTENDANCE_STATUS_BADGES.get(status_key, "badge-neutral")

    @staticmethod
    def _month_window(month: int | None, year: int | None) -> tuple[date, date]:
        today = date.today()
        target_month = month or today.month
        target_year = year or today.year
        return HRService._month_range(target_month, target_year)

    @staticmethod
    def _attendance_status_from_record(record: Attendance | None, has_leave: bool) -> str:
        if has_leave:
            return "leave_approved"
        if not record:
            return "absent_unexcused"
        if not record.check_in or not record.check_out:
            return "abnormal"

        late_ref = record.check_in.replace(hour=8, minute=30, second=0, microsecond=0)
        early_ref = record.check_out.replace(hour=17, minute=30, second=0, microsecond=0)
        is_late = record.check_in > late_ref
        is_early = record.check_out < early_ref

        if HRService._decimal(record.overtime_hours) > 0:
            return "overtime"
        if is_late and is_early:
            return "late_early"
        if is_late:
            return "late"
        if is_early:
            return "early"
        return "normal"

    @staticmethod
    def _attendance_working_hours(record: Attendance | None) -> float:
        if not record:
            return 0.0
        if record.working_hours not in (None, ""):
            return float(record.working_hours or 0)
        if record.check_in and record.check_out:
            return float(HRService._decimal((record.check_out - record.check_in).total_seconds() / 3600))
        return 0.0

    @staticmethod
    def _attendance_row_payload(
        employee: Employee,
        work_day: date,
        record: Attendance | None,
        has_leave: bool,
    ) -> dict:
        status_key = HRService._attendance_status_from_record(record, has_leave)
        return {
            "attendance_id": record.id if record else None,
            "employee_id": employee.id,
            "employee_code": f"EMP{employee.id:05d}",
            "employee_name": employee.full_name,
            "department": employee.department.name if employee.department else "--",
            "department_id": employee.department_id,
            "position": employee.position.job_title if employee.position else "--",
            "work_date": work_day.isoformat(),
            "check_in": record.check_in.isoformat() if record and record.check_in else None,
            "check_out": record.check_out.isoformat() if record and record.check_out else None,
            "working_hours": HRService._attendance_working_hours(record),
            "overtime_hours": float(record.overtime_hours or 0) if record else 0.0,
            "late_or_early": status_key in {"late", "early", "late_early"},
            "status": status_key,
            "status_label": HRService._attendance_status_label(status_key),
            "status_badge": HRService._attendance_status_badge(status_key),
            "shift_type": (record.attendance_type if record and record.attendance_type else "normal"),
            "is_abnormal": status_key == "abnormal",
        }

    @staticmethod
    def _abnormal_reasons(record: Attendance | None) -> list[str]:
        if not record:
            return ["Không có dữ liệu công"]
        reasons: list[str] = []
        if not record.check_in:
            reasons.append("Thiếu check-in")
        if not record.check_out:
            reasons.append("Thiếu check-out")
        if record.check_in and record.check_out and record.check_out < record.check_in:
            reasons.append("Sai thời gian check-in/check-out")
        duplicate = (
            Attendance.query.filter(
                Attendance.employee_id == record.employee_id,
                Attendance.date == record.date,
                Attendance.id != record.id,
            ).count()
        )
        if duplicate > 0:
            reasons.append("Có bản ghi chấm công trùng")
        if not reasons:
            reasons.append("Dữ liệu bất thường cần HR xác minh")
        return reasons

    @staticmethod
    def _sync_payroll_for_attendance(employee_id: int, work_day: date, actor_user_id: int | None) -> None:
        employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first()
        if not employee:
            return
        try:
            salary, _ = HRService._compute_salary(employee, work_day.month, work_day.year)
            HRService._append_audit_log(
                salary=salary,
                action="ATTENDANCE_SYNC",
                description=f"Đồng bộ payroll từ chấm công ngày {work_day.isoformat()}",
                user_id=actor_user_id,
            )
        except ValueError:
            return


    @staticmethod
    def _approved_leave_dates(employee_id: int, start: date, end: date) -> set[date]:
        approved = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "approved",
            LeaveRequest.from_date <= end,
            LeaveRequest.to_date >= start,
        ).all()
        result: set[date] = set()
        for item in approved:
            current = max(item.from_date, start)
            edge = min(item.to_date, end)
            while current <= edge:
                result.add(current)
                current += timedelta(days=1)
        return result

    @staticmethod
    def attendance_summary_dashboard(filters: AttendanceFilterDTO) -> dict:
        today = date.today()
        employee_query = Employee.query.filter_by(is_deleted=False)
        employee_query = HRService._attendance_required_employee_query(
            Employee.query.filter_by(is_deleted=False)
        )
        if filters.department_id:
            employee_query = employee_query.filter(Employee.department_id == filters.department_id)
        employees = employee_query.all()
        employee_ids = [e.id for e in employees]

        records = Attendance.query.filter(Attendance.date == today, Attendance.employee_id.in_(employee_ids or [0])).all()
        by_emp = {item.employee_id: item for item in records}

        late_count = 0
        present_count = 0
        abnormal_count = 0
        overtime_pending = 0
        on_leave = 0

        for emp in employees:
            leave_dates = HRService._approved_leave_dates(emp.id, today, today)
            has_leave = today in leave_dates
            if has_leave:
                on_leave += 1
            row = HRService._attendance_row_payload(emp, today, by_emp.get(emp.id), has_leave)
            if row["status"] == "late":
                late_count += 1
            if row["status"] in {"normal", "overtime", "late", "early", "late_early"}:
                present_count += 1
            if row["is_abnormal"]:
                abnormal_count += 1
            if row["overtime_hours"] > 0 and row["shift_type"] != "overtime":
                overtime_pending += 1

        return {
            "today_present": present_count,
            "late_count": late_count,
            "leave_count": on_leave,
            "overtime_pending": overtime_pending,
            "abnormal_count": abnormal_count,
            "has_abnormal": abnormal_count > 0,
        }

    @staticmethod
    def get_attendance_list(filters: AttendanceFilterDTO) -> dict:
        start, end = HRService._month_window(filters.month, filters.year)
        employees_query = Employee.query.filter_by(is_deleted=False)
        employees_query = HRService._attendance_required_employee_query(
            Employee.query.filter_by(is_deleted=False)
        )
        if filters.department_id:
            employees_query = employees_query.filter(Employee.department_id == filters.department_id)
        employees = employees_query.order_by(Employee.full_name.asc()).all()

        rows: list[dict] = []
        for emp in employees:
            leave_dates = HRService._approved_leave_dates(emp.id, start, end)
            records = Attendance.query.filter(
                Attendance.employee_id == emp.id,
                Attendance.date >= start,
                Attendance.date <= end,
            ).order_by(Attendance.date.desc()).all()
            if records:
                for record in records:
                    rows.append(HRService._attendance_row_payload(emp, record.date, record, record.date in leave_dates))
            else:
                rows.append(HRService._attendance_row_payload(emp, end, None, end in leave_dates))

        if filters.search:
            keyword = filters.search.strip().lower()
            rows = [
                row for row in rows
                if keyword in (row["employee_name"] or "").lower()
                or keyword in (row["employee_code"] or "").lower()
                or keyword in (row["department"] or "").lower()
            ]

        if filters.status and filters.status != "all":
            rows = [row for row in rows if row["status"] == filters.status]

        if filters.shift_type and filters.shift_type != "all":
            rows = [row for row in rows if (row["shift_type"] or "normal") == filters.shift_type]

        summary = HRService.attendance_summary_dashboard(filters)
        return {"items": rows, "summary": summary}

    @staticmethod
    def attendance_detail(employee_id: int, month: int | None = None, year: int | None = None) -> dict:
        employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first()
        if not employee:
            raise ValueError("Không tìm thấy nhân viên")
        if not HRService._is_attendance_required(employee):
            raise ValueError("Nhân viên này không thuộc diện bắt buộc chấm công")
        start, end = HRService._month_window(month, year)
        records = Attendance.query.filter(
            Attendance.employee_id == employee_id,
            Attendance.date >= start,
            Attendance.date <= end,
        ).all()
        leave_rows = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "approved",
            LeaveRequest.from_date <= end,
            LeaveRequest.to_date >= start,
        ).all()
        leave_usage = EmployeeLeaveUsage.query.filter_by(employee_id=employee_id, year=end.year).first()

        late_count = 0
        early_count = 0
        abnormal_count = 0
        total_hours = Decimal("0")
        overtime_hours = Decimal("0")
        worked_days = 0
        absent_days = 0

        leave_dates = HRService._approved_leave_dates(employee_id, start, end)
        record_by_day = {item.date: item for item in records}

        day_cursor = start
        while day_cursor <= end:
            record = record_by_day.get(day_cursor)
            row = HRService._attendance_row_payload(employee, day_cursor, record, day_cursor in leave_dates)
            if row["status"] in {"late", "late_early"}:
                late_count += 1
            if row["status"] in {"early", "late_early"}:
                early_count += 1
            if row["status"] == "abnormal":
                abnormal_count += 1
            if row["status"] == "absent_unexcused":
                absent_days += 1
            if row["status"] in {"normal", "late", "early", "late_early", "overtime"}:
                worked_days += 1
            total_hours += Decimal(str(row["working_hours"]))
            overtime_hours += Decimal(str(row["overtime_hours"]))
            day_cursor += timedelta(days=1)

        leave_days = 0
        unpaid_leave_days = 0
        for leave in leave_rows:
            overlap_start = max(start, leave.from_date)
            overlap_end = min(end, leave.to_date)
            days = (overlap_end - overlap_start).days + 1
            if days > 0:
                leave_days += days
                if leave.leave_type and not leave.leave_type.is_paid:
                    unpaid_leave_days += days

        return {
            "employee_id": employee.id,
            "employee_name": employee.full_name,
            "employee_code": f"EMP{employee.id:05d}",
            "department": employee.department.name if employee.department else "--",
            "position": employee.position.job_title if employee.position else "--",
            "period": {"month": end.month, "year": end.year},
            "breakdown": {
                "standard_work_days": calendar.monthrange(end.year, end.month)[1],
                "actual_work_days": worked_days,
                "leave_days": leave_days,
                "unpaid_leave_days": unpaid_leave_days,
                "total_working_hours": float(total_hours),
                "total_overtime_hours": float(overtime_hours),
                "late_count": late_count,
                "early_count": early_count,
                "penalty_days": absent_days + unpaid_leave_days,
                "abnormal_count": abnormal_count,
                "leave_quota_remaining": leave_usage.remaining_days if leave_usage else None,
            },
        }

    @staticmethod
    def attendance_record_detail(attendance_id: int) -> dict:
        record = Attendance.query.get(attendance_id)
        if not record:
            raise ValueError("Không tìm thấy bản ghi chấm công")
        employee = Employee.query.filter_by(id=record.employee_id, is_deleted=False).first()
        if not employee:
            raise ValueError("Không tìm thấy nhân viên")
        row = HRService._attendance_row_payload(employee, record.date, record, False)
        return {
            **row,
            "attendance_type": record.attendance_type or "normal",
            "reason_flags": HRService._abnormal_reasons(record) if row["is_abnormal"] else [],
        }


    @staticmethod
    def adjust_attendance(data: AttendanceAdjustmentDTO, actor_user_id: int | None = None) -> dict:
        record = Attendance.query.get(data.attendance_id)
        if not record:
            raise ValueError("Không tìm thấy bản ghi chấm công")

        before = {
            "check_in": record.check_in.isoformat() if record.check_in else None,
            "check_out": record.check_out.isoformat() if record.check_out else None,
            "status": HRService._attendance_status_from_record(record, False),
        }

        if data.check_in:
            record.check_in = datetime.fromisoformat(data.check_in.replace("Z", "+00:00")).replace(tzinfo=None)
        if data.check_out:
            record.check_out = datetime.fromisoformat(data.check_out.replace("Z", "+00:00")).replace(tzinfo=None)
        if record.check_in and record.check_out and record.check_out >= record.check_in:
            record.working_hours = Decimal(str((record.check_out - record.check_in).total_seconds() / 3600)).quantize(Decimal("0.01"))

        if data.status == "overtime" and HRService._decimal(record.overtime_hours) == 0 and record.check_in and record.check_out:
            overtime_ref = record.check_out.replace(hour=17, minute=30, second=0, microsecond=0)
            if record.check_out > overtime_ref:
                record.overtime_hours = Decimal(str((record.check_out - overtime_ref).total_seconds() / 3600)).quantize(Decimal("0.01"))
        if data.status == "abnormal":
            record.check_out = None
            record.working_hours = 0

        record.attendance_type = data.status or record.attendance_type
        after_status = HRService._attendance_status_from_record(record, False)
        db.session.add(
            HistoryLog(
                employee_id=record.employee_id,
                action="ATTENDANCE_ADJUSTMENT",
                entity_type="attendance",
                entity_id=record.id,
                description=f"Điều chỉnh chấm công. Trước: {before}. Sau: check_in={record.check_in}, check_out={record.check_out}, status={after_status}. Ghi chú: {data.note or ''}".strip(),
                performed_by=actor_user_id,
            )
        )
        HRService._sync_payroll_for_attendance(record.employee_id, record.date, actor_user_id)
        db.session.commit()
        employee = Employee.query.get(record.employee_id)
        return HRService._attendance_row_payload(employee, record.date, record, False)

    @staticmethod
    def save_attendance_history(attendance_id: int, note: str | None, actor_user_id: int | None = None) -> dict:
        record = Attendance.query.get(attendance_id)
        if not record:
            raise ValueError("Không tìm thấy bản ghi chấm công")
        db.session.add(
            HistoryLog(
                employee_id=record.employee_id,
                action="ATTENDANCE_HISTORY_NOTE",
                entity_type="attendance",
                entity_id=record.id,
                description=(note or "Lưu lịch sử thay đổi thủ công bởi HR").strip(),
                performed_by=actor_user_id,
            )
        )
        db.session.commit()
        return {"attendance_id": record.id, "saved": True}


    @staticmethod
    def attendance_audit_history(attendance_id: int) -> list[dict]:
        logs = (
            HistoryLog.query.filter_by(entity_type="attendance", entity_id=attendance_id)
            .order_by(HistoryLog.created_at.desc())
            .all()
        )
        return [
            {
                "id": log.id,
                "action": log.action,
                "description": log.description,
                "performed_by": log.performed_by,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]

    @staticmethod
    def overtime_pending_list(month: int | None = None, year: int | None = None) -> list[dict]:
        start, end = HRService._month_window(month, year)
        records = OvertimeRequest.query.join(Employee, OvertimeRequest.employee_id == Employee.id).filter(
            OvertimeRequest.overtime_date >= start,
            OvertimeRequest.overtime_date <= end,
            Employee.is_deleted.is_(False),
            OvertimeRequest.is_deleted.is_(False),
            OvertimeRequest.status.in_(["pending_manager", "pending_hr", "pending_admin", "approved", "rejected"]),
        ).order_by(OvertimeRequest.overtime_date.desc()).all()

        rows = []
        for record in records:
            hr_status = record.status
            rows.append(
                {
                    "attendance_id": record.id,
                    "employee_id": record.employee_id,
                    "employee_name": record.employee.full_name if record.employee else "--",
                    "employee_code": f"EMP{record.employee_id:05d}",
                    "department": record.employee.department.name if record.employee and record.employee.department else "--",
                    "date": record.overtime_date.isoformat(),
                    "overtime_hours": float(record.approved_hours or record.requested_hours or record.overtime_hours or 0),
                    "requested_hours": float(record.requested_hours or record.overtime_hours or 0),
                    "approved_hours": float(record.approved_hours or 0) if record.approved_hours is not None else None,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "start_ot_time": record.start_ot_time.isoformat() if record.start_ot_time else None,
                    "end_ot_time": record.end_ot_time.isoformat() if record.end_ot_time else None,
                    "reason": record.reason or "",
                    "manager_approved": record.status != "pending_manager",
                    "hr_status": hr_status,
                }
            )
        return rows

    @staticmethod
    def review_overtime(data: OvertimeApprovalDTO, actor_user_id: int | None = None) -> dict:
        record = OvertimeRequest.query.get(data.attendance_id)
        if not record:
            raise ValueError("Không tìm thấy dữ liệu tăng ca")
        action = (data.action or "").lower()
        if action not in {"approve", "reject"}:
            raise ValueError("Action không hợp lệ")
        if record.status != "pending_hr":
            raise ValueError("Yêu cầu OT chưa được quản lý duyệt hoặc đã xử lý")

        if action == "approve":
            record.status = "pending_admin"
            record.approved_hours = record.requested_hours or record.overtime_hours
        else:
            record.status = "rejected"
            record.rejection_reason = data.note or "HR từ chối"
        hr_employee = Employee.query.filter_by(user_id=actor_user_id, is_deleted=False).first() if actor_user_id else None
        record.hr_decision_by = hr_employee.id if hr_employee else None
        record.hr_decision_at = datetime.utcnow()
        record.hr_note = data.note
        if action == "reject":
            record.approved_hours = Decimal("0.00")
        db.session.add(
            HistoryLog(
                employee_id=record.employee_id,
                action="OVERTIME_REVIEW",
                entity_type="attendance",
                entity_id=record.id,
                description=f"HR {('duyệt' if action == 'approve' else 'từ chối')} tăng ca. {data.note or ''}".strip(),
                performed_by=actor_user_id,
            )
        )
        employee = Employee.query.get(record.employee_id)
        if employee and employee.user_id:
            if action == "approve":
                ot_start = record.start_ot_time.strftime("%H:%M") if record.start_ot_time else "--:--"
                ot_end = record.end_ot_time.strftime("%H:%M") if record.end_ot_time else "--:--"
                content = (
                    "HR đã kiểm tra yêu cầu OT lúc "
                    f"{datetime.utcnow().strftime('%d/%m/%Y - %H:%M')}. "
                    f"Khung giờ dự kiến: {ot_start} → {ot_end}. "
                    "Yêu cầu đã chuyển Admin duyệt cuối."
                )
            else:
                content = (
                    "HR từ chối yêu cầu OT lúc "
                    f"{datetime.utcnow().strftime('%d/%m/%Y - %H:%M')}. "
                    f"Lý do: {record.rejection_reason or 'Không có'}"
                )
            db.session.add(
                Notification(
                    user_id=employee.user_id,
                    title="Kết quả xử lý yêu cầu tăng ca",
                    content=content,
                    type="overtime",
                    link="/employee/notifications",
                )
            )
        db.session.commit()
        return {"attendance_id": record.id, "action": action, "status": record.status}

    @staticmethod
    def detect_abnormal_attendance(month: int | None = None, year: int | None = None) -> list[dict]:
        data = HRService.get_attendance_list(AttendanceFilterDTO(month=month, year=year))
        return [item for item in data["items"] if item["is_abnormal"]]
    @staticmethod
    def resolve_abnormal_attendance(data: AbnormalAttendanceResolveDTO, actor_user_id: int | None = None) -> dict:
        record = Attendance.query.get(data.attendance_id)
        if not record:
            raise ValueError("Không tìm thấy bản ghi chấm công")
        action = (data.action or "").lower()
        if action not in {"confirm_valid", "manual_edit", "reject"}:
            raise ValueError("Hành động xử lý bất thường không hợp lệ")
        before_status = HRService._attendance_status_from_record(record, False)

        if action == "manual_edit":
            if data.check_in:
                record.check_in = datetime.fromisoformat(data.check_in.replace("Z", "+00:00")).replace(tzinfo=None)
            if data.check_out:
                record.check_out = datetime.fromisoformat(data.check_out.replace("Z", "+00:00")).replace(tzinfo=None)
            if data.status:
                record.attendance_type = data.status
        elif action == "confirm_valid":
            if not record.check_in:
                record.check_in = datetime.combine(record.date, datetime.min.time()).replace(hour=8, minute=30)
            if not record.check_out:
                record.check_out = datetime.combine(record.date, datetime.min.time()).replace(hour=17, minute=30)
            if not record.attendance_type or record.attendance_type == "abnormal":
                record.attendance_type = "normal"
        else:
            record.attendance_type = "abnormal_rejected"

        if record.check_in and record.check_out and record.check_out >= record.check_in:
            record.working_hours = Decimal(str((record.check_out - record.check_in).total_seconds() / 3600)).quantize(Decimal("0.01"))

        after_status = HRService._attendance_status_from_record(record, False)
        db.session.add(
            HistoryLog(
                employee_id=record.employee_id,
                action="ABNORMAL_ATTENDANCE_RESOLVE",
                entity_type="overtime_request",
                entity_id=record.id,
                description=(
                    f"Xử lý bất thường: {action}. Trước={before_status}; Sau={after_status}. "
                    f"Ghi chú: {data.note or ''}"
                ).strip(),
                performed_by=actor_user_id,
            )
        )
        if action == "approve":
            attendance = Attendance.query.filter_by(employee_id=record.employee_id, date=record.overtime_date).first()
            if not attendance:
                attendance = Attendance(employee_id=record.employee_id, date=record.overtime_date)
                db.session.add(attendance)
            attendance.overtime_hours = Decimal(str(record.overtime_hours or 0))
            attendance.attendance_type = "overtime"
            HRService._sync_payroll_for_attendance(record.employee_id, record.overtime_date, actor_user_id)
        employee = Employee.query.get(record.employee_id)
        if employee and employee.user_id:
            db.session.add(
                Notification(
                    user_id=employee.user_id,
                    title="Kết quả duyệt tăng ca",
                    content="Yêu cầu tăng ca của bạn đã được HR duyệt." if action == "approve" else f"Yêu cầu tăng ca bị từ chối: {record.rejection_reason or ''}",
                    type="overtime",
                    link="/employee/attendance",
                )
            )
        db.session.commit()
        employee = Employee.query.get(record.employee_id)
        return HRService._attendance_row_payload(employee, record.date, record, False)

    @staticmethod
    def export_attendance(data: AttendanceExportDTO) -> tuple[io.BytesIO, str, str]:
        attendance_data = HRService.get_attendance_list(
            AttendanceFilterDTO(
                department_id=data.department_id if data.export_scope == "department" else None,
                month=data.month,
                year=data.year,
                status="all",
            )
        )["items"]

        if data.export_format == "pdf":
            html_rows = "".join(
                f"<tr><td>{row['employee_code']}</td><td>{row['employee_name']}</td><td>{row['department']}</td><td>{row['work_date']}</td><td>{row['working_hours']}</td><td>{row['status_label']}</td></tr>"
                for row in attendance_data
            )
            html = f"""
            <html><body><h2>Attendance {data.month}/{data.year}</h2>
            <table border='1' cellspacing='0' cellpadding='6'>
            <tr><th>Mã NV</th><th>Nhân viên</th><th>Phòng ban</th><th>Ngày</th><th>Giờ làm</th><th>Trạng thái</th></tr>
            {html_rows}</table></body></html>
            """
            stream = io.BytesIO(html.encode("utf-8"))
            return stream, f"attendance_{data.month}_{data.year}.pdf", "application/pdf"

        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(
            ["Mã NV", "Tên nhân viên", "Phòng ban", "Chức danh", "Ngày", "Giờ vào", "Giờ ra", "Tổng giờ làm", "OT", "Trạng thái"]
        )
        for row in attendance_data:
            writer.writerow(
                [
                    row["employee_code"],
                    row["employee_name"],
                    row["department"],
                    row["position"],
                    row["work_date"],
                    row["check_in"] or "--",
                    row["check_out"] or "--",
                    row["working_hours"],
                    row["overtime_hours"],
                    row["status_label"],
                ]
            )
        output = io.BytesIO(stream.getvalue().encode("utf-8-sig"))
        return output, f"attendance_{data.month}_{data.year}.csv", "text/csv"

    @staticmethod
    def get_attendance_meta() -> dict:
        meta = HRService.get_filter_meta()
        meta["attendance_statuses"] = [
            {"value": "all", "label": "Tất cả"},
            {"value": "normal", "label": "Bình thường"},
            {"value": "late", "label": "Đi muộn"},
            {"value": "early", "label": "Về sớm"},
            {"value": "leave_approved", "label": "Nghỉ phép"},
            {"value": "absent_unexcused", "label": "Vắng không phép"},
            {"value": "overtime", "label": "Tăng ca"},
            {"value": "abnormal", "label": "Bất thường"},
        ]
        meta["shift_types"] = [
            {"value": "all", "label": "Tất cả"},
            {"value": "normal", "label": "Ca chuẩn"},
            {"value": "overtime", "label": "Ca tăng ca"},
            {"value": "holiday", "label": "Ca ngày lễ"},
        ]
        return meta
        return meta

    @staticmethod
    def _ensure_hr_employee(user_id: int | None) -> Employee:
        if not user_id:
            raise ValueError("Không xác định được tài khoản HR")

        employee = Employee.query.filter_by(user_id=user_id, is_deleted=False).first()
        if not employee:
            raise ValueError("Không tìm thấy hồ sơ nhân sự")
        return employee

    @staticmethod
    def _serialize_dependent(dependent: Dependent) -> dict:
        return {
            "id": dependent.id,
            "full_name": dependent.full_name,
            "dob": dependent.dob.isoformat() if dependent.dob else None,
            "relationship": dependent.relationship,
            "tax_code": dependent.tax_code,
            "is_valid": bool(dependent.is_valid),
        }

    @staticmethod
    def _validate_dependent_payload(data: DependentDTO) -> None:
        if not data.full_name or len(data.full_name.strip()) < 2:
            raise ValueError("Họ tên người phụ thuộc không hợp lệ")
        if data.relationship not in {"con", "vo_chong", "bo", "me", "khac", "bo_me"}:
            raise ValueError("Quan hệ không hợp lệ")
        if data.tax_code and not re.fullmatch(r"[0-9]{10,13}", data.tax_code):
            raise ValueError("Mã số thuế cá nhân phải có 10-13 chữ số")

    @staticmethod
    def _profile_history(employee_id: int) -> list[dict]:
        logs = (
            HistoryLog.query.filter_by(employee_id=employee_id)
            .order_by(HistoryLog.created_at.desc())
            .limit(50)
            .all()
        )
        return [
            {
                "id": log.id,
                "action": log.action,
                "entity_type": log.entity_type,
                "description": log.description,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]

    @staticmethod
    def get_hr_profile(user_id: int | None) -> dict:
        employee = HRService._ensure_hr_employee(user_id)
        user = employee.user
        contract = HRService._latest_contract(employee.id)
        payroll = (
            Salary.query.filter_by(employee_id=employee.id)
            .order_by(Salary.year.desc(), Salary.month.desc())
            .first()
        )
        dependents = (
            Dependent.query.filter_by(employee_id=employee.id, is_deleted=False)
            .order_by(Dependent.created_at.desc())
            .all()
        )

        number_of_dependents = sum(1 for item in dependents if item.is_valid)

        return {
            "header": {
                "avatar": employee.avatar,
                "full_name": employee.full_name,
                "employee_code": f"EMP{employee.id:05d}",
                "department": employee.department.name if employee.department else "--",
                "position": employee.position.job_title if employee.position else "--",
                "hire_date": employee.hire_date.isoformat() if employee.hire_date else None,
                "working_status": employee.working_status,
            },
            "personal_info": {
                "full_name": employee.full_name,
                "dob": employee.dob.isoformat() if employee.dob else None,
                "gender": employee.gender,
                "address": employee.address,
                "phone": employee.phone,
                "personal_email": user.email if user else None,
            },
            "work_info": {
                "employee_code": f"EMP{employee.id:05d}",
                "department": employee.department.name if employee.department else "--",
                "position": employee.position.job_title if employee.position else "--",
                "manager": employee.manager.full_name if employee.manager else "--",
                "employment_type": employee.employment_type,
                "contract_type": getattr(contract, "contract_type", None) if contract else None,
                "contract_start_date": contract.start_date.isoformat() if contract and contract.start_date else None,
                "contract_end_date": contract.end_date.isoformat() if contract and contract.end_date else None,
                "basic_salary": float(contract.basic_salary) if contract and contract.basic_salary is not None else None,
                "allowance": float(HRService._sum_allowance(employee.id)),
                "account_status": "active" if user and user.is_active else "inactive",
            },
            "payroll_info": {
                "month": payroll.month if payroll else None,
                "year": payroll.year if payroll else None,
                "net_salary": float(payroll.net_salary) if payroll and payroll.net_salary is not None else None,
                "status": payroll.status if payroll else None,
            },
            "dependents": [HRService._serialize_dependent(item) for item in dependents],
            "number_of_dependents": number_of_dependents,
            "history": HRService._profile_history(employee.id),
        }

    @staticmethod
    def update_hr_personal_info(user_id: int | None, data: HRProfileUpdateDTO, actor_user_id: int | None = None) -> dict:
        employee = HRService._ensure_hr_employee(user_id)

        if not data.full_name or len(data.full_name.strip()) < 2:
            raise ValueError("Họ tên không hợp lệ")

        employee.full_name = data.full_name.strip()
        employee.phone = (data.phone or "").strip() or None
        employee.address = (data.address or "").strip() or None

        if data.gender and data.gender not in HRService.VALID_GENDERS:
            raise ValueError("Giới tính không hợp lệ")
        if data.gender:
            employee.gender = data.gender

        if data.dob:
            employee.dob = HRService._parse_date(data.dob, "Ngày sinh")

        if employee.user and data.personal_email:
            employee.user.email = data.personal_email.strip()

        db.session.add(
            HistoryLog(
                employee_id=employee.id,
                action="HR_PROFILE_UPDATED",
                entity_type="employee",
                entity_id=employee.id,
                description="HR cập nhật thông tin cá nhân",
                performed_by=actor_user_id,
            )
        )
        db.session.commit()
        return {"message": "Cập nhật thông tin cá nhân thành công"}

    @staticmethod
    def change_hr_password(user_id: int | None, data: HRPasswordChangeDTO, actor_user_id: int | None = None) -> dict:
        employee = HRService._ensure_hr_employee(user_id)
        user = employee.user
        if not user:
            raise ValueError("Không tìm thấy tài khoản người dùng")

        if not check_password_hash(user.password_hash, data.current_password):
            raise ValueError("Mật khẩu hiện tại không đúng")
        if len(data.new_password) < 8:
            raise ValueError("Mật khẩu mới phải có ít nhất 8 ký tự")
        if data.new_password != data.confirm_password:
            raise ValueError("Xác nhận mật khẩu không khớp")

        user.password_hash = generate_password_hash(data.new_password)
        db.session.add(
            HistoryLog(
                employee_id=employee.id,
                action="HR_PASSWORD_CHANGED",
                entity_type="user",
                entity_id=user.id,
                description="HR đổi mật khẩu",
                performed_by=actor_user_id,
            )
        )
        db.session.commit()
        return {"message": "Đổi mật khẩu thành công"}

    @staticmethod
    def upload_hr_avatar(user_id: int | None, file, actor_user_id: int | None = None) -> dict:
        employee = HRService._ensure_hr_employee(user_id)

        if not file:
            raise ValueError("Không có file avatar")

        filename = secure_filename(file.filename or "")
        if not filename:
            raise ValueError("Tên file không hợp lệ")

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in {"jpg", "jpeg", "png", "webp"}:
            raise ValueError("Avatar chỉ hỗ trợ JPG, PNG hoặc WEBP")

        upload_folder = os.path.join("app", "static", "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(upload_folder, unique_name)
        file.save(filepath)

        employee.avatar = f"/static/uploads/{unique_name}"
        db.session.add(
            HistoryLog(
                employee_id=employee.id,
                action="HR_AVATAR_UPDATED",
                entity_type="employee",
                entity_id=employee.id,
                description="HR cập nhật ảnh đại diện",
                performed_by=actor_user_id,
            )
        )
        db.session.commit()
        return {"message": "Cập nhật ảnh đại diện thành công", "avatar": employee.avatar}

    @staticmethod
    def list_dependents(user_id: int | None) -> dict:
        employee = HRService._ensure_hr_employee(user_id)
        rows = (
            Dependent.query.filter_by(employee_id=employee.id, is_deleted=False)
            .order_by(Dependent.created_at.desc())
            .all()
        )
        number_of_dependents = sum(1 for item in rows if item.is_valid)
        return {
            "items": [HRService._serialize_dependent(item) for item in rows],
            "number_of_dependents": number_of_dependents,
        }

    @staticmethod
    def create_dependent(user_id: int | None, data: DependentDTO, actor_user_id: int | None = None) -> dict:
        employee = HRService._ensure_hr_employee(user_id)
        HRService._validate_dependent_payload(data)

        dob = HRService._parse_date(data.dob, "Ngày sinh người phụ thuộc")
        if not dob or dob > date.today():
            raise ValueError("Ngày sinh người phụ thuộc không hợp lệ")

        dependent = Dependent(
            employee_id=employee.id,
            full_name=data.full_name.strip(),
            dob=dob,
            relationship=data.relationship,
            tax_code=(data.tax_code or "").strip() or None,
            is_valid=bool(data.is_valid),
        )
        db.session.add(dependent)
        db.session.flush()
        db.session.add(
            HistoryLog(
                employee_id=employee.id,
                action="HR_DEPENDENT_CREATED",
                entity_type="dependent",
                entity_id=dependent.id,
                description=f"Thêm người phụ thuộc: {dependent.full_name}",
                performed_by=actor_user_id,
            )
        )
        db.session.commit()
        return {"message": "Thêm người phụ thuộc thành công", "item": HRService._serialize_dependent(dependent)}

    @staticmethod
    def update_dependent(user_id: int | None, dependent_id: int, data: DependentDTO, actor_user_id: int | None = None) -> dict:
        employee = HRService._ensure_hr_employee(user_id)
        dependent = Dependent.query.filter_by(id=dependent_id, employee_id=employee.id, is_deleted=False).first()
        if not dependent:
            raise ValueError("Không tìm thấy người phụ thuộc")

        HRService._validate_dependent_payload(data)
        dependent.full_name = data.full_name.strip()
        dependent.relationship = data.relationship
        dependent.tax_code = (data.tax_code or "").strip() or None
        dependent.is_valid = bool(data.is_valid)
        dob = HRService._parse_date(data.dob, "Ngày sinh người phụ thuộc")
        if not dob or dob > date.today():
            raise ValueError("Ngày sinh người phụ thuộc không hợp lệ")
        dependent.dob = dob

        db.session.add(
            HistoryLog(
                employee_id=employee.id,
                action="HR_DEPENDENT_UPDATED",
                entity_type="dependent",
                entity_id=dependent.id,
                description=f"Cập nhật người phụ thuộc: {dependent.full_name}",
                performed_by=actor_user_id,
            )
        )
        db.session.commit()
        return {"message": "Cập nhật người phụ thuộc thành công", "item": HRService._serialize_dependent(dependent)}

    @staticmethod
    def profile_audit_history(user_id: int | None) -> list[dict]:
        employee = HRService._ensure_hr_employee(user_id)
        return HRService._profile_history(employee.id)