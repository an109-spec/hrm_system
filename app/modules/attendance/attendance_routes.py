"""
attendance_routes.py
────────────────────
Routes chính của module chấm công.

Route map:
    GET  /attendance/today              → Lấy / tạo bản ghi chấm công hôm nay
    POST /attendance/action             → Xử lý Check-in / Check-out (ca chính & OT)
    POST /attendance/finalize           → Chốt công (Finalize) ngày làm việc
    POST /attendance/auto-complete      → Tự động xử lý các ca quên check-out (Batch/Cronjob)
    POST /attendance/ot/reset-noti      → Hủy đơn OT dựa trên thông báo (khi user xóa noti)
    GET /attendance/api/history         → Lấy dữ liệu lịch sử chấm công (JSON)
"""

from flask import request, g, jsonify
from http import HTTPStatus
from datetime import datetime, date

from app.constants.common import RoleName
from app.common.security.decorators import auth_required, role_required
from app.common.exceptions import ValidationError, ForbiddenError
from app.modules.attendance import attendance_bp
from app.modules.attendance.service import AttendanceService
from app.utils.time import get_current_time, VN_TIMEZONE


# ============================================================
# 🔧 HELPERS
# ============================================================

def _ok(icon: str, title: str, text: str,
        data: dict | None = None,
        timer: int | None = None) -> tuple:
    """Response 200 kèm swal. Tự thêm timer + ẩn nút khi icon=success và có timer."""
    swal = {"icon": icon, "title": title, "text": text}
    if timer:
        swal["timer"] = timer
        swal["showConfirmButton"] = False
    response = {"swal": swal}
    if data is not None:
        response["data"] = data
    return response, HTTPStatus.OK


def _err(icon: str, title: str, text: str, status: int) -> tuple:
    return {"swal": {"icon": icon, "title": title, "text": text}}, status


def _forbidden(msg: str):
    return _err("error", "Không có quyền truy cập", msg, HTTPStatus.FORBIDDEN)


def _not_found(msg: str):
    return _err("warning", "Không tìm thấy", msg, HTTPStatus.NOT_FOUND)


def _bad_request(msg: str):
    return _err("warning", "Dữ liệu không hợp lệ", msg, HTTPStatus.BAD_REQUEST)


def _validation_err(msg: str):
    return _err("warning", "Không thể thực hiện", msg, HTTPStatus.UNPROCESSABLE_ENTITY)


def _wrap_action_result(result: dict) -> tuple:
    """
    Bọc kết quả trả về từ process_employee_action / _handle_* thành response chuẩn.
    Ánh xạ result["type"] → swal icon, tự suy tiêu đề từ result["action"].
    """
    TYPE_TO_ICON = {
        "success": "success",
        "warning": "warning",
        "info":    "info",
        "error":   "error",
    }
    ACTION_TITLES = {
        "check_in":                  "Check-in thành công",
        "check_out":                 "Check-out thành công",
        "check_in_ot":               "Check-in OT thành công",
        "check_out_ot":              "Hoàn thành tăng ca",
        "overtime_request_created":  "Đã gửi yêu cầu OT",
        "complete_without_ot":       "Hoàn thành ngày công",
        "already_recorded":          "Đã ghi nhận",
        "offer_overtime":            "Đăng ký tăng ca?",
        "early_checkout_prompt":     "Tan ca sớm?",
        "holiday_work_prompt":       "Làm việc ngày lễ?",
        "weekend_work_prompt":       "Làm việc cuối tuần?",
        "holiday_off":               "Nghỉ lễ",
        "weekend_off":               "Nghỉ cuối tuần",
        "leave_day":                 "Nghỉ phép",
        "lunch_break":               "Giờ nghỉ trưa",
        "invalid_state":             "Trạng thái không hợp lệ",
        "attendance_not_required":   "Không bắt buộc chấm công",
    }

    result_type = result.get("type", "info")
    icon        = TYPE_TO_ICON.get(result_type, "info")
    action      = str(result.get("action", ""))
    title       = ACTION_TITLES.get(action, "Thông báo hệ thống")
    message     = result.get("message", "")

    needs_confirm = (
        result.get("requires_confirmation")
        or result.get("requires_overtime_decision")
    )

    swal: dict = {"icon": icon, "title": title, "text": message}
    if icon == "success" and not needs_confirm:
        swal["timer"] = 2000
        swal["showConfirmButton"] = False

    return {"swal": swal, **result}, HTTPStatus.OK


def _get_now_from_body(body: dict) -> datetime:
    """
    Lấy thời điểm hiện tại.
    HR/Admin có thể truyền simulate_time để test luồng theo giờ giả lập.
    """
    simulate_time_str = body.get("simulate_time")
    if simulate_time_str:
        user = g.user
        if user.role.name in [RoleName.ADMIN, RoleName.HR]:
            from app.utils.time import _normalize, set_simulated_time
            dt = _normalize(simulate_time_str)
            if dt:
                vn_dt = dt.replace(tzinfo=VN_TIMEZONE) if dt.tzinfo is None else dt.astimezone(VN_TIMEZONE)
                set_simulated_time(vn_dt)
                return vn_dt
    return get_current_time()


# ============================================================
# 1️⃣  GET /attendance/today  — Lấy / tạo bản ghi hôm nay
# ============================================================

@attendance_bp.route("/today", methods=["GET"])
@auth_required
def get_today():
    """
    Lấy bản ghi chấm công hôm nay của nhân viên.
    Nếu chưa tồn tại thì tự động tạo mới (xác định loại ngày: thường/lễ/cuối tuần/nghỉ phép).

    Phân quyền:
        - EMPLOYEE : Chỉ xem chính mình.
        - MANAGER  : Xem nhân viên trong phòng ban mình quản lý.
        - HR/ADMIN : Xem bất kỳ nhân viên nào.

    Query params:
        employee_id (int, optional): HR/Admin/Manager có thể truyền để xem người khác.
    """
    user             = g.user
    current_employee = g.employee
    role             = user.role.name

    requested_employee_id = request.args.get("employee_id", type=int)

    # ── Phân quyền xác định employee cần lấy ─────────────────────────────
    if requested_employee_id and requested_employee_id != current_employee.id:
        if role in [RoleName.ADMIN, RoleName.HR]:
            target_employee_id = requested_employee_id
        elif role == RoleName.MANAGER:
            from app.models.department import Department
            managed_dept = Department.query.filter_by(
                manager_id=current_employee.id, is_deleted=False
            ).first()
            allowed_ids = (
                [e.id for e in managed_dept.employees if not e.is_deleted]
                if managed_dept else [current_employee.id]
            )
            if requested_employee_id not in allowed_ids:
                return _forbidden("Bạn không có quyền xem thông tin nhân viên này")
            target_employee_id = requested_employee_id
        else:
            return _forbidden("Bạn chỉ được xem thông tin của chính mình")
    else:
        target_employee_id = current_employee.id

    now_dt = get_current_time()

    try:
        record = AttendanceService.get_or_create_today(
            employee_id=target_employee_id,
            now_dt=now_dt,
        )
    except ValidationError as e:
        return _validation_err(str(e))
    except Exception as e:
        return _err("error", "Lỗi hệ thống", str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    payload = AttendanceService.build_attendance_payload(record)

    return _ok(
        icon="success",
        title="Dữ liệu chấm công hôm nay",
        text=f"Ngày {now_dt.strftime('%d/%m/%Y')} — Trạng thái: {payload.get('shift_status', '')}",
        data={
            "employee_id": target_employee_id,
            "attendance":  payload,
        },
        timer=1500,
    )


# ============================================================
# 2️⃣  POST /attendance/action  — Check-in / Check-out chính & OT
# ============================================================

@attendance_bp.route("/action", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE, RoleName.MANAGER, RoleName.HR, RoleName.ADMIN)
def process_employee_action():
    """
    Điểm vào chính cho mọi hành động chấm công của nhân viên.
    Backend tự xác định trạng thái hiện tại và xử lý đúng nghiệp vụ.

    Body JSON:
        confirm_work_on_offday   (bool, optional): Xác nhận làm việc ngày lễ/cuối tuần.
        overtime_confirmed       (bool, optional): Alias của confirm_work_on_offday.
        early_checkout_confirmed (bool, optional): Xác nhận tan ca sớm.
        overtime_decision        (str, optional) : "yes" / "no" — quyết định đăng ký OT.
        decline_offday_work      (bool, optional): Xác nhận không đi làm hôm nay.
        simulate_time            (str, optional) : HR/Admin giả lập thời điểm (YYYY-MM-DD HH:MM:SS).
    """
    body        = request.get_json(silent=True) or {}
    employee_id = g.employee.id
    now_dt      = _get_now_from_body(body)

    try:
        result = AttendanceService.process_employee_action(
            employee_id=employee_id,
            payload=body,
            current_time=now_dt,
        )
    except ValidationError as e:
        return _validation_err(str(e))
    except Exception as e:
        return _err("error", "Lỗi hệ thống", str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    return _wrap_action_result(result)


# ============================================================
# 3️⃣  POST /attendance/finalize  — Chốt công ngày làm việc
# ============================================================

@attendance_bp.route("/finalize", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def finalize_attendance():
    """
    Chốt sổ (finalize) bản ghi chấm công của một nhân viên trong ngày cụ thể.
    Tính tổng giờ, đóng gói snapshot, khóa bản ghi.

    Chỉ Admin và HR mới được phép.

    Body JSON:
        employee_id     (int, required) : ID nhân viên cần chốt công.
        attendance_date (str, optional) : Ngày cần finalize YYYY-MM-DD. Mặc định: hôm nay.
        finalize_status (bool, optional): true = Chuyển shift_status → COMPLETED. Mặc định: true.
    """
    body = request.get_json(silent=True) or {}

    # ── Validate employee_id ─────────────────────────────────────────────
    employee_id = body.get("employee_id")
    if not employee_id:
        return _bad_request("Vui lòng cung cấp employee_id")
    try:
        employee_id = int(employee_id)
    except (ValueError, TypeError):
        return _bad_request("employee_id phải là số nguyên")

    # ── Parse ngày ────────────────────────────────────────────────────────
    attendance_date_str = body.get("attendance_date")
    if attendance_date_str:
        try:
            attendance_date = datetime.strptime(attendance_date_str, "%Y-%m-%d").date()
        except ValueError:
            return _bad_request("Định dạng ngày không hợp lệ. Vui lòng dùng YYYY-MM-DD")
    else:
        attendance_date = date.today()

    # ── Tìm bản ghi ──────────────────────────────────────────────────────
    from app.models.attendance import Attendance
    record = Attendance.query.filter_by(
        employee_id=employee_id,
        date=attendance_date,
        is_deleted=False,
    ).first()

    if not record:
        return _not_found(
            f"Không tìm thấy bản ghi chấm công ngày "
            f"{attendance_date.strftime('%d/%m/%Y')} "
            f"của nhân viên #{employee_id}"
        )

    # Không cho phép finalize lại bản ghi đã khóa
    if getattr(record, "is_finalized", False):
        return _ok(
            icon="info",
            title="Đã chốt trước đó",
            text=(
                f"Bản ghi chấm công ngày {attendance_date.strftime('%d/%m/%Y')} "
                f"của nhân viên #{employee_id} đã được chốt sổ trước đó."
            ),
            data={"attendance": AttendanceService.build_attendance_payload(record)},
        )

    finalize_status = bool(body.get("finalize_status", True))

    try:
        AttendanceService.finalize_attendance(
            record=record,
            finalize_status=finalize_status,
        )
        from app.extensions.db import db
        db.session.commit()
    except ValidationError as e:
        return _validation_err(str(e))
    except Exception as e:
        return _err("error", "Lỗi hệ thống", str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    payload = AttendanceService.build_attendance_payload(record)

    return _ok(
        icon="success",
        title="Chốt công thành công",
        text=(
            f"Đã chốt công ngày {attendance_date.strftime('%d/%m/%Y')} "
            f"cho nhân viên #{employee_id}. "
            f"Tổng: {payload.get('working_hours', 0)}h "
            f"(Thường: {payload.get('regular_hours', 0)}h | "
            f"OT: {payload.get('overtime_hours', 0)}h)."
        ),
        data={
            "employee_id":     employee_id,
            "attendance_date": attendance_date.strftime("%Y-%m-%d"),
            "attendance":      payload,
        },
    )


# ============================================================
# 4️⃣  POST /attendance/auto-complete  — Batch xử lý ca quên check-out
# ============================================================

@attendance_bp.route("/auto-complete", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def auto_complete_stale_records():
    """
    Tự động xử lý tất cả các bản ghi chấm công quá hạn chưa được chốt sổ.
    Thường được gọi qua Cronjob cuối ngày hoặc kích hoạt thủ công bởi Admin.

    Chỉ Admin và HR mới được phép.

    Body JSON:
        reference_date (str, optional): Ngày tham chiếu YYYY-MM-DD.
                                        Chỉ xử lý bản ghi TRƯỚC ngày này.
                                        Mặc định: hôm nay.
    """
    body = request.get_json(silent=True) or {}

    reference_date_str = body.get("reference_date")
    if reference_date_str:
        try:
            reference_date = datetime.strptime(reference_date_str, "%Y-%m-%d").date()
        except ValueError:
            return _bad_request("Định dạng ngày không hợp lệ. Vui lòng dùng YYYY-MM-DD")
    else:
        reference_date = None  # Service sẽ dùng date.today()

    try:
        count = AttendanceService.auto_complete_stale_records(
            reference_date=reference_date,
        )
    except Exception as e:
        return _err("error", "Lỗi hệ thống", str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    if count == 0:
        return _ok(
            icon="info",
            title="Không có bản ghi cần xử lý",
            text="Tất cả các bản ghi chấm công đã được chốt sổ đầy đủ.",
            data={"processed_count": 0},
        )

    return _ok(
        icon="success",
        title="Tự động chốt công hoàn tất",
        text=(
            f"Đã tự động xử lý {count} bản ghi chấm công "
            f"chưa được chốt sổ"
            + (f" trước ngày {reference_date.strftime('%d/%m/%Y')}." if reference_date else ".")
        ),
        data={
            "processed_count": count,
            "reference_date":  reference_date.strftime("%Y-%m-%d") if reference_date else date.today().strftime("%Y-%m-%d"),
        },
    )


# ============================================================
# 5️⃣  POST /attendance/ot/reset-noti  — Hủy OT từ thông báo
# ============================================================

@attendance_bp.route("/ot/reset-noti", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE, RoleName.MANAGER, RoleName.HR, RoleName.ADMIN)
def reset_ot_from_notification():
    """
    Hủy đơn tăng ca dựa trên thông báo (notification) khi người dùng bấm nút xóa từ noti.
    Tự động đồng bộ attendance và soft-delete notification liên quan.

    Phân quyền:
        - EMPLOYEE/MANAGER : Chỉ được hủy thông báo / đơn OT của chính mình.
        - HR/ADMIN         : Có thể hủy thay cho bất kỳ nhân viên nào.

    Body JSON:
        notification_id (int, required) : ID thông báo neo (anchor notification).
        employee_id     (int, optional) : HR/Admin có thể truyền để xử lý hộ người khác.
    """
    body             = request.get_json(silent=True) or {}
    user             = g.user
    current_employee = g.employee
    role             = user.role.name

    # ── Validate notification_id ─────────────────────────────────────────
    notification_id = body.get("notification_id")
    if not notification_id:
        return _bad_request("Vui lòng cung cấp notification_id")
    try:
        notification_id = int(notification_id)
    except (ValueError, TypeError):
        return _bad_request("notification_id phải là số nguyên")

    # ── Xác định employee sở hữu thông báo ───────────────────────────────
    requested_employee_id = body.get("employee_id")

    if requested_employee_id:
        try:
            requested_employee_id = int(requested_employee_id)
        except (ValueError, TypeError):
            return _bad_request("employee_id phải là số nguyên")

        if role in [RoleName.ADMIN, RoleName.HR]:
            target_employee_id = requested_employee_id
        else:
            # Employee/Manager chỉ được thao tác trên chính mình
            if requested_employee_id != current_employee.id:
                return _forbidden("Bạn chỉ được hủy đơn OT của chính mình")
            target_employee_id = current_employee.id
    else:
        target_employee_id = current_employee.id

    # ── Kiểm tra notification thuộc đúng user ────────────────────────────
    # Lấy user_id của employee mục tiêu để validate ownership notification
    from app.models.employee import Employee
    target_emp = Employee.query.filter_by(
        id=target_employee_id, is_deleted=False
    ).first()

    if not target_emp:
        return _not_found("Không tìm thấy nhân viên")

    if not target_emp.user_id:
        return _not_found("Nhân viên chưa được liên kết với tài khoản người dùng")

    target_user_id = target_emp.user_id

    # ── Gọi service xử lý ────────────────────────────────────────────────
    try:
        result = AttendanceService.process_overtime_reset_from_notification(
            user_id=target_user_id,
            employee_id=target_employee_id,
            noti_id=notification_id,
        )
    except Exception as e:
        return _err("error", "Lỗi hệ thống", str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    # ── Phân biệt kết quả ────────────────────────────────────────────────
    success = result.get("success", False)

    if not success:
        return _ok(
            icon="error",
            title="Không thể hủy đơn OT",
            text=result.get("message", "Hủy đơn OT thất bại"),
            data=result,
        )

    if result.get("already_deleted"):
        return _ok(
            icon="info",
            title="Đã xử lý trước đó",
            text=result.get("message", "Đơn OT liên quan đã được xóa từ trước."),
            data={
                "notification_id":      notification_id,
                "target_employee_id":   target_employee_id,
                "already_deleted":      True,
            },
        )

    return _ok(
        icon="success",
        title="Hủy đơn OT thành công",
        text=result.get("message", "Đã hủy đơn tăng ca và cập nhật dữ liệu liên quan."),
        data={
            "notification_id":    notification_id,
            "target_employee_id": target_employee_id,
            "overtime_request_id": result.get("overtime_request_id"),
        },
        timer=2000,
    )

# ============================================================
# 6️⃣  GET /attendance/api/history  — Lấy dữ liệu lịch sử (JSON)
# ============================================================

@attendance_bp.route("/api/history", methods=["GET"])
@auth_required
def get_history_api():
    """
    Cung cấp dữ liệu lịch sử chấm công dưới dạng JSON cho XHR/fetch.
    """
    try:
        # Lấy các tham số từ query string
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        from_date_str = request.args.get('from_date')
        to_date_str = request.args.get('to_date')
        employee_id = request.args.get('employee_id')

        # Gọi service để lấy dữ liệu
        history_data = AttendanceService.get_history(
            page=page,
            per_page=per_page,
            from_date=from_date_str,
            to_date=to_date_str,
            employee_id=employee_id
        )
        return jsonify(history_data)

    except Exception as e:
        return jsonify(icon="error", title="Lỗi hệ thống", text=str(e)), 500

# ============================================================
# 7️⃣  DELETE /attendance/<date>  — Xóa bản ghi chấm công
# ============================================================

@attendance_bp.route('/<string:date_str>', methods=['DELETE'])
@auth_required
@role_required('Admin', 'HR')
def delete_attendance_record(date_str):
    """Xóa (soft delete) một bản ghi chấm công.
    Chỉ Admin và HR được phép.
    """
    employee_id = request.args.get('employee_id', type=int)
    if not employee_id:
        return _bad_request('Thiếu ID nhân viên.')

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        success = AttendanceService.delete_attendance(employee_id, date_obj)
        if success:
            return _ok("success", "Xóa thành công", f"Đã xóa bản ghi chấm công ngày {date_str} của nhân viên #{employee_id}")
        else:
            return _not_found(f"Không tìm thấy bản ghi chấm công phù hợp để xóa.")
    except ValueError:
        return _bad_request('Định dạng ngày không hợp lệ.')
    except Exception as e:
        return _err("error", "Lỗi máy chủ", str(e), 500)

