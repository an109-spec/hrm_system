from datetime import date, datetime, timedelta
from sqlalchemy import and_

from app.extensions.db import db
from app.models.employee import Employee
from app.models.department import Department
from app.models.attendance import Attendance, AttendanceStatus
from app.models.leave import LeaveRequest
from app.models.leave_usage import EmployeeLeaveUsage
from app.models.contract import Contract
from app.models.salary import Salary
from app.models.notification import Notification


class ManagerService:

    # =========================
    # DASHBOARD
    # =========================
    @staticmethod
    def get_dashboard(manager_id: int):
        manager = Employee.query.get(manager_id)

        employees = manager.subordinates

        total = len(employees)
        working = len([e for e in employees if e.working_status == 'working'])
        on_leave = len([e for e in employees if e.working_status == 'on_leave'])

        today = date.today()

        late_count = 0
        absent_count = 0

        for e in employees:
            att = Attendance.query.filter_by(employee_id=e.id, date=today).first()
            if not att:
                absent_count += 1
            elif att.status and att.status.status_name == "LATE":
                late_count += 1

        pending_leave = LeaveRequest.query.filter(
            LeaveRequest.employee_id.in_([e.id for e in employees]),
            LeaveRequest.status == 'pending'
        ).count()

        return {
            "total": total,
            "working": working,
            "on_leave": on_leave,
            "late": late_count,
            "absent": absent_count,
            "pending_leave": pending_leave
        }

    # =========================
    # TODAY ATTENDANCE
    # =========================
    @staticmethod
    def get_today_attendance(manager_id: int):
        manager = Employee.query.get(manager_id)
        employees = manager.subordinates
        today = date.today()

        data = []

        for e in employees:
            att = Attendance.query.filter_by(employee_id=e.id, date=today).first()

            if not att:
                status = "ABSENT"
            else:
                status = att.status.status_name if att.status else "UNKNOWN"

            data.append({
                "employee_id": e.id,
                "name": e.full_name,
                "check_in": str(att.check_in) if att else None,
                "check_out": str(att.check_out) if att else None,
                "status": status
            })

        return data

    # =========================
    # LEAVE LIST
    # =========================
    @staticmethod
    def get_leave_requests(manager_id: int, status=None):
        manager = Employee.query.get(manager_id)
        sub_ids = [e.id for e in manager.subordinates]

        query = LeaveRequest.query.filter(
            LeaveRequest.employee_id.in_(sub_ids)
        )

        if status:
            query = query.filter_by(status=status)

        return query.order_by(LeaveRequest.created_at.desc()).all()

    # =========================
    # APPROVE LEAVE
    # =========================
    @staticmethod
    def approve_leave(manager_id: int, leave_id: int, note=None):
        leave = LeaveRequest.query.get(leave_id)

        if not leave:
            raise ValueError("Leave not found")

        leave.status = "approved"
        leave.approved_by = manager_id

        # update leave usage
        usage = EmployeeLeaveUsage.query.filter_by(
            employee_id=leave.employee_id,
            year=date.today().year
        ).first()

        if usage:
            days = (leave.to_date - leave.from_date).days + 1
            usage.used_days += days
            usage.update_balance()

        # notification
        emp = Employee.query.get(leave.employee_id)
        if emp and emp.user_id:
            db.session.add(Notification(
                user_id=emp.user_id,
                title="Đơn nghỉ phép đã được duyệt",
                content="Đơn nghỉ của bạn đã được duyệt",
                type="leave"
            ))

        db.session.commit()
        return leave

    # =========================
    # REJECT LEAVE
    # =========================
    @staticmethod
    def reject_leave(manager_id: int, leave_id: int, note=None):
        leave = LeaveRequest.query.get(leave_id)

        if not leave:
            raise ValueError("Leave not found")

        leave.status = "rejected"
        leave.approved_by = manager_id

        emp = Employee.query.get(leave.employee_id)
        if emp and emp.user_id:
            db.session.add(Notification(
                user_id=emp.user_id,
                title="Đơn nghỉ phép bị từ chối",
                content="Đơn nghỉ của bạn đã bị từ chối",
                type="leave"
            ))

        db.session.commit()
        return leave

    # =========================
    # REMINDER
    # =========================
    @staticmethod
    def send_reminder(employee_ids, message=None):
        for emp_id in employee_ids:
            emp = Employee.query.get(emp_id)
            if emp and emp.user_id:
                db.session.add(Notification(
                    user_id=emp.user_id,
                    title="Nhắc nhở chấm công",
                    content=message or "Bạn chưa check-in hôm nay",
                    type="reminder"
                ))

        db.session.commit()
        return True

    # =========================
    # CONTRACT EXPIRING
    # =========================
    @staticmethod
    def get_contract_expiring(manager_id: int):
        manager = Employee.query.get(manager_id)
        sub_ids = [e.id for e in manager.subordinates]

        today = date.today()
        limit = today + timedelta(days=30)

        return Contract.query.filter(
            Contract.employee_id.in_(sub_ids),
            Contract.end_date != None,
            Contract.end_date <= limit,
            Contract.status == 'active'
        ).all()

    # =========================
    # RENEW CONTRACT
    # =========================
    @staticmethod
    def renew_contract(data):
        old_contract = Contract.query.filter_by(
            employee_id=data.employee_id,
            status='active'
        ).first()

        if old_contract:
            old_contract.status = 'expired'

        new_contract = Contract(
            employee_id=data.employee_id,
            contract_code=data.contract_code,
            basic_salary=data.basic_salary,
            start_date=data.start_date,
            end_date=data.end_date,
            status='active'
        )

        db.session.add(new_contract)
        db.session.commit()

        return new_contract

    # =========================
    # PAYROLL
    # =========================
    @staticmethod
    def get_department_salary(manager_id: int, month: int, year: int):
        manager = Employee.query.get(manager_id)
        sub_ids = [e.id for e in manager.subordinates]

        return Salary.query.filter(
            Salary.employee_id.in_(sub_ids),
            Salary.month == month,
            Salary.year == year
        ).all()