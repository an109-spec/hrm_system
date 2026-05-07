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
        "type":   response_type,
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
        "status":     "error",
        "type":       "error",
        "error_code": error_code,
        "message":    message,
    }), status_code


# ══════════════════════════════════════════════════════════════════════════════
# PAGE
# ══════════════════════════════════════════════════════════════════════════════

@attendance_bp.route("/")
def attendance_page():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    from app.models import Employee, OvertimeRequest
    employee = Employee.query.filter_by(user_id=user_id).first()

    simulated_now = request.args.get("simulated_now") or session.get("simulated_now")

    if simulated_now:
        now = datetime.fromisoformat(simulated_now.replace("Z", "+00:00"))
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        session["simulated_now"] = simulated_now
    else:
        now = datetime.now()

    selected_month = request.args.get("month", type=int) or now.month
    selected_year  = request.args.get("year",  type=int) or now.year

    today   = AttendanceService.get_today(employee.id, simulated_now)
    history = AttendanceService.get_history(
        employee.id, simulated_now,
        month=selected_month, year=selected_year,
    )

    for a in history:
        if a.check_in and a.check_out:
            a.calculated_hours = AttendanceService.recalculate_hours(a.check_in, a.check_out)

    return render_template(
        "employee/attendance.html",
        employee=employee,
        today=today,
        history=history,
        now=now,
        selected_month=selected_month,
        selected_year=selected_year,
    )


# ══════════════════════════════════════════════════════════════════════════════
# CHECK-IN
# ══════════════════════════════════════════════════════════════════════════════

@attendance_bp.route("/check", methods=["POST"])
def check_in():
    employee, error = _get_current_employee()
    if error:
        return error

    data          = request.get_json() or {}
    simulated_now = data.get("simulated_now") or session.get("simulated_now")
    if simulated_now:
        session["simulated_now"] = simulated_now

    try:
        result        = AttendanceService.check_in(
            employee.id,
            simulated_now,
            bool(data.get("confirm_work_on_offday", False)),
        )
        action        = result.get("action")
        response_type = "warning" if action in {
            AttendanceService.ACTION_HOLIDAY_WORK_PROMPT,
            AttendanceService.ACTION_WEEKEND_WORK_PROMPT,
        } else "success"

        return _success_response(
            data=result,
            message=result.get("message"),
            action=action,
            response_type=response_type,
        )
    except ValidationError as e:
        return _error_response(str(e), status_code=400, error_code="ATTENDANCE_VALIDATION_FAILED")
    except Exception as e:
        db.session.rollback()
        return _error_response(f"Lỗi hệ thống: {str(e)}", status_code=500, error_code="ATTENDANCE_CHECKIN_FAILED")


# ══════════════════════════════════════════════════════════════════════════════
# CHECK-OUT
# ══════════════════════════════════════════════════════════════════════════════

@attendance_bp.route("/check-out", methods=["POST"])
def check_out():
    employee, error = _get_current_employee()
    if error:
        return error

    data          = request.get_json() or {}
    simulated_now = data.get("simulated_now") or session.get("simulated_now")

    try:
        result = AttendanceService.check_out_regular(employee.id, simulated_now)
        return _success_response(
            data=result,
            message=result.get("message"),
            action=result.get("action", AttendanceService.ACTION_CHECK_OUT),
        )
    except ValidationError as e:
        return _error_response(str(e), status_code=400, error_code="ATTENDANCE_CHECKOUT_INVALID")
    except Exception as e:
        db.session.rollback()
        return _error_response(f"Lỗi hệ thống: {str(e)}", status_code=500, error_code="ATTENDANCE_CHECKOUT_FAILED")


# ══════════════════════════════════════════════════════════════════════════════
# TODAY / HISTORY / DELETE  (không đổi logic)
# ══════════════════════════════════════════════════════════════════════════════

@attendance_bp.route("/today", methods=["GET"])
def get_today():
    employee, error = _get_current_employee()
    if error:
        return error

    simulated_now = request.args.get("simulated_now") or session.get("simulated_now")
    try:
        today = AttendanceService.get_today(employee.id, simulated_now)
        return _success_response(data=today.to_dict() if today else None)
    except ValidationError as e:
        return _error_response(str(e), status_code=400)


@attendance_bp.route("/history", methods=["GET"])
def history():
    employee, error = _get_current_employee()
    if error:
        return error

    simulated_now = request.args.get("simulated_now") or session.get("simulated_now")
    try:
        records = AttendanceService.get_history(employee.id, simulated_now)
        return _success_response(data=[r.to_dict() for r in records])
    except ValidationError as e:
        return _error_response(str(e), status_code=400)


@attendance_bp.route("/", methods=["DELETE"])
def delete_attendance():
    employee, error = _get_current_employee()
    if error:
        return error

    data     = request.get_json() or {}
    date_str = data.get("date")
    if not date_str:
        return _error_response("Thiếu ngày cần xóa", status_code=400)

    try:
        new_last_date = AttendanceService.delete_attendance(employee.id, date_str)
        session.pop("simulated_now", None)
        rollback_date = new_last_date.isoformat() if new_last_date else datetime.now().date().isoformat()
        return _success_response(
            data={"rollback_date": rollback_date, "deleted_date": date_str},
            message=f"Đã xóa chấm công ngày {date_str}",
            action="delete_attendance",
        )
    except ValidationError as e:
        return _error_response(str(e), status_code=400)
    except Exception as e:
        db.session.rollback()
        return _error_response(f"Lỗi hệ thống: {str(e)}", status_code=500)


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION CASCADE DELETE
# ══════════════════════════════════════════════════════════════════════════════

@attendance_bp.route("/notifications/<int:noti_id>", methods=["DELETE"])
def delete_notification(noti_id: int):
    """
    Xóa notification và cascade theo type:
    - overtime  → xóa linked OT request, reset overtime trên attendance
    - attendance → chỉ xóa notification
    """
    user_id = session.get("user_id")
    if not user_id:
        return _error_response("Unauthorized", status_code=401)

    try:
        result = AttendanceService.delete_notification_cascade(noti_id, user_id)
        return _success_response(
            data=result,
            message="Đã xóa thông báo",
            action="delete_notification",
        )
    except ValidationError as e:
        return _error_response(str(e), status_code=404)
    except Exception as e:
        db.session.rollback()
        return _error_response(f"Lỗi hệ thống: {str(e)}", status_code=500)


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM TIME  ← FIXED: dùng compute_attendance_state() thật
# ══════════════════════════════════════════════════════════════════════════════

@attendance_bp.route("/system-time", methods=["GET", "POST"])
def system_time():
    """
    GET:  Trả state hiện tại theo giờ thật.
    POST: Đặt simulated_now, trả state theo giờ giả lập.

    KHÔNG còn tính state bằng if/elif — gọi compute_attendance_state() để nhất quán.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    from app.models import Employee, OvertimeRequest
    from app.utils.time import get_current_time

    if request.method == "POST":
        payload       = request.get_json(silent=True) or {}
        now           = get_current_time(payload)
        session["simulated_now"] = now.isoformat()
        mode          = "SIMULATED"
    else:
        now  = get_current_time({})
        mode = "SIMULATED" if session.get("simulated_now") else "REAL"

    employee = Employee.query.filter_by(user_id=user_id).first()
    attendance = None
    ot_request = None
    if employee:
        attendance = AttendanceService.get_today(employee.id, now.isoformat())
        ot_request = OvertimeRequest.query.filter_by(
            employee_id=employee.id,
            overtime_date=now.date(),
            is_deleted=False,
        ).order_by(OvertimeRequest.id.desc()).first()

    # ── Single source of truth ────────────────────────────────────────────
    state_result = AttendanceService.compute_attendance_state(now, attendance, ot_request)

    # Tính giờ công demo để FE hiển thị
    att_payload = AttendanceService.build_attendance_payload(attendance) if attendance else {}
    regular_hours  = float(att_payload.get("regular_hours", 0) or 0) if att_payload else 0.0
    overtime_hours = float(att_payload.get("overtime_hours", 0) or 0) if att_payload else 0.0

    return jsonify({
        "mode":             mode,
        "current_time":     now.isoformat(),
        "attendance_state": state_result.state,
        "button_enabled":   state_result.button_enabled,
        "button_text":      state_result.button_text,
        "can_scan":         state_result.can_scan,
        "message":          state_result.message,
        "overtime_status":  state_result.overtime_status,
        "regular_hours":    regular_hours,
        "overtime_hours":   overtime_hours,
        # Backward compat
        "can_check_in":     state_result.state == "not_started",
        "can_check_out":    state_result.state == "working_regular" and state_result.button_enabled,
    })