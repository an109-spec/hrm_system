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

@attendance_bp.route("/check-in", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE)
def check_in():
    employee = getattr(g, "employee", None)
    if not employee:
        raise ValueError("Không tìm thấy phiên làm việc của nhân viên.")
        
    data = request.get_json() or {}
    confirm_work_on_offday = data.get("confirm_work_on_offday", False)
    sim_time_str = data.get("sim_time")
    try:
        if sim_time_str:
            current_time = _normalize(sim_time_str)
            if not current_time:
                raise ValidationError("Chuỗi thời gian giả lập không đúng định dạng ISO.")
            set_simulated_time(current_time)
        else:
            current_time = get_current_time()

        # 2. KHỞI TẠO SERVICE VÀ XỬ LÝ LUỒNG CHẤM CÔNG VÀO CA
        workflow_service = Attendance_workflow_service(db.session)
        result_state = workflow_service.process_check_in_flow(
            employee_id=employee.id,
            current_time=current_time,
            confirm_work_on_offday=confirm_work_on_offday
        )
        
        return jsonify({
            "success": True,
            "data": {
                "state": result_state.state,
                "button_enabled": result_state.button_enabled,
                "button_text": result_state.button_text,
                "can_scan": result_state.can_scan,
                "message": result_state.message,
                "requires_confirmation": result_state.requires_confirmation,  # Kích hoạt Swal Confirm ở Front-end
                "locked_state": result_state.locked_state
            }
        }), 200

    except ValidationError as ve:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": str(ve)
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error_type": "GENERIC_ERROR",
            "message": f"Hệ thống gặp lỗi khi xử lý chấm công: {str(e)}"
        }), 400
    
@attendance_bp.route("/check-out", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE)
def check_out():
    employee = getattr(g, "employee", None)
    if not employee:
        raise ValueError("Không tìm thấy thông tin hồ sơ nhân viên trong phiên làm việc.")
        
    data = request.get_json() or {}
    early_checkout_confirmed = data.get("early_checkout_confirmed", False)
    sim_time_str = data.get("sim_time")
    
    try:
        # 1. ĐỒNG BỘ THỜI GIAN VỚI CƠ CHẾ GIẢ LẬP TOÀN CỤC
        if sim_time_str:
            current_time = _normalize(sim_time_str)
            if not current_time:
                raise ValidationError("Định dạng thời gian giả lập (sim_time) không hợp lệ. Vui lòng dùng ISO format.")
            # Ghi nhận ngay vào session để các hàm Service bên dưới gọi get_current_time() nhận được đúng trục thời gian test
            set_simulated_time(current_time)
        else:
            current_time = get_current_time()

        # 2. TRUY VẤN (Đảm bảo an toàn múi giờ khi lấy .date())
        today = current_time.date()
        attendance_record = Attendance.query.filter_by(
            employee_id=employee.id,
            date=today
        ).first()

        if not attendance_record:
            raise ValidationError("Hệ thống không tìm thấy bản ghi dữ liệu chấm công cho ngày hôm nay.")
            
        payload_service = {"early_checkout_confirmed": early_checkout_confirmed}
        
        # 3. GỌI XỬ LÝ NGHIỆP VỤ CA CHÍNH
        service_result = Attendance_workflow_service._handle_working(
            attendance=attendance_record,
            employee_id=employee.id,
            payload=payload_service,
            current_time=current_time
        )
        
        response_type = service_result.get("type", "success")
        
        # Trường hợp 1: Thao tác không hợp lệ (Sai trạng thái máy trạng thái)
        if response_type == "error":
            return jsonify({
                "success": False,
                "error_type": service_result.get("action", "invalid_state"),
                "message": service_result.get("message", "Thao tác check-out không hợp lệ.")
            }), 400

        # Trường hợp 2: Chặn giờ nghỉ trưa
        if response_type == "info" and service_result.get("action") == "lunch_break":
            return jsonify({
                "success": True,
                "swal_type": "info",
                "message": service_result.get("message"),
                "requires_confirmation": False
            }), 200

        # Trường hợp 3: Cảnh báo về sớm (Cần Pop-up Confirm phía Front-end)
        if response_type == "warning" and service_result.get("action") == "action_early_checkout_prompt":
            return jsonify({
                "success": True,
                "swal_type": "warning",
                "requires_confirmation": True,
                "message": service_result.get("message"),
                "early_minutes": service_result.get("flags", {}).get("early_minutes", 0)
            }), 200

        # Trường hợp 4: Thành công hoàn toàn (Về sớm đã duyệt, hoặc về đúng/muộn giờ)
        return jsonify({
            "success": True,
            "swal_type": "success",
            "requires_confirmation": False,
            "message": service_result.get("message"),
            "data": {
                "attendance_state": service_result.get("attendance_state"),
                "regular_hours": service_result.get("regular_hours"),
                "working_hours": service_result.get("working_hours"),
                "next_event": service_result.get("next_event"),
                "requires_overtime_decision": service_result.get("requires_overtime_decision", False)
            }
        }), 200

    except ValidationError as ve:
        db.session.rollback()
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Lỗi hệ thống trong quá trình check-out: {str(e)}"}), 500
    
@attendance_bp.route("/overtime/decision", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE)
def overtime_decision():
    employee = getattr(g, "employee", None)
    
    if not employee:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "unauthorized",
            "message": "Không tìm thấy thông tin hồ sơ nhân viên trong phiên làm việc.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi phiên làm việc",
                "allowOutsideClick": False
            },
            "data": None
        }), 401

    data = request.get_json() or {}
    decision = data.get("overtime_decision")
    sim_time_str = data.get("sim_time")
    
    try:
        # Sử dụng cơ chế sim_clock toàn cục để đồng bộ hóa thời gian
        if sim_time_str:
            current_time = _normalize(sim_time_str)
            if not current_time:
                raise ValidationError("Định dạng thời gian giả lập (sim_time) không chính xác.")
            # Ghi nhận thời gian giả lập mới vào session hệ thống
            set_simulated_time(current_time)
        else:
            current_time = get_current_time()

        # Truy vấn thực thể chấm công (đã an toàn về múi giờ)
        today = current_time.date()
        attendance_record = Attendance.query.filter_by(
            employee_id=employee.id,
            date=today
        ).first()

        if not attendance_record:
            raise ValidationError("Không tìm thấy dữ liệu chấm công hợp lệ để thực hiện quyết định tăng ca.")

        payload_service = {"overtime_decision": decision}
        
        service_result = Attendance_workflow_service._handle_after_checkout(
            attendance=attendance_record,
            employee_id=employee.id,
            payload=payload_service,
            current_time=current_time
        )

        response_type = service_result.get("type", "success")
        if response_type == "warning" and not decision:
            return jsonify({
                "success": True,
                "status": "warning",
                "message": service_result.get("message", "Bạn có muốn đăng ký tăng ca không?"),
                "requires_input": True,
                "attendance_state": service_result.get("attendance_state"),
                "swal_hint": {
                    "show_on_load": True,
                    "icon": "question",
                    "title": "Xác nhận tăng ca",
                    "allowOutsideClick": True
                }
            }), 200

        # Kịch bản TỪ CHỐI ("no") -> Đóng ngày công
        if response_type == "success" and service_result.get("overtime_status") == "NONE":
            return jsonify({
                "success": True,
                "status": "success",
                "message": service_result.get("message"),
                "swal_hint": {
                    "show_on_load": True,
                    "icon": "info",
                    "title": "Đã ghi nhận đóng ca",
                    "allowOutsideClick": False
                },
                "data": {
                    "attendance_state": service_result.get("attendance_state"),
                    "overtime_status": "NONE",
                    "attendance": service_result.get("attendance")
                }
            }), 200

        # Kịch bản ĐỒNG Ý ("yes") -> Chờ duyệt đơn OT
        if response_type == "success" and service_result.get("overtime_status") in ["pending", "PENDING"]:
            return jsonify({
                "success": True,
                "status": "success",
                "message": service_result.get("message"),
                "swal_hint": {
                    "show_on_load": True,
                    "icon": "success",
                    "title": "Đăng ký OT thành công",
                    "allowOutsideClick": False
                },
                "data": {
                    "attendance_state": service_result.get("attendance_state"),
                    "overtime_status": "PENDING",
                    "attendance": service_result.get("attendance")
                }
            }), 200

        # Kịch bản dự phòng khác
        return jsonify({
            "success": True,
            "status": response_type,
            "message": service_result.get("message"),
            "swal_hint": {
                "show_on_load": True,
                "icon": response_type if response_type in ["success", "warning", "error", "info"] else "info",
                "title": "Thông báo hệ thống",
                "allowOutsideClick": True
            },
            "data": {
                "attendance_state": service_result.get("attendance_state"),
                "overtime_status": service_result.get("overtime_status"),
                "attendance": service_result.get("attendance")
            }
        }), 200

    except ValidationError as ve:
        db.session.rollback()
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "validation_error",
            "message": str(ve),
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",
                "title": "Dữ liệu không hợp lệ",
                "allowOutsideClick": True
            },
            "data": None
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "system_error",
            "message": f"Lỗi xử lý quyết định tăng ca: {str(e)}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống",
                "allowOutsideClick": True
            },
            "data": None
        }), 500
@attendance_bp.route("/overtime/check-in", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE)
def overtime_check_in():
    employee = getattr(g, "employee", None)
    
    if not employee:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "unauthorized",
            "message": "Không tìm thấy thông tin nhân viên trong phiên làm việc hiện tại.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi phiên làm việc",
                "allowOutsideClick": False
            },
            "data": None
        }), 401

    data = request.get_json() or {}
    sim_time_str = data.get("sim_time")

    try:
        if sim_time_str:
            current_time = _normalize(sim_time_str)
            if not current_time:
                raise ValidationError("Định dạng chuỗi thời gian giả lập không hợp lệ.")
            # Đồng bộ cấu hình thời gian test vào session
            set_simulated_time(current_time)

        # Gọi nghiệp vụ xử lý, lúc này tầng Service gọi `get_current_time()` sẽ lấy đúng thời gian đã set
        service_result = AttendanceService.check_in_overtime(employee_id=employee.id)
        attendance_state = service_result.get("attendance_state")
        
        return jsonify({
            "success": True,
            "status": "success",
            "message": service_result.get("message"),
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Vào ca OT thành công",
                "allowOutsideClick": False
            },
            "data": {
                "attendance_state": attendance_state,
                "overtime_status": service_result.get("overtime_status"),
                "is_waiting_room": (attendance_state == "PRE_OT_REST"),
                "attendance": service_result.get("attendance")
            }
        }), 200

    except ValidationError as ve:
        db.session.rollback()
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "validation_error",
            "message": str(ve),
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",
                "title": "Không thể vào ca",
                "allowOutsideClick": True
            },
            "data": None
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "system_error",
            "message": f"Lỗi hệ thống khi thiết lập vào ca tăng ca: {str(e)}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống",
                "allowOutsideClick": True
            },
            "data": None
        }), 500
    
@attendance_bp.route("/overtime/check-out", methods=["POST"])
@auth_required
@role_required(RoleName.EMPLOYEE)
def overtime_check_out():
    """
    [API Endpoint] Tiếp nhận yêu cầu kết thúc ca làm việc tăng ca (OT Check-out).
    Thực hiện tính toán công, áp hệ số nhân và đóng vĩnh viễn bảng công trong ngày.
    """
    employee = getattr(g, "employee", None)
    
    # --- KỊCH BẢN 1: KHÔNG TÌM THẤY THÔNG TIN NHÂN VIÊN TRONG PHIÊN (401) ---
    # Thay vì raise lỗi thô, trả về Jsonify kèm Swal để Front-end hiển thị thông báo logout/xác thực lại
    if not employee:
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "unauthorized",
            "message": "Không tìm thấy thông tin nhân viên trong phiên làm việc.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi phiên làm việc",
                "allowOutsideClick": False
            },
            "data": None
        }), 401

    # 1. Thu thập dữ liệu từ Request Body
    data = request.get_json() or {}
    
    # Lấy chuỗi thời gian giả lập (sim_time) truyền từ giao diện test của đồ án tốt nghiệp
    sim_time_str = data.get("sim_time")

    try:
        # 2. Chuyển tiếp dữ liệu xuống hàm nghiệp vụ cốt lõi đã có của bạn
        service_result = AttendanceService.check_out_overtime(
            employee_id=employee.id,
            sim_time_str=sim_time_str
        )

        # --- KỊCH BẢN THÀNH CÔNG (200 OK) ---
        # 3. Chuẩn hóa cấu trúc Payload trả về cho Front-end và SweetAlert2
        return jsonify({
            "success": True,
            "status": "success",
            "message": service_result.get("message"),
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Chốt ca OT thành công",
                "allowOutsideClick": False  # Ép người dùng bấm OK để FE kích hoạt reload bảng công/giao diện hiện tại
            },
            "data": {
                "attendance_state": service_result.get("attendance_state"),
                "overtime_status": service_result.get("overtime_status"),
                "hours_summary": {
                    "regular_hours": service_result.get("regular_hours"),
                    "overtime_hours": service_result.get("overtime_hours"),
                    "total_working_hours": service_result.get("working_hours")
                },
                "timeline": {
                    "check_in_ot": service_result.get("overtime_check_in"),
                    "check_out_ot": service_result.get("overtime_check_out")
                },
                "attendance_payload": service_result.get("attendance")
            }
        }), 200

    except ValidationError as ve:
        # --- KỊCH BẢN 2: VI PHẠM RÀNG BUỘC LOGIC NGHIỆP VỤ (400) ---
        # Ví dụ: Chưa Check-in OT mà đã Check-out, hoặc thời gian giả lập đi lùi...
        db.session.rollback()
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "validation_error",
            "message": str(ve),
            "swal_hint": {
                "show_on_load": True,
                "icon": "warning",
                "title": "Không thể chốt ca",
                "allowOutsideClick": True
            },
            "data": None
        }), 400
        
    except Exception as e:
        # --- KỊCH BẢN 3: LỖI HỆ THỐNG / DATABASE (500) ---
        db.session.rollback()
        return jsonify({
            "success": False,
            "status": "error",
            "error_type": "system_error",
            "message": f"Lỗi hệ thống trong quá trình chốt ca tăng ca: {str(e)}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống",
                "allowOutsideClick": True
            },
            "data": None
        }), 500