from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, func
from werkzeug.security import generate_password_hash

from app.extensions.db import db
from app.models import (
    Attendance,
    Complaint,
    Contract,
    Department,
    Employee,
    HistoryLog,
    LeaveRequest,
    Notification,
    Position,
    Role,
    Salary,
    User,
)

EMPLOYMENT_TYPES = {"probation", "permanent", "intern", "contract"}
WORKING_STATUSES = {"working", "on_leave", "resigned"}
ACCOUNT_STATUSES = {"active", "locked", "inactive", "pending"}


class ServiceValidationError(ValueError):
    pass


def _as_date(value: str | None, field_name: str, required: bool = False) -> date | None:
    if not value:
        if required:
            raise ServiceValidationError(f"{field_name} là bắt buộc")
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ServiceValidationError(f"{field_name} không đúng định dạng YYYY-MM-DD") from exc


def _as_decimal(value: Any, field_name: str, required: bool = False) -> Decimal | None:
    if value in (None, ""):
        if required:
            raise ServiceValidationError(f"{field_name} là bắt buộc")
        return None
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ServiceValidationError(f"{field_name} không hợp lệ") from exc


def _account_status(user: User | None) -> str:
    if not user:
        return "pending"
    if user.is_deleted:
        return "inactive"
    if not user.is_active:
        return "locked" if user.locked_at else "inactive"
    return "active"


def _employee_to_row(employee: Employee) -> dict[str, Any]:
    user = employee.user
    latest_contract = employee.contracts.order_by(Contract.start_date.desc(), Contract.created_at.desc()).first()
    return {
        "id": int(employee.id),
        "employee_code": f"EMP-{employee.id:05d}",
        "avatar": employee.avatar,
        "full_name": employee.full_name,
        "email": user.email if user else None,
        "phone": employee.phone,
        "department": employee.department.name if employee.department else None,
        "department_id": int(employee.department_id) if employee.department_id else None,
        "position": employee.position.job_title if employee.position else None,
        "position_id": int(employee.position_id) if employee.position_id else None,
        "role": user.role.name if user and user.role else "Employee",
        "role_id": int(user.role_id) if user and user.role_id else None,
        "hire_date": employee.hire_date.isoformat() if employee.hire_date else None,
        "employment_type": employee.employment_type,
        "working_status": employee.working_status,
        "account_status": _account_status(user),
        "username": user.username if user else None,
        "user_id": int(user.id) if user else None,
        "contract": {
            "contract_code": latest_contract.contract_code if latest_contract else None,
            "end_date": latest_contract.end_date.isoformat() if latest_contract and latest_contract.end_date else None,
            "status": latest_contract.status if latest_contract else None,
            "basic_salary": float(latest_contract.basic_salary) if latest_contract and latest_contract.basic_salary is not None else None,
        },
    }


def employee_summary_cards(today: date | None = None) -> dict[str, int]:
    today = today or date.today()
    contract_cutoff = today + timedelta(days=30)

    total = Employee.query.filter_by(is_deleted=False).count()
    working = Employee.query.filter_by(is_deleted=False, working_status="working").count()
    probation = Employee.query.filter_by(is_deleted=False, employment_type="probation").count()
    inactive = Employee.query.filter(
        Employee.is_deleted.is_(False),
        or_(Employee.working_status == "resigned", Employee.user.has(User.is_active.is_(False)))
    ).count()

    leave_today = LeaveRequest.query.filter(
        LeaveRequest.is_deleted.is_(False),
        LeaveRequest.status == "approved",
        LeaveRequest.from_date <= today,
        LeaveRequest.to_date >= today,
    ).count()

    expiring_contract = Contract.query.join(Employee, Contract.employee_id == Employee.id).filter(
        Employee.is_deleted.is_(False),
        Contract.status == "active",
        Contract.end_date.isnot(None),
        Contract.end_date >= today,
        Contract.end_date <= contract_cutoff,
    ).count()

    return {
        "total": total,
        "working": working,
        "probation": probation,
        "leave_today": leave_today,
        "expiring_contract": expiring_contract,
        "inactive": inactive,
    }


def employee_notifications(today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
    in_7_days = today + timedelta(days=7)
    in_30_days = today + timedelta(days=30)

    notices: list[dict[str, Any]] = []

    probation_due = Employee.query.filter(
        Employee.is_deleted.is_(False),
        Employee.employment_type == "probation",
        Employee.hire_date.isnot(None),
        Employee.hire_date >= today - timedelta(days=85),
        Employee.hire_date <= in_7_days - timedelta(days=90),
    ).count()
    notices.append({"code": "probation", "title": "Probation sắp kết thúc", "count": probation_due})

    expiring = Contract.query.join(Employee, Contract.employee_id == Employee.id).filter(
        Employee.is_deleted.is_(False),
        Contract.status == "active",
        Contract.end_date.isnot(None),
        Contract.end_date >= today,
        Contract.end_date <= in_30_days,
    ).count()
    notices.append({"code": "contract", "title": "Hợp đồng sắp hết hạn", "count": expiring})

    serious_complaint = Complaint.query.filter(
        Complaint.is_deleted.is_(False),
        Complaint.status.in_(["pending", "in_progress"]),
        Complaint.priority.in_(["high", "urgent"]),
    ).count()
    notices.append({"code": "complaint", "title": "Complaint nghiêm trọng", "count": serious_complaint})

    leave_escalation = LeaveRequest.query.filter(
        LeaveRequest.is_deleted.is_(False),
        LeaveRequest.status.in_(["pending_admin", "supplement_requested"]),
    ).count()
    notices.append({"code": "leave", "title": "Leave escalation", "count": leave_escalation})

    current_month = today.month
    current_year = today.year
    payroll_issue = Salary.query.filter(
        Salary.is_deleted.is_(False),
        Salary.month == current_month,
        Salary.year == current_year,
        Salary.status == "pending",
    ).count()
    notices.append({"code": "payroll", "title": "Payroll issue", "count": payroll_issue})

    transfer_req = HistoryLog.query.filter(
        HistoryLog.action == "TRANSFER_REQUEST",
        HistoryLog.created_at >= datetime.combine(today - timedelta(days=30), datetime.min.time()),
    ).count()
    notices.append({"code": "transfer", "title": "Yêu cầu điều chuyển", "count": transfer_req})

    return notices


def query_employees(filters: dict[str, Any]) -> list[dict[str, Any]]:
    q = Employee.query.join(User, Employee.user_id == User.id, isouter=True).filter(Employee.is_deleted.is_(False))

    name = (filters.get("name") or "").strip()
    employee_code = (filters.get("employee_code") or "").strip().upper()
    email = (filters.get("email") or "").strip()
    department_id = filters.get("department_id", type=int) if hasattr(filters, "get") else filters.get("department_id")
    position_id = filters.get("position_id", type=int) if hasattr(filters, "get") else filters.get("position_id")
    role_id = filters.get("role_id", type=int) if hasattr(filters, "get") else filters.get("role_id")
    working_status = (filters.get("working_status") or "").strip()
    employment_type = (filters.get("employment_type") or "").strip()
    probation = (filters.get("probation") or "").strip()
    hire_date_from = _as_date(filters.get("hire_date_from"), "hire_date_from")
    hire_date_to = _as_date(filters.get("hire_date_to"), "hire_date_to")

    if name:
        q = q.filter(Employee.full_name.ilike(f"%{name}%"))
    if employee_code.startswith("EMP-") and employee_code[4:].isdigit():
        q = q.filter(Employee.id == int(employee_code[4:]))
    if email:
        q = q.filter(User.email.ilike(f"%{email}%"))
    if department_id:
        q = q.filter(Employee.department_id == int(department_id))
    if position_id:
        q = q.filter(Employee.position_id == int(position_id))
    if role_id:
        q = q.filter(User.role_id == int(role_id))
    if working_status:
        q = q.filter(Employee.working_status == working_status)
    if employment_type:
        q = q.filter(Employee.employment_type == employment_type)
    if probation == "true":
        q = q.filter(Employee.employment_type == "probation")
    elif probation == "false":
        q = q.filter(Employee.employment_type != "probation")
    if hire_date_from:
        q = q.filter(Employee.hire_date >= hire_date_from)
    if hire_date_to:
        q = q.filter(Employee.hire_date <= hire_date_to)

    rows = q.order_by(Employee.created_at.desc()).all()
    return [_employee_to_row(row) for row in rows]


def create_employee(payload: dict[str, Any], actor_id: int) -> dict[str, Any]:
    full_name = (payload.get("full_name") or "").strip()
    if len(full_name) < 2:
        raise ServiceValidationError("Họ tên không hợp lệ")

    email = (payload.get("email") or "").strip().lower()
    if not email:
        raise ServiceValidationError("Email là bắt buộc")
    if User.query.filter(func.lower(User.email) == email).first():
        raise ServiceValidationError("Email đã tồn tại")

    username = (payload.get("username") or "").strip().lower()
    if not username:
        raise ServiceValidationError("Username là bắt buộc")
    if User.query.filter(func.lower(User.username) == username).first():
        raise ServiceValidationError("Username đã tồn tại")

    password = (payload.get("password") or "").strip()
    if len(password) < 8:
        raise ServiceValidationError("Mật khẩu khởi tạo tối thiểu 8 ký tự")

    phone = (payload.get("phone") or "").strip()
    if phone and Employee.query.filter(Employee.phone == phone).first():
        raise ServiceValidationError("Số điện thoại đã tồn tại")

    role_id = payload.get("role_id")
    role = Role.query.get(role_id) if role_id else None
    if role_id and not role:
        raise ServiceValidationError("Role không tồn tại")

    department_id = payload.get("department_id")
    if department_id and not Department.query.get(department_id):
        raise ServiceValidationError("Phòng ban không tồn tại")

    position_id = payload.get("position_id")
    if position_id and not Position.query.get(position_id):
        raise ServiceValidationError("Chức danh không tồn tại")

    gender = (payload.get("gender") or "other").strip().lower()
    if gender not in {"male", "female", "other"}:
        raise ServiceValidationError("Giới tính không hợp lệ")

    employment_type = (payload.get("employment_type") or "probation").strip()
    if employment_type not in EMPLOYMENT_TYPES:
        raise ServiceValidationError("Loại hợp đồng không hợp lệ")

    working_status = (payload.get("working_status") or "working").strip()
    if working_status not in WORKING_STATUSES:
        raise ServiceValidationError("Trạng thái làm việc không hợp lệ")

    account_status = (payload.get("account_status") or "active").strip()
    if account_status not in ACCOUNT_STATUSES:
        raise ServiceValidationError("Trạng thái tài khoản không hợp lệ")

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role_id=role.id if role else None,
        is_active=account_status == "active",
    )
    if account_status == "locked":
        user.locked_at = datetime.utcnow()
        user.lock_reason = "Khởi tạo ở trạng thái lock"
        user.locked_by = actor_id

    employee = Employee(
        user=user,
        full_name=full_name,
        dob=_as_date(payload.get("dob"), "Ngày sinh", required=True),
        gender=gender,
        phone=phone or None,
        address_detail=(payload.get("address") or "").strip() or None,
        avatar=(payload.get("avatar") or "").strip() or None,
        department_id=department_id,
        position_id=position_id,
        hire_date=_as_date(payload.get("hire_date"), "Ngày vào làm", required=True),
        employment_type=employment_type,
        working_status=working_status,
    )

    db.session.add(user)
    db.session.add(employee)
    db.session.flush()

    basic_salary = _as_decimal(payload.get("basic_salary"), "Lương cơ bản")
    if basic_salary:
        contract = Contract(
            employee_id=employee.id,
            contract_code=(payload.get("contract_code") or f"HD-{employee.id}-{date.today().strftime('%Y%m%d')}").strip(),
            basic_salary=basic_salary,
            start_date=_as_date(payload.get("hire_date"), "Ngày vào làm", required=True),
            end_date=_as_date(payload.get("contract_end_date"), "Ngày kết thúc hợp đồng"),
            status="active",
        )
        db.session.add(contract)

    db.session.add(HistoryLog(
        employee_id=employee.id,
        action="CREATE_EMPLOYEE",
        entity_type="employee",
        entity_id=employee.id,
        description=f"Tạo mới nhân sự {employee.full_name}",
        performed_by=actor_id,
    ))
    db.session.add(Notification(
        user_id=actor_id,
        title="Đã tạo nhân viên mới",
        content=f"Nhân viên {employee.full_name} đã được tạo thành công.",
        type="system",
    ))
    db.session.commit()
    return _employee_to_row(employee)


def employee_detail(employee_id: int) -> dict[str, Any]:
    employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first_or_404()

    current_month = date.today().month
    current_year = date.today().year

    attendance_summary = db.session.query(
        func.count(Attendance.id).label("total"),
        func.coalesce(func.sum(Attendance.working_hours), 0).label("working_hours"),
    ).filter(
        Attendance.employee_id == employee.id,
        func.extract("month", Attendance.date) == current_month,
        func.extract("year", Attendance.date) == current_year,
    ).first()

    leave_summary = {
        "pending": LeaveRequest.query.filter_by(employee_id=employee.id, status="pending", is_deleted=False).count(),
        "approved": LeaveRequest.query.filter_by(employee_id=employee.id, status="approved", is_deleted=False).count(),
    }

    payroll_summary = Salary.query.filter_by(employee_id=employee.id, month=current_month, year=current_year, is_deleted=False).first()
    latest_contract = employee.contracts.order_by(Contract.start_date.desc(), Contract.created_at.desc()).first()
    history = HistoryLog.query.filter(
        or_(HistoryLog.employee_id == employee.id, db.and_(HistoryLog.entity_type == "user", HistoryLog.entity_id == employee.user_id))
    ).order_by(HistoryLog.created_at.desc()).limit(20).all()

    complaints = Complaint.query.filter_by(employee_id=employee.id, is_deleted=False).order_by(Complaint.created_at.desc()).limit(10).all()

    row = _employee_to_row(employee)
    row.update({
        "profile": {
            "dob": employee.dob.isoformat() if employee.dob else None,
            "gender": employee.gender,
            "address": employee.address_detail or employee.address,
        },
        "attendance_summary": {
            "total_days": int(attendance_summary.total or 0),
            "working_hours": float(attendance_summary.working_hours or 0),
        },
        "leave_summary": leave_summary,
        "payroll_summary": {
            "net_salary": float(payroll_summary.net_salary) if payroll_summary else None,
            "status": payroll_summary.status if payroll_summary else None,
            "month": current_month,
            "year": current_year,
        },
        "contract_info": {
            "contract_code": latest_contract.contract_code if latest_contract else None,
            "start_date": latest_contract.start_date.isoformat() if latest_contract else None,
            "end_date": latest_contract.end_date.isoformat() if latest_contract and latest_contract.end_date else None,
            "status": latest_contract.status if latest_contract else None,
            "basic_salary": float(latest_contract.basic_salary) if latest_contract and latest_contract.basic_salary is not None else None,
        },
        "history_log": [
            {
                "time": h.created_at.isoformat() if h.created_at else None,
                "action": h.action,
                "description": h.description,
            }
            for h in history
        ],
        "complaints": [
            {
                "id": int(c.id),
                "title": c.title,
                "status": c.status,
                "priority": c.priority,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in complaints
        ],
    })
    return row


def update_employee(employee_id: int, payload: dict[str, Any], actor_id: int) -> dict[str, Any]:
    employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first_or_404()
    user = employee.user

    if "full_name" in payload:
        full_name = (payload.get("full_name") or "").strip()
        if len(full_name) < 2:
            raise ServiceValidationError("Họ tên không hợp lệ")
        employee.full_name = full_name

    if "phone" in payload:
        phone = (payload.get("phone") or "").strip()
        if phone:
            exists = Employee.query.filter(Employee.phone == phone, Employee.id != employee.id).first()
            if exists:
                raise ServiceValidationError("Số điện thoại đã tồn tại")
        employee.phone = phone or None

    if "email" in payload and user:
        email = (payload.get("email") or "").strip().lower()
        if not email:
            raise ServiceValidationError("Email không được trống")
        exists = User.query.filter(func.lower(User.email) == email, User.id != user.id).first()
        if exists:
            raise ServiceValidationError("Email đã tồn tại")
        user.email = email

    if "department_id" in payload:
        dept_id = payload.get("department_id")
        if dept_id and not Department.query.get(dept_id):
            raise ServiceValidationError("Phòng ban không tồn tại")
        employee.department_id = dept_id

    if "position_id" in payload:
        position_id = payload.get("position_id")
        if position_id and not Position.query.get(position_id):
            raise ServiceValidationError("Chức danh không tồn tại")
        employee.position_id = position_id

    if "role_id" in payload and user:
        role = Role.query.get(payload.get("role_id"))
        if not role:
            raise ServiceValidationError("Role không tồn tại")
        user.role_id = role.id

    if "working_status" in payload:
        status = (payload.get("working_status") or "").strip()
        if status not in WORKING_STATUSES:
            raise ServiceValidationError("Trạng thái làm việc không hợp lệ")
        employee.working_status = status

    if "account_status" in payload and user:
        account_status = (payload.get("account_status") or "").strip()
        if account_status not in ACCOUNT_STATUSES:
            raise ServiceValidationError("Trạng thái tài khoản không hợp lệ")
        if account_status == "active":
            user.is_active = True
            user.locked_at = None
            user.lock_reason = None
        elif account_status == "locked":
            user.is_active = False
            user.locked_at = datetime.utcnow()
            user.lock_reason = payload.get("lock_reason") or "Khóa từ admin"
            user.locked_by = actor_id
        else:
            user.is_active = False

    db.session.add(HistoryLog(
        employee_id=employee.id,
        action="UPDATE_EMPLOYEE",
        entity_type="employee",
        entity_id=employee.id,
        description="Cập nhật hồ sơ nhân sự",
        performed_by=actor_id,
    ))
    db.session.commit()
    return _employee_to_row(employee)


def soft_delete_employee(employee_id: int, actor_id: int) -> None:
    employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first_or_404()
    employee.is_deleted = True
    employee.working_status = "resigned"
    if employee.user:
        employee.user.is_active = False
        employee.user.lock_reason = "Set inactive bởi Admin"
        employee.user.locked_at = datetime.utcnow()
        employee.user.locked_by = actor_id
    db.session.add(HistoryLog(
        employee_id=employee.id,
        action="SOFT_DELETE_EMPLOYEE",
        entity_type="employee",
        entity_id=employee.id,
        description="Chuyển trạng thái inactive thay vì xóa cứng",
        performed_by=actor_id,
    ))
    db.session.commit()


def transfer_employee(employee_id: int, payload: dict[str, Any], actor_id: int) -> dict[str, Any]:
    employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first_or_404()
    department_id = payload.get("department_id")
    position_id = payload.get("position_id")
    if department_id and not Department.query.get(department_id):
        raise ServiceValidationError("Phòng ban không tồn tại")
    if position_id and not Position.query.get(position_id):
        raise ServiceValidationError("Chức danh không tồn tại")

    old_department = employee.department.name if employee.department else "N/A"
    old_position = employee.position.job_title if employee.position else "N/A"

    if department_id:
        employee.department_id = department_id
    if position_id:
        employee.position_id = position_id

    db.session.add(HistoryLog(
        employee_id=employee.id,
        action="TRANSFER_EMPLOYEE",
        entity_type="employee",
        entity_id=employee.id,
        description=f"{old_department}/{old_position} -> {employee.department.name if employee.department else 'N/A'}/{employee.position.job_title if employee.position else 'N/A'}",
        performed_by=actor_id,
    ))
    db.session.commit()
    return _employee_to_row(employee)


def reset_employee_password(user_id: int, new_password: str, actor_id: int) -> None:
    user = User.query.get_or_404(user_id)
    if len((new_password or "").strip()) < 8:
        raise ServiceValidationError("Mật khẩu mới tối thiểu 8 ký tự")
    user.password_hash = generate_password_hash(new_password.strip())
    user.failed_login_attempts = 0
    db.session.add(HistoryLog(
        action="RESET_PASSWORD",
        entity_type="user",
        entity_id=user.id,
        description="Admin reset mật khẩu tài khoản",
        performed_by=actor_id,
    ))
    db.session.commit()


def employee_filter_metadata() -> dict[str, list[dict[str, Any]]]:
    return {
        "departments": [{"id": int(d.id), "name": d.name} for d in Department.query.filter_by(is_deleted=False).order_by(Department.name.asc()).all()],
        "positions": [{"id": int(p.id), "name": p.job_title} for p in Position.query.filter_by(is_deleted=False).order_by(Position.job_title.asc()).all()],
        "roles": [{"id": int(r.id), "name": r.name} for r in Role.query.order_by(Role.name.asc()).all()],
    }