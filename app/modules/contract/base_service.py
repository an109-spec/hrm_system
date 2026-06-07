from app.models.contract import Contract
from app.models.department import Department
from app.models.position import Position
from app.models.employee import Employee
from datetime import timedelta, date
from sqlalchemy import or_
from app.utils.time import get_current_time
from app.constants.contract import ContractStatus
from app.constants.employee import EmploymentType
class Base_Service:
    @staticmethod
    def get_active_contract(employee_id: int) -> Contract | None:
        """Lấy Hợp đồng đang có hiệu lực (Status: active)."""
        return (
            Contract.query.filter(
                Contract.employee_id == employee_id,
                Contract.status == ContractStatus.ACTIVE
            )
            .order_by(Contract.start_date.desc())
            .first()
        )
    
    @staticmethod
    def get_expiring_contracts(days_threshold: int = 30) -> list[Contract]:
        """
        Lấy các Hợp đồng sắp hết hạn
        """
        now = get_current_time()
        today = now.date()
        threshold_date = (now + timedelta(days=days_threshold)).date()
        return (
            Contract.query.filter(
                Contract.status == ContractStatus.ACTIVE,
                Contract.end_date <= threshold_date,
                Contract.end_date >= today,
                Contract.end_date != None 
            )
            .all()
        )
    
    @staticmethod
    def _latest_contract(employee_id: int) -> Contract | None:
        """
        Lấy bản ghi hợp đồng mới nhất của 1 nhân viên (chưa bị xóa).
        """
        return (
            Contract.query.filter_by(
                employee_id=employee_id, 
                is_deleted=False
            )
            .order_by(Contract.start_date.desc(), Contract.created_at.desc())
            .first()
        )

    @staticmethod
    def check_contract_overlap(employee_id: int, new_start_date: date) -> bool:
        """
        Kiểm tra xem hợp đồng mới có trùng với hợp đồng cũ đang active không.
        """
        active_contract = Base_Service.get_active_contract(employee_id)
        if active_contract and active_contract.end_date:
            if new_start_date <= active_contract.end_date:
                return True 
        return False
    
    @staticmethod
    def _status_and_days_left(contract: Contract, today: date | None = None) -> tuple[str, int | None]:
        """
        Tính toán trạng thái và số ngày còn lại của 1 hợp đồng
        """
        current_date = today or get_current_time().date()
        if contract.status == ContractStatus.TERMINATED:
            days_left = (contract.end_date - current_date).days if contract.end_date else None
            return ContractStatus.TERMINATED, days_left
        if not contract.end_date:
            return ContractStatus.ACTIVE, None
        days_left = (contract.end_date - current_date).days
        if days_left < 0:
            return ContractStatus.EXPIRED, days_left
        if days_left < 30:
            return ContractStatus.EXPIRING, days_left
        return ContractStatus.ACTIVE, days_left
    
    @staticmethod
    def _serialize_contract(contract: Contract, *, today: date | None = None) -> dict:
        """
        Serializer dữ liệu hợp đồng, kết hợp thông tin nhân viên, phòng ban, chức danh
        và trạng thái hợp đồng mới nhất.
        """
        employee = contract.employee
        status, days_left = Base_Service._status_and_days_left(contract, today=today)

        # 2. Đóng gói dữ liệu
        return {
            "id": contract.id,
            "contract_code": contract.contract_code,
            
            # Thông tin nhân viên (Lấy trực tiếp từ relationship)
            "employee_id": employee.id if employee else None,
            "employee_code": f"EMP{employee.id:05d}" if employee else "--",
            "employee_name": employee.full_name if employee else "--",
            "employment_type": employee.employment_type if employee else None, # Dùng thẳng từ Model Employee
            
            # Thông tin tổ chức (Lấy qua relationship đã khai báo trong model)
            "department": employee.department.name if employee and employee.department else "--",
            "position": employee.position.job_title if employee and employee.position else "--",
            
            # Thời gian & Lương
            "start_date": contract.start_date.isoformat() if contract.start_date else None,
            "end_date": contract.end_date.isoformat() if contract.end_date else None,
            "basic_salary": float(contract.basic_salary or 0),
            
            # Trạng thái & Tính toán
            "contract_status": status,
            "contract_status_label": ContractStatus.get_label(status), # Dùng class hằng số chuẩn
            "days_left": days_left,
            
            # Ghi chú (nếu model có field này)
            "note": getattr(contract, "note", None),
        }
    
    @staticmethod
    def _serialize_contract_list(contract: Contract, *, today: date | None = None) -> dict:
        status, _ = Base_Service._status_and_days_left(contract, today=today)

        return {
            "contract_code": contract.contract_code,
            "employee_name": contract.employee.full_name if contract.employee else "--",
            "start_date": contract.start_date.isoformat() if contract.start_date else None,
            "end_date": contract.end_date.isoformat() if contract.end_date else None,
            "contract_status": status
        }
    
    @staticmethod
    def get_filter_meta() -> dict:
        departments = Department.query.filter_by(is_deleted=False).order_by(Department.name.asc()).all()
        positions = Position.query.filter_by(is_deleted=False).order_by(Position.job_title.asc()).all()
        managers = (
            Employee.query.filter_by(is_deleted=False)
            .order_by(Employee.full_name.asc())
            .all()
        )
        status_choices = [{"value": "all", "label": "Tất cả"}] + \
                        [{"value": key, "label": label} for key, label in ContractStatus.choices()]
        type_choices = [{"value": "all", "label": "Tất cả"}] + \
                    [{"value": key, "label": label} for key, label in EmploymentType.choices()]
        return {
            "departments": [{"id": d.id, "name": d.name} for d in departments],
            "positions": [{"id": p.id, "name": p.job_title} for p in positions],
            "managers": [{"id": m.id, "name": m.full_name} for m in managers],
            "contract_statuses": status_choices,
            "contract_types": type_choices,
        }
    

    @staticmethod
    def get_contracts(search=None, contract_type=None, contract_status=None) -> dict:
        query = Contract.query.join(Employee, Contract.employee_id == Employee.id) \
            .filter(Employee.is_deleted.is_(False), Contract.is_deleted.is_(False))
        if search:
            keyword = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Contract.contract_code.ilike(keyword),
                    Employee.full_name.ilike(keyword),
                    Employee.id.cast(str).ilike(keyword)
                )
            )
        if contract_type and contract_type.lower() != "all":
            query = query.filter(Contract.employment_type == contract_type.lower())
        contracts = query.order_by(Contract.start_date.desc(), Contract.id.desc()).all()
        today = get_current_time().date()
        serialized = [Base_Service._serialize_contract_list(c, today=today) for c in contracts]
        if contract_status and contract_status.lower() != "all":
            status_filter = contract_status.lower()
            serialized = [
                row for row in serialized 
                if row.get("contract_status") == status_filter
            ]
        summary = {
            "total": len(serialized),
            "expiring": sum(1 for row in serialized if row["contract_status"] == "expiring"),
            "active": sum(1 for row in serialized if row["contract_status"] == "active"),
            "expired": sum(1 for row in serialized if row["contract_status"] == "expired"),
        }
        return {"items": serialized, "summary": summary}
    
    @staticmethod
    def get_contract_detail(contract_id: int) -> dict:
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")
        today = get_current_time().date()
        return Base_Service._serialize_contract(contract, today=today)
    
    @staticmethod
    def get_contract_reminders() -> dict:
        # 1. Lấy mốc thời gian (hỗ trợ Simulation Mode)
        now = get_current_time()
        today = now.date()
        week_later = (now + timedelta(days=7)).date()
        month_later = (now + timedelta(days=30)).date()

        reminders: list[dict] = []

        # 2. Fetch dữ liệu hợp đồng mới nhất của mỗi nhân viên
        all_contracts = (
            Contract.query.join(Employee, Contract.employee_id == Employee.id)
            .filter(Employee.is_deleted.is_(False), Contract.is_deleted.is_(False))
            .order_by(Contract.employee_id.asc(), Contract.start_date.desc(), Contract.id.desc())
            .all()
        )
        
        latest_by_employee: dict[int, Contract] = {}
        for contract in all_contracts:
            latest_by_employee.setdefault(contract.employee_id, contract)

        # 3. Lấy danh sách nhân viên để kiểm tra
        employees = Employee.query.filter_by(is_deleted=False).order_by(Employee.full_name.asc()).all()
        
        for employee in employees:
            contract = latest_by_employee.get(employee.id)
            
            # Trường hợp: Nhân viên chưa có hợp đồng
            if not contract:
                reminders.append({
                    "level": "critical",
                    "type": "missing_contract",
                    "employee_id": employee.id,
                    "employee_code": f"EMP{employee.id:05d}",
                    "employee_name": employee.full_name,
                    "message": "Nhân viên chưa có hợp đồng",
                    "days_left": None
                })
                continue

            # 4. Sử dụng hàm helper để tính trạng thái
            status, days_left = Base_Service._status_and_days_left(contract, today=today)
            
            # 5. Phân loại theo logic nghiệp vụ
            if status == ContractStatus.EXPIRED:
                reminders.append({
                    "level": "critical",
                    "type": "expired",
                    "contract_id": contract.id,
                    "employee_id": employee.id,
                    "employee_code": f"EMP{employee.id:05d}",
                    "employee_name": employee.full_name,
                    "message": "Hợp đồng đã quá hạn, cần xử lý ngay",
                    "days_left": days_left
                })
                continue

            # Xử lý cảnh báo theo thời gian (dùng logic của bạn)
            d_val = days_left if days_left is not None else 10_000
            
            if contract.end_date and contract.end_date <= week_later:
                reminders.append({
                    "level": "warning",
                    "type": "expiring_7_days",
                    "contract_id": contract.id,
                    "employee_id": employee.id,
                    "employee_code": f"EMP{employee.id:05d}",
                    "employee_name": employee.full_name,
                    "message": f"Hợp đồng còn {max(days_left or 0, 0)} ngày sẽ hết hạn",
                    "days_left": days_left
                })
            elif contract.end_date and contract.end_date <= month_later:
                reminders.append({
                    "level": "warning",
                    "type": "expiring_30_days",
                    "contract_id": contract.id,
                    "employee_id": employee.id,
                    "employee_code": f"EMP{employee.id:05d}",
                    "employee_name": employee.full_name,
                    "message": "Hợp đồng còn dưới 30 ngày sẽ hết hạn",
                    "days_left": days_left
                })
            else:
                reminders.append({
                    "level": "info",
                    "type": "normal",
                    "contract_id": contract.id,
                    "employee_id": employee.id,
                    "employee_code": f"EMP{employee.id:05d}",
                    "employee_name": employee.full_name,
                    "message": "Hợp đồng đang hiệu lực bình thường",
                    "days_left": days_left
                })

        # 6. Sắp xếp danh sách: Critical -> Warning -> Info, và ưu tiên ngày hết hạn sớm
        reminders.sort(
            key=lambda item: (
                {"critical": 0, "warning": 1, "info": 2}.get(item["level"], 3),
                item.get("days_left") if item.get("days_left") is not None else 10_000,
            )
        )

        return {
            "items": reminders,
            "summary": {
                "critical": sum(1 for item in reminders if item["level"] == "critical"),
                "warning": sum(1 for item in reminders if item["level"] == "warning"),
                "info": sum(1 for item in reminders if item["level"] == "info"),
            },
        }