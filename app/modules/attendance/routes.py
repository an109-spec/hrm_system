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

@attendance_bp.route('/<int:attendance_id>', methods=['PUT'])
@auth_required
@role_required(RoleName.HR) 
def admin_update_attendance(attendance_id):
    attendance = Attendance.query.get_or_404(attendance_id)
    data = request.get_json() or {}

    try:
        # 1. Cập nhật trạng thái và thời gian hành chính ngày thường bằng hàm _normalize chuẩn
        if 'attendance_type' in data:
            attendance.attendance_type = data['attendance_type']
        if 'check_in' in data:
            attendance.check_in = _normalize(data['check_in'])
        if 'check_out' in data:
            attendance.check_out = _normalize(data['check_out'])

        # 2. Đồng bộ các thông số thô trước khi chạy hàm tính công hành chính
        if attendance.check_in and attendance.check_out:
            total_seconds = (attendance.check_out - attendance.check_in).total_seconds()
            raw_hours = max(0.0, total_seconds / 3600)
            if raw_hours > 5:
                raw_hours -= 1.0
            attendance.regular_hours = round(raw_hours, 2)

            expected_start = datetime.combine(attendance.check_in.date(), WorkConfig.WORKDAY_START).replace(tzinfo=VN_TIMEZONE)
            attendance.late_minutes = int((attendance.check_in - expected_start).total_seconds() // 60) if attendance.check_in > expected_start else 0

            expected_end = datetime.combine(attendance.check_out.date(), WorkConfig.WORKDAY_END).replace(tzinfo=VN_TIMEZONE)
            attendance.early_leave_minutes = int((expected_end - attendance.check_out).total_seconds() // 60) if attendance.check_out < expected_end else 0
        else:
            attendance.regular_hours = 0
            attendance.late_minutes = 0
            attendance.early_leave_minutes = 0

        # 3. Thực thi Recalculate công ngày thường
        regular_dto = attendance_calculation_service.calculate_regular_work_units(attendance)
        attendance.units = regular_dto.units
        attendance.is_half_day = regular_dto.is_half_day

        # 4. KIỂM TRA BẢO VỆ LUỒNG OT (TÔN TRỌNG QUYỀN DUYỆT CỦA MANAGER)
        ot_request = OvertimeRequest.query.filter_by(
            employee_id=attendance.employee_id,
            overtime_date=attendance.date
        ).first()

        ot_message = "Không có đơn đăng ký OT cho ngày này."
        actual_ot_hours = Decimal("0.00")

        if ot_request:
            if ot_request.status == "approved":
                if 'overtime_check_in' in data:
                    ot_request.start_ot_time = _normalize(data['overtime_check_in'])
                if 'overtime_check_out' in data:
                    ot_request.end_ot_time = _normalize(data['overtime_check_out'])

                # Chỉ tính toán lại giờ OT khi có đủ cả hai mốc thời gian sau khi gọt rửa qua _normalize
                if ot_request.start_ot_time and ot_request.end_ot_time:
                    raw_ot_hours = attendance_calculation_service.calculate_overtime_hours_raw(
                        overtime_check_in=ot_request.start_ot_time,
                        overtime_check_out=ot_request.end_ot_time
                    )
                    actual_ot_hours = Decimal(str(raw_ot_hours)).quantize(Decimal("0.01"))
                    ot_request.overtime_hours = actual_ot_hours
                    ot_message = "Tính toán lại giờ OT thành công dựa trên đơn đã phê duyệt của Quản lý."
                else:
                    ot_request.overtime_hours = Decimal("0.00")
                    ot_message = "Đơn OT được duyệt nhưng thiếu mốc thời gian check-in/out của ca OT. Ép giờ OT về 0."
            else:
                ot_request.overtime_hours = Decimal("0.00")
                ot_message = f"Phát hiện đơn OT nhưng ở trạng thái '{ot_request.status}' (Chưa được duyệt). Ép giờ OT về 0."
        
        attendance.overtime_hours = actual_ot_hours

        # 5. Lưu xuống Database
        db.session.commit()

        # --- KỊCH BẢN THÀNH CÔNG (200 OK) ---
        return jsonify({
            "success": True,
            "status": "success",
            "message": f"Đã cập nhật dữ liệu ngày công thành công. Lịch sử OT: {ot_message}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Cập nhật hoàn tất",
                "allowOutsideClick": False  # Buộc HR bấm OK để đóng/reload lại bảng dữ liệu
            },
            "data": {
                "attendance_id": attendance.id,
                "check_in": attendance.check_in.isoformat() if attendance.check_in else None,
                "check_out": attendance.check_out.isoformat() if attendance.check_out else None,
                "regular_hours": float(attendance.regular_hours),
                "units": float(attendance.units),
                "is_half_day": attendance.is_half_day,
                "overtime_hours": float(attendance.overtime_hours),
                "overtime_request_status": ot_request.status if ot_request else None
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        # --- KỊCH BẢN LỖI HỆ THỐNG / DATABASE CRASH (500) ---
        return jsonify({
            "success": False,
            "status": "error",
            "message": f"Không thể lưu các thay đổi do lỗi hệ thống: {str(e)}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Thất bại",
                "allowOutsideClick": True
            },
            "data": None
        }), 500

@attendance_bp.route('/calculate', methods=['POST'])
@auth_required
@role_required(RoleName.HR) 
def calculate_monthly_attendance_to_salary():
    try:
        data = request.get_json() or {}
        
        year = data.get('year')
        month = data.get('month')
        employee_id = data.get('employee_id')

        # --- TRƯỜNG HỢP LỖI 1: THIẾU THAM SỐ ĐẦU VÀO (400) ---
        if not year or not month:
            return jsonify({
                "success": False,
                "status": "error", # Giữ nguyên để khớp logic cũ nếu có
                "message": "Thiếu tham số 'year' hoặc 'month' để xác định kỳ chốt công.",
                "swal_hint": {
                    "show_on_load": True,
                    "icon": "warning",
                    "title": "Thiếu thông tin",
                    "allowOutsideClick": True
                }
            }), 400

        # 1. Xác định danh sách nhân viên cần quét công
        if employee_id:
            employees = Employee.query.filter_by(id=employee_id).all()
            # --- TRƯỜNG HỢP LỖI 2: KHÔNG TÌM THẤY NHÂN VIÊN CHỈ ĐỊNH (404) ---
            if not employees:
                return jsonify({
                    "success": False,
                    "status": "error",
                    "message": f"Không tìm thấy nhân viên có mã ID {employee_id} trong hệ thống.",
                    "swal_hint": {
                        "show_on_load": True,
                        "icon": "error",
                        "title": "Không tìm thấy nhân sự",
                        "allowOutsideClick": True
                    }
                }), 404
        else:
            # Quét tất cả nhân viên đang hoạt động trong hệ thống
            employees = Employee.query.filter_by(status="active").all()

        start_date = date(int(year), int(month), 1)
        _, last_day = calendar.monthrange(int(year), int(month))
        end_date = date(int(year), int(month), last_day)

        processed_count = 0

        # 2. Vòng lặp tính toán ngày công cho từng nhân sự (Giữ nguyên 100% logic của bạn)
        for emp in employees:
            contract = Contract.query.filter_by(employee_id=emp.id, is_active=True).first()
            if not contract:
                continue 

            attendances = Attendance.query.filter(
                Attendance.employee_id == emp.id,
                Attendance.date >= start_date,
                Attendance.date <= end_date
            ).all()

            accumulated_work_days = Decimal("0.00")

            for att in attendances:
                day_rate = attendance_calculation_service._get_day_rate(att.attendance_type)
                multiplier = attendance_calculation_service._day_multiplier(att.is_holiday, att.is_weekend)
                
                base_day_weight = Decimal("0.50") if att.is_half_day else Decimal("1.00")
                actual_day_credit = base_day_weight * day_rate * multiplier
                accumulated_work_days += actual_day_credit

            # 3. Tìm hoặc khởi tạo bản ghi dữ liệu trong bảng lương (Salary)
            salary_record = Salary.query.filter_by(
                employee_id=emp.id,
                month=int(month),
                year=int(year)
            ).first()

            if not salary_record:
                salary_record = Salary(
                    employee_id=emp.id,
                    month=int(month),
                    year=int(year),
                    basic_salary=contract.base_salary,
                    standard_work_days=22, 
                    total_allowance=Decimal("0.00"), 
                    bonus=Decimal("0.00"),
                    penalty=Decimal("0.00"),
                    status=SalaryStatus.PENDING 
                )
                db.session.add(salary_record)
            else:
                salary_record.basic_salary = contract.base_salary
            salary_record.total_work_days = accumulated_work_days
            salary_record.calculate_net_salary()
            processed_count += 1
            
        db.session.commit()

        # --- TRƯỜNG HỢP 3: TỔNG HỢP THÀNH CÔNG (200) ---
        return jsonify({
            "success": True,
            "status": "success",
            "message": f"Hệ thống đã tổng hợp thành công dữ liệu chấm công và cập nhật số ngày công cho {processed_count} nhân sự.",
            "swal_hint": {
                "show_on_load": True,
                "icon": "success",
                "title": "Chốt công hoàn tất",
                "allowOutsideClick": False # Buộc HR bấm OK để load lại bảng lương mới
            },
            "details": {
                "year": year,
                "month": month,
                "status_set": SalaryStatus.PENDING
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "status": "error",
            "message": f"Đã xảy ra lỗi hệ thống nghiêm trọng trong quá trình xử lý tổng hợp công: {str(e)}",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi xử lý bảng công",
                "allowOutsideClick": True
            }
        }), 500
    
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

@attendance_bp.route('/today', methods=['GET'])
@auth_required
def get_today_attendance():
    try:
        # Lấy employee_id trực tiếp từ context g (đã qua lớp bảo mật @auth_required)
        employee_id = g.employee.id
        
        # Gọi service xử lý nghiệp vụ (Xử lý khớp ca đêm xuyên ngày trước 5h sáng)
        record = AttendanceCommandService.get_today(employee_id=employee_id)
        
        # --- TRƯỜNG HỢP 1: CHƯA GHI NHẬN CHẤM CÔNG ---
        if not record:
            return jsonify({
                "success": True,
                "message": "Hôm nay bạn chưa ghi nhận vào ca. Hãy thực hiện Check-in!",
                "swal_hint": {
                    "show_on_load": True,
                    "icon": "info",
                    "title": "Chưa chấm công",
                    "toast": True,
                    "position": "top-end",
                    "timer": 3000,
                    "allowOutsideClick": True
                },
                "data": {
                    "shift_status": AttendanceShiftStatus.NOT_STARTED,
                    "shift_status_label": AttendanceShiftStatus.label(AttendanceShiftStatus.NOT_STARTED),
                    "attendance_info": None
                }
            }), 200
        shift_status = record.normalized_shift_status
        message = "Lấy trạng thái chấm công thành công"
        
        # Thiết lập cấu hình Swal mặc định cho trạng thái thông thường
        swal_hint = {
            "show_on_load": False,
            "icon": "success",
            "title": "Thành công",
            "toast": False,
            "allowOutsideClick": True
        }
        
        # Phân loại trạng thái đặc thù để ép Frontend hiển thị cảnh báo tương ứng
        if shift_status == AttendanceShiftStatus.REGULAR_CHECKOUT_REQUIRED:
            message = "Bạn đã hết giờ làm việc chính thức nhưng quên chưa bấm Check-out! Vui lòng hoàn tất ca này trước."
            swal_hint.update({
                "show_on_load": True,
                "icon": "warning",
                "title": "Cần Checkout Ca Chính",
                "allowOutsideClick": False  # Ép nhân viên phải tương tác, không cho bấm ra ngoài tắt bừa
            })
            
        elif shift_status == AttendanceShiftStatus.OT_CHECKIN_REQUIRED:
            message = "Bạn đã được duyệt tăng ca hoặc đã hết giờ hành chính. Hãy thực hiện 'Check-in OT' để bắt đầu tính giờ làm thêm!"
            swal_hint.update({
                "show_on_load": True,
                "icon": "info",
                "title": "Sẵn Sàng Tăng Ca",
                "allowOutsideClick": True
            })
            
        elif shift_status == AttendanceShiftStatus.WORKING_REGULAR:
            message = "Hệ thống ghi nhận bạn đang trong ca làm việc chính thức. Chúc bạn một ngày làm việc hiệu quả!"
            swal_hint.update({
                "show_on_load": True,
                "icon": "success",
                "title": "Đang Trong Ca",
                "toast": True,          # Hiển thị dạng báo góc (Toast) cho tinh tế, không làm gián đoạn trải nghiệm
                "position": "top-end",
                "timer": 2500
            })

        return jsonify({
            "success": True,
            "message": message,
            "swal_hint": swal_hint,
            "data": {
                "shift_status": shift_status,
                "shift_status_label": record.shift_status_label,
                "attendance_info": record.to_dict()
            }
        }), 200

    except ValidationError as e:
        return jsonify({
            "success": False,
            "message": str(e),
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi dữ liệu nghiệp vụ",
                "allowOutsideClick": True
            }
        }), 400
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Đã xảy ra lỗi hệ thống khi lấy thông tin chấm công. Vui lòng liên hệ Admin!",
            "swal_hint": {
                "show_on_load": True,
                "icon": "error",
                "title": "Lỗi hệ thống (500)",
                "allowOutsideClick": True
            }
        }), 500

@attendance_bp.route('/history', methods=['GET'])
@auth_required 
@role_required(RoleName.EMPLOYEE)
def get_attendance_history():
    try:
        # 1. Lấy thông tin nhân viên từ Context của decorator @auth_required
        employee_id = g.employee.id

        # 2. Đọc và bóc tách các tham số lọc từ client gửi lên
        limit = request.args.get('limit', default=31, type=int)
        month = request.args.get('month', default=None, type=int)
        year = request.args.get('year', default=None, type=int)
        sim_time_str = request.args.get('sim_time', default=None, type=str)

        # 3. Đồng bộ hóa trục thời gian (Hỗ trợ hệ thống sim_clock để kiểm thử)
        now_dt = None
        if sim_time_str:
            now_dt = _normalize(sim_time_str)
            if not now_dt:
                raise ValidationError("Định dạng chuỗi thời gian giả lập không hợp lệ.")
            set_simulated_time(now_dt)
        else:
            now_dt = get_current_time()

        # Tự động bù tháng/năm hiện hành nếu client gửi thiếu
        if (month and not year) or (year and not month):
            month = month or now_dt.month
            year = year or now_dt.year

        # 4. Truy vấn dữ liệu từ Service tầng dưới
        history_records = AttendanceCommandService.get_history(
            employee_id=employee_id,
            limit=limit,
            month=month,
            year=year,
            now_dt=now_dt
        )

        # 5. Khởi tạo cấu trúc dữ liệu mảng payload
        serialized_data = [
            AttendanceService.build_attendance_payload(record) 
            for record in history_records
        ]

        # 6. Đóng gói payload THÀNH CÔNG: Trả nguyên cấu hình Swal tự động tắt sau 1.5s
        return jsonify({
            "status": "success",
            "swal": {
                "icon": "success",
                "title": "Tải dữ liệu thành công!",
                "text": f"Đã kết xuất thành công {len(serialized_data)} ngày công của tháng {month}/{year}.",
                "timer": 1500,
                "showConfirmButton": False
            },
            "data": serialized_data,
            "summary": {
                "requested_month": month,
                "requested_year": year,
                "system_time": now_dt.isoformat()
            }
        }), 200

    except ValidationError as e:
        return jsonify({
            "status": "error",
            "swal": {
                "icon": "warning",
                "title": "Dữ liệu không hợp lệ",
                "text": str(e),
                "confirmButtonColor": "#f39c12"
            },
            "data": None
        }), 400

    except (UnauthorizedError, ForbiddenError) as e:
        # Đóng gói payload LỖI QUYỀN TRUY CẬP: Hiện cảnh báo nghiêm trọng màu đỏ (Error)
        return jsonify({
            "status": "error",
            "swal": {
                "icon": "error",
                "title": "Từ chối truy cập",
                "text": str(e),
                "confirmButtonColor": "#d33"
            },
            "data": None
        }), 403

    except Exception as e:
        # Đóng gói payload LỖI HỆ THỐNG KHÔNG XÁC ĐỊNH
        return jsonify({
            "status": "error",
            "swal": {
                "icon": "error",
                "title": "Lỗi hệ thống",
                "text": "Đã xảy ra sự cố đột xuất trong quá trình tính toán bảng công.",
                "footer": f"Chi tiết kỹ thuật: {str(e)}",
                "confirmButtonColor": "#d33"
            },
            "data": None
        }), 500
    
@attendance_bp.route('/<int:employee_id>', methods=['DELETE'])
@auth_required
@self_or_hr_required('employee_id')  # Chấp nhận chính nhân viên sở hữu id này tự xóa để test
def delete_attendance_record(employee_id):
    try:
        date_str = request.args.get('date')
        if not date_str:
            raise ValidationError("Vui lòng cung cấp ngày cần xóa công (tham số ?date=).")
        last_active_date = AttendanceCommandService.delete_attendance(
            employee_id=employee_id,
            date_str=date_str
        )
        last_active_date_str = last_active_date.strftime('%Y-%m-%d') if last_active_date else None
        return jsonify({
            "status": "success",
            "swal": {
                "icon": "success",
                "title": "Xóa bản ghi thành công",
                "text": f"Đã xóa dữ liệu ngày {date_str} để phục vụ kiểm thử hệ thống.",
                "timer": 1500,
                "showConfirmButton": False
            },
            "data": {
                "last_active_date": last_active_date_str
            }
        }), 200

    except ValidationError as e:
        # Trả về lỗi nghiệp vụ (ví dụ sai định dạng ngày, không tìm thấy bản ghi)
        return jsonify({
            "status": "error",
            "swal": {
                "icon": "warning",
                "title": "Thao tác thất bại",
                "text": str(e),
                "confirmButtonColor": "#f39c12"
            },
            "data": None
        }), 400

    except Exception as e:
        # Trả về lỗi hệ thống đột xuất
        return jsonify({
            "status": "error",
            "swal": {
                "icon": "error",
                "title": "Lỗi kiểm thử",
                "text": "Không thể hoàn tác dữ liệu chấm công do xung đột hệ thống.",
                "footer": f"Chi tiết: {str(e)}",
                "confirmButtonColor": "#d33"
            },
            "data": None
        }), 500
    
@attendance_bp.route('/<int:notification_id>/cascade', methods=['DELETE'])
@auth_required  # Bắt buộc đăng nhập để lấy thông tin g.user từ token
def delete_notification_cascade_route(notification_id):
    try:
        # 1. Lấy user_id trực tiếp từ token của người dùng đang thao tác
        user_id = g.user.id

        # 2. Gọi hàm Service để thực hiện xóa mềm thông báo và cascade hủy đơn OT, reset công
        result = AttendanceCommandService.delete_notification_cascade(
            notification_id=notification_id,
            user_id=user_id
        )

        # 3. Trả về payload THÀNH CÔNG bọc cấu hình Swal màu xanh
        return jsonify({
            "status": "success",
            "swal": {
                "icon": "success",
                "title": "Hủy tăng ca thành công!",
                "text": "Đã xóa thông báo, hủy đơn tăng ca và khôi phục giờ hành chính.",
                "timer": 2000,
                "showConfirmButton": False
            },
            "data": result  # Chứa thông tin { "deleted": True, "notification_id": ..., "cascaded": [...] }
        }), 200

    except ValidationError as e:
        # Trả về lỗi 400 Bad Request khi không tìm thấy thông báo hoặc thông báo không thuộc về user
        return jsonify({
            "status": "error",
            "swal": {
                "icon": "warning",
                "title": "Thao tác không hợp lệ",
                "text": str(e),
                "confirmButtonColor": "#f39c12"
            },
            "data": None
        }), 400

    except Exception as e:
        # Trả về lỗi 500 nếu có sự cố bất ngờ khi tương tác với Database
        return jsonify({
            "status": "error",
            "swal": {
                "icon": "error",
                "title": "Lỗi hệ thống",
                "text": "Gặp sự cố trong quá trình hoàn tác dây chuyền dữ liệu.",
                "footer": f"Chi tiết kỹ thuật: {str(e)}",
                "confirmButtonColor": "#d33"
            },
            "data": None
        }), 500

@attendance_bp.route('/overtime/reset/<int:request_id>', methods=['POST'])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def reset_overtime_flow_route(request_id):
    overtime_request = OvertimeRequest.query.filter_by(id=request_id, is_deleted=False).first()
    
    if not overtime_request:
        return jsonify({
            "status": "error",
            "title": "Không tìm thấy!",
            "message": f"Yêu cầu tăng ca ID {request_id} không tồn tại hoặc đã bị xóa."
        }), 404

    try:
        actor_user_id = g.user.id
        data = request.get_json() or {}
        anchor_notification_id = data.get('notification_id')
        result = OvertimeService.cancel_and_reset_overtime_flow(
            overtime_request=overtime_request,
            actor_user_id=actor_user_id,
            source="admin_manual_reset",
            anchor_notification_id=anchor_notification_id
        )
        return jsonify({
            "status": "success",
            "title": "Thành công!",
            "message": f"Đã reset hoàn toàn dữ liệu OT ngày {result['overtime_date']}.",
            "details": {
                "requests_cancelled": result['deleted_requests'],
                "notifications_cleaned": result['deleted_notifications']
            }
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "title": "Lỗi hệ thống",
            "message": str(e)
        }), 500
    
@attendance_bp.route("/overtime/pending", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def get_pending_overtime():
    """
    API lấy danh sách các đơn tăng ca chờ duyệt của cấp dưới.
    """
    try:
        manager_id = g.employee.id
        data = OvertimeService.get_overtime_requests(manager_id)
        return jsonify({
            "status": "success",
            "data": data
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "icon": "error",
            "title": "Thất bại",
            "text": f"Có lỗi xảy ra khi tải dữ liệu: {str(e)}"
        }), 400