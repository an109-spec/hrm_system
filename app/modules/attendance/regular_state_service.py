from datetime import datetime, time

from app.models import Attendance
from app.modules.attendance.dto import AttendanceStateDTO
from app.constants.attendance import WorkConfig


class RegularStateService:

    @staticmethod
    def resolve(
        raw_state: str,
        now: datetime,
        current_time: time,
        is_yesterday: bool,
        date_str: str,
    ) -> AttendanceStateDTO:

        if raw_state == Attendance.ShiftStatus.NOT_STARTED:
            return RegularStateService.handle_not_started(now)

        if raw_state == Attendance.ShiftStatus.WORKING_REGULAR:

            if is_yesterday:
                return AttendanceStateDTO(
                    state=Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED,
                    button_enabled=True,
                    button_text=f"🔳 CHECKOUT CA {date_str}",
                    can_scan=True,
                    message=f"Bạn quên chưa checkout ca làm việc ngày {date_str}.",
                )

            if WorkConfig.LUNCH_START <= current_time < WorkConfig.LUNCH_END:
                return AttendanceStateDTO(
                    state=Attendance.ShiftStatus.WORKING_REGULAR,
                    button_enabled=False,
                    button_text="🍽️ NGHỈ TRƯA",
                    can_scan=False,
                    message="Đang nghỉ trưa.",
                )

            if current_time < WorkConfig.WORKDAY_END:
                return AttendanceStateDTO(
                    state=raw_state,
                    button_enabled=True,
                    button_text="🔳 ĐANG LÀM VIỆC",
                    can_scan=True,
                    message="Đang trong ca làm việc.",
                )

            return AttendanceStateDTO(
                state=Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED,
                button_enabled=True,
                button_text="🔳 XÁC NHẬN CHECKOUT",
                can_scan=True,
                message="Hết giờ làm, vui lòng checkout.",
            )

        if raw_state == Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED:

            btn_text = "🔳 CHECKOUT CA CHÍNH"
            msg = "Bạn chưa checkout."

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

        if raw_state == Attendance.ShiftStatus.REGULAR_DONE:

            if current_time < WorkConfig.OT_START:
                return AttendanceStateDTO(
                    state=Attendance.ShiftStatus.PRE_OT_REST,
                    button_enabled=False,
                    button_text="⏳ NGHỈ CHỜ TĂNG CA",
                    can_scan=False,
                    message="Đã hoàn tất ca chính. Đang nghỉ trước tăng ca.",
                )

            return AttendanceStateDTO(
                state=Attendance.ShiftStatus.OT_CHECKIN_REQUIRED,
                button_enabled=True,
                button_text="🔳 CHECKIN OT",
                can_scan=True,
                overtime_status="AVAILABLE",
                message="Đến giờ tăng ca. Bạn có thể check-in OT.",
            )

        return AttendanceStateDTO(
            state="unknown",
            button_enabled=False,
            button_text="⚠️ UNKNOWN",
            can_scan=False,
            message=f"Unknown state: {raw_state}",
        )

    @staticmethod
    def handle_not_started(now: datetime) -> AttendanceStateDTO:

        msg = "Bạn chưa bắt đầu ngày làm việc."

        if now.hour < 5:
            msg = "Chưa đến giờ làm việc ngày mới hoặc ca đêm đã kết thúc."

        return AttendanceStateDTO(
            state=Attendance.ShiftStatus.NOT_STARTED,
            button_enabled=True,
            button_text="🔳 XÁC THỰC CHẤM CÔNG",
            can_scan=True,
            message=msg,
        )

    @staticmethod
    def handle_terminal_state(
        raw_state: str,
    ) -> AttendanceStateDTO:

        mapping = {
            Attendance.ShiftStatus.COMPLETED: (
                "✅ ĐÃ HOÀN THÀNH NGÀY CÔNG",
                "Ngày công đã hoàn tất.",
            ),
            Attendance.ShiftStatus.HOLIDAY_OFF: (
                "🎉 NGHỈ LỄ",
                "Hôm nay là ngày nghỉ lễ.",
            ),
            Attendance.ShiftStatus.WEEKEND_OFF: (
                "🛌 NGHỈ CUỐI TUẦN",
                "Hôm nay là ngày nghỉ cuối tuần.",
            ),
            Attendance.ShiftStatus.LEAVE: (
                "📋 NGHỈ PHÉP",
                "Bạn đang nghỉ phép.",
            ),
            Attendance.ShiftStatus.ABSENT: (
                "❌ VẮNG MẶT",
                "Bạn bị ghi nhận vắng mặt.",
            ),
        }

        btn_text, msg = mapping[raw_state]

        return AttendanceStateDTO(
            state=raw_state,
            button_enabled=False,
            button_text=btn_text,
            can_scan=False,
            message=msg,
            locked_state=True,
        )