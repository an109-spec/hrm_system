from flask import render_template, request, session, redirect, url_for, jsonify
from datetime import datetime
from app.extensions import db

from . import attendance_bp
from .service import AttendanceService
from app.common.exceptions import ValidationError


def _get_current_employee():
    user_id = session.get("user_id")
    if not user_id:
        return None, _error_response("Bạn chưa đăng nhập", status_code=401, error_code="UNAUTHORIZED")

    from app.models import Employee

    employee = Employee.query.filter_by(user_id=user_id).first()
    if not employee:
        return None, _error_response("Không tìm thấy nhân viên", status_code=404, error_code="EMPLOYEE_NOT_FOUND")

    return employee, None

def _success_response(data=None, message=None, action=None, response_type="success", status_code=200):
    payload = {
        "status": "success",
        "type": response_type,
    }
    if message is not None:
        payload["message"] = message
    if action is not None:
        payload["action"] = action
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status_code


def _error_response(message, status_code=400, error_code="VALIDATION_ERROR"):
    return jsonify({
        "status": "error",
        "type": "error",
        "error_code": error_code,
        "message": message,
    }), status_code


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
    today = AttendanceService.get_today(employee.id, simulated_now)
    history = AttendanceService.get_history(employee.id, simulated_now)

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
    employee, error = _get_current_employee()
    if error:
        return error

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
        response_type = "warning" if action in {
            AttendanceService.ACTION_HOLIDAY_WORK_PROMPT,
            AttendanceService.ACTION_WEEKEND_WORK_PROMPT,
        } else "success"

        return _success_response(
            data=result,
            message=result.get("message"),
            action=action,
            response_type=response_type,
            status_code=200,
        )
    except ValidationError as e:
        return _error_response(str(e), status_code=400, error_code="ATTENDANCE_VALIDATION_FAILED")
    except Exception as e:
        db.session.rollback()
        return _error_response(f"Lỗi hệ thống: {str(e)}", status_code=500, error_code="ATTENDANCE_CHECKIN_FAILED")


@attendance_bp.route("/check-out", methods=["POST"])
def check_out():
    employee, error = _get_current_employee()
    if error:
        return error

    data = request.get_json() or {}
    simulated_now = data.get("simulated_now") or session.get("simulated_now")

    try:
        result = AttendanceService.check_out_regular(employee.id, simulated_now)
        return _success_response(
            data=result,
            message=result.get("message"),
            action=result.get("action", AttendanceService.ACTION_CHECK_OUT),
            response_type="success",
            status_code=200,
        )
    except ValidationError as e:
        return _error_response(str(e), status_code=400, error_code="ATTENDANCE_CHECKOUT_INVALID")
    except Exception as e:
        db.session.rollback()
        return _error_response(f"Lỗi hệ thống: {str(e)}", status_code=500, error_code="ATTENDANCE_CHECKOUT_FAILED")


@attendance_bp.route("/today", methods=["GET"])
def get_today():
    employee, error = _get_current_employee()
    if error:
        return error

    simulated_now = request.args.get("simulated_now") or session.get("simulated_now")

    try:
        today = AttendanceService.get_today(employee.id, simulated_now)
        return _success_response(data=today.to_dict() if today else None, response_type="success")
    except ValidationError as e:
        return _error_response(str(e), status_code=400, error_code="ATTENDANCE_TODAY_INVALID")


@attendance_bp.route("/history", methods=["GET"])
def history():
    employee, error = _get_current_employee()
    if error:
        return error

    simulated_now = request.args.get("simulated_now") or session.get("simulated_now")

    try:
        records = AttendanceService.get_history(employee.id, simulated_now)
        return _success_response(data=[record.to_dict() for record in records], response_type="success")
    except ValidationError as e:
        return _error_response(str(e), status_code=400, error_code="ATTENDANCE_HISTORY_INVALID")


@attendance_bp.route("/", methods=["DELETE"])
def delete_attendance():
    employee, error = _get_current_employee()
    if error:
        return error

    data = request.get_json() or {}
    date_str = data.get("date")

    if not date_str:
        return _error_response("Thiếu ngày cần xóa", status_code=400, error_code="ATTENDANCE_DATE_REQUIRED")

    try:
        new_last_date = AttendanceService.delete_attendance(employee.id, date_str)
        session.pop("simulated_now", None)
        rollback_date = new_last_date.isoformat() if new_last_date else datetime.now().date().isoformat()

        return _success_response(
            data={"rollback_date": rollback_date, "deleted_date": date_str},
            message=f"Đã xóa chấm công ngày {date_str}",
            action="delete_attendance",
            response_type="success",
            status_code=200,
        )
    except ValidationError as e:
        return _error_response(str(e), status_code=400, error_code="ATTENDANCE_DELETE_INVALID")
    except Exception as e:
        db.session.rollback()
        return _error_response(f"Lỗi hệ thống: {str(e)}", status_code=500, error_code="ATTENDANCE_DELETE_FAILED")