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