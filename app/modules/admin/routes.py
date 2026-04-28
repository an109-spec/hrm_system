from __future__ import annotations

from datetime import date, datetime, time, timezone, timedelta
from io import StringIO
import csv
import os
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from flask import jsonify, render_template, request, session, redirect, url_for, Response, flash
from sqlalchemy import cast, func, or_, String
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from app.extensions.db import db
from app.models import (
    Attendance,
    AttendanceStatus,
    Complaint,
    Contract,
    Dependent,
    Department,
    Employee,
    EmployeeAllowance,
    HistoryLog,
    LeaveRequest,
    OvertimeRequest,
    Position,
    Role,
    ResignationRequest,
    Salary,
    SystemSetting,
    User,
)
from app.models.notification import Notification
from app.modules.resignation_service import ResignationService
from app.modules.payroll_policy import PayrollPolicyService
from app.models.complaint import ComplaintMessage
from . import admin_bp
from . import service as admin_service

def _current_user() -> User | None:
    uid = session.get("user_id")
    return User.query.get(uid) if uid else None


def _guard_login():
    if not session.get("user_id"):
        return redirect(url_for("auth.login", next=request.url))
    return None
def _guard_admin_access() -> bool:
    user = _current_user()
    if not user:
        return True
    return (user.role.name.lower() if user.role else "") != "admin"


def _role_name(user: User | None) -> str:
    if not user or not user.role:
        return "Employee"
    return user.role.name


def _permissions_for_role(role: str) -> list[str]:
    map_permissions = {
        "Admin": ["*"],
        "HR": ["employee:view", "employee:update", "department:view", "position:view", "attendance:admin", "salary:admin"],
        "Manager": ["employee:view_team", "attendance:view"],
        "Employee": ["profile:view"],
    }
    return map_permissions.get(role, ["profile:view"])


def _to_float(v):
    return float(v or 0)
def _employee_code(employee: Employee | None) -> str:
    if not employee:
        return "N/A"
    return f"EMP{employee.id:04d}"


def _setting_key(user_id: int, field: str) -> str:
    return f"admin_profile:{user_id}:{field}"


def _get_profile_extras(user_id: int) -> dict[str, str]:
    fields = ["personal_email", "marital_status", "emergency_contact_name", "emergency_contact_phone"]
    mapping = {}
    for field in fields:
        row = SystemSetting.query.filter_by(key=_setting_key(user_id, field)).first()
        mapping[field] = row.value if row else ""
    return mapping


def _save_profile_extra(user_id: int, field: str, value: str) -> None:
    key = _setting_key(user_id, field)
    row = SystemSetting.query.filter_by(key=key).first()
    if row:
        row.value = value
    else:
        db.session.add(SystemSetting(key=key, value=value, description="Admin self profile extra field"))


def _write_admin_audit(user: User, employee: Employee, action: str, entity_type: str, entity_id: int | None = None, description: str = "") -> None:
    db.session.add(
        HistoryLog(
            employee_id=employee.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=f"{description} | ip={request.remote_addr or 'N/A'}",
            performed_by=user.id,
        )
    )



# -------------------------
# Admin pages (Jinja)
# -------------------------
@admin_bp.get("/admin/dashboard")
def admin_dashboard_page():
    guard = _guard_login()
    if guard:
        return guard
    return render_template("admin/dashboard.html")


@admin_bp.get("/admin/employees")
def admin_employees_page():
    guard = _guard_login()
    if guard:
        return guard
    return render_template("admin/employees.html")


@admin_bp.get("/admin/departments")
def admin_departments_page():
    guard = _guard_login()
    if guard:
        return guard
    return render_template("admin/departments.html")


@admin_bp.get("/admin/positions")
def admin_positions_page():
    guard = _guard_login()
    if guard:
        return guard
    return render_template("admin/positions.html")


@admin_bp.get("/admin/attendance")
def admin_attendance_page():
    guard = _guard_login()
    if guard:
        return guard
    return render_template("admin/attendance.html")


@admin_bp.get("/admin/salary")
def admin_salary_page():
    guard = _guard_login()
    if guard:
        return guard
    return render_template("admin/salary.html")

@admin_bp.get("/admin/salary-config")
def admin_salary_config_page():
    guard = _guard_login()
    if guard:
        return guard
    return render_template("admin/salary_config.html")

def _current_employee() -> Employee | None:
    user = _current_user()
    if user and user.employee_profile:
        return user.employee_profile
    if user:
        return Employee.query.filter_by(user_id=user.id).first()
    return None


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


@admin_bp.route("/admin/profile", methods=["GET", "POST"])
def admin_profile_page():
    guard = _guard_login()
    if guard:
        return guard

    employee = _current_employee()
    user = _current_user()
    if not employee or not user:
        flash("Không tìm thấy hồ sơ nhân viên.", "danger")
        return redirect(url_for("admin.admin_dashboard_page"))

    action = request.form.get("action")
    if request.method == "POST" and action == "change_password":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
    latest_contract = (
        Contract.query.filter_by(employee_id=employee.id)
        .order_by(Contract.start_date.desc(), Contract.created_at.desc())
        .first()
    )
    latest_salary = (
        Salary.query.filter_by(employee_id=employee.id)
        .order_by(Salary.year.desc(), Salary.month.desc())
        .first()
    )
    total_allowance = (
        db.session.query(func.coalesce(func.sum(EmployeeAllowance.amount), 0))
        .filter(EmployeeAllowance.employee_id == employee.id, EmployeeAllowance.status.is_(True))
        .scalar()
    )
    created_by_log = (
        HistoryLog.query.filter(
            HistoryLog.employee_id == employee.id,
            HistoryLog.action.in_(["CREATE_EMPLOYEE", "Tạo nhân viên", "CREATE_ADMIN"]),
        )
        .order_by(HistoryLog.created_at.asc())
        .first()
    )
    creator = User.query.get(created_by_log.performed_by) if created_by_log and created_by_log.performed_by else None
    audit_logs = (
        HistoryLog.query.filter_by(performed_by=user.id)
        .order_by(HistoryLog.created_at.desc())
        .limit(50)
        .all()
    )
    ip_recent = request.remote_addr or "127.0.0.1"
    session_devices = [
        {
            "device": request.user_agent.string or "Unknown Device",
            "logged_in_at": user.updated_at or user.created_at,
            "ip": ip_recent,
        }
    ]
    extras = _get_profile_extras(user.id)

    return render_template(
        "admin/profile.html",
        employee=employee,
        user=user,
        latest_contract=latest_contract,
        latest_salary=latest_salary,
        total_allowance=float(total_allowance or 0),
        creator=creator,
        session_devices=session_devices,
        audit_logs=audit_logs,
        employee_code=_employee_code(employee),
        extras=extras,
        enum_labelize=_labelize_enum,
    )

@admin_bp.post("/admin/profile/update")
def admin_profile_update_api():
    guard = _guard_login()
    if guard:
        return jsonify({"error": "Unauthorized"}), 401
    employee = _current_employee()
    user = _current_user()
    if not employee or not user:
        return jsonify({"error": "Không tìm thấy hồ sơ admin"}), 404

    payload = request.get_json(silent=True) or {}
    try:
        employee.phone = (payload.get("phone") or "").strip() or None
        employee.address_detail = (payload.get("address_detail") or "").strip() or None
        _save_profile_extra(user.id, "personal_email", (payload.get("personal_email") or "").strip())
        _save_profile_extra(user.id, "marital_status", (payload.get("marital_status") or "").strip())
        _save_profile_extra(user.id, "emergency_contact_name", (payload.get("emergency_contact_name") or "").strip())
        _save_profile_extra(user.id, "emergency_contact_phone", (payload.get("emergency_contact_phone") or "").strip())
        _write_admin_audit(user, employee, "UPDATE_ADMIN_PROFILE", "admin_profile", user.id, "Cập nhật thông tin cá nhân admin")
        db.session.commit()
        return jsonify({"message": "Thông tin cá nhân đã được lưu"})
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 500

@admin_bp.post("/admin/profile/change-password")
def admin_profile_change_password_api():
    guard = _guard_login()
    if guard:
        return jsonify({"error": "Unauthorized"}), 401
    employee = _current_employee()
    user = _current_user()
    if not employee or not user:
        return jsonify({"error": "Không tìm thấy hồ sơ admin"}), 404

    payload = request.get_json(silent=True) or {}
    current_password = payload.get("current_password", "")
    new_password = payload.get("new_password", "")
    confirm_password = payload.get("confirm_password", "")
    if not check_password_hash(user.password_hash, current_password):
        return jsonify({"error": "Mật khẩu hiện tại không đúng"}), 400
    if len(new_password) < 8:
        return jsonify({"error": "Mật khẩu mới cần tối thiểu 8 ký tự"}), 400
    if new_password != confirm_password:
        return jsonify({"error": "Xác nhận mật khẩu không khớp"}), 400

    user.password_hash = generate_password_hash(new_password)
    _write_admin_audit(user, employee, "CHANGE_PASSWORD", "user", user.id, "Admin đổi mật khẩu tài khoản")
    db.session.commit()
    return jsonify({"message": "Mật khẩu đã được cập nhật"})


@admin_bp.post("/admin/profile/upload-avatar")
def admin_profile_upload_avatar_api():
    guard = _guard_login()
    if guard:
        return jsonify({"error": "Unauthorized"}), 401
    employee = _current_employee()
    user = _current_user()
    if not employee or not user:
        return jsonify({"error": "Không tìm thấy hồ sơ admin"}), 404

    file = request.files.get("avatar")
    if not file:
        return jsonify({"error": "Bạn chưa chọn file ảnh"}), 400
    filename = secure_filename(file.filename)
    upload_folder = os.path.join("app", "static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, filename))
    employee.avatar = f"/static/uploads/{filename}"
    _write_admin_audit(user, employee, "UPLOAD_AVATAR", "employee", employee.id, "Admin cập nhật ảnh đại diện")
    db.session.commit()
    return jsonify({"message": "Upload avatar thành công", "url": employee.avatar})


@admin_bp.post("/admin/profile/logout-all-sessions")
def admin_profile_logout_sessions_api():
    guard = _guard_login()
    if guard:
        return jsonify({"error": "Unauthorized"}), 401
    employee = _current_employee()
    user = _current_user()
    if not employee or not user:
        return jsonify({"error": "Không tìm thấy hồ sơ admin"}), 404
    _write_admin_audit(user, employee, "LOGOUT_ALL_SESSIONS", "user", user.id, "Admin đăng xuất mọi phiên đăng nhập")
    db.session.commit()
    session.clear()
    return jsonify({"message": "Đã đăng xuất mọi phiên (bao gồm phiên hiện tại)."})


@admin_bp.get("/admin/staff-profile")
def admin_staff_profile_page():
    guard = _guard_login()
    if guard:
        return guard

    employee = _current_employee()
    user = _current_user()
    if not employee or not user:
        flash("Không tìm thấy hồ sơ nhân viên.", "danger")
        return redirect(url_for("admin.admin_dashboard_page"))

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

    def _event_sort_key(item):
        event_time = item.get("time")
        if isinstance(event_time, datetime):
            dt = event_time
        elif isinstance(event_time, date):
            dt = datetime.combine(event_time, time.min)
        else:
            return datetime.min.replace(tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt

    history_events = sorted(history_events, key=_event_sort_key, reverse=True)[:20]
    return render_template(
        "admin/staff_profile.html",
        employee=employee,
        user=user,
        latest_contract=latest_contract,
        history_events=history_events,
        enum_labelize=_labelize_enum,
    )

# -------------------------
# Auth/me
# -------------------------
@admin_bp.get("/api/auth/me")
def me():
    user = _current_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    role = _role_name(user)
    return jsonify({
        "user_id": int(user.id),
        "username": user.username,
        "role": role,
        "permissions": _permissions_for_role(role),
    })


# -------------------------
# Dashboard readonly APIs
# -------------------------
def _base_employee_query(department_id: int | None):
    q = Employee.query.filter_by(is_deleted=False)
    if department_id:
        q = q.filter(Employee.department_id == department_id)
    return q


def _employee_stats(month: int, year: int, department_id: int | None):
    q = _base_employee_query(department_id)
    total = q.count()
    new_count = q.filter(func.extract("month", Employee.hire_date) == month, func.extract("year", Employee.hire_date) == year).count()
    resigned = q.filter(Employee.working_status == "resigned").count()
    expiring_contract = 0
    return {
        "total": total,
        "new": new_count,
        "resigned": resigned,
        "expiring_contract": expiring_contract,
    }


def _attendance_stats(month: int, year: int, department_id: int | None):
    q = db.session.query(Attendance).join(Employee, Attendance.employee_id == Employee.id)
    q = q.filter(func.extract("month", Attendance.date) == month, func.extract("year", Attendance.date) == year)
    if department_id:
        q = q.filter(Employee.department_id == department_id)

    total = q.count() or 1
    present = q.join(AttendanceStatus, Attendance.status_id == AttendanceStatus.id).filter(AttendanceStatus.status_name.in_(["PRESENT", "ON_TIME", "LATE"]))
    late_count = q.join(AttendanceStatus, Attendance.status_id == AttendanceStatus.id).filter(AttendanceStatus.status_name == "LATE").count()
    absent_count = q.join(AttendanceStatus, Attendance.status_id == AttendanceStatus.id).filter(AttendanceStatus.status_name == "ABSENT").count()

    hotspot = db.session.query(
        Department.id,
        func.sum(func.case((AttendanceStatus.status_name == "LATE", 1), else_=0)).label("late_total"),
        func.count(Attendance.id).label("count_total"),
    ).select_from(Attendance).join(Employee, Attendance.employee_id == Employee.id).join(Department, Employee.department_id == Department.id).join(AttendanceStatus, Attendance.status_id == AttendanceStatus.id).filter(
        func.extract("month", Attendance.date) == month,
        func.extract("year", Attendance.date) == year,
    ).group_by(Department.id).order_by(func.sum(func.case((AttendanceStatus.status_name == "LATE", 1), else_=0)).desc()).first()

    hotspot_obj = None
    if hotspot and hotspot.count_total:
        hotspot_obj = {"department_id": int(hotspot.id), "late_rate": round((hotspot.late_total or 0) * 100.0 / hotspot.count_total, 2)}

    return {
        "attendance_rate": round(present.count() * 100.0 / total, 2),
        "late_count": late_count,
        "absent_count": absent_count,
        "hotspot_department": hotspot_obj,
    }


def _salary_stats(month: int, year: int, department_id: int | None):
    q = db.session.query(Salary)
    if department_id:
        q = q.join(Employee, Salary.employee_id == Employee.id).filter(Employee.department_id == department_id)
    q = q.filter(Salary.month == month, Salary.year == year)
    total_salary = db.session.query(func.sum(Salary.net_salary)).select_from(Salary)
    if department_id:
        total_salary = total_salary.join(Employee, Salary.employee_id == Employee.id).filter(Employee.department_id == department_id)
    total_salary = total_salary.filter(Salary.month == month, Salary.year == year).scalar() or 0
    return {"total_salary": _to_float(total_salary), "salary_records": q.count()}


def _alerts(month: int, year: int, department_id: int | None):
    pending_complaints = Complaint.query.filter(Complaint.status.in_(["pending", "in_progress"])).count()
    pending_leaves = LeaveRequest.query.filter(LeaveRequest.status == "pending").count()
    return {
        "contracts_expiring": 0,
        "pending_complaints": pending_complaints,
        "pending_leaves": pending_leaves,
    }


def _activities():
    rows = HistoryLog.query.order_by(HistoryLog.created_at.desc()).limit(5).all()
    result = []
    for r in rows:
        t = "info"
        if "APPROVE" in r.action or "CREATE" in r.action:
            t = "success"
        if "REJECT" in r.action or "DELETE" in r.action:
            t = "error"
        result.append({"time": r.created_at.isoformat() if r.created_at else None, "action": r.action, "type": t})
    return result


@admin_bp.get("/api/dashboard/overview")
def dashboard_overview():
    month = request.args.get("month", type=int) or datetime.utcnow().month
    year = request.args.get("year", type=int) or datetime.utcnow().year
    department_id = request.args.get("department_id", type=int)

    return jsonify({
        "employee": _employee_stats(month, year, department_id),
        "attendance": _attendance_stats(month, year, department_id),
        "salary": _salary_stats(month, year, department_id),
        "alerts": _alerts(month, year, department_id),
        "activities": _activities(),
    })


@admin_bp.get("/api/dashboard/employees")
def dashboard_employees():
    m = request.args.get("month", type=int) or datetime.utcnow().month
    y = request.args.get("year", type=int) or datetime.utcnow().year
    d = request.args.get("department_id", type=int)
    return jsonify(_employee_stats(m, y, d))


@admin_bp.get("/api/dashboard/attendance")
def dashboard_attendance():
    m = request.args.get("month", type=int) or datetime.utcnow().month
    y = request.args.get("year", type=int) or datetime.utcnow().year
    d = request.args.get("department_id", type=int)
    return jsonify(_attendance_stats(m, y, d))


@admin_bp.get("/api/dashboard/salary")
def dashboard_salary():
    m = request.args.get("month", type=int) or datetime.utcnow().month
    y = request.args.get("year", type=int) or datetime.utcnow().year
    d = request.args.get("department_id", type=int)
    return jsonify(_salary_stats(m, y, d))


@admin_bp.get("/api/dashboard/alerts")
def dashboard_alerts():
    m = request.args.get("month", type=int) or datetime.utcnow().month
    y = request.args.get("year", type=int) or datetime.utcnow().year
    d = request.args.get("department_id", type=int)
    return jsonify(_alerts(m, y, d))


@admin_bp.get("/api/dashboard/activities")
def dashboard_activities():
    return jsonify(_activities())


# -------------------------
# Employee admin actions
# -------------------------
@admin_bp.get("/api/admin/employees/summary")
def admin_employee_summary():
    return jsonify(admin_service.employee_summary_cards())


@admin_bp.get("/api/admin/employees/notifications")
def admin_employee_notifications():
    return jsonify(admin_service.employee_notifications())


@admin_bp.get("/api/admin/employees/meta")
def admin_employee_meta():
    return jsonify(admin_service.employee_filter_metadata())


@admin_bp.get("/api/admin/employees")
def admin_list_employees():
    try:
        data = admin_service.query_employees(request.args)
    except admin_service.ServiceValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(data)


@admin_bp.post("/api/admin/employees")
def admin_create_employee():
    actor = _current_user()
    if not actor:
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        row = admin_service.create_employee(payload, actor.id)
    except admin_service.ServiceValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(row), 201


@admin_bp.get("/api/admin/employees/<int:employee_id>")
def admin_employee_detail(employee_id: int):
    return jsonify(admin_service.employee_detail(employee_id))


@admin_bp.patch("/api/admin/employees/<int:employee_id>")
def admin_update_employee(employee_id: int):
    actor = _current_user()
    if not actor:
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        row = admin_service.update_employee(employee_id, payload, actor.id)
    except admin_service.ServiceValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(row)


@admin_bp.patch("/api/admin/employees/<int:employee_id>/transfer")
def admin_transfer_employee(employee_id: int):
    actor = _current_user()
    if not actor:
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        row = admin_service.transfer_employee(employee_id, payload, actor.id)
    except admin_service.ServiceValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(row)


@admin_bp.post("/api/admin/users/<int:user_id>/reset-password")
def admin_reset_password(user_id: int):
    actor = _current_user()
    if not actor:
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        admin_service.reset_employee_password(user_id, payload.get("new_password"), actor.id)
    except admin_service.ServiceValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"success": True})

@admin_bp.get("/api/admin/resignations")
def list_resignations_admin_api():
    if _guard_admin_access():
        return jsonify({"error": "forbidden"}), 403
    status = (request.args.get("status") or "").strip().lower()
    query = ResignationRequest.query.order_by(ResignationRequest.created_at.desc())
    if status:
        query = query.filter(ResignationRequest.status == status)
    rows = query.limit(100).all()
    return jsonify([row.to_dict() for row in rows])


@admin_bp.post("/api/admin/resignations/<int:request_id>/finalize")
def finalize_resignation_admin_api(request_id: int):
    if _guard_admin_access():
        return jsonify({"error": "forbidden"}), 403
    request_item = ResignationRequest.query.get_or_404(request_id)
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip().lower()
    note = (data.get("note") or "").strip() or None
    try:
        ResignationService.admin_finalize(request_item, session.get("user_id") or 0, action, note)
        return jsonify({"message": "Admin đã duyệt resignation", "request": request_item.to_dict()})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@admin_bp.patch("/api/admin/employees/<int:employee_id>/inactive")
def admin_soft_delete_employee(employee_id: int):
    actor = _current_user()
    if not actor:
        return jsonify({"error": "unauthorized"}), 401
    try:
        admin_service.soft_delete_employee(employee_id, actor.id)
    except admin_service.ServiceValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"success": True})
@admin_bp.patch("/api/admin/users/<int:user_id>/lock")
def lock_user(user_id: int):
    actor = _current_user()
    if not actor:
        return jsonify({"error": "unauthorized"}), 401

    user = User.query.get_or_404(user_id)
    payload = request.get_json(silent=True) or {}
    lock_reason = (payload.get("reason") or "").strip()
    note = (payload.get("note") or "").strip()

    if actor.id == user.id:
        return jsonify({"error": "Không thể tự khóa chính mình"}), 400
    if user.role and user.role.name == "Admin":
        return jsonify({"error": "Không thể khóa tài khoản Admin"}), 403
    if not lock_reason:
        return jsonify({"error": "Vui lòng chọn lý do khóa"}), 400

    user.is_active = False
    user.lock_reason = f"{lock_reason}. {note}".strip()
    user.locked_at = datetime.utcnow()
    user.locked_by = actor.id
    db.session.add(HistoryLog(action="LOCK_USER", entity_type="user", entity_id=user.id, description=user.lock_reason, performed_by=actor.id))
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.patch("/api/admin/users/<int:user_id>/unlock")
def unlock_user(user_id: int):
    actor = _current_user()
    if not actor:
        return jsonify({"error": "unauthorized"}), 401
    user = User.query.get_or_404(user_id)
    user.is_active = True
    user.lock_reason = None
    user.locked_at = None
    user.locked_by = None
    db.session.add(HistoryLog(action="UNLOCK_USER", entity_type="user", entity_id=user.id, performed_by=actor.id))
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.patch("/api/admin/users/<int:user_id>/role")
def update_user_role(user_id: int):
    actor = _current_user()
    if not actor:
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    role_id = payload.get("role_id")
    user = User.query.get_or_404(user_id)

    if not user.is_active:
        return jsonify({"error": "Không phân quyền cho tài khoản đã bị khóa"}), 400
    if actor.id == user.id and user.role and user.role.name == "Admin":
        target_role = Role.query.get(role_id)
        if target_role and target_role.name != "Admin":
            return jsonify({"error": "Admin không thể tự hạ quyền"}), 400

    role = Role.query.get_or_404(role_id)
    user.role_id = role.id
    db.session.add(HistoryLog(action="UPDATE_ROLE", entity_type="user", entity_id=user.id, description=f"Role => {role.name}", performed_by=actor.id))
    db.session.commit()
    return jsonify({"success": True})


# -------------------------
# Department APIs
# -------------------------
@admin_bp.get("/api/departments")
def list_departments():
    keyword = (request.args.get("q") or "").strip().lower()
    q = Department.query.filter_by(is_deleted=False).outerjoin(Employee, Employee.id == Department.manager_id)
    if keyword:
        q = q.filter(
            (func.lower(Department.name).like(f"%{keyword}%"))
            | (func.cast(Department.id, db.String).like(f"%{keyword}%"))
            | (func.lower(func.coalesce(Employee.full_name, "")).like(f"%{keyword}%"))
        )
    depts = q.order_by(Department.name.asc()).all()
    return jsonify([
        {
            "id": int(d.id),
            "department_code": f"DP-{d.id}",
            "name": d.name,
            "manager_id": int(d.manager_id) if d.manager_id else None,
            "manager_name": d.manager.full_name if d.manager else None,
            "employee_count": d.employee_count,
            "status": bool(d.status),
            "description": d.description,
        }
        for d in depts
    ])

@admin_bp.get("/api/departments/stats")
def department_stats():
    rows = Department.query.filter_by(is_deleted=False).all()
    total = len(rows)
    active = len([d for d in rows if d.status])
    return jsonify({
        "total": total,
        "active": active,
        "inactive": total - active,
    })


@admin_bp.get("/api/departments/managers")
def department_manager_candidates():
    roles = ["manager", "admin", "hr"]
    candidates = (
        Employee.query.join(User, User.id == Employee.user_id)
        .join(Role, Role.id == User.role_id)
        .filter(
            Employee.is_deleted.is_(False),
            func.lower(Role.name).in_(roles)
        )
        .order_by(Employee.full_name.asc())
        .all()
    )
    return jsonify([
        {"id": int(emp.id), "name": emp.full_name, "role": emp.user.role.name if emp.user and emp.user.role else "N/A"}
        for emp in candidates
    ])


@admin_bp.post("/api/departments")
def create_department():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    if Department.query.filter(func.lower(Department.name) == name.lower(), Department.is_deleted.is_(False)).first():
        return jsonify({"error": "Department exists"}), 409
    manager_id = data.get("manager_id")
    if manager_id and not Employee.query.get(manager_id):
        return jsonify({"error": "manager not found"}), 400
    dept = Department(
        name=name,
        manager_id=manager_id,
        description=(data.get("description") or "").strip() or None,
        status=bool(data.get("status", True)),
    )
    db.session.add(dept)
    db.session.add(HistoryLog(action="CREATE_DEPARTMENT", entity_type="department", entity_id=dept.id, description=f"Tạo phòng ban {name}", performed_by=session.get("user_id")))
    db.session.commit()
    return jsonify({"id": int(dept.id), "name": dept.name}), 201


@admin_bp.get("/api/departments/<int:dept_id>")
def get_department(dept_id: int):
    d = Department.query.get_or_404(dept_id)
    employees = Employee.query.filter_by(department_id=d.id, is_deleted=False).all()
    male_count = len([e for e in employees if (e.gender or "").lower() == "male"])
    female_count = len([e for e in employees if (e.gender or "").lower() == "female"])
    on_leave_count = LeaveRequest.query.join(Employee, Employee.id == LeaveRequest.employee_id).filter(
        Employee.department_id == d.id,
        Employee.is_deleted.is_(False),
        LeaveRequest.status.in_(["pending", "pending_hr", "pending_admin", "approved"]),
        LeaveRequest.to_date >= date.today(),
    ).count()
    contract_expiring_count = Contract.query.join(Employee, Employee.id == Contract.employee_id).filter(
        Employee.department_id == d.id,
        Employee.is_deleted.is_(False),
        Contract.end_date.isnot(None),
        Contract.end_date >= date.today(),
        Contract.end_date <= (date.today() + timedelta(days=45)),
    ).count()
    return jsonify({
        "id": int(d.id),
        "name": d.name,
        "department_code": f"DP-{d.id}",
        "description": d.description,
        "status": bool(d.status),
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "manager_id": int(d.manager_id) if d.manager_id else None,
        "manager_name": d.manager.full_name if d.manager else None,
        "manager_phone": d.manager.phone if d.manager else None,
        "manager_email": d.manager.user.email if d.manager and d.manager.user else None,
        "manager_role": d.manager.user.role.name if d.manager and d.manager.user and d.manager.user.role else None,
        "employee_count": len(employees),
        "male_count": male_count,
        "female_count": female_count,
        "on_leave_count": on_leave_count,
        "contract_expiring_count": contract_expiring_count,
        "employees": [{"id": int(e.id), "name": e.full_name} for e in employees],
    })


@admin_bp.patch("/api/departments/<int:dept_id>")
def update_department(dept_id: int):
    d = Department.query.get_or_404(dept_id)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name required"}), 400
        dup = Department.query.filter(Department.id != d.id, func.lower(Department.name) == name.lower(), Department.is_deleted.is_(False)).first()
        if dup:
            return jsonify({"error": "name already exists"}), 409
        d.name = name
    if "manager_id" in data:
        mid = data.get("manager_id")
        if mid and not Employee.query.get(mid):
            return jsonify({"error": "manager not found"}), 400
        d.manager_id = mid
    if "description" in data:
        d.description = (data.get("description") or "").strip() or None
    if "status" in data:
        d.status = bool(data.get("status"))
    db.session.add(HistoryLog(action="UPDATE_DEPARTMENT", entity_type="department", entity_id=d.id, description=f"Cập nhật phòng ban {d.name}", performed_by=session.get("user_id")))
    db.session.commit()
    return jsonify({"success": True})

def _department_impact_payload(department: Department) -> dict:
    employee_count = Employee.query.filter_by(department_id=department.id, is_deleted=False).count()
    pending_leave_count = LeaveRequest.query.join(Employee, Employee.id == LeaveRequest.employee_id).filter(
        Employee.department_id == department.id,
        Employee.is_deleted.is_(False),
        LeaveRequest.status.in_(["pending", "pending_hr", "pending_admin", "supplement_requested"]),
    ).count()
    pending_salary_approval = Salary.query.join(Employee, Employee.id == Salary.employee_id).filter(
        Employee.department_id == department.id,
        Employee.is_deleted.is_(False),
        Salary.status.in_(["pending", "submitted"]),
    ).count()
    has_manager = bool(department.manager_id)
    safe_to_inactive = employee_count == 0 and pending_leave_count == 0 and pending_salary_approval == 0
    return {
        "department_id": int(department.id),
        "employee_count": employee_count,
        "pending_leave_count": pending_leave_count,
        "pending_approval_count": pending_salary_approval,
        "has_manager": has_manager,
        "safe_to_inactive": safe_to_inactive,
    }


@admin_bp.get("/api/departments/<int:dept_id>/impact")
def department_impact(dept_id: int):
    d = Department.query.get_or_404(dept_id)
    return jsonify(_department_impact_payload(d))


@admin_bp.delete("/api/departments/<int:dept_id>")
def disable_department(dept_id: int):
    d = Department.query.get_or_404(dept_id)
    impact = _department_impact_payload(d)
    if not impact.get("safe_to_inactive"):
        return jsonify({
            "error": "Department has unresolved dependencies",
            "impact": impact,
        }), 409
    d.status = False
    db.session.add(HistoryLog(action="INACTIVE_DEPARTMENT", entity_type="department", entity_id=d.id, description=f"Ngưng hoạt động phòng ban {d.name}", performed_by=session.get("user_id")))
    db.session.commit()
    return jsonify({"success": True})


# -------------------------
# Position APIs
# -------------------------
@admin_bp.get("/api/positions")
def list_positions():
    keyword = (request.args.get("q") or "").strip().lower()
    min_salary = request.args.get("min_salary", type=float)
    max_salary = request.args.get("max_salary", type=float)
    status = (request.args.get("status") or "").strip().lower()

    query = Position.query.filter_by(is_deleted=False)
    if keyword:
        query = query.filter(
            or_(
                func.lower(Position.job_title).like(f"%{keyword}%"),
                cast(Position.id, String).like(f"%{keyword}%"),
            )
        )
    if min_salary is not None:
        query = query.filter(func.coalesce(Position.max_salary, 0) >= min_salary)
    if max_salary is not None:
        query = query.filter(func.coalesce(Position.min_salary, 0) <= max_salary)
    if status in {"active", "hiring", "inactive"}:
        query = query.filter(Position.status == status)

    positions = query.order_by(Position.job_title.asc()).all()
    rows = []
    for p in positions:
        employee_count = Employee.query.filter_by(position_id=p.id, is_deleted=False).count()
        rows.append({
            "id": int(p.id),
            "position_code": f"POS{int(p.id):03d}",
            "job_title": p.job_title,
            "salary_range": f"{_to_float(p.min_salary):,.0f} - {_to_float(p.max_salary):,.0f}",
            "employee_count": employee_count,
            "min_salary": _to_float(p.min_salary),
            "max_salary": _to_float(p.max_salary),
            "status": p.status,
            "requirements": p.requirements,
        })
    return jsonify(rows)
@admin_bp.get("/api/positions/stats")
def positions_stats():
    positions = Position.query.filter_by(is_deleted=False).all()
    total_positions = len(positions)
    total_holding = Employee.query.filter(Employee.position_id.isnot(None), Employee.is_deleted.is_(False)).count()
    avg_salary = db.session.query(func.avg((func.coalesce(Position.min_salary, 0) + func.coalesce(Position.max_salary, 0)) / 2)).filter(
        Position.is_deleted.is_(False)
    ).scalar() or 0
    return jsonify({
        "total_positions": total_positions,
        "holding_employees": int(total_holding or 0),
        "average_salary": float(avg_salary or 0),
    })


def _position_impact_payload(position: Position) -> dict:
    employee_count = Employee.query.filter(
        Employee.position_id == position.id,
        Employee.is_deleted.is_(False),
    ).count()
    active_contract_count = Contract.query.join(Employee, Employee.id == Contract.employee_id).filter(
        Employee.position_id == position.id,
        Employee.is_deleted.is_(False),
        Contract.is_deleted.is_(False),
        Contract.status == "active",
    ).count()
    pending_payroll_count = Salary.query.join(Employee, Employee.id == Salary.employee_id).filter(
        Employee.position_id == position.id,
        Employee.is_deleted.is_(False),
        Salary.is_deleted.is_(False),
        Salary.status.in_(["pending", "submitted"]),
    ).count()
    safe_to_inactive = employee_count == 0 and active_contract_count == 0 and pending_payroll_count == 0
    return {
        "position_id": int(position.id),
        "employee_count": int(employee_count or 0),
        "active_contract_count": int(active_contract_count or 0),
        "pending_payroll_count": int(pending_payroll_count or 0),
        "safe_to_inactive": safe_to_inactive,
    }


@admin_bp.get("/api/positions/<int:pid>/impact")
def position_impact(pid: int):
    p = Position.query.get_or_404(pid)
    return jsonify(_position_impact_payload(p))



@admin_bp.post("/api/positions")
def create_position():
    data = request.get_json(silent=True) or {}
    title = (data.get("job_title") or "").strip()
    if not title:
        return jsonify({"error": "job_title required"}), 400
    if Position.query.filter(func.lower(Position.job_title) == title.lower(), Position.is_deleted.is_(False)).first():
        return jsonify({"error": "job_title exists"}), 409
    min_salary = float(data.get("min_salary") or 0)
    max_salary = float(data.get("max_salary") or 0)
    if min_salary > max_salary:
        return jsonify({"error": "min_salary must <= max_salary"}), 400
    status = (data.get("status") or "active").strip().lower()
    if status not in {"active", "hiring", "inactive"}:
        return jsonify({"error": "status invalid"}), 400
    p = Position(job_title=title, min_salary=min_salary, max_salary=max_salary, status=status, requirements=data.get("requirements"))
    db.session.add(p)
    db.session.flush()
    db.session.add(HistoryLog(
        action="CREATE_POSITION",
        entity_type="position",
        entity_id=p.id,
        description=f"Tạo chức danh {p.job_title}",
        performed_by=session.get("user_id"),
    ))
    db.session.commit()
    return jsonify({"id": int(p.id)}), 201


@admin_bp.get("/api/positions/<int:pid>")
def get_position(pid: int):
    p = Position.query.get_or_404(pid)
    employees = Employee.query.filter_by(position_id=p.id, is_deleted=False).all()
    creator = db.session.query(User.full_name).join(
        HistoryLog, HistoryLog.performed_by == User.id
    ).filter(
        HistoryLog.entity_type == "position",
        HistoryLog.entity_id == p.id,
        HistoryLog.action == "CREATE_POSITION",
    ).order_by(HistoryLog.created_at.asc()).first()
    return jsonify({
        "id": int(p.id),
        "position_code": f"POS{int(p.id):03d}",
        "job_title": p.job_title,
        "min_salary": _to_float(p.min_salary),
        "max_salary": _to_float(p.max_salary),
        "status": p.status,
        "requirements": p.requirements,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "created_by": creator[0] if creator else "--",
        "notes": "Mức lương này dùng để làm cơ sở gợi ý khi tạo Hợp đồng lao động (Contract) cho nhân viên. Không phải là mức lương cố định cuối cùng.",
        "employees": [{"id": int(e.id), "name": e.full_name} for e in employees],
    })


@admin_bp.patch("/api/positions/<int:pid>")
def update_position(pid: int):
    p = Position.query.get_or_404(pid)
    data = request.get_json(silent=True) or {}
    if "job_title" in data:
        title = (data.get("job_title") or "").strip()
        if not title:
            return jsonify({"error": "job_title required"}), 400
        dup = Position.query.filter(Position.id != p.id, func.lower(Position.job_title) == title.lower(), Position.is_deleted.is_(False)).first()
        if dup:
            return jsonify({"error": "job_title exists"}), 409
        p.job_title = title
    min_salary = float(data.get("min_salary") or p.min_salary or 0)
    max_salary = float(data.get("max_salary") or p.max_salary or 0)
    if min_salary > max_salary:
        return jsonify({"error": "invalid salary range"}), 400
    p.min_salary = min_salary
    p.max_salary = max_salary
    if "requirements" in data:
        p.requirements = data.get("requirements")
    if "status" in data:
        status = (data.get("status") or "").strip().lower()
        if status not in {"active", "hiring", "inactive"}:
            return jsonify({"error": "status invalid"}), 400
        if status == "inactive":
            impact = _position_impact_payload(p)
            if not impact.get("safe_to_inactive"):
                return jsonify({"error": "Position has unresolved dependencies", "impact": impact}), 409
        p.status = status
    db.session.add(HistoryLog(
        action="UPDATE_POSITION",
        entity_type="position",
        entity_id=p.id,
        description=f"Cập nhật chức danh {p.job_title}",
        performed_by=session.get("user_id"),
    ))
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.patch("/api/positions/<int:pid>/status")
def update_position_status(pid: int):
    p = Position.query.get_or_404(pid)
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in {"active", "hiring", "inactive"}:
        return jsonify({"error": "status invalid"}), 400
    if status == "inactive":
    
        impact = _position_impact_payload(p)
        if not impact.get("safe_to_inactive"):
            return jsonify({"error": "Position has unresolved dependencies", "impact": impact}), 409
    p.status = status
    db.session.add(HistoryLog(
        action="UPDATE_POSITION_STATUS",
        entity_type="position",
        entity_id=p.id,
        description=f"Đổi trạng thái chức danh {p.job_title} -> {status}",
        performed_by=session.get("user_id"),
    ))
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.delete("/api/positions/<int:pid>")
def disable_position(pid: int):
    p = Position.query.get_or_404(pid)
    impact = _position_impact_payload(p)
    if not impact.get("safe_to_inactive"):
        return jsonify({"error": "Position has unresolved dependencies", "impact": impact}), 409
    p.status = "inactive"
    db.session.add(HistoryLog(
        action="INACTIVE_POSITION",
        entity_type="position",
        entity_id=p.id,
        description=f"Ngừng sử dụng chức danh {p.job_title}",
        performed_by=session.get("user_id"),
    ))
    db.session.commit()
    return jsonify({"success": True})


# -------------------------
# Attendance admin APIs
# -------------------------
def _month_lock_key(month: int, year: int) -> str:
    return f"attendance_lock:{year}-{month}"

def _is_month_locked(month: int, year: int) -> bool:
    row = SystemSetting.query.filter_by(key=_month_lock_key(month, year)).first()
    return bool(row and row.value == "locked")


def _attendance_base_query(month: int, year: int):
    return (
        db.session.query(Attendance, Employee, Department, Position, Role, AttendanceStatus)
        .join(Employee, Employee.id == Attendance.employee_id)
        .join(User, User.id == Employee.user_id, isouter=True)
        .join(Role, Role.id == User.role_id, isouter=True)
        .join(Department, Department.id == Employee.department_id, isouter=True)
        .join(Position, Position.id == Employee.position_id, isouter=True)
        .join(AttendanceStatus, AttendanceStatus.id == Attendance.status_id, isouter=True)
        .filter(
            func.extract("month", Attendance.date) == month,
            func.extract("year", Attendance.date) == year,
            Employee.is_attendance_required.is_(True),
            func.coalesce(Role.name, "").notin_(["Admin", "HR"]),
        )
    )
@admin_bp.get("/api/admin/attendance/summary")
def attendance_summary():
    month = request.args.get("month", type=int) or datetime.utcnow().month
    year = request.args.get("year", type=int) or datetime.utcnow().year

    rows = db.session.query(
        Department.id,
        Department.name,
        func.count(Employee.id).label("employee_count"),
        func.sum(AttendanceStatus.multiplier).label("total_work"),
        func.sum(func.case((AttendanceStatus.status_name == "LATE", 1), else_=0)).label("late_count"),
        func.sum(func.case((AttendanceStatus.status_name == "ABSENT", 1), else_=0)).label("absent_count"),
    ).select_from(Department).outerjoin(Employee, Employee.department_id == Department.id).outerjoin(
        Attendance,
        db.and_(Attendance.employee_id == Employee.id, func.extract("month", Attendance.date) == month, func.extract("year", Attendance.date) == year),
    ).outerjoin(AttendanceStatus, Attendance.status_id == AttendanceStatus.id).group_by(Department.id, Department.name).all()

    return jsonify([{
        "department_id": int(r.id),
        "department_name": r.name,
        "employee_count": int(r.employee_count or 0),
        "total_work": float(r.total_work or 0),
        "late_count": int(r.late_count or 0),
        "absent_count": int(r.absent_count or 0),
    } for r in rows])

@admin_bp.get("/api/admin/attendance/stats")
def attendance_stats():
    month = request.args.get("month", type=int) or datetime.utcnow().month
    year = request.args.get("year", type=int) or datetime.utcnow().year
    records = _attendance_base_query(month, year).all()
    if not records:
        return jsonify({
            "present_total": 0,
            "late_total": 0,
            "leave_total": 0,
            "ot_pending": 0,
            "abnormal_total": 0,
            "locked_total": 0,
            "unlocked_total": 0,
        })

    present_total = late_total = leave_total = abnormal_total = locked_total = 0
    for att, _, _, _, _, status in records:
        code = (status.status_name if status else "").upper()
        atype = (att.attendance_type or "").lower()
        if code in {"PRESENT", "LEAVE"} or atype in {"normal", "overtime", "holiday", "leave_approved"}:
            present_total += 1
        if code == "LATE" or atype in {"late", "early", "late_early"}:
            late_total += 1
        if code == "LEAVE" or atype == "leave_approved":
            leave_total += 1
        if code == "ABSENT" or atype in {"abnormal", "abnormal_rejected", "absent"}:
            abnormal_total += 1
        if _is_month_locked(att.date.month, att.date.year):
            locked_total += 1

    ot_pending = (
        db.session.query(func.count(OvertimeRequest.id))
        .join(Employee, Employee.id == OvertimeRequest.employee_id)
        .join(User, User.id == Employee.user_id, isouter=True)
        .join(Role, Role.id == User.role_id, isouter=True)
        .filter(
            func.extract("month", OvertimeRequest.overtime_date) == month,
            func.extract("year", OvertimeRequest.overtime_date) == year,
            OvertimeRequest.status == "pending_admin",
            Employee.is_attendance_required.is_(True),
            func.coalesce(Role.name, "").notin_(["Admin", "HR"]),
        )
        .scalar()
    )
    return jsonify({
        "present_total": int(present_total),
        "late_total": int(late_total),
        "leave_total": int(leave_total),
        "ot_pending": int(ot_pending or 0),
        "abnormal_total": int(abnormal_total),
        "locked_total": int(locked_total),
        "unlocked_total": int(len(records) - locked_total),
    })


@admin_bp.get("/api/admin/attendance/records")
def attendance_records():
    month = request.args.get("month", type=int) or datetime.utcnow().month
    year = request.args.get("year", type=int) or datetime.utcnow().year
    department_id = request.args.get("department_id", type=int)
    keyword = (request.args.get("keyword") or "").strip().lower()
    status_filter = (request.args.get("status") or "").strip().lower()
    lock_status = (request.args.get("lock_status") or "").strip().lower()
    ot_status = (request.args.get("ot_status") or "").strip().lower()

    query = _attendance_base_query(month, year)
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if keyword:
        query = query.filter(
            or_(
                func.lower(Employee.full_name).like(f"%{keyword}%"),
                func.lower(cast(Employee.id, String)).like(f"%{keyword}%"),
                func.lower(func.coalesce(Department.name, "")).like(f"%{keyword}%"),
            )
        )

    rows = query.order_by(Attendance.date.desc(), Employee.full_name.asc()).limit(500).all()
    grouped = defaultdict(lambda: {
        "attendance_ids": [],
        "employee_id": None,
        "employee_code": "",
        "employee_name": "",
        "department": "--",
        "position": "--",
        "working_days": 0,
        "total_hours": 0.0,
        "regular_hours": 0.0,
        "overtime_hours": 0.0,
        "late_count": 0,
        "early_count": 0,
        "leave_days": 0,
        "unpaid_leave_days": 0,
        "abnormal_count": 0,
        "ot_pending_count": 0,
        "attendance_status": "normal",
        "lock_status": "open",
    })

    for att, emp, dept, pos, _, status in rows:
        row_ot = OvertimeRequest.query.filter_by(employee_id=emp.id, overtime_date=att.date).order_by(OvertimeRequest.id.desc()).first()
        if ot_status and (row_ot.status if row_ot else "") != ot_status:
            continue
        status_name = (status.status_name if status else "").upper()
        code = status_name
        attendance_type = (att.attendance_type or "").lower()
        logical_status = "normal"
        if attendance_type in {"late", "early", "late_early"} or status_name == "LATE":
            logical_status = "late_early"
        elif row_ot and row_ot.status == "pending_admin":
            logical_status = "ot_pending"
        elif attendance_type in {"abnormal", "abnormal_rejected", "absent"} or status_name == "ABSENT":
            logical_status = "abnormal"
        key = emp.id
        bucket = grouped[key]
        bucket["attendance_ids"].append(att.id)
        bucket["employee_id"] = emp.id
        bucket["employee_code"] = f"EMP{emp.id:04d}"
        bucket["employee_name"] = emp.full_name
        bucket["department"] = dept.name if dept else "--"
        bucket["position"] = pos.job_title if pos else "--"
        bucket["working_days"] += 1
        bucket["total_hours"] += float(att.working_hours or 0)
        bucket["regular_hours"] += float(att.regular_hours or 0)
        bucket["overtime_hours"] += float(att.overtime_hours or 0)

        late_minutes = 0
        early_minutes = 0
        if att.check_in and att.check_in.hour >= 8 and att.check_in.minute > 0:
            late_minutes = att.check_in.hour * 60 + att.check_in.minute - 8 * 60
        if att.check_out and att.check_out.hour < 17:
            early_minutes = 17 * 60 - (att.check_out.hour * 60 + att.check_out.minute)
        if late_minutes > 0:
            bucket["late_count"] += 1
        if early_minutes > 0:
            bucket["early_count"] += 1
        if code == "LEAVE" or attendance_type == "leave_approved":
            bucket["leave_days"] += 1
        if code == "ABSENT" or attendance_type in {"absent", "absent_unexcused", "abnormal_rejected"}:
            bucket["unpaid_leave_days"] += 1
        if logical_status == "abnormal":
            bucket["abnormal_count"] += 1
        if row_ot and row_ot.status == "pending_admin":
            bucket["ot_pending_count"] += 1
        if _is_month_locked(att.date.month, att.date.year):
            bucket["lock_status"] = "locked"

    data = []
    for bucket in grouped.values():
        if bucket["abnormal_count"] > 0:
            bucket["attendance_status"] = "abnormal"
        elif bucket["ot_pending_count"] > 0:
            bucket["attendance_status"] = "ot_pending"
        elif bucket["late_count"] > 0 or bucket["early_count"] > 0:
            bucket["attendance_status"] = "late_early"
        if status_filter and bucket["attendance_status"] != status_filter:
            continue
        if lock_status and bucket["lock_status"] != lock_status:
            continue
        data.append(bucket)

    data.sort(key=lambda x: (x["department"], x["employee_name"]))
    return jsonify(data)
@admin_bp.get("/api/admin/attendance/records/<int:employee_id>/details")
def attendance_employee_details(employee_id: int):
    month = request.args.get("month", type=int) or datetime.utcnow().month
    year = request.args.get("year", type=int) or datetime.utcnow().year
    rows = (
        _attendance_base_query(month, year)
        .filter(Employee.id == employee_id)
        .order_by(Attendance.date.desc())
        .all()
    )
    return jsonify([
        {
            "attendance_id": att.id,
            "work_date": att.date.isoformat(),
            "check_in": att.check_in.isoformat() if att.check_in else None,
            "check_out": att.check_out.isoformat() if att.check_out else None,
            "working_hours": float(att.working_hours or 0),
            "regular_hours": float(att.regular_hours or 0),
            "overtime_hours": float(att.overtime_hours or 0),
            "attendance_type": att.attendance_type,
            "status_label": (status.status_name if status else att.attendance_type or "PRESENT"),
            "lock_status": "locked" if _is_month_locked(att.date.month, att.date.year) else "open",
        }
        for att, _, _, _, _, status in rows
    ])
@admin_bp.get("/api/admin/attendance/config")
def attendance_config_get():
    getv = lambda k, d: (SystemSetting.query.filter_by(key=k).first() or SystemSetting(key=k, value=str(d))).value
    statuses = AttendanceStatus.query.all()
    return jsonify({
        "work_start": getv("attendance.work_start", "08:00"),
        "work_end": getv("attendance.work_end", "17:00"),
        "standard_hours": float(getv("attendance.standard_hours", "8")),
        "statuses": [{"id": s.id, "code": s.status_name, "label": s.status_name, "multiplier": s.multiplier} for s in statuses],
    })


@admin_bp.put("/api/admin/attendance/config")
def attendance_config_update():
    data = request.get_json(silent=True) or {}
    actor = _current_user()
    for key in ["work_start", "work_end", "standard_hours"]:
        if key in data:
            setting_key = f"attendance.{key}"
            row = SystemSetting.query.filter_by(key=setting_key).first()
            if not row:
                row = SystemSetting(key=setting_key, value=str(data[key]))
                db.session.add(row)
            else:
                row.value = str(data[key])
    for status in data.get("statuses", []):
        obj = AttendanceStatus.query.get(status.get("id"))
        if obj:
            multiplier = float(status.get("multiplier", obj.multiplier))
            if multiplier < 0:
                return jsonify({"error": "multiplier must >= 0"}), 400
            obj.multiplier = multiplier
    db.session.add(HistoryLog(action="UPDATE_ATTENDANCE_CONFIG", entity_type="attendance", description="update config", performed_by=actor.id if actor else None))
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.post("/api/admin/attendance/lock-month")
def attendance_lock_month():
    actor = _current_user()
    data = request.get_json(silent=True) or {}
    month = int(data.get("month"))
    year = int(data.get("year"))
    key = _month_lock_key(month, year)
    row = SystemSetting.query.filter_by(key=key).first()
    if row and row.value == "locked":
        return jsonify({"error": "already locked"}), 409
    if not row:
        row = SystemSetting(key=key, value="locked", description="attendance month lock")
        db.session.add(row)
    else:
        row.value = "locked"
    Attendance.query.filter(
        func.extract("month", Attendance.date) == month,
        func.extract("year", Attendance.date) == year,
    ).update({Attendance.attendance_type: "locked"}, synchronize_session=False)
    db.session.add(HistoryLog(action="LOCK_ATTENDANCE", entity_type="attendance", description=f"{month}/{year}", performed_by=actor.id if actor else None))
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.post("/api/admin/attendance/reopen-month")
def attendance_reopen_month():
    actor = _current_user()
    data = request.get_json(silent=True) or {}
    if _role_name(actor) != "Admin":
        return jsonify({"error": "only admin can reopen"}), 403
    month = int(data.get("month"))
    year = int(data.get("year"))
    reason = (data.get("reason") or "").strip()
    key = _month_lock_key(month, year)
    row = SystemSetting.query.filter_by(key=key).first()
    if not row:
        row = SystemSetting(key=key, value="open")
        db.session.add(row)
    else:
        row.value = "open"
    Attendance.query.filter(
        func.extract("month", Attendance.date) == month,
        func.extract("year", Attendance.date) == year,
        Attendance.attendance_type == "locked",
    ).update({Attendance.attendance_type: "normal"}, synchronize_session=False)
    db.session.add(HistoryLog(action="REOPEN_ATTENDANCE", entity_type="attendance", description=f"{month}/{year} - {reason}", performed_by=actor.id if actor else None))
    db.session.commit()
    return jsonify({"success": True})
@admin_bp.post("/api/admin/attendance/<int:attendance_id>/manual-update")
def attendance_manual_update(attendance_id: int):
    row = Attendance.query.get_or_404(attendance_id)
    if _is_month_locked(row.date.month, row.date.year):
        return jsonify({"error": "attendance month is locked"}), 409
    payload = request.get_json(silent=True) or {}
    check_in = payload.get("check_in")
    check_out = payload.get("check_out")
    if check_in:
        row.check_in = datetime.fromisoformat(check_in)
    if check_out:
        row.check_out = datetime.fromisoformat(check_out)
    if payload.get("status_id"):
        row.status_id = int(payload.get("status_id"))
    if payload.get("overtime_hours") is not None:
        row.overtime_hours = payload.get("overtime_hours")
    note = (payload.get("note") or "").strip()
    row.attendance_type = payload.get("attendance_type") or row.attendance_type
    db.session.add(HistoryLog(
        employee_id=row.employee_id,
        action="ADMIN_MANUAL_ATTENDANCE_UPDATE",
        entity_type="attendance",
        entity_id=row.id,
        description=f"Manual update attendance {row.date.isoformat()} | {note}",
        performed_by=session.get("user_id"),
    ))
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.post("/api/admin/attendance/<int:attendance_id>/mark-abnormal")
def attendance_mark_abnormal(attendance_id: int):
    row = Attendance.query.get_or_404(attendance_id)
    if _is_month_locked(row.date.month, row.date.year):
        return jsonify({"error": "attendance month is locked"}), 409
    payload = request.get_json(silent=True) or {}
    note = (payload.get("note") or "").strip()
    row.attendance_type = "abnormal"
    db.session.add(HistoryLog(
        employee_id=row.employee_id,
        action="ADMIN_MARK_ABNORMAL_ATTENDANCE",
        entity_type="attendance",
        entity_id=row.id,
        description=f"Mark abnormal {row.date.isoformat()} | {note}",
        performed_by=session.get("user_id"),
    ))
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.get("/api/admin/attendance/overtime/pending")
def attendance_pending_overtime():
    month = request.args.get("month", type=int) or datetime.utcnow().month
    year = request.args.get("year", type=int) or datetime.utcnow().year
    rows = (
        db.session.query(OvertimeRequest, Employee, Department)
        .join(Employee, Employee.id == OvertimeRequest.employee_id)
        .join(User, User.id == Employee.user_id, isouter=True)
        .join(Role, Role.id == User.role_id, isouter=True)
        .join(Department, Department.id == Employee.department_id, isouter=True)
        .filter(
            OvertimeRequest.status == "pending_admin",
            func.extract("month", OvertimeRequest.overtime_date) == month,
            func.extract("year", OvertimeRequest.overtime_date) == year,
            Employee.is_attendance_required.is_(True),
            func.coalesce(Role.name, "").notin_(["Admin", "HR"]),
        ).all()
    )
    return jsonify([{
        "id": ot.id,
        "employee_name": emp.full_name,
        "employee_code": f"EMP{emp.id:04d}",
        "department": dept.name if dept else "--",
        "date": ot.overtime_date.isoformat(),
        "hours": float(ot.overtime_hours or 0),
        "reason": ot.reason,
        "status": ot.status,
    } for ot, emp, dept in rows])


@admin_bp.post("/api/admin/attendance/overtime/<int:overtime_id>/final-review")
def attendance_overtime_final_review(overtime_id: int):
    actor = _current_user()
    if _role_name(actor) != "Admin":
        return jsonify({"error": "only admin can final approve overtime"}), 403
    row = OvertimeRequest.query.get_or_404(overtime_id)
    payload = request.get_json(silent=True) or {}
    action = (payload.get("action") or "").strip().lower()
    note = (payload.get("note") or "").strip()
    if action not in {"approve", "reject"}:
        return jsonify({"error": "invalid action"}), 400
    if row.status != "pending_admin":
        return jsonify({"error": "Yêu cầu OT này đã được xử lý trước đó"}), 409
    row.status = "approved" if action == "approve" else "rejected"
    row.note = note
    if action == "approve":
        attendance = Attendance.query.filter_by(employee_id=row.employee_id, date=row.overtime_date).first()
        if attendance:
            attendance.overtime_hours = row.overtime_hours
            attendance.attendance_type = "holiday" if attendance.attendance_type == "holiday" else "overtime"
    employee = Employee.query.get(row.employee_id)
    if employee and employee.user_id:
        if action == "approve":
            content = (
                "Yêu cầu tăng ca của bạn đã được duyệt.\n\n"
                "Ca OT bắt đầu lúc: 19:00.\n"
                "Vui lòng quay lại hệ thống để check-in tăng ca."
            )
        else:
            content = f"Yêu cầu tăng ca của bạn đã bị từ chối.\n\nLý do: {note or 'Không có'}"
        db.session.add(
            Notification(
                user_id=employee.user_id,
                title="Kết quả duyệt tăng ca",
                content=content,
                type="overtime",
                link="/employee/notifications",
            )
        )
    db.session.add(HistoryLog(
        employee_id=row.employee_id,
        action="ADMIN_FINAL_OVERTIME_REVIEW",
        entity_type="overtime_request",
        entity_id=row.id,
        description=f"{action} overtime | {note}",
        performed_by=actor.id if actor else None,
    ))
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.get("/api/admin/attendance/export")
def attendance_export_csv():
    month = request.args.get("month", type=int) or datetime.utcnow().month
    year = request.args.get("year", type=int) or datetime.utcnow().year
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ma NV", "Ten NV", "Phong ban", "Ngay", "Gio vao", "Gio ra", "Tong gio", "Cong chuan", "OT", "Loai ca"])
    rows = _attendance_base_query(month, year).all()
    for att, emp, dept, _, _, _ in rows:
        writer.writerow([
            f"EMP{emp.id:04d}",
            emp.full_name,
            dept.name if dept else "",
            att.date.isoformat() if att.date else "",
            att.check_in.isoformat() if att.check_in else "",
            att.check_out.isoformat() if att.check_out else "",
            float(att.working_hours or 0),
            float(att.regular_hours or 0),
            float(att.overtime_hours or 0),
            att.attendance_type or "",
        ])
    filename = f"attendance_{year}_{month:02d}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

@admin_bp.get("/api/admin/attendance/audit-log")
def attendance_audit_log():
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    q = HistoryLog.query.filter_by(entity_type="attendance")
    if month and year:
        q = q.filter(HistoryLog.description.ilike(f"%{month}/{year}%"))
    rows = q.order_by(HistoryLog.created_at.desc()).limit(50).all()
    return jsonify([
        {
            "time": r.created_at.isoformat() if r.created_at else None,
            "action": r.action,
            "by": int(r.performed_by) if r.performed_by else None,
            "description": r.description,
        }
        for r in rows
    ])


PAYROLL_STATUS_LABELS = {
    "draft": "Nháp",
    "pending": "Chờ duyệt",
    "pending_approval": "Chờ duyệt",
    "approved": "Đã duyệt",
    "paid": "Đã duyệt",
    "locked": "Đã chốt",
    "finalized": "Đã chốt",
    "complaint": "Khiếu nại",
}


def _progressive_tax(taxable_income: Decimal) -> Decimal:
    policy = PayrollPolicyService.get_policy()
    return PayrollPolicyService.tax_by_bracket(taxable_income, policy["tax"]["brackets"])


def _late_penalty(employee_id: int, month: int, year: int, basic_salary: Decimal, standard_days: int) -> Decimal:
    policy = PayrollPolicyService.get_policy()
    under_15 = Decimal(str(policy["late_penalty"]["under_15"]))
    from_15_to_30 = Decimal(str(policy["late_penalty"]["from_15_to_30"]))
    over_60_half_day = bool(policy["late_penalty"]["over_60_half_day"])
    records = Attendance.query.filter(
        Attendance.employee_id == employee_id,
        func.extract("month", Attendance.date) == month,
        func.extract("year", Attendance.date) == year,
        Attendance.is_deleted.is_(False),
    ).all()
    penalty = Decimal("0")
    half_day_unit = (basic_salary / Decimal(str(max(standard_days, 1)))) / Decimal("2")
    for att in records:
        if not att.check_in:
            continue
        late_minutes = (att.check_in.hour * 60 + att.check_in.minute) - (8 * 60)
        if late_minutes < 1:
            continue
        if late_minutes < 15:
            penalty += under_15
        elif late_minutes <= 30:
            penalty += from_15_to_30
        elif late_minutes > 60 and over_60_half_day:
            penalty += half_day_unit
    return penalty.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _payroll_row(row: Salary):
    policy = PayrollPolicyService.get_policy()
    employee = row.employee
    user = employee.user if employee else None
    status_raw = (row.status or "draft").lower()
    dependent_count = PayrollPolicyService.dependent_count(employee.id if employee else None)
    total_allowance = Decimal(str(row.total_allowance or 0))
    basic_salary = Decimal(str(row.basic_salary or 0))
    bonus = Decimal(str(row.bonus or 0))
    base_deduction = Decimal(str(row.penalty or 0))
    standard_days = int(row.standard_work_days or 22)
    late_penalty = _late_penalty(employee.id, row.month, row.year, basic_salary, standard_days) if employee else Decimal("0")
    overtime_pay = (Decimal(str(row.total_work_days or 0)) - Decimal(str(standard_days)))
    if overtime_pay < 0:
        overtime_pay = Decimal("0")
    overtime_pay = (overtime_pay * (basic_salary / Decimal(str(max(standard_days, 1)))) * Decimal("1.5")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    gross = basic_salary + total_allowance + bonus + overtime_pay
    taxable_income = max(Decimal("0"), gross - total_allowance)
    insurance_rate = Decimal(str(policy["insurance"]["total_percent"])) / Decimal("100")
    insurance = (taxable_income * insurance_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    personal_deduction = Decimal(str(policy["deduction"]["personal"]))
    per_dependent = Decimal(str(policy["deduction"]["dependent_per_person"]))
    dependent_deduction = (personal_deduction + per_dependent * Decimal(str(dependent_count))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    taxable_after_deduction = max(Decimal("0"), taxable_income - insurance - personal_deduction - per_dependent * Decimal(str(dependent_count)))
    tax = _progressive_tax(taxable_after_deduction)
    total_deduction = (base_deduction + late_penalty + insurance + tax).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    net_salary = (gross - total_deduction).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    complaint = Complaint.query.filter_by(salary_id=row.id, is_deleted=False).order_by(Complaint.created_at.desc()).first()
    display_status = "complaint" if complaint and complaint.status in {"pending", "in_progress"} else status_raw
    return {
        "id": row.id,
        "employee_id": employee.id if employee else None,
        "employee_code": f"EMP-{employee.id:05d}" if employee else "N/A",
        "employee_name": employee.full_name if employee else "N/A",
        "department": employee.department.name if employee and employee.department else "--",
        "position": employee.position.job_title if employee and employee.position else "--",
        "role": user.role.name if user and user.role else "Employee",
        "month": row.month,
        "year": row.year,
        "basic_salary": float(basic_salary),
        "allowance": float(total_allowance),
        "deduction": float(base_deduction + late_penalty),
        "late_penalty": float(late_penalty),
        "ot": float(overtime_pay),
        "insurance": float(insurance),
        "tax": float(tax),
        "dependent_deduction": float(dependent_deduction),
        "number_of_dependents": int(dependent_count),
        "net_salary": float(net_salary),
        "status": display_status,
        "status_label": PAYROLL_STATUS_LABELS.get(display_status, display_status),
        "has_complaint": bool(complaint and complaint.status in {"pending", "in_progress"}),
        "complaint_status": complaint.status if complaint else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "calculated_by": "HR System",
    }


def _payroll_filtered_query():
    month = request.args.get("month", type=int) or datetime.utcnow().month
    year = request.args.get("year", type=int) or datetime.utcnow().year
    query = Salary.query.join(Employee, Salary.employee_id == Employee.id).outerjoin(User, Employee.user_id == User.id).filter(
        Salary.month == month,
        Salary.year == year,
        Salary.is_deleted.is_(False),
    )
    keyword = (request.args.get("keyword") or "").strip()
    department_id = request.args.get("department_id", type=int)
    status = (request.args.get("status") or "").strip().lower()
    role = (request.args.get("role") or "").strip()
    has_complaint = (request.args.get("has_complaint") or "").strip().lower()
    locked = (request.args.get("locked") or "").strip().lower()
    if keyword:
        query = query.outerjoin(Department, Employee.department_id == Department.id).outerjoin(Position, Employee.position_id == Position.id).filter(or_(
            Employee.full_name.ilike(f"%{keyword}%"),
            func.cast(Employee.id, String).ilike(f"%{keyword.replace('EMP-', '')}%"),
            Department.name.ilike(f"%{keyword}%"),
            Position.job_title.ilike(f"%{keyword}%"),
        ))
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if status:
        if status == "pending_approval":
            query = query.filter(Salary.status.in_(["pending", "pending_approval"]))
        elif status == "locked":
            query = query.filter(Salary.status.in_(["locked", "finalized"]))
        elif status == "approved":
            query = query.filter(Salary.status.in_(["approved", "paid"]))
        else:
            query = query.filter(Salary.status == status)
    if role:
        query = query.join(Role, User.role_id == Role.id).filter(Role.name == role)
    if locked in {"yes", "true", "1"}:
        query = query.filter(Salary.status.in_(["locked", "finalized"]))
    if locked in {"no", "false", "0"}:
        query = query.filter(~Salary.status.in_(["locked", "finalized"]))
    if has_complaint in {"yes", "true", "1"}:
        query = query.filter(Salary.id.in_(db.session.query(Complaint.salary_id).filter(Complaint.status.in_(["pending", "in_progress"]), Complaint.is_deleted.is_(False))))
    if has_complaint in {"no", "false", "0"}:
        query = query.filter(~Salary.id.in_(db.session.query(Complaint.salary_id).filter(Complaint.status.in_(["pending", "in_progress"]), Complaint.is_deleted.is_(False))))
    return query, month, year


@admin_bp.get("/api/admin/payroll/overview")
def payroll_overview():
    query, month, year = _payroll_filtered_query()
    rows = [_payroll_row(r) for r in query.order_by(Salary.updated_at.desc()).all()]
    summary = {
        "total_payroll": len(rows),
        "pending": sum(1 for r in rows if r["status"] in {"pending", "pending_approval"}),
        "approved": sum(1 for r in rows if r["status"] in {"approved", "paid"}),
        "locked": sum(1 for r in rows if r["status"] in {"locked", "finalized"}),
        "complaint": sum(1 for r in rows if r["has_complaint"]),
        "abnormal": sum(1 for r in rows if r["deduction"] > (r["basic_salary"] * 0.2)),
        "total_net": float(sum(Decimal(str(r["net_salary"])) for r in rows)),
        "month": month,
        "year": year,
    }
    return jsonify({"summary": summary, "items": rows})


@admin_bp.get("/api/admin/payroll/<int:salary_id>/detail")
def payroll_detail_admin(salary_id: int):
    row = Salary.query.filter_by(id=salary_id, is_deleted=False).first_or_404()
    payload = _payroll_row(row)
    payload["payroll_period"] = f"{row.month:02d}/{row.year}"
    return jsonify(payload)

@admin_bp.post("/api/admin/payroll/<int:salary_id>/approval")
def payroll_approval_action(salary_id: int):
    actor = _current_user()
    payload = request.get_json(silent=True) or {}
    action = (payload.get("action") or "").strip()
    reason = (payload.get("reason") or "").strip()
    salary = Salary.query.filter_by(id=salary_id, is_deleted=False).first_or_404()
    if salary.status in {"locked", "finalized"}:
        return jsonify({"error": "Payroll đã chốt, không thể duyệt lại"}), 409
    if action in {"reject", "recalculate"} and not reason:
        return jsonify({"error": "Bắt buộc nhập lý do"}), 400
    if action == "approve":
        salary.status = "approved"
        log_action = "APPROVE_PAYROLL"
    elif action == "reject":
        salary.status = "draft"
        salary.note = reason
        log_action = "REJECT_PAYROLL"
    elif action == "recalculate":
        salary.status = "pending_approval"
        salary.note = reason
        log_action = "REQUEST_RECALCULATE_PAYROLL"
    else:
        return jsonify({"error": "Action không hợp lệ"}), 400
    db.session.add(HistoryLog(action=log_action, entity_type="salary", entity_id=salary.id, description=reason or f"salary_id={salary.id}", performed_by=actor.id if actor else None))
    db.session.commit()
    return jsonify({"success": True, "status": salary.status})

@admin_bp.post("/api/admin/payroll/finalize-month")
def payroll_finalize_month():
    actor = _current_user()
    payload = request.get_json(silent=True) or {}
    month = int(payload.get("month") or 0)
    year = int(payload.get("year") or 0)
    rows = Salary.query.filter_by(month=month, year=year, is_deleted=False).all()
    if not rows:
        return jsonify({"error": "Không có bảng lương kỳ này"}), 404
    for row in rows:
        row.status = "locked"
    db.session.add(HistoryLog(action="FINALIZE_PAYROLL_MONTH", entity_type="salary", description=f"{month:02d}/{year}", performed_by=actor.id if actor else None))
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.post("/api/admin/payroll/reopen-month")
def payroll_reopen_month():
    actor = _current_user()
    payload = request.get_json(silent=True) or {}
    month = int(payload.get("month") or 0)
    year = int(payload.get("year") or 0)
    reason = (payload.get("reason") or "").strip()
    if not reason:
        return jsonify({"error": "Lý do mở lại payroll là bắt buộc"}), 400
    rows = Salary.query.filter_by(month=month, year=year, is_deleted=False).all()
    for row in rows:
        if row.status in {"locked", "finalized"}:
            row.status = "pending_approval"
    db.session.add(HistoryLog(action="REOPEN_PAYROLL_MONTH", entity_type="salary", description=f"{month:02d}/{year} | {reason}", performed_by=actor.id if actor else None))
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.get("/api/admin/payroll/complaints")
def payroll_complaints():
    month = request.args.get("month", type=int) or datetime.utcnow().month
    year = request.args.get("year", type=int) or datetime.utcnow().year
    rows = Complaint.query.join(Salary, Complaint.salary_id == Salary.id).join(Employee, Complaint.employee_id == Employee.id).filter(
        Salary.month == month,
        Salary.year == year,
        Complaint.salary_id.isnot(None),
        Complaint.is_deleted.is_(False),
    ).order_by(Complaint.created_at.desc()).limit(100).all()
    return jsonify([
        {
            "id": c.id,
            "salary_id": c.salary_id,
            "employee_name": c.employee.full_name if c.employee else "--",
            "title": c.title,
            "content": c.description,
            "status": c.status,
            "hr_replied": bool(c.admin_reply),
            "history": [{"message": m.message, "sender_id": m.sender_id, "time": m.created_at.isoformat() if m.created_at else None} for m in ComplaintMessage.query.filter_by(complaint_id=c.id, is_deleted=False).order_by(ComplaintMessage.created_at.asc()).all()],
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in rows
    ])
@admin_bp.post("/api/admin/payroll/complaints/<int:complaint_id>/handle")
def payroll_complaint_handle(complaint_id: int):
    actor = _current_user()
    payload = request.get_json(silent=True) or {}
    action = (payload.get("action") or "").strip()
    message = (payload.get("message") or "").strip()
    complaint = Complaint.query.filter_by(id=complaint_id, is_deleted=False).first_or_404()
    if action == "reply":
        complaint.admin_reply = message or "Admin đã phản hồi."
        complaint.status = "in_progress"
    elif action == "transfer_hr":
        complaint.admin_reply = message or "Chuyển HR xử lý."
        complaint.status = "in_progress"
    elif action == "resolve":
        complaint.admin_reply = message or "Đánh dấu đã giải quyết."
        complaint.status = "resolved"
        complaint.resolved_at = datetime.utcnow()
    elif action == "reopen_payroll":
        complaint.admin_reply = message or "Mở lại payroll do complaint hợp lệ."
        complaint.status = "in_progress"
        if complaint.salary_id:
            salary = Salary.query.get(complaint.salary_id)
            if salary and salary.status in {"locked", "finalized"}:
                salary.status = "pending_approval"
    else:
        return jsonify({"error": "Action không hợp lệ"}), 400
    db.session.add(HistoryLog(action="HANDLE_PAYROLL_COMPLAINT", entity_type="salary", entity_id=complaint.salary_id, description=f"complaint={complaint.id}|{action}|{message}", performed_by=actor.id if actor else None))
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.get("/api/admin/payroll/audit")
def payroll_audit():
    rows = HistoryLog.query.filter_by(entity_type="salary").order_by(HistoryLog.created_at.desc()).limit(200).all()
    return jsonify([{
        "id": r.id,
        "time": r.created_at.isoformat() if r.created_at else None,
        "action": r.action,
        "description": r.description,
        "by": r.performed_by,
    } for r in rows])


@admin_bp.get("/api/admin/payroll/export")
def payroll_export():
    query, month, year = _payroll_filtered_query()
    rows = [_payroll_row(r) for r in query.order_by(Salary.id.asc()).all()]
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["employee_code", "employee_name", "department", "position", "basic_salary", "allowance", "deduction", "ot", "tax", "net_salary", "status", "has_complaint"])
    for row in rows:
        writer.writerow([row["employee_code"], row["employee_name"], row["department"], row["position"], row["basic_salary"], row["allowance"], row["deduction"], row["ot"], row["tax"], row["net_salary"], row["status_label"], "yes" if row["has_complaint"] else "no"])
    return Response(buffer.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=payroll_{year}_{month:02d}.csv"})


@admin_bp.get("/api/admin/system-settings/salary")
def salary_setting_get():
    keys = ["salary.standard_days", "salary.ot_multiplier", "salary.tax_percent"]
    result = {}
    defaults = {"salary.standard_days": "22", "salary.ot_multiplier": "1.5", "salary.tax_percent": "10"}
    for k in keys:
        row = SystemSetting.query.filter_by(key=k).first()
        result[k] = row.value if row else defaults[k]
    return jsonify(result)

@admin_bp.get("/api/admin/salary-policy")
def admin_salary_policy_get():
    return jsonify(PayrollPolicyService.get_policy())


@admin_bp.put("/api/admin/salary-policy")
def admin_salary_policy_put():
    actor = _current_user()
    payload = request.get_json(silent=True) or {}
    try:
        data = PayrollPolicyService.update_policy(payload, actor_user_id=actor.id if actor else None)
        return jsonify({"success": True, "policy": data})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409


@admin_bp.post("/api/admin/salary-policy/lock-edit")
def admin_salary_policy_lock_edit():
    actor = _current_user()
    payload = request.get_json(silent=True) or {}
    locked = bool(payload.get("locked", True))
    PayrollPolicyService.set_edit_lock(locked, actor_user_id=actor.id if actor else None)
    return jsonify({"success": True, "locked": locked})


@admin_bp.get("/api/admin/salary-policy/history")
def admin_salary_policy_history():
    rows = (
        HistoryLog.query.filter_by(entity_type="salary_policy")
        .order_by(HistoryLog.created_at.desc())
        .limit(50)
        .all()
    )
    return jsonify(
        [
            {
                "id": row.id,
                "action": row.action,
                "description": row.description,
                "time": row.created_at.isoformat() if row.created_at else None,
                "by": row.performed_by,
            }
            for row in rows
        ]
    )


@admin_bp.post("/api/admin/salary-policy/restore")
def admin_salary_policy_restore():
    actor = _current_user()
    payload = request.get_json(silent=True) or {}
    history_id = int(payload.get("history_id") or 0)
    row = HistoryLog.query.filter_by(id=history_id, entity_type="salary_policy").first()
    if not row or row.action != "UPDATE_SALARY_POLICY":
        return jsonify({"error": "Không tìm thấy bản cấu hình hợp lệ để khôi phục"}), 404
    import ast
    try:
        raw_policy = ast.literal_eval(row.description or "{}")
        data = PayrollPolicyService.update_policy(raw_policy, actor_user_id=actor.id if actor else None)
        db.session.add(
            HistoryLog(
                action="RESTORE_SALARY_POLICY",
                entity_type="salary_policy",
                description=f"restore_from={history_id}",
                performed_by=actor.id if actor else None,
            )
        )
        db.session.commit()
        return jsonify({"success": True, "policy": data})
    except Exception:
        return jsonify({"error": "Dữ liệu history không thể restore"}), 400

@admin_bp.put("/api/admin/system-settings/salary")
def salary_setting_put():
    actor = _current_user()
    data = request.get_json(silent=True) or {}
    for k, v in data.items():
        row = SystemSetting.query.filter_by(key=k).first()
        if not row:
            row = SystemSetting(key=k, value=str(v))
            db.session.add(row)
        else:
            row.value = str(v)
    db.session.add(HistoryLog(action="UPDATE_SALARY_CONFIG", entity_type="salary", description="salary settings", performed_by=actor.id if actor else None))
    db.session.commit()
    return jsonify({"success": True})