from flask import request, jsonify, g
from http import HTTPStatus

from app.modules.payroll import payroll_bp
from app.common.security.decorators import auth_required, role_required
from app.constants.common import RoleName
from app.modules.payroll.manager_service import Manager_Payroll_Service


from app.common.responses import payroll_success_payload as swal_success, payroll_error_payload as swal_error, payroll_warning_payload as swal_warning


# ─────────────────────────────────────────────
# 1. GET /payroll/manager/salaries
#    Xem danh sách lương bộ phận (có lọc)
# ─────────────────────────────────────────────
@payroll_bp.route("/manager/salaries", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def get_department_payroll_review():
    """
    Query params:
        month           (int, bắt buộc)
        year            (int, bắt buộc)
        employee_name   (str, tuỳ chọn)
        employee_code   (str, tuỳ chọn)
        status          (str, tuỳ chọn)
        employment_type (str, tuỳ chọn)
        position        (str, tuỳ chọn)
    """
    try:
        month = request.args.get("month", type=int)
        year  = request.args.get("year",  type=int)

        if not month or not year:
            return jsonify(swal_error(
                "Vui lòng cung cấp tháng và năm.",
                title="Thiếu tham số"
            )), HTTPStatus.BAD_REQUEST

        manager_id = g.employee.id

        result = Manager_Payroll_Service.get_department_payroll_review(
            manager_id=manager_id,
            month=month,
            year=year,
            employee_name=request.args.get("employee_name"),
            employee_code=request.args.get("employee_code"),
            status=request.args.get("status"),
            employment_type=request.args.get("employment_type"),
            position=request.args.get("position"),
        )

        return jsonify(swal_success(
            f"Danh sách lương tháng {month:02d}/{year}.",
            data=result
        )), HTTPStatus.OK

    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# 2. GET /payroll/manager/salaries/<id>
#    Xem chi tiết 1 phiếu lương
# ─────────────────────────────────────────────
@payroll_bp.route("/manager/salaries/<int:salary_id>", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def get_department_payroll_detail(salary_id: int):
    try:
        manager_id = g.employee.id

        detail = Manager_Payroll_Service.get_department_payroll_detail(
            manager_id=manager_id,
            salary_id=salary_id,
        )

        # Cảnh báo nếu số người phụ thuộc thay đổi
        if detail.get("work_stats", {}).get("has_dep_warning"):
            return jsonify(swal_warning(
                "Số người phụ thuộc đã thay đổi so với thời điểm chốt lương. Vui lòng kiểm tra lại.",
                data=detail
            )), HTTPStatus.OK

        return jsonify(swal_success(
            "Lấy chi tiết phiếu lương thành công.",
            data=detail
        )), HTTPStatus.OK

    except ValueError as e:
        return jsonify(swal_error(str(e), title="Không có quyền")), HTTPStatus.FORBIDDEN
    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# 3. PATCH /payroll/manager/salaries/<id>/confirm
#    Phê duyệt / Chốt lương
# ─────────────────────────────────────────────
@payroll_bp.route("/manager/salaries/<int:salary_id>/confirm", methods=["PATCH"])
@auth_required
@role_required(RoleName.MANAGER)
def confirm_department_payroll(salary_id: int):
    """
    Body JSON (tuỳ chọn):
        note  (str)  – Ghi chú khi phê duyệt
    """
    try:
        manager_id = g.employee.id
        body = request.get_json(silent=True) or {}
        note = body.get("note")

        result = Manager_Payroll_Service.confirm_department_payroll(
            manager_id=manager_id,
            salary_id=salary_id,
            note=note,
        )

        # Trả về warning nếu có sai lệch người phụ thuộc
        if result.get("has_discrepancy"):
            return jsonify(swal_warning(
                result.get("message", "Đã chốt lương nhưng có cảnh báo về người phụ thuộc."),
                data=result
            )), HTTPStatus.OK

        return jsonify(swal_success(
            result.get("message", "Phê duyệt lương thành công."),
            data=result
        )), HTTPStatus.OK

    except ValueError as e:
        return jsonify(swal_error(str(e), title="Không thể phê duyệt")), HTTPStatus.BAD_REQUEST
    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# 4. PATCH /payroll/manager/complaints/<id>
#    Xử lý khiếu nại (Approve / Reject)
# ─────────────────────────────────────────────
@payroll_bp.route("/manager/complaints/<int:complaint_id>", methods=["PATCH"])
@auth_required
@role_required(RoleName.MANAGER)
def handle_salary_complaint(complaint_id: int):
    try:
        manager_id = g.employee.id
        body = request.get_json(silent=True) or {}
        action = body.get("action", "").strip().lower()
        note = body.get("note", "").strip()
        if action not in ("approve", "reject"):
            return jsonify(swal_error("Hành động chỉ chấp nhận 'approve' hoặc 'reject'.")), HTTPStatus.BAD_REQUEST
        if not note:
            return jsonify(swal_error("Vui lòng nhập lý do phê duyệt hoặc từ chối.")), HTTPStatus.BAD_REQUEST
        result = Manager_Payroll_Service.handle_salary_complaint(
            manager_id=manager_id,
            complaint_id=complaint_id,
            action=action,
            note=note,
        )
        return jsonify(swal_success(
            f"Khiếu nại đã được {action} thành công.",
            data=result
        )), HTTPStatus.OK
    except ValueError as e:
        return jsonify(swal_error(str(e), title="Xử lý thất bại")), HTTPStatus.BAD_REQUEST
    except Exception as e:
        print(f"Error handling complaint: {e}") 
        return jsonify(swal_error("Đã xảy ra lỗi hệ thống, vui lòng thử lại sau.")), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# 5. GET /payroll/manager/report
#    Xem báo cáo tổng hợp (Dashboard)
# ─────────────────────────────────────────────
@payroll_bp.route("/manager/report", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def get_department_payroll_report():
    """
    Query params:
        month  (int, bắt buộc)
        year   (int, bắt buộc)
    """
    try:
        month = request.args.get("month", type=int)
        year  = request.args.get("year",  type=int)

        if not month or not year:
            return jsonify(swal_error(
                "Vui lòng cung cấp tháng và năm.",
                title="Thiếu tham số"
            )), HTTPStatus.BAD_REQUEST

        manager_id = g.employee.id

        report = Manager_Payroll_Service.get_department_payroll_report(
            manager_id=manager_id,
            month=month,
            year=year,
        )

        if not report:
            return jsonify(swal_warning(
                "Không tìm thấy nhân viên thuộc phòng ban của bạn.",
                data={}
            )), HTTPStatus.OK

        return jsonify(swal_success(
            f"Báo cáo tổng hợp tháng {month:02d}/{year}.",
            data=report
        )), HTTPStatus.OK

    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR
    
# ─────────────────────────────────────────────
# 6. GET /payroll/manager/complaints
#    Lấy danh sách khiếu nại của nhân viên phòng ban
# ─────────────────────────────────────────────
@payroll_bp.route("/manager/complaints", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def get_department_complaints():
    """
    Query params:
        month  (int, optional)
        year   (int, optional)
        status (str, optional)
    """
    try:
        manager_id = g.employee.id
        month = request.args.get("month", type=int)
        year = request.args.get("year", type=int)
        status = request.args.get("status")

        complaints = Manager_Payroll_Service.get_payroll_complaints(
            manager_id=manager_id,
            month=month,
            year=year,
            status=status
        )

        return jsonify(swal_success(
            "Lấy danh sách khiếu nại thành công.",
            data=complaints
        )), HTTPStatus.OK

    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# 7. GET /payroll/manager/complaints/<id>
#    Xem chi tiết 1 khiếu nại (của nhân viên thuộc quyền)
# ─────────────────────────────────────────────
@payroll_bp.route("/manager/complaints/<int:complaint_id>", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def get_department_complaint_detail(complaint_id: int):
    try:
        manager_id = g.employee.id
        
        detail = Manager_Payroll_Service.manager_complaint_detail(
            manager_id=manager_id,
            complaint_id=complaint_id
        )

        return jsonify(swal_success(
            "Lấy chi tiết khiếu nại thành công.",
            data=detail
        )), HTTPStatus.OK

    except ValueError as e:
        # Catch lỗi "Bạn không có quyền xem..." hoặc "Không tìm thấy" từ Service
        return jsonify(swal_error(str(e), title="Truy cập thất bại")), HTTPStatus.FORBIDDEN
    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR