from flask import render_template, request, session, redirect, url_for, jsonify
from datetime import datetime
from app.extensions import db
from app.modules import employee

from . import attendance_bp
from .service import AttendanceService
from app.common.exceptions import ValidationError

@attendance_bp.route("/")
def attendance_page(): 
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    from app.models import Employee

    employee = Employee.query.filter_by(user_id=user_id).first()

    simulated_now = request.args.get("simulated_now") or session.get("simulated_now")

    if simulated_now:
        now = datetime.fromisoformat(simulated_now.replace("Z", "+00:00"))
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)

        session["simulated_now"] = simulated_now
    else:
        now = datetime.now()

    today = AttendanceService.get_today(employee.id)
    history = AttendanceService.get_history(employee.id)

    for a in history:
        if a.check_in and a.check_out:
            a.calculated_hours = AttendanceService.recalculate_hours(a.check_in, a.check_out)

    return render_template(
        "employee/attendance.html",
        employee=employee,
        today=today,
        history=history,
        now=now
    )

@attendance_bp.route("/delete", methods=["DELETE"])
def delete_attendance():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Bạn chưa đăng nhập",
            "toast": True
        }), 401

    data = request.get_json() or {}
    date_str = data.get("date") 

    if not date_str:
        return jsonify({
            "status": "error",
            "message": "Thiếu ngày cần xóa",
            "toast": True
        }), 400

    from app.models import Employee
    employee = Employee.query.filter_by(user_id=user_id).first()
    if not employee:
        return jsonify({ 
            "status": "error",
            "message": "Không tìm thấy nhân viên",
            "toast": True
        }), 404
    try:
        new_last_date = AttendanceService.delete_attendance(employee.id, date_str)
        session.pop("simulated_now", None)
        rollback_date = (
            new_last_date.isoformat()
            if new_last_date
            else datetime.now().date().isoformat()
        )

        return jsonify({
            "status": "success",
            "message": f"Đã xóa chấm công ngày {date_str}",
            "toast": True,
            "rollback_date": rollback_date
        })

    except ValidationError as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "toast": True
        }), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Lỗi hệ thống: {str(e)}",
            "toast": True
        }), 500