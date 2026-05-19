
from app.models.attendance import Attendance
from app.modules.attendance.dto import WorkUnitDTO
from decimal import Decimal
from app.constants.attendance import WorkConfig
from app.constants.overtime import OvertimeConfig
from datetime import datetime
from zoneinfo import ZoneInfo
VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

class AttendanceCalculationService:

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
    
    @staticmethod
    def _get_day_rate(attendance_type: str | None) -> Decimal:
        normalized_status = Attendance.ShiftStatus.normalize(attendance_type)
        RATE_MAP = {
            "working_regular": OvertimeConfig.MULTIPLIERS.get("after_shift", Decimal("1.50")),
            "completed":       OvertimeConfig.MULTIPLIERS.get("after_shift", Decimal("1.50")),
            "weekend_off":     OvertimeConfig.MULTIPLIERS.get("weekend", Decimal("2.00")),
            "holiday_off":     OvertimeConfig.MULTIPLIERS.get("holiday", Decimal("3.00")),
            "leave":           OvertimeConfig.MULTIPLIERS.get("after_shift", Decimal("1.50")),
        }
        ABSENT_TYPES = {
            "absent",
            "not_started",
        }
        if normalized_status in ABSENT_TYPES:
            return Decimal("0.00")
        return RATE_MAP.get(
            normalized_status, 
            OvertimeConfig.MULTIPLIERS.get("normal", Decimal("1.00"))
        )
    
    @staticmethod
    def calculate_overtime_hours(
        overtime_check_in: datetime | None,
        overtime_check_out: datetime | None,
    ) -> Decimal:

        if not overtime_check_in or not overtime_check_out:
            return Decimal("0.00")

        if overtime_check_in.tzinfo is None:
            overtime_check_in = overtime_check_in.replace(
                tzinfo=VN_TIMEZONE
            )

        if overtime_check_out.tzinfo is None:
            overtime_check_out = overtime_check_out.replace(
                tzinfo=VN_TIMEZONE
            )

        overtime_check_in = overtime_check_in.astimezone(
            VN_TIMEZONE
        )

        overtime_check_out = overtime_check_out.astimezone(
            VN_TIMEZONE
        )

        day = overtime_check_in.date()

        ot_start = datetime.combine(
            day,
            WorkConfig.OT_START,
            tzinfo=VN_TIMEZONE,
        )

        ot_end = datetime.combine(
            day,
            WorkConfig.OT_END,
            tzinfo=VN_TIMEZONE,
        )

        actual_start = max(
            ot_start,
            overtime_check_in,
        )

        actual_end = min(
            ot_end,
            overtime_check_out,
        )

        if actual_end <= actual_start:
            return Decimal("0.00")

        hours = (
            actual_end - actual_start
        ).total_seconds() / 3600

        return Decimal(
            str(round(hours, 4))
        )