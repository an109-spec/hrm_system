from datetime import date
from app.extensions.db import db

from app.models.leave import LeaveRequest, LeaveType
from app.models.leave_usage import EmployeeLeaveUsage
from app.models.notification import Notification
from app.models.employee import Employee

from .dto import LeaveRequestDTO
from .validators import LeaveValidator


class LeaveService:

    # =========================
    # LEAVE BALANCE
    # =========================
    @staticmethod
    def get_leave_balance(employee_id: int):
        year = date.today().year

        usage = EmployeeLeaveUsage.query.filter_by(
            employee_id=employee_id,
            year=year
        ).first()

        return usage

    # =========================
    # CREATE LEAVE REQUEST
    # =========================
    @staticmethod
    def create_leave_request(dto: LeaveRequestDTO):

        LeaveValidator.validate_date_range(dto.from_date, dto.to_date)
        LeaveValidator.validate_reason(dto.reason)

        usage = LeaveService.get_leave_balance(dto.employee_id)

        requested_days = (dto.to_date - dto.from_date).days + 1

        if usage:
            LeaveValidator.validate_leave_days_limit(
                usage.remaining_days,
                requested_days
            )

        leave = LeaveRequest(
            employee_id=dto.employee_id,
            leave_type_id=dto.leave_type_id,
            from_date=dto.from_date,
            to_date=dto.to_date,
            reason=dto.reason,
            status="pending",
            approved_by=dto.approved_by
        )

        db.session.add(leave)

        # notification cho manager
        employee = Employee.query.get(dto.employee_id)

        if employee and employee.manager_id:
            manager = Employee.query.get(employee.manager_id)

            if manager and manager.user_id:
                db.session.add(Notification(
                    title="Đơn xin nghỉ phép mới",
                    content=f"{employee.full_name} vừa gửi đơn xin nghỉ",
                    user_id=manager.user_id,
                    type="leave"
                ))

        db.session.commit()
        return leave

    # =========================
    # LIST LEAVE
    # =========================
    @staticmethod
    def get_my_requests(employee_id: int):
        return (
            LeaveRequest.query
            .filter_by(employee_id=employee_id, is_deleted=False)
            .order_by(LeaveRequest.created_at.desc())
            .all()
        )

    # =========================
    # CANCEL REQUEST
    # =========================
    @staticmethod
    def cancel_request(leave_id: int, employee_id: int):
        leave = LeaveRequest.query.filter_by(
            id=leave_id,
            employee_id=employee_id
        ).first()

        if not leave:
            raise ValueError("Leave request not found")

        if leave.status != "pending":
            raise ValueError("Only pending request can be cancelled")

        leave.is_deleted = True

        db.session.commit()
        return leave