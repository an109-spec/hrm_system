from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import func
from app.constants.common import RoleName
from app.models.position import Position
from app.models.department import Department
from app.models.role import Role
from app.models.base import db
from app.models.employee import Employee
from app.models.user import User
from app.models.contract import Contract
from app.constants.contract import ContractStatus
from app.constants.employee import WorkingStatus, EmploymentType
from app.utils.time import _normalize, get_current_time

class HRService: 
    @staticmethod
    def get_all_employee_summary() -> dict:
        employees = Employee.query.filter(Employee.is_deleted.is_(False)).all()
        result = {
            "total_employees": 0,
            "active_employees": 0,
            "probation_employees": 0,
            "expiring_contracts": 0
        }
        if not employees:
            return result
        today = get_current_time().date()
        thirty_days_later = today + timedelta(days=30)
        active_contracts = Contract.query.filter(
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
    def get_all_employee_list(filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        employees = Employee.query.filter(Employee.is_deleted.is_(False)).all()
        
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
    def get_employee_detail(employee_id: int) -> dict:
        """
        Lấy thông tin chi tiết nhân viên dành cho HR Admin.
        Không cần kiểm tra quyền subordinate_ids.
        """
        emp = Employee.query.filter(
            Employee.id == employee_id, 
            Employee.is_deleted.is_(False)
        ).first()
        if not emp:
            raise ValueError("Không tìm thấy nhân viên hoặc nhân viên đã bị xóa")
        return {
            "employee_id": emp.id,
            "employee_code": f"EMP{emp.id:04d}",
            "full_name": emp.full_name,
            "avatar": emp.avatar,
            "personal_info": {
                "gender": emp.gender,
                "dob": emp.dob.isoformat() if emp.dob else None,
                "age": emp.age, 
                "phone": emp.phone,
            },
            "address_info": {
                "province_id": emp.province_id,
                "district_id": emp.district_id,
                "ward_id": emp.ward_id,
                "address_detail": emp.address_detail,
                "address_full": emp.address
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

    @staticmethod
    def get_stats_by_department() -> list[dict]:
        departments = Department.query.filter_by(is_deleted=False).all()
        return [
            {
                "department_id": d.id,
                "name": d.name,
                "total_employees": d.employee_count
            } for d in departments
        ]

    # 2. Thống kê số lượng nhân viên theo Chức danh
    @staticmethod
    def get_stats_by_position() -> list[dict]:
        # Dùng join và count để đếm số lượng nhân viên theo từng chức danh
        stats = db.session.query(
            Position.id, 
            Position.job_title, 
            func.count(Employee.id).label('total')
        ).join(Employee, Position.id == Employee.position_id)\
         .filter(Employee.is_deleted.is_(False), Position.is_deleted.is_(False))\
         .group_by(Position.id, Position.job_title).all()
        return [
            {"position_id": s.id, "name": s.job_title, "total_employees": s.total} 
            for s in stats
        ]
    # 3. Hàm lọc danh sách nhân viên 
    @staticmethod
    def get_filtered_employees(filters: dict) -> list[dict]:
        query = Employee.query.filter(Employee.is_deleted.is_(False))
        if filters.get("department_id"):
            query = query.filter(Employee.department_id == int(filters["department_id"]))
        if filters.get("position_id"):
            query = query.filter(Employee.position_id == int(filters["position_id"]))
        if filters.get("working_status"):
            query = query.filter(Employee.working_status == filters["working_status"])
        if filters.get("employment_type"):
            query = query.filter(Employee.employment_type == filters["employment_type"])
        if filters.get("name"):
            search_term = f"%{filters['name']}%"
            query = query.filter(Employee.full_name.ilike(search_term))
        employees = query.order_by(Employee.created_at.desc()).all()
        return [
            {
                "employee_id": emp.id,
                "full_name": emp.full_name,
                "department": emp.department.name if emp.department else "--",
                "position": emp.position.job_title if emp.position else "--",
                "working_status": emp.working_status,
                "employment_type": emp.employment_type
            } for emp in employees
        ]



    

    
   