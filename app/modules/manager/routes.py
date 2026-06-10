from flask import jsonify, request, g

from app.constants.common import RoleName
from app.common.security.decorators import auth_required, role_required
from app.modules.manager.employee_service import EmployeeService
from . import manager_bp
from app.common.responses import swal_success, swal_error
from . import attendance_routes
# ===========================================================
# GET /manager/summary
# Lấy số liệu tổng quan nhân viên trong phòng ban của manager
# ===========================================================
@manager_bp.route("/summary", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.ADMIN, RoleName.HR)
def get_department_employee_summary():
    """
    Lấy thống kê tổng quan nhân viên trong phòng ban:
    - Tổng số nhân viên
    - Nhân viên đang làm việc (active)
    - Nhân viên thử việc (probation)
    - Hợp đồng sắp hết hạn (trong 30 ngày tới)
    """
    try:
        manager_id = g.employee.id
        summary = EmployeeService.get_department_employee_summary(manager_id)
        return swal_success(
            title="Thành công",
            message="Lấy thống kê nhân viên thành công.",
            data=summary
        )
    except ValueError as e:
        return swal_error("Không tìm thấy dữ liệu", str(e), 404)
    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ===========================================================
# GET /manager/
# Lấy danh sách nhân viên có bộ lọc (search, filter)
# ===========================================================
@manager_bp.route("/", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.ADMIN, RoleName.HR)
def get_department_employee_list():
    """
    Lấy danh sách nhân viên trong phòng ban với các bộ lọc tuỳ chọn:

    Query params (tất cả đều không bắt buộc):
      - name            : Tìm theo tên nhân viên (tìm kiếm gần đúng)
      - employee_code   : Tìm theo mã nhân viên (VD: EMP0001)
      - position        : Lọc theo chức vụ
      - working_status  : Lọc theo trạng thái làm việc (active / resigned / ...)
      - contract_type   : Lọc theo loại hợp đồng
      - probation       : Lọc nhân viên thử việc (yes / no)
      - department      : Lọc theo tên phòng ban
    """
    try:
        manager_id = g.employee.id

        filters = {
            "name":           request.args.get("name"),
            "employee_code":  request.args.get("employee_code"),
            "position":       request.args.get("position"),
            "working_status": request.args.get("working_status"),
            "contract_type":  request.args.get("contract_type"),
            "probation":      request.args.get("probation"),
            "department":     request.args.get("department"),
        }

        employees = EmployeeService.get_department_employee_list(manager_id, filters)

        return swal_success(
            title="Thành công",
            message=f"Tìm thấy {len(employees)} nhân viên.",
            data={
                "total": len(employees),
                "employees": employees
            }
        )
    except ValueError as e:
        return swal_error("Không hợp lệ", str(e), 400)
    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ===========================================================
# GET /manager/<int:employee_id>
# Lấy chi tiết hồ sơ của một nhân viên cụ thể
# ===========================================================
@manager_bp.route("/<int:employee_id>", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.ADMIN, RoleName.HR)
def get_department_employee_detail(employee_id: int):
    """
    Lấy thông tin chi tiết hồ sơ của một nhân viên trong phòng ban.
    Manager chỉ được xem nhân viên thuộc quyền quản lý của mình.

    Path param:
      - employee_id (int): ID của nhân viên cần xem
    """
    try:
        manager_id = g.employee.id
        detail = EmployeeService.get_department_employee_detail(manager_id, employee_id)
        return swal_success(
            title="Thành công",
            message="Lấy thông tin nhân viên thành công.",
            data=detail
        )
    except ValueError as e:
        # Bao gồm cả lỗi "không có quyền" và "không tìm thấy"
        status = 403 if "quyền" in str(e) else 404
        title  = "Không có quyền truy cập" if status == 403 else "Không tìm thấy"
        return swal_error(title, str(e), status)
    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)