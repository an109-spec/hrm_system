
from datetime import datetime
from app.constants.attendance import WorkConfig
from app.models.attendance import Attendance, AttendanceShiftStatus
from app.models.overtime_request import OvertimeRequest
from app.modules.attendance.dto import AttendanceStateDTO
from app.utils.time import get_current_time, VN_TIMEZONE

class AttendanceStateService:
    @staticmethod
    def compute_attendance_state(
        now: datetime | None,
        attendance: Attendance | None,
        ot_request: OvertimeRequest | None = None,
    ) -> AttendanceStateDTO:

        # =====================================================
        # TIME SOURCE STANDARDIZATION
        # =====================================================
        if now is None:
            now = get_current_time()
        # Normalize timezone
        if now.tzinfo is not None:
            now = now.astimezone(VN_TIMEZONE)

        # Convert to naive time for comparison with WorkConfig (time objects)
        current_time = now.timetz().replace(tzinfo=None)

        # =====================================================
        # CASE: NOT EXISTS IN DATABASE YET
        # =====================================================
        if not attendance:
            # Nếu là sáng sớm (trước 5h), báo ca đêm kết thúc / chưa đến ngày mới
            msg = "Bạn chưa bắt đầu ngày làm việc."
            if now.hour < 5:
                msg = "Chưa đến giờ làm việc ngày mới hoặc ca đêm đã kết thúc."
                
            return AttendanceStateDTO(
                state=AttendanceShiftStatus.NOT_STARTED,
                button_enabled=True,
                button_text="🔳 XÁC THỰC CHẤM CÔNG",
                can_scan=True,
                message=msg,
            )

        # Trích xuất thông tin từ bản ghi đã có
        is_yesterday = attendance.date < now.date()
        date_str = attendance.date.strftime('%d/%m')
        raw_state = AttendanceShiftStatus.normalize(attendance.shift_status)

        # =====================================================
        # TERMINAL STATES (Trạng thái kết thúc - Khóa flow)
        # =====================================================
        if raw_state == AttendanceShiftStatus.COMPLETED:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="✅ ĐÃ HOÀN THÀNH NGÀY CÔNG",
                can_scan=False,
                message="Ngày công đã hoàn tất.",
                locked_state=True
            )

        if raw_state == AttendanceShiftStatus.HOLIDAY_OFF:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="🎉 NGHỈ LỄ",
                can_scan=False,
                message="Hôm nay là ngày nghỉ lễ.",
                locked_state=True
            )

        if raw_state == AttendanceShiftStatus.WEEKEND_OFF:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="🛌 NGHỈ CUỐI TUẦN",
                can_scan=False,
                message="Hôm nay là ngày nghỉ cuối tuần.",
                locked_state=True
            )

        if raw_state == AttendanceShiftStatus.LEAVE:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="📋 NGHỈ PHÉP",
                can_scan=False,
                message="Bạn đang nghỉ phép.",
                locked_state=True
            )

        if raw_state == AttendanceShiftStatus.ABSENT:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="❌ VẮNG MẶT",
                can_scan=False,
                message="Bạn bị ghi nhận vắng mặt.",
                locked_state=True
            )

        # =====================================================
        # STATE: NOT STARTED (Bản ghi khởi tạo nhưng chưa quét)
        # =====================================================
        if raw_state == AttendanceShiftStatus.NOT_STARTED:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=True,
                button_text="🔳 XÁC THỰC CHẤM CÔNG",
                can_scan=True,
                message="Vui lòng check-in để bắt đầu.",
            )

        # =====================================================
        # STATE: WORKING REGULAR (Đang trong ca chính)
        # =====================================================
        if raw_state == AttendanceShiftStatus.WORKING_REGULAR:
            # Xử lý quên checkout của ngày hôm trước
            if is_yesterday:
                return AttendanceStateDTO(
                    state=AttendanceShiftStatus.REGULAR_CHECKOUT_REQUIRED,
                    button_enabled=True,
                    button_text=f"🔳 CHECKOUT CA {date_str}",
                    can_scan=True,
                    message=f"Bạn quên chưa checkout ca làm việc ngày {date_str}.",
                )
                
            # Đang trong khung giờ nghỉ trưa (Giữ nguyên state hệ thống nhưng đổi UI hiển thị)
            if WorkConfig.LUNCH_START <= current_time < WorkConfig.LUNCH_END:
                return AttendanceStateDTO(
                    state=raw_state,
                    button_enabled=False,
                    button_text="🍽️ NGHỈ TRƯA",
                    can_scan=False,
                    message="Đang trong giờ nghỉ trưa.",
                )

            # Vẫn đang trong giờ làm việc hành chính
            if current_time < WorkConfig.WORKDAY_END:
                return AttendanceStateDTO(
                    state=raw_state,
                    button_enabled=True,
                    button_text="🔳 ĐANG LÀM VIỆC",
                    can_scan=True,
                    message="Đang trong ca làm việc chính thức.",
                )

            # Đã hết giờ làm việc chính thức nhưng chưa chịu bấm checkout
            return AttendanceStateDTO(
                state=AttendanceShiftStatus.REGULAR_CHECKOUT_REQUIRED,
                button_enabled=True,
                button_text="🔳 XÁC NHẬN CHECKOUT",
                can_scan=True,
                message="Hết giờ làm việc hành chính, vui lòng checkout.",
            )

        # =====================================================
        # STATE: REGULAR CHECKOUT REQUIRED
        # =====================================================
        if raw_state == AttendanceShiftStatus.REGULAR_CHECKOUT_REQUIRED:
            btn_text = "🔳 CHECKOUT CA CHÍNH"
            msg = "Bạn chưa hoàn tất checkout ca chính."
            
            if is_yesterday:
                btn_text = f"🔳 CHECKOUT CA {date_str}"
                msg = f"Bạn chưa checkout ca làm việc ngày {date_str}."

            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=True,
                button_text=btn_text,
                can_scan=True,
                message=msg,
            )

        # =====================================================
        # STATE: REGULAR DONE (Đã checkout ca chính)
        # =====================================================
        if raw_state == AttendanceShiftStatus.REGULAR_DONE:
            # Khoảng thời gian chờ, chưa tới giờ mở đăng ký tăng ca (OT)
            if current_time < WorkConfig.OT_START:
                return AttendanceStateDTO(
                    state=AttendanceShiftStatus.PRE_OT_REST,  # Đồng bộ hóa với hằng số hệ thống
                    button_enabled=False,
                    button_text="⏳ NGHỈ CHỜ TĂNG CA",
                    can_scan=False,
                    message="Đã hoàn tất ca chính. Đang trong thời gian nghỉ giải lao trước tăng ca.",
                )

            # Đã đến hoặc qua giờ bắt đầu ca OT, nhắc nhở checkin OT
            return AttendanceStateDTO(
                state=AttendanceShiftStatus.OT_CHECKIN_REQUIRED,
                button_enabled=True,
                button_text="🔳 CHECKIN OT",
                can_scan=True,
                overtime_status="AVAILABLE",
                message="Đến giờ tăng ca. Bạn có thể thực hiện check-in OT.",
            )

        # =====================================================
        # STATE: OT PENDING (Chờ duyệt đơn OT)
        # =====================================================
        if raw_state == AttendanceShiftStatus.REGULAR_DONE_PENDING_OT_DECISION:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="⏳ CHỜ DUYỆT OT",
                can_scan=False,
                overtime_status=(
                    ot_request.status.upper()
                    if ot_request else "PENDING"
                ),
                requires_overtime_decision=True,
                message="Hệ thống đang chờ quản lý phê duyệt đơn tăng ca của bạn.",
            )

        # =====================================================
        # STATE: WORKING OVERTIME (Đang làm ca tăng ca)
        # =====================================================
        if raw_state == AttendanceShiftStatus.WORKING_OVERTIME:
            display_msg = "Đang trong ca làm việc tăng ca (OT)."
            btn_text = "🔳 KẾT THÚC OT"
        
            if is_yesterday:
                display_msg = f"Hệ thống yêu cầu chốt ca tăng ca muộn từ hôm qua ({date_str})."
                btn_text = "🔳 CHỐT CA ĐÊM"
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=True,
                button_text=btn_text,
                can_scan=True,
                overtime_status="APPROVED",
                message=display_msg,
            )
        return AttendanceStateDTO(
            state="unknown",
            button_enabled=False,
            button_text="⚠️ UNKNOWN",
            can_scan=False,
            message=f"Hệ thống phát hiện trạng thái không hợp lệ: {raw_state}",
        )