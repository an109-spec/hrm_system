from __future__ import annotations

from datetime import date, datetime, timedelta
import calendar
import csv
import io
import json
from decimal import Decimal
from sqlalchemy import and_, func, or_

from app.extensions.db import db
from app.models import (
    Attendance,
    Complaint,
    Contract,
    Department,
    Employee,
    EmployeeAllowance,
    HistoryLog,
    LeaveRequest,
    Position,
    Role,
    Salary,
    User,
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
)


class HRService:
    VALID_WORKING_STATUSES = {"working", "on_leave", "resigned"}
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

    PAYROLL_STATUSES = {"draft", "pending_approval", "approved", "finalized", "complaint"}

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
        late_minutes = Decimal("0")
        early_minutes = Decimal("0")

        for item in records:
            multiplier = Decimal(str(item.status.multiplier if item.status else 1))
            if item.check_in or item.check_out:
                total_work_days += multiplier
            overtime_hours += HRService._decimal(item.overtime_hours)

            if item.check_in:
                late_ref = item.check_in.replace(hour=8, minute=30, second=0, microsecond=0)
                if item.check_in > late_ref:
                    late_minutes += Decimal(str((item.check_in - late_ref).total_seconds() / 60))

            if item.check_out:
                early_ref = item.check_out.replace(hour=17, minute=30, second=0, microsecond=0)
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
            "complaint": "Khiếu nại",
        }
        return labels.get(status, status)

    @staticmethod
    def _compute_salary(employee: Employee, month: int, year: int) -> tuple[Salary, dict]:
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

        metrics = HRService._attendance_metrics(employee.id, month, year)
        standard_work_days = Decimal("22")
        base_salary = HRService._decimal(contract.basic_salary)

        total_allowance = HRService._sum_allowance(employee.id)
        overtime_amount = (base_salary / standard_work_days / Decimal("8")) * metrics["overtime_hours"]

        late_penalty = Decimal("0")
        if metrics["late_minutes"] > 0:
            if metrics["late_minutes"] < 15:
                late_penalty = Decimal("50000")
            elif metrics["late_minutes"] <= 30:
                late_penalty = Decimal("150000")
            else:
                late_penalty = Decimal("300000")

        early_penalty = Decimal("30000") if metrics["early_minutes"] > 0 else Decimal("0")
        unpaid_leave_penalty = (base_salary / standard_work_days) * Decimal(str(metrics["unpaid_leave_days"]))

        note_payload = HRService._salary_note_payload(salary)
        manual_allowances = note_payload.get("manual_allowances", {})
        manual_deductions = note_payload.get("manual_deductions", {})

        manual_allowance_total = sum(HRService._decimal(v) for v in manual_allowances.values())
        manual_deduction_total = sum(HRService._decimal(v) for v in manual_deductions.values())

        taxable_income = (base_salary / standard_work_days) * metrics["total_work_days"] + overtime_amount + total_allowance + manual_allowance_total
        social_insurance = taxable_income * Decimal("0.08")
        health_insurance = taxable_income * Decimal("0.015")
        unemployment_insurance = taxable_income * Decimal("0.01")

        personal_income_tax = max((taxable_income - Decimal("11000000")) * Decimal("0.05"), Decimal("0"))

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
            "allowance": float(total_allowance),
            "manual_allowance": float(manual_allowance_total),
            "overtime_amount": float(overtime_amount),
            "late_penalty": float(late_penalty),
            "early_penalty": float(early_penalty),
            "unpaid_leave_penalty": float(unpaid_leave_penalty),
            "social_insurance": float(social_insurance),
            "health_insurance": float(health_insurance),
            "unemployment_insurance": float(unemployment_insurance),
            "personal_income_tax": float(personal_income_tax),
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
        if salary.status in {"approved", "finalized"}:
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
        if salary.status in {"approved", "finalized"}:
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
            salary.status = "finalized"
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