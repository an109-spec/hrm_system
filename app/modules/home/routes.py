from . import home_bp
from flask import render_template
from flask import jsonify, session
from datetime import date

from . import home_bp

from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.salary import Salary
from app.models.leave_usage import EmployeeLeaveUsage
from app.models.notification import Notification


# =========================
# Helper
# =========================
def get_user_id():
    return session.get("user_id")


def get_employee(user_id):
    return Employee.query.filter_by(user_id=user_id).first()


# =========================
# DASHBOARD AGGREGATOR API
# =========================
@home_bp.route("/dashboard", methods=["GET"])
def dashboard():
    user_id = get_user_id()

    emp = get_employee(user_id)
    if not emp:
        return jsonify({"error": "Employee not found"}), 404

    today = date.today()
    current_year = today.year
    current_month = today.month

    # =========================
    # 1. ATTENDANCE TODAY
    # =========================
    attendance = Attendance.query.filter_by(
        employee_id=emp.id,
        date=today
    ).first()

    today_working_hours = float(attendance.working_hours) if attendance and attendance.working_hours else 0.0

    attendance_status = None
    check_in = None
    check_out = None

    if attendance:
        attendance_status = attendance.status.status_name if attendance.status else None
        check_in = attendance.check_in.isoformat() if attendance.check_in else None
        check_out = attendance.check_out.isoformat() if attendance.check_out else None

    # =========================
    # 2. LEAVE BALANCE
    # =========================
    leave = EmployeeLeaveUsage.query.filter_by(
        employee_id=emp.id,
        year=current_year
    ).first()

    remaining_days = leave.remaining_days if leave else 12

    # =========================
    # 3. LATEST SALARY
    # =========================
    salary = (
        Salary.query
        .filter_by(employee_id=emp.id, status="paid")
        .order_by(Salary.year.desc(), Salary.month.desc())
        .first()
    )

    latest_salary = {
        "month": f"{salary.month}/{salary.year}" if salary else None,
        "net_salary": float(salary.net_salary) if salary else 0
    }

    # =========================
    # 4. NOTIFICATIONS (LATEST 5)
    # =========================
    notifications = (
        Notification.query
        .filter_by(user_id=user_id)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )

    notification_list = [
        {
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "type": n.type,
            "is_read": n.is_read,
            "link": n.link,
            "created_at": n.created_at.isoformat()
        }
        for n in notifications
    ]

    # =========================
    # RESPONSE (MATCH UI DASHBOARD)
    # =========================
    return jsonify({
        "profile": {
            "employee_id": emp.id,
            "full_name": emp.full_name,
            "avatar": emp.avatar,
            "position": emp.position.job_title if emp.position else None,
            "status": emp.working_status,
        },

        "attendance_today": {
            "date": today.isoformat(),
            "working_hours": today_working_hours,
            "check_in": check_in,
            "check_out": check_out,
            "status": attendance_status
        },

        "summary": {
            "working_hours_today": today_working_hours,
            "remaining_leave_days": remaining_days,
            "latest_salary": latest_salary
        },

        "notifications": notification_list
    })
@home_bp.route('/support')
def support_page():
    return render_template('home/support.html')