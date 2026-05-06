# app/modules/attendance/overtime_service.py

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from app.extensions.db import db
from app.models import (
    Attendance,
    Employee,
    OvertimeRequest,  # nếu model này chưa có thì phải tạo
)
from app.common.exceptions import ValidationError
from app.modules.attendance.service import AttendanceService

class OvertimeService:
    """
    Service xử lý toàn bộ nghiệp vụ tăng ca (OT)

    Bao gồm:
    - tạo đơn OT
    - duyệt đơn OT
    - từ chối đơn OT
    - kiểm tra có được bắt đầu OT không
    - tính số giờ OT thực tế
    """

    OT_START = time(19, 0, 0)   # OT chỉ tính từ 19:00
    OT_END = time(22, 0, 0)     # tối đa tới 22:00

    # =========================================================
    # CREATE OT REQUEST
    # =========================================================

    @staticmethod
    def create_overtime_request(
        employee_id: int,
        target_date,
        reason: str,
    ):
        """
        Tạo đơn xin tăng ca

        Điều kiện:
        - chưa có đơn OT cùng ngày
        - lý do không được rỗng
        """

        if not reason or not reason.strip():
            raise ValidationError("Vui lòng nhập lý do tăng ca")

        existed = OvertimeRequest.query.filter_by(
            employee_id=employee_id,
            overtime_date=target_date
        ).first()

        if existed:
            raise ValidationError("Ngày này đã tồn tại đơn tăng ca")

        request = OvertimeRequest(
            employee_id=employee_id,
            overtime_date=target_date,
            reason=reason.strip(),
            status="pending",  # pending / approved / rejected
        )

        db.session.add(request)
        db.session.commit()

        return {
            "message": "Tạo đơn tăng ca thành công",
            "request_id": request.id
        }

    # =========================================================
    # APPROVE OT
    # =========================================================

    @staticmethod
    def approve_overtime(
        request_id: int,
        approver_id: int = None,
    ):
        """
        HR / Manager duyệt đơn tăng ca
        """

        request = OvertimeRequest.query.get(request_id)

        if not request:
            raise ValidationError("Không tìm thấy đơn tăng ca")

        if request.status != "pending":
            raise ValidationError("Đơn này đã được xử lý trước đó")

        request.status = "approved"
        request.approved_by = approver_id
        request.approved_at = datetime.utcnow()

        db.session.commit()

        return {
            "message": "Đã duyệt đơn tăng ca"
        }

    # =========================================================
    # REJECT OT
    # =========================================================

    @staticmethod
    def reject_overtime(
        request_id: int,
        reject_reason: str = None,
        approver_id: int = None,
    ):
        """
        HR / Manager từ chối đơn tăng ca
        """

        request = OvertimeRequest.query.get(request_id)

        if not request:
            raise ValidationError("Không tìm thấy đơn tăng ca")

        if request.status != "pending":
            raise ValidationError("Đơn này đã được xử lý trước đó")

        request.status = "rejected"
        request.reject_reason = reject_reason
        request.approved_by = approver_id
        request.approved_at = datetime.utcnow()

        db.session.commit()

        return {
            "message": "Đã từ chối đơn tăng ca"
        }

    # =========================================================
    # CAN START OT
    # =========================================================

    @staticmethod
    def can_start_ot(employee_id: int, target_date):
        """
        Kiểm tra nhân viên có được bắt đầu OT hay không

        Điều kiện:
        - đã có attendance hôm đó
        - đã checkout ca chính
        - có đơn OT đã approved
        - chưa OT check-in
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

        request = OvertimeRequest.query.filter_by(
            employee_id=employee_id,
            overtime_date=target_date,
            status="approved"
        ).first()

        if not request:
            raise ValidationError(
                "Bạn chưa có đơn tăng ca được duyệt"
            )

        return True

    # =========================================================
    # CALCULATE OVERTIME
    # =========================================================

@staticmethod
def calculate_overtime(
    overtime_check_in: datetime,
    overtime_check_out: datetime,
) -> Decimal:
    return AttendanceService.calculate_overtime_hours(
        overtime_check_in,
        overtime_check_out
    )