# app/modules/dashboard/service.py

from sqlalchemy import func
from datetime import date, datetime, timedelta, timezone

from app.extensions.db import db
from app.models.employee import Employee
from app.models.department import Department
from app.models.attendance import Attendance
from app.models.salary import Salary
from app.models.complaint import Complaint
from app.models.notification import Notification

from .dto import (
    OverviewDTO,
    AttendanceTodayDTO,
    SalarySummaryDTO,
    DepartmentDTO,
    ComplaintDTO,
    NotificationDTO
)
from app.models.leave import LeaveRequest

class DashboardService:

    # =========================
    # OVERVIEW
    # =========================
    @staticmethod
    def get_overview():
        total_emp = db.session.query(func.count(Employee.id)).scalar()

        working = db.session.query(func.count(Employee.id)).filter_by(working_status='working').scalar()
        on_leave = db.session.query(func.count(Employee.id)).filter_by(working_status='on_leave').scalar()
        resigned = db.session.query(func.count(Employee.id)).filter_by(working_status='resigned').scalar()

        total_departments = db.session.query(func.count(Department.id)).scalar()

        return OverviewDTO.to_dict(
            total_emp, working, on_leave, resigned, total_departments
        )

    # =========================
    # ATTENDANCE TODAY
    # =========================
    @staticmethod
    def get_today_attendance():
        today = date.today()

        present = db.session.query(func.count(Attendance.id)) \
            .join(Attendance.status) \
            .filter(Attendance.date == today, 
                    Attendance.status.has(status_name='PRESENT')).scalar()

        late = db.session.query(func.count(Attendance.id)) \
            .join(Attendance.status) \
            .filter(Attendance.date == today,
                    Attendance.status.has(status_name='LATE')).scalar()

        absent = db.session.query(func.count(Attendance.id)) \
            .join(Attendance.status) \
            .filter(Attendance.date == today,
                    Attendance.status.has(status_name='ABSENT')).scalar()

        return AttendanceTodayDTO.to_dict(present, late, absent)

    # =========================
    # SALARY
    # =========================
    @staticmethod
    def get_salary_summary(month, year):
        total = db.session.query(func.sum(Salary.net_salary)) \
            .filter_by(month=month, year=year).scalar() or 0

        paid = db.session.query(func.sum(Salary.net_salary)) \
            .filter_by(month=month, year=year, status='paid').scalar() or 0

        pending = total - paid

        return SalarySummaryDTO.to_dict(total, paid, pending)

    # =========================
    # DEPARTMENT
    # =========================
    @staticmethod
    def get_department_stats():
        departments = db.session.query(
            Department.name,
            func.count(Employee.id)
        ).join(Employee, Employee.department_id == Department.id) \
         .group_by(Department.name).all()

        result = [
            {
                "department": d[0],
                "total_employee": d[1]
            }
            for d in departments
        ]

        return DepartmentDTO.to_dict(result)

    # =========================
    # COMPLAINT
    # =========================
    @staticmethod
    def get_recent_complaints(limit):
        complaints = Complaint.query.order_by(
            Complaint.created_at.desc()
        ).limit(limit).all()

        return [ComplaintDTO.to_dict(c) for c in complaints]

    # =========================
    # NOTIFICATION
    # =========================
    @staticmethod
    def get_notifications(user_id):
        notis = Notification.query.filter_by(user_id=user_id) \
            .order_by(Notification.created_at.desc()) \
            .limit(10).all()

        return [NotificationDTO.to_dict(n) for n in notis]

    # =========================
    # CHART
    # =========================
    @staticmethod
    def get_attendance_chart():
        today = date.today()
        last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]

        data = []

        for d in last_7_days:
            count = db.session.query(func.count(Attendance.id)) \
                .filter(Attendance.date == d).scalar()

            data.append({
                "date": d.isoformat(),
                "count": count
            })

        return data
    
    @staticmethod
    def get_employee_dashboard_data(employee_id):
        from datetime import datetime
        from app.models.leave_usage import LeaveUsage # Giả định model quản lý ngày phép
        
        today = date.today()
        
        # 1. Lấy thông tin Employee & Position
        emp = Employee.query.get(employee_id)
        
        # 2. Lấy chấm công hôm nay
        attendance = Attendance.query.filter_by(employee_id=employee_id, date=today).first()
        
        # 3. Lấy số ngày phép (Giả định logic: Tổng 12 - Đã dùng)
        # Nếu bạn có model LeaveBalance riêng thì query từ đó
        used_leave = db.session.query(func.sum(LeaveUsage.days_count))\
            .filter_by(employee_id=employee_id, status='approved').scalar() or 0
        leave_balance = {
            "remaining_days": 12 - used_leave,
            "total_days": 12
        }

        # 4. Lấy lương tháng gần nhất (đã thanh toán)
        latest_salary = Salary.query.filter_by(employee_id=employee_id, status='paid')\
            .order_by(Salary.year.desc(), Salary.month.desc()).first()

        # 5. Lấy 5 thông báo mới nhất
        notifications = Notification.query.filter_by(user_id=emp.user_id)\
            .order_by(Notification.created_at.desc()).limit(5).all()

        return {
            "employee": emp,
            "attendance": attendance,
            "leave_balance": leave_balance,
            "latest_salary": latest_salary,
            "notifications": notifications,
            "now": datetime.now()
        }
    @staticmethod
    def get_employee_dashboard_batch(user_id):
        emp = Employee.query.filter_by(user_id=user_id).first()
        if not emp: return None

        today = date.today()
        # 1. Chấm công
        attendance = Attendance.query.filter_by(employee_id=emp.id, date=today).first()
        
        # 2. Ngày phép: Tổng 12 - (to_date - from_date + 1)
        used_days = db.session.query(
            func.sum(func.datediff(LeaveRequest.to_date, LeaveRequest.from_date) + 1)
        ).filter(LeaveRequest.employee_id == emp.id, LeaveRequest.status == 'approved').scalar() or 0
        
        # 3. Lương mới nhất
        salary = Salary.query.filter_by(employee_id=emp.id, status='paid')\
            .order_by(Salary.year.desc(), Salary.month.desc()).first()

        # 4. Thông báo (Lấy 5 mục như ảnh 2)
        notifications = Notification.query.filter_by(user_id=user_id)\
            .order_by(Notification.created_at.desc()).limit(5).all()

        return {
            "employee": emp,
            "attendance": attendance,
            "leave_balance": {"remaining": 12 - int(used_days), "total": 12},
            "latest_salary": salary,
            "notifications": notifications,
            "now": datetime.now(timezone.utc) 
        }