from datetime import time

from app.models import Attendance, OvertimeRequest
from app.modules.attendance.dto import AttendanceStateDTO


class OvertimeStateService:

    @staticmethod
    def resolve(
        raw_state: str,
        current_time: time,
        is_yesterday: bool,
        date_str: str,
        ot_request: OvertimeRequest | None,
    ) -> AttendanceStateDTO:

        if raw_state == Attendance.ShiftStatus.PRE_OT_REST:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="⏳ NGHỈ CHỜ TĂNG CA",
                can_scan=False,
                message="Đang nghỉ trước tăng ca.",
            )

        if raw_state == Attendance.ShiftStatus.OT_CHECKIN_REQUIRED:
            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=True,
                button_text="🔳 CHECKIN OT",
                can_scan=True,
                overtime_status="APPROVED",
                message="Sẵn sàng bắt đầu tăng ca.",
            )

        if raw_state == Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION:

            return AttendanceStateDTO(
                state=raw_state,
                button_enabled=False,
                button_text="⏳ CHỜ DUYỆT OT",
                can_scan=False,
                overtime_status=(
                    ot_request.status.upper()
                    if ot_request
                    else "PENDING"
                ),
                message="Đang chờ duyệt tăng ca.",
            )

        if raw_state == Attendance.ShiftStatus.WORKING_OVERTIME:

            display_msg = "Đang trong ca tăng ca."
            btn_text = "🔳 KẾT THÚC OT"

            if is_yesterday:
                display_msg = (
                    f"Đang kết thúc ca tăng ca từ hôm qua ({date_str})."
                )
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
            message=f"Unknown OT state: {raw_state}",
        )