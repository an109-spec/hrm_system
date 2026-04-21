from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
import os

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from app.extensions.db import db
from app.models import (
    Attendance,
    Complaint,
    Employee,
    EmployeeLeaveUsage,
    LeaveRequest,
    LeaveType,
    Notification,
    Salary,
    User,
)
from . import employee_bp


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
        return Employee.query.filter_by(user_id=user.id).first()
    return Employee.query.order_by(Employee.id.asc()).first()


def _ensure_login():
    if not session.get("user_id"):
        return redirect(url_for("auth.login", next=request.url))
    return None


class EmployeeDashboardService:
    @staticmethod
    def get_today_attendance(employee_id: int):
        return Attendance.query.filter_by(employee_id=employee_id, date=date.today()).first()

    @staticmethod
    def get_leave_balance(employee_id: int, current_year: int):
        usage = EmployeeLeaveUsage.query.filter_by(employee_id=employee_id, year=current_year).first()
        if usage:
            usage.update_balance()
            return usage
        return None

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

    lunch_start = datetime.combine(checkin.date(), time(12, 0))
    lunch_end = datetime.combine(checkin.date(), time(13, 0))
    if checkin <= lunch_start and checkout >= lunch_end:
        total_hours -= Decimal("1.00")
    return max(total_hours, Decimal("0"))

def _status_badge(status: str) -> tuple[str, str]:
    mapping = {
        "pending": ("⏳", "Chờ duyệt"),
        "approved": ("✅", "Đã duyệt"),
        "rejected": ("❌", "Từ chối"),
    }
    return mapping.get(status, ("ℹ️", status))

@employee_bp.route("/dashboard")
def dashboard():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    if not employee:
        return render_template("employee/dashboard.html", employee=None)

    user = _current_user()
    attendance = EmployeeDashboardService.get_today_attendance(employee.id)
    leave_balance = EmployeeDashboardService.get_leave_balance(employee.id, date.today().year)
    latest_salary = EmployeeDashboardService.get_latest_salary(employee.id)
    notifications = EmployeeDashboardService.get_notifications(user.id if user else 0)

    return render_template(
        "employee/dashboard.html",
        employee=employee,
        attendance=attendance,
        leave_balance=leave_balance,
        latest_salary=latest_salary,
        notifications=notifications,
        now=datetime.now(),
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
        return redirect(url_for("employee.dashboard"))

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

    if request.method == "POST" and action == "notification_settings":
        flash("✅ Đã lưu cấu hình nhận tin. (Bản demo UI)", "success")
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
    today = EmployeeDashboardService.get_today_attendance(employee.id) if employee else None
    history = (
        Attendance.query.filter_by(employee_id=employee.id).order_by(Attendance.date.desc()).limit(10).all()
        if employee
        else []
    )
    return render_template("employee/attendance.html", employee=employee, today=today, history=history, now=datetime.now())


@employee_bp.route("/attendance/check", methods=["POST"])
def check_in_out():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    if not employee:
        return jsonify({"error": "Không tìm thấy nhân viên"}), 404
    payload = request.get_json(silent=True) or {}
    qr_text = str(payload.get("qr_text", "")).strip()
    simulated_now = payload.get("simulated_now")

    if not qr_text:
        return jsonify({"error": "Không đọc được dữ liệu QR hợp lệ."}), 400
    current_time = datetime.now().replace(microsecond=0)
    if simulated_now:
        try:
            current_time = datetime.fromisoformat(simulated_now)
        except ValueError:
            return jsonify({"error": "Thời gian mô phỏng không hợp lệ."}), 400

    today = current_time.date()
    attendance = Attendance.query.filter_by(employee_id=employee.id, date=today).first()
    shift_start = datetime.combine(today, time(8, 0))
    late_threshold = datetime.combine(today, time(8, 10))
    check_in_deadline = datetime.combine(today, time(10, 0))

    if not attendance and (current_time < shift_start or current_time > check_in_deadline):
        return (
            jsonify(
                {
                    "error": "Chỉ được check-in trong khung 08:00 - 10:00.",
                    "window": "08:00-10:00",
                }
            ),
            400,
        )
    if not attendance:
        attendance = Attendance(employee_id=employee.id, date=today, check_in=current_time)
        db.session.add(attendance)
        db.session.commit()
        is_late_over_10 = current_time > late_threshold
        effective_start = datetime.combine(today, time(9, 0)) if is_late_over_10 else shift_start
        return jsonify(
            {
                "status": "check_in",
                "check_in": current_time.strftime("%H:%M:%S"),
                "effective_start": effective_start.strftime("%H:%M"),
                "late_over_10": is_late_over_10,
                "identity_message": "Xác nhận danh tính: Duy An - MSNV: 12345",
                "warning": "Bạn đã muộn hơn 10 phút. Thời gian tính công sẽ bắt đầu từ 09:00"
                if is_late_over_10
                else None,
                "message": "✅ Check-in thành công",
            }
        )

    if attendance.check_in and not attendance.check_out:
        attendance.check_out = current_time

        check_in_dt = attendance.check_in
        if not check_in_dt:
            check_in_dt = current_time

        late_cutoff = datetime.combine(today, time(8, 10))
        effective_start = datetime.combine(today, time(9, 0)) if check_in_dt > late_cutoff else datetime.combine(today, time(8, 0))
        attendance.working_hours = _compute_working_hours(effective_start, attendance.check_out)
        db.session.commit()
        early_checkout = current_time < datetime.combine(today, time(17, 0))
        return jsonify(
            {
                "status": "check_out",
                "check_out": current_time.strftime("%H:%M:%S"),
                "working_hours": float(attendance.working_hours or 0),
                "identity_message": "Xác nhận danh tính: Duy An - MSNV: 12345",
                "early_checkout": early_checkout,
                "message": "✅ Check-out thành công",
            }
        )

    return jsonify({"status": "done", "message": "Bạn đã hoàn thành chấm công hôm nay."})


@employee_bp.route("/leave", methods=["GET", "POST"])
def leave_request():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    if not employee:
        flash("Không tìm thấy hồ sơ nhân viên", "danger")
        return redirect(url_for("employee.dashboard"))

    usage = EmployeeDashboardService.get_leave_balance(employee.id, date.today().year)

    if request.method == "POST":
        leave_type_id = request.form.get("leave_type_id", type=int)
        from_date = request.form.get("from_date")
        to_date = request.form.get("to_date")
        reason = request.form.get("reason", "").strip()

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
        if usage and Decimal(str(usage.remaining_days)) < Decimal(requested_days):
            flash("❌ Bạn không đủ ngày phép còn lại.", "danger")
            return redirect(url_for("employee.leave_request"))

        req = LeaveRequest(
            employee_id=employee.id,
            leave_type_id=leave_type_id,
            from_date=from_obj,
            to_date=to_obj,
            reason=reason,
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

    leave_types = LeaveType.query.order_by(LeaveType.name.asc()).all()
    requests = LeaveRequest.query.filter_by(employee_id=employee.id).order_by(LeaveRequest.created_at.desc()).all()
    return render_template(
        "employee/leave.html",
        employee=employee,
        leave_types=leave_types,
        requests=requests,
        usage=usage,
        status_badge=_status_badge,
    )


@employee_bp.route("/payslip", methods=["GET", "POST"])
def payslip():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    if not employee:
        return redirect(url_for("employee.dashboard"))

    if request.method == "POST":
        salary_id = request.form.get("salary_id", type=int)
        issue_type = request.form.get("issue_type", "other")
        description = request.form.get("description", "").strip()

        if not salary_id or not description:
            flash("❌ Vui lòng điền đầy đủ thông tin khiếu nại.", "danger")
            return redirect(url_for("employee.payslip"))

        complaint = Complaint(
            employee_id=employee.id,
            salary_id=salary_id,
            type=issue_type,
            title=f"Khiếu nại phiếu lương #{salary_id}",
            description=description,
            status="pending",
        )
        db.session.add(complaint)
        db.session.commit()

        flash("✅ Đã gửi báo cáo sai sót phiếu lương.", "success")
        return redirect(url_for("employee.payslip"))

    year = request.args.get("year", date.today().year, type=int)
    salary_records = Salary.query.filter_by(employee_id=employee.id, year=year).order_by(Salary.month.desc()).all()
    disputes = (
        Complaint.query.filter_by(employee_id=employee.id)
        .filter(Complaint.salary_id.isnot(None))
        .order_by(Complaint.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "employee/payslip.html",
        employee=employee,
        salary_records=salary_records,
        year=year,
        disputes=disputes,
    )


@employee_bp.route("/notifications")
def notifications():
    guard = _ensure_login()
    if guard:
        return guard

    user = _current_user()
    items = EmployeeDashboardService.get_notifications(user.id if user else 0, limit=50)
    return render_template("employee/notifications.html", notifications=items)

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