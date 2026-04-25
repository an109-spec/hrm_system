from __future__ import annotations

from flask import jsonify, redirect, render_template, request, session, url_for

from app.models import Employee, User
from . import hr_bp
from .dto import AccountStatusDTO, CreateContractDTO, CreateEmployeeDTO, EmployeeFilterDTO, UpdateEmployeeDTO
from .service import HRService


def _current_user() -> User | None:
    user_id = session.get("user_id")
    return User.query.get(user_id) if user_id else None


def _current_employee() -> Employee | None:
    user = _current_user()
    if not user:
        return None
    return Employee.query.filter_by(user_id=user.id).first()


def _guard_hr_access():
    if not session.get("user_id"):
        return redirect(url_for("auth.login", next=request.url))

    user = _current_user()
    role_name = (user.role.name.lower() if user and user.role else "")
    if role_name != "hr":
        return redirect(url_for("employee.dashboard"))

    return None


@hr_bp.route("/employees", methods=["GET"])
def employees_page():
    guard = _guard_hr_access()
    if guard:
        return guard
    return render_template("hr/employees.html", employee=_current_employee())


@hr_bp.route("/api/meta", methods=["GET"])
def meta_api():
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    return jsonify(HRService.get_filter_meta())


@hr_bp.route("/api/employees", methods=["GET"])
def list_employees_api():
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    filters = EmployeeFilterDTO(
        search=request.args.get("search") or None,
        department_id=request.args.get("department_id", type=int),
        position_id=request.args.get("position_id", type=int),
        working_status=request.args.get("working_status") or None,
    )
    return jsonify(HRService.get_employees(filters))


@hr_bp.route("/api/employees/<int:employee_id>", methods=["GET"])
def employee_detail_api(employee_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    try:
        return jsonify(HRService.get_employee_detail(employee_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@hr_bp.route("/api/employees", methods=["POST"])
def create_employee_api():
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    dto = CreateEmployeeDTO(
        full_name=payload.get("full_name", ""),
        dob=payload.get("dob", ""),
        gender=payload.get("gender", "other"),
        phone=payload.get("phone", ""),
        address=payload.get("address"),
        department_id=payload.get("department_id"),
        position_id=payload.get("position_id"),
        manager_id=payload.get("manager_id"),
        hire_date=payload.get("hire_date"),
        employment_type=payload.get("employment_type", "probation"),
        working_status=payload.get("working_status", "working"),
        create_account=bool(payload.get("create_account")),
        username=payload.get("username"),
        email=payload.get("email"),
        password=payload.get("password"),
    )

    try:
        employee = HRService.create_employee(dto)
        return jsonify({"id": employee.id, "message": "Tạo nhân viên thành công"}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@hr_bp.route("/api/employees/<int:employee_id>", methods=["PUT"])
def update_employee_api(employee_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    dto = UpdateEmployeeDTO(
        full_name=payload.get("full_name"),
        phone=payload.get("phone"),
        address=payload.get("address"),
        department_id=payload.get("department_id"),
        position_id=payload.get("position_id"),
        manager_id=payload.get("manager_id"),
        working_status=payload.get("working_status"),
    )

    try:
        employee = HRService.update_employee(employee_id, dto)
        return jsonify({"id": employee.id, "message": "Cập nhật nhân viên thành công"})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@hr_bp.route("/api/contracts", methods=["POST"])
def create_contract_api():
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    dto = CreateContractDTO(
        employee_id=payload.get("employee_id"),
        basic_salary=payload.get("basic_salary", 0),
        start_date=payload.get("start_date"),
        end_date=payload.get("end_date"),
        contract_type=payload.get("contract_type"),
        note=payload.get("note"),
    )

    try:
        contract = HRService.create_contract(dto)
        return jsonify({"id": contract.id, "contract_code": contract.contract_code, "message": "Tạo hợp đồng thành công"}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@hr_bp.route("/api/accounts/<int:employee_id>/status", methods=["PATCH"])
def update_account_status_api(employee_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    dto = AccountStatusDTO(employee_id=employee_id, is_active=bool(payload.get("is_active")))
    try:
        account = HRService.update_account_status(dto)
        return jsonify({"user_id": account.id, "is_active": account.is_active, "message": "Cập nhật trạng thái tài khoản thành công"})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400