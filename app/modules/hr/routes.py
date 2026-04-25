from __future__ import annotations

from flask import jsonify, redirect, render_template, request, send_file, session, url_for

from app.models import Employee, User
from . import hr_bp
from .dto import (
    AccountStatusDTO,
    ContractFilterDTO,
    CreateContractDTO,
    CreateEmployeeDTO,
    EmployeeFilterDTO,
    ExtendContractDTO,
    PayrollAdjustmentDTO,
    PayrollApprovalDTO,
    PayrollCalculationDTO,
    PayrollComplaintHandleDTO,
    PayrollExportDTO,
    PayrollFilterDTO,
    TerminateContractDTO,
    UpdateContractDTO,
    UpdateEmployeeDTO,
)
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

@hr_bp.route("/contracts", methods=["GET"])
def contracts_page():
    guard = _guard_hr_access()
    if guard:
        return guard
    return render_template("hr/contracts.html", employee=_current_employee())

@hr_bp.route("/payroll", methods=["GET"])
def payroll_page():
    guard = _guard_hr_access()
    if guard:
        return guard
    return render_template("hr/payroll.html", employee=_current_employee())

@hr_bp.route("/api/meta", methods=["GET"])
def meta_api():
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    return jsonify(HRService.get_filter_meta())

@hr_bp.route("/api/payroll/meta", methods=["GET"])
def payroll_meta_api():
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    return jsonify(HRService.get_payroll_meta())


@hr_bp.route("/api/payroll/calculate", methods=["POST"])
def calculate_payroll_api():
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    month = int(payload.get("month") or 0)
    year = int(payload.get("year") or 0)
    if month < 1 or month > 12 or year < 2000:
        return jsonify({"error": "Tháng/năm không hợp lệ"}), 400

    dto = PayrollCalculationDTO(
        month=month,
        year=year,
        department_id=payload.get("department_id"),
    )
    result = HRService.calculate_monthly_payroll(dto, actor_user_id=session.get("user_id"))
    return jsonify(result)


@hr_bp.route("/api/payroll", methods=["GET"])
def payroll_list_api():
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    dto = PayrollFilterDTO(
        search=request.args.get("search") or None,
        department_id=request.args.get("department_id", type=int),
        status=request.args.get("status") or "all",
        month=request.args.get("month", type=int),
        year=request.args.get("year", type=int),
    )
    return jsonify(HRService.get_payroll_list(dto))


@hr_bp.route("/api/payroll/<int:salary_id>", methods=["GET"])
def payroll_detail_api(salary_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    try:
        return jsonify(HRService.get_payroll_detail(salary_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@hr_bp.route("/api/payroll/<int:salary_id>/adjustments", methods=["PUT"])
def payroll_adjustments_api(salary_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    dto = PayrollAdjustmentDTO(
        fuel_allowance=float(payload.get("fuel_allowance") or 0),
        meal_allowance=float(payload.get("meal_allowance") or 0),
        responsibility_allowance=float(payload.get("responsibility_allowance") or 0),
        other_allowance=float(payload.get("other_allowance") or 0),
        late_penalty=float(payload.get("late_penalty") or 0),
        early_penalty=float(payload.get("early_penalty") or 0),
        unpaid_leave_penalty=float(payload.get("unpaid_leave_penalty") or 0),
        other_penalty=float(payload.get("other_penalty") or 0),
        note=payload.get("note"),
    )

    try:
        data = HRService.update_allowance_deduction(salary_id, dto, actor_user_id=session.get("user_id"))
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@hr_bp.route("/api/payroll/<int:salary_id>/submit", methods=["POST"])
def payroll_submit_api(salary_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    try:
        return jsonify(HRService.submit_payroll_approval(salary_id, actor_user_id=session.get("user_id")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@hr_bp.route("/api/payroll/<int:salary_id>/approve", methods=["POST"])
def payroll_approve_api(salary_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    dto = PayrollApprovalDTO(action=payload.get("action", ""), note=payload.get("note"))
    try:
        return jsonify(HRService.approve_payroll_flow(salary_id, dto, actor_user_id=session.get("user_id")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@hr_bp.route("/api/payroll/export", methods=["GET"])
def payroll_export_api():
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    try:
        dto = PayrollExportDTO(
            month=int(request.args.get("month") or 0),
            year=int(request.args.get("year") or 0),
            export_scope=request.args.get("scope") or "company",
            department_id=request.args.get("department_id", type=int),
            export_format=request.args.get("format") or "excel",
        )
        stream, filename, mimetype = HRService.export_payslip(dto)
        stream.seek(0)
        return send_file(stream, as_attachment=True, download_name=filename, mimetype=mimetype)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@hr_bp.route("/api/payroll/<int:salary_id>/audit", methods=["GET"])
def payroll_audit_api(salary_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    return jsonify(HRService.payroll_audit_history(salary_id))


@hr_bp.route("/api/payroll/complaints", methods=["GET"])
def payroll_complaints_api():
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    return jsonify(HRService.get_payroll_complaints(month=month, year=year))


@hr_bp.route("/api/payroll/complaints/<int:complaint_id>/handle", methods=["POST"])
def payroll_complaint_handle_api(complaint_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    dto = PayrollComplaintHandleDTO(
        complaint_id=complaint_id,
        action=payload.get("action", ""),
        message=payload.get("message"),
        payroll_status=payload.get("payroll_status"),
    )

    try:
        result = HRService.handle_complaint(
            dto,
            handler_employee_id=_current_employee().id if _current_employee() else None,
            actor_user_id=session.get("user_id"),
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400



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

@hr_bp.route("/api/contracts", methods=["GET"])
def list_contracts_api():
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    filters = ContractFilterDTO(
        search=request.args.get("search") or None,
        contract_status=request.args.get("contract_status") or "all",
        contract_type=request.args.get("contract_type") or "all",
    )
    return jsonify(HRService.get_contracts(filters))


@hr_bp.route("/api/contracts/reminders", methods=["GET"])
def contract_reminders_api():
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    return jsonify(HRService.get_contract_reminders())


@hr_bp.route("/api/contracts/<int:contract_id>", methods=["GET"])
def contract_detail_api(contract_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    try:
        return jsonify(HRService.get_contract_detail(contract_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404



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

@hr_bp.route("/api/contracts/<int:contract_id>", methods=["PUT"])
def update_contract_api(contract_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    dto = UpdateContractDTO(
        basic_salary=payload.get("basic_salary"),
        start_date=payload.get("start_date"),
        end_date=payload.get("end_date"),
        contract_type=payload.get("contract_type"),
        note=payload.get("note"),
    )

    try:
        contract = HRService.update_contract(contract_id, dto)
        return jsonify({"id": contract.id, "message": "Cập nhật hợp đồng thành công"})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@hr_bp.route("/api/contracts/<int:contract_id>/extend", methods=["POST"])
def extend_contract_api(contract_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    dto = ExtendContractDTO(
        end_date=payload.get("end_date", ""),
        note=payload.get("note"),
    )

    try:
        contract = HRService.extend_contract(contract_id, dto)
        return jsonify({"id": contract.id, "message": "Gia hạn hợp đồng thành công"})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@hr_bp.route("/api/contracts/<int:contract_id>/terminate", methods=["POST"])
def terminate_contract_api(contract_id: int):
    guard = _guard_hr_access()
    if guard:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    dto = TerminateContractDTO(
        end_date=payload.get("end_date"),
        note=payload.get("note"),
    )

    try:
        contract = HRService.terminate_contract(contract_id, dto)
        return jsonify({"id": contract.id, "message": "Đã kết thúc hợp đồng"})
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