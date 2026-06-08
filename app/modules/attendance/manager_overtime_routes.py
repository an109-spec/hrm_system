from calendar import calendar
from datetime import date, datetime, timedelta, time
from decimal import Decimal
from app.constants.attendance import WorkConfig
from flask import request, jsonify, g
from app.constants.common import RoleName
from app.constants.payroll import SalaryStatus
from app.extensions.db import db
from app.common.security.decorators import auth_required, role_required, self_or_hr_required
from app.common.exceptions import ValidationError, ForbiddenError, UnauthorizedError
from app.models.contract import Contract
from app.models.salary import Salary
from app.modules.attendance.attendance_query_service import AttendanceCommandService
from app.modules.attendance.attendance_workflow_service import Attendance_workflow_service
from app.modules.attendance.attendance_state_service import AttendanceStateService
from app.modules.attendance.attendance_calculation_service import attendance_calculation_service
from app.modules.attendance.overtime_service import OvertimeService
from . import attendance_bp
from app.modules.attendance.service import AttendanceService
from app.models.attendance import Attendance, AttendanceShiftStatus, AttendanceType
from app.models.overtime_request import OvertimeRequest
from app.models.employee import Employee
from app.utils.time import VN_TIMEZONE, get_current_time, _normalize, set_simulated_time

@attendance_bp.route("/manager/overtime/<int:id>/approve", methods=["POST"])
@auth_required
@role_required(RoleName.MANAGER)
def manager_approve_overtime(id):
    """
    [API Endpoint] Quản lý phê duyệt đơn tăng ca của nhân viên thuộc cấp quản lý.
    Kiểm tra chặt chẽ điều kiện: Phải là quản lý trực tiếp HOẶC là Trưởng phòng của nhân viên đó.
    """
    # 1. Lấy thông tin đối tượng Employee của Manager đang đăng nhập từ hệ thống
    current_manager = getattr(g, "employee", None)
    
    # --- KỊCH BẢN 1: KHÔNG TÌM THẤY THÔNG TIN NGƯỜI ĐĂNG NHẬP (401) ---
    if not current_manager:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "unauthorized",
            "message": "Không tìm thấy thông tin nhân sự của tài khoản đang đăng nhập.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi xác thực",
                "allowOutsideClick": False
            },
            "data": None
        }), 401

    # 2. Truy vấn đơn tăng ca
    ot_request = OvertimeRequest.query.get(id)
    
    # --- KỊCH BẢN 2: KHÔNG TÌM THẤY ĐƠN TĂNG CA (404) ---
    if not ot_request:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "not_found",
            "message": f"Không tìm thấy yêu cầu tăng ca mã #{id}.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Không tìm thấy đơn",
                "allowOutsideClick": True
            },
            "data": None
        }), 404

    # 3. Lấy thông tin nhân viên gửi đơn (Tận dụng mối quan hệ có sẵn trên bản ghi ot_request)
    subordinate = ot_request.employee  
    if not subordinate:
        # Fallback nếu chưa cấu hình relationship 'employee' trên OvertimeRequest
        subordinate = Employee.query.get(ot_request.employee_id)

    # --- KỊCH BẢN 3: KHÔNG TÌM THẤY CHỦ ĐƠN TRÊN HỆ THỐNG (404) ---
    if not subordinate:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "not_found",
            "message": "Dữ liệu nhân viên gửi đơn này không tồn tại trên hệ thống.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi dữ liệu nhân sự",
                "allowOutsideClick": True
            },
            "data": None
        }), 404

    # Điều kiện A: Manager này là quản lý trực tiếp của nhân viên (Dựa trên manager_id)
    is_direct_manager = (subordinate.manager_id == current_manager.id)
    
    # Điều kiện B: Manager này là Trưởng phòng của phòng ban mà nhân viên đó đang thuộc về
    is_department_head = False
    if subordinate.department and subordinate.department.manager_id == current_manager.id:
        is_department_head = True
    
    # --- KỊCH BẢN 4: SAI THẨM QUYỀN PHÊ DUYỆT (403) ---
    if not (is_direct_manager or is_department_head):
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "forbidden",
            "message": "Thao tác bị từ chối! Bạn không phải là Quản lý trực tiếp hoặc Trưởng phòng của nhân viên này.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Bị chặn phân quyền",
                "allowOutsideClick": True
            },
            "data": None
        }), 403

    # --- KỊCH BẢN 5: ĐƠN ĐÃ ĐƯỢC DUYỆT TRƯỚC ĐÓ RỒI (400) ---
    if ot_request.status == "approved":
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "validation_error",
            "message": "Yêu cầu tăng ca này đã được phê duyệt trước đó rồi.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "info",
                "title": "Đơn đã xử lý",
                "allowOutsideClick": True
            },
            "data": None
        }), 400

    try:
        # 5. Lưu vết người duyệt (Model Employee của bạn có trường approved_overtimes liên kết qua approved_by)
        if hasattr(ot_request, 'approved_by'):
            ot_request.approved_by = current_manager.id
            
        # Gọi tầng nghiệp vụ để cập nhật trạng thái đơn thành approved
        AttendanceService.handle_ot_approved(ot_request=ot_request)
        db.session.commit()
        
        # --- KỊCH BẢN THÀNH CÔNG (200 OK) ---
        return jsonify({
            "success": True,
            "status": "success",
            "message": f"Đã phê duyệt thành công đơn tăng ca của nhân viên {subordinate.full_name}.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Phê duyệt thành công",
                "allowOutsideClick": False  # Buộc click OK để FE đồng bộ/tải lại danh sách đơn
            },
            "data": {
                "request_id": ot_request.id,
                "status": ot_request.status,
                "approved_by": current_manager.full_name
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        # --- KỊCH BẢN 6: LỖI HỆ THỐNG PHÁT SINH PHÍA DATABASE (500) ---
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "system_error",
            "message": f"Lỗi phát sinh trong quá trình xử lý cơ sở dữ liệu: {str(e)}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống",
                "allowOutsideClick": True
            },
            "data": None
        }), 500
    
@attendance_bp.route("/manager/overtime/<int:id>/reject", methods=["POST"])
@auth_required
@role_required(RoleName.MANAGER)
def manager_reject_overtime(id):
    current_manager = getattr(g, "employee", None)
    if not current_manager:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "unauthorized",
            "message": "Không tìm thấy dữ liệu nhân sự tương ứng với tài khoản đăng nhập.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi xác thực",
                "allowOutsideClick": False
            },
            "data": None
        }), 401

    data = request.get_json() or {}
    reason = data.get("reason", "").strip()
    if not reason:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "validation_error",
            "message": "Vui lòng nhập lý do từ chối đơn từ (tham số 'reason' không được để trống).",
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",
                "title": "Thiếu lý do từ chối",
                "allowOutsideClick": True
            },
            "data": None
        }), 400
    ot_request = OvertimeRequest.query.get(id)
    if not ot_request:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "not_found",
            "message": f"Không tìm thấy yêu cầu tăng ca mã #{id}.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Không tìm thấy đơn",
                "allowOutsideClick": True
            },
            "data": None
        }), 404
    subordinate = ot_request.employee
    if not subordinate:
        subordinate = Employee.query.get(ot_request.employee_id)
    if not subordinate:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "not_found",
            "message": "Không tìm thấy thông tin nhân viên sở hữu đơn này.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi dữ liệu nhân sự",
                "allowOutsideClick": True
            },
            "data": None
        }), 404
    is_direct_manager = (subordinate.manager_id == current_manager.id)
    is_department_head = (
        subordinate.department is not None 
        and subordinate.department.manager_id == current_manager.id
    )
    if not (is_direct_manager or is_department_head):
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "forbidden",
            "message": "Thao tác bị từ chối! Bạn không phải là Quản lý trực tiếp hoặc Trưởng phòng của nhân viên này.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Bị chặn phân quyền",
                "allowOutsideClick": True
            },
            "data": None
        }), 403
    if ot_request.status == "rejected":
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "validation_error",
            "message": "Yêu cầu tăng ca này đã ở trạng thái từ chối trước đó.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "info",
                "title": "Đơn đã xử lý",
                "allowOutsideClick": True
            },
            "data": None
        }), 400
    try:
        if hasattr(ot_request, 'approved_by'):
            ot_request.approved_by = current_manager.id
        AttendanceService.handle_ot_rejected(ot_request=ot_request, reason=reason)
        db.session.commit()
        return jsonify({
            "success": True,
            "status": "success",
            "message": f"Đã từ chối đơn tăng ca của nhân viên {subordinate.full_name}.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "success", 
                "title": "Đã từ chối đơn",
                "allowOutsideClick": False  # Buộc click để FE bắt sự kiện reload danh sách đơn từ
            },
            "data": {
                "request_id": ot_request.id,
                "status": ot_request.status,
                "rejection_reason": ot_request.rejection_reason
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "system_error",
            "message": f"Lỗi phát sinh trong quá trình xử lý cơ sở dữ liệu: {str(e)}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống",
                "allowOutsideClick": True
            },
            "data": None
        }), 500