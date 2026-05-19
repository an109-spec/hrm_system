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
    
    @staticmethod
    def calculate_regular_work_units(
        attendance: Attendance
    ) -> WorkUnitDTO:

        if not attendance.check_in or not attendance.check_out:
            return WorkUnitDTO(
                units=Decimal("0.00"),
                is_half_day=False,
                worked_hours=Decimal("0.00"),
                late_minutes=attendance.late_minutes or 0,
                early_leave_minutes=0,
            )

        normalized_type = Attendance.Type.normalize(
            attendance.attendance_type
        )

        absent_types = {
            Attendance.Type.ABSENT,
            Attendance.Type.ABSENT_UNEXCUSED,
            Attendance.Type.ABNORMAL_REJECTED,
        }

        if normalized_type in absent_types:
            return WorkUnitDTO(
                units=Decimal("0.00"),
                is_half_day=False,
                worked_hours=Decimal("0.00"),
                late_minutes=attendance.late_minutes or 0,
                early_leave_minutes=0,
            )

        if normalized_type == Attendance.Type.LEAVE_APPROVED:
            return WorkUnitDTO(
                units=Decimal("1.00"),
                is_half_day=False,
                worked_hours=Decimal("8.00"),
                late_minutes=0,
                early_leave_minutes=0,
            )

        raw_hours = Decimal(str(attendance.regular_hours or 0))

        late_minutes = attendance.late_minutes or 0

        start_minutes = (
            WorkConfig.WORKDAY_START.hour * 60
            + WorkConfig.WORKDAY_START.minute
        )

        threshold_minutes = (
            WorkConfig.LATE_THRESHOLD.hour * 60
            + WorkConfig.LATE_THRESHOLD.minute
        )

        half_day_limit = threshold_minutes - start_minutes

        is_half_day = late_minutes >= half_day_limit

        if raw_hours < Decimal("2.00"):
            return WorkUnitDTO(
                units=Decimal("0.00"),
                is_half_day=is_half_day,
                worked_hours=raw_hours,
                late_minutes=late_minutes,
                early_leave_minutes=0,
            )

        if is_half_day or raw_hours < Decimal("4.00"):
            return WorkUnitDTO(
                units=Decimal("0.50"),
                is_half_day=True,
                worked_hours=raw_hours,
                late_minutes=late_minutes,
                early_leave_minutes=0,
            )

        return WorkUnitDTO(
            units=Decimal("1.00"),
            is_half_day=False,
            worked_hours=raw_hours,
            late_minutes=late_minutes,
            early_leave_minutes=0,
        )