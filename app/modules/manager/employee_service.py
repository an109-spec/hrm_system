from datetime import timedelta
from sqlalchemy import or_
from app.constants.contract import ContractStatus
from app.models.base import db
from app.models.employee import Employee
from app.models.attendance import Attendance, AttendanceStatus
from app.models.contract import Contract
from app.models.leave import LeaveRequest 
from app.constants.employee import WorkingStatus, EmploymentType
from app.modules.contract.manager_service import Manager_Contract_Service
from .attendance_service import AttendanceManagerService
from app.utils.time import get_current_time
class EmployeeService:
    @staticmethod
    def get_department_employee_summary(manager_id: int) -> dict:
        employees = AttendanceManagerService._get_subordinates(manager_id)
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
        employees = Manager_Contract_Service._get_subordinates(manager_id)
        if not employees:
            return []
        rows = []
        for emp in employees:
            e_type = emp.employment_type or ""
            w_status = emp.working_status or ""
            rows.append({
                "employee_id": emp.id,
                "employee_code": f"EMP{emp.id:04d}",
                "full_name": emp.full_name,
                "position": emp.position.job_title if emp.position else "--",
                "department": emp.department.name if emp.department else "--",
                "hire_date": emp.hire_date.isoformat() if emp.hire_date else None,
                "contract_type": e_type.lower(),
                "contract_type_label": e_type.replace('_', ' ').title() if e_type else "--",
                "working_status": w_status.lower(),
                "working_status_label": w_status.replace('_', ' ').title() if w_status else "--",
            })
        name = (filters.get("name") or "").strip().lower()
        employee_code = (filters.get("employee_code") or "").strip().upper().replace("EMP", "")
        position = (filters.get("position") or "").strip().lower()
        working_status = (filters.get("working_status") or "").strip().lower()
        contract_type = (filters.get("contract_type") or "").strip().lower()
        probation = (filters.get("probation") or "").strip().lower()
        department = (filters.get("department") or "").strip().lower()
        def _matches(row: dict) -> bool:
            if name and name not in (row["full_name"] or "").lower(): return False
            if employee_code and employee_code not in row["employee_code"].replace("EMP", ""): return False
            if position and position not in (row["position"] or "").lower(): return False
            if working_status and working_status != row["working_status"]: return False
            if contract_type and contract_type != row["contract_type"]: return False
            if probation == "yes" and row["contract_type"] != "probation": return False
            if probation == "no" and row["contract_type"] == "probation": return False
            if department and department not in (row["department"] or "").lower(): return False
            return True
        return [x for x in rows if _matches(x)]

    @staticmethod
    def get_department_employee_detail(manager_id: int, employee_id: int) -> dict:
        subordinate_ids = {x.id for x in Manager_Contract_Service._get_subordinates(manager_id)}
        if employee_id not in subordinate_ids:
            raise ValueError("Không có quyền xem nhân viên này")
        emp = Employee.query.get(employee_id)
        if not emp:
            raise ValueError("Không tìm thấy nhân viên")
        return {
            "employee_id": emp.id,
            "employee_code": f"EMP{emp.id:04d}",
            "full_name": emp.full_name,
            "avatar": emp.avatar,
            "personal_info": {
                "gender": emp.gender,
                "dob": emp.dob.isoformat() if emp.dob else None,
                "age": emp.age, # Lấy từ property @property age trong model
                "phone": emp.phone,
            },
            "address_info": {
                "province_id": emp.province_id,
                "district_id": emp.district_id,
                "ward_id": emp.ward_id,
                "address_detail": emp.address_detail,
                "address_full": emp.address # Lưu trữ địa chỉ gốc nếu có
            },
            "organization": {
                "department": emp.department.name if emp.department else "--",
                "position": emp.position.job_title if emp.position else "--",
            },
            "employment_info": {
                "hire_date": emp.hire_date.isoformat() if emp.hire_date else None,
                "type": (emp.employment_type or "").replace('_', ' ').title(),
                "status": (emp.working_status or "").replace('_', ' ').title(),
                "is_attendance_required": emp.is_attendance_required
            }
        }