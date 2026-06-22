from flask import request, jsonify, g, render_template
from http import HTTPStatus

from app.modules.payroll import payroll_bp
from app.common.security.decorators import auth_required, role_required
from app.constants.common import RoleName
from app.modules.payroll.hr_service import HR_payroll_service
from app.common.responses import payroll_success_payload as swal_success, payroll_error_payload as swal_error, payroll_warning_payload as swal_warning
# ════════════════════════════════════════════════════════════════
# NHÓM 1: QUẢN LÝ BẢNG LƯƠNG (Payroll Management)
# ════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# POST /payroll/calculate
# Chạy tính lương hàng loạt
# ─────────────────────────────────────────────
@payroll_bp.route("/calculate", methods=["POST"])
@auth_required
@role_required(RoleName.HR)
def calculate_monthly_payroll():
    """
    Body JSON (bắt buộc):
        month          (int)
        year           (int)
        department_id  (int, tuỳ chọn) – giới hạn theo phòng ban
    """
    try:
        body = request.get_json(silent=True) or {}

        month = body.get("month")
        year  = body.get("year")

        if not month or not year:
            return jsonify(swal_error(
                "Vui lòng cung cấp tháng và năm.",
                title="Thiếu tham số"
            )), HTTPStatus.BAD_REQUEST

        department_id  = body.get("department_id")
        actor_user_id  = g.user.id

        result = HR_payroll_service.calculate_monthly_payroll(
            month=int(month),
            year=int(year),
            department_id=department_id,
            actor_user_id=actor_user_id,
        )

        # Có lỗi một phần → cảnh báo thay vì success thuần
        if result.get("failed", 0) > 0 and result.get("processed", 0) == 0:
            return jsonify(swal_error(
                f"Tính lương thất bại cho toàn bộ {result['failed']} nhân viên. "
                "Vui lòng kiểm tra chi tiết lỗi.",
                title="Tính lương thất bại"
            )), HTTPStatus.UNPROCESSABLE_ENTITY

        if result.get("failed", 0) > 0:
            return jsonify(swal_warning(
                f"Đã tính lương thành công {result['processed']} nhân viên. "
                f"Có {result['failed']} nhân viên gặp lỗi.",
                data=result
            )), HTTPStatus.OK

        return jsonify(swal_success(
            f"Đã tính lương thành công cho {result['processed']} nhân viên tháng "
            f"{int(month):02d}/{int(year)}.",
            data=result
        )), HTTPStatus.CREATED

    except ValueError as e:
        return jsonify(swal_error(str(e), title="Không thể tính lương")), HTTPStatus.BAD_REQUEST
    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# GET /payroll
# Lấy danh sách bảng lương (có lọc, tìm kiếm)
# ─────────────────────────────────────────────
@payroll_bp.route("/", methods=["GET"])
@auth_required
@role_required(RoleName.HR, RoleName.ADMIN)
def get_payroll_list():
    """
    Query params (tuỳ chọn):
        month, year, department_id, position_id,
        role_name, status, search, sort_by, sort_order
    """
    try:
        result = HR_payroll_service.get_payroll_list(
            month=request.args.get("month", type=int),
            year=request.args.get("year", type=int),
            department_id=request.args.get("department_id", type=int),
            position_id=request.args.get("position_id", type=int),
            role_name=request.args.get("role_name"),
            status=request.args.get("status"),
            search=request.args.get("search"),
            sort_by=request.args.get("sort_by", "employee_name"),
            sort_order=request.args.get("sort_order", "asc"),
        )

        return jsonify(swal_success("Lấy danh sách bảng lương thành công.", data=result)), HTTPStatus.OK

    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# GET /payroll/<id>
# Xem chi tiết bảng lương + lịch sử thay đổi
# ─────────────────────────────────────────────
@payroll_bp.route("/<int:salary_id>", methods=["GET"])
@auth_required
@role_required(RoleName.HR, RoleName.ADMIN)
def get_payroll_detail(salary_id: int):
    try:
        detail = HR_payroll_service.get_payroll_detail(salary_id)
        return jsonify(swal_success("Lấy chi tiết bảng lương thành công.", data=detail)), HTTPStatus.OK

    except ValueError as e:
        return jsonify(swal_error(str(e), title="Không tìm thấy")), HTTPStatus.NOT_FOUND
    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# POST /payroll/<id>/submit
# Gửi duyệt bảng lương
# ─────────────────────────────────────────────
@payroll_bp.route("/<int:salary_id>/submit", methods=["POST"])
@auth_required
@role_required(RoleName.HR)
def submit_payroll_approval(salary_id: int):
    try:
        actor_user_id = g.user.id

        result = HR_payroll_service.submit_payroll_approval(
            salary_id=salary_id,
            actor_user_id=actor_user_id,
        )

        return jsonify(swal_success(
            "Bảng lương đã được gửi duyệt thành công.",
            data=result
        )), HTTPStatus.OK

    except ValueError as e:
        return jsonify(swal_error(str(e), title="Không thể gửi duyệt")), HTTPStatus.BAD_REQUEST
    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ════════════════════════════════════════════════════════════════
# NHÓM 2: XỬ LÝ KHIẾU NẠI (Complaints & Adjustments)
# ════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# GET /payroll/complaints
# Xem danh sách khiếu nại lương
# ─────────────────────────────────────────────
@payroll_bp.route("/complaints", methods=["GET"])
@auth_required
@role_required(RoleName.HR)
def get_payroll_complaints():
    """
    Query params (tuỳ chọn):
        month   (int)
        year    (int)
        status  (str) – vd: "in_progress", "pending", "resolved"
    """
    try:
        result = HR_payroll_service.get_payroll_complaints(
            month=request.args.get("month", type=int),
            year=request.args.get("year", type=int),
            status=request.args.get("status"),
        )

        return jsonify(swal_success(
            f"Tìm thấy {len(result)} khiếu nại.",
            data={"items": result, "total": len(result)}
        )), HTTPStatus.OK

    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# POST /payroll/complaints/<id>/resolve
# Duyệt / Từ chối khiếu nại
# ─────────────────────────────────────────────
@payroll_bp.route("/complaints/<int:complaint_id>/resolve", methods=["POST"])
@auth_required
@role_required(RoleName.HR)
def handle_complaint(complaint_id: int):
    """
    Body JSON (bắt buộc):
        action          (str) – "in_progress" | "resolved" | "rejected"
        message         (str) – Ghi chú / lý do
        payroll_status  (str, tuỳ chọn) – Trạng thái bảng lương cần cập nhật
    """
    try:
        body = request.get_json(silent=True) or {}

        action  = body.get("action", "").strip()
        message = body.get("message", "").strip()

        if not action:
            return jsonify(swal_error(
                "Vui lòng cung cấp hành động (action).",
                title="Thiếu tham số"
            )), HTTPStatus.BAD_REQUEST

        result = HR_payroll_service.handle_complaint(
            complaint_id=complaint_id,
            action=action,
            handler_employee_id=g.employee.id,
            actor_user_id=g.user.id,
            message=message,
            payroll_status=body.get("payroll_status"),
        )

        action_labels = {
            "in_progress": "Tiếp nhận",
            "resolved":    "Giải quyết",
            "rejected":    "Từ chối",
        }
        label = action_labels.get(action, "Xử lý")

        return jsonify(swal_success(
            f"{label} khiếu nại #{complaint_id} thành công.",
            data=result
        )), HTTPStatus.OK

    except ValueError as e:
        return jsonify(swal_error(str(e), title="Không hợp lệ")), HTTPStatus.BAD_REQUEST
    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# POST /payroll/complaints/investigation/<att_id>
# Lưu ghi chú điều tra chấm công
# ─────────────────────────────────────────────
@payroll_bp.route("/complaints/investigation/<int:attendance_id>", methods=["POST"])
@auth_required
@role_required(RoleName.HR)
def save_investigation_note(attendance_id: int):
    """
    Body JSON (bắt buộc):
        note          (str)
        complaint_id  (int, tuỳ chọn) – Liên kết với khiếu nại cụ thể
    """
    try:
        body = request.get_json(silent=True) or {}

        note = body.get("note", "").strip()
        if not note:
            return jsonify(swal_error(
                "Vui lòng nhập nội dung ghi chú.",
                title="Thiếu thông tin"
            )), HTTPStatus.BAD_REQUEST

        result = HR_payroll_service.save_investigation_note(
            attendance_id=attendance_id,
            note=note,
            actor_user_id=g.user.id,
            complaint_id=body.get("complaint_id"),
        )

        return jsonify(swal_success(
            "Đã lưu ghi chú điều tra thành công.",
            data=result
        )), HTTPStatus.CREATED

    except ValueError as e:
        return jsonify(swal_error(str(e), title="Không tìm thấy")), HTTPStatus.NOT_FOUND
    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# PATCH /payroll/attendance/<id>/adjust
# Điều chỉnh dữ liệu chấm công (xử lý khiếu nại)
# ─────────────────────────────────────────────
@payroll_bp.route("/attendance/<int:attendance_id>/adjust", methods=["PATCH"])
@auth_required
@role_required(RoleName.HR)
def resolve_attendance_complaint(attendance_id: int):
    """
    Body JSON (tuỳ chọn – ít nhất 1 trường phải có):
        check_in        (str) – ISO datetime hoặc "HH:MM"
        check_out       (str) – ISO datetime hoặc "HH:MM"
        attendance_type (str)
        shift_status    (str)
        note            (str) – Lý do điều chỉnh
    """
    try:
        body = request.get_json(silent=True) or {}

        check_in        = body.get("check_in")
        check_out       = body.get("check_out")
        attendance_type = body.get("attendance_type")
        shift_status    = body.get("shift_status")
        note            = body.get("note", "").strip()

        # Yêu cầu ít nhất 1 trường thay đổi
        if not any([check_in, check_out, attendance_type, shift_status]):
            return jsonify(swal_error(
                "Vui lòng cung cấp ít nhất một thông tin cần điều chỉnh "
                "(check_in, check_out, attendance_type hoặc shift_status).",
                title="Thiếu dữ liệu điều chỉnh"
            )), HTTPStatus.BAD_REQUEST

        result = HR_payroll_service.resolve_attendance_complaint(
            attendance_id=attendance_id,
            check_in=check_in,
            check_out=check_out,
            attendance_type=attendance_type,
            shift_status=shift_status,
            note=note,
            actor_user_id=g.user.id,
        )

        return jsonify(swal_success(
            f"Đã điều chỉnh dữ liệu chấm công #{attendance_id} thành công.",
            data=result
        )), HTTPStatus.OK

    except ValueError as e:
        return jsonify(swal_error(str(e), title="Không thể điều chỉnh")), HTTPStatus.BAD_REQUEST
    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR
    
# ─────────────────────────────────────────────
# GET /payroll/complaints/<id>
# Xem chi tiết khiếu nại (Dành cho HR)
# ─────────────────────────────────────────────
@payroll_bp.route("/complaints/<int:complaint_id>", methods=["GET"])
@auth_required
@role_required(RoleName.HR)
def get_hr_complaint_detail(complaint_id: int):
    try:
        detail = HR_payroll_service.hr_complaint_detail(complaint_id)
        
        return jsonify(swal_success(
            "Lấy chi tiết khiếu nại thành công.",
            data=detail
        )), HTTPStatus.OK

    except ValueError as e:
        # Nếu service ném ra lỗi ValueError (ví dụ: không tìm thấy đơn), trả về 404 hoặc 400
        return jsonify(swal_error(str(e), title="Không tìm thấy")), HTTPStatus.NOT_FOUND
    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR
    
@payroll_bp.route("/analytics/total-fund", methods=["GET"])
@auth_required
@role_required(RoleName.HR, RoleName.ADMIN)
def get_total_payroll_fund():
    """
    GET /api/payroll/analytics/total-fund

    Query params:
        period_type   : "month" | "quarter" | "year"   (bắt buộc)
        year          : int                             (bắt buộc)
        month         : int 1-12                        (bắt buộc nếu period_type="month")
        quarter       : int 1-4                         (bắt buộc nếu period_type="quarter")
        department_id : int                             (tuỳ chọn)
        role_name     : str                             (tuỳ chọn)
        status        : str, nhiều giá trị cách nhau dấu phẩy
                        vd: "approved,paid,locked"      (tuỳ chọn)

    Response (Swal-compatible):
        200 OK  → { success: true,  title, text, data }
        400     → { success: false, title, text }
        500     → { success: false, title, text }
    """
    # ── 1. Đọc & validate tham số bắt buộc ────────────────────────────────
    period_type = request.args.get("period_type", "").strip().lower()
    if period_type not in ("month", "quarter", "year"):
        return jsonify({
            "success": False,
            "icon":    "warning",
            "title":   "Tham số không hợp lệ",
            "text":    "period_type phải là 'month', 'quarter' hoặc 'year'.",
        }), 400

    raw_year = request.args.get("year")
    if not raw_year or not raw_year.isdigit():
        return jsonify({
            "success": False,
            "icon":    "warning",
            "title":   "Tham số không hợp lệ",
            "text":    "Vui lòng truyền năm hợp lệ (vd: year=2025).",
        }), 400
    year = int(raw_year)

    # ── 2. Đọc tham số theo period_type ───────────────────────────────────
    month   = None
    quarter = None

    if period_type == "month":
        raw_month = request.args.get("month")
        if not raw_month or not raw_month.isdigit() or not (1 <= int(raw_month) <= 12):
            return jsonify({
                "success": False,
                "icon":    "warning",
                "title":   "Tham số không hợp lệ",
                "text":    "Vui lòng truyền tháng hợp lệ từ 1 đến 12 (vd: month=5).",
            }), 400
        month = int(raw_month)

    elif period_type == "quarter":
        raw_quarter = request.args.get("quarter")
        if not raw_quarter or not raw_quarter.isdigit() or int(raw_quarter) not in (1, 2, 3, 4):
            return jsonify({
                "success": False,
                "icon":    "warning",
                "title":   "Tham số không hợp lệ",
                "text":    "Vui lòng truyền quý hợp lệ từ 1 đến 4 (vd: quarter=2).",
            }), 400
        quarter = int(raw_quarter)

    # ── 3. Tham số tuỳ chọn ───────────────────────────────────────────────
    department_id = None
    raw_dept = request.args.get("department_id")
    if raw_dept:
        if not raw_dept.isdigit():
            return jsonify({
                "success": False,
                "icon":    "warning",
                "title":   "Tham số không hợp lệ",
                "text":    "department_id phải là số nguyên dương.",
            }), 400
        department_id = int(raw_dept)

    role_name_filter = request.args.get("role_name", "").strip() or None
    valid_roles = {RoleName.ADMIN, RoleName.HR, RoleName.MANAGER, RoleName.EMPLOYEE}
    if role_name_filter and role_name_filter not in valid_roles:
        return jsonify({
            "success": False,
            "icon":    "warning",
            "title":   "Tham số không hợp lệ",
            "text":    f"role_name không hợp lệ. Các giá trị cho phép: {', '.join(valid_roles)}.",
        }), 400

    # Tham số staus: chuỗi "approved,paid" → list ["approved", "paid"]
    status_filter = None
    raw_status = request.args.get("status", "").strip()
    if raw_status:
        status_filter = [s.strip() for s in raw_status.split(",") if s.strip()]

    # ── 4. Gọi service ────────────────────────────────────────────────────
    try:
        result = HR_payroll_service.get_total_payroll_fund(
            period_type   = period_type,
            year          = year,
            month         = month,
            quarter       = quarter,
            department_id = department_id,
            role_name     = role_name_filter,
            status_filter = status_filter,
        )
    except ValueError as e:
        return jsonify({
            "success": False,
            "icon":    "warning",
            "title":   "Không thể tính quỹ lương",
            "text":    str(e),
        }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "icon":    "error",
            "title":   "Lỗi hệ thống",
            "text":    "Đã xảy ra lỗi khi tính quỹ lương. Vui lòng thử lại sau.",
        }), 500

    # ── 5. Trả về Swal-compatible response ────────────────────────────────
    period  = result["period"]
    summary = result["summary"]

    return jsonify({
        "success": True,
        "icon":    "success",
        "title":   f"Quỹ lương {period['label']}",
        "text": (
            f"Tổng chi phí nhân sự: {summary['total_labor_cost']:,.0f} đ | "
            f"Số phiếu lương: {summary['salary_count']} | "
            f"Số nhân viên: {result['employee_count']}"
        ),
        "data": result,
    }), 200

@payroll_bp.route("/hr/generate", methods=["GET"])
@auth_required
@role_required(RoleName.HR)
def hr_generate_page():
    """
    Hiển thị trang Tạo Bảng Lương cho HR.
    Chức năng: chạy tính lương hàng loạt, xem danh sách bảng lương, gửi duyệt.
    """
    return render_template("modules/payroll/hr_generate.html")


@payroll_bp.route("/analytics", methods=["GET"])
@auth_required
@role_required(RoleName.HR, RoleName.ADMIN)
def payroll_analytics():
    """
    Render trang Phân tích Quỹ Lương.
    Đây là trang dashboard cho phép HR và Admin xem các biểu đồ và số liệu
    tổng hợp về chi phí lương của công ty.
    """
    return render_template("modules/payroll/analytics.html")