"""
overtime_routes.py
──────────────────
Routes quản lý toàn bộ luồng tăng ca (OT).

Route map:
    GET  /attendance/overtime/requests      → Manager xem danh sách đơn OT chờ duyệt của cấp dưới
    POST /attendance/overtime/request       → Employee đăng ký đơn tăng ca mới
    POST /attendance/overtime/approve       → Manager phê duyệt đơn OT
    POST /attendance/overtime/reject        → Manager từ chối đơn OT
    GET  /attendance/overtime/can-start     → Employee kiểm tra điều kiện trước khi check-in OT
    POST /attendance/overtime/reset         → Admin hủy OT và khôi phục trạng thái chấm công
"""

from flask import request, g
from http import HTTPStatus
from datetime import date

from app.constants.common import RoleName
from app.common.security.decorators import auth_required, role_required
from app.common.exceptions import ValidationError, ForbiddenError
from app.modules.attendance import attendance_bp
from app.modules.attendance.overtime_service import OvertimeService


# ============================================================
# 🔧 HELPERS
# ============================================================

def _ok(icon: str, title: str, text: str, data: dict | None = None,
        timer: int | None = None) -> tuple:
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


# ============================================================
# 1️⃣  GET /attendance/overtime/requests  — Danh sách OT chờ duyệt
# ============================================================

@attendance_bp.route("/overtime/requests", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.HR, RoleName.ADMIN)
def get_overtime_requests():
    """
    Lấy danh sách đơn tăng ca đang chờ duyệt của nhân viên cấp dưới.

    Phân quyền:
        - MANAGER  : Chỉ xem nhân viên trong phòng ban mình quản lý.
        - HR/ADMIN : Có thể truyền manager_id để xem thay cho một Manager cụ thể.

    Query params:
        manager_id (int, optional): HR/Admin truyền để xem thay.
                                    Nếu không truyền → dùng ID người đang đăng nhập.
    """
    user             = g.user
    current_employee = g.employee
    role             = user.role.name

    if role in [RoleName.ADMIN, RoleName.HR]:
        requested_manager_id = request.args.get("manager_id", type=int)
        manager_id = requested_manager_id or current_employee.id
    else:
        manager_id = current_employee.id

    rows = OvertimeService.get_overtime_requests(manager_id=manager_id)

    if not rows:
        return _ok(
            icon="info",
            title="Không có đơn chờ duyệt",
            text="Hiện tại không có đơn tăng ca nào đang chờ phê duyệt.",
            data={"total": 0, "requests": []},
        )

    return _ok(
        icon="success",
        title="Danh sách đơn tăng ca",
        text=f"Tìm thấy {len(rows)} đơn đang chờ phê duyệt.",
        data={"total": len(rows), "requests": rows},
        timer=1500,
    )


# ============================================================
# 2️⃣  POST /attendance/overtime/request  — Đăng ký đơn OT mới
# ============================================================

@attendance_bp.route("/overtime/request", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE, RoleName.MANAGER, RoleName.HR, RoleName.ADMIN)
def create_overtime_request():
    """
    Đăng ký một đơn tăng ca mới.
    Tự động nhận diện ngày lễ/cuối tuần, tính giờ,
    đồng bộ attendance và gửi notification cho Manager.

    Body JSON:
        overtime_date  (str, optional) : Ngày tăng ca YYYY-MM-DD. Mặc định: hôm nay.
        start_time     (str, optional) : Giờ bắt đầu OT HH:MM.   Mặc định: "18:00".
        end_time       (str, optional) : Giờ kết thúc OT HH:MM.  Mặc định: "22:00".
        reason         (str, optional) : Lý do tăng ca.
        note           (str, optional) : Ghi chú thêm.
    """
    body    = request.get_json(silent=True) or {}
    user    = g.user
    user_id = user.id

    try:
        result = OvertimeService.create_overtime_request(
            user_id=user_id,
            payload=body,
            actor_user_id=user_id,
        )
    except (ValueError, ValidationError) as e:
        return _validation_err(str(e))
    except Exception as e:
        return _err("error", "Lỗi hệ thống", str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    data = result.get("data", {})
    return _ok(
        icon="success",
        title="Gửi đơn thành công",
        text=(
            f"Đơn tăng ca ngày {data.get('overtime_date', '')} "
            f"({float(data.get('requested_hours', 0)):.2f} giờ, "
            f"hệ số x{data.get('multiplier', 1)}) đã được gửi. "
            f"Đang chờ Quản lý phê duyệt."
        ),
        data=data,
    )


# ============================================================
# 3️⃣  POST /attendance/overtime/approve  — Phê duyệt đơn OT
# ============================================================

@attendance_bp.route("/overtime/approve", methods=["POST"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.HR, RoleName.ADMIN)
def approve_overtime():
    """
    Phê duyệt đơn tăng ca của nhân viên cấp dưới.
    Manager bị ràng buộc phòng ban; HR/Admin bypass kiểm tra phòng ban.

    Body JSON:
        overtime_request_id (int, required)       : ID đơn OT cần duyệt.
        approved_hours      (float, optional)     : Số giờ duyệt thực tế.
                                                    Mặc định: requested_hours của đơn.
    """
    body = request.get_json(silent=True) or {}

    ot_id = body.get("overtime_request_id")
    if not ot_id:
        return _bad_request("Vui lòng cung cấp overtime_request_id")
    try:
        ot_id = int(ot_id)
    except (ValueError, TypeError):
        return _bad_request("overtime_request_id phải là số nguyên")

    user             = g.user
    current_employee = g.employee
    role             = user.role.name

    # HR/Admin không bị ràng buộc phòng ban →
    # Truyền approver_id = employee_id của người duyệt,
    # nhưng service.approve_overtime chỉ validate phòng ban khi approver_id được truyền vào
    # và employee đó thực sự là manager của phòng ban.
    # Để HR/Admin bypass: vẫn truyền approver_id của họ nhưng
    # service cần nhân viên đó là manager của phòng ban đó.
    # → Giải pháp: HR/Admin truyền approver_id là manager thực sự nếu cần,
    # hoặc service tự bypass khi role là HR/Admin.
    # Ở đây ta truyền approver_id = current_employee.id luôn,
    # service sẽ validate; nếu HR/Admin không phải manager thì cần
    # service hỗ trợ bypass — ta wrap try/except ValidationError riêng cho HR/Admin.
    approver_id    = current_employee.id
    approved_hours = body.get("approved_hours")

    try:
        result = OvertimeService.approve_overtime(
            request_id=ot_id,
            approver_id=approver_id,
            approved_hours=approved_hours,
        )
    except ValidationError as e:
        err_msg = str(e)
        # HR/Admin bị chặn do không phải manager phòng ban →
        # Cho phép bypass bằng cách gọi handle_ot_approved trực tiếp
        if role in [RoleName.ADMIN, RoleName.HR] and "phòng ban" in err_msg:
            try:
                from app.models.overtime_request import OvertimeRequest
                from app.modules.attendance.attendance_workflow_service import Attendance_workflow_service
                from app.extensions.db import db
                from app.utils.time import get_current_time
                from decimal import Decimal

                ot_req = OvertimeRequest.query.filter_by(id=ot_id, is_deleted=False).first()
                if not ot_req:
                    return _not_found(f"Không tìm thấy đơn tăng ca #{ot_id}")

                now_dt = get_current_time()
                if approved_hours is not None:
                    ot_req.approved_hours = Decimal(str(approved_hours)).quantize(Decimal("0.01"))
                else:
                    ot_req.approved_hours = Decimal(str(ot_req.requested_hours or 0))

                ot_req.approved_by    = approver_id
                ot_req.approved_at    = now_dt
                ot_req.hr_decision_by = approver_id
                ot_req.hr_decision_at = now_dt

                Attendance_workflow_service.handle_ot_approved(ot_req)
                db.session.commit()

                result = {
                    "overtime_status": ot_req.status,
                    "approved_hours":  str(ot_req.approved_hours),
                    "approved_at":     ot_req.approved_at.isoformat(),
                }
            except Exception as inner_e:
                return _err("error", "Lỗi hệ thống", str(inner_e), HTTPStatus.INTERNAL_SERVER_ERROR)
        else:
            return _validation_err(err_msg)
    except Exception as e:
        return _err("error", "Lỗi hệ thống", str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    return _ok(
        icon="success",
        title="Phê duyệt thành công",
        text=(
            f"Đơn tăng ca #{ot_id} đã được phê duyệt "
            f"({result.get('approved_hours', 0)} giờ). "
            f"Nhân viên đã nhận được thông báo."
        ),
        data={
            "overtime_request_id": ot_id,
            "overtime_status":     result.get("overtime_status"),
            "approved_hours":      result.get("approved_hours"),
            "approved_at":         result.get("approved_at"),
        },
    )


# ============================================================
# 4️⃣  POST /attendance/overtime/reject  — Từ chối đơn OT
# ============================================================

@attendance_bp.route("/overtime/reject", methods=["POST"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.HR, RoleName.ADMIN)
def reject_overtime():
    """
    Từ chối đơn tăng ca của nhân viên cấp dưới.
    Khi từ chối: reset dữ liệu OT trong attendance + gửi notification cho nhân viên.

    Body JSON:
        overtime_request_id (int, required) : ID đơn OT cần từ chối.
        reason              (str, optional) : Lý do từ chối.
    """
    body = request.get_json(silent=True) or {}

    ot_id = body.get("overtime_request_id")
    if not ot_id:
        return _bad_request("Vui lòng cung cấp overtime_request_id")
    try:
        ot_id = int(ot_id)
    except (ValueError, TypeError):
        return _bad_request("overtime_request_id phải là số nguyên")

    user             = g.user
    current_employee = g.employee
    role             = user.role.name
    reason           = str(body.get("reason") or "").strip()

    # HR/Admin truyền approver_id=None để bypass kiểm tra phòng ban trong service
    approver_id = None if role in [RoleName.ADMIN, RoleName.HR] else current_employee.id

    try:
        result = OvertimeService.reject_overtime(
            request_id=ot_id,
            reject_reason=reason,
            approver_id=approver_id,
        )
    except ValidationError as e:
        return _validation_err(str(e))
    except Exception as e:
        return _err("error", "Lỗi hệ thống", str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    return _ok(
        icon="success",
        title="Đã từ chối đơn OT",
        text=(
            f"Đơn tăng ca #{ot_id} đã bị từ chối."
            + (f" Lý do: {reason}" if reason else "")
            + " Nhân viên đã nhận được thông báo."
        ),
        data={
            "overtime_request_id": ot_id,
            "overtime_status":     result.get("overtime_status"),
            "rejection_reason":    result.get("rejection_reason"),
            "processed_at":        result.get("processed_at"),
        },
    )


# ============================================================
# 5️⃣  GET /attendance/overtime/can-start  — Kiểm tra điều kiện check-in OT
# ============================================================

@attendance_bp.route("/overtime/can-start", methods=["GET"])
@auth_required
@role_required(RoleName.EMPLOYEE, RoleName.MANAGER, RoleName.HR, RoleName.ADMIN)
def can_start_ot():
    """
    Kiểm tra điều kiện trước khi nhân viên thực hiện check-in OT.
    Frontend dùng để quyết định có hiển thị nút check-in OT hay không.

    Query params:
        target_date  (str, optional) : Ngày kiểm tra YYYY-MM-DD. Mặc định: hôm nay.
        employee_id  (int, optional) : HR/Admin có thể kiểm tra hộ người khác.
    """
    user             = g.user
    current_employee = g.employee
    role             = user.role.name

    # ── Xác định employee cần kiểm tra ───────────────────────────────────
    requested_employee_id = request.args.get("employee_id", type=int)

    if requested_employee_id:
        if role in [RoleName.ADMIN, RoleName.HR]:
            target_employee_id = requested_employee_id
        elif role == RoleName.MANAGER:
            # Manager chỉ kiểm tra được nhân viên trong phòng ban mình
            from app.models.department import Department
            managed_dept = Department.query.filter_by(
                manager_id=current_employee.id, is_deleted=False
            ).first()
            allowed_ids = (
                [e.id for e in managed_dept.employees if not e.is_deleted]
                if managed_dept else [current_employee.id]
            )
            if requested_employee_id not in allowed_ids:
                return _forbidden("Bạn không có quyền kiểm tra trạng thái của nhân viên này")
            target_employee_id = requested_employee_id
        else:
            if requested_employee_id != current_employee.id:
                return _forbidden("Bạn chỉ được kiểm tra trạng thái của chính mình")
            target_employee_id = current_employee.id
    else:
        target_employee_id = current_employee.id

    # ── Parse ngày ────────────────────────────────────────────────────────
    target_date_str = request.args.get("target_date")
    if target_date_str:
        try:
            from datetime import datetime
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except ValueError:
            return _bad_request("Định dạng ngày không hợp lệ. Vui lòng dùng YYYY-MM-DD")
    else:
        target_date = date.today()

    # ── Kiểm tra điều kiện ────────────────────────────────────────────────
    try:
        OvertimeService.can_start_ot(
            employee_id=target_employee_id,
            target_date=target_date,
        )
    except ValidationError as e:
        # Trả về HTTP 200 nhưng can_start=False để frontend dễ xử lý
        return _ok(
            icon="warning",
            title="Chưa thể bắt đầu OT",
            text=str(e),
            data={
                "can_start":   False,
                "employee_id": target_employee_id,
                "target_date": target_date.strftime("%Y-%m-%d"),
                "reason":      str(e),
            },
        )
    except Exception as e:
        return _err("error", "Lỗi hệ thống", str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    return _ok(
        icon="success",
        title="Sẵn sàng bắt đầu OT",
        text=(
            f"Nhân viên #{target_employee_id} đủ điều kiện check-in tăng ca "
            f"ngày {target_date.strftime('%d/%m/%Y')}."
        ),
        data={
            "can_start":   True,
            "employee_id": target_employee_id,
            "target_date": target_date.strftime("%Y-%m-%d"),
        },
        timer=1500,
    )


# ============================================================
# 6️⃣  POST /attendance/overtime/reset  — Hủy OT + khôi phục chấm công
# ============================================================

@attendance_bp.route("/overtime/reset", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def reset_overtime_flow():
    """
    Hủy toàn bộ đơn OT trong ngày và khôi phục trạng thái chấm công về ban đầu.
    Dùng khi cần reset dữ liệu lỗi hoặc hủy hàng loạt. Chỉ Admin và HR.

    Body JSON:
        overtime_request_id    (int, required) : ID đơn OT làm anchor (xác định ngày + nhân viên).
        source                 (str, optional) : Nhãn nguồn reset cho audit log.
                                                 Mặc định: "admin_manual".
        anchor_notification_id (int, optional) : ID notification cần xóa kèm.
    """
    body = request.get_json(silent=True) or {}

    ot_id = body.get("overtime_request_id")
    if not ot_id:
        return _bad_request("Vui lòng cung cấp overtime_request_id")
    try:
        ot_id = int(ot_id)
    except (ValueError, TypeError):
        return _bad_request("overtime_request_id phải là số nguyên")

    from app.models.overtime_request import OvertimeRequest
    ot_request = OvertimeRequest.query.filter_by(
        id=ot_id, is_deleted=False
    ).first()

    if not ot_request:
        return _not_found(f"Không tìm thấy đơn tăng ca #{ot_id}")

    source = str(body.get("source") or "admin_manual").strip()

    anchor_notification_id = body.get("anchor_notification_id")
    if anchor_notification_id:
        try:
            anchor_notification_id = int(anchor_notification_id)
        except (ValueError, TypeError):
            anchor_notification_id = None

    actor_user_id = g.user.id

    try:
        result = OvertimeService.cancel_and_reset_overtime_flow(
            overtime_request=ot_request,
            actor_user_id=actor_user_id,
            source=source,
            anchor_notification_id=anchor_notification_id,
        )
    except ValidationError as e:
        return _validation_err(str(e))
    except Exception as e:
        return _err("error", "Lỗi hệ thống", str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    overtime_date = result.get("overtime_date", "")
    deleted_req   = result.get("deleted_requests", 0)
    deleted_noti  = result.get("deleted_notifications", 0)

    return _ok(
        icon="success",
        title="Reset OT thành công",
        text=(
            f"Đã hủy {deleted_req} đơn tăng ca ngày {overtime_date} "
            f"và xóa {deleted_noti} thông báo liên quan. "
            f"Trạng thái chấm công đã được khôi phục."
        ),
        data={
            "overtime_date":         overtime_date,
            "deleted_requests":      deleted_req,
            "deleted_notifications": deleted_noti,
            "anchor_request_id":     ot_id,
            "source":                source,
        },
    )