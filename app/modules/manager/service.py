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
from app.models.history import HistoryLog
from app.models.overtime_request import OvertimeRequest
from app.models.salary import Salary
from app.models.complaint import Complaint
from app.models.position import Position

class ManagerService:

    PAYROLL_REVIEWABLE_STATUSES = {"pending_manager", "manager_review"}
    PAYROLL_STATUS_LABELS = {
        "pending_hr": "Chờ HR xử lý",
        "pending_manager": "Chờ Manager xác nhận",
        "manager_review": "Chờ Manager xác nhận",
        "manager_confirmed": "Đã xác nhận",
        "pending_admin": "Chờ Admin duyệt",
        "approved": "Đã duyệt",
        "paid": "Đã chốt",
        "finalized": "Đã chốt",
        "complaint": "Khiếu nại",
        "pending": "Chờ HR xử lý",
    }
    @staticmethod
    def get_overtime_requests(manager_id: int) -> list[dict]:
        sub_ids = [e.id for e in ManagerService._get_subordinates(manager_id)]
        if not sub_ids:
            return []
        rows = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id.in_(sub_ids),
            OvertimeRequest.status == "pending_manager",
            OvertimeRequest.is_deleted.is_(False),
        ).order_by(OvertimeRequest.created_at.desc()).all()
        return [
            {
                "id": x.id,
                "employee_id": x.employee_id,
                "employee_name": x.employee.full_name if x.employee else "--",
                "overtime_date": x.overtime_date.isoformat(),
                "overtime_hours": float(x.overtime_hours or 0),
                "reason": x.reason,
                "note": x.note,
                "status": x.status,
            }
            for x in rows
        ]

    @staticmethod
    def review_overtime(manager_id: int, overtime_id: int, action: str, note: str | None = None):
        request_ot = OvertimeRequest.query.get(overtime_id)
        if not request_ot or request_ot.is_deleted:
            raise ValueError("Không tìm thấy yêu cầu OT")
        if request_ot.employee_id not in [e.id for e in ManagerService._get_subordinates(manager_id)]:
            raise ValueError("Không có quyền xử lý yêu cầu OT này")
        if request_ot.status != "pending_manager":
            raise ValueError("Yêu cầu OT đã được xử lý")
        if action not in {"approve", "reject"}:
            raise ValueError("Hành động không hợp lệ")

        request_ot.manager_decision_by = manager_id
        request_ot.manager_decision_at = datetime.utcnow()
        request_ot.manager_note = note
        if action == "approve":
            request_ot.status = "pending_hr"
        else:
            request_ot.status = "rejected"
            request_ot.rejection_reason = note or "Manager từ chối"

        employee = Employee.query.get(request_ot.employee_id)
        if employee and employee.user_id:
            title = "Yêu cầu tăng ca đã được quản lý duyệt" if action == "approve" else "Yêu cầu tăng ca bị từ chối"
            db.session.add(Notification(user_id=employee.user_id, title=title, content=note or "", type="overtime", link="/employee/attendance"))
        db.session.add(HistoryLog(employee_id=request_ot.employee_id, action="MANAGER_OVERTIME_REVIEW", entity_type="overtime_request", entity_id=request_ot.id, description=f"Manager {action} overtime request", performed_by=manager_id))
        db.session.commit()
        return request_ot
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

        if not rows: # type: ignore
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
            for l in rows # pyright: ignore[reportUndefinedVariable]
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
    def _normalize_payroll_status(status: str | None) -> str:
        if not status:
            return "pending_hr"
        return status.strip().lower()

    @staticmethod
    def _payroll_status_label(status: str | None) -> str:
        normalized = ManagerService._normalize_payroll_status(status)
        return ManagerService.PAYROLL_STATUS_LABELS.get(normalized, status or "Chưa xác định")

    @staticmethod
    def _tax_and_insurance(salary: Salary) -> tuple[float, float]:
        basic = float(salary.basic_salary or 0)
        worked_ratio = 1.0
        if salary.standard_work_days and float(salary.standard_work_days) > 0:
            worked_ratio = max(float(salary.total_work_days or 0) / float(salary.standard_work_days), 0)
        gross = (basic * worked_ratio) + float(salary.total_allowance or 0) + float(salary.bonus or 0)
        insurance = gross * 0.105
        taxable = max(gross - insurance - 11_000_000, 0)
        tax = taxable * 0.05
        return round(insurance, 2), round(tax, 2)

    @staticmethod
    def get_department_payroll_review(
        manager_id: int,
        month: int,
        year: int,
        employee_name: str | None = None,
        employee_code: str | None = None,
        status: str | None = None,
        employment_type: str | None = None,
        position: str | None = None,
    ) -> dict:
        employees = ManagerService._get_subordinates(manager_id)
        sub_ids = [e.id for e in employees]
        if not sub_ids:
            return {"summary": {}, "items": []}

        query = Salary.query.join(Employee, Salary.employee_id == Employee.id).filter(
            Salary.employee_id.in_(sub_ids),
            Salary.month == month,
            Salary.year == year,
            Salary.is_deleted.is_(False),
        )
        if employee_name:
            query = query.filter(Employee.full_name.ilike(f"%{employee_name.strip()}%"))
        if employee_code:
            code = employee_code.strip().upper()
            query = query.filter(db.cast(Salary.employee_id, db.String).ilike(f"%{code.replace('EMP', '')}%"))
        if status:
            query = query.filter(Salary.status == status.strip().lower())
        if employment_type:
            query = query.filter(Employee.employment_type == employment_type)
        if position:
            query = query.filter(Employee.position.has(Position.job_title.ilike(f"%{position.strip()}%")))

        rows = query.order_by(Employee.full_name.asc()).all()
        complaint_salary_ids = {
            c.salary_id
            for c in Complaint.query.filter(
                Complaint.salary_id.in_([x.id for x in rows]),
                Complaint.status.in_(["pending", "in_progress"]),
                Complaint.is_deleted.is_(False),
            ).all()
            if c.salary_id
        }
        items: list[dict] = []
        total_net = 0.0
        pending_manager_count = 0
        abnormal_count = 0
        for salary in rows:
            insurance, tax = ManagerService._tax_and_insurance(salary)
            status_code = ManagerService._normalize_payroll_status(salary.status)
            if status_code in ManagerService.PAYROLL_REVIEWABLE_STATUSES:
                pending_manager_count += 1

            attendance = Attendance.query.filter_by(
                employee_id=salary.employee_id,
                is_deleted=False,
            ).filter(
                db.extract("month", Attendance.date) == month,
                db.extract("year", Attendance.date) == year,
            ).all()
            leave_days = LeaveRequest.query.filter(
                LeaveRequest.employee_id == salary.employee_id,
                LeaveRequest.status == "approved",
                db.extract("month", LeaveRequest.from_date) == month,
                db.extract("year", LeaveRequest.from_date) == year,
            ).count()
            overtime_hours = float(sum((a.overtime_hours or 0) for a in attendance))
            actual_work_days = float(sum((a.working_hours or 0) for a in attendance)) / 8 if attendance else float(salary.total_work_days or 0)
            abnormal = overtime_hours > 60 or actual_work_days < 10
            if abnormal:
                abnormal_count += 1

            net = float(salary.net_salary or 0)
            total_net += net
            items.append(
                {
                    "salary_id": salary.id,
                    "employee_id": salary.employee_id,
                    "employee_code": f"EMP{salary.employee_id:04d}",
                    "employee_name": salary.employee.full_name if salary.employee else "--",
                    "department": salary.employee.department.department_name if salary.employee and salary.employee.department else "--",
                    "position": salary.employee.position.job_title if salary.employee and salary.employee.position else "--",
                    "basic_salary": float(salary.basic_salary or 0),
                    "actual_work_days": round(actual_work_days, 2),
                    "leave_days": leave_days,
                    "overtime_hours": round(overtime_hours, 2),
                    "allowance": float(salary.total_allowance or 0),
                    "deduction": float(salary.penalty or 0),
                    "insurance": insurance,
                    "tax": tax,
                    "net_salary": net,
                    "status": status_code,
                    "status_label": ManagerService._payroll_status_label(status_code),
                    "has_complaint": salary.id in complaint_salary_ids,
                    "is_abnormal": abnormal,
                }
            )

        return {
            "summary": {
                "total_payroll_fund": round(total_net, 2),
                "calculated_employees": len(rows),
                "pending_confirmation": pending_manager_count,
                "complaints": len(complaint_salary_ids),
                "abnormal": abnormal_count,
                "unfinalized": len([x for x in rows if ManagerService._normalize_payroll_status(x.status) != "paid"]),
            },
            "items": items,
        }

    @staticmethod
    def get_department_payroll_detail(manager_id: int, salary_id: int) -> dict:
        sub_ids = [e.id for e in ManagerService._get_subordinates(manager_id)]
        row = Salary.query.filter_by(id=salary_id, is_deleted=False).first()
        if not row or row.employee_id not in sub_ids:
            raise ValueError("Không có quyền truy cập payroll này")
        insurance, tax = ManagerService._tax_and_insurance(row)
        return {
            "salary_id": row.id,
            "employee_name": row.employee.full_name if row.employee else "--",
            "basic_salary": float(row.basic_salary or 0),
            "allowance": float(row.total_allowance or 0),
            "bonus": float(row.bonus or 0),
            "overtime": 0,
            "deduction": float(row.penalty or 0),
            "insurance": insurance,
            "tax": tax,
            "net_salary": float(row.net_salary or 0),
            "status": ManagerService._normalize_payroll_status(row.status),
            "status_label": ManagerService._payroll_status_label(row.status),
        }

    @staticmethod
    def confirm_department_payroll(manager_id: int, salary_id: int, note: str | None = None) -> dict:
        sub_ids = [e.id for e in ManagerService._get_subordinates(manager_id)]
        row = Salary.query.filter_by(id=salary_id, is_deleted=False).first()
        if not row or row.employee_id not in sub_ids:
            raise ValueError("Không có quyền xác nhận payroll này")
        if ManagerService._normalize_payroll_status(row.status) not in ManagerService.PAYROLL_REVIEWABLE_STATUSES:
            raise ValueError("Payroll không ở trạng thái chờ Manager xác nhận")
        row.status = "pending_admin"
        row.note = f"{(row.note or '').strip()}\n[Manager Confirm] {note or 'Đã kiểm tra hợp lệ'}".strip()
        db.session.add(
            HistoryLog(
                employee_id=row.employee_id,
                action="MANAGER_PAYROLL_CONFIRMED",
                entity_type="salary",
                entity_id=row.id,
                description=f"Manager xác nhận payroll #{row.id}",
                performed_by=manager_id,
            )
        )
        if row.employee and row.employee.user_id:
            db.session.add(Notification(user_id=row.employee.user_id, title="Payroll đã được Manager xác nhận", content=f"Payroll tháng {row.month}/{row.year} đang chờ Admin duyệt.", type="salary"))
        db.session.commit()
        return {"message": "Đã xác nhận payroll, chuyển trạng thái Chờ Admin duyệt", "status": row.status}

    @staticmethod
    def send_payroll_feedback(manager_id: int, salary_id: int, issue_type: str, description: str) -> dict:
        sub_ids = [e.id for e in ManagerService._get_subordinates(manager_id)]
        row = Salary.query.filter_by(id=salary_id, is_deleted=False).first()
        if not row or row.employee_id not in sub_ids:
            raise ValueError("Không có quyền gửi phản hồi payroll này")
        complaint = Complaint(
            employee_id=row.employee_id,
            handled_by=manager_id,
            salary_id=row.id,
            type=issue_type or "salary_data_error",
            title=f"[Manager Feedback] Payroll {row.month}/{row.year} - {row.employee.full_name if row.employee else row.employee_id}",
            description=description.strip(),
            status="in_progress",
            priority="high",
        )
        row.status = "pending_hr"
        db.session.add(complaint)
        db.session.add(
            HistoryLog(
                employee_id=row.employee_id,
                action="MANAGER_PAYROLL_FEEDBACK",
                entity_type="salary",
                entity_id=row.id,
                description=f"Manager phản hồi payroll #{row.id}",
                performed_by=manager_id,
            )
        )
        db.session.commit()
        return {"message": "Đã gửi phản hồi bất thường về HR", "complaint_id": complaint.id}

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