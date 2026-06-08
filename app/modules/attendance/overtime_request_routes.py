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

@attendance_bp.route('/overtime/requests', methods=['POST'])
@auth_required  
@role_required(RoleName.EMPLOYEE, RoleName.MANAGER)  
def create_overtime_request():
    try:
        data = request.get_json() or {}   
        
        # 1. Xác định chính xác User ID của nhân viên được đăng ký tăng ca
        if g.user.role.name == RoleName.MANAGER and "employee_id" in data:
            try:
                emp_id = int(data.get("employee_id"))
                # Service tìm kiếm hồ sơ qua user_id, ta truy vấn nhanh từ employee_id ra user_id
                target_emp = Employee.query.filter_by(id=emp_id, is_deleted=False).first()
                if not target_emp:
                    raise ValidationError("Không tìm thấy hồ sơ nhân viên do Quản lý chỉ định.")
                target_user_id = target_emp.user_id
            except (ValueError, TypeError):
                raise ValidationError("ID nhân viên do Quản lý chỉ định không đúng định dạng số.")
        else:
            if not g.employee:
                raise ValidationError("Tài khoản của bạn chưa được liên kết với bất kỳ hồ sơ nhân sự nào.")
            target_user_id = g.user.id

        # 2. Đóng gói payload đúng định dạng Dictionary mà tầng Service yêu cầu
        # Chuyển đổi tên trường 'target_date' từ frontend thành 'overtime_date' để đồng bộ
        service_payload = {
            "overtime_date": data.get("target_date"),
            "start_time": data.get("start_time", "18:00"),  # Nhận giờ bắt đầu từ Client (mặc định 18:00)
            "end_time": data.get("end_time", "22:00"),      # Nhận giờ kết thúc từ Client (mặc định 22:00)
            "reason": data.get("reason"),
            "note": data.get("note")
        }

        # 3. Gọi Service xử lý nghiệp vụ tập trung
        result = OvertimeService.create_overtime_request(
            user_id=target_user_id,
            payload=service_payload,
            actor_user_id=g.user.id  # Người thực hiện thao tác bấm nút trên giao diện
        )
        
        # Bóc tách cụm dữ liệu inner trả về từ Service
        res_data = result.get("data", {})

        # 4. Trả phản hồi chuẩn hóa về cho Client hiển thị thông báo SweetAlert
        return jsonify({
            "success": True,
            "status": "success",
            "message": result.get("message") or "Đã gửi yêu cầu làm thêm giờ thành công!",
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Nộp đơn thành công",
                "allowOutsideClick": False  # Ép người dùng nhấn OK để reload trang dữ liệu mới
            },
            "data": {
                "request_id": res_data.get("request_id"),
                "overtime_status": res_data.get("status"),
                "requested_hours": float(res_data.get("requested_hours", 0)),
                "target_date": res_data.get("overtime_date"),
                "server_time": get_current_time().isoformat()
            }
        }), 201

    except ValidationError as e:
        return jsonify({
            "success": False,
            "status": "error",
            "message": str(e),
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",
                "title": "Thông tin chưa hợp lệ",
                "allowOutsideClick": True
            },
            "data": None
        }), 400

    except ValueError as e:
        # Bắt toàn bộ các ngoại lệ chặn logic (Validation của ngày tháng, trùng lặp đơn) từ tầng Service đưa lên
        return jsonify({
            "success": False,
            "status": "error",
            "message": str(e),
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",
                "title": "Không thể xử lý đơn",
                "allowOutsideClick": True
            },
            "data": None
        }), 400

    except Exception as e:
        # Ghi log lỗi chi tiết ra màn hình console của Server để ông dễ theo dõi debug khi làm đồ án
        print(f"❌ [CRITICAL ERROR] Create Overtime Exception: {str(e)}")
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Hệ thống gặp sự cố trong quá trình lưu đơn yêu cầu. Vui lòng thử lại sau!",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống",
                "allowOutsideClick": True
            },
            "data": None
        }), 500

@attendance_bp.route('/overtime/requests/<int:request_id>/approve', methods=['POST'])
@auth_required
@role_required(RoleName.MANAGER)
def approve_overtime_request(request_id):
    try:
        if not g.employee:
            raise ValidationError("Tài khoản Manager của bạn chưa liên kết với hồ sơ nhân sự trên hệ thống.")
        data = request.get_json() or {}
        approved_hours = data.get('approved_hours', None)
        result = OvertimeService.approve_overtime(
            request_id=request_id,
            approver_id=g.employee.id, 
            approved_hours=approved_hours
        )
        return jsonify({
            "success": True,
            "status": "success",  
            "message": result.get("message") or "Đã phê duyệt đơn yêu cầu làm thêm giờ thành công.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Phê duyệt thành công",
                "allowOutsideClick": False  
            },
            "data": result
        }), 200

    except ValidationError as e:
        return jsonify({
            "success": False,
            "status": "success", 
            "message": str(e),
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",
                "title": "Không thể duyệt đơn",
                "allowOutsideClick": True
            },
            "data": None
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Đã xảy ra lỗi hệ thống trong quá trình phê duyệt đơn.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống (500)",
                "allowOutsideClick": True
            },
            "data": None
        }), 500
    
@attendance_bp.route('/overtime/requests/<int:request_id>/reject', methods=['POST'])
@auth_required
@role_required(RoleName.MANAGER) 
def reject_overtime_request(request_id):
    try:
        if not g.employee:
            raise ValidationError("Tài khoản Manager của bạn chưa được liên kết với hồ sơ nhân sự.")
        data = request.get_json() or {}
        reject_reason = data.get("reject_reason", "").strip()
        result = OvertimeService.reject_overtime(
            request_id=request_id,
            reject_reason=reject_reason,
            approver_id=g.employee.id
        )
        return jsonify({
            "success": True,
            "status": "success",  
            "message": result.get("message") or "Đã từ chối đơn yêu cầu làm thêm giờ.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Đã từ chối đơn",
                "allowOutsideClick": False  # Bắt người dùng ấn OK để reload trang cập nhật bảng
            },
            "data": result
        }), 200

    except ValidationError as e:
        return jsonify({
            "success": False,
            "status": "success",  
            "message": str(e),
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",
                "title": "Không thể xử lý",
                "allowOutsideClick": True
            },
            "data": None
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Đã xảy ra lỗi hệ thống khi xử lý từ chối đơn.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống (500)",
                "allowOutsideClick": True
            },
            "data": None
        }), 500

@attendance_bp.route('/overtime/check-eligibility', methods=['GET'])
@auth_required
@role_required(RoleName.EMPLOYEE)  
def check_overtime_eligibility():
    try:
        if not g.employee:
            raise ValidationError("Tài khoản của bạn chưa được liên kết với hồ sơ nhân sự.")
            
        date_str = request.args.get('date')
        now_dt = get_current_time()
        
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                raise ValidationError("Định dạng ngày không hợp lệ. Vui lòng sử dụng YYYY-MM-DD.")
        else:
            target_date = now_dt.date()

        # Gọi hàm kiểm tra điều kiện cốt lõi của OvertimeService
        OvertimeService.can_start_ot(
            employee_id=g.employee.id,
            target_date=target_date
        )
        
        # --- TRƯỜNG HỢP 1: ĐỦ ĐIỀU KIỆN TĂNG CA (ELIGIBLE = TRUE) ---
        return jsonify({
            "success": True,
            "status": "success",  # Giữ nguyên key gốc của bạn để tránh ảnh hưởng logic cũ
            "message": "Bạn hoàn toàn đủ điều kiện thực hiện ca làm thêm (OT)!",
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Hợp lệ",
                "toast": True,        # Dạng toast góc màn hình nhẹ nhàng cho TH thành công
                "position": "top-end",
                "timer": 2000,
                "allowOutsideClick": True
            },
            "data": {
                "eligible": True,
                "reason": None
            }
        }), 200

    except ValidationError as e:
        # --- TRƯỜNG HỢP 2: KHÔNG ĐỦ ĐIỀU KIỆN / LỖI INPUT (ELIGIBLE = FALSE) ---
        reason_text = str(e)
        return jsonify({
            "success": False,
            "status": "success",  # Giữ nguyên status="success" theo đúng logic ban đầu của bạn
            "message": reason_text,
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",     # Hiện icon Warning cảnh báo lý do từ chối
                "title": "Chưa thể tăng ca",
                "allowOutsideClick": False  # Ép nhân viên phải ấn "OK" xác nhận đã đọc lý do
            },
            "data": {
                "eligible": False,
                "reason": reason_text
            }
        }), 200

    except Exception as e:
        # --- TRƯỜNG HỢP 3: LỖI HỆ THỐNG PHÁT SINH NGOÀI Ý MUỐN ---
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Đã xảy ra lỗi hệ thống trong quá trình thẩm định điều kiện.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống",
                "allowOutsideClick": True
            },
            "data": {
                "eligible": False,
                "reason": "Internal Server Error"
            }
        }), 500