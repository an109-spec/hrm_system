from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import Attendance, OvertimeRequest
from app.modules.attendance.dto import AttendanceStateDTO, WorkUnitDTO
from app.modules.attendance.regular_state_service import (
    RegularStateService,
)
from app.modules.attendance.overtime_state_service import (
    OvertimeStateService,
)
from app.utils.time import get_current_time

VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

from decimal import Decimal

from app.constants.attendance import WorkConfig


class AttendanceStateService:

    @staticmethod
    def compute_attendance_state(
        now: datetime | None,
        attendance: Attendance | None,
        ot_request: OvertimeRequest | None = None,
    ) -> AttendanceStateDTO:

        if now is None:
            now = get_current_time()

        if now.tzinfo is not None:
            now = now.astimezone(VN_TIMEZONE)

        current_time = now.timetz().replace(tzinfo=None)

        if not attendance:
            return RegularStateService.handle_not_started(now)

        raw_state = Attendance.ShiftStatus.normalize(
            attendance.shift_status
        )

        is_yesterday = attendance.date < now.date()
        date_str = attendance.date.strftime("%d/%m")

        # =====================================================
        # TERMINAL STATES
        # =====================================================

        if raw_state in Attendance.ShiftStatus.TERMINAL_STATUSES:
            return RegularStateService.handle_terminal_state(
                raw_state
            )

        # =====================================================
        # REGULAR FLOW
        # =====================================================

        if raw_state in {
            Attendance.ShiftStatus.NOT_STARTED,
            Attendance.ShiftStatus.WORKING_REGULAR,
            Attendance.ShiftStatus.REGULAR_DONE,
            Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED,
        }:
            return RegularStateService.resolve(
                raw_state=raw_state,
                now=now,
                current_time=current_time,
                is_yesterday=is_yesterday,
                date_str=date_str,
            )

        # =====================================================
        # OT FLOW
        # =====================================================

        return OvertimeStateService.resolve(
            raw_state=raw_state,
            current_time=current_time,
            is_yesterday=is_yesterday,
            date_str=date_str,
            ot_request=ot_request,
        )
    
