from app.utils.time import get_current_time
from app.extensions.db import db

from app.models.leave import LeaveRequest
from app.models.leave_usage import EmployeeLeaveUsage
from app.models.notification import Notification
from app.models.employee import Employee
from sqlalchemy.orm import joinedload 
from .dto import LeaveRequestDTO
from .validators import LeaveValidator

class LeaveService:
    @staticmethod
    def get_leave_balance(employee_id: int, year: int = None) -> EmployeeLeaveUsage:
        if year is None:
            now = get_current_time()
            year = now.year
        usage = EmployeeLeaveUsage.query.filter_by(
            employee_id=employee_id,
            year=year
        ).first()
        if not usage:
            usage = EmployeeLeaveUsage(
                employee_id=employee_id,
                year=year,
                total_days=12,
                used_days=0,
                remaining_days=12
            )
            db.session.add(usage)
            db.session.commit()
        return usage

    @staticmethod
    def update_usage_after_approve(employee_id: int, days: int, year: int):
        usage = LeaveService.get_leave_balance(employee_id, year)
        if usage:
            usage.used_days += days
            usage.update_balance()
            db.session.commit()

    @staticmethod
    def create_leave_request(dto: LeaveRequestDTO):
        LeaveValidator.validate_date_range(dto.from_date, dto.to_date)
        LeaveValidator.validate_reason(dto.reason)
        now = get_current_time()
        usage = LeaveService.get_leave_balance(dto.employee_id, now.year)
        if usage:
            LeaveValidator.validate_leave_days_limit(
                usage.remaining_days,
                dto.requested_days
            )
        leave = LeaveRequest(
            employee_id=dto.employee_id,
            leave_type_id=dto.leave_type_id,
            from_date=dto.from_date,
            to_date=dto.to_date,
            reason=dto.reason,
            status="pending",
            approved_by=dto.approved_by,
            document_url=dto.document_url,
            subtype=dto.subtype,
            relation=dto.relation
        )
        db.session.add(leave)
        employee = Employee.query.get(dto.employee_id)
        if employee and employee.manager_id:
            manager = Employee.query.get(employee.manager_id)
            if manager and manager.user_id:
                db.session.add(Notification(
                    user_id=manager.user_id,
                    title="Đơn xin nghỉ phép mới",
                    content=f"Nhân viên {employee.full_name} gửi đơn nghỉ {dto.requested_days} ngày ({dto.from_date.strftime('%d/%m')}).",
                    type="leave",
                    link="/admin/leave/manage" 
                ))
        db.session.commit()
        return leave

    @staticmethod
    def get_my_requests(employee_id: int):
        return (
            LeaveRequest.query
            .options(
                joinedload(LeaveRequest.leave_type), # Load sẵn tên loại nghỉ (VD: Nghỉ phép năm)
                joinedload(LeaveRequest.approver)    # Load sẵn thông tin người duyệt
            )
            .filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.is_deleted == False
            )
            .order_by(LeaveRequest.created_at.desc())
            .all()
        )
    @staticmethod
    def cancel_request(leave_id: int, employee_id: int):
        """
        Hủy đơn xin nghỉ phép. 
        Chỉ cho phép hủy khi đơn chưa được duyệt (Approved) hoặc bị từ chối (Rejected).
        """
        leave = LeaveRequest.query.filter_by(
            id=leave_id,
            employee_id=employee_id,
            is_deleted=False # Chỉ tìm các đơn chưa bị xóa ẩn
        ).first()

        if not leave:
            raise ValueError("❌ Không tìm thấy đơn xin nghỉ phép.")

        # Các trạng thái được phép hủy (tất cả các trạng thái 'chờ' hoặc yêu cầu bổ sung)
        allow_cancel_statuses = ['pending', 'pending_hr', 'pending_admin', 'supplement_requested']

        if leave.status not in allow_cancel_statuses:
            raise ValueError(f"❌ Không thể hủy đơn ở trạng thái: {leave.status}. Chỉ đơn đang chờ duyệt mới có thể hủy.")

        # Cập nhật trạng thái thành 'cancelled' để giữ vết trong DB
        leave.status = 'cancelled'
        
        # Nếu Duy An muốn đơn này biến mất hoàn toàn khỏi danh sách hiển thị thông thường
        # thì mới dùng is_deleted = True. Nhưng lời khuyên là nên giữ lại để đối soát.
        # leave.is_deleted = True 

        db.session.commit()
        return leave