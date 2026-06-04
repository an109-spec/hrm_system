from __future__ import annotations
from datetime import date
from typing import Any

from flask import url_for
from app.constants.employee import WorkingStatus
from app.extensions.db import db
from app.models import Contract, Employee, HistoryLog, Notification, ResignationRequest, Role, User
from app.utils.time import get_current_time  
from app.constants.resignation import ResignationStatus
class ResignationService:

    @staticmethod
    def list_users_by_roles(role_names: list[str]) -> list[User]:
        return (
            User.query.join(Role, User.role_id == Role.id)
            .filter(
                Role.name.in_(role_names),     
                User.is_active == True,       
                User.is_deleted == False,    
                Role.is_deleted == False   
            )
            .all()
        )

    @staticmethod
    def _base_create_resignation(
        *,
        employee: Employee,
        manager_id: int | None,
        request_type: str,
        status: str,
        expected_last_day: date,
        reason_category: str,
        reason_text: str | None,
        extra_note: str | None,
        attachment_url: str | None,
        handover_employee_id: int | None,
        history_action: str,
        history_desc: str,
        performed_by: int
    ) -> ResignationRequest:
        
        # 1. Kiểm tra đơn trùng lặp (Logic dùng chung)
        pending = ResignationRequest.query.filter(
            ResignationRequest.employee_id == employee.id,
            ResignationRequest.status.in_([
                ResignationStatus.PENDING_MANAGER, 
                ResignationStatus.PENDING_HR, 
                ResignationStatus.PENDING_ADMIN
            ]),
            ResignationRequest.is_deleted == False 
        ).first()
        
        if pending:
            raise ValueError("Nhân viên đã có đơn nghỉ việc đang xử lý trên hệ thống")

        now_ts = get_current_time()
        
        try:
            # 2. Khởi tạo request
            request_item = ResignationRequest(
                employee_id=employee.id,
                manager_id=manager_id,
                handover_employee_id=handover_employee_id,
                request_type=request_type,
                status=status,
                expected_last_day=expected_last_day,
                reason_category=reason_category,
                reason_text=reason_text,
                extra_note=extra_note,
                attachment_url=attachment_url,
                created_at=now_ts
            )
            db.session.add(request_item)
            
            # 3. Cập nhật trạng thái
            employee.working_status = WorkingStatus.PENDING_RESIGNATION
            db.session.flush()
            
            # 4. Ghi log
            HistoryLog.append(
                employee_id=employee.id,
                action=history_action,
                entity_type="resignation",
                entity_id=request_item.id,
                description=history_desc,
                performed_by=performed_by
            )
            db.session.flush()
            
            # 5. Thông báo
            ResignationService._notify_status_change(request_item)
            
            db.session.commit()
            return request_item
            
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def create_request(*, employee: Employee, **kwargs) -> ResignationRequest:
        return ResignationService._base_create_resignation(
            employee=employee,
            manager_id=employee.manager_id,
            status=ResignationStatus.PENDING_MANAGER,
            history_action="RESIGNATION_SUBMITTED",
            history_desc=f"{employee.full_name or 'Nhân viên'} gửi đơn nghỉ việc, ngày dự kiến: {kwargs['expected_last_day'].isoformat()}",
            performed_by=employee.user_id,
            **kwargs
        )

    @staticmethod
    def create_proposal_by_manager(*, manager: Employee, employee: Employee, **kwargs) -> ResignationRequest:
        return ResignationService._base_create_resignation(
            employee=employee,
            manager_id=manager.id,
            status=ResignationStatus.PENDING_HR,
            history_action="MANAGER_PROPOSAL_SUBMITTED",
            history_desc=f"Quản lý {manager.full_name} đề xuất nghỉ cho {employee.full_name}.",
            performed_by=manager.user_id,
            # Proposal có thể không cần handover_employee_id nên để mặc định None
            handover_employee_id=kwargs.get('handover_employee_id'),
            **kwargs
        )

    @staticmethod
    def _notify_status_change(request_item: ResignationRequest) -> None:
        target_link = url_for('resignation.get_resignation', resignation_id=request_item.id)
        employee = request_item.employee
        employee_name = employee.full_name or f"Nhân viên #{request_item.employee_id}"
        now_ts = get_current_time()
        if request_item.status == ResignationStatus.PENDING_MANAGER:
            if employee and employee.manager and employee.manager.user_id:
                db.session.add(Notification(
                    user_id=employee.manager.user_id,
                    title="Đơn nghỉ việc mới cần duyệt",
                    content=f"{employee_name} đã gửi đơn nghỉ việc.",
                    type="resignation",
                    link=target_link,
                    created_at=now_ts
                ))

        elif request_item.status == ResignationStatus.PENDING_HR:
            for user in ResignationService.list_users_by_roles(["HR"]):
                db.session.add(Notification(
                    user_id=user.id,
                    title="Đơn cần HR xử lý",
                    content=f"Đơn của {employee_name} đã được Manager duyệt, chờ HR xử lý.",
                    type="resignation",
                    link=target_link,
                    created_at=now_ts
                ))
        elif request_item.status == ResignationStatus.PENDING_ADMIN:
            for user in ResignationService.list_users_by_roles(["ADMIN"]):
                db.session.add(Notification(
                    user_id=user.id,
                    title="Đơn cần Admin phê duyệt cuối",
                    content=f"Đơn của {employee_name} đã được HR duyệt, chờ Admin xử lý.",
                    type="resignation",
                    link=target_link,
                    created_at=now_ts
                ))
        
        # Gửi cho Nhân viên (khi bị từ chối)
        elif request_item.status == ResignationStatus.REJECTED:
            if employee and employee.user_id:
                db.session.add(Notification(
                    user_id=employee.user_id,
                    title="Đơn nghỉ việc bị từ chối",
                    content=f"Đơn nghỉ việc của bạn đã bị từ chối.",
                    type="resignation",
                    link=target_link,
                    created_at=now_ts
                ))

    @staticmethod
    def _complete_transaction(request_item: ResignationRequest) -> None:
        """Hàm dùng chung để lưu thay đổi, gửi thông báo và commit giao dịch"""
        db.session.flush()
        ResignationService._notify_status_change(request_item)
        db.session.commit()

    @staticmethod
    def manager_review(request_item: ResignationRequest, manager_user_id: int, action: str, note: str | None) -> None:
        if request_item.status != ResignationStatus.PENDING_MANAGER:
            raise ValueError("Đơn nghỉ việc không ở trạng thái chờ Manager duyệt")
            
        try:
            if action == "approve":
                request_item.status = ResignationStatus.PENDING_HR
                request_item.manager_note = note
                request_item.reviewed_by_manager_id = manager_user_id
                HistoryLog.append(
                    employee_id=request_item.employee_id,
                    action="RESIGNATION_MANAGER_APPROVED",
                    entity_type="resignation",
                    entity_id=request_item.id,
                    description=note or "Manager duyệt và chuyển HR xử lý offboarding",
                    performed_by=manager_user_id
                )
            elif action == "reject":
                request_item.status = ResignationStatus.REJECTED
                request_item.manager_note = note
                request_item.reviewed_by_manager_id = manager_user_id
                if request_item.employee:
                    request_item.employee.working_status = WorkingStatus.ACTIVE
                HistoryLog.append(
                    employee_id=request_item.employee_id,
                    action="RESIGNATION_MANAGER_REJECTED",
                    entity_type="resignation",
                    entity_id=request_item.id,
                    description=note or "Manager từ chối đơn nghỉ việc",
                    performed_by=manager_user_id
                )
            else:
                raise ValueError("Hành động xử lý (Action) không hợp lệ")
                
            ResignationService._complete_transaction(request_item)
            
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def hr_process(request_item: ResignationRequest, hr_user_id: int, action: str, payload: dict[str, Any]) -> None:
        if request_item.status != ResignationStatus.PENDING_HR:
            raise ValueError("Đơn nghỉ việc không ở trạng thái HR xử lý")
            
        try:
            if action == "forward_admin":
                request_item.status = ResignationStatus.PENDING_ADMIN
                request_item.hr_note = (payload.get("hr_note") or "").strip() or None
                request_item.final_payroll_note = (payload.get("final_payroll_note") or "").strip() or None
                request_item.final_attendance_note = (payload.get("final_attendance_note") or "").strip() or None
                request_item.leave_balance_note = (payload.get("leave_balance_note") or "").strip() or None
                request_item.insurance_note = (payload.get("insurance_note") or "").strip() or None
                request_item.asset_handover_note = (payload.get("asset_handover_note") or "").strip() or None
                request_item.processed_by_hr_id = hr_user_id
                
                HistoryLog.append(
                    employee_id=request_item.employee_id,
                    action="RESIGNATION_HR_FORWARDED",
                    entity_type="resignation",
                    entity_id=request_item.id,
                    description="HR đã hoàn tất offboarding checklist và chuyển Admin duyệt cuối",
                    performed_by=hr_user_id
                )
            elif action == "reject":
                request_item.status = ResignationStatus.REJECTED
                request_item.hr_note = (payload.get("hr_note") or "").strip() or None
                request_item.processed_by_hr_id = hr_user_id
                if request_item.employee:
                    request_item.employee.working_status = WorkingStatus.ACTIVE
                HistoryLog.append(
                    employee_id=request_item.employee_id,
                    action="RESIGNATION_HR_REJECTED",
                    entity_type="resignation",
                    entity_id=request_item.id,
                    description=request_item.hr_note or "HR từ chối hồ sơ nghỉ việc",
                    performed_by=hr_user_id
                )
            else:
                raise ValueError("Hành động xử lý (Action) không hợp lệ")
                
            ResignationService._complete_transaction(request_item)
            
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def admin_finalize(request_item: ResignationRequest, admin_user_id: int, action: str, note: str | None) -> None:
        if request_item.status != ResignationStatus.PENDING_ADMIN:
            raise ValueError("Đơn nghỉ việc không ở trạng thái chờ Admin duyệt")

        now_ts = get_current_time()

        try:
            if action == "approve":
                request_item.status = ResignationStatus.APPROVED
                request_item.admin_note = note
                request_item.approved_by_admin_id = admin_user_id
                
                if request_item.employee:
                    request_item.employee.working_status = WorkingStatus.RESIGNED
                    if request_item.employee.user:
                        request_item.employee.user.is_active = False
                        request_item.employee.user.locked_at = now_ts  
                        request_item.employee.user.locked_by = admin_user_id
                        request_item.employee.user.lock_reason = "Khoá tài khoản do nghỉ việc"

                active_contract = Contract.query.filter_by(employee_id=request_item.employee_id).order_by(Contract.start_date.desc(), Contract.id.desc()).first()
                if active_contract and (active_contract.status or "").lower() == "active":
                    active_contract.status = "terminated"

                HistoryLog.append(
                    employee_id=request_item.employee_id,
                    action="RESIGNATION_ADMIN_APPROVED",
                    entity_type="resignation",
                    entity_id=request_item.id,
                    description=note or "Admin duyệt nghỉ việc, khoá tài khoản và cập nhật trạng thái nhân sự",
                    performed_by=admin_user_id
                )

            elif action == "reject":
                request_item.status = ResignationStatus.REJECTED
                request_item.admin_note = note
                request_item.approved_by_admin_id = admin_user_id
                
                if request_item.employee:
                    request_item.employee.working_status = WorkingStatus.ACTIVE
                    
                HistoryLog.append(
                    employee_id=request_item.employee_id,
                    action="RESIGNATION_ADMIN_REJECTED",
                    entity_type="resignation",
                    entity_id=request_item.id,
                    description=note or "Admin từ chối nghỉ việc",
                    performed_by=admin_user_id
                )
            else:
                raise ValueError("Hành động xử lý (Action) không hợp lệ")

            ResignationService._complete_transaction(request_item)
            
        except Exception as e:
            db.session.rollback()
            raise e