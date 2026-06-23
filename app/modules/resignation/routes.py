from datetime import date
from flask import request, jsonify, g, render_template

from app.common.exceptions import ForbiddenError, NotFoundError
from app.common.security.decorators import auth_required, role_required
from app.common.security.permissions import is_manager_of
from app.constants.common import RoleName
from app.constants.resignation import ResignationStatus, ResignationType
from app.extensions.db import db
from app.models import Employee
from app.models.resignation import ResignationRequest
from app.modules.resignation import resignation_bp
from app.modules.resignation.resignation_service import ResignationService

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _swal_ok(message: str, data: dict | None = None, status_code: int = 200):
    """Chuẩn phản hồi thành công – frontend đọc payload.swal để hiện SweetAlert2."""
    payload = {
        "swal": {
            "icon": "success",
            "title": "Thành công",
            "text": message,
        },
        "status": "success",
        "message": message,
    }
    if data:
        payload["data"] = data
    return jsonify(payload), status_code


def _swal_error(message: str, status_code: int = 400):
    """Chuẩn phản hồi lỗi – frontend đọc payload.swal để hiện SweetAlert2."""
    payload = {
        "swal": {
            "icon": "error",
            "title": "Lỗi",
            "text": message,
        },
        "status": "error",
        "message": message,
    }
    return jsonify(payload), status_code


def _get_resignation_or_404(resignation_id: int) -> ResignationRequest:
    item = ResignationRequest.query.filter_by(
        id=resignation_id, is_deleted=False
    ).first()
    if not item:
        raise NotFoundError("Không tìm thấy đơn nghỉ việc")
    return item


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"Ngày không hợp lệ: '{value}'. Định dạng yêu cầu: YYYY-MM-DD")


# ─────────────────────────────────────────────
# 1. POST /api/resignation/submit
# ─────────────────────────────────────────────

@resignation_bp.route("/submit", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE, RoleName.MANAGER)
def submit_resignation():
    """
    Nhân viên tự gửi đơn xin nghỉ việc.
    Body JSON:
        expected_last_day    (str YYYY-MM-DD, bắt buộc)
        reason_category      (str, bắt buộc)
        reason_text          (str, tuỳ chọn)
        extra_note           (str, tuỳ chọn)
        attachment_url       (str, tuỳ chọn)
        handover_employee_id (int, tuỳ chọn)
        request_type         (str, tuỳ chọn – mặc định "employee")
    """
    try:
        body = request.get_json(silent=True) or {}
        employee: Employee = g.employee

        expected_last_day = _parse_date(body.get("expected_last_day"))
        reason_category = (body.get("reason_category") or "").strip()
        if not reason_category:
            return _swal_error("Vui lòng chọn lý do nghỉ việc.")

        resignation = ResignationService.create_request(
            employee=employee,
            request_type=body.get("request_type", ResignationType.EMPLOYEE),
            expected_last_day=expected_last_day,
            reason_category=reason_category,
            reason_text=(body.get("reason_text") or "").strip() or None,
            extra_note=(body.get("extra_note") or "").strip() or None,
            attachment_url=(body.get("attachment_url") or "").strip() or None,
            handover_employee_id=body.get("handover_employee_id"),
        )
        return _swal_ok(
            "Đơn nghỉ việc đã được gửi thành công.",
            {"resignation": resignation.to_dict()},
            201,
        )

    except ValueError as exc:
        return _swal_error(str(exc))
    except Exception as exc:
        return _swal_error(f"Đã xảy ra lỗi: {str(exc)}", 500)


# ─────────────────────────────────────────────
# 2. POST /api/resignation/propose
# ─────────────────────────────────────────────

@resignation_bp.route("/propose", methods=["POST"])
@auth_required
@role_required(RoleName.MANAGER)
def propose_resignation():
    """
    Manager / HR / Admin đề xuất nghỉ việc cho một nhân viên.
    Body JSON:
        employee_id          (int, bắt buộc)
        expected_last_day    (str YYYY-MM-DD, bắt buộc)
        reason_category      (str, bắt buộc)
        reason_text          (str, tuỳ chọn)
        extra_note           (str, tuỳ chọn)
        attachment_url       (str, tuỳ chọn)
        handover_employee_id (int, tuỳ chọn)
    """
    try:
        body = request.get_json(silent=True) or {}
        current_user = g.user
        manager_employee: Employee = g.employee

        employee_id = body.get("employee_id")
        if not employee_id:
            return _swal_error("Thiếu thông tin employee_id.")

        # Manager chỉ được đề xuất cho nhân viên trực thuộc
        if current_user.role.name == RoleName.MANAGER:
            if not is_manager_of(employee_id):
                raise ForbiddenError("Bạn không có quyền đề xuất nghỉ cho nhân viên này.")

        target_employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first()
        if not target_employee:
            return _swal_error("Không tìm thấy nhân viên.", 404)

        expected_last_day = _parse_date(body.get("expected_last_day"))
        reason_category = (body.get("reason_category") or "").strip()
        if not reason_category:
            return _swal_error("Vui lòng chọn lý do nghỉ việc.")

        resignation = ResignationService.create_proposal_by_manager(
            manager=manager_employee,
            employee=target_employee,
            request_type=ResignationType.MANAGER_PROPOSAL,
            expected_last_day=expected_last_day,
            reason_category=reason_category,
            reason_text=(body.get("reason_text") or "").strip() or None,
            extra_note=(body.get("extra_note") or "").strip() or None,
            attachment_url=(body.get("attachment_url") or "").strip() or None,
            handover_employee_id=body.get("handover_employee_id"),
        )
        return _swal_ok(
            f"Đã đề xuất nghỉ việc cho {target_employee.full_name}.",
            {"resignation": resignation.to_dict()},
            201,
        )

    except ForbiddenError as exc:
        return _swal_error(str(exc), 403)
    except ValueError as exc:
        return _swal_error(str(exc))
    except Exception as exc:
        return _swal_error(f"Đã xảy ra lỗi: {str(exc)}", 500)


# ─────────────────────────────────────────────
# 3. PATCH /api/resignation/<id>/manager-review
# ─────────────────────────────────────────────

@resignation_bp.route("/<int:resignation_id>/manager-review", methods=["PATCH"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.ADMIN)
def manager_review(resignation_id: int):
    """
    Manager duyệt hoặc từ chối đơn nghỉ việc.
    Body JSON:
        action  ("approve" | "reject", bắt buộc)
        note    (str, tuỳ chọn)
    """
    try:
        body = request.get_json(silent=True) or {}
        current_user = g.user
        resignation = _get_resignation_or_404(resignation_id)

        if current_user.role.name == RoleName.MANAGER:
            if not is_manager_of(resignation.employee_id):
                raise ForbiddenError("Bạn không có quyền duyệt đơn này.")

        action = (body.get("action") or "").strip()
        if action not in ("approve", "reject"):
            return _swal_error("Hành động không hợp lệ. Chỉ chấp nhận 'approve' hoặc 'reject'.")

        ResignationService.manager_review(
            request_item=resignation,
            manager_user_id=current_user.id,
            action=action,
            note=(body.get("note") or "").strip() or None,
        )

        msg = "Đã duyệt đơn nghỉ việc." if action == "approve" else "Đã từ chối đơn nghỉ việc."
        return _swal_ok(msg, {"resignation": resignation.to_dict()})

    except ForbiddenError as exc:
        return _swal_error(str(exc), 403)
    except ValueError as exc:
        return _swal_error(str(exc))
    except Exception as exc:
        return _swal_error(f"Đã xảy ra lỗi: {str(exc)}", 500)


# ─────────────────────────────────────────────
# 4. PATCH /api/resignation/<id>/hr-process
# ─────────────────────────────────────────────

@resignation_bp.route("/<int:resignation_id>/hr-process", methods=["PATCH"])
@auth_required
@role_required(RoleName.HR, RoleName.ADMIN)
def hr_process(resignation_id: int):
    """
    HR xử lý offboarding checklist, sau đó chuyển Admin hoặc từ chối.
    Body JSON:
        action                ("forward_admin" | "reject", bắt buộc)
        hr_note               (str, tuỳ chọn)
        final_payroll_note    (str, tuỳ chọn)
        final_attendance_note (str, tuỳ chọn)
        leave_balance_note    (str, tuỳ chọn)
        insurance_note        (str, tuỳ chọn)
        asset_handover_note   (str, tuỳ chọn)
    """
    try:
        body = request.get_json(silent=True) or {}
        current_user = g.user
        resignation = _get_resignation_or_404(resignation_id)

        action = (body.get("action") or "").strip()
        if action not in ("forward_admin", "reject"):
            return _swal_error("Hành động không hợp lệ. Chỉ chấp nhận 'forward_admin' hoặc 'reject'.")

        ResignationService.hr_process(
            request_item=resignation,
            hr_user_id=current_user.id,
            action=action,
            payload=body,
        )

        msg = (
            "Đã hoàn tất offboarding checklist và chuyển Admin duyệt."
            if action == "forward_admin"
            else "Đã từ chối hồ sơ nghỉ việc."
        )
        return _swal_ok(msg, {"resignation": resignation.to_dict()})

    except ValueError as exc:
        return _swal_error(str(exc))
    except Exception as exc:
        return _swal_error(f"Đã xảy ra lỗi: {str(exc)}", 500)


# ─────────────────────────────────────────────
# 5. PATCH /api/resignation/<id>/admin-finalize
# ─────────────────────────────────────────────

@resignation_bp.route("/<int:resignation_id>/admin-finalize", methods=["PATCH"])
@auth_required
@role_required(RoleName.ADMIN)
def admin_finalize(resignation_id: int):
    """
    Admin phê duyệt cuối hoặc từ chối; nếu approve sẽ khoá tài khoản nhân viên.
    Body JSON:
        action  ("approve" | "reject", bắt buộc)
        note    (str, tuỳ chọn)
    """
    try:
        body = request.get_json(silent=True) or {}
        current_user = g.user
        resignation = _get_resignation_or_404(resignation_id)

        action = (body.get("action") or "").strip()
        if action not in ("approve", "reject"):
            return _swal_error("Hành động không hợp lệ. Chỉ chấp nhận 'approve' hoặc 'reject'.")

        ResignationService.admin_finalize(
            request_item=resignation,
            admin_user_id=current_user.id,
            action=action,
            note=(body.get("note") or "").strip() or None,
        )

        msg = (
            "Đã phê duyệt nghỉ việc. Tài khoản nhân viên đã bị khoá."
            if action == "approve"
            else "Đã từ chối đơn nghỉ việc."
        )
        return _swal_ok(msg, {"resignation": resignation.to_dict()})

    except ValueError as exc:
        return _swal_error(str(exc))
    except Exception as exc:
        return _swal_error(f"Đã xảy ra lỗi: {str(exc)}", 500)


# ─────────────────────────────────────────────
# 6. GET /api/resignation/  – Danh sách đơn theo quyền
# ─────────────────────────────────────────────

@resignation_bp.route("/", methods=["GET"])
@auth_required
def list_resignations():
    """
    Danh sách đơn nghỉ việc phân quyền:
      Admin / HR  → toàn bộ đơn
      Manager     → đơn của nhân viên trực thuộc (+ của chính mình)
      Employee    → chỉ đơn của chính mình
    Query params:
        status   (str, tuỳ chọn)
        page     (int, mặc định 1)
        per_page (int, mặc định 20, tối đa 100)
    """
    try:
        current_user = g.user
        current_employee: Employee = g.employee

        status_filter = request.args.get("status")
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))

        query = ResignationRequest.query.filter_by(is_deleted=False)

        if status_filter:
            query = query.filter(ResignationRequest.status == status_filter)

        role_name = current_user.role.name

        if role_name in (RoleName.ADMIN, RoleName.HR):
            pass  # full access
        elif role_name == RoleName.MANAGER:
            sub_ids = [e.id for e in current_employee.subordinates]
            sub_ids.append(current_employee.id)
            query = query.filter(ResignationRequest.employee_id.in_(sub_ids))
        else:
            query = query.filter(ResignationRequest.employee_id == current_employee.id)

        pagination = query.order_by(ResignationRequest.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            "status": "success",
            "data": {
                "items": [r.to_dict() for r in pagination.items],
                "total": pagination.total,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "pages": pagination.pages,
            },
        }), 200

    except Exception as exc:
        return _swal_error(f"Đã xảy ra lỗi: {str(exc)}", 500)


# ─────────────────────────────────────────────
# 7. GET /api/resignation/<id>  – Chi tiết một đơn
# ─────────────────────────────────────────────

@resignation_bp.route("/<int:resignation_id>", methods=["GET"])
@auth_required
def get_resignation(resignation_id: int):
    """
    Chi tiết đơn nghỉ việc, phân quyền tương tự danh sách.
    """
    try:
        current_user = g.user
        current_employee: Employee = g.employee
        resignation = _get_resignation_or_404(resignation_id)

        role_name = current_user.role.name
        if role_name in (RoleName.ADMIN, RoleName.HR):
            pass
        elif role_name == RoleName.MANAGER:
            if (
                not is_manager_of(resignation.employee_id)
                and resignation.employee_id != current_employee.id
            ):
                raise ForbiddenError("Bạn không có quyền xem đơn này.")
        else:
            if resignation.employee_id != current_employee.id:
                raise ForbiddenError("Bạn không có quyền xem đơn này.")

        return jsonify({"status": "success", "data": resignation.to_dict()}), 200

    except ForbiddenError as exc:
        return _swal_error(str(exc), 403)
    except Exception as exc:
        return _swal_error(f"Đã xảy ra lỗi: {str(exc)}", 500)
    
"""
Phần bổ sung vào routes.py của module resignation.
Thêm các route render template (GET pages).
Dán vào cuối file routes.py hiện tại.
"""
# ─────────────────────────────────────────────
# PAGE: /resignation/my-list   (Nhân viên xem đơn của mình)
# ─────────────────────────────────────────────

@resignation_bp.route("/my-list", methods=["GET"])
@auth_required
def my_list():
    return render_template("modules/resignation/my_list.html")


# ─────────────────────────────────────────────
# PAGE: /resignation/          (Manager / HR / Admin xem tất cả)
# ─────────────────────────────────────────────

@resignation_bp.route("/all", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.HR, RoleName.ADMIN)
def list_all():
    return render_template("modules/resignation/list_all.html")


# ─────────────────────────────────────────────
# PAGE: /resignation/submit-form
# ─────────────────────────────────────────────

@resignation_bp.route("/submit-form", methods=["GET"])
@auth_required
@role_required(RoleName.EMPLOYEE, RoleName.MANAGER)
def submit_form():
    current_employee: Employee = g.employee
    # Lấy danh sách đồng nghiệp để chọn bàn giao (cùng phòng ban, trừ chính mình)
    handover_candidates = (
        Employee.query
        .filter(
            Employee.department_id == current_employee.department_id,
            Employee.id != current_employee.id,
            Employee.is_deleted == False,
        )
        .all()
    )
    return render_template(
        "modules/resignation/submit_form.html",
        today_iso=date.today().isoformat(),
        handover_candidates=handover_candidates,
    )


# ─────────────────────────────────────────────
# PAGE: /resignation/propose-form   (Manager đề xuất)
# ─────────────────────────────────────────────

@resignation_bp.route("/propose-form", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def propose_form():
    manager_employee: Employee = g.employee
    subordinates = manager_employee.subordinates or []

    # Ứng viên bàn giao: cùng phòng ban, không phải subordinate này
    handover_candidates = (
        Employee.query
        .filter(
            Employee.department_id == manager_employee.department_id,
            Employee.is_deleted == False,
        )
        .all()
    )
    return render_template(
        "modules/resignation/propose_form.html",
        today_iso=date.today().isoformat(),
        subordinates=subordinates,
        handover_candidates=handover_candidates,
    )


# ─────────────────────────────────────────────
# PAGE: /resignation/<id>      (Chi tiết đơn)
# ─────────────────────────────────────────────

@resignation_bp.route("/<int:resignation_id>/detail", methods=["GET"])
@auth_required
def resignation_detail_page(resignation_id: int):
    from app.common.exceptions import ForbiddenError, NotFoundError
    from app.common.security.permissions import is_manager_of
    from app.models.resignation import ResignationRequest

    current_user = g.user
    current_employee: Employee = g.employee

    item = ResignationRequest.query.filter_by(id=resignation_id, is_deleted=False).first()
    if not item:
        return render_template("errors/404.html"), 404

    role_name = current_user.role.name
    if role_name in (RoleName.ADMIN, RoleName.HR):
        pass
    elif role_name == RoleName.MANAGER:
        if not is_manager_of(item.employee_id) and item.employee_id != current_employee.id:
            return render_template("errors/403.html"), 403
    else:
        if item.employee_id != current_employee.id:
            return render_template("errors/403.html"), 403

    return render_template("modules/resignation/detail.html", resignation=item)

@resignation_bp.route("/my-requests")
@auth_required
def render_my_list():
    """Render trang danh sách các đơn xin nghỉ việc của người dùng hiện tại."""
    return render_template("modules/resignation/my_list.html", title="Đơn xin nghỉ việc của tôi")

@resignation_bp.route("/submit")
@auth_required
def render_submit_form():
    """Render form để nhân viên tự gửi đơn xin nghỉ việc."""
    return render_template("modules/resignation/submit_form.html", title="Gửi đơn nghỉ việc")

@resignation_bp.route("/<int:request_id>")
@auth_required
def render_detail(request_id):
    """Render trang chi tiết của một đơn xin nghỉ việc cụ thể."""
    return render_template("modules/resignation/detail.html", title="Chi tiết đơn nghỉ việc", request_id=request_id)

@resignation_bp.route("/propose")
def render_propose_form():
    """Render form cho Manager đề xuất cho nhân viên nghỉ việc."""
    return render_template("modules/resignation/propose_form.html", title="Đề xuất cho nhân viên nghỉ việc")

@resignation_bp.route("/all-requests")
def render_list_all():
    """Render trang quản lý tất cả các đơn xin nghỉ việc cho HR/Admin."""
    return render_template("modules/resignation/list_all.html", title="Quản lý đơn thôi việc")
