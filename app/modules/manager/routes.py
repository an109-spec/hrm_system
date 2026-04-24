from __future__ import annotations

from flask import jsonify, render_template, request, session, redirect, url_for
from app.models.employee import Employee
from . import manager_bp
from .service import ManagerService
from app.modules.employee.routes import _get_holiday_for_date
from app.utils.time import parse_simulated_time

def _current_manager() -> Employee | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return Employee.query.filter_by(user_id=user_id).first()

def _guard_login():
    if not session.get("user_id"):
        return redirect(url_for("auth.login", next=request.url))
    return None

@manager_bp.route("/")
def dashboard_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    return render_template("manager/dashboard.html", employee=manager)


@manager_bp.route("/attendance")
def attendance_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    now = parse_simulated_time({})
    today_holiday = _get_holiday_for_date(now.date())
    return render_template(
        "manager/attendance.html",
        employee=manager,
        today_holiday=today_holiday,
    )

@manager_bp.route("/department-employees")
def department_employees_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    return render_template("manager/department_employees.html", employee=manager)

@manager_bp.route("/leave-management")
def leave_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    return render_template("manager/leave.html", employee=manager)


@manager_bp.route("/contracts")
def contracts_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    return render_template("manager/contract.html", employee=manager)


@manager_bp.route("/payroll")
def payroll_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    return render_template("manager/payroll.html", employee=manager)


@manager_bp.route("/profile")
def profile_page():
    return redirect(url_for("employee.profile"))


@manager_bp.route("/notifications")
def notifications_page():
    return redirect(url_for("employee.notifications"))


@manager_bp.route("/dashboard", methods=["GET"])
def dashboard_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    return jsonify(ManagerService.get_dashboard(manager.id))


@manager_bp.route("/attendance/today", methods=["GET"])
def attendance_today_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    return jsonify(ManagerService.get_today_attendance(manager.id))


@manager_bp.route("/attendance/month", methods=["GET"])
def attendance_month_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404

    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    if not month or not year:
        return jsonify({"error": "month và year là bắt buộc"}), 400

    return jsonify(ManagerService.get_month_attendance_summary(manager.id, month, year))


@manager_bp.route("/leave", methods=["GET"])
def leave_list_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404

    status = request.args.get("status") or None
    return jsonify(ManagerService.get_leave_requests(manager.id, status))

@manager_bp.route("/leave/<int:leave_id>/approve", methods=["POST"])
def approve_leave_api(leave_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404

    data = request.get_json(silent=True) or {}
    leave = ManagerService.approve_leave(manager.id, leave_id, data.get("note"))
    return jsonify({"message": "Approved", "id": leave.id})


@manager_bp.route("/leave/<int:leave_id>/reject", methods=["POST"])
def reject_leave_api(leave_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404

    data = request.get_json(silent=True) or {}
    leave = ManagerService.reject_leave(manager.id, leave_id, data.get("note"))
    return jsonify({"message": "Rejected", "id": leave.id})

@manager_bp.route("/reminder", methods=["POST"])
def reminder_api():
    data = request.get_json(silent=True) or {}
    employee_ids = data.get("employee_ids") or []
    ManagerService.send_reminder(employee_ids, data.get("message"))
    return jsonify({"message": "Sent"})


@manager_bp.route("/contracts/expiring", methods=["GET"])
def contract_expiring_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404

    return jsonify(ManagerService.get_contract_expiring(manager.id))


@manager_bp.route("/contracts/renew", methods=["POST"])
def renew_contract_api():
    data = request.get_json(silent=True) or {}
    contract = ManagerService.renew_contract(data)
    return jsonify({"id": contract.id, "message": "Renewed"})


@manager_bp.route("/salary", methods=["GET"])
def salary_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404

    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    if not month or not year:
        return jsonify({"error": "month và year là bắt buộc"}), 400


    return jsonify(ManagerService.get_department_salary(manager.id, month, year))