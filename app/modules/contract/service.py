from __future__ import annotations

from datetime import date, datetime, time, timedelta
from sqlalchemy import or_
from app.extensions.db import db
from app.models.attendance import Attendance, AttendanceStatus
from app.models.contract import Contract
from app.models.contract_proposal import ContractProposal
from app.models.department import Department
from app.models.employee import Employee

from app.models.leave import LeaveRequest
from app.models.leave_usage import EmployeeLeaveUsage

from app.models.notification import Notification
from app.models.history import HistoryLog
from app.models.overtime_request import OvertimeRequest
from app.models.salary import Salary
from app.models.complaint import Complaint
from app.models.position import Position
from app.models.role import Role
from app.models.user import User
from app.utils.time import get_current_time
class ManagerService:

    @staticmethod
    def get_contract_expiring(manager_id: int) -> list[dict]:
        sub_ids = [e.id for e in ManagerService._get_subordinates(manager_id)]
        if not sub_ids:
            return []

        today = date.today()
        limit = today + timedelta(days=30)
        rows = (
            Contract.query.filter(
                Contract.employee_id.in_(sub_ids),
                Contract.status == "active",
                Contract.end_date.isnot(None),
                Contract.end_date <= limit,
            )
            .order_by(Contract.end_date.asc())
            .all()
        )
        data = []
        for c in rows:
            remaining_days = (c.end_date - today).days if c.end_date else None
            data.append(
                {
                    "id": c.id,
                    "employee_id": c.employee_id,
                    "employee_name": c.employee.full_name if c.employee else "--",
                    "contract_code": c.contract_code,
                    "start_date": c.start_date.isoformat() if c.start_date else None,
                    "end_date": c.end_date.isoformat() if c.end_date else None,
                    "basic_salary": float(c.basic_salary or 0),
                    "days_left": remaining_days,
                }
            )
        return data
    @staticmethod
    def _latest_contracts_for_employee_ids(employee_ids: list[int]) -> dict[int, Contract]:
        if not employee_ids:
            return {}
        rows = (
            Contract.query.filter(Contract.employee_id.in_(employee_ids), Contract.is_deleted.is_(False))
            .order_by(Contract.employee_id.asc(), Contract.start_date.desc(), Contract.id.desc())
            .all()
        )
        latest: dict[int, Contract] = {}
        for row in rows:
            if row.employee_id not in latest:
                latest[row.employee_id] = row
        return latest

    @staticmethod
    def _resolve_contract_status(contract: Contract, employee_id: int, today: date | None = None) -> tuple[str, int | None]:
        current = today or date.today()
        end_date = contract.end_date
        days_left = (end_date - current).days if end_date else None
        pending = (
            ContractProposal.query.filter_by(contract_id=contract.id, employee_id=employee_id, is_deleted=False)
            .filter(ContractProposal.status.in_(["pending_hr", "pending_admin"]))
            .order_by(ContractProposal.created_at.desc())
            .first()
        )
        if pending:
            if pending.proposal_type == "renewal":
                return "pending_renewal", days_left
            if pending.proposal_type == "probation_conversion":
                return "pending_probation_conversion", days_left
            if pending.proposal_type == "termination":
                return "proposed_termination", days_left
        if (contract.status or "").lower() in {"terminated", "ended"}:
            return "ended", days_left
        if not end_date:
            return "active", None
        if days_left < 0:
            return "expired", days_left
        if days_left <= 30:
            return "expiring", days_left
        return "active", days_left
    @staticmethod
    def get_department_contract_overview(
        manager_id: int,
        *,
        employee_name: str | None = None,
        employee_code: str | None = None,
        contract_type: str | None = None,
        contract_status: str | None = None,
        end_date_from: str | None = None,
        end_date_to: str | None = None,
        department: str | None = None,
        position: str | None = None,
    ) -> dict:
        employees = ManagerService._get_subordinates(manager_id)
        ids = [e.id for e in employees]
        latest_contract_map = ManagerService._latest_contracts_for_employee_ids(ids)
        rows: list[dict] = []
        today = date.today()
        for emp in employees:
            contract = latest_contract_map.get(emp.id)
            if not contract:
                continue
            status, days_left = ManagerService._resolve_contract_status(contract, emp.id, today=today)
            contract_type_value = getattr(contract, "contract_type", None) or emp.employment_type or "contract"
            rows.append(
                {
                    "id": contract.id,
                    "employee_id": emp.id,
                    "employee_code": f"EMP{emp.id:04d}",
                    "employee_name": emp.full_name,
                    "position": emp.position.position_name if emp.position else "--",
                    "department": emp.department.department_name if emp.department else "--",
                    "contract_type": contract_type_value,
                    "start_date": contract.start_date.isoformat() if contract.start_date else None,
                    "end_date": contract.end_date.isoformat() if contract.end_date else None,
                    "days_left": days_left,
                    "status": status,
                    "status_label": ManagerService.CONTRACT_STATUS_LABELS.get(status, status),
                    "latest_renewal_at": contract.updated_at.isoformat() if contract.updated_at else None,
                }
            )
        key_name = (employee_name or "").strip().lower()
        key_code = (employee_code or "").strip().lower()
        key_department = (department or "").strip().lower()
        key_position = (position or "").strip().lower()
        if key_name:
            rows = [x for x in rows if key_name in (x["employee_name"] or "").lower()]
        if key_code:
            rows = [x for x in rows if key_code in (x["employee_code"] or "").lower()]
        if (contract_type or "").strip().lower() not in {"", "all"}:
            rows = [x for x in rows if (x["contract_type"] or "").lower() == contract_type.strip().lower()]
        if (contract_status or "").strip().lower() not in {"", "all"}:
            rows = [x for x in rows if (x["status"] or "").lower() == contract_status.strip().lower()]
        if key_department:
            rows = [x for x in rows if key_department in (x["department"] or "").lower()]
        if key_position:
            rows = [x for x in rows if key_position in (x["position"] or "").lower()]
        if end_date_from:
            rows = [x for x in rows if x["end_date"] and x["end_date"] >= end_date_from]
        if end_date_to:
            rows = [x for x in rows if x["end_date"] and x["end_date"] <= end_date_to]

        summary = {
            "total_contracts": len(rows),
            "expiring": sum(1 for x in rows if x["status"] == "expiring"),
            "probation": sum(1 for x in rows if (x["contract_type"] or "").lower() == "probation"),
            "pending_renewal": sum(1 for x in rows if x["status"] == "pending_renewal"),
            "termination_proposals": ContractProposal.query.filter_by(manager_id=manager_id, proposal_type="termination", is_deleted=False).filter(
                ContractProposal.status.in_(["pending_hr", "pending_admin"])
            ).count(),
        }
        return {"summary": summary, "rows": rows}

    @staticmethod
    def get_contract_detail_for_manager(manager_id: int, contract_id: int) -> dict:
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")
        subordinate_ids = {x.id for x in ManagerService._get_subordinates(manager_id)}
        if contract.employee_id not in subordinate_ids:
            raise ValueError("Không có quyền xem hợp đồng này")
        emp = contract.employee
        proposals = (
            ContractProposal.query.filter_by(contract_id=contract.id, employee_id=contract.employee_id, is_deleted=False)
            .order_by(ContractProposal.created_at.desc())
            .limit(10)
            .all()
        )
        status, _ = ManagerService._resolve_contract_status(contract, contract.employee_id)
        return {
            "id": contract.id,
            "employee": {
                "id": emp.id if emp else None,
                "code": f"EMP{emp.id:04d}" if emp else "--",
                "full_name": emp.full_name if emp else "--",
                "position": emp.position.position_name if emp and emp.position else "--",
                "department": emp.department.department_name if emp and emp.department else "--",
            },
            "contract_type": getattr(contract, "contract_type", None) or (emp.employment_type if emp else None),
            "basic_salary": float(contract.basic_salary or 0),
            "allowance": 0.0,
            "start_date": contract.start_date.isoformat() if contract.start_date else None,
            "end_date": contract.end_date.isoformat() if contract.end_date else None,
            "status": status,
            "status_label": ManagerService.CONTRACT_STATUS_LABELS.get(status, status),
            "performance_review": "Đánh giá chuyên môn sẽ được HR tổng hợp theo kỳ.",
            "manager_note": proposals[0].professional_note if proposals else None,
            "renewal_history": [
                {
                    "proposal_type": p.proposal_type,
                    "status": p.status,
                    "proposed_date": p.proposed_date.isoformat() if p.proposed_date else None,
                    "reason": p.reason,
                    "professional_note": p.professional_note,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in proposals
            ],
        }

    @staticmethod
    def _notify_hr_admin(title: str, content: str, link: str = "/hr/contracts") -> None:
        recipients = User.query.join(Role, User.role_id == Role.id).filter(Role.name.in_(["HR", "Admin"])).all()
        for user in recipients:
            db.session.add(Notification(user_id=user.id, title=title, content=content, type="contract", link=link))

    @staticmethod
    def create_contract_proposal(
        manager_id: int,
        *,
        contract_id: int,
        proposal_type: str,
        reason: str,
        proposed_date: str | None = None,
        proposed_duration_months: int | None = None,
        professional_note: str | None = None,
    ) -> dict:
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")
        subordinate_ids = {x.id for x in ManagerService._get_subordinates(manager_id)}
        if contract.employee_id not in subordinate_ids:
            raise ValueError("Không có quyền thao tác hợp đồng này")
        normalized_type = (proposal_type or "").strip().lower()
        if normalized_type not in {"renewal", "termination", "probation_conversion"}:
            raise ValueError("Loại đề xuất không hợp lệ")
        if not (reason or "").strip():
            raise ValueError("Lý do đề xuất là bắt buộc")
        proposal = ContractProposal(
            contract_id=contract.id,
            employee_id=contract.employee_id,
            manager_id=manager_id,
            proposal_type=normalized_type,
            reason=reason.strip(),
            proposed_date=datetime.strptime(proposed_date, "%Y-%m-%d").date() if proposed_date else None,
            proposed_duration_months=proposed_duration_months,
            professional_note=(professional_note or "").strip() or None,
            status="pending_hr",
        )
        db.session.add(proposal)
        db.session.flush()
        db.session.add(
            HistoryLog(
                employee_id=contract.employee_id,
                action="MANAGER_CONTRACT_PROPOSAL",
                entity_type="contract_proposal",
                entity_id=proposal.id,
                description=f"Manager đề xuất {normalized_type} cho hợp đồng #{contract.id}",
                performed_by=manager_id,
            )
        )
        ManagerService._notify_hr_admin(
            title="Đề xuất hợp đồng mới từ Manager",
            content=f"{contract.employee.full_name if contract.employee else 'Nhân viên'}: {normalized_type}",
        )
        db.session.commit()
        return {"id": proposal.id, "status": proposal.status, "message": "Đã gửi đề xuất đến HR/Admin"}
    @staticmethod
    def confirm_contract_review(manager_id: int, contract_id: int, note: str | None = None) -> dict:
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")
        subordinate_ids = {x.id for x in ManagerService._get_subordinates(manager_id)}
        if contract.employee_id not in subordinate_ids:
            raise ValueError("Không có quyền xác nhận")
        db.session.add(
            HistoryLog(
                employee_id=contract.employee_id,
                action="MANAGER_CONTRACT_REVIEW_CONFIRMED",
                entity_type="contract",
                entity_id=contract.id,
                description=(note or "Manager đã xác nhận review thông tin chuyên môn."),
                performed_by=manager_id,
            )
        )
        ManagerService._notify_hr_admin(
            title="Manager đã xác nhận review hợp đồng",
            content=f"Hợp đồng #{contract.contract_code} đã được Manager review.",
        )
        db.session.commit()
        return {"message": "Đã xác nhận review", "contract_id": contract.id}

    @staticmethod
    def _latest_contract(employee_id: int) -> Contract | None:
        return Contract.query.filter_by(employee_id=employee_id, is_deleted=False).order_by(Contract.start_date.desc()).first()

