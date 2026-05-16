from __future__ import annotations

from sqlalchemy import extract
from datetime import date, datetime, time
from decimal import Decimal
import os
import uuid
from flask import current_app
from flask import Response, flash, jsonify, redirect, render_template, request, session, url_for

from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload
from app.extensions.db import db
from app.models import (
    Attendance,
    Complaint,
    Contract,
    Employee,
    EmployeeLeaveUsage,
    HistoryLog,
    LeaveRequest,
    LeaveType,
    Notification,
    OvertimeRequest,
    Salary,
    User,
    Holiday,
    ResignationRequest,
    
)
from app.modules.leave.service import LeaveService
from app.modules.leave.dto import LeaveRequestDTO
from app.common.exceptions import ValidationError
from app.common.constants import (
    RoleName,
    WorkingStatus,
    EmploymentType,
    LeaveStatus,
    AttendanceStatus,
    SalaryStatus,
    AttendanceConstants,
    WorkConfig,
    OvertimeConfig,
    _build_lunar_public_holidays_for_year,
    _resolve_lunar_date_class,
    LEAVE_TYPE_CONFIGS,
    VN_FIXED_PUBLIC_HOLIDAYS,
    VN_LUNAR_PUBLIC_HOLIDAYS,
)
from app.modules.attendance.service import AttendanceService

from app.utils.time import get_current_time, is_simulation_mode, VN_TIMEZONE, set_simulated_time
from app.utils.ui_helpers import get_status_badge, format_minutes_to_string, labelize_enum
from app.common.security import auth_required, role_required
from flask import g

from .overtime_service import EmployeeOvertimeService
from .notification_service import EmployeeNotificationService
from .complaint_service import EmployeeComplaintService
from .dependent_service import EmployeeDependentService
from .payroll_service import EmployeePayrollService
from . import employee_bp
from app.modules.resignation_service import ResignationService
from app.modules.overtime_reset_service import reset_overtime_request_flow
from app import ensure_leave_types
from .constants import (
ALLOWED_FUNERAL_RELATIONS,
ENUM_LABELS,
PERSONAL_SUBTYPES
)

def _build_shift_and_actions(attendance: "Attendance | None") -> dict:
    now = get_current_time() # Khớp với simulation trong time.py
    current_time = now.time()
    today_date = now.date()

    # 1. Xác định trạng thái ca làm việc (Shift State)
    if current_time < WorkConfig.WORKDAY_START:
        shift_state = "BEFORE_SHIFT"
    elif WorkConfig.LUNCH_START <= current_time < WorkConfig.LUNCH_END:
        shift_state = "LUNCH_BREAK"
    elif WorkConfig.WORKDAY_START <= current_time < WorkConfig.WORKDAY_END:
        shift_state = "WORKING"
    elif WorkConfig.WORKDAY_END <= current_time < WorkConfig.OT_START:
        shift_state = "REST_BEFORE_OT"
    elif WorkConfig.OT_START <= current_time <= WorkConfig.OT_END:
        shift_state = "OT_WINDOW"
    else:
        shift_state = "OFF"

    # 2. Xử lý ngày lễ (Dùng Cache tối ưu hiệu năng)
    lunar_holidays = OvertimeConfig.get_lunar_holidays(today_date.year)
    date_str = today_date.strftime("%m-%d")
    
    holiday_name = VN_FIXED_PUBLIC_HOLIDAYS.get(date_str) or lunar_holidays.get(date_str)
    is_holiday = holiday_name is not None
    is_weekend = now.weekday() >= 5

    # 3. Xác định trạng thái điểm danh (Attendance State)
    if not attendance:
        if is_holiday:
            attendance_state = "holiday_off"
        elif is_weekend:
            attendance_state = "weekend_off"
        else:
            attendance_state = "not_started"
    else:
        # Sử dụng hàm normalize đã hợp nhất trong constants.py
        attendance_state = AttendanceConstants.normalize(attendance.shift_status)

    # 4. Kiểm tra đơn OT đã duyệt
    approved_ot_request = None
    if attendance:
        approved_ot_request = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == attendance.employee_id,
            OvertimeRequest.overtime_date == today_date,
            OvertimeRequest.is_deleted.is_(False),
            OvertimeRequest.status == "approved" 
        ).first()

    # 5. Thiết lập Action Flags (Logic điều khiển nút bấm)
    has_checkin = bool(attendance and attendance.check_in)
    has_checkout = bool(attendance and attendance.check_out)
    has_ot_in = bool(attendance and attendance.overtime_check_in)
    has_ot_out = bool(attendance and attendance.overtime_check_out)
    
    # Cho phép Check-out ngay cả trong giờ nghỉ trưa để tránh nhân viên bị kẹt
    # Nhưng chặn Check-in trong giờ nghỉ trưa để đảm bảo đúng quy định
    in_lunch = WorkConfig.LUNCH_START <= current_time < WorkConfig.LUNCH_END

    return {
        "attendance_state": attendance_state,
        "shift_state": shift_state,
        "action_flags": {
            "can_check_in": (
                WorkConfig.CHECKIN_START <= current_time < WorkConfig.WORKDAY_END
                and not in_lunch
                and not has_checkin
                and attendance_state == "not_started"
            ),
            "can_check_out": (
                has_checkin 
                and not has_checkout 
                # Bỏ điều kiện 'not in_lunch' để nhân viên thoải mái về sớm/về trưa
            ),
            "can_start_ot": (
                shift_state == "OT_WINDOW"
                and has_checkout # Bắt buộc phải xong hành chính mới được OT
                and bool(approved_ot_request)
                and not has_ot_in
            ),
            "can_end_ot": (
                has_ot_in 
                and not has_ot_out
            ),
        },
        "today_holiday": holiday_name,
        "is_weekend": is_weekend,
        "has_approved_ot": bool(approved_ot_request),
        "current_sim_time": now.strftime("%H:%M:%S") 
    }

def is_public_holiday(target_date: date) -> bool:
    date_str = target_date.strftime("%m-%d")
    if date_str in VN_FIXED_PUBLIC_HOLIDAYS:
        return True
    lunar_holidays = OvertimeConfig.get_lunar_holidays(target_date.year)
    if date_str in lunar_holidays:
        return True
    return False

def _get_holiday_lookup() -> dict[str, str]:
    now = get_current_time()
    current_year = now.year
    lookup = {}
    db_holidays = Holiday.query.filter(
        db.or_(
            Holiday.is_recurring.is_(True),
            db.extract('year', Holiday.date) == current_year
        )
    ).all()
    for holiday in db_holidays:
        key = holiday.date.strftime("%m-%d")
        lookup[key] = holiday.name
    for holiday_key, holiday_name in VN_FIXED_PUBLIC_HOLIDAYS.items():
        lookup.setdefault(holiday_key, holiday_name)
    lunar_holidays = _build_lunar_public_holidays_for_year(current_year)
    for holiday_key, holiday_name in lunar_holidays.items():
        lookup.setdefault(holiday_key, holiday_name)
    return lookup

def _compute_working_hours(check_in: time, check_out: time) -> Decimal:
    if not check_in or not check_out:
        return Decimal("0.00")
    today = get_current_time().date() 
    start = datetime.combine(today, check_in)
    end = datetime.combine(today, check_out)
    if end <= start:
        return Decimal("0.00")
    total_seconds = Decimal(str((end - start).total_seconds()))
    lunch_start = datetime.combine(today, WorkConfig.LUNCH_START)
    lunch_end = datetime.combine(today, WorkConfig.LUNCH_END)
    overlap_start = max(start, lunch_start)
    overlap_end = min(end, lunch_end)
    if overlap_start < overlap_end:
        overlap_seconds = Decimal(str((overlap_end - overlap_start).total_seconds()))
        total_seconds -= overlap_seconds
    total_hours = (total_seconds / Decimal("3600")).quantize(Decimal("0.01"))
    return max(total_hours, Decimal("0.00"))

def _attendance_metrics(
    record: Attendance | None,
    is_holiday: bool = False,
    is_weekend: bool = False,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    
    if not record or not record.check_in:
        return (Decimal("0.00"),) * 5
    day_type = "normal"
    if is_holiday:
        day_type = "holiday"
    elif is_weekend:
        day_type = "weekend"

    # 2. Tính toán số giờ thô (raw hours)
    raw_total = _compute_working_hours(record.check_in, record.check_out)
    raw_regular = min(raw_total, Decimal("8.00"))
    raw_overtime = max(raw_total - raw_regular, Decimal("0.00"))

    # Cộng dồn ca OT riêng (nếu có check-in/out ca OT)
    if record.overtime_check_in and record.overtime_check_out:
        raw_overtime += _compute_working_hours(record.overtime_check_in, record.overtime_check_out)
        raw_total = raw_regular + raw_overtime
    payroll_regular = OvertimeConfig.apply_multiplier(raw_regular, day_type)
    ot_type = day_type if day_type != "normal" else "after_shift"
    payroll_overtime = OvertimeConfig.apply_multiplier(raw_overtime, ot_type)
    payroll_total = (payroll_regular + payroll_overtime).quantize(Decimal("0.01"))
    return (
        payroll_total,    # Tổng giờ quy đổi lương
        payroll_regular,  # Giờ hành chính quy đổi
        raw_overtime,     # Tổng giờ OT thô
        raw_total,        # Tổng giờ làm thô
        payroll_overtime  # Giờ OT quy đổi
    )

def _save_leave_document(file_storage, category: str) -> str:
    if not file_storage or not file_storage.filename:
        raise ValidationError("Vui lòng tải lên giấy tờ đính kèm.")
    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed_ext = {"pdf", "png", "jpg", "jpeg"}
    if ext not in allowed_ext:
        raise ValidationError(f"Định dạng .{ext} không hợp lệ. Chỉ chấp nhận PDF hoặc ảnh.")
    path_parts = ["static", "uploads", "leave", category.lower()]
    full_folder_path = os.path.join(current_app.root_path, *path_parts)
    os.makedirs(full_folder_path, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    abs_save_path = os.path.join(full_folder_path, unique_name)
    file_storage.save(abs_save_path)
    return "/".join(path_parts[1:] + [unique_name])

from app.modules.employee.notification_service import EmployeeNotificationService

@employee_bp.route("/profile", methods=["GET", "POST"])
@auth_required 
@role_required("Employee")
def profile():
    employee = g.employee
    user = g.user
    from app.utils.time import get_current_time
    now = get_current_time()

    if not employee:
        flash("Không tìm thấy hồ sơ nhân viên.", "danger")
        return redirect(url_for("home.index_page"))

    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_profile":
            employee.full_name = request.form.get("full_name", employee.full_name).strip()
            employee.phone = request.form.get("phone", employee.phone).strip()
            user.email = request.form.get("email", user.email).strip()

            employee.province_id = request.form.get("province")
            employee.district_id = request.form.get("district")
            employee.ward_id = request.form.get("ward")
            employee.address_detail = request.form.get("address_detail", "").strip()

            db.session.commit()
            flash("✅ Đã cập nhật thông tin cá nhân.", "success")
            return redirect(url_for("employee.profile"))
        elif action == "change_password":
            current_pw = request.form.get("current_password", "")
            new_pw = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")
            if not check_password_hash(user.password_hash, current_pw):
                flash("❌ Mật khẩu hiện tại không đúng.", "danger")
            elif len(new_pw) < 8:
                flash("❌ Mật khẩu mới cần tối thiểu 8 ký tự.", "danger")
            elif new_pw != confirm_pw:
                flash("❌ Xác nhận mật khẩu không khớp.", "danger")
            else:
                user.password_hash = generate_password_hash(new_pw)
                db.session.commit()
                flash("✅ Đổi mật khẩu thành công.", "success")
            return redirect(url_for("employee.profile"))
    notifications = (
        Notification.query.filter_by(user_id=user.id, is_deleted=False)
        .order_by(Notification.created_at.desc())
        .limit(20)
        .all()
    )
    unread_count = EmployeeNotificationService.get_unread_count(user.id)
    complaints = (
        Complaint.query.filter_by(employee_id=employee.id)
        .order_by(Complaint.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "employee/profile.html",
        employee=employee,
        user=user,
        notifications=notifications,
        unread_count=unread_count, 
        complaints=complaints,
        now=now
    )

@employee_bp.route("/staff-profile")
@auth_required
@role_required("Employee")
def staff_profile():
    employee = g.employee
    user = g.user
    latest_contract = (
        Contract.query.filter_by(employee_id=employee.id)
        .order_by(Contract.start_date.desc(), Contract.created_at.desc())
        .first()
    )
    history_logs = (
        HistoryLog.query.filter_by(employee_id=employee.id)
        .order_by(HistoryLog.created_at.desc())
        .limit(10)
        .all()
    )
    history_events = []
    if employee.hire_date:
        history_events.append({
            "time": employee.hire_date,
            "event": "🎉 Gia nhập công ty",
            "detail": f"Vị trí: {employee.position.job_title if employee.position else 'Chuyên viên'}"
        })
    if user.created_at:
        history_events.append({
            "time": user.created_at,
            "event": "🔐 Tạo tài khoản",
            "detail": f"Username: {user.username}"
        })

    if employee.updated_at:
        history_events.append({
            "time": employee.updated_at,
            "event": "🔄 Cập nhật hồ sơ",
            "detail": "Thông tin nhân sự đã được thay đổi"
        })
    if latest_contract and latest_contract.start_date:
        history_events.append({
            "time": latest_contract.start_date,
            "event": "📝 Ký hợp đồng",
            "detail": f"Mã HĐ: {latest_contract.contract_code}"
        })
    for log in history_logs:
        history_events.append({
            "time": log.created_at,
            "event": f"📌 {log.action}",
            "detail": log.description or "Không có mô tả"
        })
    history_events.sort(
        key=lambda x: (
            datetime.combine(x["time"], time.min).replace(tzinfo=VN_TIMEZONE) 
            if isinstance(x["time"], date) and not isinstance(x["time"], datetime)
            else (x["time"].replace(tzinfo=VN_TIMEZONE) if x["time"].tzinfo is None else x["time"].astimezone(VN_TIMEZONE))
        ),
        reverse=True
    )
    display_events = history_events[:20]
    return render_template(
        "employee/staff_profile.html",
        employee=employee,
        user=user,
        latest_contract=latest_contract,
        history_events=display_events,
        enum_labelize=labelize_enum
    )

@employee_bp.route("/update-profile", methods=["POST"])
@auth_required
@role_required("Employee")  
def update_profile_ajax():
    employee = g.employee
    if not employee:
        return jsonify({"error": "Không tìm thấy hồ sơ nhân viên"}), 404
    data = request.get_json()
    if not data:
        return jsonify({"error": "Không có dữ liệu yêu cầu"}), 400
    try:
        dob_str = data.get("dob")
        if dob_str:
            employee.dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
        gender = data.get("gender")
        if gender in {"male", "female", "other"}:
            employee.gender = gender
        employee.full_name = data.get("full_name", employee.full_name).strip()
        employee.phone = data.get("phone", employee.phone).strip()
        employee.province_id = data.get("province", employee.province_id)
        employee.district_id = data.get("district", employee.district_id)
        employee.ward_id = data.get("ward", employee.ward_id)
        employee.address_detail = data.get("address_detail", employee.address_detail).strip()
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": "Cập nhật hồ sơ thành công!",
            "data": {
                "full_name": employee.full_name,
                "phone": employee.phone
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Update Profile Error: {str(e)}") 
        return jsonify({"error": "Có lỗi xảy ra trong quá trình lưu dữ liệu"}), 500
    
@employee_bp.route("/attendance")
@auth_required
@role_required("Employee")
def attendance():
    employee = g.employee
    user = g.user
    if not employee:
        flash("Không tìm thấy hồ sơ nhân viên.", "danger")
        return redirect(url_for("home.index_page"))
    now = get_current_time()
    latest_attendance = (
        Attendance.query.filter_by(employee_id=employee.id)
        .order_by(Attendance.date.desc())
        .first()
    )
    if latest_attendance and latest_attendance.date > now.date():
        fallback_time = (
            latest_attendance.check_out.time() if latest_attendance.check_out
            else (latest_attendance.check_in.time() if latest_attendance.check_in else time(17, 0))
        )
        now = datetime.combine(latest_attendance.date, fallback_time).replace(tzinfo=VN_TIMEZONE)
        set_simulated_time(now)
    try:
        month_param = request.args.get("month")
        year_param = request.args.get("year")
        selected_month = int(month_param) if month_param else now.month
        selected_year = int(year_param) if year_param else now.year
        if not (1 <= selected_month <= 12): selected_month = now.month
        if not (2020 <= selected_year <= now.year + 1): selected_year = now.year
    except (ValueError, TypeError):
        selected_month = now.month
        selected_year = now.year
    today = Attendance.query.filter_by(
        employee_id=employee.id, 
        date=now.date()
    ).first()
    try:
        history = AttendanceService.get_history(
            employee.id,
            now.isoformat(),
            month=selected_month,
            year=selected_year,
        )
    except ValidationError as e:
        flash(f"Lỗi lọc dữ liệu: {str(e)}", "warning")
        history = []
    today_ot_request = (
        OvertimeRequest.query.filter_by(
            employee_id=employee.id,
            overtime_date=now.date(),
            is_deleted=False,
        )
        .order_by(OvertimeRequest.id.desc())
        .first()
    )
    ot_preview_hours = Decimal("0.00")
    if (
        today
        and today_ot_request
        and (today_ot_request.status or "").lower() in {"approved", "pending_admin"}
        and Decimal(str(today.overtime_hours or 0)) <= Decimal("0.00")
    ):
        val = (today_ot_request.approved_hours or 
               today_ot_request.requested_hours or 
               today_ot_request.overtime_hours or 0)
        ot_preview_hours = Decimal(str(val)).quantize(Decimal("0.01"))
    shift_info = _build_shift_and_actions(today)
    today_holiday = is_public_holiday(now.date())
    holiday_lookup = _get_holiday_lookup()
    role_name = (user.role.name.lower() if user and user.role else "")
    can_reset_ot_request = (role_name == RoleName.ADMIN.lower() or os.getenv("FLASK_ENV") == "development")
    return render_template(
        "employee/attendance.html",
        employee=employee,
        today=today,
        history=history,
        now=now,
        selected_month=selected_month,  
        selected_year=selected_year,   
        current_year=now.year,
        today_holiday=today_holiday,
        holiday_lookup=holiday_lookup,
        today_ot_request=today_ot_request,
        ot_preview_hours=ot_preview_hours,       
        shift_info=shift_info,                                    
        can_reset_ot_request=can_reset_ot_request,
        enum_labelize=labelize_enum 
    )

@employee_bp.route("/system/time", methods=["GET", "POST"])
@auth_required
@role_required("Employee")  
def system_time_control():
    employee = g.employee
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        now = get_current_time(payload)
        session["simulated_now"] = now.isoformat()
        session["system_time_mode"] = "SIMULATED"
    else:
        now = get_current_time()
        session["system_time_mode"] = "SIMULATED" if session.get("simulated_now") else "REAL"
    attendance = AttendanceService.get_today(employee.id, now.isoformat())
    ot_request = (
        OvertimeRequest.query.filter_by(
            employee_id=employee.id,
            overtime_date=now.date(),
            is_deleted=False,
        )
        .order_by(OvertimeRequest.id.desc())
        .first()
    )
    state_result = AttendanceService.compute_attendance_state(now, attendance, ot_request)
    regular_hours = 0.0
    overtime_hours = 0.0
    if attendance:
        if attendance.check_in and not attendance.check_out:
            regular_hours = float(AttendanceService.calculate_regular_hours_raw(attendance.check_in, now))
        else:
            regular_hours = float(attendance.regular_hours or 0)
        if attendance.overtime_check_in and not attendance.overtime_check_out:
            overtime_hours = float(AttendanceService.calculate_overtime_hours_raw(attendance.overtime_check_in, now))
        else:
            overtime_hours = float(attendance.overtime_hours or 0)
    return jsonify({
        "status": "success",
        "mode": session.get("system_time_mode", "REAL"),
        "current_time": now.isoformat(),
        "attendance_state": state_result.state,
        "button_enabled": state_result.button_enabled,
        "button_text": state_result.button_text,
        "can_scan": state_result.can_scan,
        "message": state_result.message,
        "overtime_status": state_result.overtime_status,
        "regular_hours": round(regular_hours, 2),
        "overtime_hours": round(overtime_hours, 2),
        "can_check_in": state_result.state == "not_started",
        "can_check_out": state_result.state == "working_regular" and state_result.button_enabled,
        "employee_name": employee.full_name
    }), 200

@employee_bp.route("/attendance/state", methods=["GET"])
@auth_required
@role_required(RoleName.EMPLOYEE) 
def attendance_state_api():
    employee = g.employee
    if not employee:
        return jsonify({"message": "Employee not found"}), 404
    from app.utils.time import get_current_time
    now = get_current_time() 
    today_attendance = Attendance.query.filter_by(
        employee_id=employee.id, 
        date=now.date()
    ).first()
    today_ot_request = (
        OvertimeRequest.query.filter_by(
            employee_id=employee.id,
            overtime_date=now.date(),
            is_deleted=False,
        )
        .order_by(OvertimeRequest.id.desc())
        .first()
    )
    state_result = AttendanceService.compute_attendance_state(
        now, today_attendance, today_ot_request
    )
    return jsonify({
        "current_time": now.isoformat(),
        "mode": "SIMULATED" if session.get("simulated_now") else "REAL",
        "today": AttendanceService.build_attendance_payload(today_attendance) if today_attendance else None,
        "today_ot_request": {
            "id": today_ot_request.id if today_ot_request else None,
            "status": today_ot_request.status if today_ot_request else None,
        },
        "state": state_result.state,
        "button_enabled": state_result.button_enabled,
        "button_text": state_result.button_text,
        "can_scan": state_result.can_scan,
        "message": state_result.message,
        "overtime_status": state_result.overtime_status,
        "can_check_in": state_result.state == "not_started",
        "can_check_out": state_result.state == "working_regular" and state_result.button_enabled,
    })

@employee_bp.route("/attendance/check", methods=["POST"])
@auth_required
@role_required("Employee")
def employee_attendance_check_api():
    employee = g.employee
    payload = request.get_json(silent=True) or {}
    now = get_current_time(payload) 
    if "simulated_now" in payload:
        session["simulated_now"] = now.isoformat()
    try:
        result = AttendanceService.process_employee_action(
            employee_id=employee.id, 
            payload=payload, 
            current_time=now 
        )
        return jsonify({
            "status": "success",
            "message": result.get("message", "Thao tác thành công"),
            "current_time": now.isoformat(), # Trả về để UI cập nhật lại đồng hồ
            **result
        })
    except ValidationError as e:
        return jsonify({
            "status": "error",
            "type": "validation",
            "message": str(e)
        }), 400
    except Exception as e:
        db.session.rollback() 
        return jsonify({
            "status": "error",
            "type": "system",
            "message": f"Lỗi hệ thống: {str(e)}"
        }), 500

@employee_bp.route("/attendance/delete", methods=["DELETE"])
@auth_required
@role_required("Employee") 
def delete_attendance_record():
    employee = g.employee 
    payload = request.get_json(silent=True) or {}
    date_str = payload.get("date")
    if not date_str:
        return jsonify({
            "status": "error",
            "message": "Thiếu ngày cần xóa",
        }), 400
    now = get_current_time()
    try:
        new_last_date = AttendanceService.delete_attendance(employee.id, date_str)
        rollback_date = (
            new_last_date.isoformat()
            if new_last_date
            else now.date().isoformat()
        )
        return jsonify({
            "status": "success",
            "message": f"Đã xóa chấm công ngày {date_str}",
            "rollback_date": rollback_date,
            "system_time_mode": "SIMULATED" if session.get("simulated_now") else "REAL"
        })
    except ValidationError as e:
        return jsonify({
            "status": "error",
            "message": str(e),
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Lỗi hệ thống: {str(e)}",
        }), 500

@employee_bp.route("/leave", methods=["GET", "POST"])
@auth_required
@role_required("Employee")
def leave_request():
    employee = g.employee
    now = get_current_time()
    
    if not employee:
        flash("Không tìm thấy hồ sơ nhân viên", "danger")
        return redirect(url_for("home.index_page"))
    usage = LeaveService.get_leave_balance(employee.id, now.year)
    leave_types = ensure_leave_types()
    leave_type_by_id = {t.id: t for t in leave_types}
    
    annual_type = next((t for t in leave_types if t.name == "Nghỉ phép năm"), None)
    holiday_type = next((t for t in leave_types if t.name == "Nghỉ lễ"), None)

    if request.method == "POST":
        leave_type_id = request.form.get("leave_type_id", type=int)
        from_date_str = request.form.get("from_date")
        to_date_str = request.form.get("to_date")
        reason = request.form.get("reason", "").strip()
        subtype = request.form.get("personal_subtype", "").strip()
        relation = request.form.get("relation", "").strip().lower()
        leave_document = request.files.get("leave_document")
        selected_type = leave_type_by_id.get(leave_type_id)
        if not selected_type:
            flash("❌ Loại nghỉ không hợp lệ.", "danger")
            return redirect(url_for("employee.leave_request"))

        if selected_type.name == "Nghỉ lễ":
            flash("❌ Nghỉ lễ do hệ thống tự động xử lý, không cần gửi đơn.", "danger")
            return redirect(url_for("employee.leave_request"))
        try:
            from_obj = datetime.strptime(from_date_str, "%Y-%m-%d").date()
            to_obj = datetime.strptime(to_date_str, "%Y-%m-%d").date()
            document_url = None
            if leave_document and leave_document.filename != '':
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'leave_docs')
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                filename = secure_filename(leave_document.filename)
                unique_filename = f"{now.strftime('%Y%m%d%H%M%S')}_{filename}"
                leave_document.save(os.path.join(upload_folder, unique_filename))
                document_url = f"uploads/leave_docs/{unique_filename}"
            dto = LeaveRequestDTO(
                employee_id=employee.id,
                leave_type_id=leave_type_id,
                from_date=from_obj,
                to_obj=to_obj,
                reason=reason,
                document_url=document_url,
                subtype=subtype if subtype else None,
                relation=relation if relation else None,
                approved_by=employee.manager_id
            )
            LeaveService.create_leave_request(dto)
            flash("✅ Đã gửi đơn nghỉ phép thành công.", "success")
            return redirect(url_for("employee.leave_request"))
        except ValueError as e:
            flash(f"❌ {str(e)}", "danger")
        except Exception as e:
            flash(f"❌ Lỗi hệ thống: {str(e)}", "danger")
        return redirect(url_for("employee.leave_request"))
    requests_list = LeaveService.get_my_requests(employee.id)
    today_holiday = is_public_holiday(now.date())

    return render_template(
        "employee/leave.html",
        employee=employee,
        leave_types=leave_types,
        requests=requests_list,
        usage=usage,
        current_year=now.year,
        now=now,
        annual_type_id=annual_type.id if annual_type else None,
        holiday_type_id=holiday_type.id if holiday_type else None,
        personal_subtypes=PERSONAL_SUBTYPES, 
        today_holiday=today_holiday,
        allowed_funeral_relations=sorted(ALLOWED_FUNERAL_RELATIONS),
        status_badge=get_status_badge
    )

@employee_bp.route("/payslip", methods=["GET"])
@auth_required
@role_required("Employee")
def payslip():
    user_id = g.user.id 
    now = get_current_time()
    filters = {
        "year": request.args.get("year", default=now.year, type=int),
        "status": request.args.get("status", default="").strip(),
        "paid_state": request.args.get("paid_state", default="").strip(),
        "has_complaint": request.args.get("has_complaint", default="false")
    }
    try:
        payroll_data = EmployeePayrollService.payroll_history(user_id=user_id, filters=filters)
        return render_template(
            "employee/payslip.html",
            summary=payroll_data["summary"],           # Thông tin kỳ lương mới nhất
            payslips=payroll_data["items"],            # Danh sách các phiếu lương để loop
            dependents=payroll_data["number_of_dependents"],
            selected_year=filters["year"],             # Năm đang chọn để lọc
            current_year=now.year,                     # Năm hiện tại của simulation
            now=now
        )
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("home.index_page"))
    except Exception as e:
        flash(f"Lỗi hệ thống: {str(e)}", "danger")
        return redirect(url_for("home.index_page"))

@employee_bp.route("/payslip/api/history", methods=["GET"])
@auth_required
@role_required("Employee")
def employee_payroll_history_api():
    user_id = g.user.id
    now = get_current_time()
    filters = {
        "year": request.args.get("year", default=now.year, type=int),
        "status": request.args.get("status"),
        "has_complaint": request.args.get("has_complaint"),
        "paid_state": request.args.get("paid_state"),
    }
    try:
        data = EmployeePayrollService.payroll_history(user_id, filters)
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        return jsonify({"error": "Đã xảy ra lỗi hệ thống", "detail": str(e)}), 500

@employee_bp.route("/payslip/api/<int:salary_id>", methods=["GET"])
@auth_required
@role_required("Employee")
def employee_payroll_detail_api(salary_id: int):
    user_id = g.user.id
    try:
        detail_data = EmployeePayrollService.payroll_detail(user_id, salary_id)
        return jsonify(detail_data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as e:
        return jsonify({"error": "Lỗi hệ thống khi tải chi tiết lương", "detail": str(e)}), 500

@employee_bp.route("/payslip/api/<int:salary_id>/pdf", methods=["GET"])
@auth_required
@role_required("Employee")
def employee_payroll_pdf_api(salary_id: int):
    user_id = g.user.id
    try:
        filename, content = EmployeePayrollService.payslip_pdf(user_id, salary_id)
        return Response(
            content,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as e:
        return jsonify({"error": "Lỗi khi tạo file PDF", "detail": str(e)}), 500

@employee_bp.route("/payslip/api/<int:salary_id>/complaint", methods=["POST"])
@auth_required
@role_required("Employee")
def employee_payroll_complaint_api(salary_id: int):
    # 1. Lấy user_id từ đối tượng g (do decorator thiết lập)
    user_id = g.user.id
    
    # 2. Thu thập dữ liệu từ request (form-data và files)
    # Service của bạn yêu cầu: user_id, salary_id, issue_type, description, attachment
    issue_type = request.form.get("issue_type", "other")
    description = request.form.get("description", "").strip()
    attachment = request.files.get("attachment")

    try:
        # 3. Gọi Service xử lý nghiệp vụ gửi khiếu nại
        # Hàm này sẽ tự handle: Tạo Complaint, Lưu File, Gửi thông báo cho Manager/HR
        result = EmployeePayrollService.submit_complaint(
            user_id=user_id,
            salary_id=salary_id,
            issue_type=issue_type,
            description=description,
            attachment=attachment
        )
        
        return jsonify(result)

    except ValueError as exc:
        # Bắt các lỗi validate từ Service (thiếu mô tả, sai định dạng file, không tìm thấy lương)
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        # Bắt lỗi hệ thống (lỗi upload file, lỗi commit database)
        return jsonify({"error": "Lỗi hệ thống khi gửi khiếu nại", "detail": str(e)}), 500

@employee_bp.route("/payslip/api/complaints", methods=["GET"])
@auth_required
@role_required("Employee")
def employee_payroll_complaints_api():
    user_id = g.user.id
    try:
        complaints_list = EmployeePayrollService.salary_complaints(user_id)
        return jsonify({
            "items": complaints_list,
            "total": len(complaints_list)
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        return jsonify({"error": "Không thể tải danh sách khiếu nại", "detail": str(e)}), 500
    
@employee_bp.route("/payslip/api/complaints/<int:complaint_id>/close", methods=["POST"])
@auth_required
@role_required("Employee")
def employee_payroll_close_complaint_api(complaint_id: int):
    user_id = g.user.id
    try:
        result = EmployeePayrollService.close_salary_complaint(user_id, complaint_id)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        return jsonify({"error": "Lỗi khi đóng khiếu nại", "detail": str(e)}), 500

from flask import render_template, g, current_app
from app.utils.time import get_current_time, VN_TIMEZONE
from app.models import Complaint  # Import đúng Model bạn vừa gửi
from .notification_service import EmployeeNotificationService # Import Class Service mới

@employee_bp.route("/notifications", methods=["GET"])
@auth_required
@role_required("Employee")
def notifications():
    user = g.user
    employee = g.employee  
    now = get_current_time()
    items = EmployeeNotificationService.get_notifications(user_id=user.id, limit=50)
    complaint_map: dict[int, dict] = {}
    if employee:
        active_complaints = (
            Complaint.query.filter_by(employee_id=employee.id)
            .filter(Complaint.notification_id.isnot(None))
            .all()
        )
        for complaint in active_complaints:
            if complaint.notification_id:
                complaint_map[complaint.notification_id] = {
                    "id": complaint.id,
                    "status": complaint.status,
                    "has_reply": bool(complaint.admin_reply),
                    "closed": bool(complaint.closed_by_employee),
                }
    return render_template(
        "employee/notifications.html",
        notifications=items,      
        complaint_map=complaint_map,
        now=now
    )

@employee_bp.route("/notifications/<int:noti_id>/read", methods=["POST"])
@auth_required
@role_required("Employee")
def mark_notification_read(noti_id: int):
    user_id = g.user.id
    try:
        noti_detail = EmployeeNotificationService.notification_detail(
            user_id=user_id, 
            noti_id=noti_id
        )
        return jsonify({
            "success": True, 
            "id": noti_detail["id"], 
            "is_read": noti_detail["is_read"]
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as e:
        return jsonify({"error": "Lỗi hệ thống khi cập nhật trạng thái thông báo", "detail": str(e)}), 500

@employee_bp.route("/notifications/<int:noti_id>/feedback", methods=["POST"])
@auth_required
@role_required("Employee")
def send_notification_feedback(noti_id: int):
    user = g.user
    employee = g.employee
    issue_type = request.form.get("issue_type", "other").strip() or "other"
    description = request.form.get("description", "").strip()
    attachment = request.files.get("attachment")
    try:
        result = EmployeeNotificationService.submit_notification_complaint(
            user=user,
            employee=employee,
            noti_id=noti_id,
            issue_type=issue_type,
            description=description,
            attachment=attachment
        )
        return jsonify({
            "success": True, 
            **result
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        return jsonify({"error": "Lỗi hệ thống khi gửi phản hồi thông báo", "detail": str(e)}), 500

@employee_bp.route("/notifications/<int:noti_id>/detail", methods=["GET"])
@auth_required
@role_required("Employee")
def notification_detail_api(noti_id: int):
    user_id = g.user.id
    try:
        noti_detail = EmployeeNotificationService.notification_detail(
            user_id=user_id, 
            noti_id=noti_id
        )
        return jsonify(noti_detail)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as e:
        return jsonify({"error": "Không thể tải chi tiết thông báo", "detail": str(e)}), 500

@employee_bp.route("/notifications/<int:noti_id>/delete", methods=["DELETE"])
@auth_required
@role_required("Employee")
def delete_notification_with_cascade(noti_id: int):
    user_id = g.user.id
    try:
        result = AttendanceService.delete_notification_cascade(
            notification_id=noti_id, 
            user_id=user_id
        )
        return jsonify({
            "ok": True, 
            **result
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        db.session.rollback()
        return jsonify({
            "error": f"Không thể xóa thông báo do lỗi hệ thống", 
            "detail": str(exc)
        }), 500
    
@employee_bp.route("/notifications/<int:noti_id>/overtime-reset", methods=["POST"])
@auth_required
@role_required("Employee")
def reset_overtime_from_notification(noti_id: int):
    user = g.user
    employee = g.employee
    try:
        result = AttendanceService.process_overtime_reset_from_notification(
            user_id=user.id,
            employee_id=employee.id,
            noti_id=noti_id
        )
        return jsonify(result), 200
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 404


@employee_bp.route("/complaints/<int:complaint_id>/close", methods=["POST"])
@auth_required
@role_required("Employee")
def close_complaint_api(complaint_id: int):
    try:
        result = EmployeeComplaintService.close_complaint(
            user_id=g.user.id, 
            complaint_id=complaint_id
        )
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@employee_bp.route("/resignation/my", methods=["GET"])
@auth_required
def my_resignation_requests():
    employee = g.employee
    rows = (
        ResignationRequest.query.filter_by(
            employee_id=employee.id,
            is_deleted=False 
        )
        .order_by(ResignationRequest.created_at.desc())
        .all()
    )
    return jsonify([row.to_dict() for row in rows]), 200


@employee_bp.route("/resignation", methods=["POST"])
@auth_required
@role_required("Employee")
def submit_resignation_request():
    employee = getattr(g, "current_employee", None)
    
    if not employee:
        return jsonify({"error": "Không tìm thấy hồ sơ nhân viên hợp lệ cho tài khoản này"}), 404
    expected_last_day = request.form.get("expected_last_day")
    reason_category = (request.form.get("reason_category") or "").strip().lower()
    reason_text = (request.form.get("reason_text") or "").strip() or None
    extra_note = (request.form.get("extra_note") or "").strip() or None
    handover_employee_id = request.form.get("handover_employee_id", type=int)
    if not expected_last_day:
        return jsonify({"error": "Ngày dự kiến nghỉ là bắt buộc"}), 400
    try:
        expected_last_day_date = date.fromisoformat(expected_last_day)
    except ValueError:
        return jsonify({"error": "Định dạng ngày không hợp lệ. Vui lòng dùng YYYY-MM-DD"}), 400
    allowed_reasons = {"transfer", "personal", "health", "study", "other"}
    if reason_category not in allowed_reasons:
        return jsonify({"error": "Lý do nghỉ việc không hợp lệ"}), 400
    attachment_url = None
    file = request.files.get("attachment")
    if file and file.filename:
        filename = secure_filename(file.filename)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in {"pdf", "jpg", "jpeg", "png", "doc", "docx"}:
            return jsonify({"error": "Định dạng file đính kèm không được hỗ trợ"}), 400
        folder = os.path.join(os.getcwd(), "app", "static", "uploads", "resignation")
        os.makedirs(folder, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        absolute_path = os.path.join(folder, unique_name)
        file.save(absolute_path)
        attachment_url = f"/static/uploads/resignation/{unique_name}"
    try:
        request_item = ResignationService.create_request(
            employee=employee,
            expected_last_day=expected_last_day_date,
            reason_category=reason_category,
            reason_text=reason_text,
            extra_note=extra_note,
            handover_employee_id=handover_employee_id,
            attachment_url=attachment_url,
            request_type="employee",
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        return jsonify({"error": f"Lỗi xử lý hệ thống: {str(e)}"}), 500
    return jsonify({
        "message": "Đã gửi đơn nghỉ việc, chờ Manager duyệt", 
        "request": request_item.to_dict()
    }), 201

@employee_bp.route("/profile/dependents", methods=["GET"])
@auth_required
@role_required("Employee")
def employee_dependents_api():
    employee = getattr(g, "current_employee", None)
    if not employee:
        return jsonify({"error": "Không tìm thấy hồ sơ nhân viên hợp lệ cho tài khoản này"}), 404
    try:
        data = EmployeeDependentService.list_dependents(employee=employee)
        return jsonify(data), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        return jsonify({"error": f"Lỗi hệ thống: {str(e)}"}), 500

@employee_bp.route("/profile/dependents", methods=["POST"])
@auth_required
@role_required("Employee")
def employee_create_dependent_api():
    employee = getattr(g, "current_employee", None)
    current_user = getattr(g, "current_user", None)
    if not employee or not current_user:
        return jsonify({"error": "Không tìm thấy thông tin nhân viên hợp lệ"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        result = EmployeeDependentService.create_dependent(
            employee=employee,
            payload=payload,
            actor_user_id=current_user.id
        )
        return jsonify(result), 201
        
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        return jsonify({"error": f"Lỗi xử lý hệ thống: {str(e)}"}), 500

@employee_bp.route("/profile/dependents/<int:dependent_id>", methods=["PUT"])
@auth_required
@role_required("Employee")
def employee_update_dependent_api(dependent_id: int):
    employee = getattr(g, "current_employee", None)
    current_user = getattr(g, "current_user", None)
    if not employee or not current_user:
        return jsonify({"error": "Không tìm thấy thông tin nhân viên hợp lệ"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        result = EmployeeDependentService.update_dependent(
            employee=employee,
            dependent_id=dependent_id,
            payload=payload,
            actor_user_id=current_user.id
        )
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        return jsonify({"error": f"Lỗi xử lý hệ thống: {str(e)}"}), 500

@employee_bp.route("/profile/dependents/<int:dependent_id>", methods=["DELETE"])
@auth_required
@role_required("Employee")
def employee_delete_dependent_api(dependent_id: int):
    employee = getattr(g, "current_employee", None)
    current_user = getattr(g, "current_user", None)
    
    if not employee or not current_user:
        return jsonify({"error": "Không tìm thấy thông tin nhân viên hợp lệ"}), 404
    try:
        result = EmployeeDependentService.delete_dependent(
            employee=employee,
            dependent_id=dependent_id,
            actor_user_id=current_user.id
        )
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        return jsonify({"error": f"Lỗi xử lý hệ thống: {str(e)}"}), 500


@employee_bp.route("/attendance/overtime-request", methods=["POST"])
@auth_required
@role_required("Employee")
def submit_overtime_request_api():
    current_user = getattr(g, "current_user", None)
    if not current_user:
        return jsonify({"error": "Không tìm thấy thông tin phiên đăng nhập hợp lệ"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        result = EmployeeOvertimeService.submit_overtime(
            user_id=current_user.id,
            payload=payload,
            actor_user_id=current_user.id
        )
        return jsonify(result), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        return jsonify({"error": f"Lỗi hệ thống trong quá trình xử lý: {str(e)}"}), 500
    
@employee_bp.route("/attendance/overtime-request/reset", methods=["DELETE"])
@auth_required
@role_required("Employee")
def reset_overtime_request_api():
    user = getattr(g, "current_user", None)
    employee = getattr(g, "current_employee", None)
    if not user or not employee:
        return jsonify({"error": "Không tìm thấy thông tin người dùng hoặc nhân viên hợp lệ"}), 404
    role_name = (user.role.name.lower() if user.role else "")
    is_dev_or_test = current_app.config.get("DEBUG") or current_app.config.get("TESTING")
    
    if role_name != "admin" and not is_dev_or_test:
        return jsonify({"error": "Chỉ ADMIN hoặc môi trường DEV/TEST mới được reset OT Request"}), 403
    ot_request = (
        OvertimeRequest.query.filter_by(
            employee_id=employee.id,
            overtime_date=date.today(),
            is_deleted=False,
        )
        .order_by(OvertimeRequest.id.desc())
        .first()
    )
    if not ot_request:
        return jsonify({"error": "Không có yêu cầu OT nào trong ngày hôm nay để reset"}), 404
    ot_date = ot_request.overtime_date
    ot_id = ot_request.id
    allowed_statuses = {
        EmployeeOvertimeService.STATUS_PENDING_MANAGER,  # "pending_manager"
        EmployeeOvertimeService.STATUS_APPROVED,         # "approved"
        EmployeeOvertimeService.STATUS_REJECTED          # "rejected"
    }
    if ot_request.status not in allowed_statuses:
        return jsonify({"error": f"Yêu cầu OT có trạng thái '{ot_request.status}' không được hỗ trợ để reset"}), 400
    notifications = Notification.query.filter(
        Notification.is_deleted.is_(False),
        Notification.type == "overtime",
        db.or_(
            Notification.link.like("/employee/attendance%"),
            Notification.link.like("/manager/overtime%"),  
            Notification.link.like("/hr/attendance%"),
            Notification.link.like("/admin/attendance%"),
        ),
        db.or_(
            Notification.content.ilike(f"%{employee.full_name}%"),
            Notification.content.ilike(f"%#{ot_id}%"),
            Notification.content.ilike(f"%{ot_date.strftime('%d/%m')}%"),
        ),
    ).all()
    for item in notifications:
        item.is_deleted = True
    attendance = Attendance.query.filter_by(employee_id=employee.id, date=ot_date).first()
    if attendance:
        attendance.overtime_hours = Decimal("0.00")
        if attendance.attendance_type == "overtime":
            attendance.attendance_type = "normal"
    ot_request.is_deleted = True
    db.session.add(
        HistoryLog(
            employee_id=employee.id,
            action="OVERTIME_RESET_TEST_MODE",
            entity_type="overtime_request",
            entity_id=ot_id,
            description=f"Reset OT request test-mode (Hủy trạng thái {ot_request.status}) ngày {ot_date.isoformat()}",
            performed_by=user.id,
        )
    )
    db.session.commit()
    return jsonify({
        "message": "Đã tiến hành reset toàn bộ dữ liệu đơn OT trong ngày (Môi trường Test)",
        "status": "RESET_OK"
    }), 200

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@employee_bp.route("/upload-avatar", methods=["POST"])
@auth_required                 
@role_required("Employee")         
def upload_avatar():
    employee = getattr(g, "current_employee", None) or getattr(g, "current_user", None)
    
    if not employee:
        return jsonify({"status": "error", "message": "Không tìm thấy thông tin nhân viên trong phiên làm việc"}), 404
    if "avatar" not in request.files:
        return jsonify({"status": "error", "message": "Vui lòng chọn file ảnh để tải lên"}), 400
    file = request.files.get("avatar")
    if file.filename == "":
        return jsonify({"status": "error", "message": "Tên file không hợp lệ"}), 400
    if not allowed_file(file.filename):
        return jsonify({"status": "error", "message": "Định dạng file không hỗ trợ (Chỉ nhận JPG, JPEG, PNG, GIF)"}), 400
    original_filename = secure_filename(file.filename)
    extension = original_filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{extension}"
    upload_folder = os.path.join(current_app.root_path, "static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    filepath = os.path.join(upload_folder, unique_filename)
    try:
        file.save(filepath)
        employee.avatar = f"/static/uploads/{unique_filename}"
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": "Cập nhật ảnh đại diện thành công",
            "url": employee.avatar
        }), 200
    except Exception as e:
        db.session.rollback()
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}), 500