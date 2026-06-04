from flask import request, jsonify, g, url_for
from app.modules.leave import leave_bp
from app.modules.leave.service import LeaveService
from app.common.security.decorators import auth_required, role_required
from app.constants.common import RoleName


# ─────────────────────────────────────────────
# 1. Danh sách lịch sử nghỉ phép cá nhân
# ─────────────────────────────────────────────
@leave_bp.route("/my-requests", methods=["GET"])
@auth_required

def my_requests():
    try:
        data = LeaveService.get_my_requests(g.employee.id)
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# 2. Tạo đơn nghỉ phép mới
# ─────────────────────────────────────────────
@leave_bp.route("/request/create", methods=["GET", "POST"])
@auth_required
def create_request():
    if request.method == "GET":
        try:
            form_data = LeaveService.get_create_form_data(g.employee.id)
            return jsonify({
                "success": True,
                "data": form_data
            }), 200
        except Exception as e:
            return jsonify({
                "success": False,
                "swal": {
                    "icon": "error",
                    "title": "Không thể tải form",
                    "text": str(e)
                }
            }), 500

    # POST – Tạo đơn mới
    try:
        payload = request.get_json(force=True) or {}
        result = LeaveService.create_leave_request(g.employee.id, payload)
        return jsonify({
            "success": True,
            "swal": {
                "icon": "success",
                "title": "Gửi đơn thành công",
                "text": "Đơn nghỉ phép của bạn đã được gửi và đang chờ duyệt."
            },
            "data": result
        }), 201
    except ValueError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "warning",
                "title": "Dữ liệu không hợp lệ",
                "text": str(e)
            }
        }), 422
    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Tạo đơn thất bại",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# 3. Xem chi tiết đơn cá nhân
# ─────────────────────────────────────────────
@leave_bp.route("/request/<int:id>", methods=["GET"])
@auth_required
def get_detail(id):
    try:
        data = LeaveService.get_leave_request_detail(id, g.employee.id)
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except PermissionError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Không có quyền truy cập",
                "text": str(e)
            }
        }), 403
    except LookupError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "warning",
                "title": "Không tìm thấy",
                "text": str(e)
            }
        }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi hệ thống",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# 4. Hủy đơn đang chờ duyệt
# ─────────────────────────────────────────────
@leave_bp.route("/request/cancel/<int:id>", methods=["POST"])
@auth_required
def cancel_request(id):
    try:
        LeaveService.cancel_request(id, g.employee.id)
        return jsonify({
            "success": True,
            "swal": {
                "icon": "success",
                "title": "Hủy đơn thành công",
                "text": "Đơn nghỉ phép đã được hủy."
            }
        }), 200
    except PermissionError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Không có quyền",
                "text": str(e)
            }
        }), 403
    except ValueError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "warning",
                "title": "Không thể hủy",
                "text": str(e)
            }
        }), 422
    except LookupError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "warning",
                "title": "Không tìm thấy đơn",
                "text": str(e)
            }
        }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi hệ thống",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# 5. Danh sách đơn cần phê duyệt (Manager)
# ─────────────────────────────────────────────
@leave_bp.route("/manager/pending", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def mgr_pending_list():
    try:
        data = LeaveService.get_pending_requests_for_manager(g.employee.id)
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi tải danh sách",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# 6. Xem chi tiết đơn để duyệt / từ chối (Manager)
# ─────────────────────────────────────────────
@leave_bp.route("/manager/request/<int:id>", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def mgr_view_detail(id):
    try:
        data = LeaveService.get_leave_request_for_manager(id, g.employee.id)
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except PermissionError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Không có quyền truy cập",
                "text": str(e)
            }
        }), 403
    except LookupError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "warning",
                "title": "Không tìm thấy đơn",
                "text": str(e)
            }
        }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi hệ thống",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# 7. Duyệt đơn (Manager)
# ─────────────────────────────────────────────
@leave_bp.route("/manager/approve/<int:id>", methods=["POST"])
@auth_required
@role_required(RoleName.MANAGER)
def mgr_approve(id):
    try:
        LeaveService.approve_leave_request(id, g.employee.id)
        return jsonify({
            "success": True,
            "swal": {
                "icon": "success",
                "title": "Đã duyệt",
                "text": "Đơn nghỉ phép đã được phê duyệt thành công."
            }
        }), 200
    except PermissionError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Không có quyền",
                "text": str(e)
            }
        }), 403
    except LookupError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "warning",
                "title": "Không tìm thấy đơn",
                "text": str(e)
            }
        }), 404
    except ValueError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "warning",
                "title": "Không thể duyệt",
                "text": str(e)
            }
        }), 422
    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi hệ thống",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# 8. Từ chối đơn (Manager – có ghi lý do)
# ─────────────────────────────────────────────
@leave_bp.route("/manager/reject/<int:id>", methods=["POST"])
@auth_required
@role_required(RoleName.MANAGER)
def mgr_reject(id):
    try:
        payload = request.get_json(force=True) or {}
        reject_reason = payload.get("reason", "").strip()
        if not reject_reason:
            return jsonify({
                "success": False,
                "swal": {
                    "icon": "warning",
                    "title": "Thiếu lý do",
                    "text": "Vui lòng nhập lý do từ chối trước khi xác nhận."
                }
            }), 422

        LeaveService.reject_leave_request(id, g.employee.id, reject_reason)
        return jsonify({
            "success": True,
            "swal": {
                "icon": "success",
                "title": "Đã từ chối",
                "text": "Đơn nghỉ phép đã bị từ chối."
            }
        }), 200
    except PermissionError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Không có quyền",
                "text": str(e)
            }
        }), 403
    except LookupError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "warning",
                "title": "Không tìm thấy đơn",
                "text": str(e)
            }
        }), 404
    except ValueError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "warning",
                "title": "Không thể từ chối",
                "text": str(e)
            }
        }), 422
    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi hệ thống",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# 9. Xem lịch nghỉ của team
# ─────────────────────────────────────────────
@leave_bp.route("/team/calendar", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.HR)
def team_calendar():
    try:
        data = LeaveService.get_team_leave_requests(g.employee.id)
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi tải lịch nghỉ",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# 10. Báo cáo nghỉ phép phòng ban
# ─────────────────────────────────────────────
@leave_bp.route("/dept/report", methods=["GET"])
@auth_required
@role_required(RoleName.HR, RoleName.MANAGER)
def dept_report():
    try:
        data = LeaveService.get_department_leave_requests(g.employee.id)
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi tải báo cáo",
                "text": str(e)
            }
        }), 500
    

# ─────────────────────────────────────────────
# 11. Danh sách đơn nghỉ phép của team (Manager)
# Hỗ trợ lọc qua Query Parameters: status, from_date, to_date, is_paid, 
# employee_name, employee_code, department, leave_type, emergency_only, has_attachment
# ─────────────────────────────────────────────
@leave_bp.route("/manager/leaves", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def get_manager_leaves():
    try:
        # Lấy tất cả tham số từ URL (?status=pending&...)
        filters = request.args.to_dict()
        
        # Gọi service
        data = LeaveService.get_leave_requests(g.employee.id, filters)
        
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi tải danh sách",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# 12. Thống kê nghỉ phép của team (Dashboard summary)
# ─────────────────────────────────────────────
@leave_bp.route("/manager/leaves/summary", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def get_manager_leave_summary():
    try:
        # Gọi service
        data = LeaveService.get_leave_summary(g.employee.id)
        
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi tải thống kê",
                "text": str(e)
            }
        }), 500