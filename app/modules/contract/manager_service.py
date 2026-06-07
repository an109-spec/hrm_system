from app.models.contract import Contract
from app.models.department import Department
from app.models.position import Position
from app.models.employee import Employee
from datetime import timedelta, date
from sqlalchemy import or_, func
from app.utils.time import get_current_time
from app.constants.contract import ContractStatus, ProposalType
from app.constants.employee import EmploymentType
from app.constants.contract import ContractStatus
from app.utils.time import get_current_time
from app.modules.contract.base_service import Base_Service
from app.models.contract_proposal import ContractProposal
from app.models.user import User
from app.models.role import Role
from app.modules.notification.notification_service import NotificationService
from app.modules.history.service import HistoryService
from app.modules.dashboard.dto import NotificationDTO
from app.constants.common import RoleName
from app.extensions.db import db
class Manager_Contract_Service:
    @staticmethod
    def _get_subordinates(manager_id: int) -> list[Employee]:
        """
        Lấy toàn bộ nhân viên thuộc (các) phòng ban mà manager này quản lý.
        Ràng buộc: Chỉ lấy nhân viên trong cùng phòng ban.
        """
        manager = Employee.query.get(manager_id)
        if not manager or manager.is_deleted:
            return []
        managed_depts = manager.managed_department
        if not managed_depts:
            return []
        if not isinstance(managed_depts, list):
            managed_depts = [managed_depts]
        all_subordinates = []
        for dept in managed_depts:
            if hasattr(dept, 'employees'):
                emps = [
                    e for e in dept.employees 
                    if e.id != manager_id and not e.is_deleted
                ]
                all_subordinates.extend(emps)
        return all_subordinates
    
    '''
    TRẢ VỀ DS HỢP ĐỒNG SẮP HẾT HẠN 
    '''
    @staticmethod
    def get_contract_expiring(manager_id: int) -> list[dict]:
        # 1. Lấy danh sách nhân viên cấp dưới
        sub_ids = [e.id for e in Manager_Contract_Service._get_subordinates(manager_id)]
        if not sub_ids:
            return []

        # 2. Sử dụng helper thời gian của hệ thống
        today = get_current_time().date()
        limit = today + timedelta(days=30)

        # 3. Truy vấn sử dụng Hằng số (Constants) thay vì Hardcoded string
        rows = (
            Contract.query.filter(
                Contract.employee_id.in_(sub_ids),
                Contract.status == ContractStatus.ACTIVE, # Dùng hằng số
                Contract.end_date.isnot(None),
                Contract.end_date <= limit,
                Contract.end_date >= today # Chỉ lấy những cái chưa hết hạn
            )
            .order_by(Contract.end_date.asc())
            .all()
        )

        data = []
        for c in rows:
            # 4. Sử dụng logic tính toán tập trung từ Base_Service
            _, days_left = Base_Service._status_and_days_left(c, today)
            
            data.append(
                {
                    "id": c.id,
                    "employee_id": c.employee_id,
                    "employee_name": c.employee.full_name if c.employee else "--",
                    "contract_code": c.contract_code,
                    "start_date": c.start_date.isoformat() if c.start_date else None,
                    "end_date": c.end_date.isoformat() if c.end_date else None,
                    "basic_salary": float(c.basic_salary or 0),
                    "days_left": days_left,
                }
            )
        return data
    
    @staticmethod
    def _latest_contracts_for_employee_ids(employee_ids: list[int]) -> dict[int, Contract]:
        """
        Lấy danh sách hợp đồng mới nhất của nhiều nhân viên cùng lúc.
        """
        if not employee_ids:
            return {}
            
        rows = (
            Contract.query.filter(
                Contract.employee_id.in_(employee_ids), 
                Contract.is_deleted.is_(False)
            )
            .order_by(
                Contract.employee_id.asc(), 
                Contract.start_date.desc(), 
                Contract.created_at.desc()
            )
            .all()
        )
        latest: dict[int, Contract] = {}
        for row in rows:
            if row.employee_id not in latest:
                latest[row.employee_id] = row
        return latest
    
    '''
    XEM DS VÀ CHI TIẾT HỢP ĐỒNG NHÂN VIÊN
    '''
    @staticmethod
    def get_contracts(manager_id: int, search=None, contract_type=None, contract_status=None) -> dict:
        # 1. Lấy danh sách ID nhân viên cấp dưới
        subordinates = Manager_Contract_Service._get_subordinates(manager_id)
        subordinate_ids = [s.id for s in subordinates]

        # Nếu manager không quản lý ai, trả về danh sách rỗng
        if not subordinate_ids:
            return {"items": [], "summary": {"total": 0, "expiring": 0, "active": 0, "expired": 0}}

        # 2. Xây dựng query với điều kiện lọc theo nhân viên
        query = Contract.query.join(Employee, Contract.employee_id == Employee.id) \
            .filter(
                Employee.is_deleted.is_(False), 
                Contract.is_deleted.is_(False),
                Contract.employee_id.in_(subordinate_ids) # RÀNG BUỘC PHẠM VI
            )
        
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
    def get_contract_detail(manager_id: int, contract_id: int) -> dict:
        # 1. Tìm hợp đồng
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")

        # 2. Kiểm tra quyền sở hữu (Manager có quản lý nhân viên sở hữu hợp đồng này không?)
        subordinates = Manager_Contract_Service._get_subordinates(manager_id)
        subordinate_ids = {s.id for s in subordinates}
        
        if contract.employee_id not in subordinate_ids:
            raise PermissionError("Bạn không có quyền truy cập hợp đồng của nhân viên này")

        # 3. Trả về dữ liệu nếu hợp lệ
        today = get_current_time().date()
        return Base_Service._serialize_contract(contract, today=today)
    
    '''
    CHỌN NHÂN VIÊN THỰC HIỆN GIA HẠN
    '''
    @staticmethod
    def _validate_manager_access(manager_id: int, employee_id: int):
        """
        Logic kiểm tra quyền tập trung. 
        Nếu không hợp lệ sẽ raise PermissionError.
        """
        subordinates = Manager_Contract_Service._get_subordinates(manager_id)
        subordinate_ids = {s.id for s in subordinates}
        if employee_id not in subordinate_ids:
            raise PermissionError("Bạn không có quyền thao tác trên nhân viên này")
        
    @staticmethod
    def get_contract_for_renewal_or_adjustment(manager_id: int, employee_id: int) -> dict:
        # 1. Kiểm tra quyền qua hàm dùng chung
        Manager_Contract_Service._validate_manager_access(manager_id, employee_id)

        # 2. Query contract
        contract = Contract.query.filter(
            Contract.employee_id == employee_id,
            Contract.is_deleted == False,
            Contract.status.in_(['active', 'expired'])
        ).order_by(Contract.start_date.desc()).first()
        if not contract:
            raise ValueError("Nhân viên này không có hợp đồng phù hợp để thực hiện gia hạn/điều chỉnh")
        return Base_Service._serialize_contract(contract, today=get_current_time().date())
    '''
    GỬI YÊU CẦU GIA HẠN
    '''
    @staticmethod
    def request_contract_renewal(
        manager_id: int,
        contract_id: int,
        reason: str,
        proposed_duration_months: int,
        professional_note: str = None
    ) -> dict:
        # 1. Query lấy đối tượng contract (cần object thật để lưu DB)
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")
        
        # 2. TẬN DỤNG logic kiểm tra quyền dùng chung
        Manager_Contract_Service._validate_manager_access(manager_id, contract.employee_id)

        if not reason or not reason.strip():
            raise ValueError("Lý do gia hạn là bắt buộc")

        # 3. Tạo đề xuất gia hạn
        proposal = ContractProposal(
            contract_id=contract.id,
            employee_id=contract.employee_id,
            manager_id=manager_id,
            proposal_type=ProposalType.RENEWAL,
            reason=reason.strip(),
            proposed_duration_months=proposed_duration_months,
            professional_note=professional_note.strip() if professional_note else None,
            status="pending_hr",
        )
        db.session.add(proposal)
        db.session.flush()

        # 4. Ghi log & Thông báo (giữ nguyên logic cũ)
        proposal_label = ProposalType.get_label(ProposalType.RENEWAL)
        
        HistoryService.log_event(
            action="MANAGER_RENEWAL_REQUEST",
            employee_id=contract.employee_id,
            entity_type="contract_proposal",
            entity_id=proposal.id,
            description=f"Manager yêu cầu {proposal_label.lower()} hợp đồng #{contract.contract_code}",
            performed_by=manager_id
        )

        hr_users = User.query.join(Role).filter(Role.name == RoleName.HR).all()
        for hr_user in hr_users:
            NotificationService.create(NotificationDTO(
                user_id=hr_user.id,
                title=f"Yêu cầu {proposal_label} hợp đồng mới",
                content=f"Nhân viên {contract.employee.full_name} cần {proposal_label.lower()} hợp đồng.",
                type=ProposalType.RENEWAL,
                link=f"/hr/contracts/proposals/{proposal.id}",
                is_read=False
            ))

        db.session.commit()
        return {"id": proposal.id, "status": "success", "message": f"Đã gửi yêu cầu {proposal_label.lower()} đến HR"}

    '''
    BỘ LỌC 
    '''
    @staticmethod
    def get_filtered_contracts(
        manager_id: int, 
        search: str = None, 
        contract_type: str = None, 
        contract_status: str = None
    ) -> dict:
        """
        Hàm mới: Lấy danh sách hợp đồng có lọc dữ liệu tại DB.
        Sử dụng Hằng số (Constants) để đảm bảo tính nhất quán.
        """
        # 1. Lấy danh sách ID nhân viên cấp dưới
        subordinates = Manager_Contract_Service._get_subordinates(manager_id)
        subordinate_ids = [s.id for s in subordinates]

        if not subordinate_ids:
            return {"items": [], "summary": {"total": 0, "expiring": 0, "active": 0, "expired": 0}}

        # 2. Xây dựng Query cơ bản
        query = Contract.query.join(Employee, Contract.employee_id == Employee.id) \
            .filter(
                Employee.is_deleted.is_(False), 
                Contract.is_deleted.is_(False),
                Contract.employee_id.in_(subordinate_ids)
            )
        
        # 3. Lọc dữ liệu tại DB
        if search and search.strip():
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
        
        # Lọc trạng thái sử dụng Constant từ ContractStatus
        if contract_status and contract_status.lower() != "all":
            # Sử dụng hằng số để lọc (Đảm bảo match chính xác với DB)
            query = query.filter(Contract.status == contract_status.lower())
        
        # 4. Thực thi truy vấn
        contracts = query.order_by(Contract.start_date.desc(), Contract.id.desc()).all()
        
        # 5. Serialize
        today = get_current_time().date()
        serialized = [Base_Service._serialize_contract_list(c, today=today) for c in contracts]
        
        # 6. Tính toán summary theo hằng số đã định nghĩa
        summary = {
            "total": len(serialized),
            # Dùng hằng số để đếm status
            "expiring": sum(1 for row in serialized if row.get("contract_status") == ContractStatus.EXPIRING),
            "active": sum(1 for row in serialized if row.get("contract_status") == ContractStatus.ACTIVE),
            "expired": sum(1 for row in serialized if row.get("contract_status") == ContractStatus.EXPIRED),
        }
        
        return {"items": serialized, "summary": summary}
    
    '''
    PHÂN TRANG
    '''
    @staticmethod
    def get_filtered_contracts_with_pagination(
        manager_id: int, 
        search: str = None, 
        contract_type: str = None, 
        contract_status: str = None,
        page: int = 1,
        per_page: int = 20
    ) -> dict:
        subordinates = Manager_Contract_Service._get_subordinates(manager_id)
        subordinate_ids = [s.id for s in subordinates]
        if not subordinate_ids:
            return {
                "items": [], 
                "meta": {"total": 0, "pages": 0, "current_page": page, "per_page": per_page},
                "summary": {"total": 0, "expiring": 0, "active": 0, "expired": 0}
            }
        query = Contract.query.join(Employee, Contract.employee_id == Employee.id) \
            .filter(
                Employee.is_deleted.is_(False), 
                Contract.is_deleted.is_(False),
                Contract.employee_id.in_(subordinate_ids)
            )
        if search and search.strip():
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
        if contract_status and contract_status.lower() != "all":
            query = query.filter(Contract.status == contract_status.lower())
        stats = query.with_entities(Contract.status, func.count(Contract.id)).group_by(Contract.status).all()
        stats_dict = {s[0]: s[1] for s in stats}
        summary = {
            "total": sum(stats_dict.values()),
            "expiring": stats_dict.get(ContractStatus.EXPIRING, 0),
            "active": stats_dict.get(ContractStatus.ACTIVE, 0),
            "expired": stats_dict.get(ContractStatus.EXPIRED, 0),
        }
        pagination = query.order_by(Contract.start_date.desc(), Contract.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        today = get_current_time().date()
        serialized_items = [Base_Service._serialize_contract_list(c, today=today) for c in pagination.items]
        return {
            "items": serialized_items,
            "meta": {
                "total": pagination.total,       # Tổng số bản ghi tìm thấy
                "pages": pagination.pages,       # Tổng số trang
                "current_page": pagination.page,
                "per_page": per_page
            },
            "summary": summary
        }