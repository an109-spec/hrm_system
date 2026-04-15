from flask import request, jsonify
from flask_login import login_required, current_user

from . import leave_bp
from .service import LeaveService
from .dto import LeaveRequestDTO
from app.models.employee import Employee


# =========================
# GET LEAVE BALANCE
# =========================
@leave_bp.route("/balance", methods=["GET"])
@login_required
def get_balance():
    emp = Employee.query.filter_by(user_id=current_user.id).first()

    if not emp:
        return jsonify({"error": "Employee not found"}), 404

    usage = LeaveService.get_leave_balance(emp.id)

    return jsonify({
        "employee_id": emp.id,
        "total_days": usage.total_days if usage else 0,
        "used_days": usage.used_days if usage else 0,
        "remaining_days": usage.remaining_days if usage else 0,
    })


# =========================
# CREATE LEAVE REQUEST
# =========================
@leave_bp.route("/", methods=["POST"])
@login_required
def create_leave():
    emp = Employee.query.filter_by(user_id=current_user.id).first()

    data = request.json

    dto = LeaveRequestDTO(
        employee_id=emp.id,
        leave_type_id=data["leave_type_id"],
        from_date=data["from_date"],
        to_date=data["to_date"],
        reason=data["reason"],
        approved_by=emp.manager_id
    )

    leave = LeaveService.create_leave_request(dto)

    return jsonify({
        "id": leave.id,
        "status": leave.status,
        "message": "Leave request created"
    })


# =========================
# MY LEAVE REQUESTS
# =========================
@leave_bp.route("/my", methods=["GET"])
@login_required
def my_requests():
    emp = Employee.query.filter_by(user_id=current_user.id).first()

    leaves = LeaveService.get_my_requests(emp.id)

    return jsonify([
        {
            "id": l.id,
            "from_date": l.from_date.isoformat(),
            "to_date": l.to_date.isoformat(),
            "status": l.status,
            "reason": l.reason,
            "created_at": l.created_at.isoformat()
        }
        for l in leaves
    ])


# =========================
# CANCEL REQUEST
# =========================
@leave_bp.route("/<int:leave_id>/cancel", methods=["POST"])
@login_required
def cancel_leave(leave_id):
    emp = Employee.query.filter_by(user_id=current_user.id).first()

    leave = LeaveService.cancel_request(leave_id, emp.id)

    return jsonify({
        "id": leave.id,
        "status": "cancelled"
    })