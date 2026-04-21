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
        if sim_time_str:
            now_dt = datetime.fromisoformat(sim_time_str.replace("Z", "+00:00"))
        else:
            now_dt = datetime.now()

        today = now_dt.date()

        record = Attendance.query.filter_by(employee_id=employee_id, date=today).first()

        if not record:
            check_in_time = now_dt.time()
            
            # Tạo mốc giờ chuẩn 08:00:00 của ngày hôm nay để so sánh
            standard_time_dt = now_dt.replace(hour=8, minute=0, second=0, microsecond=0)
            
            # Tính số phút chênh lệch so với 08:00
            # Nếu check-in trước 8h, diff sẽ âm hoặc bằng 0
            diff = now_dt - standard_time_dt
            minutes_diff = int(diff.total_seconds() / 60)
            
            # Quyết định trạng thái: Chỉ coi là LATE nếu muộn hơn 10 phút (tức là từ 08:11 trở đi)
            is_late = minutes_diff > 10
            
            status_name = "LATE" if is_late else "PRESENT"
            status = AttendanceStatus.query.filter_by(status_name=status_name).first()

            record = Attendance(
                employee_id=employee_id,
                date=today,
                check_in=now_dt, 
                status_id=status.id if status else None,
                working_hours=0 # Mới vào làm chưa có giờ công
            )
            
            db.session.add(record)
            db.session.commit()
            
            # Trả về thông báo chi tiết cho Frontend alert
            if is_late:
                msg = f"Check-in: {check_in_time.strftime('%H:%M')}. Bạn đi muộn {minutes_diff} phút. Thời gian tính công sẽ bắt đầu từ 09:00."
            else:
                if minutes_diff > 0:
                    msg = f"Check-in: {check_in_time.strftime('%H:%M')}. Bạn muộn {minutes_diff} phút (Trong mức cho phép). Chúc bạn làm việc hiệu quả!"
                else:
                    msg = f"Check-in: {check_in_time.strftime('%H:%M')}. Bạn đến rất đúng giờ. Chúc bạn làm việc hiệu quả!"
                
            return {"message": msg}

        # CHECK OUT
        if record.check_out:
            raise ValidationError("Bạn đã hoàn thành ca hôm nay")

        record.check_out = now_dt

        # Tính giờ làm việc
        # Logic: Nếu vào trễ (>8:10), giờ bắt đầu tính là 09:00
        start_dt = record.check_in
        if start_dt.hour > 8 or (start_dt.hour == 8 and start_dt.minute > 10):
            start_dt = start_dt.replace(hour=9, minute=0, second=0)
        elif start_dt.hour < 8:
            start_dt = start_dt.replace(hour=8, minute=0, second=0)

        delta = now_dt - start_dt
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
            now_dt = datetime.fromisoformat(sim_time_str.replace("Z", "+00:00"))
            today = now_dt.date()
        else:
            today = date.today()

        return Attendance.query.filter_by(
            employee_id=employee_id,
            date=today
        ).first()

    # ==============================
    # HISTORY
    # ==============================
    @staticmethod
    def get_history(employee_id: int, limit=10):
        return Attendance.query.filter_by(
            employee_id=employee_id
        ).order_by(Attendance.date.desc()).limit(limit).all()
    @staticmethod
    def recalculate_hours(check_in, check_out):
        start_dt = check_in

        if start_dt.hour > 8 or (start_dt.hour == 8 and start_dt.minute > 10):
            start_dt = start_dt.replace(hour=9, minute=0, second=0)
        elif start_dt.hour < 8:
            start_dt = start_dt.replace(hour=8, minute=0, second=0)

        delta = check_out - start_dt
        total_seconds = delta.total_seconds()

        lunch_start = start_dt.replace(hour=12, minute=0, second=0)
        lunch_end = start_dt.replace(hour=13, minute=0, second=0)

        overlap_start = max(start_dt, lunch_start)
        overlap_end = min(check_out, lunch_end)

        lunch_seconds = 0
        if overlap_end > overlap_start:
            lunch_seconds = (overlap_end - overlap_start).total_seconds()

        return round((total_seconds - lunch_seconds) / 3600, 2)