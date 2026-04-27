from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from sqlalchemy import func

from app.extensions.db import db
from app.models import Contract, Employee, HistoryLog, Notification, ResignationRequest, Role, User

ROLE_EMPLOYEE = "employee"
ROLE_MANAGER = "manager"
ROLE_HR = "hr"
ROLE_ADMIN = "admin"

STATUS_PENDING_MANAGER = "pending_manager"
STATUS_PENDING_HR = "pending_hr"
STATUS_PENDING_ADMIN = "pending_admin"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

REQUEST_EMPLOYEE = "employee"
REQUEST_MANAGER = "manager_proposal"


class ResignationService:
    @staticmethod
    def list_users_by_roles(role_names: Iterable[str]) -> list[User]:
        values = [v.lower() for v in role_names]
        return (
            User.query.join(Role, User.role_id == Role.id)
            .filter(func.lower(Role.name).in_(values), User.is_active.is_(True))
            .all()
        )

    @staticmethod
    def create_request(
        *,
        employee: Employee,
        expected_last_day: date,
        reason_category: str,
        reason_text: str | None,
        extra_note: str | None,
        handover_employee_id: int | None,
        attachment_url: str | None,
        request_type: str,
    ) -> ResignationRequest:
        pending = ResignationRequest.query.filter(
            ResignationRequest.employee_id == employee.id,
            ResignationRequest.status.in_([STATUS_PENDING_MANAGER, STATUS_PENDING_HR, STATUS_PENDING_ADMIN]),
        ).first()
        if pending:
            raise ValueError("Nhân viên đã có đơn nghỉ việc đang xử lý")

        request_item = ResignationRequest(
            employee_id=employee.id,
            manager_id=employee.manager_id,
            handover_employee_id=handover_employee_id,
            request_type=request_type,
            status=STATUS_PENDING_MANAGER,
            expected_last_day=expected_last_day,
            reason_category=reason_category,
            reason_text=reason_text,
            extra_note=extra_note,
            attachment_url=attachment_url,
        )
        db.session.add(request_item)
        employee.working_status = "pending_resignation"
        db.session.add(
            HistoryLog(
                employee_id=employee.id,
                action="RESIGNATION_SUBMITTED",
                entity_type="resignation",
                description=f"{employee.full_name} gửi đơn nghỉ việc, ngày dự kiến nghỉ {expected_last_day.isoformat()}",
                performed_by=employee.user_id,
            )
        )
        db.session.flush()
        ResignationService._notify_new_request(request_item)
        db.session.commit()
        return request_item

    @staticmethod
    def _notify_new_request(request_item: ResignationRequest) -> None:
        employee = request_item.employee
        if employee and employee.manager and employee.manager.user_id:
            db.session.add(
                Notification(
                    user_id=employee.manager.user_id,
                    title="Đơn nghỉ việc mới cần duyệt",
                    content=f"{employee.full_name} vừa gửi đơn nghỉ việc.",
                    type="resignation",
                    link="/manager/department-employees",
                )
            )
        for user in ResignationService.list_users_by_roles([ROLE_HR]):
            db.session.add(
                Notification(
                    user_id=user.id,
                    title="Resignation mới cần HR xử lý",
                    content=f"Đơn nghỉ việc của {employee.full_name} đang chờ xử lý theo quy trình offboarding.",
                    type="resignation",
                    link="/hr/employees",
                )
            )
        for user in ResignationService.list_users_by_roles([ROLE_ADMIN]):
            db.session.add(
                Notification(
                    user_id=user.id,
                    title="Resignation mới cần theo dõi",
                    content=f"{employee.full_name} đã phát sinh resignation workflow.",
                    type="resignation",
                    link="/admin/employees",
                )
            )

    @staticmethod
    def manager_review(request_item: ResignationRequest, manager_user_id: int, action: str, note: str | None) -> None:
        if request_item.status != STATUS_PENDING_MANAGER:
            raise ValueError("Đơn nghỉ việc không ở trạng thái chờ Manager duyệt")
        if action == "approve":
            request_item.status = STATUS_PENDING_HR
            request_item.manager_note = note
            request_item.reviewed_by_manager_id = manager_user_id
            db.session.add(
                HistoryLog(
                    employee_id=request_item.employee_id,
                    action="RESIGNATION_MANAGER_APPROVED",
                    entity_type="resignation",
                    entity_id=request_item.id,
                    description=note or "Manager duyệt và chuyển HR xử lý offboarding",
                    performed_by=manager_user_id,
                )
            )
        elif action == "reject":
            request_item.status = STATUS_REJECTED
            request_item.manager_note = note
            request_item.reviewed_by_manager_id = manager_user_id
            request_item.employee.working_status = "active"
            db.session.add(
                HistoryLog(
                    employee_id=request_item.employee_id,
                    action="RESIGNATION_MANAGER_REJECTED",
                    entity_type="resignation",
                    entity_id=request_item.id,
                    description=note or "Manager từ chối đơn nghỉ việc",
                    performed_by=manager_user_id,
                )
            )
        else:
            raise ValueError("Action không hợp lệ")
        ResignationService._notify_employee_status(request_item)
        db.session.commit()

    @staticmethod
    def hr_process(request_item: ResignationRequest, hr_user_id: int, action: str, payload: dict) -> None:
        if request_item.status != STATUS_PENDING_HR:
            raise ValueError("Đơn nghỉ việc không ở trạng thái HR xử lý")
        if action == "forward_admin":
            request_item.status = STATUS_PENDING_ADMIN
            request_item.hr_note = (payload.get("hr_note") or "").strip() or None
            request_item.final_payroll_note = (payload.get("final_payroll_note") or "").strip() or None
            request_item.final_attendance_note = (payload.get("final_attendance_note") or "").strip() or None
            request_item.leave_balance_note = (payload.get("leave_balance_note") or "").strip() or None
            request_item.insurance_note = (payload.get("insurance_note") or "").strip() or None
            request_item.asset_handover_note = (payload.get("asset_handover_note") or "").strip() or None
            request_item.processed_by_hr_id = hr_user_id
            db.session.add(
                HistoryLog(
                    employee_id=request_item.employee_id,
                    action="RESIGNATION_HR_FORWARDED",
                    entity_type="resignation",
                    entity_id=request_item.id,
                    description="HR đã hoàn tất offboarding checklist và chuyển Admin duyệt cuối",
                    performed_by=hr_user_id,
                )
            )
            for user in ResignationService.list_users_by_roles([ROLE_ADMIN]):
                db.session.add(
                    Notification(
                        user_id=user.id,
                        title="Cần Admin duyệt nghỉ việc",
                        content=f"Resignation của {request_item.employee.full_name} đang chờ duyệt cuối.",
                        type="resignation",
                        link="/admin/employees",
                    )
                )
        elif action == "reject":
            request_item.status = STATUS_REJECTED
            request_item.hr_note = (payload.get("hr_note") or "").strip() or None
            request_item.processed_by_hr_id = hr_user_id
            request_item.employee.working_status = "active"
            db.session.add(
                HistoryLog(
                    employee_id=request_item.employee_id,
                    action="RESIGNATION_HR_REJECTED",
                    entity_type="resignation",
                    entity_id=request_item.id,
                    description=request_item.hr_note or "HR từ chối hồ sơ nghỉ việc",
                    performed_by=hr_user_id,
                )
            )
        else:
            raise ValueError("Action không hợp lệ")

        ResignationService._notify_employee_status(request_item)
        db.session.commit()

    @staticmethod
    def admin_finalize(request_item: ResignationRequest, admin_user_id: int, action: str, note: str | None) -> None:
        if request_item.status != STATUS_PENDING_ADMIN:
            raise ValueError("Đơn nghỉ việc không ở trạng thái chờ Admin duyệt")
        if action == "approve":
            request_item.status = STATUS_APPROVED
            request_item.admin_note = note
            request_item.approved_by_admin_id = admin_user_id
            request_item.employee.working_status = "resigned"
            if request_item.employee.user:
                request_item.employee.user.is_active = False
                request_item.employee.user.locked_at = datetime.utcnow()
                request_item.employee.user.locked_by = admin_user_id
                request_item.employee.user.lock_reason = "Khoá tài khoản do nghỉ việc"
            active_contract = (
                Contract.query.filter_by(employee_id=request_item.employee_id)
                .order_by(Contract.start_date.desc(), Contract.id.desc())
                .first()
            )
            if active_contract and (active_contract.status or "").lower() == "active":
                active_contract.status = "terminated"
            db.session.add(
                HistoryLog(
                    employee_id=request_item.employee_id,
                    action="RESIGNATION_ADMIN_APPROVED",
                    entity_type="resignation",
                    entity_id=request_item.id,
                    description=note or "Admin duyệt nghỉ việc, khoá tài khoản và cập nhật trạng thái nhân sự",
                    performed_by=admin_user_id,
                )
            )
        elif action == "reject":
            request_item.status = STATUS_REJECTED
            request_item.admin_note = note
            request_item.approved_by_admin_id = admin_user_id
            request_item.employee.working_status = "active"
            db.session.add(
                HistoryLog(
                    employee_id=request_item.employee_id,
                    action="RESIGNATION_ADMIN_REJECTED",
                    entity_type="resignation",
                    entity_id=request_item.id,
                    description=note or "Admin từ chối nghỉ việc",
                    performed_by=admin_user_id,
                )
            )
        else:
            raise ValueError("Action không hợp lệ")
        ResignationService._notify_employee_status(request_item)
        db.session.commit()

    @staticmethod
    def _notify_employee_status(request_item: ResignationRequest) -> None:
        if request_item.employee and request_item.employee.user_id:
            db.session.add(
                Notification(
                    user_id=request_item.employee.user_id,
                    title="Cập nhật đơn nghỉ việc",
                    content=f"Trạng thái đơn nghỉ việc mới nhất: {request_item.status}",
                    type="resignation",
                    link="/employee/profile",
                )
            )