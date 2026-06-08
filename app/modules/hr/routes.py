from flask import jsonify, request, g

from app.constants.common import RoleName
from app.common.security.decorators import auth_required, role_required
from app.modules.hr.service import HRService
from . import hr_bp
from app.common.responses import swal_success, swal_error, swal_warning

# ------------------------------------------------------------------
# GET /hr/summary
# Dashboard tổng quan: tổng số NV, đang làm, thử việc, HĐ hết hạn
# ------------------------------------------------------------------
@hr_bp.route("/summary", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_all_employee_summary():
    """
    Lấy số liệu tổng quan toàn bộ nhân viên:
      - total_employees      : Tổng số nhân viên
      - active_employees     : Đang làm việc
      - probation_employees  : Thử việc
      - expiring_contracts   : Hợp đồng hết hạn trong 30 ngày tới
    """
    try:
        summary = HRService.get_all_employee_summary()
        return swal_success(
            title="Thành công",
            message="Lấy thống kê tổng quan nhân viên thành công.",
            data=summary
        )
    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Không thể lấy dữ liệu tổng quan: {str(e)}", 500)


# ------------------------------------------------------------------
# GET /hr/employees
# Danh sách nhân viên có hỗ trợ tìm kiếm / lọc nâng cao
# ------------------------------------------------------------------
@hr_bp.route("/employees", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_filtered_employees():
    """
    Lấy danh sách nhân viên với các bộ lọc tuỳ chọn qua query params:
      - name            : Tìm kiếm theo tên (gần đúng)
      - employee_code   : Tìm theo mã nhân viên
      - department_id   : Lọc theo phòng ban (ID)
      - position_id     : Lọc theo chức danh (ID)
      - working_status  : Lọc theo trạng thái (active / resigned / ...)
      - employment_type : Lọc theo loại hợp đồng (probation / full_time / ...)
    """
    try:
        filters = {
            "name":            request.args.get("name"),
            "employee_code":   request.args.get("employee_code"),
            "department_id":   request.args.get("department_id"),
            "position_id":     request.args.get("position_id"),
            "working_status":  request.args.get("working_status"),
            "employment_type": request.args.get("employment_type"),
        }
        # Loại bỏ các key None để service không hiểu nhầm
        filters = {k: v for k, v in filters.items() if v is not None}

        employees = HRService.get_filtered_employees(filters)
        return swal_success(
            title="Thành công",
            message=f"Tìm thấy {len(employees)} nhân viên.",
            data={
                "total": len(employees),
                "employees": employees
            }
        )
    except ValueError as e:
        return swal_warning("Tham số không hợp lệ", str(e), 400)
    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Không thể lấy danh sách nhân viên: {str(e)}", 500)


# ------------------------------------------------------------------
# GET /hr/employees/<int:id>
# Chi tiết hồ sơ một nhân viên cụ thể
# ------------------------------------------------------------------
@hr_bp.route("/employees/<int:id>", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_employee_detail(id: int):
    """
    Lấy đầy đủ thông tin hồ sơ của nhân viên theo ID.

    Path param:
      - id (int): ID của nhân viên
    """
    try:
        detail = HRService.get_employee_detail(id)
        return swal_success(
            title="Thành công",
            message="Lấy thông tin chi tiết nhân viên thành công.",
            data=detail
        )
    except ValueError as e:
        return swal_error("Không tìm thấy", str(e), 404)
    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Không thể lấy thông tin nhân viên: {str(e)}", 500)


# ------------------------------------------------------------------
# GET /hr/stats/department
# Thống kê số lượng nhân viên theo phòng ban
# ------------------------------------------------------------------
@hr_bp.route("/stats/department", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_stats_by_department():
    """
    Trả về danh sách phòng ban kèm số lượng nhân viên:
      [{ department_id, name, total_employees }, ...]
    """
    try:
        stats = HRService.get_stats_by_department()
        return swal_success(
            title="Thành công",
            message="Thống kê nhân viên theo phòng ban thành công.",
            data={
                "total_departments": len(stats),
                "departments": stats
            }
        )
    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Không thể thống kê theo phòng ban: {str(e)}", 500)


# ------------------------------------------------------------------
# GET /hr/stats/position
# Thống kê số lượng nhân viên theo chức danh
# ------------------------------------------------------------------
@hr_bp.route("/stats/position", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_stats_by_position():
    """
    Trả về danh sách chức danh kèm số lượng nhân viên:
      [{ position_id, name, total_employees }, ...]
    """
    try:
        stats = HRService.get_stats_by_position()
        return swal_success(
            title="Thành công",
            message="Thống kê nhân viên theo chức danh thành công.",
            data={
                "total_positions": len(stats),
                "positions": stats
            }
        )
    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Không thể thống kê theo chức danh: {str(e)}", 500)


