from flask import request, g
from http import HTTPStatus
from datetime import datetime, date

from app.extensions.db import db
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.department import Department
from app.constants.common import RoleName
from app.common.security.decorators import auth_required
from app.common.exceptions import ForbiddenError, NotFoundError
from app.modules.attendance import attendance_bp


# ============================================================
# 🔧 HELPER: Phân quyền lọc danh sách employee_id
# ============================================================

def _resolve_allowed_employee_ids(requested_employee_id=None):
    """
    Trả về danh sách employee_id được phép truy cập theo role.

    Returns:
        None         → HR/Admin không lọc (xem tất cả)
        list[int]    → Danh sách ID được phép
    Raises:
        ForbiddenError  nếu vượt quyền
        NotFoundError   nếu employee_id không tồn tại
    """
    user             = g.user
    current_employee = g.employee
    role             = user.role.name

    # ── ADMIN / HR: Không giới hạn ──────────────────────────────────────
    if role in [RoleName.ADMIN, RoleName.HR]:
        if requested_employee_id:
            target = Employee.query.filter_by(
                id=int(requested_employee_id), is_deleted=False
            ).first()
            if not target:
                raise NotFoundError("Không tìm thấy nhân viên")
            return [int(requested_employee_id)]
        return None  # Xem tất cả

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

        if requested_employee_id:
            if int(requested_employee_id) not in allowed_ids:
                raise ForbiddenError("Bạn không có quyền xem thông tin nhân viên này")
            return [int(requested_employee_id)]

        return allowed_ids

    # ── EMPLOYEE: Chỉ xem chính mình ────────────────────────────────────
    if requested_employee_id and int(requested_employee_id) != current_employee.id:
        raise ForbiddenError("Bạn chỉ được xem thông tin của chính mình")

    return [current_employee.id]


def _swal_forbidden(message: str):
    return {
        "swal": {"icon": "error", "title": "Không có quyền truy cập", "text": message}
    }, HTTPStatus.FORBIDDEN


def _swal_not_found(message: str):
    return {
        "swal": {"icon": "warning", "title": "Không tìm thấy", "text": message}
    }, HTTPStatus.NOT_FOUND


def _swal_bad_request(message: str):
    return {
        "swal": {"icon": "warning", "title": "Dữ liệu không hợp lệ", "text": message}
    }, HTTPStatus.BAD_REQUEST


# ============================================================
# 1️⃣  GET /attendance/today/list  — Danh sách chấm công hôm nay
# ============================================================

@attendance_bp.route("/today/list", methods=["GET"])
@auth_required
def list_today():
    """
    Lấy danh sách bản ghi chấm công của tất cả nhân viên hôm nay (dành cho Manager/HR/Admin).

    Query params:
        employee_id (int, optional): HR/Admin có thể xem người khác;
                                     Manager xem trong phòng ban;
                                     Employee chỉ xem chính mình.
    """
    requested_employee_id = request.args.get("employee_id", type=int)

    try:
        allowed_ids = _resolve_allowed_employee_ids(requested_employee_id)
    except ForbiddenError as e:
        return _swal_forbidden(str(e))
    except NotFoundError as e:
        return _swal_not_found(str(e))

    today = date.today()

    query = Attendance.query.filter(
        Attendance.date == today,
        Attendance.is_deleted == False,
    )
    if allowed_ids is not None:
        query = query.filter(Attendance.employee_id.in_(allowed_ids))

    records = query.all()

    if not records:
        return {
            "swal": {
                "icon": "info",
                "title": "Chưa có dữ liệu",
                "text": f"Không tìm thấy bản ghi chấm công nào cho ngày {today.strftime('%d/%m/%Y')}",
            },
            "date": today.strftime("%Y-%m-%d"),
            "data": [],
        }, HTTPStatus.OK

    data = []
    for r in records:
        emp = r.employee
        data.append({
            "employee_id":        emp.id,
            "full_name":          emp.full_name,
            "date":               today.strftime("%Y-%m-%d"),
            "check_in":           r.check_in.strftime("%H:%M:%S")  if r.check_in  else None,
            "check_out":          r.check_out.strftime("%H:%M:%S") if r.check_out else None,
            "attendance_type":    r.attendance_type,
            "regular_hours":      float(r.regular_hours or 0),
            "late_minutes":       r.late_minutes or 0,
            "early_leave_minutes": r.early_leave_minutes or 0,
            "status":             r.status if hasattr(r, "status") else None,
        })

    return {
        "swal": {
            "icon": "success",
            "title": "Dữ liệu hôm nay",
            "text": f"Tổng {len(data)} bản ghi — {today.strftime('%d/%m/%Y')}",
            "timer": 1500,
            "showConfirmButton": False,
        },
        "date":  today.strftime("%Y-%m-%d"),
        "total": len(data),
        "data":  data,
    }, HTTPStatus.OK


# ============================================================
# 2️⃣  GET /attendance/api/history  — Bảng công cá nhân (API)
# ============================================================

@attendance_bp.route("/api/history", methods=["GET"])
@auth_required
def get_history():
    """
    Lấy lịch sử chấm công theo khoảng thời gian.

    Query params:
        employee_id (int, optional) : Xem nhân viên cụ thể (theo phân quyền).
        from_date   (str, optional) : YYYY-MM-DD, mặc định đầu tháng hiện tại.
        to_date     (str, optional) : YYYY-MM-DD, mặc định hôm nay.
        page        (int, optional) : Số trang, mặc định 1.
        per_page    (int, optional) : Số bản ghi mỗi trang, mặc định 31 (1 tháng).
    """
    requested_employee_id = request.args.get("employee_id", type=int)

    try:
        allowed_ids = _resolve_allowed_employee_ids(requested_employee_id)
    except ForbiddenError as e:
        return _swal_forbidden(str(e))
    except NotFoundError as e:
        return _swal_not_found(str(e))

    # ── Parse khoảng thời gian ───────────────────────────────────────────
    today = date.today()
    default_from = today.replace(day=1)

    from_str = request.args.get("from_date")
    to_str   = request.args.get("to_date")

    try:
        from_date = datetime.strptime(from_str, "%Y-%m-%d").date() if from_str else default_from
        to_date   = datetime.strptime(to_str,   "%Y-%m-%d").date() if to_str   else today
    except ValueError:
        return _swal_bad_request("Định dạng ngày không hợp lệ. Vui lòng dùng YYYY-MM-DD")

    if from_date > to_date:
        return _swal_bad_request("from_date không được lớn hơn to_date")

    # ── Phân trang ───────────────────────────────────────────────────────
    page     = request.args.get("page",     default=1,  type=int)
    per_page = request.args.get("per_page", default=31, type=int)
    per_page = min(per_page, 100)  # Giới hạn tối đa để bảo vệ hiệu năng

    query = Attendance.query.filter(
        Attendance.date >= from_date,
        Attendance.date <= to_date,
        Attendance.is_deleted == False,
    ).order_by(Attendance.date.desc())

    if allowed_ids is not None:
        query = query.filter(Attendance.employee_id.in_(allowed_ids))

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    if not paginated.items:
        return {
            "swal": {
                "icon": "info",
                "title": "Không có dữ liệu",
                "text": (
                    f"Không tìm thấy bản ghi chấm công "
                    f"từ {from_date.strftime('%d/%m/%Y')} đến {to_date.strftime('%d/%m/%Y')}"
                ),
            },
            "pagination": {
                "page": page, "per_page": per_page,
                "total": 0, "pages": 0,
            },
            "data": [],
        }, HTTPStatus.OK

    data = []
    for r in paginated.items:
        emp = r.employee
        data.append({
            "employee_id":         emp.id,
            "full_name":           emp.full_name,
            "date":                r.date.strftime("%Y-%m-%d") if r.date else None,
            "check_in":            r.check_in.strftime("%H:%M:%S")  if r.check_in  else None,
            "check_out":           r.check_out.strftime("%H:%M:%S") if r.check_out else None,
            "attendance_type":     r.attendance_type,
            "regular_hours":       float(r.regular_hours or 0),
            "late_minutes":        r.late_minutes or 0,
            "early_leave_minutes": r.early_leave_minutes or 0,
            "status":              r.status if hasattr(r, "status") else None,
        })

    return {
        "swal": {
            "icon": "success",
            "title": "Lịch sử chấm công",
            "text": f"Tìm thấy {paginated.total} bản ghi",
            "timer": 1500,
            "showConfirmButton": False,
        },
        "pagination": {
            "page":     paginated.page,
            "per_page": paginated.per_page,
            "total":    paginated.total,
            "pages":    paginated.pages,
        },
        "from_date": from_date.strftime("%Y-%m-%d"),
        "to_date":   to_date.strftime("%Y-%m-%d"),
        "data":      data,
    }, HTTPStatus.OK


# ============================================================
# 3️⃣  DELETE /attendance/<date>  — Hủy bản ghi công ngày cụ thể
# ============================================================

@attendance_bp.route("/<string:attendance_date>", methods=["DELETE"])
@auth_required
def delete_attendance(attendance_date: str):
    """
    Hủy (soft-delete) bản ghi chấm công theo ngày.

    URL param:
        attendance_date (str) : Ngày cần hủy, định dạng YYYY-MM-DD.

    Query param:
        employee_id (int, optional) : HR/Admin có thể xóa hộ người khác.
                                      Employee chỉ được xóa của chính mình.
    """
    # ── 1. Parse ngày ────────────────────────────────────────────────────
    try:
        target_date = datetime.strptime(attendance_date, "%Y-%m-%d").date()
    except ValueError:
        return _swal_bad_request("Định dạng ngày không hợp lệ. Vui lòng dùng YYYY-MM-DD")

    # Không cho phép xóa ngày trong tương lai
    if target_date > date.today():
        return _swal_bad_request("Không thể hủy bản ghi chấm công của ngày trong tương lai")

    # ── 2. Xác định employee sở hữu bản ghi ─────────────────────────────
    requested_employee_id = request.args.get("employee_id", type=int)

    # Với DELETE: Employee & Manager chỉ được xóa của chính mình
    # HR/Admin được xóa hộ người khác
    user = g.user
    role = user.role.name
    current_employee = g.employee

    if role in [RoleName.ADMIN, RoleName.HR]:
        target_employee_id = requested_employee_id or current_employee.id
        # Kiểm tra nhân viên tồn tại nếu HR/Admin truyền employee_id
        if requested_employee_id:
            target_emp = Employee.query.filter_by(
                id=requested_employee_id, is_deleted=False
            ).first()
            if not target_emp:
                return _swal_not_found("Không tìm thấy nhân viên")
    else:
        # Manager và Employee chỉ được xóa bản ghi của chính mình
        if requested_employee_id and int(requested_employee_id) != current_employee.id:
            return _swal_forbidden("Bạn chỉ được hủy bản ghi chấm công của chính mình")
        target_employee_id = current_employee.id

    # ── 3. Tìm bản ghi chấm công ─────────────────────────────────────────
    record = Attendance.query.filter_by(
        employee_id=target_employee_id,
        date=target_date,
        is_deleted=False,
    ).first()

    if not record:
        return _swal_not_found(
            f"Không tìm thấy bản ghi chấm công ngày {target_date.strftime('%d/%m/%Y')}"
        )

    # ── 4. Soft delete ────────────────────────────────────────────────────
    record.is_deleted = True
    db.session.commit()

    return {
        "swal": {
            "icon": "success",
            "title": "Hủy thành công",
            "text": (
                f"Đã hủy bản ghi chấm công ngày "
                f"{target_date.strftime('%d/%m/%Y')} "
                f"của nhân viên #{target_employee_id}"
            ),
        },
        "deleted": {
            "employee_id": target_employee_id,
            "date":        target_date.strftime("%Y-%m-%d"),
        },
    }, HTTPStatus.OK


# ============================================================
# 4️⃣  DELETE /notifications/<id>  — Xóa thông báo + Hủy OT liên quan
# ============================================================

@attendance_bp.route("/notifications/<int:notification_id>", methods=["DELETE"])
@auth_required
def delete_notification_cascade(notification_id: int):
    """
    Xóa thông báo và hủy OvertimeRequest liên quan (nếu có).

    URL param:
        notification_id (int) : ID thông báo cần xóa.

    Phân quyền:
        - Employee : chỉ được xóa thông báo của chính mình.
        - Manager  : chỉ được xóa thông báo của chính mình.
        - HR/Admin : có thể xóa bất kỳ thông báo nào.
    """
    from app.models.notification import Notification      # Import muộn tránh circular
    from app.models.overtime_request import OvertimeRequest       # Import muộn tránh circular

    user             = g.user
    current_employee = g.employee
    role             = user.role.name

    # ── 1. Tìm thông báo ─────────────────────────────────────────────────
    notification = Notification.query.filter_by(
        id=notification_id, is_deleted=False
    ).first()

    if not notification:
        return _swal_not_found("Không tìm thấy thông báo")

    # ── 2. Kiểm tra quyền sở hữu ─────────────────────────────────────────
    is_hr_or_admin = role in [RoleName.ADMIN, RoleName.HR]

    if not is_hr_or_admin:
        # Employee và Manager chỉ được xóa thông báo của chính mình
        owner_employee_id = getattr(notification, "employee_id", None)
        if owner_employee_id and int(owner_employee_id) != current_employee.id:
            return _swal_forbidden("Bạn không có quyền xóa thông báo này")

    # ── 3. Cascade: Hủy OvertimeRequest liên quan (nếu có) ───────────────
    cancelled_ot_id = None
    ot_ref_id = getattr(notification, "overtime_request_id", None)

    if ot_ref_id:
        ot_request = OvertimeRequest.query.filter_by(
            id=ot_ref_id, is_deleted=False
        ).first()

        if ot_request:
            # Chỉ hủy nếu OT đang ở trạng thái chờ duyệt (pending)
            ot_status = getattr(ot_request, "status", None)
            if ot_status == "pending":
                ot_request.status     = "cancelled"
                cancelled_ot_id       = ot_request.id
            # Nếu đã duyệt/từ chối thì chỉ xóa thông báo, không động vào OT

    # ── 4. Soft delete thông báo ──────────────────────────────────────────
    notification.is_deleted = True
    db.session.commit()

    # ── 5. Phản hồi ──────────────────────────────────────────────────────
    if cancelled_ot_id:
        return {
            "swal": {
                "icon": "success",
                "title": "Đã xóa thông báo",
                "text": (
                    f"Thông báo #{notification_id} đã được xóa. "
                    f"Yêu cầu tăng ca #{cancelled_ot_id} đã bị hủy kèm theo."
                ),
            },
            "deleted": {
                "notification_id":    notification_id,
                "cancelled_overtime": cancelled_ot_id,
            },
        }, HTTPStatus.OK

    return {
        "swal": {
            "icon": "success",
            "title": "Đã xóa thông báo",
            "text": f"Thông báo #{notification_id} đã được xóa thành công.",
            "timer": 1800,
            "showConfirmButton": False,
        },
        "deleted": {
            "notification_id":    notification_id,
            "cancelled_overtime": None,
        },
    }, HTTPStatus.OK