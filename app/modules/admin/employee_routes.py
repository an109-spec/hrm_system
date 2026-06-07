from flask import request, jsonify, g
from . import admin_bp
from app.modules.admin.employee_service import Employee_service
from app.common.security.decorators import auth_required, role_required
from app.common.exceptions import NotFoundError, ValidationError
from app.constants.common import RoleName


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def swal_success(title: str, message: str, data=None, status_code: int = 200):
    """Response thành công theo chuẩn SweetAlert2."""
    payload = {
        "swal": {
            "icon": "success",
            "title": title,
            "text": message,
        },
        "success": True,
    }
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status_code


def swal_error(title: str, message: str, status_code: int = 400):
    """Response lỗi theo chuẩn SweetAlert2."""
    payload = {
        "swal": {
            "icon": "error",
            "title": title,
            "text": message,
        },
        "success": False,
    }
    return jsonify(payload), status_code


def user_to_dict(user) -> dict:
    """Serialize User object sang dict gọn gàng."""
    emp = user.employee_profile
    return {
        "user_id": user.id,
        "email": user.email,
        "username": getattr(user, "username", None),
        "is_active": user.is_active,
        "locked_at": user.locked_at.isoformat() if user.locked_at else None,
        "lock_reason": user.lock_reason,
        "role": user.role.name if user.role else None,
        "employee_id": emp.id if emp else None,
        "employee_name": emp.full_name if emp else None,
    }


# ─────────────────────────────────────────────
# Route 1 – POST /api/admin/users/<user_id>/reset-password
# Reset mật khẩu cho nhân viên
# ─────────────────────────────────────────────

@admin_bp.route("/api/admin/users/<int:user_id>/reset-password", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN)
def reset_employee_password(user_id: int):
    """
    Admin reset mật khẩu cho một tài khoản người dùng.
    Đồng thời xóa trạng thái khóa do nhập sai mật khẩu (nếu có).

    Body JSON:
        new_password (str, bắt buộc) – tối thiểu 8 ký tự
    """
    data = request.get_json(silent=True) or {}
    new_password = (data.get("new_password") or "").strip()

    if not new_password:
        return swal_error(
            "Thiếu thông tin",
            "Vui lòng cung cấp mật khẩu mới ('new_password').",
            400,
        )

    if len(new_password) < 8:
        return swal_error(
            "Mật khẩu không hợp lệ",
            "Mật khẩu mới phải có tối thiểu 8 ký tự.",
            400,
        )

    try:
        Employee_service.reset_employee_password(
            user_id=user_id,
            new_password=new_password,
            actor_id=g.user.id,
        )
        return swal_success(
            "Reset mật khẩu thành công",
            f"Mật khẩu của tài khoản ID {user_id} đã được đặt lại. Trạng thái khóa (nếu có) cũng đã được gỡ bỏ.",
        )

    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except ValidationError as e:
        return swal_error("Dữ liệu không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 2 – POST /api/admin/users/<user_id>/lock
# Khóa tài khoản nhân viên
# ─────────────────────────────────────────────

@admin_bp.route("/api/admin/users/<int:user_id>/lock", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN)
def lock_user_account(user_id: int):
    """
    Admin khóa tài khoản người dùng.
    Nếu tài khoản đã khóa trước đó, trả về thành công mà không thay đổi gì.

    Body JSON:
        reason (str, tuỳ chọn) – lý do khóa tài khoản
    """
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip() or "Khóa bởi Admin"

    try:
        user = Employee_service.lock_user_account(
            user_id=user_id,
            reason=reason,
            performed_by=g.user.id,
        )
        return swal_success(
            "Khóa tài khoản thành công",
            f"Tài khoản ID {user_id} đã bị khóa. Lý do: {reason}",
            data=user_to_dict(user),
        )

    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 3 – POST /api/admin/users/<user_id>/unlock
# Mở khóa tài khoản nhân viên
# ─────────────────────────────────────────────

@admin_bp.route("/api/admin/users/<int:user_id>/unlock", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN)
def unlock_user_account(user_id: int):
    """
    Admin mở khóa tài khoản người dùng.
    Đồng thời reset số lần đăng nhập sai về 0.
    Không cần Body JSON.
    """
    try:
        user = Employee_service.unlock_user_account(
            user_id=user_id,
            performed_by=g.user.id,
        )
        return swal_success(
            "Mở khóa thành công",
            f"Tài khoản ID {user_id} đã được mở khóa và có thể đăng nhập bình thường.",
            data=user_to_dict(user),
        )

    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 4 – GET /api/admin/employees/summary
# Báo cáo tóm tắt nhân sự
# ─────────────────────────────────────────────

@admin_bp.route("/api/admin/employees/summary", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_employee_summary():
    """
    Lấy báo cáo tóm tắt nhân sự: tổng số, đang làm việc,
    thử việc, không hoạt động, hợp đồng sắp hết hạn.
    Hỗ trợ lọc thêm theo Phòng ban, Chức danh, Trạng thái, Loại hợp đồng.

    Query params:
        department_id   (int, tuỳ chọn)
        position_id     (int, tuỳ chọn)
        working_status  (str, tuỳ chọn) – vd: "active", "resigned"
        employment_type (str, tuỳ chọn) – vd: "probation", "official"
    """
    department_id = request.args.get("department_id", type=int)
    position_id = request.args.get("position_id", type=int)
    working_status = request.args.get("working_status")
    employment_type = request.args.get("employment_type")

    try:
        summary = Employee_service.get_employee_summary(
            department_id=department_id,
            position_id=position_id,
            working_status=working_status,
            employment_type=employment_type,
        )
        return swal_success(
            "Thành công",
            "Lấy báo cáo tóm tắt nhân sự thành công.",
            data=summary,
        )

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)