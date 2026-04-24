from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from sqlalchemy import or_
from app.extensions.db import db
from app.models.attendance import Attendance
from app.models.contract import Contract
from app.models.department import Department
from app.models.employee import Employee

from app.models.leave import LeaveRequest
from app.models.leave_usage import EmployeeLeaveUsage

from app.models.notification import Notification
from app.models.salary import Salary

class ManagerService:

    @staticmethod
    def _get_subordinates(manager_id: int) -> list[Employee]:
        manager = Employee.query.get(manager_id)
        if not manager:
            return []
        direct_subordinates = [
            emp for emp in manager.subordinates if not getattr(emp, "is_deleted", False)
        ]
        if direct_subordinates:
            return direct_subordinates

        managed_department = Department.query.filter_by(manager_id=manager_id).first()
        if not managed_department:
            return []

        return [
            emp
            for emp in managed_department.employees
            if emp.id != manager_id and not getattr(emp, "is_deleted", False)
        ]
    @staticmethod
    def _approved_leave_employee_ids(employee_ids: list[int], target_date: date) -> set[int]:
        if not employee_ids:
            return set()
        rows = LeaveRequest.query.filter(
            LeaveRequest.employee_id.in_(employee_ids),
            LeaveRequest.status == "approved",
            LeaveRequest.from_date <= target_date,
            LeaveRequest.to_date >= target_date,
        ).all()
        return {row.employee_id for row in rows}

    @staticmethod
    def _attendance_to_status(att: Attendance | None, on_leave: bool) -> str:
        if on_leave:
            return "LEAVE"
        if not att or not att.check_in:
            return "ABSENT"
        if att.status and att.status.status_name:
            return att.status.status_name
        return "ON_TIME"

    @staticmethod
    def get_dashboard(manager_id: int) -> dict:
        employees = ManagerService._get_subordinates(manager_id)
        ids = [e.id for e in employees]

        today = date.today()
        leave_ids = ManagerService._approved_leave_employee_ids(ids, today)
        late_count = 0
        absent_count = 0
        working_count = 0
        for e in employees:
            att = Attendance.query.filter_by(employee_id=e.id, date=today).first()
            status = ManagerService._attendance_to_status(att, e.id in leave_ids)
            if status in {"ON_TIME", "PRESENT"}:
                working_count += 1
            elif status == "LATE":
                late_count += 1
                working_count += 1
            elif status == "ABSENT":
                absent_count += 1
        pending_leave = (
            LeaveRequest.query.filter(
                LeaveRequest.employee_id.in_(ids),
                LeaveRequest.status == "pending",
            ).count()
            if ids
            else 0
        )

        return {
            "total": len(employees),
            "working": working_count,
            "on_leave": len(leave_ids),
            "late": late_count,
            "absent": absent_count,
            "pending_leave": pending_leave,
        }


    @staticmethod
    def get_today_attendance(manager_id: int) -> list[dict]:
        employees = ManagerService._get_subordinates(manager_id)
        ids = [e.id for e in employees]
        today = date.today()
        leave_ids = ManagerService._approved_leave_employee_ids(ids, today)
        data: list[dict] = []

        for e in employees:
            att = Attendance.query.filter_by(employee_id=e.id, date=today).first()

            status = ManagerService._attendance_to_status(att, e.id in leave_ids)
            data.append(
                {
                    "employee_id": e.id,
                    "name": e.full_name,
                    "position": e.position.job_title if e.position else "--",
                    "check_in": att.check_in.strftime("%H:%M") if att and att.check_in else None,
                    "check_out": att.check_out.strftime("%H:%M") if att and att.check_out else None,
                    "status": status,
                }
            )

        return data


    @staticmethod
    def get_leave_requests(manager_id: int, status: str | None = None) -> list[dict]:
        employees = ManagerService._get_subordinates(manager_id)
        sub_ids = [e.id for e in employees]
        if not sub_ids:
            # Fallback theo người duyệt được chỉ định trên đơn
            query = LeaveRequest.query.filter(LeaveRequest.approved_by == manager_id)
        else:
            query = LeaveRequest.query.filter(
                or_(
                    LeaveRequest.employee_id.in_(sub_ids),
                    LeaveRequest.approved_by == manager_id,
                )
            )

        if status:
            query = query.filter(LeaveRequest.status == status)

        if not rows:
            return []
        return [
            {
                "id": l.id,
                "employee_id": l.employee_id,
                "name": l.employee.full_name if l.employee else "--",
                "type": l.leave_type.name if l.leave_type else "--",
                "from": l.from_date.isoformat(),
                "to": l.to_date.isoformat(),
                "status": l.status,
                "reason": l.reason or "",
                "created_at": l.created_at.date().isoformat() if l.created_at else None,
                "days": (l.to_date - l.from_date).days + 1,
            }
            for l in rows
        ]

    @staticmethod
    def _ensure_leave_in_scope(manager_id: int, leave_id: int) -> LeaveRequest:
        leave = LeaveRequest.query.get(leave_id)

        if not leave:
            raise ValueError("Không tìm thấy đơn nghỉ phép")
        sub_ids = [e.id for e in ManagerService._get_subordinates(manager_id)]
        can_process = leave.employee_id in sub_ids or leave.approved_by == manager_id
        if not can_process:
            raise ValueError("Không có quyền xử lý đơn này")
        return leave
    @staticmethod
    def approve_leave(manager_id: int, leave_id: int, note: str | None = None) -> LeaveRequest:
        leave = ManagerService._ensure_leave_in_scope(manager_id, leave_id)
        leave.status = "approved"
        leave.approved_by = manager_id

        usage = EmployeeLeaveUsage.query.filter_by(
            employee_id=leave.employee_id,
            year=leave.from_date.year,
        ).first()

        is_annual_leave = bool(leave.leave_type and leave.leave_type.name == "Nghỉ phép năm")
        if usage and is_annual_leave:
            days = (leave.to_date - leave.from_date).days + 1
            usage.used_days = Decimal(usage.used_days or 0) + Decimal(days)
            usage.update_balance()

        emp = Employee.query.get(leave.employee_id)
        if emp and emp.user_id:
            db.session.add(
                Notification(
                    user_id=emp.user_id,
                    title="Đơn nghỉ phép đã được duyệt",
                    content=note or "Đơn nghỉ của bạn đã được quản lý duyệt.",
                    type="leave",
                )
            )

        db.session.commit()
        return leave

    @staticmethod
    def reject_leave(manager_id: int, leave_id: int, note: str | None = None) -> LeaveRequest:
        leave = ManagerService._ensure_leave_in_scope(manager_id, leave_id)

        leave.status = "rejected"
        leave.approved_by = manager_id

        emp = Employee.query.get(leave.employee_id)
        if emp and emp.user_id:
            db.session.add(
                Notification(
                    user_id=emp.user_id,
                    title="Đơn nghỉ phép bị từ chối",
                    content=note or "Đơn nghỉ của bạn đã bị từ chối.",
                    type="leave",
                )
            )

        db.session.commit()
        return leave

    @staticmethod
    def send_reminder(employee_ids: list[int], message: str | None = None) -> bool:
        if not employee_ids:
            return True

        employees = Employee.query.filter(Employee.id.in_(employee_ids)).all()
        for emp in employees:
            if emp.user_id:
                db.session.add(
                    Notification(
                        user_id=emp.user_id,
                        title="Nhắc nhở chấm công",
                        content=message
                        or f"Chào {emp.full_name}, bạn chưa thực hiện check-in hôm nay. Vui lòng kiểm tra lại thiết bị hoặc báo quản lý nếu có sai sót.",
                        type="reminder",
                    )
                )

        db.session.commit()
        return True


    @staticmethod
    def get_contract_expiring(manager_id: int) -> list[dict]:
        sub_ids = [e.id for e in ManagerService._get_subordinates(manager_id)]
        if not sub_ids:
            return []

        today = date.today()
        limit = today + timedelta(days=30)
        rows = (
            Contract.query.filter(
                Contract.employee_id.in_(sub_ids),
                Contract.status == "active",
                Contract.end_date.isnot(None),
                Contract.end_date <= limit,
            )
            .order_by(Contract.end_date.asc())
            .all()
        )
        data = []
        for c in rows:
            remaining_days = (c.end_date - today).days if c.end_date else None
            data.append(
                {
                    "id": c.id,
                    "employee_id": c.employee_id,
                    "employee_name": c.employee.full_name if c.employee else "--",
                    "contract_code": c.contract_code,
                    "start_date": c.start_date.isoformat() if c.start_date else None,
                    "end_date": c.end_date.isoformat() if c.end_date else None,
                    "basic_salary": float(c.basic_salary or 0),
                    "days_left": remaining_days,
                }
            )
        return data


    @staticmethod
    def renew_contract(data: dict) -> Contract:
        employee_id = int(data.get("employee_id"))
        old_contract = Contract.query.filter_by(employee_id=employee_id, status="active").first()
        if old_contract:
            old_contract.status = "expired"

        start_date = datetime.strptime(data.get("start_date"), "%Y-%m-%d").date()
        end_raw = data.get("end_date")
        end_date = datetime.strptime(end_raw, "%Y-%m-%d").date() if end_raw else None
        new_contract = Contract(
        employee_id=employee_id,
        contract_code=data.get("contract_code"),
        basic_salary=Decimal(str(data.get("basic_salary", 0))),
        start_date=start_date,
        end_date=end_date,
        status="active",
        )

        db.session.add(new_contract)
        emp = Employee.query.get(employee_id)
        if emp and emp.user_id:
            db.session.add(
                Notification(
                    user_id=emp.user_id,
                    title="Hợp đồng đã được gia hạn",
                    content=f"Hợp đồng mới ({new_contract.contract_code}) đã được tạo.",
                    type="contract",
                )
            )

        db.session.commit()

        return new_contract

    # =========================
    # PAYROLL
    # =========================
    @staticmethod
    def get_department_salary(manager_id: int, month: int, year: int) -> list[dict]:
        sub_ids = [e.id for e in ManagerService._get_subordinates(manager_id)]
        if not sub_ids:
            return []

        rows = (
            Salary.query.filter(
                Salary.employee_id.in_(sub_ids),
                Salary.month == month,
                Salary.year == year,
            )
            .order_by(Salary.employee_id.asc())
            .all()
        )

        return [
            {
                "name": s.employee.full_name if s.employee else "--",
                "basic_salary": float(s.basic_salary or 0),
                "allowance": float(s.total_allowance or 0),
                "net_salary": float(s.net_salary or 0),
                "status": s.status,
            }
            for s in rows
        ]

    @staticmethod
    def get_month_attendance_summary(manager_id: int, month: int, year: int) -> list[dict]:
        employees = ManagerService._get_subordinates(manager_id)
        results = []
        for e in employees:
            records = Attendance.query.filter(
                Attendance.employee_id == e.id,
                db.extract("month", Attendance.date) == month,
                db.extract("year", Attendance.date) == year,
            ).all()

            on_time = 0
            late = 0
            absent = 0
            leave = 0
            abnormal_days = []

            for r in records:
                status = r.status.status_name if r.status else "UNKNOWN"
                if status in {"ON_TIME", "PRESENT"}:
                    on_time += 1
                elif status == "LATE":
                    late += 1
                    abnormal_days.append(
                        {
                            "date": r.date.isoformat(),
                            "status": "LATE",
                            "check_in": r.check_in.strftime("%H:%M") if r.check_in else None,
                            "check_out": r.check_out.strftime("%H:%M") if r.check_out else None,
                            "multiplier": 0.5,
                        }
                    )
                elif status == "LEAVE":
                    leave += 1
                else:
                    absent += 1
                    abnormal_days.append(
                        {
                            "date": r.date.isoformat(),
                            "status": "ABSENT",
                            "check_in": None,
                            "check_out": None,
                            "multiplier": 0,
                        }
                    )

            total_work_day = on_time + (late * 0.5) + leave
            results.append(
                {
                    "employee_id": e.id,
                    "name": e.full_name,
                    "phone": e.phone,
                    "on_time": on_time,
                    "late": late,
                    "absent": absent,
                    "leave": leave,
                    "total_work_day": total_work_day,
                    "abnormal_days": abnormal_days,
                }
            )

        return results