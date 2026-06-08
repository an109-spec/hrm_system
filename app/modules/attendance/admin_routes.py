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