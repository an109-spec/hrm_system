
from decimal import Decimal, ROUND_HALF_UP
from operator import or_

from sqlalchemy import and_, asc, desc, or_
from sqlalchemy.orm import joinedload
from app.constants.attendance import AttendanceConstants, WorkConfig, AttendanceStatus
from app.constants.payroll import ConfigLockStatus, SalaryComplaintStatus, SalarySettings, SalaryStatus, PayrollConfig
from app.extensions.db import db
from app.constants.common import RoleName
from app.models.allowance import EmployeeAllowance
from app.models.complaint import Complaint
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.notification import Notification
from app.models.role import Role
from app.models.salary import Salary
from app.models.contract import Contract
from app.models.history import HistoryLog
from app.constants.contract import ContractStatus
from app.models.user import User
from app.modules.payroll.admin_service import PayrollPolicyService
from app.utils.date_utils import get_month_range
from app.utils.time import _normalize, get_current_time
from .base_service import PersonalPayrollService
from .tax_rules import TaxRules

class HR_payroll_service(PersonalPayrollService):
    tax_by_bracket = staticmethod(TaxRules.tax_by_bracket)

    @staticmethod
    def sum_allowance(employee_id: int) -> dict:
        rows = EmployeeAllowance.query.filter_by(employee_id=employee_id, status=True, is_deleted=False).all()
        policy = PayrollPolicyService.get_policy().get("tax_free_allowances", {})
        
        # This maps a keyword in the allowance name (e.g., "ăn trưa") to the key in the policy dict (e.g., "meal_allowance")
        LIMIT_POLICY_KEYS = {
            "meal": "meal_allowance",
            "trưa": "meal_allowance",
            "fuel": "fuel_allowance",
            "xăng": "fuel_allowance",
            "responsibility": "responsibility_allowance",
            "trách nhiệm": "responsibility_allowance",
        }
        
        totals = {"total": Decimal("0"), "taxable": Decimal("0"), "tax_free": Decimal("0")}
        for row in rows:
            amount = Decimal(str(row.final_amount or 0))
            totals["total"] += amount
            
            # If the allowance type is fundamentally taxable, add it all to taxable amount.
            if row.allowance_type.is_taxable:
                totals["taxable"] += amount
                continue

            # For non-taxable types, check if they exceed the policy limit.
            limit = Decimal("0")
            name_lower = row.allowance_type.name.lower()
            for keyword, policy_key in LIMIT_POLICY_KEYS.items():
                if keyword in name_lower:
                    # Get the limit *only* from the policy, default to 0 if not found.
                    limit = Decimal(str(policy.get(policy_key, 0)))
                    break
            
            if limit > 0 and amount > limit:
                # If amount exceeds limit, the excess is taxable.
                totals["taxable"] += (amount - limit)
                totals["tax_free"] += limit
            else:
                # Otherwise, the entire amount is tax-free.
                totals["tax_free"] += amount
        return totals

    @staticmethod
    def calculate_insurance(base_salary_for_ins: Decimal, policy: dict = None) -> dict:
        if policy is None:
            policy = PayrollConfig.get_default()
        ins_config = policy.get("insurance", {})
        salary_base = base_salary_for_ins 
        social_percent = Decimal(str(ins_config.get("social_percent", 0)))
        health_percent = Decimal(str(ins_config.get("health_percent", 0)))
        unemp_percent = Decimal(str(ins_config.get("unemployment_percent", 0)))
        social_ins = salary_base * (social_percent / Decimal("100"))
        health_ins = salary_base * (health_percent / Decimal("100"))
        unemp_ins = salary_base * (unemp_percent / Decimal("100"))
        return {
            "social": social_ins.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            "health": health_ins.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            "unemployment": unemp_ins.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            "total": (social_ins + health_ins + unemp_ins).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        }

    @staticmethod
    def calculate_attendance_penalty(employee_id: int, month: int, year: int, base_salary: Decimal, standard_days: int, policy: dict) -> dict:
        rules = policy.get("late_penalty_rules", [])
        if not rules:
            return {"total": Decimal("0"), "details": []}

        start_date, end_date = get_month_range(month, year)
        attendances = Attendance.query.filter(
            Attendance.employee_id == employee_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date,
            Attendance.late_minutes > 0,
            Attendance.is_deleted.is_(False)
        ).all()

        total_penalty = Decimal("0")
        details = []
        
        # Sắp xếp rules để đảm bảo duyệt từ lỗi nặng nhất đến nhẹ nhất
        sorted_rules = sorted(rules, key=lambda x: x.get("min", 0), reverse=True)

        for att in attendances:
            matched_rule = None
            for rule in sorted_rules:
                if att.late_minutes >= rule["min"]:
                    matched_rule = rule
                    break
            
            if not matched_rule:
                continue

            penalty_amount = Decimal("0")
            if matched_rule.get("type") == "half_day":
                if standard_days > 0:
                    penalty_amount = (base_salary / Decimal(str(standard_days))) * Decimal("0.5")
            else:
                penalty_amount = Decimal(str(matched_rule.get("penalty", 0)))

            total_penalty += penalty_amount

            if penalty_amount > 0:
                details.append({
                    "date": str(att.date),
                    "late_minutes": att.late_minutes,
                    "amount": float(penalty_amount),
                    "reason": matched_rule.get("label", "Phạt đi muộn")
                })
        return {"total": total_penalty.quantize(Decimal("1"), rounding=ROUND_HALF_UP), "details": details}
    
    @staticmethod
    def get_total_dependent_deduction(employee_id: int) -> Decimal:
        policy = PayrollPolicyService.get_policy()
        deduction_per_person = Decimal(str(policy.get("deduction", {}).get("dependent_per_person", 4400000)))
        count = PayrollPolicyService._dependent_count(employee_id)
        return deduction_per_person * Decimal(str(count))

    @staticmethod
    def _compute_salary_employee(employee: Employee, month: int, year: int) -> tuple[Salary, dict]:
        policy   = PayrollPolicyService.get_policy()
        brackets = policy.get("tax_brackets", [])
        contract = (
            Contract.query.filter(
                Contract.employee_id == employee.id,
                Contract.status == ContractStatus.ACTIVE
            )
            .order_by(Contract.start_date.desc(), Contract.id.desc())
            .first()
        )
        if not contract:
            raise ValueError(f"{employee.full_name} không có hợp đồng đang hiệu lực (active)")

        # ------------------------------------------------------------------ #
        # 2. Số giờ làm việc trong tháng                                      #
        #    _attendance_metrics trả về:                                      #
        #      regular_hours = work_days × 8  (chưa nhân hệ số gì)           #
        #      ot_hours      = giờ OT đã nhân hệ số (after_shift/weekend/holiday) #
        # ------------------------------------------------------------------ #
        metrics     = HR_payroll_service._attendance_metrics([employee.id], month, year)
        emp_metrics = metrics.get(employee.id, {"regular_hours": 0.0, "ot_hours": 0.0})

        regular_hours = Decimal(str(emp_metrics["regular_hours"]))  # vd: 22 ngày × 8 = 176h
        ot_hours      = Decimal(str(emp_metrics["ot_hours"]))       # vd: 4h × 1.5 = 6h quy đổi

        default_rate = Decimal("50000")
    
        position_config = PayrollPolicyService.get_salary_config_for_position(employee.position_id)
        
        # Lấy 'hourly_rate' từ dict config, nếu không có thì lấy giá trị mặc định
        raw_rate = position_config.get("hourly_rate", str(default_rate))
        hourly_rate = Decimal(str(raw_rate))

        # Gross = (giờ thường + giờ OT quy đổi) × đơn giá giờ
        gross_regular = regular_hours * hourly_rate
        gross_ot      = ot_hours      * hourly_rate   # ot_hours đã × hệ số, chỉ × đơn giá
        gross_salary  = gross_regular + gross_ot

        # ------------------------------------------------------------------ #
        # 3. Phụ cấp                                                          #
        # ------------------------------------------------------------------ #
        allowance_info   = HR_payroll_service.sum_allowance(employee.id)
        total_allowance  = allowance_info["total"]
        taxable_allowance  = allowance_info["taxable"]
        tax_free_allowance = allowance_info["tax_free"]

        # ------------------------------------------------------------------ #
        # 4. Bảo hiểm — tính trên lương hợp đồng (base_salary trong contract) #
        #    Fallback về gross nếu contract không có base_salary              #
        # ------------------------------------------------------------------ #
        base_salary_for_ins = HR_payroll_service._decimal(contract.base_salary) or gross_salary
        insurance           = HR_payroll_service.calculate_insurance(base_salary_for_ins, policy)
        total_insurance     = insurance["total"]

        # ------------------------------------------------------------------ #
        # 5. Phạt đi muộn / về sớm                                           #
        #    standard_days lấy từ WorkConfig để nhất quán với hệ thống       #
        # ------------------------------------------------------------------ #
        standard_days = policy.get("standard_work_days", WorkConfig.STANDARD_WORKING_DAYS)
        penalty_info  = HR_payroll_service.calculate_attendance_penalty(
            employee.id, month, year, gross_salary, standard_days, policy
        )
        total_penalty = penalty_info["total"]

        # ------------------------------------------------------------------ #
        # 6. Giảm trừ thuế TNCN                                              #
        # ------------------------------------------------------------------ #
        personal_deduction  = Decimal(str(
            policy.get("deduction", {}).get("personal", 11_000_000)
        ))
        dependent_deduction = HR_payroll_service.get_total_dependent_deduction(employee.id)

        # Thu nhập tính thuế = gross + phụ cấp chịu thuế - BH - giảm trừ cá nhân - giảm trừ phụ thuộc
        taxable_income = (
            gross_salary
            + taxable_allowance
            - total_insurance
            - personal_deduction
            - dependent_deduction
        )
        taxable_income = max(Decimal("0"), taxable_income)

        # ------------------------------------------------------------------ #
        # 7. Thuế TNCN (lũy tiến từng phần)                                  #
        # ------------------------------------------------------------------ #
        pit_tax = HR_payroll_service.tax_by_bracket(taxable_income, brackets)

        # ------------------------------------------------------------------ #
        # 8. Thực nhận                                                        #
        # ------------------------------------------------------------------ #
        net_salary = gross_salary + total_allowance - total_insurance - pit_tax - total_penalty
        salary_record = Salary(
            employee_id          = employee.id,
            month                = month,
            year                 = year,
            gross_salary         = gross_salary.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            total_allowance      = total_allowance.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            taxable_allowance    = taxable_allowance.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            tax_free_allowance   = tax_free_allowance.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            insurance_employee   = total_insurance.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            personal_deduction   = personal_deduction.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            dependent_deduction  = dependent_deduction.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            taxable_income       = taxable_income.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            pit_tax              = pit_tax,
            attendance_penalty   = total_penalty.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            net_salary           = net_salary.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
        )

        # ------------------------------------------------------------------ #
        # 10. Breakdown chi tiết (log / hiển thị phiếu lương)                #
        # ------------------------------------------------------------------ #
        breakdown = {
            "employee_id":   employee.id,
            "full_name":     employee.full_name,
            "month":         month,
            "year":          year,
            # --- Giờ công ---
            "hourly_rate":   float(hourly_rate),
            "regular_hours": float(regular_hours),   # giờ hành chính thực tế
            "ot_hours_weighted": float(ot_hours),    # giờ OT đã quy đổi hệ số
            # --- Lương gộp ---
            "gross_regular": float(gross_regular),
            "gross_ot":      float(gross_ot),
            "gross_salary":  float(gross_salary),
            # --- Phụ cấp ---
            "allowance": {
                "total":     float(total_allowance),
                "taxable":   float(taxable_allowance),
                "tax_free":  float(tax_free_allowance),
            },
            # --- Bảo hiểm ---
            "insurance": {
                "base":         float(base_salary_for_ins),
                "social":       float(insurance["social"]),
                "health":       float(insurance["health"]),
                "unemployment": float(insurance["unemployment"]),
                "total":        float(total_insurance),
            },
            # --- Giảm trừ thuế ---
            "deductions": {
                "personal":  float(personal_deduction),
                "dependent": float(dependent_deduction),
            },
            "taxable_income": float(taxable_income),
            "pit_tax":        float(pit_tax),
            # --- Phạt ---
            "attendance_penalty": {
                "total":   float(total_penalty),
                "details": penalty_info["details"],
            },
            # --- Thực nhận ---
            "net_salary": float(net_salary),
        }

        return salary_record, breakdown
    
    @staticmethod
    def _compute_salary(employee: Employee, month: int, year: int) -> tuple[Salary, dict]:
        policy = PayrollPolicyService.get_policy()
        brackets = policy.get("tax_brackets", [])

        # Xác định role và lương cơ bản
        role_name = employee.user.role.name if (employee.user and employee.user.role) else None
        base_salary = SalarySettings.BASE_SALARY_BY_ROLE.get(role_name)
        if base_salary is None:
            raise ValueError(
                f"{employee.full_name} có role '{role_name}' không có mức lương cố định được cấu hình"
            )

        # Phụ cấp
        allowance_info = HR_payroll_service.sum_allowance(employee.id)
        total_allowance = allowance_info["total"]
        taxable_allowance = allowance_info["taxable"]
        tax_free_allowance = allowance_info["tax_free"]

        # Bảo hiểm (tính trên lương cơ bản)
        insurance = HR_payroll_service.calculate_insurance(base_salary, policy)
        total_insurance = insurance["total"]

        # Giảm trừ
        personal_deduction = Decimal(str(policy.get("deduction", {}).get("personal", 11000000)))
        dependent_deduction = HR_payroll_service.get_total_dependent_deduction(employee.id)

        # Thu nhập tính thuế
        taxable_income = (
            base_salary + taxable_allowance
            - total_insurance
            - personal_deduction
            - dependent_deduction
        )
        taxable_income = max(Decimal("0"), taxable_income)
        # Thuế TNCN
        pit_tax = HR_payroll_service.tax_by_bracket(taxable_income, brackets)
        # Thực nhận (không trừ phạt vì không chấm công)
        net_salary = base_salary + total_allowance - total_insurance - pit_tax
        # Ghi nhận bản ghi Salary
        salary_record = Salary(
            employee_id=employee.id,
            month=month,
            year=year,
            gross_salary=base_salary.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            total_allowance=total_allowance.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            taxable_allowance=taxable_allowance.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            tax_free_allowance=tax_free_allowance.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            insurance_employee=total_insurance.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            personal_deduction=personal_deduction.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            dependent_deduction=dependent_deduction.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            taxable_income=taxable_income.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            pit_tax=pit_tax,
            attendance_penalty=Decimal("0"),
            net_salary=net_salary.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
        )
        breakdown = {
            "employee_id": employee.id,
            "full_name": employee.full_name,
            "role": role_name,
            "month": month,
            "year": year,
            "base_salary": float(base_salary),
            "allowance": {
                "total": float(total_allowance),
                "taxable": float(taxable_allowance),
                "tax_free": float(tax_free_allowance),
            },
            "insurance": {
                "social": float(insurance["social"]),
                "health": float(insurance["health"]),
                "unemployment": float(insurance["unemployment"]),
                "total": float(total_insurance),
            },
            "deductions": {
                "personal": float(personal_deduction),
                "dependent": float(dependent_deduction),
            },
            "taxable_income": float(taxable_income),
            "pit_tax": float(pit_tax),
            "attendance_penalty": None,  # Không áp dụng
            "net_salary": float(net_salary),
        }
        return salary_record, breakdown

    @staticmethod
    def calculate_monthly_payroll(
        month: int,
        year: int,
        department_id: int | None = None,
        actor_user_id: int | None = None
    ) -> dict:
        # Giả sử bạn có hàm kiểm tra trạng thái khóa từ PayrollPolicyService
        # Nếu đang khóa, không cho phép tính lương mới
        current_lock_status = PayrollPolicyService.get_setting_value("config_edit_locked",ConfigLockStatus.UNLOCKED)
        if current_lock_status == ConfigLockStatus.LOCKED:
            raise ValueError("Hệ thống đang khóa cấu hình lương, không thể tính lương mới.")
        query = Employee.query.filter_by(is_deleted=False)
        if department_id:
            query = query.filter(Employee.department_id == department_id)
        employees = query.order_by(Employee.full_name.asc()).all()
        computed = []
        errors = []
        for employee in employees:
            try:
                role_name = (
                    employee.user.role.name
                    if (employee.user and employee.user.role)
                    else None
                )
                # Kiểm tra đã tính lương tháng này chưa
                existing = Salary.query.filter_by(
                    employee_id=employee.id,
                    month=month,
                    year=year,
                    is_deleted=False
                ).first()
                
                if existing:
                    errors.append({
                        "employee_id": employee.id,
                        "full_name": employee.full_name,
                        "reason": f"Đã tồn tại bản ghi lương tháng {month}/{year}",
                    })
                    continue
                # Tính lương
                if role_name == RoleName.EMPLOYEE:
                    salary, detail = HR_payroll_service._compute_salary_employee(
                        employee, month, year
                    )
                elif role_name in (RoleName.HR, RoleName.ADMIN, RoleName.MANAGER):
                    salary, detail = HR_payroll_service._compute_salary(
                        employee, month, year
                    )
                else:
                    errors.append({
                        "employee_id": employee.id,
                        "full_name": employee.full_name,
                        "reason": f"Role '{role_name}' không được hỗ trợ tính lương",
                    })
                    continue
                # 2. GÁN TRẠNG THÁI MẶC ĐỊNH LÀ DRAFT
                salary.status = SalaryStatus.DRAFT
                db.session.add(salary)
                db.session.flush()
                HR_payroll_service._append_audit_log(
                    salary=salary,
                    action="CALCULATE_PAYROLL",
                    description=f"Tính lương tháng {month}/{year} cho {employee.full_name} (Status: {SalaryStatus.DRAFT})",
                    user_id=actor_user_id,
                )
                computed.append({"employee_id": employee.id, **detail})
            except ValueError as e:
                errors.append({
                    "employee_id": employee.id,
                    "full_name": employee.full_name,
                    "reason": str(e),
                })
                continue

        db.session.commit()

        return {
            "processed": len(computed),
            "failed": len(errors),
            "items": computed,
            "errors": errors,
        }
    ################################################################################
    #Tính giờ, trạng thái chấm công, điều chỉnh check-in/out và lưu vết thay đổi.
    ################################################################################
    @staticmethod
    def _attendance_metrics(employee_ids: list, month: int, year: int) -> dict:
        HOURS_PER_DAY = 8

        regular_work_days = HR_payroll_service.get_department_regular_work_days(
            employee_ids, month, year
        )
        ot_stats = HR_payroll_service.get_department_overtime_stats(
            employee_ids, month, year
        )
        result = {}
        for emp_id in set(employee_ids):
            work_days = regular_work_days.get(emp_id, 0.0)
            result[emp_id] = {
                "regular_hours": work_days * HOURS_PER_DAY,  
                "ot_hours": ot_stats.get(emp_id, 0.0),
            }
        return result

    @staticmethod
    def _attendance_status_from_record(record: Attendance | None, has_leave: bool) -> str:
        # 1. Trạng thái nghỉ phép
        if has_leave:
            return AttendanceStatus.LEAVE

        # 2. Trạng thái vắng mặt
        if not record:
            return AttendanceStatus.ABSENT
        # 3. Xử lý các trạng thái chờ hoàn tất ca
        shift_status = record.normalized_shift_status
        pending_statuses = {
            AttendanceConstants.STATUS_REGULAR_DONE,
            AttendanceConstants.STATUS_PENDING_OT,
            AttendanceConstants.STATUS_PRE_OT_REST,
            AttendanceConstants.STATUS_OT_CHECKIN_REQ,
        }
        if shift_status in pending_statuses:
            return "ca_chinh_cho_hoan_tat" 
        # 4. Kiểm tra dữ liệu bất thường
        if not record.check_in or not record.check_out:
            return "abnormal" # Có thể cân nhắc thêm vào AttendanceStatus nếu cần

        # 5. Logic thời gian sử dụng WorkConfig
        # Lấy time object từ datetime để so sánh
        check_in_time = record.check_in.time()
        check_out_time = record.check_out.time()

        is_late = check_in_time > WorkConfig.WORKDAY_START
        is_early = check_out_time < WorkConfig.WORKDAY_END

        # 6. Xác định trạng thái cuối cùng
        # Kiểm tra OT
        if HR_payroll_service._decimal(record.overtime_hours) > 0:
            return "overtime"

        # Sử dụng AttendanceStatus.LATE nếu đi muộn hoặc về sớm
        if is_late or is_early:
            return AttendanceStatus.LATE

        # Mặc định là Có mặt (Present)
        return AttendanceStatus.PRESENT
    
    @staticmethod
    def _is_attendance_required(employee: Employee) -> bool:
        if not employee.user or not employee.user.role:
            return False
        return employee.user.role.name == RoleName.EMPLOYEE
    

    '''
    Bước 3: Sửa lỗi dữ liệu
    '''
    @staticmethod
    def resolve_attendance_complaint(
        attendance_id: int,
        check_in: str | None = None,
        check_out: str | None = None,
        attendance_type: str | None = None,
        shift_status: str | None = None,
        note: str = "",
        actor_user_id: int | None = None
    ) -> dict:
        record = Attendance.query.get(attendance_id)
        if not record:
            raise ValueError("Không tìm thấy bản ghi chấm công")
        before_snapshot = {
            "check_in": str(record.check_in),
            "check_out": str(record.check_out),
            "type": record.attendance_type,
            "status": record.shift_status
        }
        if check_in:
            record.check_in = _normalize(check_in)
        if check_out:
            record.check_out = _normalize(check_out)
        if record.check_in and record.check_out:
            if record.check_out < record.check_in:
                raise ValueError("Giờ check-out không được nhỏ hơn check-in")
            
            delta = record.check_out - record.check_in
            record.working_hours = Decimal(str(delta.total_seconds() / 3600)).quantize(Decimal("0.01"))
        if attendance_type:
            record.set_attendance_type(attendance_type)
        if shift_status:
            record.set_shift_status(shift_status)
        description = (
            f"HR điều chỉnh từ khiếu nại. "
            f"Trước: {before_snapshot}. "
            f"Sau: check_in={record.check_in}, check_out={record.check_out}, "
            f"type={record.attendance_type}, status={record.shift_status}. "
            f"Note: {note}"
        )
        HistoryLog.append(
            employee_id=record.employee_id,
            action="COMPLAINT_ADJUSTMENT",
            entity_type="attendance",
            entity_id=record.id,
            description=description,
            performed_by=actor_user_id
        )
        db.session.commit()
        return {"success": True, "attendance_id": record.id}
    
    '''
    Bước 1: HR truy cập danh sách để xem tổng quan các khiếu nại đang tồn tại
    '''
    @staticmethod
    def get_payroll_complaints(
        month: int | None = None, 
        year: int | None = None, 
        status: str | None = None
    ) -> list[dict]:
        query = Complaint.query.join(Employee, Complaint.employee_id == Employee.id).filter(
            or_(Complaint.salary_id.isnot(None), Complaint.type.ilike("%salary%"))
        )
        # 1. Lọc theo trạng thái (HR thường quan tâm đến IN_PROGRESS)
        if status:
            query = query.filter(Complaint.status == status)
        # 2. Lọc theo tháng/năm (nếu có)
        if month and year:
            query = query.join(Salary, Complaint.salary_id == Salary.id, isouter=True).filter(
                or_(Salary.id.is_(None), and_(Salary.month == month, Salary.year == year))
            )
        # 3. Lấy dữ liệu
        complaints = query.order_by(Complaint.created_at.desc()).limit(100).all()
        # 4. Trả về thông tin chi tiết cho HR
        return [
            {
                "id": item.id,
                "employee": item.employee.full_name if item.employee else "--",
                "title": item.title,
                "status": item.status,
                "admin_reply": item.admin_reply,  # Quan trọng: Lời nhắn của Manager
                "handled_by": item.handled_by,    # Quan trọng: Manager nào đã duyệt
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
            }
            for item in complaints
        ]
    '''
Bước 4: Giải quyết và Chốt sổ 
chuyển đổi trạng thái của một khiếu nại từ "Chờ xử lý" (pending) sang các trạng thái kết thúc
    '''
    @staticmethod
    def handle_complaint(
        complaint_id: int,
        action: str, 
        handler_employee_id: int | None = None,
        actor_user_id: int | None = None,
        message: str = "",
        payroll_status: str | None = None
    ) -> dict:
        complaint = Complaint.query.get(complaint_id)
        if not complaint:
            raise ValueError("Không tìm thấy khiếu nại")
        valid_actions = {SalaryComplaintStatus.IN_PROGRESS, SalaryComplaintStatus.RESOLVED, SalaryComplaintStatus.REJECTED}
        if action not in valid_actions:
            raise ValueError(f"Trạng thái không hợp lệ: {action}")
        complaint.status = action
        complaint.handled_by = handler_employee_id
        
        if action == SalaryComplaintStatus.RESOLVED:
            complaint.resolved_at = get_current_time()
        if action in {SalaryComplaintStatus.RESOLVED, SalaryComplaintStatus.REJECTED}:
            notification = HR_payroll_service.create_complaint_notification(
                employee_id=complaint.employee_id, 
                complaint_id=complaint.id, 
                status=action,
                message=message
            )
            db.session.flush() 
            complaint.notification_id = notification.id
        if complaint.salary_id:
            salary = Salary.query.get(complaint.salary_id)
            if salary:
                if payroll_status:
                    salary.status = payroll_status
                
                HR_payroll_service._append_audit_log(
                    salary=salary,
                    action="HANDLE_PAYROLL_COMPLAINT",
                    description=f"Xử lý khiếu nại #{complaint.id}: {action}. Ghi chú: {message}".strip(),
                    user_id=actor_user_id,
                )
        db.session.commit()
        return {"id": complaint.id, "status": complaint.status}

    @staticmethod
    def create_complaint_notification(employee_id: int, complaint_id: int, status: str, message: str = ""):
        status_label = "đã được giải quyết" if status == SalaryComplaintStatus.RESOLVED else "đã bị từ chối"
        content = f"Khiếu nại #{complaint_id} của bạn {status_label}. {message}".strip()
        notification = Notification(
            user_id=employee_id,
            title=f"Kết quả khiếu nại #{complaint_id}",
            message=content,
            entity_type="complaint",
            entity_id=complaint_id
        )
        db.session.add(notification)
        return notification

    '''
Bước 2: Điều tra và Ghi chú
    Khi HR bắt đầu kiểm tra một khiếu nại (ví dụ: nhân viên khiếu nại thiếu giờ làm), 
    họ sẽ thực hiện kiểm tra dữ liệu thực tế. 
    Hàm này cho phép HR lưu lại các ghi chú điều tra
    '''
    @staticmethod
    def save_investigation_note(
        attendance_id: int, 
        note: str, 
        actor_user_id: int,
        complaint_id: int | None = None
    ) -> dict:
        record = Attendance.query.get(attendance_id)
        if not record:
            raise ValueError("Không tìm thấy bản ghi chấm công")
        context_prefix = f"[Complaint ID: {complaint_id}] " if complaint_id else "[Direct Investigation] "
        full_description = f"{context_prefix}{note.strip()}"
        db.session.add(
            HistoryLog(
                employee_id=record.employee_id,
                action="INVESTIGATION_NOTE",
                entity_type="attendance",
                entity_id=record.id,
                description=full_description,
                performed_by=actor_user_id,
            )
        )
        db.session.commit()
        return {"attendance_id": record.id, "success": True}

    @staticmethod
    def hr_complaint_detail(complaint_id: int) -> dict:
        complaint = Complaint.query.filter_by(
            id=complaint_id, 
            is_deleted=False
        ).first()
        
        if not complaint:
            raise ValueError("Không tìm thấy khiếu nại")
            
        file_list = []
        for file in complaint.attachments.all():
            file_list.append({
                "file_name": file.file_name,
                "file_url": f"/static/uploads/{file.file_url}",
                "file_type": file.file_type
            })

        return {
            "id": complaint.id,
            "title": complaint.title,
            "description": complaint.description,
            "type": complaint.type,
            "status": complaint.status,
            "status_label": SalaryComplaintStatus.LABELS.get(complaint.status),
            "priority": complaint.priority,
            "created_at": complaint.created_at.strftime("%d/%m/%Y %H:%M") if complaint.created_at else None,
            "admin_reply": complaint.admin_reply,
            "resolved_at": complaint.resolved_at.strftime("%d/%m/%Y %H:%M") if complaint.resolved_at else None,
            "handler_name": complaint.handler.full_name if complaint.handler else "Đang chờ phân công",
            "attachments": file_list,
            "salary_period": f"Tháng {complaint.salary.month:02d}/{complaint.salary.year}" if complaint.salary else "N/A"
        }

    ################################################################################
    #Quản lý vòng đời phiếu lương (duyệt, khiếu nại, xem danh sách, trạng thái).
    ################################################################################

    @staticmethod
    def get_payroll_list(
        month: int = None,
        year: int = None,
        department_id: int = None,
        position_id: int = None,
        role_name: str = None,
        status: str = None,
        search: str = None,
        sort_by: str = "employee_name",
        sort_order: str = "asc"
    ) -> dict:
        current_time = get_current_time()
        month = month or current_time.month
        year = year or current_time.year
        query = Salary.query.join(Employee, Salary.employee_id == Employee.id)
        if role_name:
            query = query.join(Employee.user).join(User.role)
        query = query.filter(
            Salary.month == month,
            Salary.year == year,
            Employee.is_deleted.is_(False)
        )
        if department_id:
            query = query.filter(Employee.department_id == department_id)
        if position_id:
            query = query.filter(Employee.position_id == position_id)
        if role_name:
            query = query.filter(Role.name == role_name)
        if status and status != "all":
            query = query.filter(Salary.status == status)
        sort_map = {
            "employee_name": Employee.full_name,
            "net_salary": Salary.net_salary,
            "status": Salary.status,
            "basic_salary": Salary.basic_salary,
            "department": Employee.department_id,
        }
        sort_column = sort_map.get(sort_by, Employee.full_name)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        salaries = query.all()
        rows = [HR_payroll_service._serialize_payroll(item) for item in salaries]
        if search:
            keyword = search.lower().strip()
            rows = [
                row for row in rows
                if keyword in (row["employee_name"] or "").lower()
                or keyword in (row["employee_code"] or "").lower()
                or keyword in (row["department"] or "").lower()
            ]
        complaint_count = Complaint.query.filter(
            or_(
                Complaint.salary_id.in_([r["id"] for r in rows] or [0]), 
                Complaint.type.ilike("%salary%")
            ),
            Complaint.status.in_(["pending", "in_progress"]),
        ).count()
        summary = {
            "payroll_fund": sum(row["net_salary"] for row in rows),
            "pending_approval": sum(1 for row in rows if row["status"] == "pending_approval"),
            "complaint_count": complaint_count,
            "missing_payroll": max(Employee.query.filter_by(is_deleted=False).count() - len(rows), 0),
        }
        return {"items": rows, "summary": summary}

    @staticmethod
    def get_payroll_detail(salary_id: int) -> dict:
        salary = Salary.query.options(
            joinedload(Salary.employee).joinedload(Employee.department),
            joinedload(Salary.employee).joinedload(Employee.position)
        ).get(salary_id)
        if not salary:
            raise ValueError("Không tìm thấy bảng lương")
        data = HR_payroll_service._serialize_payroll(salary)
        note_data = salary.note_data
        data["manual_adjustments"] = {
            "allowances": note_data.get("manual_allowances", []),
            "deductions": note_data.get("manual_deductions", []),
            "note": salary.note 
        }
        data["audit_history"] = HR_payroll_service.payroll_audit_history(salary_id)
        return data

   
    '''
    Khi đã bấm "Gửi duyệt", dữ liệu phải được "đóng băng"
    '''
    @staticmethod
    def submit_payroll_approval(salary_id: int, actor_user_id: int | None = None) -> dict:
        # 1. Lấy thông tin bảng lương
        salary = Salary.query.get(salary_id)
        if not salary:
            raise ValueError("Không tìm thấy bảng lương")
        # Chỉ những trạng thái thuộc DRAFT, REJECTED, hoặc COMPLAINT mới được phép gửi duyệt
        if not SalaryStatus.is_editable(salary.status):
            raise ValueError(
                f"Bảng lương đang ở trạng thái '{SalaryStatus.get_label(salary.status)}', "
                "không thể gửi duyệt. Chỉ có thể gửi khi ở trạng thái Nháp, Bị từ chối hoặc Khiếu nại."
            )
        # 3. Kiểm tra tính mới nhất: Không cho phép gửi tháng cũ nếu đã có tháng mới hơn
        latest_salary = Salary.query.filter_by(employee_id=salary.employee_id)\
                                    .order_by(Salary.year.desc(), Salary.month.desc())\
                                    .first()
        if latest_salary and (salary.year < latest_salary.year or 
                             (salary.year == latest_salary.year and salary.month < latest_salary.month)):
            raise ValueError(
                f"Không thể gửi duyệt bảng lương tháng {salary.month}/{salary.year} "
                f"vì đã có dữ liệu tháng {latest_salary.month}/{latest_salary.year} mới hơn."
            )
        # 4. Cập nhật trạng thái sang PENDING
        salary.status = SalaryStatus.PENDING 
        # 5. Gửi thông báo cho TẤT CẢ ADMIN
        admin_role = Role.query.filter_by(name=RoleName.ADMIN).first()
        if admin_role:
            admins = User.query.filter_by(role_id=admin_role.id).all()
            for admin in admins:
                new_note = Notification(
                    user_id=admin.id,
                    message=f"Nhân viên {salary.employee.full_name} cần duyệt bảng lương tháng {salary.month}/{salary.year}.",
                )
                db.session.add(new_note)
        # 6. Audit Log
        HR_payroll_service._append_audit_log(
            salary=salary,
            action="SUBMIT_PAYROLL_APPROVAL",
            description=f"Gửi duyệt payroll tháng {salary.month}/{salary.year}",
            user_id=actor_user_id,
        )
        db.session.commit()
        return {"id": salary.id, "status": salary.status}

    ################################################################################
    #Tiện ích
    ################################################################################
    @staticmethod
    def _serialize_payroll(salary: Salary) -> dict:
        note_data = salary.note_data 
        metrics = note_data.get("metrics", {})
        breakdown = note_data.get("breakdown", {})
        employee = salary.employee
        return {
            "id": salary.id,
            "employee_id": employee.id if employee else None,
            "employee_code": f"EMP{employee.id:05d}" if employee else "--",
            "employee_name": employee.full_name if employee else "--",
            "department": employee.department.name if (employee and employee.department) else "--",
            "position": employee.position.job_title if (employee and employee.position) else "--",
            "basic_salary": float(salary.basic_salary or 0),
            "total_work_days": float(salary.total_work_days or 0),
            "leave_days": metrics.get("leave_days", 0),
            "overtime_hours": metrics.get("overtime_hours", 0),
            "allowance": float(salary.total_allowance or 0),
            "penalty": float(salary.penalty or 0),
            "net_salary": float(salary.net_salary or 0),
            "status": salary.status,
            "status_label": SalaryStatus.get_label(salary.status),
            "breakdown": breakdown,
        }
    
    @staticmethod
    def _decimal(value: object | None) -> Decimal:
        if value in (None, ""):
            return Decimal("0")
        return Decimal(str(value))

    @staticmethod
    def _append_audit_log(*, salary: Salary, action: str, description: str, user_id: int | None) -> None:
        HistoryLog.append(
            employee_id=salary.employee_id,
            action=action,
            entity_type="salary",
            entity_id=salary.id,
            description=description,
            performed_by=user_id
        )
        
    @staticmethod
    def payroll_audit_history(salary_id: int) -> list[dict]:
        logs = (
            HistoryLog.query
            .options(joinedload(HistoryLog.employee)) 
            .filter_by(entity_type="salary", entity_id=salary_id)
            .order_by(HistoryLog.created_at.desc())
            .all()
        )
        return [
            {
                "id": log.id,
                "action": log.action,
                "description": log.description,
                "performed_by_id": log.performed_by,
                "performed_by_name": log.employee.full_name if log.employee else "System",
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    
    @staticmethod
    def get_total_payroll_fund(
        period_type: str,          # "month" | "quarter" | "year"
        year: int,
        month: int | None = None,  # Bắt buộc nếu period_type = "month"
        quarter: int | None = None, # 1-4, bắt buộc nếu period_type = "quarter"
        department_id: int | None = None,
        role_name: str | None = None,
        status_filter: list[str] | None = None,  # Lọc theo trạng thái lương (vd: ["approved", "paid"])
    ) -> dict:
        policy = PayrollPolicyService.get_policy()
        ins_config = policy.get("insurance", {})

        # ── Tỷ lệ NSDLĐ đóng (phần công ty chi thêm, không trừ vào lương NV) ──
        employer_social_pct    = Decimal(str(ins_config.get("employer_social_percent",    17.0)))
        employer_health_pct    = Decimal(str(ins_config.get("employer_health_percent",     3.0)))
        employer_unemp_pct     = Decimal(str(ins_config.get("employer_unemployment_percent", 1.0)))
        employer_total_pct     = employer_social_pct + employer_health_pct + employer_unemp_pct

        # ── Xác định danh sách tháng cần tính ──────────────────────────────────
        if period_type == "month":
            if not month:
                raise ValueError("Cần truyền `month` khi period_type='month'")
            months_in_period = [(year, month)]
            period_label = f"Tháng {month:02d}/{year}"

        elif period_type == "quarter":
            if not quarter or quarter not in (1, 2, 3, 4):
                raise ValueError("Cần truyền `quarter` (1-4) khi period_type='quarter'")
            q_start = (quarter - 1) * 3 + 1
            months_in_period = [(year, m) for m in range(q_start, q_start + 3)]
            period_label = f"Quý {quarter}/{year}"

        elif period_type == "year":
            months_in_period = [(year, m) for m in range(1, 13)]
            period_label = f"Năm {year}"

        else:
            raise ValueError("period_type phải là 'month', 'quarter' hoặc 'year'")

        # ── Query bảng Salary ───────────────────────────────────────────────────
        month_values  = [m for _, m in months_in_period]
        status_filter = status_filter or [
            SalaryStatus.APPROVED,
            SalaryStatus.PAID,
            SalaryStatus.LOCKED,
        ]

        query = (
            Salary.query
            .join(Employee, Salary.employee_id == Employee.id)
            .filter(
                Salary.year  == year,
                Salary.month.in_(month_values),
                Salary.status.in_(status_filter),
                Salary.is_deleted.is_(False),
                Employee.is_deleted.is_(False),
            )
        )

        if department_id:
            query = query.filter(Employee.department_id == department_id)

        if role_name:
            query = (
                query
                .join(Employee.user)
                .join(User.role)
                .filter(Role.name == role_name)
            )

        salaries = query.all()

        # ── Tổng hợp ────────────────────────────────────────────────────────────
        # Accumulators toàn kỳ
        acc = {
            "gross":               Decimal("0"),
            "net":                 Decimal("0"),
            "allowance":           Decimal("0"),
            "pit_tax":             Decimal("0"),
            "insurance_employee":  Decimal("0"),
            "insurance_employer":  Decimal("0"),
            "penalty":             Decimal("0"),
        }

        # Breakdown theo tháng  {(year, month): acc_dict}
        by_month: dict[tuple, dict] = {
            ym: {k: Decimal("0") for k in acc} | {"salary_count": 0}
            for ym in months_in_period
        }

        # Breakdown theo phòng ban  {dept_name: acc_dict}
        by_dept:  dict[str, dict] = {}

        # Breakdown theo role  {role_name: acc_dict}
        by_role_map: dict[str, dict] = {}

        employee_ids_seen: set[int] = set()

        for sal in salaries:
            emp  = sal.employee
            ym   = (sal.year, sal.month)

            # ── Bảo hiểm NSDLĐ: tính trên gross_salary (hoặc base lương đóng BH) ──
            # Dùng gross_salary làm căn cứ (đã lưu tĩnh); phần NSDLĐ không trừ vào NV
            ins_base          = HR_payroll_service._decimal(sal.gross_salary)
            employer_ins      = (ins_base * employer_total_pct / Decimal("100")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )

            # ── Giá trị từng dòng ──────────────────────────────────────────────
            row = {
                "gross":              HR_payroll_service._decimal(sal.gross_salary),
                "net":                HR_payroll_service._decimal(sal.net_salary),
                "allowance":          HR_payroll_service._decimal(sal.total_allowance),
                "pit_tax":            HR_payroll_service._decimal(sal.pit_tax),
                "insurance_employee": HR_payroll_service._decimal(sal.insurance_employee),
                "insurance_employer": employer_ins,
                "penalty":            HR_payroll_service._decimal(sal.attendance_penalty),
            }

            # ── Cộng vào tổng toàn kỳ ─────────────────────────────────────────
            for k in acc:
                acc[k] += row[k]

            # ── Cộng vào breakdown tháng ──────────────────────────────────────
            if ym in by_month:
                for k in acc:
                    by_month[ym][k] += row[k]
                by_month[ym]["salary_count"] += 1

            # ── Cộng vào breakdown phòng ban ──────────────────────────────────
            dept_name = emp.department.name if (emp and emp.department) else "Chưa phân phòng"
            if dept_name not in by_dept:
                by_dept[dept_name] = {k: Decimal("0") for k in acc} | {"salary_count": 0}
            for k in acc:
                by_dept[dept_name][k] += row[k]
            by_dept[dept_name]["salary_count"] += 1

            # ── Cộng vào breakdown role ───────────────────────────────────────
            rname = (
                emp.user.role.name
                if (emp and emp.user and emp.user.role)
                else "Không rõ"
            )
            if rname not in by_role_map:
                by_role_map[rname] = {k: Decimal("0") for k in acc} | {"salary_count": 0}
            for k in acc:
                by_role_map[rname][k] += row[k]
            by_role_map[rname]["salary_count"] += 1

            employee_ids_seen.add(emp.id if emp else -1)

        # ── Helper: format một acc dict ra float + labor_cost ─────────────────
        def _fmt(d: dict) -> dict:
            labor_cost = d["gross"] + d["insurance_employer"]  # chi phí thực công ty
            return {
                "total_gross":              float(d["gross"]),
                "total_net":                float(d["net"]),
                "total_allowance":          float(d["allowance"]),
                "total_pit_tax":            float(d["pit_tax"]),
                "total_insurance_employee": float(d["insurance_employee"]),
                "total_insurance_employer": float(d["insurance_employer"]),
                "total_penalty":            float(d["penalty"]),
                "total_labor_cost":         float(labor_cost),
                "salary_count":             d.get("salary_count", len(salaries)),
            }

        # ── Kết quả by_period (sắp xếp theo tháng tăng dần) ──────────────────
        by_period_list = []
        for (y, m), d in sorted(by_month.items()):
            entry = _fmt(d)
            entry["year"]  = y
            entry["month"] = m
            entry["label"] = f"Tháng {m:02d}/{y}"
            by_period_list.append(entry)

        # ── Kết quả by_department ─────────────────────────────────────────────
        by_dept_list = []
        for dname, d in sorted(by_dept.items(), key=lambda x: -x[1]["gross"]):
            entry = _fmt(d)
            entry["department"] = dname
            by_dept_list.append(entry)

        # ── Kết quả by_role ───────────────────────────────────────────────────
        by_role_list = []
        for rname, d in sorted(by_role_map.items(), key=lambda x: -x[1]["gross"]):
            entry = _fmt(d)
            entry["role"] = rname
            by_role_list.append(entry)

        # ── Tổng toàn kỳ ─────────────────────────────────────────────────────
        summary = _fmt(acc)
        summary["salary_count"] = len(salaries)

        return {
            "period": {
                "type":    period_type,
                "label":   period_label,
                "year":    year,
                "month":   month,
                "quarter": quarter,
                "months":  [{"year": y, "month": m} for y, m in months_in_period],
            },
            "filters": {
                "department_id": department_id,
                "role_name":     role_name,
                "status_filter": status_filter,
            },
            "summary":        summary,
            "by_period":      by_period_list,
            "by_department":  by_dept_list,
            "by_role":        by_role_list,
            "employee_count": len(employee_ids_seen),
            "salary_count":   len(salaries),
        }