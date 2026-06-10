"""
attendance_workflow_routes.py
─────────────────────────────
Routes điều phối toàn bộ luồng chấm công (check-in, check-out, OT, offday).

Route map:
    POST /attendance/action              → Hành động chấm công thông minh (dispatch theo state)
    POST /attendance/check-in            → Check-in ca chính
    POST /attendance/check-out           → Check-out ca chính (hỗ trợ tan ca sớm)
    POST /attendance/overtime/check-in   → Check-in tăng ca (OT)
    POST /attendance/overtime/check-out  → Check-out tăng ca (OT)
    POST /attendance/offday              → Xử lý ngày nghỉ / lễ / phép
    POST /attendance/overtime/approve    → HR/Manager duyệt đơn OT
    POST /attendance/overtime/reject     → HR/Manager từ chối đơn OT
    POST /attendance/simulate/clock      → HR/Admin set đồng hồ giả lập (debug)
"""

from flask import request, g
from http import HTTPStatus

from app.extensions.db import db
from app.models.attendance import Attendance
from app.models.overtime_request import OvertimeRequest
from app.constants.common import RoleName
from app.common.security.decorators import auth_required
from app.common.exceptions import ValidationError, ForbiddenError, NotFoundError
from app.modules.attendance import attendance_bp
from app.modules.attendance.attendance_workflow_service import Attendance_workflow_service
from app.utils.time import get_current_time, set_simulated_time, _normalize, VN_TIMEZONE


# ============================================================
# 🔧 HELPERS
# ============================================================

def _ok(result: dict, swal_override: dict | None = None) -> tuple:
    """
    Bọc kết quả service thành response chuẩn kèm swal.
    Ánh xạ type → icon SweetAlert2:
        success → success   warning → warning
        info    → info      error   → error
    """
    type_to_icon = {
        "success": "success",
        "warning": "warning",
        "info":    "info",
        "error":   "error",
    }
    result_type = result.get("type", "info")
    icon = type_to_icon.get(result_type, "info")
    needs_confirm = result.get("requires_confirmation") or result.get("requires_overtime_decision")

    swal = swal_override or {
        "icon":              icon,
        "title":             _swal_title(result.get("action", "")),
        "text":              result.get("message", ""),
        **({"timer": 2000, "showConfirmButton": False} if icon == "success" and not needs_confirm else {}),
    }

    return {
        "swal": swal,
        **result,
    }, HTTPStatus.OK


def _swal_title(action: str) -> str:
    """Ánh xạ action code → tiêu đề SweetAlert2 thân thiện."""
    TITLES = {
        "check_in":                      "Check-in thành công",
        "check_out":                     "Check-out thành công",
        "check_in_ot":                   "Check-in OT thành công",
        "check_out_ot":                  "Hoàn thành tăng ca",
        "overtime_request_created":      "Đã gửi yêu cầu OT",
        "complete_without_ot":           "Hoàn thành ngày công",
        "already_recorded":              "Đã ghi nhận",
        "offer_overtime":                "Đăng ký tăng ca?",
        "early_checkout_prompt":         "Tan ca sớm?",
        "holiday_work_prompt":           "Làm việc ngày lễ?",
        "weekend_work_prompt":           "Làm việc cuối tuần?",
        "holiday_off":                   "Nghỉ lễ",
        "weekend_off":                   "Nghỉ cuối tuần",
        "leave_day":                     "Nghỉ phép",
        "ot_approved":                   "OT đã được duyệt",
        "ot_rejected":                   "OT đã bị từ chối",
        "lunch_break":                   "Giờ nghỉ trưa",
        "pre_ot_rest":                   "Chờ tăng ca",
        "ot_approved_wait":              "OT được duyệt",
        "ot_pending_approval":           "Đang chờ duyệt",
        "attendance_not_required":       "Không bắt buộc chấm công",
        "invalid_state":                 "Trạng thái không hợp lệ",
    }
    return TITLES.get(str(action).lower(), "Thông báo hệ thống")


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

def _assert_manager():
    """Raise ForbiddenError nếu không phải Manager/HR/Admin."""
    user = g.user
    if user.role.name not in [RoleName.MANAGER]:
        raise ForbiddenError("Chỉ Manager mới có quyền thực hiện thao tác này")


def _get_now(body: dict | None = None):
    """
    Trả về thời điểm hiện tại (có hỗ trợ sim_time từ body nếu HR/Admin).
    Nếu body có simulate_time → set đồng hồ giả lập và trả về thời điểm đó.
    """
    body = body or {}
    simulate_time_str = body.get("simulate_time")

    if simulate_time_str:
        user = g.user
        if user.role.name in [RoleName.ADMIN, RoleName.HR]:
            dt = _normalize(simulate_time_str)
            if dt:
                set_simulated_time(dt)
                return dt.replace(tzinfo=VN_TIMEZONE) if dt.tzinfo is None else dt.astimezone(VN_TIMEZONE)

    return get_current_time()


# ============================================================
# 1️⃣  POST /attendance/action  — Điểm vào thông minh (Smart Dispatch)
# ============================================================

@attendance_bp.route("/action", methods=["POST"])
@auth_required
def attendance_action():
    """
    Route điều phối chấm công thông minh.
    Frontend gọi 1 endpoint duy nhất; backend tự xác định state hiện tại
    và gọi đúng handler tương ứng.

    Body JSON:
        simulate_time           (str, optional) : HR/Admin giả lập thời điểm
        confirm_work_on_offday  (bool, optional): Xác nhận làm việc ngày nghỉ
        overtime_confirmed      (bool, optional): Alias của confirm_work_on_offday
        early_checkout_confirmed(bool, optional): Xác nhận tan ca sớm
        overtime_decision       (str, optional) : "yes" / "no" — quyết định đăng ký OT
        decline_offday_work     (bool, optional): Từ chối làm việc ngày nghỉ
    """
    body             = request.get_json(silent=True) or {}
    current_employee = g.employee
    employee_id      = current_employee.id
    now_dt           = _get_now(body)
    today            = now_dt.date()

    # ── Bước 1: Xử lý ngày nghỉ / phép trước ────────────────────────────
    offday_result = Attendance_workflow_service._handle_offday_logic(
        employee_id=employee_id,
        payload=body,
        today=today,
    )

    # Nếu offday handler chưa pass-through → Trả về luôn
    if not offday_result.get("pass_through"):
        return _ok(offday_result)

    # ── Bước 2: Lấy bản ghi chấm công hiện hành ─────────────────────────
    attendance = Attendance.query.filter_by(
        employee_id=employee_id,
        date=today,
        is_deleted=False,
    ).first()

    # ── Bước 3: Dispatch theo trạng thái ca ─────────────────────────────
    from app.constants.attendance import AttendanceConstants

    # Chưa có bản ghi → check-in mới
    if not attendance:
        try:
            result = Attendance_workflow_service._handle_not_started(
                employee_id=employee_id,
                payload=body,
                current_time=now_dt,
            )
        except ValidationError as e:
            return _validation_err(str(e))
        return _ok(result)

    normalized_shift = AttendanceConstants.normalize(attendance.shift_status)

    # Trạng thái chưa bắt đầu → check-in
    NOT_STARTED_STATES = {
        AttendanceConstants.STATUS_NOT_STARTED,
    }
    if normalized_shift in NOT_STARTED_STATES:
        try:
            result = Attendance_workflow_service._handle_not_started(
                employee_id=employee_id,
                payload=body,
                current_time=now_dt,
            )
        except ValidationError as e:
            return _validation_err(str(e))
        return _ok(result)

    # Trạng thái đang làm ca chính / cần checkout ca chính
    WORKING_STATES = {
        AttendanceConstants.STATUS_WORKING_REGULAR,
        AttendanceConstants.STATUS_REGULAR_CHECKOUT_REQ,
    }
    if normalized_shift in WORKING_STATES:
        try:
            result = Attendance_workflow_service._handle_working(
                attendance=attendance,
                employee_id=employee_id,
                payload=body,
                current_time=now_dt,
            )
        except ValidationError as e:
            return _validation_err(str(e))
        return _ok(result)

    # Trạng thái sau checkout ca chính (OT / hoàn tất)
    POST_CHECKOUT_STATES = {
        AttendanceConstants.STATUS_REGULAR_DONE,
        AttendanceConstants.STATUS_REGULAR_DONE_PENDING_OT,
        AttendanceConstants.STATUS_PRE_OT_REST,
        AttendanceConstants.STATUS_OT_CHECKIN_REQUIRED,
        AttendanceConstants.STATUS_WORKING_OVERTIME,
    }
    if normalized_shift in POST_CHECKOUT_STATES:
        ot_request = Attendance_workflow_service._get_ot_request(employee_id, today)
        try:
            result = Attendance_workflow_service._handle_after_checkout(
                attendance=attendance,
                employee_id=employee_id,
                payload=body,
                current_time=now_dt,
            )
        except ValidationError as e:
            return _validation_err(str(e))
        return _ok(result)

    # Terminal states → Không cho thao tác thêm
    return _ok({
        "type":             "info",
        "action":           "already_recorded",
        "attendance_state": normalized_shift,
        "message":          "Bản ghi ngày công đã hoàn tất.",
        "attendance":       None,
    })


# ============================================================
# 2️⃣  POST /attendance/check-in  — Check-in ca chính
# ============================================================

@attendance_bp.route("/check-in", methods=["POST"])
@auth_required
def check_in():
    """
    Check-in ca làm việc chính.

    Body JSON:
        confirm_work_on_offday (bool, optional): Xác nhận làm việc ngày lễ/cuối tuần
        simulate_time          (str, optional) : HR/Admin giả lập thời điểm
    """
    body        = request.get_json(silent=True) or {}
    employee_id = g.employee.id
    now_dt      = _get_now(body)
    confirm     = bool(body.get("confirm_work_on_offday")) or bool(body.get("overtime_confirmed"))

    try:
        result = Attendance_workflow_service.check_in(
            employee_id=employee_id,
            current_time=now_dt,
            confirm_work=confirm,
        )
    except ValidationError as e:
        return _validation_err(str(e))

    return _ok(result)


# ============================================================
# 3️⃣  POST /attendance/check-out  — Check-out ca chính
# ============================================================

@attendance_bp.route("/check-out", methods=["POST"])
@auth_required
def check_out():
    """
    Check-out ca làm việc chính.
    Tự động xử lý tan ca sớm nếu truyền early_checkout_confirmed=true.

    Body JSON:
        early_checkout_confirmed (bool, optional): Xác nhận muốn tan ca sớm
        simulate_time            (str, optional) : HR/Admin giả lập thời điểm
    """
    body             = request.get_json(silent=True) or {}
    employee_id      = g.employee.id
    now_dt           = _get_now(body)
    early_confirmed  = bool(body.get("early_checkout_confirmed"))

    try:
        result = Attendance_workflow_service.check_out_regular(
            employee_id=employee_id,
            current_time=now_dt,
            early_checkout=early_confirmed,
        )
    except ValidationError as e:
        return _validation_err(str(e))

    return _ok(result)


# ============================================================
# 4️⃣  POST /attendance/overtime/check-in  — Check-in tăng ca
# ============================================================

@attendance_bp.route("/overtime/check-in", methods=["POST"])
@auth_required
def check_in_overtime():
    """
    Check-in ca tăng ca (OT). Yêu cầu phải có đơn OT đã được duyệt.
    """
    body = request.get_json(silent=True) or {}
    now_dt = _get_now(body) # Tự động lấy thời gian (thực hoặc giả lập)

    try:
        # LƯU Ý: Đảm bảo service nhận tham số current_time
        result = Attendance_workflow_service.check_in_overtime(
            employee_id=g.employee.id,
            current_time=now_dt 
        )
    except ValidationError as e:
        return _validation_err(str(e))

    return _ok(result)


# ============================================================
# 5️⃣  POST /attendance/overtime/check-out  — Check-out tăng ca
# ============================================================

@attendance_bp.route("/overtime/check-out", methods=["POST"])
@auth_required
def check_out_overtime():
    """
    Check-out ca tăng ca (OT). Tự động tính giờ OT + hệ số nhân.
    """
    body = request.get_json(silent=True) or {}
    now_dt = _get_now(body) # Tự động lấy thời gian (thực hoặc giả lập)

    try:
        # LƯU Ý: Đảm bảo service nhận tham số current_time
        result = Attendance_workflow_service.check_out_overtime(
            employee_id=g.employee.id,
            current_time=now_dt
        )
    except ValidationError as e:
        return _validation_err(str(e))

    return _ok(result)

# ============================================================
# 6️⃣  POST /attendance/offday  — Khai báo ngày nghỉ / lễ / phép
# ============================================================

@attendance_bp.route("/offday", methods=["POST"])
@auth_required
def handle_offday():
    """
    Xử lý tình huống ngày nghỉ: nghỉ phép đã duyệt, nghỉ lễ, cuối tuần.
    Nếu nhân viên chọn từ chối làm việc ngày nghỉ → Chốt bản ghi nghỉ.

    Body JSON:
        decline_offday_work (bool, optional): true = Xác nhận không đi làm hôm nay
        simulate_time       (str, optional) : HR/Admin giả lập thời điểm
    """
    body        = request.get_json(silent=True) or {}
    employee_id = g.employee.id
    now_dt      = _get_now(body)

    result = Attendance_workflow_service._handle_offday_logic(
        employee_id=employee_id,
        payload=body,
        today=now_dt.date(),
    )

    # pass_through = True nghĩa là không phải ngày nghỉ đặc biệt
    if result.get("pass_through"):
        return _ok({
            "type":             "info",
            "action":           "not_offday",
            "attendance_state": "WORKING",
            "message":          "Hôm nay là ngày làm việc bình thường. Vui lòng dùng /check-in.",
        })

    return _ok(result)
