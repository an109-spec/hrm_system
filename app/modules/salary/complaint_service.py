from datetime import datetime
from app.extensions.db import db

from app.models.complaint import Complaint
from app.models.salary import Salary
from app.models.notification import Notification


class SalaryComplaintService:

    # =========================
    # CREATE COMPLAINT
    # =========================
    @staticmethod
    def create(employee_id: int, salary_id: int,
               type: str, description: str, evidence_url: str = None):

        salary = Salary.query.get(salary_id)

        if not salary:
            raise ValueError("Salary not found")

        complaint = Complaint(
            employee_id=employee_id,
            salary_id=salary_id,
            type=type,
            title="Khiếu nại phiếu lương",
            description=description,
            status="pending"
        )

        db.session.add(complaint)

        # notify HR/Admin
        db.session.add(Notification(
            title="Khiếu nại phiếu lương mới",
            content=f"Employee {employee_id} gửi khiếu nại lương",
            user_id=salary.employee.user_id,
            type="salary"
        ))

        db.session.commit()

        return complaint

    # =========================
    # LIST COMPLAINTS
    # =========================
    @staticmethod
    def get_by_employee(employee_id: int):
        return (
            Complaint.query
            .filter_by(employee_id=employee_id, type="salary")
            .order_by(Complaint.created_at.desc())
            .all()
        )

    # =========================
    # UPDATE STATUS (HR)
    # =========================
    @staticmethod
    def update_status(complaint_id: int, status: str):
        complaint = Complaint.query.get(complaint_id)

        if not complaint:
            raise ValueError("Complaint not found")

        complaint.status = status

        if status == "resolved":
            complaint.resolved_at = datetime.utcnow()

        db.session.commit()
        return complaint