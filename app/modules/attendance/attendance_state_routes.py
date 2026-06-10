"""
attendance_state_routes.py
──────────────────────────
Routes phục vụ trạng thái ca làm việc theo thời gian thực.

Route map:
    GET  /attendance/state              → Trạng thái ca hiện tại của nhân viên (dùng cho Widget/Dashboard)
    GET  /attendance/state/<employee_id>→ HR/Admin/Manager xem trạng thái của nhân viên cụ thể
    POST /attendance/state/simulate     → HR/Admin giả lập trạng thái tại một thời điểm bất kỳ (debug/test)
"""

from flask import request, g
from http import HTTPStatus
from datetime import datetime, date

from app.extensions.db import db
from app.models.attendance import Attendance
from app.models.overtime_request import OvertimeRequest
from app.constants.common import RoleName
from app.common.security.decorators import auth_required
from app.common.exceptions import ForbiddenError, NotFoundError
from app.modules.attendance import attendance_bp
from app.modules.attendance.attendance_state_service import AttendanceStateService
from app.utils.time import get_current_time, VN_TIMEZONE


# ============================================================
# 🔧 HELPER: Lấy bản ghi Attendance + OvertimeRequest hôm nay
# ============================================================

def _fetch_today_attendance(employee_id: int) -> tuple[Attendance | None, OvertimeRequest | None]:
    """
    Lấy bản ghi Attendance và OvertimeRequest hiện hành của nhân viên.
    Ưu tiên bản ghi ngày hôm nay, fallback về ngày hôm qua nếu chưa checkout.
    """
    today = date.today()

    attendance = Attendance.query.filter_by(
        employee_id=employee_id,
        date=today,
        is_deleted=False,
    ).first()

    # Fallback: Tìm bản ghi hôm qua nếu hôm nay chưa có
    # (Xử lý trường hợp quên checkout ca đêm / OT qua đêm)
    if not attendance:
        from datetime import timedelta
        yesterday = today - timedelta(days=1)
        attendance = Attendance.query.filter_by(
            employee_id=employee_id,
            date=yesterday,
            is_deleted=False,
        ).filter(
            # Chỉ lấy nếu chưa hoàn tất (shift_status chưa COMPLETED)
            Attendance.shift_status.notin_(["completed", "holiday_off", "weekend_off", "leave", "absent"])
        ).first()

    # Lấy OvertimeRequest đang hoạt động (pending / approved) trong ngày
    ot_request = None
    if attendance:
        ot_request = OvertimeRequest.query.filter_by(
            employee_id=employee_id,
            is_deleted=False,
        ).filter(
            OvertimeRequest.status.in_(["pending", "approved"])
        ).order_by(OvertimeRequest.created_at.desc()).first()

    return attendance, ot_request


def _resolve_target_employee(requested_employee_id: int | None):
    """
    Phân quyền xác định employee được xem trạng thái.

    Returns:
        employee_id (int)
    Raises:
        ForbiddenError, NotFoundError
    """
    from app.models.employee import Employee
    from app.models.department import Department

    user             = g.user
    current_employee = g.employee
    role             = user.role.name

    # Không truyền employee_id → Luôn xem chính mình (mọi role)
    if not requested_employee_id:
        return current_employee.id

    # ── HR / ADMIN: Xem bất kỳ ai ───────────────────────────────────────
    if role in [RoleName.ADMIN, RoleName.HR]:
        target = Employee.query.filter_by(id=requested_employee_id, is_deleted=False).first()
        if not target:
            raise NotFoundError("Không tìm thấy nhân viên")
        return target.id

    # ── MANAGER: Xem nhân viên trong phòng ban mình quản lý ─────────────
    if role == RoleName.MANAGER:
        managed_dept = Department.query.filter_by(
            manager_id=current_employee.id, is_deleted=False
        ).first()

        allowed_ids = (
            [e.id for e in managed_dept.employees if not e.is_deleted]
            if managed_dept
            else [current_employee.id]
        )

        if int(requested_employee_id) not in allowed_ids:
            raise ForbiddenError("Bạn không có quyền xem trạng thái của nhân viên này")

        return int(requested_employee_id)

    # ── EMPLOYEE: Chỉ xem chính mình ────────────────────────────────────
    if int(requested_employee_id) != current_employee.id:
        raise ForbiddenError("Bạn chỉ được xem trạng thái chấm công của chính mình")

    return current_employee.id


def _state_dto_to_dict(dto) -> dict:
    """Chuyển AttendanceStateDTO thành dict an toàn để serialize JSON."""
    return {
        "state":                      str(dto.state),
        "button_enabled":             dto.button_enabled,
        "button_text":                dto.button_text,
        "can_scan":                   dto.can_scan,
        "message":                    dto.message,
        "overtime_status":            getattr(dto, "overtime_status", None),
        "requires_overtime_decision": getattr(dto, "requires_overtime_decision", False),
        "locked_state":               getattr(dto, "locked_state", False),
    }


# ============================================================
# 1️⃣  GET /attendance/state  — Trạng thái ca hiện tại (bản thân)
# ============================================================

@attendance_bp.route("/state", methods=["GET"])
@auth_required
def get_my_attendance_state():
    """
    Lấy trạng thái ca làm việc hiện tại của chính người dùng đang đăng nhập.
    Dùng cho Widget Sidebar / Dashboard thời gian thực.

    Response trả về AttendanceStateDTO dạng JSON kèm swal notification.
    """
    current_employee = g.employee

    attendance, ot_request = _fetch_today_attendance(current_employee.id)
    now = get_current_time()

    state_dto = AttendanceStateService.compute_attendance_state(
        now=now,
        attendance=attendance,
        ot_request=ot_request,
    )

    return {
        "swal": {
            "icon":              "success",
            "title":             "Trạng thái ca làm việc",
            "text":              state_dto.message,
            "timer":             1500,
            "showConfirmButton": False,
        },
        "employee_id":  current_employee.id,
        "full_name":    current_employee.full_name,
        "checked_at":   now.strftime("%Y-%m-%d %H:%M:%S"),
        "state":        _state_dto_to_dict(state_dto),
    }, HTTPStatus.OK


# ============================================================
# 2️⃣  GET /attendance/state/<employee_id>  — HR/Admin/Manager xem người khác
# ============================================================

@attendance_bp.route("/state/<int:employee_id>", methods=["GET"])
@auth_required
def get_employee_attendance_state(employee_id: int):
    """
    Xem trạng thái ca làm việc của một nhân viên cụ thể.

    Phân quyền:
        - EMPLOYEE : Chỉ được xem chính mình (employee_id phải trùng)
        - MANAGER  : Xem nhân viên trong phòng ban mình quản lý
        - HR/ADMIN : Xem bất kỳ nhân viên nào

    URL param:
        employee_id (int) : ID nhân viên cần xem
    """
    try:
        target_id = _resolve_target_employee(employee_id)
    except ForbiddenError as e:
        return {
            "swal": {"icon": "error", "title": "Không có quyền truy cập", "text": str(e)}
        }, HTTPStatus.FORBIDDEN
    except NotFoundError as e:
        return {
            "swal": {"icon": "warning", "title": "Không tìm thấy", "text": str(e)}
        }, HTTPStatus.NOT_FOUND

    # Lấy thông tin nhân viên để hiển thị
    from app.models.employee import Employee
    target_employee = Employee.query.get(target_id)

    attendance, ot_request = _fetch_today_attendance(target_id)
    now = get_current_time()

    state_dto = AttendanceStateService.compute_attendance_state(
        now=now,
        attendance=attendance,
        ot_request=ot_request,
    )

    return {
        "swal": {
            "icon":              "success",
            "title":             f"Trạng thái — {target_employee.full_name}",
            "text":              state_dto.message,
            "timer":             1500,
            "showConfirmButton": False,
        },
        "employee_id": target_id,
        "full_name":   target_employee.full_name,
        "checked_at":  now.strftime("%Y-%m-%d %H:%M:%S"),
        "state":       _state_dto_to_dict(state_dto),
    }, HTTPStatus.OK

