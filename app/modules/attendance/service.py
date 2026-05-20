from __future__ import annotations
from datetime import datetime, date, timedelta, time
from decimal import Decimal
from calendar import monthrange
from sqlalchemy.exc import IntegrityError
from flask import session
from types import SimpleNamespace
from app.extensions import db
from app.utils.time import get_current_time
from app.common.exceptions import ValidationError

from app.models.employee import Employee
from app.models.overtime_request import OvertimeRequest
from app.models.leave import LeaveRequest
from app.models.notification import Notification
from app.models.attendance import AttendanceType, Attendance, AttendanceStatus


from .dto import AttendanceStateDTO, WorkUnitDTO
from app.modules.attendance.constants import AttendanceAction

from .constants import VN_TIMEZONE
from app.constants.attendance import WorkConfig
from app.constants.attendance import (
    LUNCH_START,
    LUNCH_END,
    REGULAR_START,
    REGULAR_END,
    OT_CHECKIN_OPEN,
    OT_END_LIMIT,
    REGULAR_DAY_RATE,
    WEEKEND_RATE,
    HOLIDAY_RATE,
    AttendanceConstants,

)
from app.constants.holidays import VN_FIXED_PUBLIC_HOLIDAYS, HolidayConfig
from app.constants.employee import WorkingStatus
from app.constants.leave import LeaveStatus

from .attendance_calculation_service import attendance_calculation_service

class AttendanceService:
    @staticmethod
    def get_or_create_today(
        employee_id: int,
        now_dt: datetime,
    ) -> Attendance:
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=VN_TIMEZONE)
        else:
            now_dt = now_dt.astimezone(VN_TIMEZONE)
        today = now_dt.date()
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=today,
        ).first()
        if record:
            return record
        employee = Employee.query.get(employee_id)

        if not employee:
            raise ValidationError("Nhân viên không tồn tại")
        if not employee.is_attendance_required:
            raise ValidationError(
                "Nhân viên không thuộc đối tượng chấm công"
            )
        emp_status = employee.working_status
        if hasattr(emp_status, "name"):  
            emp_status = emp_status.value
            
        if str(emp_status).strip().lower() == WorkingStatus.RESIGNED:
            raise ValidationError(
                "Nhân viên không còn hoạt động"
            )
        is_weekend = today.weekday() >= 5
        holiday = AttendanceService._get_holiday(today)
        is_holiday = holiday is not None
        leave_request = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "approved",
            LeaveRequest.from_date <= today,
            LeaveRequest.to_date >= today,
        ).first()
        if leave_request:
            shift_status = Attendance.ShiftStatus.LEAVE
            attendance_type = Attendance.Type.LEAVE_APPROVED
        elif is_holiday:
            shift_status = Attendance.ShiftStatus.HOLIDAY_OFF
            attendance_type = Attendance.Type.HOLIDAY
        elif is_weekend:
            shift_status = Attendance.ShiftStatus.WEEKEND_OFF
            attendance_type = Attendance.Type.WEEKEND
        else:
            shift_status = Attendance.ShiftStatus.NOT_STARTED
            attendance_type = Attendance.Type.NORMAL
        record = Attendance(
            employee_id=employee_id,
            date=today,
            working_hours=Decimal("0.00"),
            regular_hours=Decimal("0.00"),
            overtime_hours=Decimal("0.00"),
            is_half_day=False,
            late_minutes=0,
            is_weekend=is_weekend,
            is_holiday=is_holiday,
            shift_status=Attendance.ShiftStatus.normalize(shift_status),
            attendance_type=Attendance.Type.normalize(attendance_type)
        )
        db.session.add(record)
        try:
            db.session.commit()

        except IntegrityError:
            db.session.rollback()
            record = Attendance.query.filter_by(
                employee_id=employee_id,
                date=today,
            ).first()
            if record:
                return record
            raise ValidationError("Xung đột dữ liệu chấm công, vui lòng thử lại.")
        return record
    
    @staticmethod
    def _resolve_attendance_type(
        *,
        is_holiday: bool = False,
        is_weekend: bool = False,
        is_leave: bool = False,
        is_absent: bool = False,
        is_abnormal: bool = False,
    ) -> str:
        if is_leave:
            return AttendanceType.LEAVE_APPROVED
        if is_absent:
            return AttendanceType.ABSENT
        if is_abnormal:
            return AttendanceType.ABNORMAL
        if is_holiday:
            return AttendanceType.HOLIDAY
        if is_weekend:
            return AttendanceType.WEEKEND
        return AttendanceType.NORMAL

    @staticmethod
    def finalize_attendance(
        record: Attendance,
        finalize_status: bool = True
    ) -> None:
        regular_hours = Decimal(str(record.regular_hours or 0))
        overtime_hours = Decimal(str(record.overtime_hours or 0)) 

        # 1. Tính toán tổng số giờ làm việc thực tế (Làm tròn 2 chữ số thập phân)
        record.working_hours = (regular_hours + overtime_hours).quantize(Decimal("0.01"))
        
        # 2. Phân tách và giải quyết loại hình ngày công (Thường / Lễ / Cuối tuần)
        base_type = AttendanceService._resolve_attendance_type(
            is_weekend=bool(record.is_weekend),
            is_holiday=bool(record.is_holiday),
        )
        
        # Nếu đi muộn quá quy định (nửa ngày công) trên ngày làm việc thường -> Chuyển trạng thái Abnormal
        if record.is_half_day and base_type == Attendance.Type.NORMAL:
            record.set_attendance_type(Attendance.Type.ABNORMAL)
        else:
            record.set_attendance_type(base_type)
            
        # 3. Đóng gói snapshot dữ liệu dạng chuỗi một cách an toàn
        record.dto_snapshot = {
            "working_hours": str(record.working_hours),
            "regular_hours": str(regular_hours),
            "overtime_hours": str(overtime_hours),
            "attendance_type": record.normalized_attendance_type,
            "shift_status": record.normalized_shift_status,
        }
        
        # 4. Kiểm tra điều kiện để chốt sổ (Finalize) ngày công
        if finalize_status:
            current_state = record.normalized_shift_status
            
            # Nhóm các trạng thái được phép chuyển thẳng sang hoàn thành ngày công
            FINALIZABLE_STATES = {
                Attendance.ShiftStatus.REGULAR_DONE,
                Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                Attendance.ShiftStatus.WORKING_OVERTIME,
                Attendance.ShiftStatus.PRE_OT_REST,
            }
            
            if current_state in FINALIZABLE_STATES:
                record.set_shift_status(Attendance.ShiftStatus.COMPLETED)
                record.is_finalized = True
                record.finalized_at = get_current_time()
                
        # 5. Kích hoạt cờ khóa đột biến dữ liệu trên thực thể Model
        if getattr(record, "is_finalized", False):
            record.lock_record()

    @staticmethod
    def auto_complete_stale_records(
        reference_date: date | None = None
    ) -> int:
        now_dt = get_current_time()
        today = reference_date or now_dt.date()
        
        stale_statuses = [
            Attendance.ShiftStatus.WORKING_REGULAR,
            Attendance.ShiftStatus.REGULAR_DONE,
            Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
            Attendance.ShiftStatus.PRE_OT_REST,
            Attendance.ShiftStatus.WORKING_OVERTIME,
        ]
        
        stale_records = Attendance.query.filter(
            Attendance.date < today,
            Attendance.shift_status.in_(stale_statuses),
        ).all()
        
        count = 0
        for record in stale_records:
            # Nếu bản ghi bằng cách nào đó đã hoàn tất, bỏ qua để tránh ghi đè
            if Attendance.ShiftStatus.normalize(record.shift_status) == Attendance.ShiftStatus.COMPLETED:
                continue
            
            # XỬ LÝ QUÊN CHECK-OUT CA CHÍNH
            if (
                not record.check_out
                and record.check_in
                and record.shift_status in {
                    Attendance.ShiftStatus.WORKING_REGULAR,
                    Attendance.ShiftStatus.REGULAR_DONE,
                    Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                }
            ):
                regular_end_time = getattr(WorkConfig, "WORKDAY_END", None)
                
                record.check_out = datetime.combine(
                    record.date,
                    regular_end_time,
                    tzinfo=VN_TIMEZONE,
                )
                result = attendance_calculation_service.calculate_regular_work_units(record)
                record.regular_hours = result.worked_hours.quantize(Decimal("0.01"))
                record.is_half_day = result.is_half_day
                record.late_minutes = record.late_minutes or 0
                
            # XỬ LÝ QUÊN CHECK-OUT CA TĂNG CA (OT)
            if (
                record.overtime_check_in
                and not record.overtime_check_out
                and record.shift_status in {
                    Attendance.ShiftStatus.WORKING_OVERTIME,
                    Attendance.ShiftStatus.PRE_OT_REST,
                }
            ):
                ot_end_time = getattr(WorkConfig, "OT_END", None)
                record.overtime_check_out = datetime.combine(
                    record.date,
                    ot_end_time,
                    tzinfo=VN_TIMEZONE,
                )
                raw_ot = attendance_calculation_service.calculate_overtime_hours_raw(
                    record.overtime_check_in,
                    record.overtime_check_out,
                )
                multiplier = attendance_calculation_service._day_multiplier(
                    bool(record.is_holiday),
                    bool(record.is_weekend),
                )
                record.overtime_hours = (raw_ot * multiplier).quantize(Decimal("0.01"))
            AttendanceService.finalize_attendance(record)
            count += 1
        if count > 0:
            db.session.commit()
        return count
    
    @staticmethod
    def _to_iso(dt: datetime | None) -> str | None:
        if not dt:
            return None
        try:
            if not hasattr(dt, "tzinfo"):
                return dt.isoformat()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=VN_TIMEZONE)
            return dt.astimezone(VN_TIMEZONE).isoformat()
        except Exception:
            return str(dt)

    @staticmethod
    def build_attendance_payload(record: Attendance) -> dict | None:
        if not record:
            return None
        shift_status = Attendance.ShiftStatus.normalize(record.shift_status)
        attendance_type = Attendance.Type.normalize(record.attendance_type)
        regular_dto = attendance_calculation_service.calculate_regular_work_units(record)
        overtime_raw = attendance_calculation_service.calculate_overtime_hours_raw(
            record.overtime_check_in,
            record.overtime_check_out
        )
        multiplier = attendance_calculation_service._get_day_rate(attendance_type)
        return {
            "date": (
                record.date.isoformat()
                if record.date else None
            ),
            "check_in": AttendanceService._to_iso(record.check_in),
            "check_out": AttendanceService._to_iso(record.check_out),
            "overtime_check_in": AttendanceService._to_iso(record.overtime_check_in),
            "overtime_check_out": AttendanceService._to_iso(record.overtime_check_out),
            
            # Ép kiểu an toàn sang chuỗi cho Frontend dễ hiển thị, tránh lỗi Null/None
            "regular_hours": str(record.regular_hours or 0),
            "overtime_hours": str(record.overtime_hours or 0),
            "working_hours": str(record.working_hours or 0),
            
            # SỬA LỖI: Trích xuất thuộc tính worked_hours từ DTO thay vì ép chuỗi cả Object DTO
            "regular_hours_raw": str(regular_dto.worked_hours),
            "overtime_hours_raw": str(overtime_raw),
            "day_multiplier": str(multiplier),
            
            # Trả về mã trạng thái chuẩn hóa
            "shift_status": shift_status,
            "attendance_type": attendance_type,
            
            # Các thông tin bổ trợ hiển thị UI giao diện quản lý
            "late_minutes": record.late_minutes or 0,
            "is_half_day": bool(record.is_half_day),
            "is_weekend": bool(record.is_weekend),
            "is_holiday": bool(record.is_holiday),
        }
    
    @staticmethod
    def process_employee_action(
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:

        today = current_time.date()

        attendance = Attendance.query.filter_by(
            employee_id=employee_id,
            date=today,
        ).first()
        if not attendance:
            return AttendanceService._handle_not_started(
                employee_id,
                payload,
                current_time,
            )
        shift_status = Attendance.ShiftStatus.normalize(
            attendance.shift_status
        )
        attendance.shift_status = shift_status  # sync runtime
        if shift_status == Attendance.ShiftStatus.COMPLETED:
            return {
                "type": "success",
                "action": AttendanceAction.ACTION_ALREADY_RECORDED,
                "attendance_state": shift_status,
                "message": "Ngày công đã hoàn tất",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }
        OFFDAY_STATES = {
            Attendance.ShiftStatus.HOLIDAY_OFF,
            Attendance.ShiftStatus.WEEKEND_OFF,
            Attendance.ShiftStatus.LEAVE,
            Attendance.ShiftStatus.ABSENT,
        }
        if shift_status in OFFDAY_STATES:
            return AttendanceService._handle_offday_logic(
                employee_id=employee_id,
                payload=payload,
                today=today,
            )
        if attendance.check_in is None:
            return AttendanceService._handle_not_started(
                employee_id,
                payload,
                current_time,
            )
        if shift_status in {
            Attendance.ShiftStatus.WORKING_REGULAR,
            Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED,
        }:
            return AttendanceService._handle_working(
                attendance,
                employee_id,
                payload,
                current_time,
            )
        POST_REGULAR_STATES = {
            Attendance.ShiftStatus.REGULAR_DONE,
            Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
            Attendance.ShiftStatus.PRE_OT_REST,
            Attendance.ShiftStatus.OT_CHECKIN_REQUIRED,
            Attendance.ShiftStatus.WORKING_OVERTIME,
        }

        if shift_status in POST_REGULAR_STATES:
            return AttendanceService._handle_after_checkout(
                attendance,
                employee_id,
                payload,
                current_time,
            )
        return {
            "type": "error",
            "attendance_state": shift_status,
            "message": f"Trạng thái không hợp lệ: {shift_status}",
            "attendance": AttendanceService.build_attendance_payload(attendance),
        }

    @staticmethod
    def process_overtime_reset_from_notification(user_id: int, employee_id: int, noti_id: int) -> dict:
        noti = Notification.query.filter_by(id=noti_id, user_id=user_id, is_deleted=False).first()
        if not noti:
            return {
                "success": False,
                "message": "Không tìm thấy dữ liệu thông báo hợp lệ hoặc thông báo đã bị xóa."
            }
        anchor_time = noti.created_at or noti.updated_at
        anchor_date = anchor_time.date()
        row = (
            OvertimeRequest.query.filter_by(employee_id=employee_id, is_deleted=False)
            .filter(OvertimeRequest.overtime_date == anchor_date) # Ép trùng ngày với thông báo để an toàn
            .filter(OvertimeRequest.created_at <= anchor_time)
            .order_by(OvertimeRequest.created_at.desc())
            .first()
        )
        if not row:
            if not noti.is_deleted:
                noti.is_deleted = True
                db.session.commit()
            return {
                "success": True,  
                "already_deleted": True,
                "message": "Đơn yêu cầu tăng ca liên quan không tồn tại hoặc đã được xóa từ trước."
            }
        attendance_record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=row.overtime_date
        ).first()
        if attendance_record:
            if getattr(attendance_record, "overtime_request_id", None) == row.id:
                attendance_record.overtime_request_id = None
                attendance_record.overtime_check_in = None
                attendance_record.overtime_check_out = None
                if attendance_record.check_out:
                    attendance_record.set_shift_status(Attendance.ShiftStatus.ATTENDANCE_COMPLETE)
                else:
                    attendance_record.set_shift_status(Attendance.ShiftStatus.CHAM_CONG_HOP_LE)
        row.is_deleted = True
        noti.is_deleted = True
        try:
            db.session.commit()
            return {
                "success": True,
                "message": f"Đã xóa thành công đơn tăng ca ngày {row.overtime_date} và cập nhật dữ liệu liên quan.",
                "overtime_request_id": row.id
            }
        except Exception as e:
            db.session.rollback()
            return {
                "success": False,
                "message": f"Hệ thống gặp lỗi khi thực hiện xóa đơn: {str(e)}"
            }