from flask import request, jsonify, g

from app.modules.payroll import payroll_bp
from app.modules.payroll.base_service import BasePayrollService, PersonalPayrollService
from app.common.security.decorators import auth_required, role_required, self_or_hr_required
from app.common.security.permissions import salary_owner_or_hr_required
from app.constants.common import RoleName


# ===========================================================================
# 🔧 HELPER: Chuẩn hoá response trả về dạng SweetAlert2 (Swal)
# ===========================================================================

def swal_success(title="Thành công", message="", data=None, status_code=200):
    response = {
        "swal": {"icon": "success", "title": title, "text": message}
    }
    if data is not None:
        response["data"] = data
    return jsonify(response), status_code


def swal_error(title="Lỗi", message="Đã xảy ra lỗi, vui lòng thử lại.", status_code=400):
    return jsonify({
        "swal": {"icon": "error", "title": title, "text": message}
    }), status_code


def swal_warning(title="Cảnh báo", message="", status_code=400):
    return jsonify({
        "swal": {"icon": "warning", "title": title, "text": message}
    }), status_code


def _require_month_year():
    """
    Đọc month/year từ query string.
    Trả về (month, year, None) nếu hợp lệ,
    hoặc (None, None, response) nếu thiếu — caller return response ngay.
    """
    month = request.args.get("month", type=int)
    year  = request.args.get("year",  type=int)
    if not month or not year:
        return None, None, swal_warning(
            title="Thiếu thông tin",
            message="Vui lòng cung cấp tháng (month) và năm (year) trong query string."
        )
    return month, year, None


# ===========================================================================
# 📋 PAYROLL HISTORY — /payroll/history
# Xem lịch sử bảng lương theo năm với đầy đủ bộ lọc.
# ===========================================================================

@payroll_bp.route("/history/me", methods=["GET"])
@auth_required
def get_my_payroll_history():
    """
    Tất cả 4 actor xem lịch sử bảng lương của chính mình.
    Query params:
      - year          (int, bắt buộc)
      - status        (str, tuỳ chọn)  — lọc theo trạng thái lương
      - paid_state    (str, tuỳ chọn)  — 'paid' | 'unpaid'
      - has_complaint (str, tuỳ chọn)  — '1' | 'true' | 'yes'
    """
    try:
        year = request.args.get("year", type=int)
        if not year:
            return swal_warning(
                title="Thiếu thông tin",
                message="Vui lòng cung cấp năm (year) trong query string."
            )

        filters = {
            "year":          year,
            "status":        request.args.get("status",        "").strip(),
            "paid_state":    request.args.get("paid_state",    "").strip(),
            "has_complaint": request.args.get("has_complaint", "").strip(),
        }

        data = PersonalPayrollService.payroll_history(
            user_id=g.user.id,
            filters=filters
        )
        return jsonify({"data": data}), 200

    except ValueError as e:
        return swal_error(title="Không tìm thấy", message=str(e), status_code=404)
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@payroll_bp.route("/history/<int:employee_id>", methods=["GET"])
@auth_required
@self_or_hr_required(employee_id_key="employee_id")
def get_payroll_history_by_id(employee_id):
    """
    Admin / HR xem lịch sử bảng lương của bất kỳ nhân viên.
    Employee / Manager bị chặn bởi self_or_hr_required nếu không phải của mình.
    Query params giống route /history/me.
    """
    try:
        year = request.args.get("year", type=int)
        if not year:
            return swal_warning(
                title="Thiếu thông tin",
                message="Vui lòng cung cấp năm (year) trong query string."
            )

        from app.models.employee import Employee
        from app.extensions.db import db
        emp = db.session.get(Employee, employee_id)
        if not emp:
            return swal_error(
                title="Không tìm thấy",
                message="Nhân viên không tồn tại trong hệ thống.",
                status_code=404
            )

        filters = {
            "year":          year,
            "status":        request.args.get("status",        "").strip(),
            "paid_state":    request.args.get("paid_state",    "").strip(),
            "has_complaint": request.args.get("has_complaint", "").strip(),
        }

        data = PersonalPayrollService.payroll_history(
            user_id=emp.user_id,
            filters=filters
        )
        return jsonify({"data": data}), 200

    except ValueError as e:
        return swal_error(title="Không tìm thấy", message=str(e), status_code=404)
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


# ===========================================================================
# 📄 PAYSLIP DETAIL — /payroll/payslip/<salary_id>
# Xem chi tiết một phiếu lương cụ thể (snapshot tĩnh từ DB).
# ===========================================================================

@payroll_bp.route("/payslip/<int:salary_id>", methods=["GET"])
@auth_required
@salary_owner_or_hr_required(salary_id_key="salary_id")
def get_payslip_detail(salary_id):
    """
    Xem chi tiết phiếu lương theo salary_id.
    - Employee / Manager: chỉ xem phiếu của chính mình
      (salary_owner_or_hr_required kiểm soát).
    - Admin / HR: bypass, xem được của tất cả.
    Trả về toàn bộ breakdown: lương cơ bản, phụ cấp, OT, khấu trừ,
    bảo hiểm, thuế, giảm trừ gia cảnh, thực lĩnh và trạng thái khiếu nại.
    """
    try:
        data = PersonalPayrollService.payroll_detail(
            user_id=g.user.id,
            salary_id=salary_id
        )
        return jsonify({"data": data}), 200

    except ValueError as e:
        return swal_error(title="Không tìm thấy", message=str(e), status_code=404)
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


# ===========================================================================
# 📈 SALARY HISTORY CHART — /payroll/salary-history
# Lịch sử lương theo năm — dữ liệu gọn để vẽ biểu đồ Dashboard.
# ===========================================================================

@payroll_bp.route("/salary-history/me", methods=["GET"])
@auth_required
def get_my_salary_history():
    """
    Tất cả 4 actor xem lịch sử lương theo năm để hiển thị biểu đồ.
    Query params bắt buộc: ?year=2025
    Trả về list tháng gồm: net_salary, status, status_label.
    """
    try:
        year = request.args.get("year", type=int)
        if not year:
            return swal_warning(
                title="Thiếu thông tin",
                message="Vui lòng cung cấp năm (year) trong query string."
            )

        data = BasePayrollService.get_salary_history(
            employee_id=g.employee.id,
            year=year
        )
        return jsonify({"data": data}), 200

    except ValueError as e:
        return swal_error(title="Không hợp lệ", message=str(e))
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@payroll_bp.route("/salary-history/<int:employee_id>", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_salary_history_by_id(employee_id):
    """
    Admin / HR xem lịch sử lương của bất kỳ nhân viên theo năm.
    Dùng cho trang quản trị hoặc báo cáo nhân sự.
    Query params bắt buộc: ?year=2025
    """
    try:
        year = request.args.get("year", type=int)
        if not year:
            return swal_warning(
                title="Thiếu thông tin",
                message="Vui lòng cung cấp năm (year) trong query string."
            )

        data = BasePayrollService.get_salary_history(
            employee_id=employee_id,
            year=year
        )
        return jsonify({"data": data}), 200

    except ValueError as e:
        return swal_error(title="Không hợp lệ", message=str(e))
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


# ===========================================================================
# 🗂️ ALL EMPLOYEES SALARY — /payroll/all
# Admin / HR xem bảng lương toàn bộ nhân viên trong hệ thống theo tháng.
# ===========================================================================

@payroll_bp.route("/all", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_all_employee_salaries():
    """
    Admin / HR xem toàn bộ bảng lương của tất cả nhân viên trong một tháng.
    Query params:
      - month   (int, bắt buộc)
      - year    (int, bắt buộc)
      - status  (str, tuỳ chọn)  — lọc theo trạng thái lương
      - dept_id (int, tuỳ chọn)  — lọc theo phòng ban
    """
    try:
        month, year, err = _require_month_year()
        if err:
            return err

        status  = request.args.get("status",  "").strip()
        dept_id = request.args.get("dept_id", type=int)

        from app.models.salary import Salary
        from app.models.employee import Employee
        from app.constants.payroll import SalaryStatus, SalaryComplaintStatus

        query = (
            Salary.query
            .join(Employee, Salary.employee_id == Employee.id)
            .filter(
                Salary.month      == month,
                Salary.year       == year,
                Salary.is_deleted == False,
                Employee.is_deleted == False
            )
        )

        if status:
            query = query.filter(Salary.status == status)
        if dept_id:
            query = query.filter(Employee.department_id == dept_id)

        rows = query.order_by(Employee.full_name.asc()).all()

        items = []
        for row in rows:
            complaint = BasePayrollService._latest_salary_complaint(row.employee_id, row.id)
            items.append({
                "salary_id":       row.id,
                "employee_id":     row.employee_id,
                "employee_name":   row.employee.full_name if row.employee else "N/A",
                "department":      (
                    row.employee.department.name
                    if row.employee and row.employee.department
                    else "N/A"
                ),
                "month":           row.month,
                "year":            row.year,
                "basic_salary":    float(row.basic_salary    or 0),
                "total_allowance": float(row.total_allowance or 0),
                "overtime_salary": float(row.overtime_salary or 0),
                "insurance":       float(row.insurance       or 0),
                "tax":             float(row.tax             or 0),
                "penalty":         float(row.penalty         or 0),
                "net_salary":      float(row.net_salary      or 0),
                "status":          row.status,
                "status_label":    SalaryStatus.get_label(row.status),
                "number_of_dependents": row.number_of_dependents,
                "has_complaint":   bool(complaint),
                "complaint_status": complaint.status if complaint else None,
                "complaint_status_label": (
                    SalaryComplaintStatus.LABELS.get(complaint.status, "Không rõ")
                    if complaint else "Không có khiếu nại"
                ),
            })

        return jsonify({
            "data": {
                "period":        f"{month:02d}/{year}",
                "total_records": len(items),
                "items":         items,
            }
        }), 200

    except Exception as e:
        return swal_error(message=str(e), status_code=500)


# ===========================================================================
# 🔍 LATEST SALARY SNAPSHOT — /payroll/latest
# Phiếu lương mới nhất — hiển thị nhanh trên Widget Dashboard.
# ===========================================================================

@payroll_bp.route("/latest/me", methods=["GET"])
@auth_required
def get_my_latest_salary():
    """
    Tất cả 4 actor xem phiếu lương mới nhất của chính mình.
    Dùng cho Widget tóm tắt lương trên Dashboard — không cần truyền tháng/năm.
    """
    try:
        from app.constants.payroll import SalaryStatus, SalaryComplaintStatus

        row = BasePayrollService._latest_salary(g.employee.id)
        if not row:
            return jsonify({
                "data":    None,
                "message": "Chưa có kỳ lương nào được ghi nhận."
            }), 200

        complaint = BasePayrollService._latest_salary_complaint(g.employee.id, row.id)

        return jsonify({
            "data": {
                "salary_id":    row.id,
                "period":       f"{row.month:02d}/{row.year}",
                "net_salary":   float(row.net_salary or 0),
                "status":       row.status,
                "status_label": SalaryStatus.get_label(row.status),
                "has_complaint": bool(complaint),
                "complaint_status_label": (
                    SalaryComplaintStatus.LABELS.get(complaint.status, "Không rõ")
                    if complaint else "Không có khiếu nại"
                ),
                "payment_date": (
                    row.updated_at.strftime("%d/%m/%Y")
                    if row.status == SalaryStatus.PAID and row.updated_at
                    else None
                ),
            }
        }), 200

    except ValueError as e:
        return swal_error(title="Không tìm thấy", message=str(e), status_code=404)
    except Exception as e:
        return swal_error(message=str(e), status_code=500)


@payroll_bp.route("/latest/<int:employee_id>", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_latest_salary_by_id(employee_id):
    """
    Admin / HR xem snapshot lương mới nhất của một nhân viên bất kỳ.
    Dùng cho trang hồ sơ nhân viên phía quản trị.
    """
    try:
        from app.constants.payroll import SalaryStatus, SalaryComplaintStatus

        row = BasePayrollService._latest_salary(employee_id)
        if not row:
            return jsonify({
                "data":    None,
                "message": "Nhân viên này chưa có kỳ lương nào."
            }), 200

        complaint = BasePayrollService._latest_salary_complaint(employee_id, row.id)

        return jsonify({
            "data": {
                "salary_id":    row.id,
                "employee_id":  employee_id,
                "period":       f"{row.month:02d}/{row.year}",
                "net_salary":   float(row.net_salary or 0),
                "status":       row.status,
                "status_label": SalaryStatus.get_label(row.status),
                "has_complaint": bool(complaint),
                "complaint_status_label": (
                    SalaryComplaintStatus.LABELS.get(complaint.status, "Không rõ")
                    if complaint else "Không có khiếu nại"
                ),
                "payment_date": (
                    row.updated_at.strftime("%d/%m/%Y")
                    if row.status == SalaryStatus.PAID and row.updated_at
                    else None
                ),
            }
        }), 200

    except ValueError as e:
        return swal_error(title="Không tìm thấy", message=str(e), status_code=404)
    except Exception as e:
        return swal_error(message=str(e), status_code=500)