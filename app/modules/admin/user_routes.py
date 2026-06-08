from flask import request, jsonify, g
from . import admin_bp
from app.modules.admin.user_service import User_Service
from app.common.security.decorators import auth_required, role_required
from app.common.exceptions import NotFoundError
from app.constants.common import RoleName
from app.common.responses import swal_success, swal_error


def user_to_dict(user) -> dict:
    """Serialize User object sang dict đầy đủ."""
    emp = user.employee_profile
    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "role_id": user.role_id,
        "role_name": user.role.name if user.role else None,
        "employee_id": emp.id if emp else None,
        "employee_name": emp.full_name if emp else None,
        "department_name": emp.department.name if emp and emp.department else None,
        "position_name": emp.position.job_title if emp and emp.position else None,
    }


def role_to_dict(role) -> dict:
    """Serialize Role object sang dict."""
    return {
        "id": role.id,
        "name": role.name,
    }


# ─────────────────────────────────────────────
# Route 1 – POST /api/employees/<employee_id>/account
# Tạo tài khoản hệ thống cho nhân viên
# ─────────────────────────────────────────────

@admin_bp.route("/api/employees/<int:employee_id>/account", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN)
def create_user_for_pending_employee(employee_id: int):
    """
    Tạo tài khoản đăng nhập cho nhân viên đang chờ (pending).
    Điều kiện bắt buộc phía service:
      - Nhân viên phải có Phòng ban & Chức danh
      - Nhân viên chưa có tài khoản (user_id IS NULL)
      - Nhân viên phải có hợp đồng đang active và chưa hết hạn

    Body JSON:
        username  (str, bắt buộc)
        email     (str, bắt buộc)
        password  (str, bắt buộc)
        role_id   (int, bắt buộc) – ID vai trò từ bảng roles
    """
    data = request.get_json(silent=True) or {}

    # Validate đầu vào tối thiểu trước khi gọi service
    missing = [f for f in ("username", "email", "password", "role_id") if not data.get(f)]
    if missing:
        return swal_error(
            "Thiếu thông tin",
            f"Vui lòng cung cấp đầy đủ các trường: {', '.join(missing)}.",
            400,
        )

    username = data["username"].strip()
    email = data["email"].strip()
    password = data["password"]

    if not username:
        return swal_error("Dữ liệu không hợp lệ", "Tên đăng nhập không được để trống.", 400)
    if not email or "@" not in email:
        return swal_error("Dữ liệu không hợp lệ", "Email không hợp lệ.", 400)
    if len(password) < 8:
        return swal_error("Dữ liệu không hợp lệ", "Mật khẩu phải có tối thiểu 8 ký tự.", 400)

    try:
        new_user = User_Service.create_user_for_pending_employee(
            employee_id=employee_id,
            user_data=data,
            current_user_id=g.user.id,
        )
        return swal_success(
            "Tạo tài khoản thành công",
            f"Tài khoản '{new_user.username}' đã được tạo và liên kết với hồ sơ nhân viên.",
            data=user_to_dict(new_user),
            status_code=201,
        )

    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except ValueError as e:
        return swal_error("Không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 2 – PATCH /api/users/<user_id>/role
# Cập nhật vai trò (phân quyền) cho người dùng
# ─────────────────────────────────────────────

@admin_bp.route("/api/users/<int:user_id>/role", methods=["PATCH"])
@auth_required
@role_required(RoleName.ADMIN)
def assign_role_to_user(user_id: int):
    """
    Admin phân quyền / thay đổi vai trò cho một người dùng.
    Vai trò hợp lệ: Admin, HR, Manager, Employee.

    Body JSON:
        role_name (str, bắt buộc) – tên vai trò, vd: "HR", "Manager"
    """
    data = request.get_json(silent=True) or {}
    role_name = (data.get("role_name") or "").strip()

    if not role_name:
        return swal_error(
            "Thiếu thông tin",
            f"Vui lòng cung cấp 'role_name'. Các giá trị hợp lệ: "
            f"{RoleName.ADMIN}, {RoleName.HR}, {RoleName.MANAGER}, {RoleName.EMPLOYEE}.",
            400,
        )

    try:
        user = User_Service.assign_role_to_user(
            user_id=user_id,
            role_name=role_name,
            performed_by=g.user.id,
        )
        return swal_success(
            "Phân quyền thành công",
            f"Tài khoản ID {user_id} đã được gán vai trò '{role_name}'.",
            data=user_to_dict(user),
        )

    except ValueError as e:
        return swal_error("Không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 3 – GET /api/roles
# Lấy danh sách tất cả vai trò khả dụng
# ─────────────────────────────────────────────

@admin_bp.route("/api/roles", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_all_roles():
    """
    Lấy danh sách tất cả vai trò trong hệ thống.
    Dùng để render dropdown phân quyền trên giao diện.
    """
    try:
        roles = User_Service.get_all_roles()
        items = [role_to_dict(r) for r in roles]
        return swal_success(
            "Thành công",
            f"Tìm thấy {len(items)} vai trò.",
            data={"items": items, "total": len(items)},
        )

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)