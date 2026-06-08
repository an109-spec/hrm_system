from flask import request, jsonify, g
from . import admin_bp
from app.modules.admin.dept_pos_service import Dept_Pos_Service
from app.common.security.decorators import auth_required, role_required
from app.common.exceptions import NotFoundError, ValidationError, ConflictError
from app.constants.common import RoleName
from app.common.responses import swal_success, swal_error




def dept_to_dict(dept) -> dict:
    """Serialize Department object sang dict."""
    return {
        "id": dept.id,
        "name": dept.name,
        "description": getattr(dept, "description", None),
        "manager_id": dept.manager_id,
        "manager_name": dept.manager.full_name if getattr(dept, "manager", None) else None,
        "status": dept.status,
    }


def pos_to_dict(pos) -> dict:
    """Serialize Position object sang dict."""
    return {
        "id": pos.id,
        "job_title": pos.job_title,
        "status": pos.status,
        "requirements": getattr(pos, "requirements", None),
    }


def employee_to_dict(emp) -> dict:
    """Serialize Employee object sang dict (dạng gọn cho danh sách)."""
    return {
        "id": emp.id,
        "full_name": emp.full_name,
        "phone": emp.phone,
        "employment_type": emp.employment_type,
        "working_status": emp.working_status,
        "department_id": emp.department_id,
        "department_name": emp.department.name if emp.department else None,
        "position_id": emp.position_id,
        "position_name": emp.position.job_title if emp.position else None,
    }


# ─────────────────────────────────────────────
# Route 1 – GET /api/metadata/filters
# Dữ liệu cho bộ lọc (PB, Chức danh, Vai trò)
# ─────────────────────────────────────────────

@admin_bp.route("/api/metadata/filters", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_filter_metadata():
    """
    Lấy toàn bộ dữ liệu cần thiết để render bộ lọc trên giao diện:
    danh sách Phòng ban, Chức danh và Vai trò đang hoạt động.
    """
    try:
        metadata = Dept_Pos_Service.employee_filter_metadata()
        return swal_success(
            "Thành công",
            "Lấy dữ liệu bộ lọc thành công.",
            data=metadata,
        )
    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 2 – GET /api/employees
# Danh sách nhân viên theo bộ lọc PB/Chức danh
# ─────────────────────────────────────────────

@admin_bp.route("/api/employees", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_employees_by_filter():
    """
    Lấy danh sách nhân viên, tuỳ chọn lọc theo Phòng ban và/hoặc Chức danh.

    Query params:
        department_id (int, tuỳ chọn)
        position_id   (int, tuỳ chọn)
    """
    department_id = request.args.get("department_id", type=int)
    position_id = request.args.get("position_id", type=int)

    try:
        employees = Dept_Pos_Service.get_employees_by_filter(
            department_id=department_id,
            position_id=position_id,
        )
        items = [employee_to_dict(e) for e in employees]
        return swal_success(
            "Thành công",
            f"Tìm thấy {len(items)} nhân viên.",
            data={"items": items, "total": len(items)},
        )
    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 3 – PATCH /api/employees/<id>/transfer
# Điều chuyển nhân viên sang PB/Chức danh khác
# ─────────────────────────────────────────────

@admin_bp.route("/api/employees/<int:id>/transfer", methods=["PATCH"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def transfer_employee(id: int):
    """
    Điều chuyển nhân viên sang Phòng ban và/hoặc Chức danh mới.

    Body JSON (ít nhất một trong hai):
        department_id (int, tuỳ chọn)
        position_id   (int, tuỳ chọn)
    """
    data = request.get_json(silent=True) or {}

    if "department_id" not in data and "position_id" not in data:
        return swal_error(
            "Thiếu thông tin",
            "Vui lòng cung cấp ít nhất 'department_id' hoặc 'position_id' để điều chuyển.",
            400,
        )

    try:
        employee = Dept_Pos_Service.transfer_employee(
            employee_id=id,
            payload=data,
            actor_id=g.user.id,
        )
        return swal_success(
            "Điều chuyển thành công",
            f"Nhân viên '{employee.full_name}' đã được điều chuyển thành công.",
            data=employee_to_dict(employee),
        )
    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except (ValidationError, ValueError) as e:
        return swal_error("Dữ liệu không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 4 – PATCH /api/employees/<id>/position
# Gán / Thay đổi chức danh cho nhân viên
# ─────────────────────────────────────────────

@admin_bp.route("/api/employees/<int:id>/position", methods=["PATCH"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def assign_position_to_employee(id: int):
    """
    Gán hoặc thay đổi Chức danh cho một nhân viên cụ thể.

    Body JSON:
        position_id (int, bắt buộc)
    """
    data = request.get_json(silent=True) or {}
    position_id = data.get("position_id")

    if not position_id:
        return swal_error(
            "Thiếu thông tin",
            "Vui lòng cung cấp 'position_id'.",
            400,
        )

    try:
        employee = Dept_Pos_Service.assign_position_to_employee(
            employee_id=id,
            position_id=int(position_id),
            actor_id=g.user.id,
        )
        pos_name = employee.position.job_title if employee.position else "N/A"
        return swal_success(
            "Cập nhật thành công",
            f"Đã gán chức danh '{pos_name}' cho nhân viên '{employee.full_name}'.",
            data=employee_to_dict(employee),
        )
    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except ValidationError as e:
        return swal_error("Dữ liệu không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 5 – POST /api/departments
# Tạo mới phòng ban
# ─────────────────────────────────────────────

@admin_bp.route("/api/departments", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN)
def create_department():
    """
    Tạo mới một Phòng ban.
    Nếu chỉ định manager_id, sẽ tự động nâng cấp vai trò người đó lên Manager.

    Body JSON:
        name        (str, bắt buộc)
        description (str, tuỳ chọn)
        manager_id  (int, tuỳ chọn) – employee_id của người quản lý
        status      (bool, tuỳ chọn, mặc định True)
    """
    data = request.get_json(silent=True) or {}

    if not (data.get("name") or "").strip():
        return swal_error("Thiếu thông tin", "Vui lòng cung cấp tên phòng ban ('name').", 400)

    try:
        dept = Dept_Pos_Service.create_department(data=data, actor_id=g.user.id)
        return swal_success(
            "Tạo phòng ban thành công",
            f"Phòng ban '{dept.name}' đã được tạo.",
            data=dept_to_dict(dept),
            status_code=201,
        )
    except (ValidationError, ValueError) as e:
        return swal_error("Dữ liệu không hợp lệ", str(e), 400)

    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 6 – PATCH /api/departments/<id>
# Đổi tên phòng ban
# ─────────────────────────────────────────────

@admin_bp.route("/api/departments/<int:id>", methods=["PATCH"])
@auth_required
@role_required(RoleName.ADMIN)
def update_department_name(id: int):
    """
    Đổi tên một Phòng ban.
    Không ảnh hưởng đến nhân viên hay quản lý hiện tại.

    Body JSON:
        name (str, bắt buộc) – tên mới
    """
    data = request.get_json(silent=True) or {}
    new_name = (data.get("name") or "").strip()

    if not new_name:
        return swal_error("Thiếu thông tin", "Vui lòng cung cấp tên mới ('name').", 400)

    try:
        dept = Dept_Pos_Service.update_department_name(
            dept_id=id,
            new_name=new_name,
            actor_id=g.user.id,
        )
        return swal_success(
            "Cập nhật thành công",
            f"Tên phòng ban đã được đổi thành '{dept.name}'.",
            data=dept_to_dict(dept),
        )
    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except ConflictError as e:
        return swal_error("Trùng lặp dữ liệu", str(e), 409)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 7 – GET /api/departments/<id>/stats
# Thống kê số lượng nhân viên trong phòng ban
# ─────────────────────────────────────────────

@admin_bp.route("/api/departments/<int:id>/stats", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_department_stats(id: int):
    """
    Xem thống kê nhanh của một Phòng ban:
    tổng số nhân viên và thông tin Quản lý hiện tại.
    """
    try:
        total_employees = Dept_Pos_Service.count_employees_by_department(department_id=id)
        manager = Dept_Pos_Service.get_department_manager(department_id=id)

        stats = {
            "department_id": id,
            "total_employees": total_employees,
            "manager": {
                "id": manager.id,
                "full_name": manager.full_name,
                "position_name": manager.position.job_title if manager.position else None,
            } if manager else None,
        }
        return swal_success(
            "Thành công",
            f"Phòng ban có {total_employees} nhân viên.",
            data=stats,
        )
    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 8 – POST /api/positions
# Tạo mới chức danh
# ─────────────────────────────────────────────

@admin_bp.route("/api/positions", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def create_position():
    """
    Tạo mới một Chức danh công việc.

    Body JSON:
        job_title    (str, bắt buộc)
        status       (str, tuỳ chọn, mặc định "active")
        requirements (str, tuỳ chọn) – mô tả yêu cầu chức danh
    """
    data = request.get_json(silent=True) or {}

    if not (data.get("job_title") or "").strip():
        return swal_error("Thiếu thông tin", "Vui lòng cung cấp tên chức danh ('job_title').", 400)

    try:
        position = Dept_Pos_Service.create_position(data=data, actor_id=g.user.id)
        return swal_success(
            "Tạo chức danh thành công",
            f"Chức danh '{position.job_title}' đã được tạo.",
            data=pos_to_dict(position),
            status_code=201,
        )
    except ConflictError as e:
        return swal_error("Trùng lặp dữ liệu", str(e), 409)

    except (ValidationError, ValueError) as e:
        return swal_error("Dữ liệu không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 9 – PATCH /api/positions/<id>
# Đổi tên chức danh
# ─────────────────────────────────────────────

@admin_bp.route("/api/positions/<int:id>", methods=["PATCH"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def update_position_title(id: int):
    """
    Đổi tên một Chức danh.
    Không ảnh hưởng đến nhân viên đang giữ chức danh này.

    Body JSON:
        job_title (str, bắt buộc) – tên mới
    """
    data = request.get_json(silent=True) or {}
    new_title = (data.get("job_title") or "").strip()

    if not new_title:
        return swal_error("Thiếu thông tin", "Vui lòng cung cấp tên mới ('job_title').", 400)

    try:
        position = Dept_Pos_Service.update_position_title(
            pos_id=id,
            new_title=new_title,
            actor_id=g.user.id,
        )
        return swal_success(
            "Cập nhật thành công",
            f"Tên chức danh đã được đổi thành '{position.job_title}'.",
            data=pos_to_dict(position),
        )
    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except ConflictError as e:
        return swal_error("Trùng lặp dữ liệu", str(e), 409)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)