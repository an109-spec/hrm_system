from flask import request, jsonify, g

from app.common.security.permissions import permission_required
from . import manager_bp
from .service import ManagerService


# =========================
# DASHBOARD
# =========================
@manager_bp.route("/dashboard")
@permission_required("employee:view_team")
def dashboard():
    data = ManagerService.get_dashboard(g.employee.id)
    return jsonify(data)


# =========================
# ATTENDANCE TODAY
# =========================
@manager_bp.route("/attendance/today")
def attendance_today():
    data = ManagerService.get_today_attendance(g.employee.id)
    return jsonify(data)


# =========================
# LEAVE LIST
# =========================
@manager_bp.route("/leave")
def leave_list():
    status = request.args.get("status")
    data = ManagerService.get_leave_requests(g.employee.id, status)
    return jsonify([l.id for l in data])


# =========================
# APPROVE
# =========================
@manager_bp.route("/leave/<int:leave_id>/approve", methods=["POST"])
def approve_leave(leave_id):
    data = request.json or {}
    leave = ManagerService.approve_leave(g.employee.id, leave_id, data.get("note"))
    return jsonify({"message": "Approved", "id": leave.id})


# =========================
# REJECT
# =========================
@manager_bp.route("/leave/<int:leave_id>/reject", methods=["POST"])
def reject_leave(leave_id):
    data = request.json or {}
    leave = ManagerService.reject_leave(g.employee.id, leave_id, data.get("note"))
    return jsonify({"message": "Rejected", "id": leave.id})


# =========================
# REMINDER
# =========================
@manager_bp.route("/reminder", methods=["POST"])
def reminder():
    data = request.json
    ManagerService.send_reminder(data.get("employee_ids"), data.get("message"))
    return jsonify({"message": "Sent"})


# =========================
# CONTRACT
# =========================
@manager_bp.route("/contracts/expiring")
def contract_expiring():
    data = ManagerService.get_contract_expiring(g.employee.id)
    return jsonify([c.contract_code for c in data])


@manager_bp.route("/contracts/renew", methods=["POST"])
def renew_contract():
    data = request.json
    contract = ManagerService.renew_contract(data)
    return jsonify({"id": contract.id})


# =========================
# SALARY
# =========================
@manager_bp.route("/salary")
def salary():
    month = int(request.args.get("month"))
    year = int(request.args.get("year"))

    data = ManagerService.get_department_salary(g.employee.id, month, year)
    return jsonify([s.id for s in data])