from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from flask import flash, jsonify, redirect, render_template, request, session, url_for

from app.extensions.db import db
from app.models import Attendance, Employee, EmployeeLeaveUsage, LeaveRequest, LeaveType, Notification, Salary, SystemSetting, User
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


class DashboardService:
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


def _compute_working_hours(checkin: time, checkout: time) -> Decimal:
    ci = datetime.combine(date.today(), checkin)
    co = datetime.combine(date.today(), checkout)
    total = co - ci
    total_hours = Decimal(total.total_seconds() / 3600).quantize(Decimal("0.01"))

    lunch_start = time(12, 0)
    lunch_end = time(13, 0)
    if checkin <= lunch_start and checkout >= lunch_end:
        total_hours -= Decimal("1.00")
    return max(total_hours, Decimal("0"))


@employee_bp.route("/dashboard")
def dashboard():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    if not employee:
        return render_template("employee/dashboard.html", employee=None)

    user = _current_user()
    attendance = DashboardService.get_today_attendance(employee.id)
    leave_balance = DashboardService.get_leave_balance(employee.id, date.today().year)
    latest_salary = DashboardService.get_latest_salary(employee.id)
    notifications = DashboardService.get_notifications(user.id if user else 0)

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

    if request.method == "POST" and employee:
        employee.full_name = request.form.get("full_name", employee.full_name)
        employee.phone = request.form.get("phone", employee.phone)
        employee.address = request.form.get("address", employee.address)
        if user:
            user.email = request.form.get("email", user.email)
        db.session.commit()
        flash("Đã cập nhật thông tin cá nhân.", "success")
        return redirect(url_for("employee.profile"))

    notifications = DashboardService.get_notifications(user.id if user else 0, limit=20)
    return render_template("employee/profile.html", employee=employee, user=user, notifications=notifications)


@employee_bp.route("/attendance")
def attendance():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    today = DashboardService.get_today_attendance(employee.id) if employee else None
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

    current_time = datetime.now().time().replace(microsecond=0)
    today = date.today()
    attendance = Attendance.query.filter_by(employee_id=employee.id, date=today).first()

    if not attendance:
        attendance = Attendance(employee_id=employee.id, date=today, check_in=current_time)
        db.session.add(attendance)
        db.session.commit()
        return jsonify({"status": "check_in", "check_in": current_time.strftime("%H:%M:%S")})

    if attendance.check_in and not attendance.check_out:
        attendance.check_out = current_time
        attendance.working_hours = _compute_working_hours(attendance.check_in, attendance.check_out)
        db.session.commit()
        return jsonify(
            {
                "status": "check_out",
                "check_out": current_time.strftime("%H:%M:%S"),
                "working_hours": float(attendance.working_hours or 0),
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
        flash("Không tìm thấy hồ sơ nhân viên", "error")
        return redirect(url_for("employee.dashboard"))

    if request.method == "POST":
        leave_type_id = request.form.get("leave_type_id", type=int)
        from_date = request.form.get("from_date")
        to_date = request.form.get("to_date")
        reason = request.form.get("reason", "")

        req = LeaveRequest(
            employee_id=employee.id,
            leave_type_id=leave_type_id,
            from_date=datetime.strptime(from_date, "%Y-%m-%d").date(),
            to_date=datetime.strptime(to_date, "%Y-%m-%d").date(),
            reason=reason,
            approved_by=employee.manager_id,
        )
        db.session.add(req)
        db.session.commit()
        flash("Đã gửi đơn nghỉ phép thành công.", "success")
        return redirect(url_for("employee.leave_request"))

    leave_types = LeaveType.query.order_by(LeaveType.name.asc()).all()
    requests = LeaveRequest.query.filter_by(employee_id=employee.id).order_by(LeaveRequest.created_at.desc()).all()
    usage = DashboardService.get_leave_balance(employee.id, date.today().year)
    return render_template(
        "employee/leave.html",
        employee=employee,
        leave_types=leave_types,
        requests=requests,
        usage=usage,
    )


@employee_bp.route("/payslip")
def payslip():
    guard = _ensure_login()
    if guard:
        return guard

    employee = _current_employee()
    if not employee:
        return redirect(url_for("employee.dashboard"))

    year = request.args.get("year", date.today().year, type=int)
    salary_records = (
        Salary.query.filter_by(employee_id=employee.id, year=year)
        .order_by(Salary.month.desc())
        .all()
    )
    return render_template("employee/payslip.html", employee=employee, salary_records=salary_records, year=year)


@employee_bp.route("/notifications")
def notifications():
    guard = _ensure_login()
    if guard:
        return guard

    user = _current_user()
    items = DashboardService.get_notifications(user.id if user else 0, limit=50)
    return render_template("employee/notifications.html", notifications=items)


@employee_bp.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    results = []
    if q:
        results = Employee.query.filter(Employee.full_name.ilike(f"%{q}%")).limit(20).all()
    return render_template("employee/search.html", q=q, results=results)