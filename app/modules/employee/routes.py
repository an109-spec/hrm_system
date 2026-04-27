from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
import os
import re
import uuid
from lunardate import LunarDate
from flask import Response, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
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
    Salary,
    User,
    Holiday,
    ResignationRequest,
)
from app.modules.attendance.overtime_service import OvertimeService
from app.common.exceptions import ValidationError
from app.modules.attendance.service import AttendanceService
from app.utils.time import parse_simulated_time
from .ess_service import EmployeeESSService
from .payroll_service import EmployeePayrollService
from . import employee_bp
from app.modules.resignation_service import ResignationService
VN_FIXED_PUBLIC_HOLIDAYS: dict[str, str] = {
    "01-01": "Tết Dương lịch",
    "04-30": "Ngày Giải phóng miền Nam",
    "05-01": "Quốc tế Lao động",
    "09-02": "Quốc khánh",
}
VN_LUNAR_PUBLIC_HOLIDAYS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Tết Nguyên đán (Mùng 1)"),
    (1, 2, "Tết Nguyên đán (Mùng 2)"),
    (1, 3, "Tết Nguyên đán (Mùng 3)"),
    (3, 10, "Giỗ Tổ Hùng Vương"),
)


def _build_lunar_public_holidays_for_year(year: int) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for lunar_month, lunar_day, holiday_name in VN_LUNAR_PUBLIC_HOLIDAYS:
        try:
            solar_date = LunarDate(year, lunar_month, lunar_day).toSolarDate()
        except ValueError:
            continue
        lookup[solar_date.strftime("%m-%d")] = holiday_name
    return lookup

def _current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def _current_employee() -> Employee | None:
    user = _current_user()
    if user and user.employee_profile:
        return user.employee_profile
    if user:
        employee = Employee.query.filter_by(user_id=user.id).first()
        if employee:
            return employee

        # Tài khoản legacy (đặc biệt là admin seed cũ) có thể chưa có hồ sơ Employee.
        # Tạo hồ sơ mặc định để không bị lỗi "Không tìm thấy hồ sơ nhân viên"
        # khi truy cập trang hồ sơ/thông tin cá nhân.
        employee = Employee(
            user_id=user.id,
            full_name=(user.username or user.email or f"User {user.id}").strip(),
            phone=None,
            dob=date(2000, 1, 1),
            gender="other",
            hire_date=date.today(),
            working_status="active",
        )
        db.session.add(employee)
        db.session.commit()
        return employee
    return Employee.query.order_by(Employee.id.asc()).first()


def _ensure_login():
    if not session.get("user_id"):
        return redirect(url_for("auth.login", next=request.url))
    return None

def _redirect_when_missing_employee():
    user = _current_user()
    role_name = (user.role.name.lower() if user and user.role else "")
    if role_name == "admin":
        return redirect(url_for("admin.admin_dashboard_page"))
    return redirect(url_for("auth.login"))

def _is_attendance_required(employee: Employee | None) -> bool:
    if not employee:
        return False
    return employee.is_attendance_required is not False


def _get_holiday_for_date(target_date: date) -> Holiday | None:
    default_holiday_name = VN_FIXED_PUBLIC_HOLIDAYS.get(target_date.strftime("%m-%d"))
    lunar_holiday_lookup = _build_lunar_public_holidays_for_year(target_date.year)
    lunar_holiday_name = lunar_holiday_lookup.get(target_date.strftime("%m-%d"))
    exact_holiday = Holiday.query.filter_by(date=target_date).first()
    if exact_holiday:
        return exact_holiday

    recurring_holiday = (
        Holiday.query.filter(
            Holiday.is_recurring.is_(True),
            db.extract("month", Holiday.date) == target_date.month,
            db.extract("day", Holiday.date) == target_date.day,
        )
        .order_by(Holiday.id.asc())
        .first()
    )
    if recurring_holiday:
        return recurring_holiday

    if default_holiday_name:
        return Holiday(
            name=default_holiday_name,
            date=target_date,
            is_paid=True,
            is_recurring=True,
        )
    if lunar_holiday_name:
        return Holiday(
            name=lunar_holiday_name,
            date=target_date,
            is_paid=True,
            is_recurring=False,
        )
    return None

def _get_holiday_lookup() -> dict[str, str]:
    lookup = {
        holiday.date.strftime("%m-%d"): holiday.name
        for holiday in Holiday.query.order_by(Holiday.is_recurring.desc(), Holiday.id.asc()).all()
    }
    for holiday_key, holiday_name in VN_FIXED_PUBLIC_HOLIDAYS.items():
        lookup.setdefault(holiday_key, holiday_name)
    for holiday_key, holiday_name in _build_lunar_public_holidays_for_year(date.today().year).items():
        lookup.setdefault(holiday_key, holiday_name)
    return lookup
class EmployeeDashboardService:
    @staticmethod
    def get_today_attendance(employee_id: int, target_date: date | None = None):
        target_date = target_date or date.today()
        return Attendance.query.filter_by(employee_id=employee_id, date=target_date).first()

    @staticmethod
    def get_leave_balance(employee_id: int, current_year: int):
        usage = EmployeeLeaveUsage.query.filter_by(employee_id=employee_id, year=current_year).first()
        if not usage:
            usage = EmployeeLeaveUsage(
                employee_id=employee_id,
                year=current_year,
                total_days=12,
                used_days=0,
                remaining_days=12,
            )
            db.session.add(usage)
            db.session.commit()
            usage.update_balance()
            return usage

        if usage.total_days is None or int(usage.total_days) <= 0:
            usage.total_days = 12
        if usage.used_days is None or int(usage.used_days) < 0:
            usage.used_days = 0
        usage.update_balance()
        db.session.commit()
        return usage

    @staticmethod
    def get_latest_salary(employee_id: int):
        return (
            Salary.query.filter_by(employee_id=employee_id, status="paid")
            .order_by(Salary.year.desc(), Salary.month.desc())
            .first()
        )

    @staticmethod
    def get_notifications(user_id: int, limit: int = 5):
        return (
            Notification.query.filter_by(user_id=user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .all()
        )


def _compute_working_hours(checkin: datetime, checkout: datetime) -> Decimal:
    total_seconds = Decimal((checkout - checkin).total_seconds())
    total_hours = (total_seconds / Decimal("3600")).quantize(Decimal("0.01"))

    if total_hours <= 0:
        return Decimal("0")

    lunch_start = datetime.combine(checkin.date(), time(12, 0, 0))
    lunch_end = datetime.combine(checkin.date(), time(13, 0, 0))
    overlap_start = max(checkin, lunch_start)
    overlap_end = min(checkout, lunch_end)
    if overlap_end > overlap_start:
        overlap_seconds = Decimal((overlap_end - overlap_start).total_seconds())
        total_hours -= (overlap_seconds / Decimal("3600")).quantize(Decimal("0.01"))
    return max(total_hours, Decimal("0"))

    return current_time
def _attendance_metrics(record: Attendance | None) -> tuple[Decimal, Decimal, Decimal]:
    if not record:
        return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")

    regular_hours = Decimal(str(record.regular_hours or 0))
    overtime_hours = Decimal(str(record.overtime_hours or 0))
    worked_hours = Decimal(str(record.working_hours or 0))

    if record.check_in and record.check_out and regular_hours <= 0:
        today = record.date
        policy_start = (
            datetime.combine(today, time(9, 0))
            if record.check_in.time() > AttendanceService.LATE_THRESHOLD
            else datetime.combine(today, time(8, 0))
        )
        effective_start = max(record.check_in.replace(tzinfo=None), policy_start)
        regular_hours = _compute_working_hours(
            effective_start,
            min(
                record.check_out.replace(tzinfo=None),
                datetime.combine(today, AttendanceService.REGULAR_END),
            ),
        )

    if worked_hours <= 0:
        worked_hours = regular_hours + overtime_hours

    return worked_hours, regular_hours, overtime_hours

def _format_minutes_as_hours_minutes(total_minutes: int) -> str:
    hours, minutes = divmod(total_minutes, 60)
    if hours > 0 and minutes > 0:
        return f"{hours} giờ {minutes} phút"
    if hours > 0:
        return f"{hours} giờ"
    return f"{minutes} phút"

def _status_badge(status: str) -> tuple[str, str]:
    mapping = {
        "pending": ("⏳", "Chờ Manager duyệt"),
        "pending_hr": ("🧾", "Chờ HR duyệt"),
        "pending_admin": ("🛡️", "Chờ Admin duyệt"),
        "approved": ("✅", "Đã duyệt"),
        "rejected": ("❌", "Từ chối"),
        "supplement_requested": ("📎", "Yêu cầu bổ sung"),
        "cancelled": ("🚫", "Hủy đơn"),
        "complaint": ("📣", "Khiếu nại"),
    }
    return mapping.get(status, ("ℹ️", status))

def _labelize_enum(value: str | None) -> str:
    if not value:
        return "Chưa cập nhật"
    labels = {
        "probation": "Thử việc",
        "permanent": "Chính thức",
        "intern": "Thực tập",
        "contract": "Hợp đồng",
        "active": "Đang làm việc",
        "on_leave": "Tạm nghỉ",
        "resigned": "Đã nghỉ việc",
        "male": "Nam",
        "female": "Nữ",
        "other": "Khác",
    }
    return labels.get(value, value)

LEAVE_TYPE_CONFIGS = [
    {"name": "Nghỉ phép năm", "is_paid": True},
    {"name": "Nghỉ ốm", "is_paid": True},
    {"name": "Nghỉ không lương", "is_paid": False},
    {"name": "Nghỉ lễ", "is_paid": True},
    {"name": "Nghỉ việc riêng có lương", "is_paid": True},
    {"name": "Nghỉ thai sản", "is_paid": True},
]

PERSONAL_SUBTYPES = {
    "PERSONAL_MARRIAGE": "Kết hôn",
    "PERSONAL_FUNERAL": "Tang lễ",
}

ALLOWED_FUNERAL_RELATIONS = {"cha", "mẹ", "vợ", "chồng", "con"}


def _ensure_leave_types() -> list[LeaveType]:
    changed = False
    for cfg in LEAVE_TYPE_CONFIGS:
        existed = LeaveType.query.filter_by(name=cfg["name"]).first()
        if existed:
            if existed.is_paid != cfg["is_paid"]:
                existed.is_paid = cfg["is_paid"]
                changed = True
            continue
        db.session.add(LeaveType(name=cfg["name"], is_paid=cfg["is_paid"]))
        changed = True
    if changed:
        db.session.commit()
    return LeaveType.query.order_by(LeaveType.id.asc()).all()


def _save_leave_document(file_storage, category: str) -> str:
    if not file_storage or not file_storage.filename:
        raise ValidationError("Vui lòng tải lên giấy tờ đính kèm.")

    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    allowed_ext = {"pdf", "png", "jpg", "jpeg"}
    if ext not in allowed_ext:
        raise ValidationError("Chỉ chấp nhận file PDF hoặc ảnh (png/jpg/jpeg).")

    folder = os.path.join("app", "static", "uploads", "leave", category)
    os.makedirs(folder, exist_ok=True)
    filename = secure_filename(file_storage.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    abs_path = os.path.join(folder, unique_name)
    file_storage.save(abs_path)
    return f"/static/uploads/leave/{category}/{unique_name}"

@employee_bp.route("/dashboard")
def dashboard():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    if not employee:
        flash("Không tìm thấy hồ sơ nhân viên.", "danger")
        return _redirect_when_missing_employee()

    user = _current_user()
    now = parse_simulated_time({})
    attendance = EmployeeDashboardService.get_today_attendance(employee.id, now.date())
    attendance_history = (
        Attendance.query.filter_by(employee_id=employee.id)
        .order_by(Attendance.date.desc())
        .limit(45)
        .all()
    )
    leave_balance = EmployeeDashboardService.get_leave_balance(employee.id, date.today().year)
    latest_salary = EmployeeDashboardService.get_latest_salary(employee.id)
    notifications = EmployeeDashboardService.get_notifications(user.id if user else 0)
    today_holiday = _get_holiday_for_date(now.date())
    holiday_lookup = _get_holiday_lookup()
    return render_template(
        "employee/dashboard.html",
        employee=employee,
        attendance=attendance,
        leave_balance=leave_balance,
        latest_salary=latest_salary,
        notifications=notifications,
        now=now,
        attendance_history=attendance_history,
        today_holiday=today_holiday,
        holiday_lookup=holiday_lookup,
    )


@employee_bp.route("/profile", methods=["GET", "POST"])
def profile():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    user = _current_user()

    if not employee or not user:
        flash("Không tìm thấy hồ sơ nhân viên.", "danger")
        return _redirect_when_missing_employee()

    action = request.form.get("action")

    if request.method == "POST" and action == "update_profile":
        # Cập nhật thông tin cơ bản
        employee.full_name = request.form.get("full_name", employee.full_name).strip()
        employee.phone = request.form.get("phone", employee.phone).strip()
        user.email = request.form.get("email", user.email).strip()

        # 🔥 THÊM CÁC DÒNG NÀY ĐỂ LƯU ĐỊA CHỈ PHÂN CẤP
        # Lưu mã code của Tỉnh/Huyện/Xã
        employee.province_id = request.form.get("province")
        employee.district_id = request.form.get("district")
        employee.ward_id = request.form.get("ward")
        # Lưu địa chỉ chi tiết (số nhà, tên đường)
        employee.address_detail = request.form.get("address_detail", "").strip()

        db.session.commit()
        flash("✅ Đã cập nhật thông tin cá nhân.", "success")
        return redirect(url_for("employee.profile"))

    if request.method == "POST" and action == "change_password":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not check_password_hash(user.password_hash, current_password):
            flash("❌ Mật khẩu hiện tại không đúng.", "danger")
            return redirect(url_for("employee.profile"))

        if len(new_password) < 8:
            flash("❌ Mật khẩu mới cần tối thiểu 8 ký tự.", "danger")
            return redirect(url_for("employee.profile"))

        if new_password != confirm_password:
            flash("❌ Xác nhận mật khẩu không khớp.", "danger")
            return redirect(url_for("employee.profile"))

        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("✅ Đổi mật khẩu thành công.", "success")
        return redirect(url_for("employee.profile"))

    notifications = EmployeeDashboardService.get_notifications(user.id, limit=20)
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
        complaints=complaints,
    )

@employee_bp.route("/staff-profile")
def staff_profile():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    user = _current_user()
    if not employee or not user:
        flash("Không tìm thấy hồ sơ nhân viên.", "danger")
        return _redirect_when_missing_employee()

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
        history_events.append(
            {
                "time": employee.hire_date,
                "event": "🎉 Gia nhập công ty",
                "detail": f"Vị trí: {employee.position.job_title if employee.position else 'Chưa có'}",
                "source": "Employee + Position",
            }
        )
    if user.created_at:
        history_events.append(
            {
                "time": user.created_at,
                "event": "🔐 Tạo tài khoản",
                "detail": f"Username: {user.username}",
                "source": "User",
            }
        )
    if employee.updated_at:
        history_events.append(
            {
                "time": employee.updated_at,
                "event": "🔄 Cập nhật thông tin",
                "detail": "Sửa đổi hồ sơ nhân sự",
                "source": "Employee.updated_at",
            }
        )
    if latest_contract and latest_contract.start_date:
        history_events.append(
            {
                "time": latest_contract.start_date,
                "event": "📝 Ký hợp đồng",
                "detail": f"Mã HĐ: {latest_contract.contract_code}",
                "source": "Contracts",
            }
        )
    for log in history_logs:
        history_events.append(
            {
                "time": log.created_at,
                "event": f"📌 {log.action}",
                "detail": log.description or "Không có mô tả",
                "source": f"{log.entity_type or 'HistoryLog'}",
            }
        )
    from datetime import timezone

    def _event_sort_key(item):
        event_time = item.get("time")

        # 1. Convert về datetime
        if isinstance(event_time, datetime):
            dt = event_time
        elif isinstance(event_time, date):
            dt = datetime.combine(event_time, time.min)
        else:
            return datetime.min.replace(tzinfo=timezone.utc)

        # 2. FIX QUAN TRỌNG: normalize timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        return dt

    history_events = sorted(history_events, key=_event_sort_key, reverse=True)[:20]

    return render_template(
        "employee/staff_profile.html",
        employee=employee,
        user=user,
        latest_contract=latest_contract,
        history_events=history_events,
        enum_labelize=_labelize_enum,
    )
@employee_bp.route("/update-profile", methods=["POST"])
def update_profile_ajax():
    guard = _ensure_login()
    if guard:
        return jsonify({"error": "Unauthorized"}), 401

    employee = _current_employee()
    user = _current_user()
    
    # Lấy dữ liệu JSON từ request.get_json() thay vì request.form
    data = request.get_json()
    if not data:
        return jsonify({"error": "Không có dữ liệu"}), 400

    try:

        dob = data.get("dob")
        if dob:
            employee.dob = datetime.strptime(dob, "%Y-%m-%d").date()

        gender = data.get("gender")
        if gender in {"male", "female", "other"}:
            employee.gender = gender

        # Cập nhật thông tin
        employee.full_name = data.get("full_name", employee.full_name).strip()
        employee.phone = data.get("phone", employee.phone).strip()
        
        # Lưu mã địa chỉ
        employee.province_id = data.get("province")
        employee.district_id = data.get("district")
        employee.ward_id = data.get("ward")
        employee.address_detail = data.get("address_detail", "").strip()

        db.session.commit()
        return jsonify({"message": "Cập nhật thành công!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
@employee_bp.route("/attendance")
def attendance():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    now = parse_simulated_time({})
    latest_attendance = (
        Attendance.query.filter_by(employee_id=employee.id).order_by(Attendance.date.desc()).first()
        if employee
        else None
    )
    if latest_attendance and latest_attendance.date > now.date():
        fallback_time = (
            latest_attendance.check_out.time()
            if latest_attendance.check_out
            else (
                latest_attendance.check_in.time()
                if latest_attendance.check_in
                else time(17, 0)
            )
        )
        now = datetime.combine(latest_attendance.date, fallback_time)
        session["simulated_now"] = now.isoformat()
    today = EmployeeDashboardService.get_today_attendance(employee.id, now.date()) if employee else None
    history = (
        Attendance.query.filter_by(employee_id=employee.id).order_by(Attendance.date.desc()).limit(10).all()
        if employee
        else []
    )
    if today:
        _, today.regular_hours, today.overtime_hours = _attendance_metrics(today)
    for record in history:
        _, record.regular_hours, record.overtime_hours = _attendance_metrics(record)
    today_holiday = _get_holiday_for_date(now.date())
    holiday_lookup = _get_holiday_lookup()
    return render_template(
        "employee/attendance.html",
        employee=employee,
        today=today,
        history=history,
        now=now,
        today_holiday=today_holiday,
        holiday_lookup=holiday_lookup,
    )


@employee_bp.route("/attendance/check", methods=["POST"])
def check_in_out():
    # =========================
    # AUTH GUARD
    # =========================
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    if not employee:
        return jsonify({
            "toast": True,
            "type": "error",
            "message": "Không tìm thấy nhân viên"
        }), 404

    if not _is_attendance_required(employee):
        return jsonify({
            "toast": True,
            "type": "info",
            "message": "Vai trò hiện tại không áp dụng chấm công bắt buộc."
        }), 200
    # =========================
    # PARSE REQUEST
    # =========================
    payload = request.get_json(silent=True) or {}

    qr_text = str(payload.get("qr_text") or payload.get("qr_data") or "").strip()
    if not qr_text:
        return jsonify({
            "toast": True,
            "type": "error",
            "message": "Không đọc được dữ liệu QR."
        }), 400

    try:
        current_time = parse_simulated_time(payload)

        # normalize timezone
        if current_time.tzinfo is not None:
            from datetime import timezone
            current_time = current_time.astimezone(timezone.utc)

        session["simulated_now"] = current_time.isoformat()

    except ValueError as e:
        return jsonify({
            "toast": True,
            "type": "error",
            "message": str(e)
        }), 400

    # =========================
    # LOAD ATTENDANCE
    # =========================
    try:
        today = current_time.date()

        attendance = Attendance.query.filter_by(
            employee_id=employee.id,
            date=today
        ).first()

        shift_start = datetime.combine(today, AttendanceService.REGULAR_START)
        late_threshold = datetime.combine(today, AttendanceService.LATE_THRESHOLD)

        # =========================
        # CHECK-IN FLOW
        # =========================
        if not attendance:
            attendance_type = "holiday" if OvertimeService.is_weekend(today) else "normal"
            attendance = Attendance(
                employee_id=employee.id,
                date=today,
                check_in=current_time,
                attendance_type=attendance_type
            )

            db.session.add(attendance)
            db.session.commit()

            late_minutes = 0
            early_minutes = 0
            if current_time < shift_start:
                early_minutes = int(
                    (shift_start - current_time).total_seconds() // 60
                )
            if current_time > late_threshold:
                late_minutes = int(
                    (current_time - late_threshold).total_seconds() // 60
                )

            msg = f"Check-in lúc {current_time.strftime('%H:%M:%S')}"
            if early_minutes > 0:
                msg += f" • Bạn đến sớm {early_minutes} phút, chúc bạn 1 ngày làm việc hiệu quả"
            elif late_minutes > 0:
                msg += f" • Muộn {_format_minutes_as_hours_minutes(late_minutes)}"

            return jsonify({
                "toast": True,
                "type": "warning" if late_minutes > 0 else "success",
                "action": "check_in",
                "message": msg
            })

        # =========================
        # CHECK-OUT FLOW
        # =========================
        if attendance.check_in and not attendance.check_out:
            check_in_time = attendance.check_in
            if check_in_time.tzinfo is not None:
                check_in_time = check_in_time.replace(tzinfo=None)
            if current_time < check_in_time:
                return jsonify({
                    "toast": True,
                    "type": "error",
                    "message": "Thời gian check-out không hợp lệ"
                }), 400
            overtime_confirmed = bool(payload.get("overtime_confirmed"))
            overtime_rejected = bool(payload.get("overtime_rejected"))
            should_suggest_ot = OvertimeService.should_suggest_overtime(current_time, today)

            if should_suggest_ot and not overtime_confirmed and not overtime_rejected:
                return jsonify({
                    "toast": False,
                    "type": "warning",
                    "action": "confirm_overtime",
                    "message": "Hiện tại đã ngoài giờ làm việc / ngày nghỉ. Bạn có muốn đăng ký tăng ca không?",
                    "attendance_state": "holiday" if OvertimeService.is_weekend(today) else "overtime",
                })
            attendance.check_out = current_time

            # =========================
            # EFFECTIVE START (late rule)
            # =========================
            policy_start = (
                datetime.combine(today, time(9, 0))
                if check_in_time > late_threshold
                else datetime.combine(today, time(8, 0))
            )
            effective_start = max(check_in_time, policy_start)
            # =========================
            # WORK HOURS CALC
            # =========================
            regular_hours = _compute_working_hours(
                effective_start,
                min(attendance.check_out, datetime.combine(today, AttendanceService.REGULAR_END))
            )
            overtime_start_raw = payload.get("overtime_start")
            overtime_start_dt = current_time
            if overtime_start_raw:
                try:
                    overtime_start_dt = datetime.fromisoformat(str(overtime_start_raw).replace("Z", "+00:00"))
                    if overtime_start_dt.tzinfo is not None:
                        overtime_start_dt = overtime_start_dt.replace(tzinfo=None)
                except ValueError:
                    overtime_start_dt = current_time

            overtime_hours = Decimal("0.00")
            if overtime_confirmed:
                overtime_hours = OvertimeService.calculate_overtime(overtime_start_dt, attendance.check_out)

            attendance.regular_hours = regular_hours
            attendance.overtime_hours = overtime_hours
            attendance.working_hours = regular_hours + overtime_hours
            if OvertimeService.is_weekend(today):
                attendance.attendance_type = "holiday"
            elif overtime_hours > 0:
                attendance.attendance_type = "overtime"
            else:
                attendance.attendance_type = "normal"
            db.session.commit()

            # =========================
            # EARLY LEAVE CHECK
            # =========================
            end_of_day = datetime.combine(today, AttendanceService.REGULAR_END)
            early_minutes = 0

            if current_time < end_of_day:
                early_minutes = int(
                    (end_of_day - current_time).total_seconds() // 60
                )

            msg = f"Check-out lúc {current_time.strftime('%H:%M:%S')}"
            msg += f" • Ca chính: {regular_hours}h"
            if overtime_hours > 0:
                msg += f" • Tăng ca: {overtime_hours}h"

            if early_minutes > 0:
                msg += f" • Về sớm {early_minutes} phút"
            worked_hours, regular_hours, overtime_hours = _attendance_metrics(attendance)
            status_key = "checked_out"
            if overtime_hours > 0:
                status_key = "overtime"
            elif check_in_time > late_threshold:
                status_key = "late"
            elif early_minutes > 0:
                status_key = "early_leave"

            return jsonify({
                "toast": True,
                "type": "warning" if early_minutes > 0 else "success",
                "action": "check_out",
                "message": msg,
                "attendance_state": attendance.attendance_type,
                "worked_hours": str(worked_hours),
                "regular_hours": str(regular_hours),
                "overtime_hours": str(overtime_hours),
                "check_in": attendance.check_in.isoformat() if attendance.check_in else None,
                "check_out": attendance.check_out.isoformat() if attendance.check_out else None,
                "status_key": status_key,
            })

        # =========================
        # ALREADY DONE
        # =========================
        return jsonify({
            "toast": True,
            "type": "info",
            "action": "done",
            "message": "Bạn đã hoàn thành chấm công hôm nay"
        })

    except Exception as exc:
        db.session.rollback()
        return jsonify({
            "toast": True,
            "type": "error",
            "message": f"Lỗi hệ thống: {str(exc)}"
        }), 500

@employee_bp.route("/attendance/delete", methods=["DELETE"])
def delete_attendance_record():
    guard = _ensure_login()
    if guard:
        return jsonify({
            "status": "error",
            "message": "Bạn chưa đăng nhập",
            "toast": True
        }), 401

    employee = _current_employee()
    if not employee:
        return jsonify({
            "status": "error",
            "message": "Không tìm thấy nhân viên",
            "toast": True
        }), 404

    payload = request.get_json(silent=True) or {}
    date_str = payload.get("date")
    if not date_str:
        return jsonify({
            "status": "error",
            "message": "Thiếu ngày cần xóa",
            "toast": True
        }), 400

    try:
        new_last_date = AttendanceService.delete_attendance(employee.id, date_str)
        rollback_date = (
            new_last_date.isoformat()
            if new_last_date
            else datetime.now().date().isoformat()
        )

        return jsonify({
            "status": "success",
            "message": f"Đã xóa chấm công ngày {date_str}",
            "toast": True,
            "rollback_date": rollback_date
        })
    except ValidationError as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "toast": True
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Lỗi hệ thống: {str(e)}",
            "toast": True
        }), 500

@employee_bp.route("/leave", methods=["GET", "POST"])
def leave_request():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    if not employee:
        flash("Không tìm thấy hồ sơ nhân viên", "danger")
        return redirect(url_for("employee.dashboard"))

    now = parse_simulated_time({})
    usage = EmployeeDashboardService.get_leave_balance(employee.id, now.year)
    leave_types = _ensure_leave_types()
    leave_type_by_id = {t.id: t for t in leave_types}
    annual_type = next((t for t in leave_types if t.name == "Nghỉ phép năm"), None)
    holiday_type = next((t for t in leave_types if t.name == "Nghỉ lễ"), None)

    if request.method == "POST":
        leave_type_id = request.form.get("leave_type_id", type=int)
        from_date = request.form.get("from_date")
        to_date = request.form.get("to_date")
        reason = request.form.get("reason", "").strip()
        personal_subtype = request.form.get("personal_subtype", "").strip()
        relation = request.form.get("relation", "").strip().lower()
        leave_document = request.files.get("leave_document")

        selected_type = leave_type_by_id.get(leave_type_id)
        if not selected_type:
            flash("❌ Loại nghỉ không hợp lệ.", "danger")
            return redirect(url_for("employee.leave_request"))
        try:
            from_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
            to_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            flash("❌ Ngày nghỉ không hợp lệ.", "danger")
            return redirect(url_for("employee.leave_request"))

        if to_obj < from_obj:
            flash("❌ Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu.", "danger")
            return redirect(url_for("employee.leave_request"))

        requested_days = (to_obj - from_obj).days + 1
        if selected_type.name == "Nghỉ lễ":
            flash("❌ Nghỉ lễ do hệ thống tự động xử lý, không cần gửi đơn.", "danger")
            return redirect(url_for("employee.leave_request"))
        if selected_type.name == "Nghỉ phép năm":
            remaining_days = Decimal(str(usage.remaining_days)) if usage else Decimal("0")
            if remaining_days <= 0:
                flash("❌ Bạn đã dùng hết phép năm.", "danger")
                return redirect(url_for("employee.leave_request"))
            if remaining_days < Decimal(requested_days):
                flash("❌ Bạn không đủ ngày phép còn lại.", "danger")
                return redirect(url_for("employee.leave_request"))

        document_url = None
        subtype = None
        normalized_relation = None

        if selected_type.name == "Nghỉ ốm":
            try:
                document_url = _save_leave_document(leave_document, "sick")
            except ValidationError as e:
                flash(f"❌ {str(e)}", "danger")
                return redirect(url_for("employee.leave_request"))

        if selected_type.name == "Nghỉ việc riêng có lương":
            if personal_subtype not in PERSONAL_SUBTYPES:
                flash("❌ Vui lòng chọn lý do nghỉ việc riêng (kết hôn/tang lễ).", "danger")
                return redirect(url_for("employee.leave_request"))
            if requested_days > 3:
                flash("❌ Nghỉ việc riêng có lương chỉ tối đa 3 ngày.", "danger")
                return redirect(url_for("employee.leave_request"))
            subtype = personal_subtype

            if personal_subtype == "PERSONAL_FUNERAL":
                if relation not in ALLOWED_FUNERAL_RELATIONS:
                    flash("❌ Tang lễ chỉ áp dụng cho cha/mẹ/vợ/chồng/con.", "danger")
                    return redirect(url_for("employee.leave_request"))
                normalized_relation = relation

            try:
                document_url = _save_leave_document(leave_document, "personal")
            except ValidationError as e:
                flash(f"❌ {str(e)}", "danger")
                return redirect(url_for("employee.leave_request"))

        if selected_type.name == "Nghỉ thai sản":
            if (employee.gender or "").lower() != "female":
                flash("❌ Nghỉ thai sản chỉ áp dụng cho nhân viên nữ.", "danger")
                return redirect(url_for("employee.leave_request"))
            if requested_days > 180:
                flash("❌ Nghỉ thai sản tối đa 180 ngày.", "danger")
                return redirect(url_for("employee.leave_request"))

            overlap = (
                LeaveRequest.query.filter(
                    LeaveRequest.employee_id == employee.id,
                    LeaveRequest.is_deleted.is_(False),
                    LeaveRequest.status.in_(["pending", "approved"]),
                    LeaveRequest.from_date <= to_obj,
                    LeaveRequest.to_date >= from_obj,
                )
                .first()
            )
            if overlap:
                flash("❌ Khoảng thời gian nghỉ thai sản không được trùng với đơn nghỉ khác.", "danger")
                return redirect(url_for("employee.leave_request"))

            try:
                document_url = _save_leave_document(leave_document, "maternity")
            except ValidationError as e:
                flash(f"❌ {str(e)}", "danger")
                return redirect(url_for("employee.leave_request"))
        req = LeaveRequest(
            employee_id=employee.id,
            leave_type_id=leave_type_id,
            from_date=from_obj,
            to_date=to_obj,
            reason=reason,
            document_url=document_url,
            subtype=subtype,
            relation=normalized_relation,
            approved_by=employee.manager_id,
        )
        db.session.add(req)


        if employee.manager and employee.manager.user_id:
            db.session.add(
                Notification(
                    user_id=employee.manager.user_id,
                    title="Đơn nghỉ phép mới cần duyệt",
                    content=f"{employee.full_name} gửi đơn nghỉ từ {from_obj.strftime('%d/%m/%Y')} đến {to_obj.strftime('%d/%m/%Y')}.",
                    type="leave",
                    link=url_for("employee.leave_request"),
                )
            )


        db.session.commit()
        flash("✅ Đã gửi đơn nghỉ phép thành công.", "success")
        return redirect(url_for("employee.leave_request"))

    requests = LeaveRequest.query.filter_by(employee_id=employee.id).order_by(LeaveRequest.created_at.desc()).all()    
    today_holiday = _get_holiday_for_date(now.date())

    return render_template(
        "employee/leave.html",
        employee=employee,
        leave_types=leave_types,
        requests=requests,
        usage=usage,
        current_year=now.year,
        now=now,
        annual_type_id=annual_type.id if annual_type else None,
        holiday_type_id=holiday_type.id if holiday_type else None,
        personal_subtypes=PERSONAL_SUBTYPES,
        today_holiday=today_holiday,
        allowed_funeral_relations=sorted(ALLOWED_FUNERAL_RELATIONS),
        status_badge=_status_badge,
    )


@employee_bp.route("/payslip", methods=["GET"])
def payslip():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    if not employee:
        return redirect(url_for("employee.dashboard"))

    return render_template("employee/payslip.html", current_year=date.today().year)

@employee_bp.route("/payslip/api/history", methods=["GET"])
def employee_payroll_history_api():
    guard = _ensure_login()
    if guard:
        return guard
    filters = {
        "year": request.args.get("year", type=int),
        "status": request.args.get("status", type=str),
        "has_complaint": request.args.get("has_complaint", type=str),
        "paid_state": request.args.get("paid_state", type=str),
    }
    try:
        return jsonify(EmployeePayrollService.payroll_history(session.get("user_id"), filters))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@employee_bp.route("/payslip/api/<int:salary_id>", methods=["GET"])
def employee_payroll_detail_api(salary_id: int):
    guard = _ensure_login()
    if guard:
        return guard
    try:
        return jsonify(EmployeePayrollService.payroll_detail(session.get("user_id"), salary_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@employee_bp.route("/payslip/api/<int:salary_id>/pdf", methods=["GET"])
def employee_payroll_pdf_api(salary_id: int):
    guard = _ensure_login()
    if guard:
        return guard
    try:
        filename, content = EmployeePayrollService.payslip_pdf(session.get("user_id"), salary_id)
        return Response(content, mimetype="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@employee_bp.route("/payslip/api/<int:salary_id>/complaint", methods=["POST"])
def employee_payroll_complaint_api(salary_id: int):
    guard = _ensure_login()
    if guard:
        return guard
    try:
        return jsonify(
            EmployeePayrollService.submit_complaint(
                session.get("user_id"),
                salary_id,
                request.form.get("issue_type", "other"),
                request.form.get("description", ""),
                request.files.get("attachment"),
            )
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@employee_bp.route("/payslip/api/complaints", methods=["GET"])
def employee_payroll_complaints_api():
    guard = _ensure_login()
    if guard:
        return guard
    try:
        return jsonify({"items": EmployeePayrollService.salary_complaints(session.get("user_id"))})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@employee_bp.route("/payslip/api/complaints/<int:complaint_id>/close", methods=["POST"])
def employee_payroll_close_complaint_api(complaint_id: int):
    guard = _ensure_login()
    if guard:
        return guard
    try:
        return jsonify(EmployeePayrollService.close_salary_complaint(session.get("user_id"), complaint_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@employee_bp.route("/notifications")
def notifications():
    guard = _ensure_login()
    if guard:
        return guard

    user = _current_user()
    employee = _current_employee()
    items = EmployeeDashboardService.get_notifications(user.id if user else 0, limit=50)

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
    )

@employee_bp.route("/notifications/<int:noti_id>/read", methods=["POST"])
def mark_notification_read(noti_id: int):
    guard = _ensure_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    noti = Notification.query.filter_by(id=noti_id, user_id=user.id).first()
    if not noti:
        return jsonify({"error": "Notification not found"}), 404

    noti.is_read = True
    db.session.commit()
    return jsonify({"success": True, "id": noti.id, "is_read": noti.is_read})

@employee_bp.route("/notifications/<int:noti_id>/feedback", methods=["POST"])
def send_notification_feedback(noti_id: int):
    guard = _ensure_login()
    if guard:
        return guard

    user = _current_user()
    employee = _current_employee()
    if not user or not employee:
        return jsonify({"error": "Unauthorized"}), 401

    noti = Notification.query.filter_by(id=noti_id, user_id=user.id).first()
    if not noti:
        return jsonify({"error": "Notification not found"}), 404

    issue_type = request.form.get("issue_type", "other").strip() or "other"
    detail = request.form.get("description", "").strip()
    try:
        result = EmployeeESSService.submit_notification_complaint(
            user=user,
            employee=employee,
            noti_id=noti.id,
            issue_type=issue_type,
            description=detail,
            attachment=request.files.get("attachment"),
        )
        return jsonify({"success": True, **result})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@employee_bp.route("/notifications/<int:noti_id>/detail", methods=["GET"])
def notification_detail_api(noti_id: int):
    guard = _ensure_login()
    if guard:
        return guard
    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        return jsonify(EmployeeESSService.notification_detail(user.id, noti_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@employee_bp.route("/complaints/<int:complaint_id>/close", methods=["POST"])
def close_complaint_api(complaint_id: int):
    guard = _ensure_login()
    if guard:
        return guard
    try:
        return jsonify(EmployeeESSService.close_complaint(session.get("user_id"), complaint_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@employee_bp.route("/resignation/my", methods=["GET"])
def my_resignation_requests():
    employee = _current_employee()
    if not employee:
        return jsonify({"error": "Không tìm thấy hồ sơ nhân viên"}), 404
    rows = (
        ResignationRequest.query.filter_by(employee_id=employee.id)
        .order_by(ResignationRequest.created_at.desc())
        .all()
    )
    return jsonify([row.to_dict() for row in rows])


@employee_bp.route("/resignation", methods=["POST"])
def submit_resignation_request():
    employee = _current_employee()
    if not employee:
        return jsonify({"error": "Không tìm thấy hồ sơ nhân viên"}), 404

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
        return jsonify({"error": "Định dạng ngày không hợp lệ"}), 400

    allowed_reasons = {"transfer", "personal", "health", "study", "other"}
    if reason_category not in allowed_reasons:
        return jsonify({"error": "Lý do nghỉ việc không hợp lệ"}), 400

    attachment_url = None
    file = request.files.get("attachment")
    if file and file.filename:
        filename = secure_filename(file.filename)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in {"pdf", "jpg", "jpeg", "png", "doc", "docx"}:
            return jsonify({"error": "File đính kèm không hợp lệ"}), 400
        folder = os.path.join("app", "static", "uploads", "resignation")
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

    return jsonify({"message": "Đã gửi đơn nghỉ việc, chờ Manager duyệt", "request": request_item.to_dict()})
@employee_bp.route("/profile/dependents", methods=["GET"])
def employee_dependents_api():
    guard = _ensure_login()
    if guard:
        return guard
    try:
        return jsonify(EmployeeESSService.list_dependents(session.get("user_id")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@employee_bp.route("/profile/dependents", methods=["POST"])
def employee_create_dependent_api():
    guard = _ensure_login()
    if guard:
        return guard
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(EmployeeESSService.create_dependent(session.get("user_id"), payload, actor_user_id=session.get("user_id")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@employee_bp.route("/profile/dependents/<int:dependent_id>", methods=["PUT"])
def employee_update_dependent_api(dependent_id: int):
    guard = _ensure_login()
    if guard:
        return guard
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(EmployeeESSService.update_dependent(session.get("user_id"), dependent_id, payload, actor_user_id=session.get("user_id")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@employee_bp.route("/profile/dependents/<int:dependent_id>", methods=["DELETE"])
def employee_delete_dependent_api(dependent_id: int):
    guard = _ensure_login()
    if guard:
        return guard
    try:
        return jsonify(EmployeeESSService.delete_dependent(session.get("user_id"), dependent_id, actor_user_id=session.get("user_id")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@employee_bp.route("/attendance/overtime-request", methods=["POST"])
def submit_overtime_request_api():
    guard = _ensure_login()
    if guard:
        return guard
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(EmployeeESSService.submit_overtime(session.get("user_id"), payload, actor_user_id=session.get("user_id")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@employee_bp.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    results = []
    if q:
        results = Employee.query.filter(Employee.full_name.ilike(f"%{q}%")).limit(20).all()
    return render_template("employee/search.html", q=q, results=results)
@employee_bp.route("/dev-login")
def dev_login():
    session["user_id"] = 1
    return redirect("/employee/dashboard")

@employee_bp.route("/upload-avatar", methods=["POST"])
def upload_avatar():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    if not employee:
        return jsonify({"error": "Không tìm thấy nhân viên"}), 404

    file = request.files.get("avatar")
    if not file:
        return jsonify({"error": "Không có file"}), 400

    filename = secure_filename(file.filename)

    upload_folder = os.path.join("app", "static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)

    # 🔥 QUAN TRỌNG: lưu vào employee, không phải user
    employee.avatar = f"/static/uploads/{filename}"
    db.session.commit()

    return jsonify({
        "message": "Upload thành công",
        "url": employee.avatar
    })