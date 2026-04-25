from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import func, or_

from app.extensions.db import db
from app.models import Contract, Department, Employee, EmployeeAllowance, Position, Role, User
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
