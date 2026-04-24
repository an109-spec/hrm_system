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
from app.modules.attendance.overtime_service import OvertimeService
from app.common.exceptions import ValidationError
from app.modules.attendance.service import AttendanceService
from app.utils.time import parse_simulated_time
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
    def get_today_attendance(employee_id: int, target_date: date | None = None):
        target_date = target_date or date.today()
        return Attendance.query.filter_by(employee_id=employee_id, date=target_date).first()

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

def _format_minutes_as_hours_minutes(total_minutes: int) -> str:
    hours, minutes = divmod(total_minutes, 60)
    if hours > 0 and minutes > 0:
        return f"{hours} giờ {minutes} phút"
    if hours > 0:
        return f"{hours} giờ"
    return f"{minutes} phút"

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

    return render_template(
        "employee/dashboard.html",
        employee=employee,
        attendance=attendance,
        leave_balance=leave_balance,
        latest_salary=latest_salary,
        notifications=notifications,
        now=now,
        attendance_history=attendance_history,
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
    return render_template("employee/attendance.html", employee=employee, today=today, history=history, now = now)


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
            current_time = current_time.replace(tzinfo=None)

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

            return jsonify({
                "toast": True,
                "type": "warning" if early_minutes > 0 else "success",
                "action": "check_out",
                "message": msg,
                "attendance_state": attendance.attendance_type,
                "regular_hours": str(regular_hours),
                "overtime_hours": str(overtime_hours),
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