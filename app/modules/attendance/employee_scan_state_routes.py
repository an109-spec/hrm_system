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

@attendance_bp.route("/decline-offday", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE)
def employee_decline_offday():
    current_employee = getattr(g, "employee", None)
    if not current_employee:
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

    today_date = get_current_time().date()
    service_payload = {
        "decline_offday_work": True
    }

    try:
        result = AttendanceService._handle_offday_logic(
            employee_id=current_employee.id,
            payload=service_payload,
            today=today_date
        )
        if result.get("pass_through") is True:
            return jsonify({
                "success": False,
                "status": "error",
                "error_type": "validation_error",
                "message": "Thao tác thất bại. Hôm nay là ngày làm việc tiêu chuẩn, không phải ngày lễ hoặc ngày nghỉ cuối tuần.",
                "swal_hint": {
                    "show_on_load": True,
                    "icon": "warning",
                    "title": "Không thể thao tác",
                    "allowOutsideClick": True
                },
                "data": None
            }), 400
        if result.get("action") == "attendance_not_required":
            return jsonify({
                "success": True,
                "status": "success",
                "message": result.get("message"),
                "swal_hint": {
                    "show_on_load": True,
                    "icon": "info",
                    "title": "Thông báo miễn trừ",
                    "allowOutsideClick": True
                },
                "data": result
            }), 200
        if result.get("final") and result.get("locked_state"):
            return jsonify({
                "success": True,
                "status": "success",
                "message": result.get("message"),
                "swal_hint": {
                    "show_on_load": True,
                    "icon": "success",
                    "title": "Xác nhận nghỉ thành công",
                    "allowOutsideClick": False  # Ép người dùng bấm OK để reload lại giao diện nút bấm mới
                },
                "data": {
                    "action": result.get("action"),
                    "attendance_state": result.get("attendance_state"),
                    "attendance": result.get("attendance")
                }
            }), 200
        return jsonify({
            "success": True,
            "status": "success",
            "message": "Xử lý thông tin ngày nghỉ hoàn tất.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Ghi nhận thành công",
                "allowOutsideClick": True
            },
            "data": result
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "system_error",
            "message": f"Lỗi phát sinh trong quá trình xử lý đóng bảng công ngày nghỉ: {str(e)}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống",
                "allowOutsideClick": True
            },
            "data": None
        }), 500
    
@attendance_bp.route("/employee/scan", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE)
def employee_scan_any_qr():
    current_employee = getattr(g, "employee", None)
    if not current_employee:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "unauthorized",
            "message": "Không tìm thấy thông tin nhân sự của tài khoản này.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi xác thực",
                "allowOutsideClick": False
            },
            "data": None
        }), 401
    payload = request.get_json() or {}
    raw_qr_text = payload.get("qr_content", "").strip()
    if not raw_qr_text:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "validation_error",
            "message": "Không thể xử lý. Camera chưa quét được nội dung ký tự nào từ mã QR này.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",
                "title": "Mã QR không hợp lệ",
                "allowOutsideClick": True
            },
            "data": None
        }), 400
    try:
        now_dt = get_current_time()
        return jsonify({
            "success": True,
            "status": "success",
            "message": "Ghi nhận tín hiệu quét mã QR thành công!",
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Quét mã thành công",
                "allowOutsideClick": False  
            },
            "data": {
                "employee_id": current_employee.id,
                "employee_name": current_employee.full_name,
                "scanned_at": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "captured_content": raw_qr_text  # Trả ra để hiển thị debug hoặc xử lý giải mã ở bước sau
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "system_error",
            "message": f"Gặp lỗi trong quá trình phân tích lượt quét: {str(e)}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống",
                "allowOutsideClick": True
            },
            "data": None
        }), 500

@attendance_bp.route("/state", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE)
def get_current_state():
    employee = getattr(g, "employee", None)
    if not employee:
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Không tìm thấy thông tin nhân viên trong phiên làm việc. Vui lòng đăng nhập lại.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",
                "title": "Hết phiên làm việc",
                "allowOutsideClick": False
            },
            "data": None
        }), 400
    data = request.get_json() or {}
    sim_time_str = data.get("sim_time")
    if sim_time_str:
        current_time = _normalize(sim_time_str)
        if not current_time:
            return jsonify({
                "success": False,
                "status": "error",
                "message": "Chuỗi thời gian giả lập không đúng định dạng ISO.",
                "swal_hint": {
                    "show_on_load": True,
                    "icon": "error",
                    "title": "Sai định dạng thời gian",
                    "allowOutsideClick": True
                },
                "data": None
            }), 400
    else:
        current_time = get_current_time()
    today = current_time.date()
    try:
        attendance_record = Attendance.query.filter_by(
            employee_id=employee.id
        ).order_by(Attendance.date.desc()).first()
        if attendance_record and attendance_record.date < today - timedelta(days=1):
            attendance_record = None
        ot_request = OvertimeRequest.query.filter_by(
            employee_id=employee.id,
            overtime_date=today
        ).first()
        state_dto = AttendanceStateService.compute_attendance_state(
            now=current_time,
            attendance=attendance_record,
            ot_request=ot_request
        )
        return jsonify({
            "success": True,
            "status": "success",
            "message": "Đồng bộ trạng thái giao diện thành công.",
            "swal_hint": {
                "show_on_load": False,
                "icon": "success",
                "title": "Thành công"
            },
            "data": {
                "state": state_dto.state,
                "button_enabled": state_dto.button_enabled,
                "button_text": state_dto.button_text,
                "can_scan": state_dto.can_scan,
                "message": state_dto.message,
                "locked_state": getattr(state_dto, "locked_state", False)
            }
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "SYSTEM_ERROR",
            "message": f"Hệ thống gặp lỗi khi tính toán trạng thái hiển thị: {str(e)}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi tải trạng thái",
                "allowOutsideClick": True
            },
            "data": None
        }), 500
    
@attendance_bp.route('/checkout', methods=['POST'])
@auth_required  
@role_required(RoleName.EMPLOYEE)
def checkout_regular():
    employee = g.employee
    current_time = get_current_time()
    today = current_time.date()
    
    attendance = Attendance.query.filter_by(
        employee_id=employee.id, 
        date=today
    ).first()
    
    # --- KỊCH BẢN 1: CHƯA CHECK-IN (400) ---
    if not attendance:
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Không tìm thấy bản ghi Check-in cho ngày hôm nay. Vui lòng Check-in trước.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",
                "title": "Chưa Check-in!",
                "allowOutsideClick": True
            },
            "data": None
        }), 400
        
    # --- KỊCH BẢN 2: ĐÃ CHECK-OUT RỒI (400) ---
    if attendance.check_out:
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Hệ thống ghi nhận bạn đã thực hiện Check-out trước đó rồi.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "info",
                "title": "Đã Check-out",
                "allowOutsideClick": True
            },
            "data": None
        }), 400

    try:
        attendance.check_out = current_time
        time_delta = attendance.check_out - attendance.check_in
        total_seconds = time_delta.total_seconds()
        raw_hours = total_seconds / 3600.0
        
        if attendance.check_in.time() < time(12, 0) and attendance.check_out.time() > time(13, 0):
            raw_hours -= 1.0
            
        attendance.regular_hours = max(Decimal("0.00"), Decimal(f"{raw_hours:.2f}"))
        workday_end_time = datetime.combine(today, WorkConfig.WORKDAY_END).replace(tzinfo=VN_TIMEZONE)
        if current_time < workday_end_time:
            early_delta = workday_end_time - current_time
            attendance.early_leave_minutes = int(early_delta.total_seconds() // 60)
        else:
            attendance.early_leave_minutes = 0
        work_unit_dto = AttendanceService.calculate_regular_work_units(attendance)

        attendance.units = work_unit_dto.units
        attendance.is_half_day = work_unit_dto.is_half_day
        attendance.late_minutes = work_unit_dto.late_minutes
        attendance.early_leave_minutes = work_unit_dto.early_leave_minutes
        
        if attendance.attendance_type == AttendanceType.NORMAL:
            attendance.attendance_type = AttendanceType.ATTENDED

        db.session.commit()
        return jsonify({
            "success": True,
            "status": "success",
            "message": "Check-out hành chính thành công. Chúc bạn một buổi tối vui vẻ!",
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Check-out thành công",
                "allowOutsideClick": False  # Buộc nhân viên bấm OK để đóng hoặc reload lại trạng thái nút bấm trên UI
            },
            "data": {
                "employee_id": employee.id,
                "check_in": attendance.check_in.strftime("%H:%M:%S"),
                "check_out": attendance.check_out.strftime("%H:%M:%S"),
                "worked_hours": float(attendance.regular_hours),
                "late_minutes": attendance.late_minutes,
                "early_leave_minutes": attendance.early_leave_minutes,
                "work_units": float(attendance.units),
                "is_half_day": attendance.is_half_day
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "status": "error",
            "message": f"Có lỗi xảy ra trong quá trình xử lý dữ liệu: {str(e)}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống",
                "allowOutsideClick": True
            },
            "data": None
        }), 500

@attendance_bp.route('/overtime/checkout', methods=['POST'])
@auth_required 
@role_required(RoleName.EMPLOYEE)
def checkout_overtime():
    employee = g.employee
    current_time = get_current_time()
    today = current_time.date()
    
    # Truy vấn đơn OT đã được duyệt trong ngày của nhân viên
    ot_request = OvertimeRequest.query.filter_by(
        employee_id=employee.id,
        overtime_date=today,
        status="approved"  
    ).first()

    # --- KỊCH BẢN LỖI 1: KHÔNG CÓ ĐƠN ĐƯỢC DUYỆT (404) ---
    if not ot_request:
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Không tìm thấy đơn đăng ký tăng ca (OT) được phê duyệt cho ngày hôm nay.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Không tìm thấy đơn OT",
                "allowOutsideClick": True
            }
        }), 404
        
    # --- KỊCH BẢN LỖI 2: CHƯA CHECK-IN OT MÀ ĐÃ ĐÒI CHECK-OUT (400) ---
    if not ot_request.start_ot_time:
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Bạn chưa thực hiện Check-in ca tăng ca (OT). Không thể Check-out.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",
                "title": "Chưa Check-in OT",
                "allowOutsideClick": True
            }
        }), 400
        
    # --- KỊCH BẢN LỖI 3: ĐÃ CHECK-OUT TRƯỚC ĐÓ RỒI (400) ---
    if ot_request.end_ot_time:
        return jsonify({
            "success": False,
            "status": "error",
            "message": "Bạn đã ghi nhận Check-out ca tăng ca (OT) ngày hôm nay rồi.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "info",
                "title": "Đã ghi nhận trước đó",
                "allowOutsideClick": True
            }
        }), 400

    try:
        # Thực hiện cập nhật mốc thời gian kết thúc và tính toán số giờ
        ot_request.end_ot_time = current_time
        calculated_hours = attendance_calculation_service.calculate_overtime_hours_raw(
            overtime_check_in=ot_request.start_ot_time,
            overtime_check_out=ot_request.end_ot_time
        )
        ot_request.overtime_hours = calculated_hours.quantize(Decimal("0.01"))
        
        db.session.commit()
        
        # --- KỊCH BẢN 4: CHECK-OUT THÀNH CÔNG (200 OK) ---
        return jsonify({
            "success": True,
            "status": "success",
            "message": "Ghi nhận kết thúc ca tăng ca (OT) thành công.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Check-out OT thành công",
                "allowOutsideClick": False  # Ép nhân viên bấm OK để hệ thống reload lại bảng công mới
            },
            "data": {
                "overtime_date": ot_request.overtime_date.strftime("%Y-%m-%d"),
                "start_ot_time": ot_request.start_ot_time.strftime("%H:%M:%S"),
                "end_ot_time": ot_request.end_ot_time.strftime("%H:%M:%S"),
                "approved_hours_limit": float(ot_request.approved_hours or 0),
                "actual_overtime_hours": float(ot_request.overtime_hours)
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        # --- KỊCH BẢN LỖI 5: LỖI HỆ THỐNG / DB CRASH (500) ---
        return jsonify({
            "success": False,
            "status": "error",
            "message": f"Hệ thống xảy ra lỗi trong quá trình xử lý dữ liệu: {str(e)}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống",
                "allowOutsideClick": True
            }
        }), 500