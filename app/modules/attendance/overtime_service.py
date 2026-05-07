from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal

from app.extensions.db import db
from app.models import (
    Attendance,
    Employee,
    OvertimeRequest,
)
from app.common.exceptions import ValidationError
from app.modules.attendance.service import AttendanceService


class OvertimeService:
    """
    Service xử lý nghiệp vụ tăng ca (OT).
    Bao gồm: tạo đơn, duyệt, từ chối, kiểm tra điều kiện, tính giờ.
    """

    OT_START = AttendanceService.OT_CHECKIN_OPEN   # 19:00 — single source of truth
    OT_END   = AttendanceService.OT_END            # 22:00

    # ══════════════════════════════════════════════════════════════════════
    # CREATE OT REQUEST
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def create_overtime_request(
        employee_id: int,
        target_date: date,
        reason: str,
    ) -> dict:
        """
        Tạo đơn xin tăng ca.
        Điều kiện: chưa có đơn OT cùng ngày, lý do không rỗng.
        """
        if not reason or not reason.strip():
            raise ValidationError("Vui lòng nhập lý do tăng ca")

        existed = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == target_date,
            OvertimeRequest.is_deleted.is_(False),
        ).first()

        if existed:
            raise ValidationError("Ngày này đã tồn tại đơn tăng ca")

        ot_req = OvertimeRequest(
            employee_id=employee_id,
            overtime_date=target_date,
            reason=reason.strip(),
            status="pending",
        )

        db.session.add(ot_req)
        db.session.commit()

        return {
            "message":    "Tạo đơn tăng ca thành công",
            "request_id": ot_req.id,
        }

    # ══════════════════════════════════════════════════════════════════════
    # APPROVE OT
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def approve_overtime(
        request_id: int,
        approver_id: int | None = None,
    ) -> dict:
        """
        HR / Manager duyệt đơn tăng ca.
        Sau khi approve:
        - OT request.status = approved
        - Attendance chuyển sang PRE_OT_REST
        - Employee nhận notification
        """
        ot_req = OvertimeRequest.query.get(request_id)

        if not ot_req:
            raise ValidationError("Không tìm thấy đơn tăng ca")

        if ot_req.status not in ("pending", "pending_hr", "pending_admin"):
            raise ValidationError("Đơn này đã được xử lý trước đó")

        ot_req.status      = "approved"
        ot_req.approved_by = approver_id
        ot_req.approved_at = datetime.utcnow()

        # Hook → cập nhật attendance + tạo notification
        AttendanceService.handle_ot_approved(ot_req)

        db.session.commit()

        return {"message": "Đã duyệt đơn tăng ca"}

    # ══════════════════════════════════════════════════════════════════════
    # REJECT OT
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def reject_overtime(
        request_id: int,
        reject_reason: str = "",
        approver_id: int | None = None,
    ) -> dict:
        """
        HR / Manager từ chối đơn tăng ca.
        Sau khi reject:
        - OT request.status = rejected
        - Attendance chuyển sang COMPLETED
        - Employee nhận notification
        """
        ot_req = OvertimeRequest.query.get(request_id)

        if not ot_req:
            raise ValidationError("Không tìm thấy đơn tăng ca")

        if ot_req.status not in ("pending", "pending_hr", "pending_admin"):
            raise ValidationError("Đơn này đã được xử lý trước đó")

        ot_req.status        = "rejected"
        ot_req.reject_reason = reject_reason
        ot_req.approved_by   = approver_id
        ot_req.approved_at   = datetime.utcnow()

        # Hook → finalize attendance + tạo notification
        AttendanceService.handle_ot_rejected(ot_req, reason=reject_reason)

        db.session.commit()

        return {"message": "Đã từ chối đơn tăng ca"}

    # ══════════════════════════════════════════════════════════════════════
    # CAN START OT
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def can_start_ot(employee_id: int, target_date: date) -> bool:
        """
        Kiểm tra nhân viên có được bắt đầu (xác thực) OT hay không.

        Điều kiện:
        - Đã có attendance hôm đó
        - Đã checkout ca chính
        - Có đơn OT đã approved
        - Chưa OT check-in

        Lưu ý: KHÔNG chặn theo giờ — employee xác thực được ngay sau khi approved.
        Công OT vẫn clamp về 19:00 khi tính thực tế.
        """
        attendance = Attendance.query.filter_by(
            employee_id=employee_id,
            date=target_date
        ).first()

        if not attendance:
            raise ValidationError("Chưa có dữ liệu chấm công hôm nay")

        if not attendance.check_out:
            raise ValidationError("Bạn chưa checkout ca chính")

        if attendance.overtime_check_in:
            raise ValidationError("Bạn đã bắt đầu OT rồi")

        ot_req = OvertimeRequest.query.filter_by(
            employee_id=employee_id,
            overtime_date=target_date,
            status="approved",
        ).filter(OvertimeRequest.is_deleted.is_(False)).first()

        if not ot_req:
            raise ValidationError("Bạn chưa có đơn tăng ca được duyệt")

        return True

    # ══════════════════════════════════════════════════════════════════════
    # CALCULATE OVERTIME
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def calculate_overtime(
        overtime_check_in: datetime,
        overtime_check_out: datetime,
    ) -> Decimal:
        """Tính giờ OT raw (chưa nhân hệ số). Clamp về 19:00–22:00."""
        return AttendanceService.calculate_overtime_hours_raw(
            overtime_check_in,
            overtime_check_out,
        )