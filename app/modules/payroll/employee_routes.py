from flask import request, jsonify, g
from app.modules.payroll import payroll_bp
from app.modules.payroll.employee_service import EmployeePayrollService
from app.common.security.decorators import (
    auth_required,
    role_required,
)
from app.common.security.permissions import (
    complaint_owner_or_hr_required,
)
from app.constants.common import RoleName

# =====================================================
# 1. GỬI KHIẾU NẠI
# POST /payroll/complaints
# =====================================================
@payroll_bp.route("/complaints", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE)
def submit_complaint():
    data = request.form
    salary_id = data.get("salary_id")
    noti_id = data.get("noti_id")
    issue_type = data.get("issue_type")
    description = data.get("description")
    attachments = request.files.getlist("attachments")

    if not issue_type:
        return jsonify({
            "success": False,
            "icon": "warning",
            "title": "Thiếu loại khiếu nại",
            "text": "Vui lòng chọn loại khiếu nại."
        }), 400

    if not description:
        return jsonify({
            "success": False,
            "icon": "warning",
            "title": "Thiếu nội dung",
            "text": "Vui lòng nhập nội dung khiếu nại."
        }), 400

    try:

        # gửi từ notification
        if noti_id:
            result = EmployeePayrollService.submit_complaint_from_noti(
                user_id=g.user.id,
                noti_id=int(noti_id),
                issue_type=issue_type,
                description=description,
                attachment=attachments
            )

        # gửi trực tiếp từ phiếu lương
        else:

            if not salary_id:
                return jsonify({
                    "success": False,
                    "icon": "warning",
                    "title": "Thiếu dữ liệu",
                    "text": "Không xác định được phiếu lương."
                }), 400

            result = EmployeePayrollService.submit_complaint(
                user_id=g.user.id,
                salary_id=int(salary_id),
                issue_type=issue_type,
                description=description,
                attachment=attachments
            )

        return jsonify({
            "success": True,
            "icon": "success",
            "title": "Thành công",
            "text": result["message"],
            "data": result
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "icon": "error",
            "title": "Gửi khiếu nại thất bại",
            "text": str(e)
        }), 400


# =====================================================
# 2. DANH SÁCH KHIẾU NẠI
# GET /payroll/complaints
# =====================================================
@payroll_bp.route("/complaints", methods=["GET"])
@auth_required
@role_required(RoleName.EMPLOYEE)
def salary_complaints():

    complaints = EmployeePayrollService.salary_complaints(
        user_id=g.user.id
    )

    return jsonify({
        "success": True,
        "data": complaints
    })


# =====================================================
# 3. CHI TIẾT KHIẾU NẠI
# GET /payroll/complaints/<id>
# =====================================================
@payroll_bp.route("/complaints/<int:complaint_id>", methods=["GET"])
@auth_required
@role_required(RoleName.EMPLOYEE)
@complaint_owner_or_hr_required("complaint_id")
def complaint_detail(complaint_id):

    try:

        data = EmployeePayrollService.complaint_detail(
            user_id=g.user.id,
            complaint_id=complaint_id
        )

        return jsonify({
            "success": True,
            "data": data
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "icon": "error",
            "title": "Không thể tải dữ liệu",
            "text": str(e)
        }), 400


# =====================================================
# 4. ĐÓNG KHIẾU NẠI
# PATCH /payroll/complaints/<id>/close
# =====================================================
@payroll_bp.route("/complaints/<int:complaint_id>/close", methods=["PATCH"])
@auth_required
@role_required(RoleName.EMPLOYEE)
@complaint_owner_or_hr_required("complaint_id")
def close_salary_complaint(complaint_id):

    try:

        result = EmployeePayrollService.close_salary_complaint(
            user_id=g.user.id,
            complaint_id=complaint_id
        )

        return jsonify({
            "success": True,
            "icon": "success",
            "title": "Thành công",
            "text": result["message"]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "icon": "error",
            "title": "Không thể đóng khiếu nại",
            "text": str(e)
        }), 400


# =====================================================
# 5. BÁO CÁO THÁNG
# GET /payroll/reports/monthly?month=5&year=2026
# =====================================================
@payroll_bp.route("/reports/monthly", methods=["GET"])
@auth_required
@role_required(RoleName.EMPLOYEE)
def monthly_report():

    try:

        month = request.args.get("month", type=int)
        year = request.args.get("year", type=int)

        if not month or not year:
            return jsonify({
                "success": False,
                "icon": "warning",
                "title": "Thiếu dữ liệu",
                "text": "Vui lòng truyền month và year."
            }), 400

        report = EmployeePayrollService.get_full_monthly_report(
            employee_id=g.employee.id,
            month=month,
            year=year
        )

        return jsonify({
            "success": True,
            "data": report
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "icon": "error",
            "title": "Không thể lấy báo cáo",
            "text": str(e)
        }), 400