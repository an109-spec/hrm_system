from flask import request, jsonify, g

from app.modules.personnel import personnel_bp
from app.modules.personnel.profile_service import ProfileService
from app.modules.personnel.dependent_service import EmployeeDependentService
from app.modules.personnel.dto import UpdateProfileDTO, ChangePasswordDTO
from app.modules.personnel.validators import validate_update_profile, validate_change_password
from app.common.security.decorators import auth_required, self_or_hr_required
from app.common.exceptions import NotFoundError, UnauthorizedError, ValidationError


# ===========================================================================
# 🔧 HELPER: Chuẩn hoá response trả về dạng SweetAlert2 (Swal)
# ===========================================================================

from app.common.responses import swal_success, swal_error, swal_warning

# ===========================================================================
# 👤 PROFILE ROUTES — /personnel/profile
# Tất cả 4 actor (Admin, HR, Manager, Employee) đều truy cập được.
# Mỗi người chỉ xem/sửa thông tin của chính mình,
# Admin và HR có thể xem/sửa của người khác qua employee_id.
# ===========================================================================

@personnel_bp.route("/profile/me", methods=["GET"])
@auth_required
def get_my_profile():
    """
    Lấy thông tin hồ sơ cá nhân của chính mình.
    Tất cả actor đều có quyền truy cập.
    """
    try:
        profile = ProfileService.get_profile(user_id=g.user.id)
        return jsonify({"data": profile}), 200
    except NotFoundError as e:
        return swal_error(title="Không tìm thấy", message=str(e), status_code=404)
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@personnel_bp.route("/profile/<int:employee_id>", methods=["GET"])
@auth_required
@self_or_hr_required(employee_id_key="employee_id")
def get_profile_by_id(employee_id):
    """
    Lấy hồ sơ nhân viên theo employee_id.
    - Nhân viên chỉ xem được của chính mình.
    - Admin / HR xem được của tất cả.
    """
    try:
        profile = ProfileService.get_profile(employee_id=employee_id)
        return jsonify({"data": profile}), 200
    except NotFoundError as e:
        return swal_error(title="Không tìm thấy", message=str(e), status_code=404)
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@personnel_bp.route("/profile/me", methods=["PUT"])
@auth_required
def update_my_profile():
    """
    Cập nhật thông tin cá nhân của chính mình.
    Tất cả actor đều có quyền tự cập nhật hồ sơ của mình.
    """
    try:
        dto = UpdateProfileDTO(request.get_json(silent=True) or {})
        validate_update_profile(dto)
        result = ProfileService.update_profile(user_id=g.user.id, dto=dto)
        return swal_success(
            title=result.get("title", "Thành công"),
            message=result.get("message", "Thông tin đã được cập nhật."),
            data=result.get("data")
        )
    except ValidationError as e:
        return swal_warning(title="Dữ liệu không hợp lệ", message=str(e))
    except NotFoundError as e:
        return swal_error(title="Không tìm thấy", message=str(e), status_code=404)
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@personnel_bp.route("/profile/<int:employee_id>", methods=["PUT"])
@auth_required
@self_or_hr_required(employee_id_key="employee_id")
def update_profile_by_id(employee_id):
    """
    Admin / HR cập nhật hồ sơ nhân viên theo employee_id.
    Nhân viên chỉ có thể sửa của chính mình (đã kiểm soát bởi self_or_hr_required).
    """
    try:


        dto = UpdateProfileDTO(request.get_json(silent=True) or {})
        validate_update_profile(dto)
        result = ProfileService.update_profile_by_employee_id(employee_id=employee_id, dto=dto)
        return swal_success(
            title=result.get("title", "Thành công"),
            message=result.get("message", "Thông tin đã được cập nhật."),
            data=result.get("data")
        )
    except ValidationError as e:
        return swal_warning(title="Dữ liệu không hợp lệ", message=str(e))
    except NotFoundError as e:
        return swal_error(title="Không tìm thấy", message=str(e), status_code=404)
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


# ===========================================================================
# 🔑 PASSWORD — /personnel/profile/change-password
# ===========================================================================

@personnel_bp.route("/profile/change-password", methods=["POST"])
@auth_required
def change_password():
    """
    Đổi mật khẩu cho chính tài khoản đang đăng nhập.
    Tất cả 4 actor đều có quyền thực hiện.
    """
    try:
        dto = ChangePasswordDTO(request.get_json(silent=True) or {})
        validate_change_password(dto)
        result = ProfileService.change_password(user_id=g.user.id, dto=dto)
        return swal_success(
            title=result.get("title", "Đổi mật khẩu thành công!"),
            message=result.get("message", "Mật khẩu đã được cập nhật.")
        )
    except ValidationError as e:
        return swal_warning(title="Kiểm tra lại thông tin", message=str(e))
    except UnauthorizedError as e:
        return swal_error(title="Xác thực thất bại", message=str(e), status_code=401)
    except NotFoundError as e:
        return swal_error(title="Không tìm thấy tài khoản", message=str(e), status_code=404)
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


# ===========================================================================
# 🖼️ AVATAR — /personnel/profile/avatar
# ===========================================================================

@personnel_bp.route("/profile/me/avatar", methods=["POST"])
@auth_required
def update_my_avatar():
    """
    Nhân viên tự cập nhật ảnh đại diện của mình.
    Tất cả actor đều có quyền.
    """
    try:
        file = request.files.get("avatar")
        result = ProfileService.update_avatar(
            employee_id=g.employee.id,
            file=file,
            actor_user_id=g.user.id
        )
        return swal_success(
            title="Cập nhật thành công",
            message="Ảnh đại diện đã được cập nhật.",
            data={"avatar": result.get("avatar")}
        )
    except ValueError as e:
        return swal_warning(title="File không hợp lệ", message=str(e))
    except NotFoundError as e:
        return swal_error(title="Không tìm thấy", message=str(e), status_code=404)
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@personnel_bp.route("/profile/<int:employee_id>/avatar", methods=["POST"])
@auth_required
@self_or_hr_required(employee_id_key="employee_id")
def update_avatar_by_id(employee_id):
    """
    Admin / HR cập nhật ảnh đại diện cho nhân viên theo employee_id.
    """
    try:
        file = request.files.get("avatar")
        result = ProfileService.update_avatar(
            employee_id=employee_id,
            file=file,
            actor_user_id=g.user.id
        )
        return swal_success(
            title="Cập nhật thành công",
            message="Ảnh đại diện đã được cập nhật.",
            data={"avatar": result.get("avatar")}
        )
    except ValueError as e:
        return swal_warning(title="File không hợp lệ", message=str(e))
    except NotFoundError as e:
        return swal_error(title="Không tìm thấy", message=str(e), status_code=404)
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


# ===========================================================================
# 📋 HISTORY — /personnel/profile/history
# ===========================================================================

@personnel_bp.route("/profile/me/history", methods=["GET"])
@auth_required
def get_my_history():
    """
    Lấy lịch sử hoạt động của chính mình.
    Tất cả actor đều có quyền xem lịch sử của mình.
    """
    try:
        logs = ProfileService.get_history(employee_id=g.employee.id)
        return jsonify({"data": logs}), 200
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@personnel_bp.route("/profile/<int:employee_id>/history", methods=["GET"])
@auth_required
@self_or_hr_required(employee_id_key="employee_id")
def get_history_by_id(employee_id):
    """
    Admin / HR xem lịch sử hoạt động của nhân viên theo employee_id.
    """
    try:
        logs = ProfileService.get_history(employee_id=employee_id)
        return jsonify({"data": logs}), 200
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


# ===========================================================================
# 👨‍👩‍👧 DEPENDENT ROUTES — /personnel/profile/dependents
# Quản lý người phụ thuộc (để tính giảm trừ gia cảnh thuế TNCN).
# ===========================================================================

@personnel_bp.route("/profile/me/dependents", methods=["GET"])
@auth_required
def get_my_dependents():
    """
    Lấy danh sách người phụ thuộc của chính mình.
    """
    try:
        result = EmployeeDependentService.list_dependents(employee=g.employee)
        return jsonify({"data": result}), 200
    except ValueError as e:
        return swal_error(title="Không hợp lệ", message=str(e))
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@personnel_bp.route("/profile/<int:employee_id>/dependents", methods=["GET"])
@auth_required
@self_or_hr_required(employee_id_key="employee_id")
def get_dependents_by_id(employee_id):
    """
    Admin / HR xem danh sách người phụ thuộc của nhân viên.
    """
    try:
        result = EmployeeDependentService.list_dependents_by_employee_id(employee_id=employee_id)
        return jsonify({"data": result}), 200
    except ValueError as e:
        return swal_error(title="Không hợp lệ", message=str(e))
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@personnel_bp.route("/profile/me/dependents", methods=["POST"])
@auth_required
def create_my_dependent():
    """
    Thêm người phụ thuộc cho chính mình.
    """
    try:
        payload = request.get_json(silent=True) or {}
        result = EmployeeDependentService.create_dependent(
            employee=g.employee,
            payload=payload,
            actor_user_id=g.user.id
        )
        return swal_success(
            title="Thêm thành công",
            message=result.get("message", "Đã thêm người phụ thuộc."),
            data=result.get("item"),
            status_code=201
        )
    except ValueError as e:
        return swal_warning(title="Dữ liệu không hợp lệ", message=str(e))
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@personnel_bp.route("/profile/<int:employee_id>/dependents", methods=["POST"])
@auth_required
@self_or_hr_required(employee_id_key="employee_id")
def create_dependent_by_id(employee_id):
    """
    Admin / HR thêm người phụ thuộc cho nhân viên.
    """
    try:

        payload = request.get_json(silent=True) or {}
        result = EmployeeDependentService.create_dependent_by_employee_id(
            employee_id=employee_id,
            payload=payload,
            actor_user_id=g.user.id
        )
        return swal_success(
            title="Thêm thành công",
            message=result.get("message", "Đã thêm người phụ thuộc."),
            data=result.get("item"),
            status_code=201
        )
    except ValueError as e:
        return swal_warning(title="Dữ liệu không hợp lệ", message=str(e))
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@personnel_bp.route("/profile/me/dependents/<int:dependent_id>", methods=["PUT"])
@auth_required
def update_my_dependent(dependent_id):
    """
    Cập nhật thông tin người phụ thuộc của chính mình.
    """
    try:
        payload = request.get_json(silent=True) or {}
        result = EmployeeDependentService.update_dependent(
            employee=g.employee,
            dependent_id=dependent_id,
            payload=payload,
            actor_user_id=g.user.id
        )
        return swal_success(
            title="Cập nhật thành công",
            message=result.get("message", "Đã cập nhật thông tin người phụ thuộc."),
            data=result.get("item")
        )
    except ValueError as e:
        return swal_warning(title="Dữ liệu không hợp lệ", message=str(e))
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@personnel_bp.route("/profile/<int:employee_id>/dependents/<int:dependent_id>", methods=["PUT"])
@auth_required
@self_or_hr_required(employee_id_key="employee_id")
def update_dependent_by_id(employee_id, dependent_id):
    """
    Admin / HR cập nhật thông tin người phụ thuộc của nhân viên.
    """
    try:

        payload = request.get_json(silent=True) or {}
        result = EmployeeDependentService.update_dependent_by_employee_id(
            employee_id=employee_id,
            dependent_id=dependent_id,
            payload=payload,
            actor_user_id=g.user.id
        )
        return swal_success(
            title="Cập nhật thành công",
            message=result.get("message", "Đã cập nhật thông tin người phụ thuộc."),
            data=result.get("item")
        )
    except ValueError as e:
        return swal_warning(title="Dữ liệu không hợp lệ", message=str(e))
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@personnel_bp.route("/profile/me/dependents/<int:dependent_id>", methods=["DELETE"])
@auth_required
def delete_my_dependent(dependent_id):
    """
    Xóa người phụ thuộc của chính mình.
    Lưu ý: Không thể xóa nếu đã được chốt trong bảng lương.
    """
    try:
        result = EmployeeDependentService.delete_dependent(
            employee=g.employee,
            dependent_id=dependent_id,
            actor_user_id=g.user.id
        )
        return swal_success(
            title="Đã xóa",
            message=result.get("message", "Người phụ thuộc đã được xóa khỏi hồ sơ.")
        )
    except ValueError as e:
        return swal_warning(title="Không thể xóa", message=str(e))
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@personnel_bp.route("/profile/<int:employee_id>/dependents/<int:dependent_id>", methods=["DELETE"])
@auth_required
@self_or_hr_required(employee_id_key="employee_id")
def delete_dependent_by_id(employee_id, dependent_id):
    """
    Admin / HR xóa người phụ thuộc của nhân viên.
    """
    try:
        result = EmployeeDependentService.delete_dependent_by_employee_id(
            employee_id=employee_id,
            dependent_id=dependent_id,
            actor_user_id=g.user.id
        )
        return swal_success(
            title="Đã xóa",
            message=result.get("message", "Người phụ thuộc đã được xóa khỏi hồ sơ.")
        )
    except ValueError as e:
        return swal_warning(title="Không thể xóa", message=str(e))
    except Exception as e:
        return swal_error(message=str(e), status_code=500)
    
from flask import Blueprint, g, jsonify, render_template
from app.common.security.decorators import auth_required

@personnel_bp.route("/profile")
@auth_required
def render_my_profile():
    """Render trang hồ sơ cá nhân của người dùng đang đăng nhập."""
    return render_template("modules/personnel/profile.html", title="Hồ sơ của tôi")

@personnel_bp.route("/profile/edit")
@auth_required
def render_edit_profile():
    """Render trang chỉnh sửa hồ sơ cá nhân."""
    return render_template("modules/personnel/edit_profile.html", title="Chỉnh sửa hồ sơ")

@personnel_bp.route("/profile/change-password")
@auth_required
def render_change_password():
    """Render trang để người dùng thay đổi mật khẩu."""
    return render_template("modules/personnel/change_password.html", title="Đổi mật khẩu")

@personnel_bp.route("/profile/dependents")
@auth_required
def render_dependents_list():
    """Render trang danh sách người phụ thuộc của người dùng."""
    return render_template("modules/personnel/dependents_list.html", title="Người phụ thuộc")

@personnel_bp.route("/profile/dependents/form")
@auth_required
def render_dependent_form():
    """Render form để thêm hoặc chỉnh sửa người phụ thuộc."""
    return render_template("modules/personnel/dependent_form.html", title="Thêm/Sửa người phụ thuộc")

@personnel_bp.route("/profile/activity")
@auth_required
def render_activity_history():
    """Render trang lịch sử hoạt động của người dùng."""
    return render_template("modules/personnel/activity_history.html", title="Lịch sử hoạt động")

@personnel_bp.route("/employees")
def render_employee_list():
    """Render trang danh sách toàn bộ nhân viên."""
    return render_template("modules/personnel/employee_list.html", title="Danh sách nhân viên")

@personnel_bp.route("/employees/<int:employee_id>")
def render_employee_profile(employee_id):
    """Render trang hồ sơ của một nhân viên cụ thể."""
    return render_template("modules/personnel/profile.html", title="Hồ sơ nhân viên", employee_id=employee_id)
