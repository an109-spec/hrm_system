# app/modules/dashboard/dto.py

class OverviewDTO:
    @staticmethod
    def to_dict(total_emp, working, on_leave, resigned, total_departments):
        return {
            "total_employees": total_emp,
            "working": working,
            "on_leave": on_leave,
            "resigned": resigned,
            "total_departments": total_departments
        }


class AttendanceTodayDTO:
    @staticmethod
    def to_dict(present, late, absent):
        return {
            "present": present,
            "late": late,
            "absent": absent
        }


class SalarySummaryDTO:
    @staticmethod
    def to_dict(total, paid, pending):
        return {
            "total_salary": float(total),
            "paid": float(paid),
            "pending": float(pending)
        }


class DepartmentDTO:
    @staticmethod
    def to_dict(departments):
        return departments


class ComplaintDTO:
    @staticmethod
    def to_dict(c):
        return {
            "id": c.id,
            "title": c.title,
            "status": c.status,
            "priority": c.priority,
            "created_at": c.created_at.isoformat()
        }


class NotificationDTO:
    @staticmethod
    def to_dict(n):
        return {
            "id": n.id,
            "title": n.title,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat()
        }