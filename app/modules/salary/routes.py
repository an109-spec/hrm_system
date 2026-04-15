from flask import request, jsonify
from flask_login import login_required, current_user

from . import salary_bp
from .service import SalaryService
from .complaint_service import SalaryComplaintService
from app.models.employee import Employee


# =========================
# GET SALARY LIST (UI TABLE)
# =========================
@salary_bp.route("/", methods=["GET"])
@login_required
def get_salaries():
    year = int(request.args.get("year", 2026))

    emp = Employee.query.filter_by(user_id=current_user.id).first()

    data = SalaryService.get_by_employee(emp.id, year)

    return jsonify([
        {
            "id": s.id,
            "month": s.month,
            "year": s.year,
            "basic_salary": float(s.basic_salary),
            "total_work_days": float(s.total_work_days),
            "net_salary": float(s.net_salary),
            "status": s.status
        }
        for s in data
    ])


# =========================
# PAYSLIP DETAIL
# =========================
@salary_bp.route("/<int:salary_id>", methods=["GET"])
@login_required
def detail(salary_id):
    salary = SalaryService.get_detail(salary_id)

    if not salary:
        return jsonify({"error": "Not found"}), 404

    return jsonify({
        "id": salary.id,
        "employee": salary.employee.full_name,
        "basic_salary": float(salary.basic_salary),
        "net_salary": float(salary.net_salary),
        "allowance": float(salary.total_allowance),
        "bonus": float(salary.bonus),
        "penalty": float(salary.penalty),
        "status": salary.status
    })


# =========================
# CREATE COMPLAINT (UI FORM)
# =========================
@salary_bp.route("/complaint", methods=["POST"])
@login_required
def create_complaint():
    emp = Employee.query.filter_by(user_id=current_user.id).first()
    data = request.json

    try:
        complaint = SalaryComplaintService.create(
            employee_id=emp.id,
            salary_id=data["salary_id"],
            type=data["type"],
            description=data["description"],
            evidence_url=data.get("evidence_url")
        )

        return jsonify({
            "id": complaint.id,
            "status": complaint.status
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# =========================
# LIST COMPLAINTS
# =========================
@salary_bp.route("/complaint/my", methods=["GET"])
@login_required
def my_complaints():
    emp = Employee.query.filter_by(user_id=current_user.id).first()

    data = SalaryComplaintService.get_by_employee(emp.id)

    return jsonify([
        {
            "id": c.id,
            "title": c.title,
            "status": c.status,
            "created_at": c.created_at.isoformat()
        }
        for c in data
    ])


# =========================
# UPDATE STATUS (HR ONLY)
# =========================
@salary_bp.route("/complaint/<int:cid>/status", methods=["PUT"])
@login_required
def update_complaint(cid):
    data = request.json

    try:
        c = SalaryComplaintService.update_status(cid, data["status"])

        return jsonify({
            "id": c.id,
            "status": c.status
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400