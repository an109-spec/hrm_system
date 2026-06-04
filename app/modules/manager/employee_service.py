from datetime import timedelta
from sqlalchemy import or_
from app.constants.contract import ContractStatus
from app.models.base import db
from app.models.employee import Employee
from app.models.attendance import Attendance, AttendanceStatus
from app.models.contract import Contract
from app.models.leave import LeaveRequest 
from app.constants.employee import WorkingStatus, EmploymentType
from .attendance_service import AttendanceManagerService
from app.utils.time import get_current_time
class EmployeeService:
    @staticmethod
    def get_department_employee_summary(manager_id: int) -> dict:
        employees =AttendanceManagerService._get_subordinates(manager_id)
        result = {
            "total_employees": 0,
            "active_employees": 0,
            "probation_employees": 0,
            "expiring_contracts": 0
        }
        if not employees:
            return result
        emp_ids = [e.id for e in employees]
        today = get_current_time().date()
        thirty_days_later = today + timedelta(days=30)
        active_contracts = Contract.query.filter(
            Contract.employee_id.in_(emp_ids),
            Contract.status == ContractStatus.ACTIVE,
            Contract.is_deleted.is_(False)
        ).all()
        for emp in employees:
            if emp.working_status == WorkingStatus.ACTIVE:
                result["active_employees"] += 1
            
            if emp.employment_type == EmploymentType.PROBATION:
                result["probation_employees"] += 1
        for contract in active_contracts:
            if contract.end_date and (today <= contract.end_date <= thirty_days_later):
                result["expiring_contracts"] += 1
        result["total_employees"] = len(employees)
        return result

    @staticmethod
    def get_department_employee_list(manager_id: int, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        employees = ManagerService._get_subordinates(manager_id)
        today = get_current_time().date()
        current_month = today.month
        current_year = today.year
        rows: list[dict] = []
        for emp in employees:
            latest_contract = ManagerService._latest_contract(emp.id)
            latest_salary = ManagerService._latest_salary(emp.id)
            today_attendance = Attendance.query.filter_by(employee_id=emp.id, date=today).first()
            today_leave = LeaveRequest.query.filter(
                LeaveRequest.employee_id == emp.id,
                LeaveRequest.status == "approved",
                LeaveRequest.from_date <= today,
                LeaveRequest.to_date >= today,
            ).first()
            monthly_leave_count = LeaveRequest.query.filter(
                LeaveRequest.employee_id == emp.id,
                LeaveRequest.status == "approved",
                db.extract("month", LeaveRequest.from_date) == current_month,
                db.extract("year", LeaveRequest.from_date) == current_year,
            ).count()
            complaint_count = Complaint.query.filter(
                Complaint.employee_id == emp.id,
                Complaint.status.in_(["pending", "in_progress"]),
                Complaint.is_deleted.is_(False),
            ).count()
            att_status = ManagerService._attendance_to_status(today_attendance, bool(today_leave))
            attendance_warning = Attendance.query.filter(
                Attendance.employee_id == emp.id,
                Attendance.date >= today - timedelta(days=30),
                Attendance.date <= today,
            ).join(Attendance.status, isouter=True).filter(
                or_(AttendanceStatus.status_name == "LATE", AttendanceStatus.status_name == "ABSENT")
            ).count() > 0
            rows.append(
                {
                    "employee_id": emp.id,
                    "employee_code": f"EMP{emp.id:04d}",
                    "full_name": emp.full_name,
                    "avatar": emp.avatar,
                    "position": emp.position.job_title if emp.position else "--",
                    "department": emp.department.name if emp.department else "--",
                    "hire_date": emp.hire_date.isoformat() if emp.hire_date else None,
                    "contract_type": (emp.employment_type or "").lower(),
                    "contract_type_label": ManagerService.EMPLOYMENT_LABELS.get((emp.employment_type or "").lower(), emp.employment_type or "--"),
                    "working_status": (emp.working_status or "").lower(),
                    "working_status_label": ManagerService.WORKING_STATUS_LABELS.get((emp.working_status or "").lower(), emp.working_status or "--"),
                    "attendance_today": att_status,
                    "leave_days_month": monthly_leave_count,
                    "payroll_status": ManagerService._normalize_payroll_status(latest_salary.status) if latest_salary else "N/A",
                    "payroll_status_label": ManagerService._payroll_status_label(latest_salary.status) if latest_salary else "--",
                    "is_on_leave_today": bool(today_leave),
                    "has_complaint": complaint_count > 0,
                    "attendance_warning": attendance_warning,
                    "is_probation": emp.employment_type == "probation",
                    "contract_end_date": latest_contract.end_date.isoformat() if latest_contract and latest_contract.end_date else None,
                }
            )

        name = (filters.get("name") or "").strip().lower()
        employee_code = (filters.get("employee_code") or "").strip().upper().replace("EMP", "")
        position = (filters.get("position") or "").strip().lower()
        working_status = (filters.get("working_status") or "").strip().lower()
        contract_type = (filters.get("contract_type") or "").strip().lower()
        probation = (filters.get("probation") or "").strip().lower()
        department = (filters.get("department") or "").strip().lower()
        leave_only = str(filters.get("leave_today", "")).lower() in {"1", "true", "yes"}
        complaint_only = str(filters.get("has_complaint", "")).lower() in {"1", "true", "yes"}

        def _matches(row: dict) -> bool:
            if name and name not in (row["full_name"] or "").lower():
                return False
            if employee_code and employee_code not in row["employee_code"].replace("EMP", ""):
                return False
            if position and position not in (row["position"] or "").lower():
                return False
            if working_status and working_status != row["working_status"]:
                return False
            if contract_type and contract_type != row["contract_type"]:
                return False
            if probation == "yes" and not row["is_probation"]:
                return False
            if probation == "no" and row["is_probation"]:
                return False
            if department and department not in (row["department"] or "").lower():
                return False
            if leave_only and not row["is_on_leave_today"]:
                return False
            if complaint_only and not row["has_complaint"]:
                return False
            return True

        return [x for x in rows if _matches(x)]

    @staticmethod
    def get_department_employee_detail(manager_id: int, employee_id: int) -> dict:
        subordinate_ids = {x.id for x in ManagerService._get_subordinates(manager_id)}
        if employee_id not in subordinate_ids:
            raise ValueError("Không có quyền xem nhân viên này")
        emp = Employee.query.get(employee_id)
        if not emp:
            raise ValueError("Không tìm thấy nhân viên")
        latest_contract = ManagerService._latest_contract(employee_id)
        latest_salary = ManagerService._latest_salary(employee_id)
        today = get_current_time().date()
        recent_attendance = Attendance.query.filter(Attendance.employee_id == employee_id).order_by(Attendance.date.desc()).limit(10).all()
        leave_history = LeaveRequest.query.filter(LeaveRequest.employee_id == employee_id).order_by(LeaveRequest.from_date.desc()).limit(10).all()
        leave_usage = EmployeeLeaveUsage.query.filter_by(employee_id=employee_id, year=today.year).first()
        complaints = Complaint.query.filter(Complaint.employee_id == employee_id, Complaint.is_deleted.is_(False)).order_by(Complaint.created_at.desc()).limit(5).all()
        return {
            "employee_id": emp.id,
            "employee_code": f"EMP{emp.id:04d}",
            "full_name": emp.full_name,
            "phone": emp.phone,
            "address": emp.address_detail or emp.address,
            "position": emp.position.job_title if emp.position else "--",
            "department": emp.department.name if emp.department else "--",
            "hire_date": emp.hire_date.isoformat() if emp.hire_date else None,
            "contract": {
                "contract_code": latest_contract.contract_code if latest_contract else None,
                "start_date": latest_contract.start_date.isoformat() if latest_contract and latest_contract.start_date else None,
                "end_date": latest_contract.end_date.isoformat() if latest_contract and latest_contract.end_date else None,
                "status": latest_contract.status if latest_contract else None,
            },
            "attendance_recent": [
                {
                    "date": row.date.isoformat(),
                    "check_in": row.check_in.isoformat() if row.check_in else None,
                    "check_out": row.check_out.isoformat() if row.check_out else None,
                    "overtime_hours": float(row.overtime_hours or 0),
                    "status": row.status.status_name if row.status else "UNKNOWN",
                }
                for row in recent_attendance
            ],
            "leave": {
                "remaining_quota": int(leave_usage.remaining_days) if leave_usage else 0,
                "pending_requests": LeaveRequest.query.filter_by(employee_id=employee_id, status="pending").count(),
                "history": [
                    {
                        "from_date": row.from_date.isoformat(),
                        "to_date": row.to_date.isoformat(),
                        "status": row.status,
                        "reason": row.reason,
                    }
                    for row in leave_history
                ],
            },
            "payroll_summary": {
                "basic_salary": float(latest_salary.basic_salary or 0) if latest_salary else 0,
                "allowance": float(latest_salary.total_allowance or 0) if latest_salary else 0,
                "deduction": float(latest_salary.penalty or 0) if latest_salary else 0,
                "net_salary": float(latest_salary.net_salary or 0) if latest_salary else 0,
                "status": ManagerService._payroll_status_label(latest_salary.status) if latest_salary else "--",
            },
            "performance": {
                "attendance_warning_days_30": Attendance.query.filter(
                    Attendance.employee_id == employee_id,
                    Attendance.date >= today - timedelta(days=30),
                    Attendance.date <= today,
                ).join(Attendance.status, isouter=True).filter(
                    or_(AttendanceStatus.status_name == "LATE", AttendanceStatus.status_name == "ABSENT")
                ).count(),
                "approved_leave_days_ytd": LeaveRequest.query.filter(
                    LeaveRequest.employee_id == employee_id,
                    LeaveRequest.status == "approved",
                    db.extract("year", LeaveRequest.from_date) == today.year,
                ).count(),
            },
            "complaints": [
                {
                    "id": row.id,
                    "type": row.type,
                    "title": row.title,
                    "status": row.status,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in complaints
            ],
        }