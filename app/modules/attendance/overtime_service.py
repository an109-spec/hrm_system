from __future__ import annotations

from datetime import datetime, timezone, date
from decimal import Decimal

from app.extensions.db import db
from app.models import (
    Attendance,
    OvertimeRequest,
)
from app.models.attendance import AttendanceShiftStatus
from app.common.exceptions import ValidationError
from app.modules.attendance.service import AttendanceService

class OvertimeService:
    OT_START = AttendanceService.OT_CHECKIN_OPEN   
    OT_END   = AttendanceService.OT_END            

    @staticmethod
    def create_overtime_request(
        employee_id: int,
        target_date: date,
        reason: str,
        requested_hours: float = 0.0  # Thêm tham số này để nhận giờ từ FE
    ) -> dict:
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
            requested_hours=requested_hours,
            overtime_hours=0.0,  # Bắt buộc phải có vì nullable=False
            status="pending"     # Khớp với default trong Model
        )

        db.session.add(ot_req)
        db.session.commit()

        return {
            "message": "Tạo đơn tăng ca thành công",
            "request_id": ot_req.id,
        }

    @staticmethod
    def approve_overtime(
        request_id: int,
        approver_id: int,
        approved_hours: float | None = None
    ) -> dict:
        ot_req = OvertimeRequest.query.get(request_id)

        if not ot_req:
            raise ValidationError("Không tìm thấy đơn tăng ca")

        # Khớp với logic status rút gọn (chỉ còn pending)
        if ot_req.status != "pending":
            raise ValidationError(f"Đơn này không ở trạng thái chờ duyệt (Hiện tại: {ot_req.status})")

        # Cập nhật thông tin phê duyệt
        ot_req.status = "approved"
        ot_req.approved_by = approver_id
        ot_req.approved_at = datetime.now(timezone.utc)
        
        # Cập nhật thông tin HR duyệt (vì bạn giữ lại cột hr_decision trong model)
        ot_req.hr_decision_by = approver_id
        ot_req.hr_decision_at =datetime.now(timezone.utc)

        # Logic chốt số giờ được hưởng
        if approved_hours is not None:
            ot_req.approved_hours = approved_hours
        else:
            # Nếu Admin không nhập giờ cụ thể, lấy bằng giờ đăng ký
            ot_req.approved_hours = ot_req.requested_hours

        # Hook → cập nhật attendance
        AttendanceService.handle_ot_approved(ot_req)

        db.session.commit()

        return {"message": "Đã duyệt đơn tăng ca"}

    @staticmethod
    def reject_overtime(
        request_id: int,
        reject_reason: str = "",
        approver_id: int | None = None,
    ) -> dict:
        ot_req = OvertimeRequest.query.get(request_id)

        if not ot_req:
            raise ValidationError("Không tìm thấy đơn tăng ca")
        if ot_req.status not in ("pending", "pending_hr", "pending_admin"):
            raise ValidationError("Đơn này đã được xử lý hoặc không ở trạng thái chờ duyệt")
        ot_req.status = "rejected"
        ot_req.rejection_reason = reject_reason 
        ot_req.approved_by = approver_id
        ot_req.approved_at = datetime.now(timezone.utc)
        
        # Cập nhật thêm vào cột HR (vì model có sẵn, tội gì không dùng để sau này truy vết)
        ot_req.hr_decision_by = approver_id
        ot_req.hr_decision_at = datetime.now(timezone.utc)
        ot_req.hr_note = f"Từ chối với lý do: {reject_reason}"

        # Hook → finalize attendance + tạo notification
        # Đảm bảo AttendanceService nhận đúng tham số
        AttendanceService.handle_ot_rejected(ot_req, reason=reject_reason)

        db.session.commit()

        return {"message": "Đã từ chối đơn tăng ca"}

    # ══════════════════════════════════════════════════════════════════════
    # CAN START OT
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def can_start_ot(employee_id: int, target_date: date) -> bool:
        attendance = Attendance.query.filter_by(
            employee_id=employee_id,
            date=target_date
        ).first()

        if not attendance:
            raise ValidationError("Chưa có dữ liệu chấm công ngày hôm nay")
        valid_statuses = (
            AttendanceShiftStatus.REGULAR_DONE,
            AttendanceShiftStatus.OT_CHECKIN_REQUIRED,
            AttendanceShiftStatus.REGULAR_DONE_PENDING_OT_DECISION
        )
        
        if attendance.shift_status not in valid_statuses:
            if not attendance.check_out:
                raise ValidationError("Bạn chưa checkout ca hành chính. Vui lòng hoàn thành ca chính trước.")
            raise ValidationError(f"Trạng thái hiện tại ({attendance.shift_status_label}) không cho phép bắt đầu OT.")

        # Kiểm tra nếu đã check-in OT rồi
        if attendance.overtime_check_in:
            raise ValidationError("Bạn đã thực hiện check-in tăng ca trước đó rồi.")

        # Kiểm tra đơn OT được duyệt
        ot_req = OvertimeRequest.query.filter_by(
            employee_id=employee_id,
            overtime_date=target_date,
            status="approved",
            is_deleted=False # BaseModel của bạn có is_deleted mặc định là False
        ).first()

        if not ot_req:
            raise ValidationError("Bạn không có đơn đăng ký tăng ca nào được phê duyệt cho ngày hôm nay.")

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