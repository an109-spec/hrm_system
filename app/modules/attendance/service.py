from datetime import datetime, date, timezone
from sqlalchemy import and_

from app.extensions import db
from app.models import Attendance, AttendanceStatus
from app.common.exceptions import ValidationError


class AttendanceService:

    # ==============================
    # CHECK IN / OUT
    # ==============================
    @staticmethod
    def check_in_out(employee_id: int, sim_time_str: str = None):
        if not sim_time_str:
            raise ValidationError("Thiếu simulated_now")

        now_dt = datetime.fromisoformat(sim_time_str.replace("Z", "+00:00")).replace(tzinfo=None)

        today = now_dt.date()

        record = Attendance.query.filter_by(employee_id=employee_id, date=today).first()

        if not record:
            # Cho phép check-in bất cứ lúc nào, nhưng tính trạng thái dựa trên mốc 08:10
            standard_time_dt = now_dt.replace(hour=8, minute=10, second=0, microsecond=0)
            
            # Nếu now_dt > 08:10:00 -> LATE
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

        # CHECK OUT
        if record.check_out:
            raise ValidationError("Bạn đã hoàn thành ca hôm nay")

        record.check_out = now_dt
        # Chặn nếu check-out quá sớm sau khi check-in (ví dụ dưới 1 phút)
        duration = (now_dt - record.check_in.replace(tzinfo=None)).total_seconds()
        if duration < 60:
            
            record.check_out = None # Reset lại
            raise ValidationError("Thao tác quá nhanh. Vui lòng đợi ít nhất 1 phút sau khi check-in.")
        # Tính giờ làm việc
        # Logic: Nếu vào trễ (>8:10), giờ bắt đầu tính là 09:00
        start_dt = record.check_in.replace(tzinfo=None)
        if start_dt.hour > 8 or (start_dt.hour == 8 and start_dt.minute > 10):
            start_dt = start_dt.replace(hour=9, minute=0, second=0)
        elif start_dt.hour < 8:
            start_dt = start_dt.replace(hour=8, minute=0, second=0)

        delta = now_dt.replace(tzinfo=None) - start_dt.replace(tzinfo=None)
        total_seconds = delta.total_seconds()

        # ===== TRỪ THỜI GIAN NGHỈ TRƯA CHUẨN =====
        lunch_start = start_dt.replace(hour=12, minute=0, second=0, microsecond=0)
        lunch_end = start_dt.replace(hour=13, minute=0, second=0, microsecond=0)

        overlap_start = max(start_dt, lunch_start)
        overlap_end = min(now_dt, lunch_end)

        lunch_seconds = 0
        if overlap_end > overlap_start:
            lunch_seconds = (overlap_end - overlap_start).total_seconds()

        # ===== GIỜ CÔNG THỰC =====
        hours = (total_seconds - lunch_seconds) / 3600

        record.working_hours = max(0, round(hours, 2))

        record.working_hours = max(0, round(hours, 2))
        db.session.commit()

        return {"message": f"Check-out thành công. Tổng công: {record.working_hours}h"}

    # ==============================
    # GET TODAY
    # ==============================
    @staticmethod
    def get_today(employee_id: int, sim_time_str=None):
        if sim_time_str:
            now_dt = datetime.fromisoformat(sim_time_str.replace("Z", "+00:00")).replace(tzinfo=None)
            today = now_dt.date()
        else:
            raise ValidationError("Thiếu simulated_now")

        return Attendance.query.filter_by(
            employee_id=employee_id,
            date=today
        ).first()

    # ==============================
    # HISTORY
    # ==============================
    @staticmethod
    def get_history(employee_id: int, sim_time_str=None, limit=10):
        if not sim_time_str:
            raise ValidationError("Thiếu simulated_now")

        now_dt = datetime.fromisoformat(sim_time_str.replace("Z", "+00:00")).replace(tzinfo=None)

        return Attendance.query.filter(
            Attendance.employee_id == employee_id,
            Attendance.date <= now_dt.date()
        ).order_by(Attendance.date.desc()).limit(limit).all()
    @staticmethod
    def recalculate_hours(check_in, check_out):
        start_dt = check_in

        if start_dt.hour > 8 or (start_dt.hour == 8 and start_dt.minute > 10):
            start_dt = start_dt.replace(hour=9, minute=0, second=0)
        elif start_dt.hour < 8:
            start_dt = start_dt.replace(hour=8, minute=0, second=0)

        delta = check_out.replace(tzinfo=None) - start_dt.replace(tzinfo=None)
        total_seconds = delta.total_seconds()

        lunch_start = start_dt.replace(hour=12, minute=0, second=0)
        lunch_end = start_dt.replace(hour=13, minute=0, second=0)

        overlap_start = max(start_dt, lunch_start)
        overlap_end = min(check_out, lunch_end)

        lunch_seconds = 0
        if overlap_end > overlap_start:
            lunch_seconds = (overlap_end - overlap_start).total_seconds()

        return round((total_seconds - lunch_seconds) / 3600, 2)
    
    @staticmethod
    def delete_attendance(employee_id, target_date_str):
        target_date = datetime.fromisoformat(target_date_str).date()
        
        # Lấy bản ghi mới nhất của user
        latest = Attendance.query.filter_by(employee_id=employee_id)\
            .order_by(Attendance.date.desc()).first()
            
        if not latest or latest.date != target_date:
            raise ValidationError("Chỉ được xóa bản ghi của ngày mới nhất để đảm bảo tính liên tục.")
            
        db.session.delete(latest)
        db.session.commit()
        
        # Tìm ngày mới nhất còn lại để FE rollback
        remaining = Attendance.query.filter_by(employee_id=employee_id)\
            .order_by(Attendance.date.desc()).first()
        return remaining.date if remaining else None