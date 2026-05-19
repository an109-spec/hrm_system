from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.common.exceptions import ValidationError
from app.constants import VN_TIMEZONE, WorkingStatus
from app.extensions import db
from app.models import Attendance, AttendanceStatus, Employee, Holiday, LeaveRequest


class AttendanceDayService:
    @staticmethod
    def get_or_create_today(employee_id: int, now_dt: datetime) -> Attendance:
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=VN_TIMEZONE)
        else:
            now_dt = now_dt.astimezone(VN_TIMEZONE)
        today = now_dt.date()
        record = Attendance.query.filter_by(employee_id=employee_id, date=today).first()
        if record:
            return record
        employee = Employee.query.get(employee_id)
        if not employee:
            raise ValidationError("Nhân viên không tồn tại")
        if not employee.is_attendance_required:
            raise ValidationError("Nhân viên không thuộc đối tượng chấm công")
        if (employee.working_status or "").strip().lower() == WorkingStatus.RESIGNED:
            raise ValidationError("Nhân viên không còn hoạt động")
        is_weekend = today.weekday() >= 5
        holiday = AttendanceDayService.get_holiday(today)
        is_holiday = holiday is not None
        leave_request = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == LeaveRequest.Status.APPROVED,
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
        record = Attendance(employee_id=employee_id,date=today,working_hours=Decimal("0.00"),regular_hours=Decimal("0.00"),overtime_hours=Decimal("0.00"),is_half_day=False,late_minutes=0,is_weekend=is_weekend,is_holiday=is_holiday)
        record.set_shift_status(shift_status)
        record.set_attendance_type(attendance_type)
        record.is_leave_day = bool(leave_request)
        record.is_offday = is_weekend or is_holiday or bool(leave_request)
        db.session.add(record)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return Attendance.query.filter_by(employee_id=employee_id, date=today).first()
        return record

    @staticmethod
    def get_status(status_name: str | None) -> AttendanceStatus | None:
        normalized = Attendance.ShiftStatus.normalize(status_name)
        if not Attendance.ShiftStatus.is_valid(normalized):
            return None
        return AttendanceStatus.query.filter_by(status_name=normalized).first()

    @staticmethod
    def get_holiday(target_date: date) -> Holiday | None:
        holiday = Holiday.query.filter(Holiday.date == target_date, Holiday.is_recurring.is_(False), Holiday.is_active.is_(True)).first()
        if holiday:
            return holiday
        return Holiday.query.filter(Holiday.is_recurring.is_(True), Holiday.is_active.is_(True), db.extract("month", Holiday.date) == target_date.month, db.extract("day", Holiday.date) == target_date.day).first()