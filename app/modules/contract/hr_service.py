from app.constants.contract import ContractStatus, ContractRequestStatus, ProposalType
from app.models.employee import Employee
from app.modules.notification.notification_service import NotificationService
from app.modules.notification.dto import NotificationDTO
from app.models.contract import Contract
from app.extensions import db
from .admin_service import Admin_Contract_Service
from app.modules.history.service import HistoryService
from app.models.contract_proposal import ContractProposal
class HR_Contract_Service:
    @staticmethod
    def extend_contract(contract_id: int, data: dict, current_user_id: int) -> Contract:
        # 1. Tìm hợp đồng
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")

        # 2. Kiểm tra trạng thái: Không được gia hạn nếu đã chấm dứt (terminated)
        if contract.status == ContractStatus.TERMINATED:
            raise ValueError("Không thể gia hạn hợp đồng đã chấm dứt (terminated).")
        if "duration" in data:
            new_end_date = Admin_Contract_Service._calculate_end_date(contract.start_date, data["duration"])
        elif "end_date" in data:
            # Nếu truyền trực tiếp ngày, hãy đảm bảo data['end_date'] là đối tượng datetime.date
            new_end_date = data["end_date"]
        else:
            raise ValueError("Vui lòng cung cấp 'duration' hoặc 'end_date' để gia hạn.")
        if not new_end_date:
            raise ValueError("Ngày gia hạn không hợp lệ.")
        if new_end_date <= contract.start_date:
            raise ValueError("Ngày kết thúc mới phải sau ngày bắt đầu hợp đồng.")
        # 4. Lưu dữ liệu và ghi log
        try:
            contract.end_date = new_end_date
            contract.status = ContractStatus.ACTIVE # Tự động đưa về trạng thái Active
            if "note" in data:
                contract.note = data.get("note")
            db.session.flush() 
            HistoryService.log_event(
                action="EXTEND_CONTRACT",
                employee_id=contract.employee_id,
                entity_type="Contract",
                entity_id=contract.id,
                description=f"Gia hạn hợp đồng [{contract.contract_code}] đến ngày {new_end_date}",
                performed_by=current_user_id
            )
            db.session.commit()
            return contract
        except Exception as e:
            db.session.rollback()
            raise e
        
    @staticmethod
    def process_renewal_request(proposal_id: int, is_approved: bool, hr_id: int, feedback: str = None) -> dict:
        """
        HR duyệt/từ chối yêu cầu gia hạn dựa trên ContractRequestStatus
        """
        proposal = ContractProposal.query.filter_by(id=proposal_id, is_deleted=False).first()
        if not proposal:
            raise ValueError("Không tìm thấy yêu cầu")
        
        # Kiểm tra trạng thái bằng hằng số có sẵn
        if proposal.status != ContractRequestStatus.PENDING:
            raise ValueError(f"Yêu cầu không thể xử lý (Trạng thái hiện tại: {ContractRequestStatus.get_label(proposal.status)})")

        try:
            if is_approved:
                # 1. Gọi hàm gia hạn
                extension_data = {
                    "duration": proposal.proposed_duration_months,
                    "note": f"Gia hạn theo yêu cầu Manager: {proposal.reason}"
                }
                HR_Contract_Service.extend_contract(proposal.contract_id, extension_data, hr_id)
                
                # 2. Cập nhật trạng thái duyệt
                proposal.status = ContractRequestStatus.APPROVED
            else:
                proposal.status = ContractRequestStatus.REJECTED
            
            proposal.hr_feedback = feedback
            db.session.flush()

            # 3. Ghi log
            HistoryService.log_event(
                action="HR_PROCESS_RENEWAL",
                employee_id=proposal.employee_id,
                entity_type="contract_proposal",
                entity_id=proposal.id,
                description=f"HR đã {'Duyệt' if is_approved else 'Từ chối'} yêu cầu gia hạn. Phản hồi: {feedback}",
                performed_by=hr_id
            )
            
            db.session.commit()
            return {"status": "success", "message": f"Yêu cầu đã được {ContractRequestStatus.get_label(proposal.status)}"}
            
        except Exception as e:
            db.session.rollback()
            raise e
        
    @staticmethod
    def process_renewal_request(proposal_id: int, is_approved: bool, hr_id: int, feedback: str = None) -> dict:
        proposal = ContractProposal.query.filter_by(id=proposal_id, is_deleted=False).first()
        if not proposal:
            raise ValueError("Không tìm thấy yêu cầu")
        
        if proposal.status != ContractRequestStatus.PENDING:
            raise ValueError(f"Yêu cầu không thể xử lý (Trạng thái: {ContractRequestStatus.get_label(proposal.status)})")

        try:
            if is_approved:
                extension_data = {
                    "duration": proposal.proposed_duration_months,
                    "note": f"Gia hạn theo yêu cầu Manager: {proposal.reason}"
                }
                HR_Contract_Service.extend_contract(proposal.contract_id, extension_data, hr_id)
                proposal.status = ContractRequestStatus.APPROVED
            else:
                proposal.status = ContractRequestStatus.REJECTED
            
            proposal.hr_feedback = feedback
            db.session.flush()

            # 3. Ghi log lịch sử
            HistoryService.log_event(
                action="HR_PROCESS_RENEWAL",
                employee_id=proposal.employee_id,
                entity_type="contract_proposal",
                entity_id=proposal.id,
                description=f"HR đã {'Duyệt' if is_approved else 'Từ chối'} yêu cầu gia hạn. Phản hồi: {feedback}",
                performed_by=hr_id
            )

            # 4. GỬI THÔNG BÁO TỚI MANAGER VÀ EMPLOYEE
            status_label = "được duyệt" if is_approved else "bị từ chối"
            notification_title = f"Yêu cầu gia hạn hợp đồng {status_label}"
            notification_content = (
                f"Yêu cầu gia hạn hợp đồng cho nhân viên {proposal.employee.full_name} "
                f"đã {status_label}. Phản hồi từ HR: {feedback or 'Không có ghi chú'}"
            )

            # Gửi cho Manager
            manager_employee = Employee.query.get(proposal.manager_id)
            if manager_employee and manager_employee.user_id:
                NotificationService.create(NotificationDTO(
                    user_id=manager_employee.user_id,
                    title=notification_title,
                    content=notification_content,
                    type=ProposalType.RENEWAL,
                    link=f"/manager/contracts/proposals/{proposal.id}",
                    is_read=False
                ))

            # Gửi cho Employee (cần kiểm tra user_id của nhân viên)
            employee = proposal.employee # Giả định ContractProposal có relationship employee
            if employee and employee.user_id:
                NotificationService.create(NotificationDTO(
                    user_id=employee.user_id,
                    title=notification_title,
                    content=notification_content, # Nội dung có thể tùy chỉnh nếu muốn khác
                    type=ProposalType.RENEWAL,
                    link=f"/employee/contracts", # Link tới trang hợp đồng của nhân viên
                    is_read=False
                ))

            db.session.commit()
            return {"status": "success", "message": f"Yêu cầu đã được {ContractRequestStatus.get_label(proposal.status)}"}
            
        except Exception as e:
            db.session.rollback()
            raise e