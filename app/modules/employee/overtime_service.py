from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo
from decimal import Decimal

from app.extensions.db import db
from app.models import (
    Employee,
    HistoryLog,
    Notification,
    OvertimeRequest,
    Role,
    User,
)

from app.utils.time import get_current_time
from app.common.constants import OvertimeConfig 
VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


class EmployeeOvertimeService:

    OT_ALLOWED_TYPES = {
        "manual",
        "after_shift",
        "holiday",
        "weekend",
    }

    STATUS_SUBMITTED = "submitted"
    STATUS_PENDING_MANAGER = "pending_manager"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    @staticmethod
    def _users_by_role(role_name: str) -> list[User]:
        normalized = (role_name or "").strip().lower()
        if not normalized:
            return []

        roles = Role.query.filter(
            db.func.lower(Role.name) == normalized
        ).all()

        if not roles:
            roles = Role.query.filter(
                db.func.lower(Role.name).like(f"%{normalized}%")
            ).all()

        role_ids = [r.id for r in roles]

        if not role_ids:
            return []

        return User.query.filter(
            User.role_id.in_(role_ids),
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        ).all()

    @staticmethod
    def _employee_by_user(user_id: int | None) -> Employee:
        employee = Employee.query.filter_by(
            user_id=user_id,
            is_deleted=False,
        ).first()

        if not employee:
            raise ValueError("Không tìm thấy hồ sơ nhân viên")

        return employee

    @staticmethod
    def _build_datetime(target_date: date, time_str: str) -> datetime:
        parsed_time = datetime.strptime(time_str, "%H:%M").time()
        return datetime.combine(target_date, parsed_time).replace(tzinfo=VN_TIMEZONE)
    
    @staticmethod
    def submit_overtime(
        user_id: int | None,
        payload: dict,
        actor_user_id: int | None = None,
    ) -> dict:
        employee = EmployeeOvertimeService._employee_by_user(user_id)
        now = get_current_time() # Simulation-aware
        
        ot_date_raw = payload.get("overtime_date")
        ot_date = date.fromisoformat(ot_date_raw) if ot_date_raw else now.date()

        # 1. Kiểm tra trùng lặp
        existing = OvertimeRequest.query.filter_by(
            employee_id=employee.id,
            overtime_date=ot_date,
            is_deleted=False,
        ).first()
        if existing:
            raise ValueError(f"Bạn đã gửi yêu cầu OT cho ngày {ot_date.strftime('%d/%m/%Y')} rồi.")

        # 2. Xác định ngày lễ/cuối tuần
        holiday_info = OvertimeConfig._get_holiday_for_date(ot_date)
        is_holiday = holiday_info is not None
        is_weekend = ot_date.weekday() >= 5 
        
        holiday_name = ""
        if is_holiday:
            holiday_name = holiday_info.name if hasattr(holiday_info, 'name') else holiday_info.get("name")

        # 3. Thiết lập loại OT và Hệ số lương
        if is_holiday:
            detected_type = "holiday"
            multiplier =OvertimeConfig.MULTIPLIERS["holiday"]
            default_reason = f"Làm việc ngày lễ: {holiday_name}"
        elif is_weekend:
            detected_type = "weekend"
            multiplier = OvertimeConfig.MULTIPLIERS["weekend"]
            default_reason = "Làm việc cuối tuần"
        else:
            detected_type = (payload.get("request_type") or "after_shift").strip().lower()
            multiplier = OvertimeConfig.MULTIPLIERS["after_shift"]
            default_reason = "Tăng ca sau giờ hành chính"

        # 4. Xử lý thời gian
        raw_start_time = payload.get("start_time") or "18:00"
        raw_end_time = payload.get("end_time") or "22:00"
        start_ot_time = EmployeeOvertimeService._build_datetime(ot_date, raw_start_time)
        end_ot_time = EmployeeOvertimeService._build_datetime(ot_date, raw_end_time)

        if end_ot_time <= start_ot_time:
            raise ValueError("Giờ kết thúc phải sau giờ bắt đầu")

        if detected_type in ["holiday", "weekend"]:
            calculation_start = start_ot_time
        else:
            official_pay_start = EmployeeOvertimeService._build_datetime(ot_date, OvertimeConfig.OFFICIAL_PAY_START_TIME)
            calculation_start = max(start_ot_time, official_pay_start)

        if end_ot_time > calculation_start:
            billable_seconds = (end_ot_time - calculation_start).total_seconds()
        else:
            billable_seconds = 0
            
        hours = Decimal(str(billable_seconds / 3600)).quantize(Decimal("0.01"))
        
        if hours <= 0:
            raise ValueError("Thời gian OT không đủ (Ngày thường phải làm sau 19:00 mới tính lương)")

        # 6. Lưu Database
        reason = (payload.get("reason") or "").strip() or default_reason
        request_ot = OvertimeRequest(
            employee_id=employee.id,
            overtime_date=ot_date,
            overtime_hours=hours,
            requested_hours=hours,
            start_ot_time=start_ot_time,
            end_ot_time=end_ot_time,
            reason=reason,
            note=(payload.get("note") or "").strip() or None,
            status=EmployeeOvertimeService.STATUS_PENDING_MANAGER,
            is_holiday_ot=is_holiday,
            holiday_multiplier=multiplier,
            created_at=now,
            updated_at=now,
        )
        db.session.add(request_ot)
        db.session.flush()

        # 7. Thông báo cho Manager
        managers = EmployeeOvertimeService._users_by_role("manager")
        for m in managers:
            db.session.add(Notification(
                user_id=m.id,
                title="🔔 Yêu cầu OT mới",
                content=f"{employee.full_name} đăng ký OT {detected_type} ngày {ot_date.strftime('%d/%m')}: {hours}h",
                type="overtime",
                link="/manager/overtime",
                created_at=now,
                updated_at=now,
            ))

        # 8. Ghi History Log
        db.session.add(HistoryLog(
            employee_id=employee.id,
            action="OVERTIME_SUBMITTED",
            entity_type="overtime_request",
            entity_id=request_ot.id,
            description=f"Gửi yêu cầu OT ({detected_type}): {raw_start_time}-{raw_end_time} (x{multiplier})",
            performed_by=actor_user_id or user_id,
        ))

        db.session.commit()

        return {
            "message": "Đã gửi yêu cầu OT thành công",
            "status": request_ot.status,
            "request_id": request_ot.id,
            "billable_hours": float(hours),
            "multiplier": float(multiplier),
            "holiday_name": holiday_name
        }

