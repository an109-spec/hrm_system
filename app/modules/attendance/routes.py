from flask import render_template, request, session, redirect, url_for, jsonify
from datetime import datetime
from app.extensions import db

from . import attendance_bp
from .service import AttendanceService
from app.common.exceptions import ValidationError

def _get_current_employee():
    user_id = session.get("user_id")
    if not user_id:
        return None, jsonify({
            "status": "error",
            "message": "Bạn chưa đăng nhập"
        }), 401

    from app.models import Employee

    employee = Employee.query.filter_by(user_id=user_id).first()
    if not employee:
        return None, jsonify({
            "status": "error",
            "message": "Không tìm thấy nhân viên"
        }), 404

    return employee, None, None


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

@attendance_bp.route("/check", methods=["POST"])
def check_in():
    employee, error_response, status_code = _get_current_employee()
    if error_response:
        return error_response, status_code

    data = request.get_json() or {}
    simulated_now = data.get("simulated_now") or session.get("simulated_now")
    if simulated_now:
        session["simulated_now"] = simulated_now

    try:
        result = AttendanceService.check_in(
            employee.id,
            simulated_now,
            bool(data.get("confirm_work_on_offday", False))
        )
        action = result.get("action")
        is_prompt = action in {"holiday_work_prompt", "weekend_work_prompt"}
        response_type = "warning" if is_prompt else "success"
        return jsonify({
            "status": "success",
            "type": response_type,
            **result
        })
    except ValidationError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}), 500


@attendance_bp.route("/check-out", methods=["POST"])
def check_out():
    employee, error_response, status_code = _get_current_employee()
    if error_response:
        return error_response, status_code

    data = request.get_json() or {}
    simulated_now = data.get("simulated_now") or session.get("simulated_now")

    try:
        result = AttendanceService.check_out_regular(employee.id, simulated_now)
        return jsonify({
            "status": "success",
            "type": "success",
            "action": "check_out",
            **result
        })
    except ValidationError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}), 500


@attendance_bp.route("/today", methods=["GET"])
def get_today():
    employee, error_response, status_code = _get_current_employee()
    if error_response:
        return error_response, status_code

    simulated_now = request.args.get("simulated_now") or session.get("simulated_now")

    try:
        today = AttendanceService.get_today(employee.id, simulated_now)
        return jsonify({"status": "success", "data": today.to_dict() if today else None})
    except ValidationError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@attendance_bp.route("/history", methods=["GET"])
def history():
    employee, error_response, status_code = _get_current_employee()
    if error_response:
        return error_response, status_code

    simulated_now = request.args.get("simulated_now") or session.get("simulated_now")

    try:
        records = AttendanceService.get_history(employee.id, simulated_now)
        return jsonify({"status": "success", "data": [record.to_dict() for record in records]})
    except ValidationError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@attendance_bp.route("/", methods=["DELETE"])
def delete_attendance():
    employee, error_response, status_code = _get_current_employee()
    if error_response:
        return error_response, status_code
    data = request.get_json() or {}
    date_str = data.get("date") 

    if not date_str:
        return jsonify({
            "status": "error",
            "message": "Thiếu ngày cần xóa"
        }), 400

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
            "rollback_date": rollback_date
        })

    except ValidationError as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Lỗi hệ thống: {str(e)}",
        }), 500