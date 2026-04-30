from datetime import datetime, time
from decimal import Decimal

from flask import session

from app.extensions import db
from app.models import Attendance, AttendanceStatus, Employee
from app.common.exceptions import ValidationError


class AttendanceService:
    """
    Enterprise Attendance Flow

    Tách riêng hoàn toàn:
    - check_in()
    - check_out_regular()
    - check_in_overtime()
    - check_out_overtime()

    Không dùng check_in_out() kiểu cũ nữa.
    """

    # ===== FIXED SHIFT CONFIG =====

    REGULAR_START = time(8, 0, 0)
    REGULAR_END = time(17, 0, 0)

    LUNCH_START = time(12, 0, 0)
    LUNCH_END = time(13, 0, 0)

    HALF_DAY_THRESHOLD = time(9, 0, 0)  # sau 09:00 => half day

    OT_START = time(19, 0, 0)
    OT_END = time(22, 0, 0)

    SHIFT_STATUS_NOT_STARTED = "not_started"
    SHIFT_STATUS_WORKING = "working_regular"
    SHIFT_STATUS_REGULAR_DONE = "regular_done"
    SHIFT_STATUS_PRE_OT_REST = "pre_ot_rest"
    SHIFT_STATUS_WORKING_OT = "working_overtime"
    SHIFT_STATUS_COMPLETED = "completed"

    # =========================================================
    # COMMON
    # =========================================================

    @staticmethod
    def parse_time(sim_time_str: str) -> datetime:
        if not sim_time_str:
            raise ValidationError("Thiếu simulated_now")

        now_dt = datetime.fromisoformat(
            sim_time_str.replace("Z", "+00:00")
        )

        if now_dt.tzinfo is not None:
            now_dt = now_dt.replace(tzinfo=None)

        return now_dt

    @staticmethod
    def get_or_create_today(employee_id: int, now_dt: datetime) -> Attendance:
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date()
        ).first()

        if record:
            return record

        record = Attendance(
            employee_id=employee_id,
            date=now_dt.date(),
            shift_status=AttendanceService.SHIFT_STATUS_NOT_STARTED,
            working_hours=Decimal("0.00"),
            regular_hours=Decimal("0.00"),
            overtime_hours=Decimal("0.00"),
            is_half_day=False,
            late_minutes=0,
            is_weekend=False,
            is_holiday=False,
        )

        db.session.add(record)
        db.session.flush()

        return record

    @staticmethod
    def get_status(status_name: str):
        return AttendanceStatus.query.filter_by(
            status_name=status_name
        ).first()

    # =========================================================
    # REGULAR HOURS
    # =========================================================

    @staticmethod
    def calculate_regular_hours(
        check_in: datetime,
        check_out: datetime
    ) -> Decimal:
        """
        Logic chuẩn:

        if check_in < 08:00:
            start = 08:00

        elif check_in > 08:00:
            start = check_in

        nếu check_in > 09:00:
            => half day = 4.0h

        check_out:
            max = 17:00
        """

        if not check_in or not check_out:
            return Decimal("0.00")

        day = check_in.date()

        shift_start = datetime.combine(day, AttendanceService.REGULAR_START)
        shift_end = datetime.combine(day, AttendanceService.REGULAR_END)

        lunch_start = datetime.combine(day, AttendanceService.LUNCH_START)
        lunch_end = datetime.combine(day, AttendanceService.LUNCH_END)

        half_day_limit = datetime.combine(
            day,
            AttendanceService.HALF_DAY_THRESHOLD
        )

        # check-out capped at 17:00
        actual_end = min(check_out, shift_end)

        # check-in logic chuẩn
        if check_in < shift_start:
            actual_start = shift_start
        else:
            actual_start = check_in

        if actual_end <= actual_start:
            return Decimal("0.00")

        # sau 09:00 => half day cố định
        if check_in > half_day_limit:
            return Decimal("4.00")

        total_seconds = (actual_end - actual_start).total_seconds()

        # trừ nghỉ trưa nếu overlap
        overlap_start = max(actual_start, lunch_start)
        overlap_end = min(actual_end, lunch_end)

        lunch_seconds = 0
        if overlap_end > overlap_start:
            lunch_seconds = (overlap_end - overlap_start).total_seconds()

        hours = (total_seconds - lunch_seconds) / 3600

        return Decimal(str(round(max(0, hours), 2)))

    # =========================================================
    # OVERTIME
    # =========================================================

    @staticmethod
    def calculate_overtime_hours(
        overtime_check_in: datetime,
        overtime_check_out: datetime
    ) -> Decimal:
        """
        OT chuẩn:

        max(19:00, overtime_check_in)
        →
        min(22:00, overtime_check_out)
        """

        if not overtime_check_in or not overtime_check_out:
            return Decimal("0.00")

        day = overtime_check_in.date()

        ot_start = datetime.combine(day, AttendanceService.OT_START)
        ot_end = datetime.combine(day, AttendanceService.OT_END)

        actual_start = max(ot_start, overtime_check_in)
        actual_end = min(ot_end, overtime_check_out)

        if actual_end <= actual_start:
            return Decimal("0.00")

        hours = (actual_end - actual_start).total_seconds() / 3600

        return Decimal(str(round(hours, 2)))

    # =========================================================
    # CHECK IN
    # =========================================================

    @staticmethod
    def check_in(employee_id: int, sim_time_str: str):
        employee = Employee.query.get(employee_id)

        if employee and employee.is_attendance_required is False:
            raise ValidationError(
                "Nhân sự này không áp dụng chấm công bắt buộc."
            )

        now_dt = AttendanceService.parse_time(sim_time_str)

        record = AttendanceService.get_or_create_today(
            employee_id,
            now_dt
        )

        if record.check_in:
            raise ValidationError("Bạn đã check-in hôm nay.")

        record.check_in = now_dt
        record.shift_status = AttendanceService.SHIFT_STATUS_WORKING

        late_minutes = max(
            0,
            int(
                (
                    now_dt - datetime.combine(
                        now_dt.date(),
                        AttendanceService.REGULAR_START
                    )
                ).total_seconds() / 60
            )
        )

        record.late_minutes = late_minutes

        if now_dt.time() > AttendanceService.HALF_DAY_THRESHOLD:
            record.is_half_day = True

        status_name = "LATE" if late_minutes > 0 else "PRESENT"
        status = AttendanceService.get_status(status_name)

        if status:
            record.status_id = status.id

        db.session.commit()

        return {
            "message": f"Check-in thành công lúc {now_dt.strftime('%H:%M:%S')}"
        }

    # =========================================================
    # CHECK OUT REGULAR
    # =========================================================

    @staticmethod
    def check_out_regular(employee_id: int, sim_time_str: str):
        now_dt = AttendanceService.parse_time(sim_time_str)

        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date()
        ).first()

        if not record or not record.check_in:
            raise ValidationError("Bạn chưa check-in.")

        if record.check_out:
            raise ValidationError("Bạn đã check-out ca chính.")

        record.check_out = now_dt

        record.regular_hours = (
            AttendanceService.calculate_regular_hours(
                record.check_in,
                record.check_out
            )
        )

        record.shift_status = (
            AttendanceService.SHIFT_STATUS_REGULAR_DONE
        )

        db.session.commit()

        return {
            "message": f"Check-out ca chính thành công. Công thường: {record.regular_hours}h"
        }

    # =========================================================
    # CHECK IN OT
    # =========================================================

    @staticmethod
    def check_in_overtime(employee_id: int, sim_time_str: str):
        now_dt = AttendanceService.parse_time(sim_time_str)

        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date()
        ).first()

        if not record or not record.check_out:
            raise ValidationError(
                "Bạn phải hoàn tất ca chính trước khi OT."
            )

        if record.overtime_check_in:
            raise ValidationError("Bạn đã check-in OT.")

        record.overtime_check_in = now_dt
        record.shift_status = (
            AttendanceService.SHIFT_STATUS_WORKING_OT
        )

        db.session.commit()

        return {
            "message": f"Check-in OT lúc {now_dt.strftime('%H:%M:%S')}"
        }

    # =========================================================
    # CHECK OUT OT
    # =========================================================

    @staticmethod
    def check_out_overtime(employee_id: int, sim_time_str: str):
        now_dt = AttendanceService.parse_time(sim_time_str)

        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date()
        ).first()

        if not record or not record.overtime_check_in:
            raise ValidationError("Bạn chưa check-in OT.")

        if record.overtime_check_out:
            raise ValidationError("Bạn đã check-out OT.")

        record.overtime_check_out = now_dt

        record.overtime_hours = (
            AttendanceService.calculate_overtime_hours(
                record.overtime_check_in,
                record.overtime_check_out
            )
        )

        AttendanceService.finalize_attendance(record)

        db.session.commit()

        return {
            "message": f"Check-out OT thành công. Tăng ca: {record.overtime_hours}h"
        }

    # =========================================================
    # FINALIZE
    # =========================================================

    @staticmethod
    def finalize_attendance(record: Attendance):
        total = (
            Decimal(record.regular_hours or 0)
            + Decimal(record.overtime_hours or 0)
        )

        record.working_hours = total
        record.shift_status = (
            AttendanceService.SHIFT_STATUS_COMPLETED
        )

    # =========================================================
    # GET TODAY
    # =========================================================

    @staticmethod
    def get_today(employee_id: int, sim_time_str: str = None):
        sim_time_str = sim_time_str or session.get("simulated_now")
        now_dt = AttendanceService.parse_time(sim_time_str)

        return Attendance.query.filter_by(
            employee_id=employee_id,
            date=now_dt.date()
        ).first()

    # =========================================================
    # HISTORY
    # =========================================================

    @staticmethod
    def get_history(employee_id: int, sim_time_str=None, limit=10):
        sim_time_str = sim_time_str or session.get("simulated_now")
        now_dt = AttendanceService.parse_time(sim_time_str)

        return Attendance.query.filter(
            Attendance.employee_id == employee_id,
            Attendance.date <= now_dt.date()
        ).order_by(
            Attendance.date.desc()
        ).limit(limit).all()