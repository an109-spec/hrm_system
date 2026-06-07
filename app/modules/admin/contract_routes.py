from flask import request, jsonify, g
from . import admin_bp
from .contract_service import Admin_Service
from app.common.security.decorators import auth_required, role_required
from app.common.exceptions import NotFoundError
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


def employee_to_dict(emp) -> dict:
    """Serialize Employee object sang dict gọn gàng."""
    return {
        "id": emp.id,
        "full_name": emp.full_name,
        "dob": emp.dob.isoformat() if emp.dob else None,
        "gender": emp.gender,
        "phone": emp.phone,
        "address": emp.address,
        "hire_date": emp.hire_date.isoformat() if emp.hire_date else None,
        "employment_type": emp.employment_type,
        "working_status": emp.working_status,
        "department_id": emp.department_id,
        "department_name": emp.department.name if emp.department else None,
        "position_id": emp.position_id,
        "position_name": emp.position.job_title if emp.position else None,
        "user_id": emp.user_id,
    }


# ─────────────────────────────────────────────
# Route 1 – POST /api/admin/employees
# Tạo mới hồ sơ nhân viên (Shell record)
# ─────────────────────────────────────────────

@admin_bp.route("/api/admin/employees", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def create_employee():
    """
    Khởi tạo hồ sơ nhân viên cơ bản (shell record).
    Thông tin công việc sẽ được gán ở bước sau.

    Body JSON:
        full_name        (str, bắt buộc)
        dob              (str ISO, bắt buộc) – vd: "1995-06-15"
        gender           (str, tuỳ chọn)     – "male" | "female" | "other"
        phone            (str, tuỳ chọn)
        address          (str, tuỳ chọn)
        hire_date        (str ISO, tuỳ chọn)
        employment_type  (str, tuỳ chọn)     – mặc định "probation"
    """
    data = request.get_json(silent=True) or {}

    if not (data.get("full_name") or "").strip():
        return swal_error("Thiếu thông tin", "Vui lòng cung cấp họ tên nhân viên ('full_name').", 400)

    if not data.get("dob"):
        return swal_error("Thiếu thông tin", "Vui lòng cung cấp ngày sinh ('dob').", 400)

    try:
        employee = Admin_Service.create_employee(
            data=data,
            current_user_id=g.user.id,
        )
        return swal_success(
            "Tạo hồ sơ thành công",
            f"Hồ sơ nhân viên '{employee.full_name}' đã được khởi tạo. Vui lòng tiếp tục gán Phòng ban & Chức danh.",
            data=employee_to_dict(employee),
            status_code=201,
        )

    except ValueError as e:
        return swal_error("Dữ liệu không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 2 – PATCH /api/admin/employees/<id>/work-info
# Gán Phòng ban & Chức danh cho nhân viên
# ─────────────────────────────────────────────

@admin_bp.route("/api/admin/employees/<int:id>/work-info", methods=["PATCH"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def assign_work_info(id: int):
    """
    Gán Phòng ban và/hoặc Chức danh cho nhân viên.

    Body JSON:
        department_id  (int, tuỳ chọn)
        position_id    (int, tuỳ chọn)
    """
    data = request.get_json(silent=True) or {}

    if "department_id" not in data and "position_id" not in data:
        return swal_error(
            "Thiếu thông tin",
            "Vui lòng cung cấp ít nhất 'department_id' hoặc 'position_id'.",
            400,
        )

    try:
        employee = Admin_Service.assign_work_info(
            employee_id=id,
            data=data,
            current_user_id=g.user.id,
        )
        dept_name = employee.department.name if employee.department else "Chưa gán"
        pos_name = employee.position.job_title if employee.position else "Chưa gán"
        return swal_success(
            "Cập nhật thành công",
            f"Đã gán '{dept_name}' / '{pos_name}' cho nhân viên {employee.full_name}.",
            data=employee_to_dict(employee),
        )

    except ValueError as e:
        return swal_error("Dữ liệu không hợp lệ", str(e), 400)

    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 3 – GET /api/admin/employees/pending
# Danh sách nhân viên chờ tạo tài khoản
# ─────────────────────────────────────────────

@admin_bp.route("/api/admin/employees/pending", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_pending_employees():
    """
    Lấy danh sách nhân viên đã có Phòng ban & Chức danh
    nhưng chưa được tạo tài khoản (user_id IS NULL).
    """
    try:
        employees = Admin_Service.get_employees_pending_account()
        items = [employee_to_dict(e) for e in employees]
        return swal_success(
            "Thành công",
            f"Có {len(items)} nhân viên đang chờ tạo tài khoản.",
            data={"items": items, "total": len(items)},
        )

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 4 – GET /api/admin/employees/pending/<id>
# Chi tiết hồ sơ nhân viên chờ tạo tài khoản
# ─────────────────────────────────────────────

@admin_bp.route("/api/admin/employees/pending/<int:id>", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_pending_employee_detail(id: int):
    """
    Xem chi tiết hồ sơ nhân viên trong danh sách chờ tạo tài khoản.
    Chỉ trả về nếu nhân viên thỏa điều kiện: có PB + Chức danh, chưa có user.
    """
    try:
        employee = Admin_Service.get_pending_employee_detail(employee_id=id)
        return swal_success(
            "Thành công",
            "Lấy thông tin hồ sơ nhân viên thành công.",
            data=employee_to_dict(employee),
        )

    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 5 – PATCH /api/admin/employees/pending/<id>
# Cập nhật hồ sơ nhân viên chờ tạo tài khoản
# ─────────────────────────────────────────────

@admin_bp.route("/api/admin/employees/pending/<int:id>", methods=["PATCH"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def update_pending_employee(id: int):
    """
    Chỉnh sửa hồ sơ nhân viên chưa có tài khoản.
    Chỉ cho phép sửa thông tin cá nhân (không sửa PB/Chức danh ở đây).

    Body JSON (tất cả tuỳ chọn, chỉ truyền field cần sửa):
        full_name  (str)
        dob        (str ISO)
        gender     (str)
        phone      (str)
        address    (str)
        hire_date  (str ISO)
    """
    data = request.get_json(silent=True) or {}

    if not data:
        return swal_error(
            "Thiếu thông tin",
            "Vui lòng cung cấp ít nhất một trường cần cập nhật.",
            400,
        )

    try:
        employee = Admin_Service.update_pending_employee(
            employee_id=id,
            data=data,
            current_user_id=g.user.id,
        )
        return swal_success(
            "Cập nhật thành công",
            f"Hồ sơ nhân viên '{employee.full_name}' đã được cập nhật.",
            data=employee_to_dict(employee),
        )

    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except ValueError as e:
        return swal_error("Dữ liệu không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)