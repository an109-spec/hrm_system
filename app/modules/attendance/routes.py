from flask import render_template, session, redirect, url_for, jsonify
from datetime import datetime

from . import attendance_bp
from .service import AttendanceService


# =============================
# PAGE
# =============================
@attendance_bp.route("/")
def attendance_page():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    from app.models import Employee

    employee = Employee.query.filter_by(user_id=user_id).first()

    today = AttendanceService.get_today(employee.id)
    history = AttendanceService.get_history(employee.id)

    return render_template(
        "employee/attendance.html",
        today=today,
        history=history,
        now=datetime.now()
    )


# =============================
# CHECK IN / OUT API
# =============================
@attendance_bp.route("/check", methods=["POST"])
def check_in_out():
    user_id = session.get("user_id")

    from app.models import Employee
    employee = Employee.query.filter_by(user_id=user_id).first()

    result = AttendanceService.check_in_out(employee.id)

    return jsonify(result)