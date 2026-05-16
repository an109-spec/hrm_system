from flask import render_template, request, session, redirect, url_for, jsonify
from datetime import datetime
from app.extensions import db

from . import attendance_bp
from .service import AttendanceService
from app.common.exceptions import ValidationError
from decimal import Decimal
from app.models import Employee

from app.modules.attendance.service import (
    AttendanceService,
)
from app.utils.time import (
    VN_TIMEZONE,
    set_simulated_time,
    reset_simulated_time,
    get_current_time,
)

def _get_current_employee():
    user_id = session.get("user_id")
    if not user_id:
        return None, _error_response("Bạn chưa đăng nhập", status_code=401, error_code="UNAUTHORIZED")
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

@attendance_bp.route("/")
def attendance_page():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(
            url_for("auth.login")
        )
    employee = Employee.query.filter_by(
        user_id=user_id
    ).first()
    if not employee:
        return redirect(
            url_for("auth.login")
        )
    simulated_now = request.args.get(
        "simulated_now"
    )
    if simulated_now:

        try:
            sim_dt = datetime.fromisoformat(
                simulated_now.replace(
                    "Z",
                    "+00:00",
                )
            )
            if sim_dt.tzinfo is None:
                sim_dt = sim_dt.replace(
                    tzinfo=VN_TIMEZONE
                )
            else:
                sim_dt = sim_dt.astimezone(
                    VN_TIMEZONE
                )
            set_simulated_time(sim_dt)
        except ValueError:
            pass
    now = get_current_time()
    selected_month = (
        request.args.get(
            "month",
            type=int,
        )
        or now.month
    )
    selected_year = (
        request.args.get(
            "year",
            type=int,
        )
        or now.year
    )
    today = AttendanceService.get_today(
        employee.id,
        now.isoformat(),
    )
    history = AttendanceService.get_history(
        employee.id,
        now.isoformat(),
        month=selected_month,
        year=selected_year,
    )
    for attendance in history:
        if (
            attendance.check_in
            and attendance.check_out
        ):
            attendance.calculated_hours = (
                AttendanceService.recalculate_hours(
                    attendance
                )
            )
        else:
            attendance.calculated_hours = (
                Decimal("0.00")
            )
    return render_template(
        "employee/attendance.html",
        employee=employee,
        today=today,
        history=history,
        now=now,
        selected_month=selected_month,
        selected_year=selected_year,
    )

@attendance_bp.route(
    "/check",
    methods=["POST"],
)
def check_in():
    employee, error = _get_current_employee()
    if error:
        return error
    data = request.get_json() or {}
    simulated_now = data.get(
        "simulated_now"
    )
    if simulated_now:
        try:
            sim_dt = datetime.fromisoformat(
                simulated_now.replace(
                    "Z",
                    "+00:00",
                )
            )
            if sim_dt.tzinfo is None:

                sim_dt = sim_dt.replace(
                    tzinfo=VN_TIMEZONE
                )
            else:
                sim_dt = sim_dt.astimezone(
                    VN_TIMEZONE
                )
            set_simulated_time(sim_dt)
        except ValueError:
            return _error_response(
                "Định dạng simulated_now không hợp lệ.",
                status_code=400,
                error_code="INVALID_SIMULATION_TIME",
            )
    try:
        result = AttendanceService.check_in(
            employee_id=employee.id,
            sim_time_str=None,
            confirm_work_on_offday=bool(
                data.get(
                    "confirm_work_on_offday",
                    False,
                )
            ),
        )
        return _success_response(
            data=result,
            message=result.get(
                "message"
            ),
            action=result.get(
                "action"
            ),
            response_type=result.get(
                "type",
                "success",
            ),
        )
    except ValidationError as e:
        return _error_response(
            str(e),
            status_code=400,
            error_code=(
                "ATTENDANCE_VALIDATION_FAILED"
            ),
        )
    except Exception as e:
        db.session.rollback()
        return _error_response(
            f"Lỗi hệ thống: {str(e)}",
            status_code=500,
            error_code=(
                "ATTENDANCE_CHECKIN_FAILED"
            ),
        )
@attendance_bp.route(
    "/check-out",
    methods=["POST"],
)
def check_out():
    employee, error = _get_current_employee()
    if error:
        return error
    data = request.get_json() or {}
    simulated_now = data.get(
        "simulated_now"
    )
    if simulated_now:
        try:
            sim_dt = datetime.fromisoformat(
                simulated_now.replace(
                    "Z",
                    "+00:00",
                )
            )
            if sim_dt.tzinfo is None:
                sim_dt = sim_dt.replace(
                    tzinfo=VN_TIMEZONE
                )
            else:
                sim_dt = sim_dt.astimezone(
                    VN_TIMEZONE
                )
            set_simulated_time(sim_dt)
        except ValueError:
            return _error_response(
                "Định dạng simulated_now không hợp lệ.",
                status_code=400,
                error_code=(
                    "INVALID_SIMULATION_TIME"
                ),
            )
    try:
        result = (
            AttendanceService.check_out_regular(
                employee_id=employee.id,
                sim_time_str=None,
                early_checkout=bool(
                    data.get(
                        "early_checkout",
                        False,
                    )
                ),
            )
        )
        return _success_response(
            data=result,
            message=result.get(
                "message"
            ),
            action=result.get(
                "action",
                AttendanceService.ACTION_CHECK_OUT,
            ),
            response_type=result.get(
                "type",
                "success",
            ),
        )
    except ValidationError as e:
        return _error_response(
            str(e),
            status_code=400,
            error_code=(
                "ATTENDANCE_CHECKOUT_INVALID"
            ),
        )
    except Exception as e:
        db.session.rollback()
        return _error_response(
            f"Lỗi hệ thống: {str(e)}",
            status_code=500,
            error_code=(
                "ATTENDANCE_CHECKOUT_FAILED"
            ),
        )

@attendance_bp.route(
    "/today",
    methods=["GET"],
)
def get_today():
    employee, error = _get_current_employee()
    if error:
        return error
    simulated_now = request.args.get(
        "simulated_now"
    )
    if simulated_now:
        try:
            sim_dt = datetime.fromisoformat(
                simulated_now.replace(
                    "Z",
                    "+00:00",
                )
            )
            if sim_dt.tzinfo is None:
                sim_dt = sim_dt.replace(
                    tzinfo=VN_TIMEZONE
                )
            else:
                sim_dt = sim_dt.astimezone(
                    VN_TIMEZONE
                )
            set_simulated_time(sim_dt)
        except ValueError:
            return _error_response(
                "Định dạng simulated_now không hợp lệ.",
                status_code=400,
                error_code=(
                    "INVALID_SIMULATION_TIME"
                ),
            )
    try:
        today = AttendanceService.get_today(
            employee.id,
            sim_time_str=None,
        )
        return _success_response(
            data=(
                today.to_dict()
                if today
                else None
            )
        )
    except ValidationError as e:
        return _error_response(
            str(e),
            status_code=400,
        )
    except Exception as e:
        return _error_response(
            f"Lỗi hệ thống: {str(e)}",
            status_code=500,
        )

@attendance_bp.route(
    "/history",
    methods=["GET"],
)
def history():
    employee, error = _get_current_employee()
    if error:
        return error
    simulated_now = request.args.get(
        "simulated_now"
    )
    if simulated_now:
        try:
            sim_dt = datetime.fromisoformat(
                simulated_now.replace(
                    "Z",
                    "+00:00",
                )
            )
            if sim_dt.tzinfo is None:
                sim_dt = sim_dt.replace(
                    tzinfo=VN_TIMEZONE
                )
            else:
                sim_dt = sim_dt.astimezone(
                    VN_TIMEZONE
                )
            set_simulated_time(sim_dt)
        except ValueError:
            return _error_response(
                "Định dạng simulated_now không hợp lệ.",
                status_code=400,
                error_code=(
                    "INVALID_SIMULATION_TIME"
                ),
            )
    month = request.args.get(
        "month",
        type=int,
    )
    year = request.args.get(
        "year",
        type=int,
    )
    try:
        records = AttendanceService.get_history(
            employee_id=employee.id,
            sim_time_str=None,
            month=month,
            year=year,
        )
        serialized = []
        for r in records:
            if hasattr(r, "to_dict"):
                serialized.append(
                    r.to_dict()
                )
            else:
                serialized.append({
                    "id": r.id,
                    "date": (
                        r.date.isoformat()
                        if r.date
                        else None
                    ),
                    "check_in": (
                        r.check_in.isoformat()
                        if r.check_in
                        else None
                    ),
                    "check_out": (
                        r.check_out.isoformat()
                        if r.check_out
                        else None
                    ),
                    "regular_hours": str(
                        r.regular_hours
                    ),
                    "overtime_hours": str(
                        r.overtime_hours
                    ),
                    "working_hours": str(
                        r.working_hours
                    ),
                    "shift_status": (
                        r.shift_status
                    ),
                    "attendance_type": (
                        r.attendance_type
                    ),
                    "late_minutes": (
                        r.late_minutes
                    ),
                    "is_half_day": (
                        r.is_half_day
                    ),
                    "is_weekend": (
                        r.is_weekend
                    ),
                    "is_holiday": (
                        r.is_holiday
                    ),
                })
        return _success_response(
            data=serialized
        )
    except ValidationError as e:
        return _error_response(
            str(e),
            status_code=400,
        )
    except Exception as e:
        return _error_response(
            f"Lỗi hệ thống: {str(e)}",
            status_code=500,
        )

@attendance_bp.route("/delete", methods=["DELETE"])
def delete_attendance():
    employee, error = _get_current_employee()
    if error:
        return error
    data = request.get_json() or {}
    date_str = data.get("date")
    if not date_str:
        return _error_response(
            "Thiếu ngày cần xóa",
            status_code=400,
        )
    try:
        new_last_date = AttendanceService.delete_attendance(
            employee.id,
            date_str,
        )
        from datetime import datetime, time as dt_time
        if new_last_date:
            rollback_dt = datetime.combine(
                new_last_date,
                dt_time.min,
            ).replace(
                tzinfo=VN_TIMEZONE
            )
            set_simulated_time(
                rollback_dt,
                speed=1,
            )
            rollback_date = (
                rollback_dt.date().isoformat()
            )
        else:
            reset_simulated_time()
            rollback_date = (
                get_current_time()
                .date()
                .isoformat()
            )
        return _success_response(
            data={
                "rollback_date": rollback_date,
                "deleted_date": date_str,
            },
            message=(
                f"Đã xóa chấm công ngày {date_str}"
            ),
            action="delete_attendance",
        )
    except ValidationError as e:
        return _error_response(
            str(e),
            status_code=400,
        )
    except Exception as e:
        db.session.rollback()
        return _error_response(
            f"Lỗi hệ thống: {str(e)}",
            status_code=500,
        )
    
@attendance_bp.route("/notifications/<int:noti_id>", methods=["DELETE"])
def delete_notification(noti_id: int):
    user_id = session.get("user_id")

    if not user_id:
        return _error_response(
            "Unauthorized",
            status_code=401,
            error_code="UNAUTHORIZED",
        )

    try:
        result = AttendanceService.delete_notification_cascade(
            notification_id=noti_id,
            user_id=user_id,
        )

        return _success_response(
            data=result,
            message="Đã xóa thông báo",
            action="delete_notification",
        )

    except ValidationError as e:
        return _error_response(
            str(e),
            status_code=404,
            error_code="NOTIFICATION_NOT_FOUND",
        )

    except Exception as e:
        db.session.rollback()

        return _error_response(
            f"Lỗi hệ thống: {str(e)}",
            status_code=500,
            error_code="DELETE_NOTIFICATION_FAILED",
        )

@attendance_bp.route("/system-time", methods=["GET", "POST"])
def system_time():

    from app.models import (
        Employee,
        Attendance,
        OvertimeRequest,
    )

    from app.utils.time import (
        get_current_time,
        set_simulated_time,
        is_simulation_mode,
        reset_simulated_time,
    )

    user_id = session.get("user_id")

    if not user_id:
        return _error_response(
            "Unauthorized",
            status_code=401,
            error_code="UNAUTHORIZED",
        )

    # =====================================================
    # HANDLE POST (SET SIMULATION TIME)
    # =====================================================
    if request.method == "POST":

        payload = request.get_json(silent=True) or {}

        simulated_now = payload.get("simulated_now")
        speed = float(payload.get("speed", 1))

        # RESET SIMULATION
        if not simulated_now:

            reset_simulated_time()

        else:

            try:

                sim_dt = datetime.fromisoformat(
                    simulated_now.replace("Z", "+00:00")
                )

                set_simulated_time(
                    sim_dt,
                    speed=speed,
                )

            except ValueError:

                return _error_response(
                    "Thời gian mô phỏng không hợp lệ",
                    status_code=400,
                    error_code="INVALID_SIMULATION_TIME",
                )

    # =====================================================
    # CURRENT TIME (SINGLE SOURCE OF TRUTH)
    # =====================================================
    now = get_current_time()

    mode = (
        "SIMULATED"
        if is_simulation_mode()
        else "REAL"
    )

    # =====================================================
    # LOAD EMPLOYEE
    # =====================================================
    employee = Employee.query.filter_by(
        user_id=user_id
    ).first()

    attendance = None
    ot_request = None

    if employee:

        attendance = AttendanceService.get_today(
            employee.id,
            now_dt=now,
        )

        ot_request = (
            OvertimeRequest.query.filter_by(
                employee_id=employee.id,
                overtime_date=now.date(),
                is_deleted=False,
            )
            .order_by(
                OvertimeRequest.id.desc()
            )
            .first()
        )

    # =====================================================
    # COMPUTE STATE
    # =====================================================
    state_result = (
        AttendanceService.compute_attendance_state(
            now=now,
            attendance=attendance,
            ot_request=ot_request,
        )
    )

    # =====================================================
    # BUILD PAYLOAD
    # =====================================================
    att_payload = (
        AttendanceService.build_attendance_payload(
            attendance
        )
        if attendance
        else None
    )

    regular_hours = (
        float(att_payload.get("regular_hours", 0))
        if att_payload
        else 0.0
    )

    overtime_hours = (
        float(att_payload.get("overtime_hours", 0))
        if att_payload
        else 0.0
    )

    # =====================================================
    # RESPONSE
    # =====================================================
    return jsonify({

        "mode": mode,

        "current_time": now.isoformat(),

        "attendance_state": state_result.state,

        "button_enabled": (
            state_result.button_enabled
        ),

        "button_text": (
            state_result.button_text
        ),

        "can_scan": (
            state_result.can_scan
        ),

        "message": (
            state_result.message
        ),

        "overtime_status": (
            state_result.overtime_status
        ),

        "regular_hours": regular_hours,

        "overtime_hours": overtime_hours,

        "attendance": att_payload,

        "can_check_in": (
            state_result.state
            == Attendance.ShiftStatus.NOT_STARTED
        ),

        "can_check_out": (
            state_result.state in {
                Attendance.ShiftStatus.WORKING_REGULAR,
                Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED,
            }
        ),

        "can_checkin_ot": (
            state_result.state
            == Attendance.ShiftStatus.OT_CHECKIN_REQUIRED
        ),

        "can_checkout_ot": (
            state_result.state
            == Attendance.ShiftStatus.WORKING_OVERTIME
        ),
    })