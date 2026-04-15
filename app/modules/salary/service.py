from app.models.salary import Salary
from app.models.contract import Contract
from app.models.attendance import Attendance
from app.models.allowance import EmployeeAllowance
from app.models.employee import Employee


class SalaryService:

    # =========================
    # LIST SALARY (UI TABLE)
    # =========================
    @staticmethod
    def get_by_employee(employee_id: int, year: int):
        return (
            Salary.query
            .filter_by(employee_id=employee_id, year=year)
            .order_by(Salary.month.asc())
            .all()
        )

    # =========================
    # GET DETAIL PAYSLIP
    # =========================
    @staticmethod
    def get_detail(salary_id: int):
        return Salary.query.get(salary_id)

    # =========================
    # CALCULATE (CORE LOGIC)
    # =========================
    @staticmethod
    def calculate_salary(employee_id: int, month: int, year: int):
        """
        Core formula:
        (basic_salary / standard_days * actual_days)
        + allowances + bonus - penalty
        """

        contract = Contract.query.filter_by(employee_id=employee_id).first()
        salary = Salary.query.filter_by(
            employee_id=employee_id,
            month=month,
            year=year
        ).first()

        if not salary or not contract:
            return None

        base = salary.basic_salary

        # allowance
        allowances = sum(
            a.final_amount for a in salary.employee.allowances
        ) if salary.employee else 0

        actual = (base / salary.standard_work_days) * salary.total_work_days

        salary.net_salary = actual + allowances + salary.bonus - salary.penalty

        return salary

    # =========================
    # UPDATE AFTER ATTENDANCE
    # =========================
    @staticmethod
    def update_working_days(employee_id: int, month: int, year: int, days: float):
        salary = Salary.query.filter_by(
            employee_id=employee_id,
            month=month,
            year=year
        ).first()

        if salary:
            salary.total_work_days = days