# Import hàm get_current_time của bạn
from app.utils.time import get_current_time
from app.models.contract import Contract
from app.models.employee import Employee
from app.modules.history.service import HistoryService 
from app.utils.time import get_current_time
from app.constants.contract import ContractStatus
from app.constants.employee import EmploymentType
from app.constants.common import RoleName
from decimal import Decimal
from datetime import date
import re
from dateutil.relativedelta import relativedelta
from .base_service import Base_Service
from app.extensions import db
from app.modules.payroll.admin_service import PayrollPolicyService
from app.constants.payroll import SalarySettings
from app.common.exceptions import NotFoundError
class Admin_Contract_Service:
    @staticmethod
    def _generate_contract_code() -> str:
        year = get_current_time().year 
        prefix = f"HD{year}"
        latest_code = (
            Contract.query.filter(Contract.contract_code.like(f"{prefix}-%"))
            .order_by(Contract.id.desc())
            .with_entities(Contract.contract_code)
            .first()
        )
        seq = 1
        if latest_code and latest_code[0]:
            try:
                # Tách phần số phía sau dấu '-'
                seq = int(str(latest_code[0]).split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f"{prefix}-{seq:03d}"
    
    @staticmethod
    def _calculate_end_date(start_date: date, duration_str: str) -> date | None:
        if not duration_str or duration_str.lower() in ['permanent', 'indefinite', '0']:
            return None
        match = re.match(r"(\d+)([my])", duration_str.lower())
        if not match:
            return None # Hoặc raise ValueError
        value = int(match.group(1))
        unit = match.group(2)
        delta = relativedelta(months=value) if unit == 'm' else relativedelta(years=value)
        return start_date + delta - relativedelta(days=1)

    @staticmethod
    def create_contract(data: dict, current_user_id: int) -> Contract:
        """
        Tạo hợp đồng và thiết lập liên kết với nhân viên.
        """
        employee_id = data.get("employee_id")
        
        # 1. Kiểm tra nhân viên tồn tại
        employee = Employee.query.filter_by(id=employee_id, is_deleted=False).first()
        if not employee:
            raise NotFoundError(f"Không tìm thấy nhân viên với ID {employee_id}")

        # 2. Xử lý Lương
        manual_salary = data.get("basic_salary")
        if manual_salary:
            salary = Decimal(str(manual_salary))
        else:
            # Giả sử hàm này lấy đúng cấu hình lương
            config = PayrollPolicyService.get_salary_config_for_position(employee.position_id)
            salary = Decimal(str(config.get("basic_salary", 0))) if config else Decimal("8800000")

        # 3. Kiểm tra trùng lặp (không được có hợp đồng active khác)
        today = get_current_time().date()
        if Base_Service.check_contract_overlap(employee_id, today):
            raise ValueError("Nhân viên đang có hợp đồng hiệu lực. Vui lòng chấm dứt hợp đồng cũ trước.")

        # 4. Tính toán thời gian & loại hợp đồng
        duration = data.get("duration", "2m") 
        end_date = Admin_Contract_Service._calculate_end_date(today, duration)
        contract_type = (data.get("contract_type") or EmploymentType.PROBATION).lower()
        # 5. Khởi tạo Hợp đồng và LIÊN KẾT (Phần quan trọng nhất)
        new_contract = Contract(
            employee=employee,  
            contract_code=Admin_Contract_Service._generate_contract_code(),
            basic_salary=salary,
            start_date=today,
            end_date=end_date,
            status=ContractStatus.ACTIVE,
            contract_type=contract_type,
            note=data.get("note")
        )
        try:
            db.session.add(new_contract)
            db.session.flush() 
            HistoryService.log_event(
                action="CREATE_CONTRACT",
                employee_id=employee.id,
                entity_type="Contract",
                entity_id=new_contract.id,
                description=f"Tạo hợp đồng {new_contract.contract_code} cho nhân viên: {employee.full_name}",
                performed_by=current_user_id
            )
            db.session.commit()
            return new_contract
        except Exception as e:
            db.session.rollback()
            raise e
        
    @staticmethod
    def terminate_contract(contract_id: int, data: dict, current_user_id: int) -> Contract:
        # 1. Tìm hợp đồng
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")
        raw_end_date = data.get("end_date")
        if isinstance(raw_end_date, date):
            terminate_date = raw_end_date
        elif isinstance(raw_end_date, str):
            terminate_date = date.fromisoformat(raw_end_date)
        else:
            terminate_date = get_current_time().date()
        if terminate_date < contract.start_date:
            raise ValueError("Ngày kết thúc không thể trước ngày bắt đầu")
        try:
            contract.end_date = terminate_date
            contract.status = ContractStatus.TERMINATED
            if "note" in data:
                contract.note = data.get("note")
            if contract.employee and contract.employee.user:
                user = contract.employee.user
                user.is_active = False
                user.lock_reason = f"Tự động khóa do chấm dứt hợp đồng {contract.contract_code}"
                user.locked_at = get_current_time() # Dùng hàm của bạn
                user.locked_by = current_user_id
            db.session.flush()
            HistoryService.log_event(
                action="TERMINATE_CONTRACT",
                employee_id=contract.employee_id,
                entity_type="Contract",
                entity_id=contract.id,
                description=f"Chấm dứt hợp đồng [{contract.contract_code}] vào ngày {terminate_date}. Tài khoản người dùng đã bị khóa.",
                performed_by=current_user_id
            )
            db.session.commit()
            return contract
        except Exception as e:
            db.session.rollback()
            raise e
        