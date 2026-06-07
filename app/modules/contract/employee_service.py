from app.models.contract import Contract
from app.constants.contract import ContractStatus
from app.constants.employee import EmploymentType

class ContractService:

    @staticmethod
    def get_my_contract_details(contract_id: int, user_id: int) -> dict:
        """
        Lấy thông tin hợp đồng của chính nhân viên đang đăng nhập.
        """
        # 1. Query lấy contract kèm thông tin employee để check user_id
        contract = Contract.query.join(Contract.employee).filter(
            Contract.id == contract_id,
            Contract.is_deleted == False
        ).first()

        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")

        # 2. KIỂM TRA QUYỀN: 
        # So sánh user_id của người đang đăng nhập với user_id của chủ sở hữu hợp đồng
        if contract.employee.user_id != user_id:
            raise PermissionError("Bạn không có quyền xem hợp đồng này")

        # 3. Trả về dữ liệu chi tiết
        return {
            "id": contract.id,
            "contract_code": contract.contract_code,
            "basic_salary": float(contract.basic_salary),
            "start_date": contract.start_date.strftime("%d/%m/%Y") if contract.start_date else None,
            "end_date": contract.end_date.strftime("%d/%m/%Y") if contract.end_date else None,
            
            "status": {
                "value": contract.status,
                "label": ContractStatus.get_label(contract.status)
            },
            
            "employee": {
                "full_name": contract.employee.full_name,
                "employment_type": {
                    "value": contract.employee.employment_type,
                    "label": EmploymentType.get_label(contract.employee.employment_type)
                }
            }
        }
    
    