from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.constants.overtime import OvertimeConfig
from app.extensions.db import db

from app.models.overtime_request import OvertimeRequest

from app.models.attendance import Attendance, AttendanceShiftStatus
from app.common.exceptions import ValidationError
from app.modules.attendance.attendance_workflow_service import Attendance_workflow_service
from app.modules.attendance.attendance_query_service import Attendance_Query_Service, AttendanceCommandService
from app.utils.time import (
    get_current_time,
    VN_TIMEZONE,
)
from app.constants.attendance import WorkConfig

class OvertimeService:

    @staticmethod
    def create_overtime_request(
        employee_id: int,
        target_date: date | None,
        reason: str,
        requested_hours: float | Decimal = 0,
    ) -> dict:
        now_dt = get_current_time()
        target_date = target_date or now_dt.date()
        
        if not reason or not reason.strip():
            raise ValidationError("Vui lòng nhập lý do tăng ca.")
            
        requested_hours = Decimal(str(requested_hours or 0)).quantize(Decimal("0.01"))
        if requested_hours < Decimal("0"):
            raise ValidationError("Số giờ tăng ca không hợp lệ.")
            
        # Kiểm tra đơn trùng lặp
        existed = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == target_date,
            OvertimeRequest.is_deleted.is_(False), # Lưu ý: Đảm bảo BaseModel của bạn thực sự có trường is_deleted nhé
        ).first()
        
        if existed:
            raise ValidationError("Ngày này đã tồn tại đơn tăng ca.")
            
        # Khởi tạo đơn mới - Trạng thái lấy đồng bộ dạng chuỗi "pending" theo mặc định Model
        ot_req = OvertimeRequest(
            employee_id=employee_id,
            overtime_date=target_date,
            reason=reason.strip(),
            requested_hours=requested_hours,
            overtime_hours=Decimal("0.00"),
            status="pending", 
        )
        db.session.add(ot_req)
        db.session.flush() # Lấy trước ot_req.id mà chưa cần commit toàn bộ transaction
        
        # Tìm kiếm dữ liệu chấm công ngày hôm đó để cập nhật trạng thái ca làm việc
        attendance = Attendance.query.filter_by(
            employee_id=employee_id,
            date=target_date,
        ).first()
        
        if attendance:
            # Tận dụng property có sẵn từ Model Attendance để so sánh cho sạch code
            if attendance.normalized_shift_status == AttendanceShiftStatus.REGULAR_DONE:
                attendance.set_shift_status(AttendanceShiftStatus.REGULAR_DONE_PENDING_OT_DECISION)
                # ĐÃ BỎ dòng gán id lỗi: attendance.overtime_request_id = ot_req.id
                
        db.session.commit()
        
        return {
            "message": "Tạo đơn tăng ca thành công.",
            "request_id": ot_req.id,
            "overtime_status": ot_req.status,
            "requested_hours": str(ot_req.requested_hours),
            "target_date": str(ot_req.overtime_date),
            "server_time": now_dt.isoformat(),
        }

    @staticmethod
    def approve_overtime(
        request_id: int,
        approver_id: int,
        approved_hours: float | Decimal | None = None,
    ) -> dict:
        ot_req = OvertimeRequest.query.get(request_id)
        if not ot_req:
            raise ValidationError("Không tìm thấy đơn tăng ca.")
            
        # Sửa lỗi: Sử dụng chuỗi text "pending" thay vì gọi qua Enum không tồn tại
        if (ot_req.status or "").strip().lower() != "pending":
            raise ValidationError(
                f"Đơn này không ở trạng thái chờ duyệt (Hiện tại: {ot_req.status})"
            )
            
        now_dt = get_current_time()
        
        # Ép kiểu dữ liệu Decimal chuẩn xác cho số giờ phê duyệt
        if approved_hours is None:
            approved_hours = Decimal(str(ot_req.requested_hours or 0))
        else:
            approved_hours = Decimal(str(approved_hours))
            
        approved_hours = approved_hours.quantize(Decimal("0.01"))
        if approved_hours < Decimal("0"):
            raise ValidationError("Số giờ duyệt không hợp lệ.")
        ot_req.status = "approved" 
        ot_req.approved_by = approver_id
        ot_req.approved_at = now_dt
        ot_req.hr_decision_by = approver_id
        ot_req.hr_decision_at = now_dt
        ot_req.approved_hours = approved_hours
        Attendance_workflow_service.handle_ot_approved(ot_req)
        
        # Đồng bộ commit cuối cùng cho toàn bộ tiến trình thay đổi
        db.session.commit()
        
        return {
            "message": "Đã duyệt đơn tăng ca.",
            "request_id": ot_req.id,
            "overtime_status": ot_req.status,
            "approved_hours": str(ot_req.approved_hours),
            "approved_at": ot_req.approved_at.isoformat() if ot_req.approved_at else None,
            "server_time": now_dt.isoformat(),
        }

    @staticmethod
    def reject_overtime(
        request_id: int,
        reject_reason: str = "",
        approver_id: int | None = None,
    ) -> dict:
        ot_req = OvertimeRequest.query.get(request_id)
        if not ot_req:
            raise ValidationError("Không tìm thấy đơn tăng ca.")
            
        # Sửa lỗi: Check chuỗi text trực tiếp thay vì gọi qua Enum không tồn tại
        current_status = (ot_req.status or "").strip().lower()
        valid_pending_states = {"pending", "pending_hr", "pending_admin"}
        
        if current_status not in valid_pending_states:
            raise ValidationError(
                f"Đơn này đã được xử lý hoặc không ở trạng thái chờ duyệt. (Hiện tại: {ot_req.status})"
            )
            
        now_dt = get_current_time()
        reject_reason = (reject_reason or "").strip()
        
        # Cập nhật thông tin từ chối trên Đơn tăng ca (Khớp hoàn toàn với Model)
        ot_req.status = "rejected"  # Đồng nhất chuỗi text thường
        ot_req.rejection_reason = reject_reason if reject_reason else "Từ chối yêu cầu tăng ca."
        ot_req.approved_by = approver_id
        ot_req.approved_at = now_dt
        ot_req.hr_decision_by = approver_id
        ot_req.hr_decision_at = now_dt
        ot_req.hr_note = (
            f"Từ chối với lý do: {reject_reason}"
            if reject_reason
            else "Từ chối yêu cầu tăng ca."
        )
        Attendance_workflow_service.handle_ot_rejected(ot_req, reason=reject_reason)
        db.session.commit()
        return {
            "message": "Đã từ chối đơn tăng ca.",
            "request_id": ot_req.id,
            "overtime_status": ot_req.status,
            "rejection_reason": ot_req.rejection_reason,
            "processed_at": now_dt.isoformat(),
            "server_time": now_dt.isoformat(),
        }

    @staticmethod
    def can_start_ot(
        employee_id: int,
        target_date: date,
    ) -> bool:
        attendance = Attendance.query.filter_by(
            employee_id=employee_id,
            date=target_date,
        ).first()
        
        if not attendance:
            raise ValidationError("Chưa có dữ liệu chấm công ngày hôm nay.")
        current_state = attendance.normalized_shift_status
        allowed_states = {
            Attendance.ShiftStatus.REGULAR_DONE,
            Attendance.ShiftStatus.OT_CHECKIN_REQUIRED,
            Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
            Attendance.ShiftStatus.PRE_OT_REST,
        }
        if current_state not in allowed_states:
            if not attendance.check_out:
                raise ValidationError(
                    "Bạn chưa checkout ca hành chính. Vui lòng hoàn thành ca chính trước."
                )
            raise ValidationError(
                f"Trạng thái hiện tại ({attendance.shift_status_label}) không cho phép bắt đầu OT."
            )
        if attendance.overtime_check_in:
            raise ValidationError("Bạn đã thực hiện check-in tăng ca trước đó rồi.")
            
        if attendance.overtime_check_out:
            raise ValidationError("Bạn đã hoàn thành tăng ca hôm nay.")
        approved_ot = AttendanceCommandService._get_approved_ot(
            employee_id=employee_id,
            target_date=target_date,
        )
        
        if not approved_ot:
            raise ValidationError("Bạn không có đơn tăng ca được phê duyệt cho hôm nay.")
        return True

    @staticmethod
    def calculate_overtime(
        overtime_check_in: datetime,
        overtime_check_out: datetime,
    ) -> Decimal:
        if not overtime_check_in or not overtime_check_out:
            return Decimal("0.00")
        if overtime_check_in.tzinfo is None:
            overtime_check_in = overtime_check_in.replace(tzinfo=VN_TIMEZONE)
        else:
            overtime_check_in = overtime_check_in.astimezone(VN_TIMEZONE)
        if overtime_check_out.tzinfo is None:
            overtime_check_out = overtime_check_out.replace(tzinfo=VN_TIMEZONE)
        else:
            overtime_check_out = overtime_check_out.astimezone(VN_TIMEZONE)
        ot_start_dt = datetime.combine(
            overtime_check_in.date(),
            OvertimeConfig.OFFICIAL_PAY_START_TIME,
            tzinfo=VN_TIMEZONE,
        )
        ot_end_dt = datetime.combine(
            overtime_check_in.date(),
            WorkConfig.OT_END,
            tzinfo=VN_TIMEZONE,
        )
        effective_start = max(overtime_check_in, ot_start_dt)
        effective_end = min(overtime_check_out, ot_end_dt)
        
        if effective_end <= effective_start:
            return Decimal("0.00")
        total_seconds = (effective_end - effective_start).total_seconds()
        hours = Decimal(str(total_seconds / 3600))
        return hours.quantize(Decimal("0.01"))