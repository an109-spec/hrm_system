from datetime import datetime, time 
from decimal import Decimal
from app.extensions import db
from app.models import Attendance, AttendanceStatus, Employee
from app.common.exceptions import ValidationError


class AttendanceService:
    REGULAR_START = time(8, 0, 0)
    LATE_THRESHOLD = time(8, 10, 0)
    REGULAR_END = time(17, 0, 0)

    @staticmethod
    def calculate_regular_hours(check_in: datetime, check_out: datetime) -> Decimal:
        end_of_shift = datetime.combine(check_in.date(), AttendanceService.REGULAR_END)
        capped_checkout = min(check_out, end_of_shift)
        if capped_checkout <= check_in:
            return Decimal("0.00")
        return Decimal(str(AttendanceService.recalculate_hours(check_in, capped_checkout)))
    @staticmethod
    def check_in_out(employee_id: int, sim_time_str: str = None):
        employee = Employee.query.get(employee_id)
        if employee and employee.is_attendance_required is False:
            return {"message": "Nhân sự này không áp dụng chấm công bắt buộc."}
        if not sim_time_str:
            raise ValidationError("Thiếu simulated_now")
        now_dt = datetime.fromisoformat(sim_time_str.replace("Z", "+00:00"))
        if now_dt.tzinfo is not None:
            now_dt = now_dt.replace(tzinfo=None)
        today = now_dt.date()
        record = Attendance.query.filter_by(employee_id=employee_id, date=today).first()
        if not record:
            standard_time_dt = now_dt.replace(hour=8, minute=10, second=0, microsecond=0)
            is_late = now_dt > standard_time_dt
            status_name = "LATE" if is_late else "PRESENT"
            status = AttendanceStatus.query.filter_by(status_name=status_name).first()
            record = Attendance(
                employee_id=employee_id,
                date=today,
                check_in=now_dt,
                status_id=status.id if status else None,
                working_hours=0
            )
            db.session.add(record)
            db.session.commit()
            msg = f"Check-in lúc {now_dt.strftime('%H:%M:%S')}. Trạng thái: {'Muộn' if is_late else 'Đúng giờ'}"
            return {"message": msg}
        if record.check_out:
            raise ValidationError("Bạn đã hoàn thành ca hôm nay")
        check_in = record.check_in
        if not check_in:
            raise ValidationError("Dữ liệu check-in không hợp lệ")
        if check_in.tzinfo is not None:
            check_in = check_in.replace(tzinfo=None)
        if now_dt < check_in:
            record.check_out = None
            raise ValidationError("Thời gian check-out không hợp lệ")
        duration = (now_dt - check_in).total_seconds()
        if duration < 60:
            record.check_out = None # Reset lại
            raise ValidationError("Thao tác quá nhanh. Vui lòng đợi ít nhất 1 phút sau khi check-in.")
        record.check_out = now_dt
        record.working_hours = AttendanceService.recalculate_hours(check_in, now_dt)
        db.session.commit()
        return {"message": f"Check-out thành công. Tổng công: {record.working_hours}h"}

    @staticmethod
    def get_today(employee_id: int, sim_time_str: str = None):
        from flask import session
        sim_time_str = sim_time_str or session.get("simulated_now")

        if not sim_time_str:
            raise ValidationError("Thiếu simulated_now")

        now_dt = datetime.fromisoformat(sim_time_str.replace("Z", "+00:00"))
        if now_dt.tzinfo is not None:
            now_dt = now_dt.replace(tzinfo=None)

        today = now_dt.date()

        return Attendance.query.filter_by(
            employee_id=employee_id,
            date=today
        ).first()

    @staticmethod
    def get_history(employee_id: int, sim_time_str=None, limit=10):
        from flask import session

        sim_time_str = sim_time_str or session.get("simulated_now")
        if not sim_time_str:
            raise ValidationError("Thiếu simulated_now")

        now_dt = datetime.fromisoformat(sim_time_str.replace("Z", "+00:00"))
        if now_dt.tzinfo is not None:
            now_dt = now_dt.replace(tzinfo=None)

        return Attendance.query.filter(
            Attendance.employee_id == employee_id,
            Attendance.date <= now_dt.date()
        ).order_by(Attendance.date.desc()).limit(limit).all()
    
    @staticmethod
    def recalculate_hours(check_in, check_out):
        if not check_in or not check_out:
            raise ValidationError("Thiếu dữ liệu check-in/check-out")

        if check_in.tzinfo is not None:
            check_in = check_in.replace(tzinfo=None)

        if check_out.tzinfo is not None:
            check_out = check_out.replace(tzinfo=None)

        if check_out < check_in:
            raise ValidationError("Thời gian không hợp lệ")

        start_dt = check_in.replace()

        if start_dt.hour > 8 or (start_dt.hour == 8 and start_dt.minute > 10):
            start_dt = start_dt.replace(hour=9, minute=0, second=0, microsecond=0)
        elif start_dt.hour < 8:
            start_dt = start_dt.replace(hour=8, minute=0, second=0, microsecond=0)

        delta = check_out - start_dt
        total_seconds = delta.total_seconds()

        lunch_start = start_dt.replace(hour=12, minute=0, second=0, microsecond=0)
        lunch_end = start_dt.replace(hour=13, minute=0, second=0, microsecond=0)

        overlap_start = max(start_dt, lunch_start)
        overlap_end = min(check_out, lunch_end)

        lunch_seconds = 0
        if overlap_end > overlap_start:
            lunch_seconds = (overlap_end - overlap_start).total_seconds()

        hours = (total_seconds - lunch_seconds) / 3600
        return max(0, round(hours, 2))
    
    @staticmethod
    def delete_attendance(employee_id, target_date_str):
        from flask import session

        if not target_date_str:
            raise ValidationError("Thiếu ngày cần xóa")

        dt = datetime.fromisoformat(target_date_str.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        target_date = dt.date()

        try:
            latest = Attendance.query.filter_by(employee_id=employee_id)\
                .order_by(Attendance.date.desc()).first()

            if not latest or latest.date != target_date:
                raise ValidationError("Chỉ được xóa bản ghi của ngày mới nhất để đảm bảo tính liên tục.")

            db.session.delete(latest)
            db.session.commit()

            # 🔥 reset demo time
            session.pop("simulated_now", None)

            remaining = Attendance.query.filter_by(employee_id=employee_id)\
                .order_by(Attendance.date.desc()).first()

            return remaining.date if remaining else None

        except Exception:
            db.session.rollback()
            raise