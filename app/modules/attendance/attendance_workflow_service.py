from __future__ import annotations
from datetime import datetime, date, timedelta, time
from decimal import Decimal
from calendar import monthrange
from operator import and_
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
from app.models.attendance import AttendanceType, Attendance, AttendanceStatus, AttendanceShiftStatus


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
from .service import AttendanceService
from .attendance_query_service import AttendanceCommandService
class Attendance_workflow_service:
    @staticmethod
    def _handle_not_started(
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:
        confirm_work = bool(payload.get("confirm_work_on_offday")) or bool(payload.get("overtime_confirmed"))
        result = Attendance_workflow_service.check_in(
            employee_id=employee_id,
            current_time=current_time,
            confirm_work=confirm_work,
        )
        response_type = (
            "warning"
            if result.get("action") in {
                AttendanceAction.ACTION_HOLIDAY_WORK_PROMPT,
                AttendanceAction.ACTION_WEEKEND_WORK_PROMPT,
            }
            else "success"
        )
        return {
            "type": response_type,
            "status_code": 200,
            **result,
        }

    @staticmethod
    def _handle_working(
        attendance: Attendance,
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:
        today = current_time.date()
        end_of_day = datetime.combine(
            today,
            WorkConfig.WORKDAY_END,  # Giờ tan ca chính thức (17:00)
            tzinfo=VN_TIMEZONE,
        )

        lunch_start = datetime.combine(
            today,
            WorkConfig.LUNCH_START,  # Bắt đầu nghỉ trưa (12:00)
            tzinfo=VN_TIMEZONE,
        )

        lunch_end = datetime.combine(
            today,
            WorkConfig.LUNCH_END,    # Kết thúc nghỉ trưa (13:00)
            tzinfo=VN_TIMEZONE,
        )

        # 2. CHUẨN HÓA TRẠNG THÁI: Sử dụng helper từ AttendanceConstants
        state = AttendanceConstants.normalize(attendance.shift_status)

        early_checkout_confirmed = bool(
            payload.get("early_checkout_confirmed")
        )
        
        # Kiểm tra tính hợp lệ của trạng thái hiện tại
        if state not in {
            AttendanceConstants.STATUS_WORKING_REGULAR,
            AttendanceConstants.STATUS_REGULAR_CHECKOUT_REQ,
        }:
            return {
                "type": "error",
                "action": "invalid_state",
                "attendance_state": state,
                "message": f"Không hợp lệ để xử lý WORKING: {state}",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        # 3. XỬ LÝ KHUNG GIỜ NGHỈ TRƯA
        if lunch_start <= current_time < lunch_end:
            # Format tự động chuỗi thời gian hiển thị từ cấu hình hệ thống
            lunch_start_str = WorkConfig.LUNCH_START.strftime('%H:%M')
            lunch_end_str = WorkConfig.LUNCH_END.strftime('%H:%M')
            return {
                "type": "info",
                "action": "lunch_break",
                "attendance_state": state,
                "message": f"Đang trong giờ nghỉ trưa ({lunch_start_str}–{lunch_end_str})",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        # 4. XỬ LÝ TAN CA ĐÚNG GIỜ HOẶC MUỘN HƠN (>= 17:00)
        if current_time >= end_of_day:
            return AttendanceService.check_out_regular(
                employee_id=employee_id,
                current_time=current_time,
                early_checkout=False,
            )

        # 5. XỬ LÝ TAN CA SỚM (Trước 17:00)
        early_minutes = int(
            (end_of_day - current_time).total_seconds() // 60
        )
        
        # Nếu chưa xác nhận trên giao diện -> Trả cảnh báo yêu cầu hiện Popup xác nhận
        if not early_checkout_confirmed:
            return {
                "type": "warning",
                "action": AttendanceAction.ACTION_EARLY_CHECKOUT_PROMPT,  # Đã sửa thành AttendanceAction
                "attendance_state": state,
                "message": (
                    f"Bạn có muốn tan ca sớm không? "
                    f"(sớm {early_minutes} phút)"
                ),
                "requires_confirmation": True,
                "flags": {
                    "early_minutes": early_minutes,
                },
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }
        return AttendanceService.check_out_regular(
            employee_id=employee_id,
            current_time=current_time,
            early_checkout=True,
        )
    

    @staticmethod
    def _handle_after_checkout(
        attendance: Attendance,
        employee_id: int,
        payload: dict,
        current_time: datetime,
    ) -> dict:

        # Khai báo chuẩn hóa trạng thái từ thực thể Model
        state = Attendance.ShiftStatus.normalize(attendance.shift_status)

        overtime_decision = str(
            payload.get("overtime_decision") or ""
        ).strip().lower()

        # =========================================================
        # 0. NORMALIZE CURRENT TIME (TIMEZONE SAFE)
        # =========================================================
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=VN_TIMEZONE)
        else:
            current_time = current_time.astimezone(VN_TIMEZONE)

        # =========================================================
        # 1. OT CONTEXT PRE-FETCH
        # =========================================================
        ot_request = Attendance_workflow_service._get_ot_request(
            employee_id,
            current_time.date(),
        )

        ot_status = ot_request.status if ot_request else None

        # =========================================================
        # 2. REGULAR DONE (HOÀN THÀNH CA CHÍNH)
        # =========================================================
        if state == Attendance.ShiftStatus.REGULAR_DONE:

            if overtime_decision not in {"yes", "no"}:
                return {
                    "type": "warning",
                    "action": AttendanceAction.ACTION_OFFER_OVERTIME,
                    "attendance_state": Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                    "overtime_status": ot_status or "NONE",
                    "message": "Bạn có muốn đăng ký tăng ca không?",
                    "requires_overtime_decision": True,
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            if overtime_decision == "no":
                # Chuyển trạng thái sang COMPLETED để sẵn sàng đóng bản ghi
                attendance.set_shift_status(Attendance.ShiftStatus.COMPLETED)

                # Hàm này tính toán tổng giờ, tạo snapshot, khóa bản ghi (is_finalized=True)
                AttendanceService.finalize_attendance(
                    attendance,
                    finalize_status=True,
                )

                db.session.commit()

                return {
                    "type": "success",
                    "action": AttendanceAction.ACTION_COMPLETE_WITHOUT_OT,
                    "attendance_state": Attendance.ShiftStatus.COMPLETED,
                    "overtime_status": "NONE",  # Ghi nhận rõ ràng không phát sinh OT thay vì REJECTED
                    "message": "Đã hoàn thành ngày làm việc.",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            # Nếu quyết định là "yes" -> Tiến hành tạo yêu cầu OT ở trạng thái chờ
            return AttendanceService._create_ot_request_pending(
                attendance,
                employee_id,
                current_time,
            )

        # =========================================================
        # 3. PENDING OT DECISION (ĐANG CHỜ QUYẾT ĐỊNH TĂNG CA)
        # =========================================================
        if state == Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION:

            if ot_status == "approved":
                attendance.set_shift_status(Attendance.ShiftStatus.PRE_OT_REST)
                db.session.commit()

                return {
                    "type": "info",
                    "action": "ot_approved_wait",
                    "attendance_state": Attendance.ShiftStatus.PRE_OT_REST,
                    "overtime_status": "APPROVED",
                    "message": "Yêu cầu tăng ca đã được phê duyệt.",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            if ot_status in {"pending", "pending_hr", "pending_admin"}:
                return {
                    "type": "info",
                    "action": "ot_pending_approval",
                    "attendance_state": state,
                    "overtime_status": "PENDING",
                    "message": "Đang chờ duyệt tăng ca.",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            return {
                "type": "warning",
                "action": AttendanceAction.ACTION_OFFER_OVERTIME,
                "attendance_state": state,
                "overtime_status": ot_status or "NONE",
                "message": "Chưa có quyết định tăng ca.",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        # =========================================================
        # 4. PRE OT REST (NGHỈ GIẢI LAO TRƯỚC TĂNG CA)
        # =========================================================
        if state == Attendance.ShiftStatus.PRE_OT_REST:

            # Nếu đơn tăng ca đột ngột bị hủy hoặc không còn ở trạng thái approved
            if ot_status != "approved":
                attendance.set_shift_status(Attendance.ShiftStatus.COMPLETED)
                
                AttendanceService.finalize_attendance(
                    attendance,
                    finalize_status=True,
                )
                db.session.commit()

                return {
                    "type": "warning",
                    "action": AttendanceAction.ACTION_COMPLETE_WITHOUT_OT,
                    "attendance_state": Attendance.ShiftStatus.COMPLETED,
                    "overtime_status": ot_status or "CANCELLED",
                    "message": "Không còn ca OT hợp lệ. Hệ thống kết thúc ngày công.",
                    "attendance": AttendanceService.build_attendance_payload(attendance),
                }

            # SỬA XUNG ĐỘT: Nếu đã có dữ liệu check-in OT, điều hướng thẳng sang xử lý WORKING_OVERTIME 
            # thay vì gán đè thủ công trạng thái tại đây làm mất kiểm soát luồng dữ liệu
            if attendance.overtime_check_in:
                state = Attendance.ShiftStatus.WORKING_OVERTIME
            else:
                ot_open_dt = datetime.combine(
                    current_time.date(),
                    OT_CHECKIN_OPEN,
                    tzinfo=VN_TIMEZONE,
                )

                if current_time < ot_open_dt:
                    return {
                        "type": "info",
                        "action": "pre_ot_rest",
                        "attendance_state": state,
                        "overtime_status": "APPROVED",
                        "message": "Chờ tới giờ hệ thống mở check-in OT.",
                        "attendance": AttendanceService.build_attendance_payload(attendance),
                    }

                # Chuyển sang hàm check-in OT chuyên trách xử lý nghiệp vụ chuyên sâu
                return Attendance_workflow_service.check_in_overtime(
                    employee_id,
                    current_time.isoformat(),  # Đồng bộ chuyển đổi sang chuỗi (str) khớp với tham số nhận vào
                )

        # =========================================================
        # 5. WORKING OVERTIME (ĐANG TRONG CA TĂNG CA)
        # =========================================================
        if state == Attendance.ShiftStatus.WORKING_OVERTIME:

            if not attendance.overtime_check_out:
                # Điều hướng sang hàm checkout OT chuyên trách của bạn
                return Attendance_workflow_service.check_out_overtime(
                    employee_id=employee_id,
                    sim_time_str=current_time.isoformat(),  # Truyền tham số chuỗi đồng bộ an toàn
                )

            # Trường hợp đã có thông tin checkout OT từ trước
            attendance.set_shift_status(Attendance.ShiftStatus.COMPLETED)
            
            AttendanceService.finalize_attendance(
                attendance,
                finalize_status=True,
            )
            db.session.commit()

            return {
                "type": "success",
                "action": AttendanceAction.ACTION_ALREADY_RECORDED,
                "attendance_state": Attendance.ShiftStatus.COMPLETED,
                "overtime_status": "DONE",
                "message": "Đã ghi nhận hoàn thành tăng ca trước đó.",
                "attendance": AttendanceService.build_attendance_payload(attendance),
            }

        # =========================================================
        # 6. SAFE FALLBACK (NGÀY CÔNG ĐÃ ĐƯỢC CHỐT SỔ KHÓA DỮ LIỆU)
        # =========================================================
        return {
            "type": "success",
            "action": AttendanceAction.ACTION_ALREADY_RECORDED,
            "attendance_state": state,
            "overtime_status": ot_status or "NONE",
            "message": "Bản ghi ngày công hiện tại đã hoàn tất và được đóng lại.",
            "attendance": AttendanceService.build_attendance_payload(attendance),
        }
    @staticmethod
    def _get_ot_request(employee_id: int, work_date: date) -> OvertimeRequest | None:

        return (
            db.session.query(OvertimeRequest)
            .filter(
                and_(
                    OvertimeRequest.employee_id == employee_id,
                    OvertimeRequest.work_date == work_date 
                )
            )
            .order_by(
                OvertimeRequest.status == "approved", 
                OvertimeRequest.created_at.desc()
            )
            .first()
        )
    
    @staticmethod
    def check_out_overtime(employee_id: int, sim_time_str: str | None = None) -> dict:
        # 1. Xử lý thời gian hiện tại từ chuỗi giả lập hoặc thời gian thực tế hệ thống
        if sim_time_str:
            try:
                now_dt = datetime.fromisoformat(sim_time_str)
                if now_dt.tzinfo is None:
                    now_dt = now_dt.replace(tzinfo=VN_TIMEZONE)
            except ValueError:
                raise ValidationError("Định dạng chuỗi thời gian giả lập không hợp lệ.")
        else:
            now_dt = get_current_time()

        if not now_dt:
            raise ValidationError("Không xác định được thời gian OT.")

        # 2. Tìm kiếm bản ghi chấm công trong ngày của nhân viên
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date(),
        ).first()

        if not record:
            raise ValidationError("Không tìm thấy dữ liệu chấm công.")
        if not record.overtime_check_in:
            raise ValidationError("Bạn chưa check-in tăng ca.")
        if record.overtime_check_out:
            raise ValidationError("Bạn đã check-out OT rồi.")
        normalized_shift = AttendanceConstants.normalize(record.normalized_shift_status)
        allowed_states = {
            AttendanceConstants.STATUS_WORKING_OVERTIME,
            AttendanceConstants.STATUS_PRE_OT_REST,
        }
        if normalized_shift not in allowed_states:
            raise ValidationError("Không thể kết thúc OT ở trạng thái hiện tại.")

        # 4. Kiểm tra đơn đăng ký tăng ca đã được duyệt hay chưa
        approved_ot = AttendanceService._get_ot_request(employee_id, now_dt.date())
        if not approved_ot or approved_ot.status != "approved":
            raise ValidationError("Yêu cầu tăng ca không tồn tại hoặc chưa được duyệt.")

        if now_dt < record.overtime_check_in:
            raise ValidationError("Thời gian OT không hợp lệ.")
        ot_end_dt = datetime.combine(
            now_dt.date(),
            WorkConfig.OT_END,
            tzinfo=VN_TIMEZONE
        )
        final_ot_time = min(now_dt, ot_end_dt)
        record.overtime_check_out = final_ot_time
        raw_ot = attendance_calculation_service.calculate_overtime_hours_raw(
            record.overtime_check_in,
            record.overtime_check_out,
        )
        if isinstance(raw_ot, (float, int, str)):
            raw_ot = Decimal(str(raw_ot))
        elif raw_ot is None:
            raw_ot = Decimal("0.00")
        if raw_ot < Decimal("0.00"):
            raw_ot = Decimal("0.00")
        if hasattr(approved_ot, 'holiday_multiplier') and approved_ot.holiday_multiplier is not None:
            multiplier = Decimal(str(approved_ot.holiday_multiplier))
        else:
            multiplier = Decimal(
                str(
                    AttendanceService._day_multiplier(
                        bool(record.is_holiday),
                        bool(record.is_weekend),
                    )
                )
            )
        record.overtime_hours = (raw_ot * multiplier).quantize(Decimal("0.01"))
        record.set_shift_status(AttendanceConstants.STATUS_COMPLETED)
        record.overtime_status = approved_ot.status
        AttendanceService.finalize_attendance(
            record,
            finalize_status=True,
        )
        
        db.session.commit()
        multiplier_label = (
            f" (x{multiplier.normalize()})"
            if multiplier > Decimal("1")
            else ""
        )
        return {
            "type": "success",
            "action": "check_out_ot",  # Thay thế hằng số hành động trực tiếp bằng chuỗi nếu cần
            "message": (
                "Đã hoàn thành tăng ca. "
                f"OT: {record.overtime_hours}h"
                f"{multiplier_label}"
            ),
            "attendance_state": record.normalized_shift_status,
            "overtime_status": approved_ot.status,
            "regular_hours": str(record.regular_hours),
            "overtime_hours": str(record.overtime_hours),
            "working_hours": str(record.working_hours),
            "overtime_check_in": record.overtime_check_in.isoformat(),
            "overtime_check_out": record.overtime_check_out.isoformat(),
            "attendance": AttendanceService.build_attendance_payload(record),
        }

    @staticmethod
    def check_in(
        employee_id: int,
        current_time: datetime,
        confirm_work: bool = False,
    ) -> dict:
        now_dt = current_time.astimezone(VN_TIMEZONE)
        record = AttendanceService.get_or_create_today(
            employee_id,
            now_dt,
        )
        normalized_shift = AttendanceConstants.normalize(record.shift_status)
        OFFDAY_STATES = {
            AttendanceConstants.STATUS_HOLIDAY_OFF,
            AttendanceConstants.STATUS_WEEKEND_OFF,
        }
        if normalized_shift in OFFDAY_STATES and not confirm_work:
            return {
                "action": (
                    AttendanceAction.ACTION_HOLIDAY_WORK_PROMPT
                    if normalized_shift == AttendanceConstants.STATUS_HOLIDAY_OFF
                    else AttendanceAction.ACTION_WEEKEND_WORK_PROMPT
                ),
                "requires_confirmation": True,
                "attendance_state": normalized_shift,
                "message": (
                    "Hôm nay là ngày nghỉ lễ. Bạn có muốn đi làm không?"
                    if normalized_shift == AttendanceConstants.STATUS_HOLIDAY_OFF
                    else "Hôm nay là ngày nghỉ cuối tuần. Bạn có muốn đi làm không?"
                ),
            }
        if record.check_in:
            raise ValidationError("Bạn đã check-in hôm nay.")
        is_weekend = bool(record.is_weekend)
        is_holiday = bool(record.is_holiday)
        if normalized_shift in OFFDAY_STATES and confirm_work:
            record.check_out = None
            record.overtime_check_in = None
            record.overtime_check_out = None
            record.regular_hours = Decimal("0.00")
            record.overtime_hours = Decimal("0.00")
            record.working_hours = Decimal("0.00")
        record.check_in = now_dt
        record.set_shift_status(AttendanceConstants.STATUS_WORKING_REGULAR)
        shift_start_dt = datetime.combine(
            now_dt.date(),
            WorkConfig.WORKDAY_START,  # Sử dụng chuẩn cấu hình giờ làm (08:00:00)
            tzinfo=VN_TIMEZONE,
        )
        late_minutes = max(
            0,
            int((now_dt - shift_start_dt).total_seconds() / 60)
        )
        record.late_minutes = late_minutes
        penalty_info = AttendanceConstants.get_late_penalty(late_minutes)
        record.is_half_day = penalty_info["is_half_day"]
        if record.is_half_day:
            status_name = AttendanceStatus.PRESENT  
            status_lookup = "HALF_DAY" if late_minutes >= 60 else "LATE" if late_minutes > 0 else "PRESENT"
        else:
            status_lookup = "LATE" if late_minutes > 0 else "PRESENT"
        db_status = AttendanceCommandService.get_status(status_lookup)
        if db_status:
            record.status_id = db_status.id
        if record.is_half_day and not is_weekend and not is_holiday:
            record.set_attendance_type(Attendance.Type.ABNORMAL)
        else:
            if is_holiday:
                record.set_attendance_type(Attendance.Type.HOLIDAY)
            elif is_weekend:
                record.set_attendance_type(Attendance.Type.WEEKEND)
            else:
                record.set_attendance_type(Attendance.Type.NORMAL)
        db.session.commit()
        msg = f"Check-in thành công lúc {now_dt.strftime('%H:%M:%S')}"
        resp_type = "success"
        multiplier = attendance_calculation_service._day_multiplier(is_holiday, is_weekend)
        if is_holiday:
            msg += f" (Ngày lễ — công x{multiplier.normalize()})"
        elif is_weekend and multiplier > 1:
            msg += f" (Cuối tuần — công x{multiplier.normalize()})"
        if late_minutes > 0:
            msg += f". Đi muộn {late_minutes} phút{penalty_info['message']}."
            resp_type = "warning"
        return {
            "action": AttendanceAction.ACTION_CHECK_IN,
            "type": resp_type,
            "message": msg,
            "attendance_state": record.normalized_shift_status,
            "attendance": AttendanceService.build_attendance_payload(record),
        }
 
    @staticmethod
    def _create_ot_request_pending(
        attendance: Attendance,
        employee_id: int,
        current_time: datetime,
    ) -> dict:

        now_dt = current_time.astimezone(VN_TIMEZONE)
        today = now_dt.date()
        existing = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == today,
        ).first()
        current_ot_status = "pending"
        if not existing:
            is_holiday = bool(attendance.is_holiday)
            is_weekend = bool(attendance.is_weekend)
            multiplier = attendance_calculation_service._day_multiplier(
                is_holiday,
                is_weekend,
            )
            ot_req = OvertimeRequest(
                employee_id=employee_id,
                overtime_date=today,
                status="pending",              # Đồng bộ chuỗi trạng thái thô dạng chữ thường
                requested_hours=Decimal("3.00"),
                overtime_hours=Decimal("0.00"),
                is_holiday_ot=is_holiday,
                holiday_multiplier=multiplier,
                reason="Đăng ký tăng ca sau giờ hành chính",
            )
            db.session.add(ot_req)
            db.session.flush()
            current_ot_status = ot_req.status
        else:
            current_ot_status = existing.status
        attendance.set_shift_status(
            AttendanceShiftStatus.REGULAR_DONE_PENDING_OT_DECISION
        )
        if attendance.is_holiday:
            attendance.set_attendance_type(AttendanceType.HOLIDAY)
        elif attendance.is_weekend:
            attendance.set_attendance_type(AttendanceType.WEEKEND)
        db.session.commit()
        return {
            "type": "success",
            "action": AttendanceAction.ACTION_OVERTIME_REQUEST_CREATED,
            "attendance_state": attendance.normalized_shift_status,
            "overtime_status": current_ot_status,
            "message": "Đã gửi yêu cầu tăng ca. Vui lòng chờ phê duyệt.",
            "attendance": AttendanceService.build_attendance_payload(attendance),
        }
    
    @staticmethod
    def handle_ot_approved(ot_request: OvertimeRequest) -> None:
        attendance = Attendance.query.filter_by(
            employee_id=ot_request.employee_id,
            date=ot_request.overtime_date,
        ).first()
        
        if attendance:
            # Tối ưu: Dùng property normalized_shift_status có sẵn của Model Attendance
            current_state = attendance.normalized_shift_status
            allowed_states = {
                AttendanceShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                AttendanceShiftStatus.REGULAR_DONE,
            }
            if current_state in allowed_states:
                attendance.set_shift_status(AttendanceShiftStatus.PRE_OT_REST)
                
        ot_request.status = "approved"
        
        employee = Employee.query.get(ot_request.employee_id)
        if employee and employee.user_id:
            formatted_date = ot_request.overtime_date.strftime('%d/%m/%Y')
            new_notification = Notification(
                user_id=employee.user_id,
                type="overtime",
                title="Yêu cầu tăng ca đã được duyệt",
                content=(
                    f"Yêu cầu tăng ca ngày {formatted_date} đã được phê duyệt. "
                    f"Bạn có thể xác thực để bắt đầu tăng ca."
                ),
                link="/employee/attendance",
                is_read=False
            )
            db.session.add(new_notification)
        

    @staticmethod
    def handle_ot_rejected(
        ot_request: OvertimeRequest,
        reason: str = "",
    ) -> None:

        current_time = (
            get_current_time()
            .astimezone(VN_TIMEZONE)
        )
        attendance = Attendance.query.filter_by(
            employee_id=ot_request.employee_id,
            date=ot_request.overtime_date,
        ).first()
        if attendance:

            current_state = (
                Attendance.ShiftStatus.normalize(
                    attendance.shift_status
                )
            )
            allowed_states = {
                Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
                Attendance.ShiftStatus.REGULAR_DONE,
                Attendance.ShiftStatus.PRE_OT_REST,
                Attendance.ShiftStatus.WORKING_OVERTIME,
            }
            if current_state in allowed_states:

                attendance.overtime_check_in = None
                attendance.overtime_check_out = None

                from decimal import Decimal
                attendance.overtime_hours = Decimal(
                    "0.00"
                )
                attendance.set_shift_status(
                    Attendance.ShiftStatus.REGULAR_DONE
                )
        ot_request.status = "rejected"
        if reason:
            ot_request.rejection_reason = reason
        if attendance:
            if attendance.is_holiday:
                attendance.set_attendance_type(
                    Attendance.Type.HOLIDAY
                )
            elif attendance.is_weekend:
                attendance.set_attendance_type(
                    Attendance.Type.WEEKEND
                )
            else:
                attendance.set_attendance_type(
                    Attendance.Type.NORMAL
                )
        employee = Employee.query.get(
            ot_request.employee_id
        )
        if employee and employee.user_id:
            reason_str = (
                f" Lý do: {reason}"
                if reason
                else ""
            )
            db.session.add(
                Notification(
                    user_id=employee.user_id,
                    type="overtime",
                    title="Yêu cầu tăng ca bị từ chối",
                    content=(
                        f"Yêu cầu tăng ca ngày "
                        f"{ot_request.overtime_date.strftime('%d/%m/%Y')} "
                        f"đã bị từ chối."
                        f"{reason_str}"
                    ),
                    link="/employee/attendance",
                    created_at=current_time,
                )
            )

    @staticmethod
    def _handle_offday_logic(
        employee_id: int,
        payload: dict,
        today: date,
    ) -> dict:
        current_time = (
            get_current_time()
            .astimezone(VN_TIMEZONE)
        )
        is_holiday = AttendanceService._is_holiday(today)
        is_weekend = today.weekday() >= 5
        employee = Employee.query.get(employee_id)
        if employee and employee.is_attendance_required is False:
            return {
                "type": "info",
                "action": "attendance_not_required",
                "attendance_state": "EXEMPT",
                "message": "Nhân sự này không bắt buộc chấm công.",
                "pass_through": False,
            }
        leave = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.from_date <= today,
            LeaveRequest.to_date >= today,
            LeaveRequest.status == "approved",
            LeaveRequest.is_deleted.is_(False),
        ).first()
        if leave:
            result_today = AttendanceService.get_or_create_today(
                employee_id=employee_id,
                now_dt=current_time,
            )
            record = result_today[0] if isinstance(result_today, tuple) else result_today
            record.set_attendance_type(
                Attendance.Type.LEAVE_APPROVED
            )
            record.set_shift_status(
                Attendance.ShiftStatus.LEAVE
            )
            record.check_in = None
            record.check_out = None
            record.overtime_check_in = None
            record.overtime_check_out = None
            record.regular_hours = Decimal("0.00")
            record.overtime_hours = Decimal("0.00")
            record.working_hours = Decimal("0.00")
            AttendanceService.finalize_attendance(
                record,
                finalize_status=True,
            )
            db.session.commit()
            return {
                "type": "info",
                "action": "leave_day",
                "attendance_state": (
                    Attendance.ShiftStatus.LEAVE
                ),
                "message": "Hôm nay là ngày nghỉ phép đã được duyệt.",
                "attendance": (
                    AttendanceService
                    .build_attendance_payload(record)
                ),
                "final": True,
                "locked_state": True,
            }
        if (
            bool(payload.get("decline_offday_work"))
             and (is_holiday or is_weekend)
        ):
            result_today = AttendanceService.get_or_create_today(
                employee_id=employee_id,
                now_dt=current_time,
            )
            record = result_today[0] if isinstance(result_today, tuple) else result_today
            record.is_holiday = is_holiday
            record.is_weekend = is_weekend
            attendance_type = (
                Attendance.Type.HOLIDAY
                if is_holiday
                else Attendance.Type.WEEKEND
            )
            shift_status = (
                Attendance.ShiftStatus.HOLIDAY_OFF
                if is_holiday
                else Attendance.ShiftStatus.WEEKEND_OFF
            )
            record.set_attendance_type(
                attendance_type
            )
            record.set_shift_status(
                shift_status
            )
            record.check_in = None
            record.check_out = None
            record.overtime_check_in = None
            record.overtime_check_out = None
            record.regular_hours = Decimal("0.00")
            record.overtime_hours = Decimal("0.00")
            record.working_hours = Decimal("0.00")
            AttendanceService.finalize_attendance(
                record,
                finalize_status=True,
            )
            db.session.commit()
            action_code = (
                AttendanceAction.ACTION_HOLIDAY_OFF
                if is_holiday
                else AttendanceAction.ACTION_WEEKEND_OFF
            )
            return {
                "type": "info",
                "status_code": 200,
                "action": action_code,
                "attendance_state": (
                    Attendance.ShiftStatus.normalize(
                        record.shift_status
                    )
                ),
                "message": (
                    "Đã ghi nhận nghỉ lễ hôm nay."
                    if is_holiday
                    else "Đã ghi nhận nghỉ cuối tuần hôm nay."
                ),
                "attendance": (
                    AttendanceService
                    .build_attendance_payload(record)
                ),
                "final": True,
                "locked_state": True,
            }
        return {
            "pass_through": True
        }
    
    @staticmethod
    def check_out_regular(
        employee_id: int,
        current_time: datetime,
        early_checkout: bool = False,
    ) -> dict:
        now_dt = current_time.astimezone(VN_TIMEZONE)

        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date(),
        ).first()

        if not record or not record.check_in:
            raise ValidationError("Bạn chưa check-in.")

        if record.check_out:
            raise ValidationError("Bạn đã check-out ca chính.")
        work_result = AttendanceService.calculate_regular_work_units(record)

        raw_regular_hours = Decimal(str(work_result.worked_hours))
        record.is_half_day = bool(work_result.is_half_day)
        if work_result.is_half_day:
            raw_regular_hours = (raw_regular_hours * Decimal("0.5")).quantize(
                Decimal("0.0001")
            )
        multiplier = AttendanceService._day_multiplier(
            bool(record.is_holiday),
            bool(record.is_weekend),
        )
        record.regular_hours = (raw_regular_hours * multiplier).quantize(
            Decimal("0.01")
        )
        record.set_shift_status(Attendance.ShiftStatus.REGULAR_DONE)
        AttendanceService.finalize_attendance(record, finalize_status=False)
        multiplier_label = (
            f" (x{multiplier.normalize()})" if multiplier > 1 else ""
        )
        if early_checkout:
            end_of_day = datetime.combine(
                now_dt.date(),
                REGULAR_END,
                tzinfo=VN_TIMEZONE,
            )

            early_minutes = max(
                0, int((end_of_day - now_dt).total_seconds() // 60)
            )
            db.session.commit()
            return {
                "type": "warning",
                "action": AttendanceAction.ACTION_CHECK_OUT,  # SỬA: Dùng đúng Class hằng số
                "message": (
                    f"Check-out lúc {now_dt.strftime('%H:%M:%S')}. "
                    f"Về sớm {early_minutes} phút."
                ),
                "attendance_state": Attendance.ShiftStatus.normalize(
                    record.shift_status
                ),
                "status_key": "early_leave",
                "regular_hours": str(record.regular_hours),
                "overtime_hours": str(record.overtime_hours or 0),
                "working_hours": str(record.working_hours),
                "attendance": AttendanceService.build_attendance_payload(record),
                "next_event": "offer_overtime",
                "requires_overtime_decision": True,
            }
        db.session.commit()
        return {
            "type": "success",
            "action": AttendanceAction.ACTION_CHECK_OUT,  # SỬA: Dùng đúng Class hằng số
            "message": (
                f"Check-out ca chính thành công. "
                f"Công thường: {record.regular_hours}h{multiplier_label}"
                + (
                    " (áp dụng nửa ngày công do đi muộn quá mức)"
                    if (
                        work_result.is_half_day
                        and not record.is_weekend
                        and not record.is_holiday
                    )
                    else ""
                )
            ),
            "attendance_state": Attendance.ShiftStatus.normalize(
                record.shift_status
            ),
            "regular_hours": str(record.regular_hours),
            "overtime_hours": str(record.overtime_hours or 0),
            "working_hours": str(record.working_hours),
            "attendance": AttendanceService.build_attendance_payload(record),
            "next_event": "offer_overtime",
            "requires_overtime_decision": True,
        }
    
    @staticmethod
    def check_in_overtime(employee_id: int) -> dict:
        now_dt = get_current_time()
        if not now_dt:
            raise ValidationError("Không xác định được thời gian hệ thống.")
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date(),
        ).first()
        if not record:
            raise ValidationError("Không tìm thấy dữ liệu chấm công hôm nay.")
        if not record.check_in:
            raise ValidationError("Bạn chưa check-in ca chính.")
        if not record.check_out:
            raise ValidationError("Bạn phải hoàn tất ca chính trước khi OT.")
        approved_ot = AttendanceService._get_approved_ot(
            employee_id,
            now_dt.date(),
        )
        if not approved_ot:
            raise ValidationError(
                "Yêu cầu tăng ca chưa được phê duyệt hoặc không tồn tại."
            )
        if record.overtime_check_in:
            raise ValidationError("Bạn đã check-in OT rồi.")
        normalized_shift = Attendance.ShiftStatus.normalize(record.shift_status)

        allowed_states = {
            Attendance.ShiftStatus.PRE_OT_REST,
            Attendance.ShiftStatus.OT_CHECKIN_REQUIRED,
        }
        if normalized_shift not in allowed_states:
            raise ValidationError(
                "Không thể bắt đầu tăng ca ở trạng thái hiện tại."
            )
        ot_open_dt = datetime.combine(
            now_dt.date(),
            WorkConfig.OT_START,
            tzinfo=now_dt.tzinfo,
        )
        if now_dt < record.check_out:
            raise ValidationError("Thời gian OT không thể trước thời gian checkout ca chính.")
        record.overtime_check_in = now_dt
        record.overtime_request_id = approved_ot.id 
        if now_dt < ot_open_dt:
            record.set_shift_status(Attendance.ShiftStatus.PRE_OT_REST)
            msg = (
                f"Đã xác thực tăng ca lúc {now_dt.strftime('%H:%M:%S')}. "
                f"Công OT sẽ bắt đầu tính từ giờ cấu hình {WorkConfig.OT_START.strftime('%H:%M:%S')}."
            )
        else:
            record.set_shift_status(Attendance.ShiftStatus.WORKING_OVERTIME)
            msg = f"Check-in tăng ca thành công lúc {now_dt.strftime('%H:%M:%S')}."
        db.session.commit()
        return {
            "type": "success",
            "action": AttendanceService.ACTION_CHECK_IN_OT,
            "message": msg,
            "attendance_state": record.normalized_shift_status,
            "overtime_status": approved_ot.status,
            "attendance": AttendanceService.build_attendance_payload(record),
        }