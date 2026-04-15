from datetime import datetime, date
from sqlalchemy import and_

from app.extensions import db
from app.models import Attendance, AttendanceStatus
from app.common.exceptions import ValidationError


class AttendanceService:

    # ==============================
    # CHECK IN / OUT
    # ==============================
    @staticmethod
    def check_in_out(employee_id: int):
        today = date.today()
        now = datetime.now()

        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=today
        ).first()

        # ======================
        # CHECK IN
        # ======================
        if not record:
            status = AttendanceStatus.query.filter_by(status_name="PRESENT").first()

            record = Attendance(
                employee_id=employee_id,
                date=today,
                check_in=now.time(),
                status_id=status.id if status else None
            )

            db.session.add(record)
            db.session.commit()
            return {"message": "Check-in thành công"}

        # ======================
        # CHECK OUT
        # ======================
        if record.check_out:
            raise ValidationError("Bạn đã check-out rồi")

        record.check_out = now.time()

        # tính giờ làm
        if record.check_in:
            delta = datetime.combine(today, record.check_out) - datetime.combine(today, record.check_in)
            record.working_hours = round(delta.total_seconds() / 3600, 2)

        db.session.commit()

        return {"message": "Check-out thành công"}

    # ==============================
    # GET TODAY
    # ==============================
    @staticmethod
    def get_today(employee_id: int):
        return Attendance.query.filter_by(
            employee_id=employee_id,
            date=date.today()
        ).first()

    # ==============================
    # HISTORY
    # ==============================
    @staticmethod
    def get_history(employee_id: int, limit=10):
        return Attendance.query.filter_by(
            employee_id=employee_id
        ).order_by(Attendance.date.desc()).limit(limit).all()