from datetime import date
from operator import or_
from app.extensions.db import db
from app.models.employee import Employee
from app.models.attendance import Attendance


class AttendanceJob:

    @staticmethod
    def run_daily():
        """
        Chốt công tự động cuối ngày
        """
        today = date.today()

        employees = Employee.query.filter(
            Employee.is_deleted.is_(False),
            or_(
                Employee.is_attendance_required.is_(True),
                Employee.is_attendance_required.is_(None),
            ),
        ).all()

        for emp in employees:
            attendance = Attendance.query.filter_by(
                employee_id=emp.id,
                date=today
            ).first()

            # nếu chưa check-in -> tạo ABSENT
            if not attendance:
                attendance = Attendance(
                    employee_id=emp.id,
                    date=today,
                    working_hours=0,
                    status_id=None
                )
                db.session.add(attendance)

        db.session.commit()