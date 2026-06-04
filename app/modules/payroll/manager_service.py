from datetime import date, timedelta
from decimal import Decimal
from app.constants.common import RoleName
from app.constants.overtime import OvertimeConfig
from app.extensions import db

from sqlalchemy.util import defaultdict
from calendar import monthrange
from app.constants.holidays import VN_FIXED_PUBLIC_HOLIDAYS, HolidayConfig
from app.constants.leave import LeaveStatus
from app.constants.payroll import SalaryComplaintStatus, SalaryStatus

from app.models.attendance import Attendance
from app.models.complaint import Complaint
from app.models.employee import Employee
from app.models.leave import LeaveRequest, LeaveType
from app.models.history import HistoryLog
from app.models.notification import Notification
from app.models.overtime_request import OvertimeRequest
from app.models.position import Position
from app.models.salary import Salary
from sqlalchemy import and_, extract, func, or_, cast, String
from sqlalchemy.orm import joinedload, contains_eager

from app.models.user import User
from app.modules.attendance.attendance_calculation_service import attendance_calculation_service
from app.modules.payroll.base_service import BasePayrollService, PersonalPayrollService
from app.utils.date_utils import get_month_range
from app.utils.time import get_current_time
class Manager_Payroll_Service(PersonalPayrollService):
    @staticmethod
    def _get_subordinates(manager_id: int) -> list[Employee]:
        """
        Lấy toàn bộ nhân viên thuộc (các) phòng ban mà manager này quản lý.
        Ràng buộc: Chỉ lấy nhân viên trong cùng phòng ban.
        """
        manager = Employee.query.get(manager_id)
        if not manager or manager.is_deleted:
            return []
        managed_depts = manager.managed_department
            
        if not managed_depts:
            return []
        if not isinstance(managed_depts, list):
            managed_depts = [managed_depts]

        all_subordinates = []
        for dept in managed_depts:
            if hasattr(dept, 'employees'):
                emps = [
                    e for e in dept.employees 
                    if e.id != manager_id and not e.is_deleted
                ]
                all_subordinates.extend(emps)
        return all_subordinates
        
    @staticmethod
    def get_department_salary(
        manager_id: int, 
        month: int, 
        year: int, 
        search: str = None, 
        status: str = None, 
        sort_by: str = 'id_asc'
    ) -> list[dict]:
        """
        Lấy danh sách lương cho Manager (bao gồm cấp dưới và chính Manager).
        Bổ sung đối soát người phụ thuộc để hiển thị cảnh báo trên UI.
        """
        # 1. Lấy danh sách ID: Cấp dưới + Chính Manager
        subordinates = Manager_Payroll_Service._get_subordinates(manager_id)
        sub_ids = [e.id for e in subordinates]
        # Gộp chính mình vào danh sách hiển thị
        view_ids = sub_ids + [manager_id]
        # 2. Khởi tạo Query
        query = Salary.query.join(Salary.employee).options(contains_eager(Salary.employee)).filter(
            Salary.employee_id.in_(view_ids),
            Salary.month == month,
            Salary.year == year,
            Salary.is_deleted.is_(False)
        )
        # --- CHỨC NĂNG 1: TÌM KIẾM ---
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    Employee.full_name.ilike(search_filter),
                    cast(Salary.employee_id, String).like(search_filter)
                )
            )
        # --- CHỨC NĂNG 2: LỌC THEO TRẠNG THÁI ---
        if status:
            query = query.filter(Salary.status == status)
        # --- CHỨC NĂNG 3: SẮP XẾP ---
        sort_options = {
            'net_asc': Salary.net_salary.asc(),
            'net_desc': Salary.net_salary.desc(),
            'id_desc': Salary.employee_id.desc()
        }
        query = query.order_by(sort_options.get(sort_by, Salary.employee_id.asc()))
        salary_records = query.all()
        # 3. Trả về dữ liệu kèm logic đối soát người phụ thuộc
        result = []
        for s in salary_records:
            # Lấy số lượng người phụ thuộc hiện tại trong DB để so sánh với lúc chốt
            current_dep_count = BasePayrollService._dependent_count(s.employee_id)
            result.append({
                "salary_id": s.id, # Cần ID này để bấm nút "Gửi lên HR"
                "employee_id": s.employee_id,
                "is_manager": s.employee_id == manager_id, # Đánh dấu để UI highlight dòng của Manager
                "name": s.employee.full_name if s.employee else "--",
                "employee_code": f"EMP{s.employee_id:04d}",
                "basic_salary": float(s.basic_salary or 0),
                "total_work_days": float(s.total_work_days or 0),
                "penalty": float(s.penalty or 0),
                "net_salary": float(s.net_salary or 0),
                "status": s.status,
                "status_label": SalaryStatus.get_label(s.status),
                "note": s.note,
                
                # Bổ sung thông tin người phụ thuộc (Điểm cộng logic)
                "snapshot_dependents": s.number_of_dependents, # Số lượng lúc chốt
                "current_dependents": current_dep_count,      # Số lượng thực tế hiện tại
                "dep_mismatch": current_dep_count != s.number_of_dependents # Flag để Frontend hiện icon ⚠️
            })
        return result

    @staticmethod
    def get_department_regular_work_days(employee_ids: list, month: int, year: int) -> dict:
        """
        Tính tổng công hành chính của danh sách nhân viên trong tháng.
        Sử dụng range date để tối ưu hóa truy vấn.
        """
        start_date, end_date = get_month_range(month, year)
        attendance_records = Attendance.query.filter(
            Attendance.employee_id.in_(employee_ids),
            Attendance.date >= start_date,
            Attendance.date <= end_date,
            Attendance.is_deleted.is_(False)
        ).all()
        department_stats = defaultdict(Decimal)
        for record in attendance_records:
            work_unit = attendance_calculation_service.calculate_regular_work_units(record)
            department_stats[record.employee_id] += work_unit.units
        return {emp_id: float(total_days) for emp_id, total_days in department_stats.items()}

    @staticmethod
    def get_department_overtime_stats(employee_ids: list, month: int, year: int) -> dict:
        start_date, end_date = get_month_range(month, year)
        approved_requests = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id.in_(employee_ids),
            OvertimeRequest.overtime_date >= start_date,
            OvertimeRequest.overtime_date <= end_date,
            OvertimeRequest.status == "approved",
            OvertimeRequest.is_deleted.is_(False)
        ).all()
        department_ot_stats = defaultdict(Decimal)
        for req in approved_requests:
            hours = req.approved_hours or Decimal("0.00")
            type_key = "after_shift" # Mặc định
            if req.is_holiday_ot:
                type_key = "holiday"
            elif req.overtime_date.weekday() >= 5: 
                type_key = "weekend"
            weighted_hours = OvertimeConfig.apply_multiplier(hours, type_key)
            department_ot_stats[req.employee_id] += weighted_hours
        return {emp_id: float(total_weighted_hours) for emp_id, total_weighted_hours in department_ot_stats.items()}

    @staticmethod
    def count_department_late_occurrences(employee_ids: list, month: int, year: int) -> dict:
        """
        Đếm số lần đi muộn của từng nhân viên trong danh sách.
        Sử dụng range date để tận dụng Index trên cột date.
        """
        start_date, end_date = get_month_range(month, year)
        stats = db.session.query(
            Attendance.employee_id, 
            func.count(Attendance.id).label("late_count")
        ).filter(
            Attendance.employee_id.in_(employee_ids),
            Attendance.late_minutes > 0,
            Attendance.date >= start_date, 
            Attendance.date <= end_date,   
            Attendance.is_deleted.is_(False)
        ).group_by(Attendance.employee_id).all()
        return {stat.employee_id: stat.late_count for stat in stats}

    @staticmethod
    def get_leave_summary(month: int = None, year: int = None, employee_ids: list = None) -> dict:
        """
        Tính tổng ngày nghỉ có lương và không lương, tự động trừ T7, CN và Ngày lễ.
        """
        today = get_current_time()
        month = month or today.month
        year = year or today.year
        month_start, month_end = get_month_range(month, year)
        lunar_holidays = HolidayConfig.get_lunar_holidays(year)
        query = db.session.query(LeaveRequest, LeaveType).join(
            LeaveType, LeaveRequest.leave_type_id == LeaveType.id
        ).filter(
            LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.is_deleted.is_(False),
            LeaveRequest.from_date <= month_end,
            LeaveRequest.to_date >= month_start
        )
        if employee_ids:
            query = query.filter(LeaveRequest.employee_id.in_(employee_ids))
        leaves = query.all()
        summary = {emp_id: {"paid_leave_days": 0, "unpaid_leave_days": 0} for emp_id in employee_ids} if employee_ids else {}
        for request, leave_type in leaves:
            emp_id = request.employee_id
            if emp_id not in summary:
                summary[emp_id] = {"paid_leave_days": 0, "unpaid_leave_days": 0}
            start = max(request.from_date, month_start)
            end = min(request.to_date, month_end)
            days_in_month = 0
            current = start
            while current <= end:
                date_str = current.strftime("%m-%d")
                is_weekend = current.weekday() >= 5
                is_holiday = (date_str in VN_FIXED_PUBLIC_HOLIDAYS) or (date_str in lunar_holidays)
                if not is_weekend and not is_holiday:
                    days_in_month += 1
                current += timedelta(days=1)
            if leave_type.is_paid:
                summary[emp_id]["paid_leave_days"] += days_in_month
            else:
                summary[emp_id]["unpaid_leave_days"] += days_in_month
        return summary

    @staticmethod
    def get_department_payroll_report(manager_id: int, month: int, year: int) -> dict:
        """
        Hàm tổng hợp báo cáo lương/chấm công cho quản lý.
        Đây là điểm gọi duy nhất (Entry point) để lấy toàn bộ dữ liệu báo cáo.
        """
        # 1. Lấy danh sách cấp dưới
        subordinates = Manager_Payroll_Service._get_subordinates(manager_id)
        if not subordinates:
            return {}

        employee_ids = [e.id for e in subordinates]
        reg_days = Manager_Payroll_Service.get_department_regular_work_days(employee_ids, month, year)
        ot_stats = Manager_Payroll_Service.get_department_overtime_stats(employee_ids, month, year)
        late_stats = Manager_Payroll_Service.count_department_late_occurrences(employee_ids, month, year)
        leave_summary = Manager_Payroll_Service.get_leave_summary(month=month, year=year, employee_ids=employee_ids)
        report = {}
        for emp in subordinates:
            emp_id = emp.id
            report[emp_id] = {
                "full_name": getattr(emp, 'full_name', 'N/A'),
                "metrics": {
                    "regular_work_days": reg_days.get(emp_id, 0.0),
                    "weighted_ot_hours": ot_stats.get(emp_id, 0.0),
                    "late_occurrences": late_stats.get(emp_id, 0),
                    "leave": leave_summary.get(emp_id, {"paid_leave_days": 0, "unpaid_leave_days": 0})
                }
            }
        return report

    @staticmethod
    def get_department_payroll_review(
        manager_id: int,
        month: int,
        year: int,
        employee_name: str | None = None,
        employee_code: str | None = None,
        status: str | None = None,
        employment_type: str | None = None,
        position: str | None = None,
    ) -> dict:
        # 1. Lấy danh sách cấp dưới và gộp thêm chính Manager
        employees = Manager_Payroll_Service._get_subordinates(manager_id)
        sub_ids = [e.id for e in employees]
        view_ids = sub_ids + [manager_id] # Đảm bảo Manager luôn thấy mình

        # 2. Truy vấn dữ liệu lương
        query = Salary.query.join(Employee, Salary.employee_id == Employee.id).filter(
            Salary.employee_id.in_(view_ids),
            Salary.month == month,
            Salary.year == year,
            Salary.is_deleted.is_(False),
        )

        # --- Filters (Giữ nguyên logic của bạn) ---
        if employee_name:
            query = query.filter(Employee.full_name.ilike(f"%{employee_name.strip()}%"))
        if employee_code:
            code = employee_code.strip().upper().replace('EMP', '')
            query = query.filter(db.cast(Salary.employee_id, db.String).ilike(f"%{code}%"))
        if status:
            query = query.filter(Salary.status == status.strip().lower())
        if employment_type:
            query = query.filter(Employee.employment_type == employment_type)
        if position:
            query = query.filter(Employee.position.has(Position.job_title.ilike(f"%{position.strip()}%")))

        rows = query.order_by(Employee.full_name.asc()).all()

        items = []
        pending_count = 0

        for salary in rows:
            # 3. Tính toán giờ làm thực tế (Giữ nguyên logic của bạn)
            attendance_data = Attendance.query.filter(
                Attendance.employee_id == salary.employee_id,
                db.extract("month", Attendance.date) == month,
                db.extract("year", Attendance.date) == year,
                Attendance.is_deleted.is_(False)
            ).all()
            reg_hours = sum(float(a.working_hours or 0) for a in attendance_data)
            ot_holiday_hours = sum(float(a.overtime_hours or 0) for a in attendance_data if a.is_holiday or a.is_weekend)
            ot_after_hours = sum(float(a.overtime_hours or 0) for a in attendance_data if not (a.is_holiday or a.is_weekend))
            # 4. LOGIC ĐỐI SOÁT NGƯỜI PHỤ THUỘC (Điểm nhấn đồ án)
            current_dep = BasePayrollService._dependent_count(salary.employee_id)
            is_mismatch = (current_dep != (salary.number_of_dependents or 0))
            # 5. Xử lý trạng thái
            raw_status = (salary.status or "pending").strip().lower()
            if raw_status == 'pending':
                pending_count += 1
            # 6. Cấu trúc dữ liệu trả về
            items.append({
                "salary_id": salary.id,
                "is_self": salary.employee_id == manager_id, # Đánh dấu dòng của chính Manager
                "employee_code": f"EMP{salary.employee_id:04d}",
                "employee_name": salary.employee.full_name if salary.employee else "--",
                "position": salary.employee.position.job_title if salary.employee and salary.employee.position else "--",     
                "work_stats": {
                    "total_work_days": float(salary.total_work_days or 0), 
                    "reg_hours": round(reg_hours, 1),
                    "ot_after_hours": round(ot_after_hours, 1),
                    "ot_holiday_hours": round(ot_holiday_hours, 1),
                },
                "review_params": {
                    "penalty_amount": float(salary.penalty or 0), 
                    "snapshot_dependents": salary.number_of_dependents or 0,
                    "current_dependents": current_dep,
                    "has_warning": is_mismatch # Trả về True nếu số lượng thay đổi
                },
                "status": raw_status,
                "status_label": SalaryStatus.get_label(raw_status)
            })
        return {
            "summary": {
                "total_employees": len(rows),
                "pending_confirmation": pending_count
            },
            "items": items
        }
    
    @staticmethod
    def get_department_payroll_detail(manager_id: int, salary_id: int) -> dict:
        """
        Lấy thông tin chi tiết bảng lương (bao gồm cấp dưới và chính Manager).
        Bổ sung cảnh báo đối soát người phụ thuộc.
        """
        # 1. Lấy danh sách cấp dưới
        subordinates = Manager_Payroll_Service._get_subordinates(manager_id)
        sub_ids = [e.id for e in subordinates]
        
        # 2. Truy vấn bản ghi
        row = Salary.query.options(
            joinedload(Salary.employee).joinedload(Employee.position)
        ).filter_by(id=salary_id, is_deleted=False).first()

        # KIỂM TRA QUYỀN: Phải là cấp dưới HOẶC là chính Manager
        if not row:
            raise ValueError("Dữ liệu không tồn tại")
            
        is_self = (row.employee_id == manager_id)
        if row.employee_id not in sub_ids and not is_self:
            raise ValueError("Bạn không có quyền truy cập thông tin này")

        # 3. Logic đối soát người phụ thuộc (Điểm cộng logic cho đồ án)
        current_dep = BasePayrollService._dependent_count(row.employee_id)
        is_mismatch = (current_dep != (row.number_of_dependents or 0))

        # 4. Xử lý khiếu nại (giữ nguyên logic của bạn)
        complaint = Manager_Payroll_Service._latest_salary_complaint(row.employee_id, row.id)
        formatted_complaint = Manager_Payroll_Service._format_complaints([complaint])[0] if complaint else None

        return {
            "salary_id": row.id,
            "is_self": is_self, # Flag để Frontend biết đây là lương của chính Manager
            "employee": {
                "id": row.employee_id,
                "code": f"EMP{row.employee_id:04d}",
                "name": row.employee.full_name if row.employee else "--",
                "position": row.employee.position.job_title if row.employee and row.employee.position else "--",
            },
            "earnings": {
                "basic_salary": float(row.basic_salary or 0),
                "overtime_salary": float(row.overtime_salary or 0),
                "bonus": float(row.bonus or 0),
                "allowances": {
                    "total": float(row.total_allowance or 0),
                    "lunch": float(row.lunch_allowance or 0),
                    "responsibility": float(row.responsibility_allowance or 0),
                }
            },
            "deductions": {
                "insurance": float(row.insurance or 0),
                "tax": float(row.tax or 0),
                "penalty": float(row.penalty or 0),
                "family_deduction": float(row.family_deduction or 0),
            },
            "work_stats": {
                "month_year": f"{row.month:02d}/{row.year}",
                "standard_work_days": int(row.standard_work_days or 22),
                "total_work_days": float(row.total_work_days or 0),
                # Thông tin đối soát người phụ thuộc
                "snapshot_dependents": row.number_of_dependents or 0,
                "current_dependents": current_dep,
                "has_dep_warning": is_mismatch,
            },
            "net_salary": float(row.net_salary or 0),
            "status": row.status,
            "status_label": SalaryStatus.get_label(row.status),
            "note": row.note,
            "latest_complaint": formatted_complaint
        }

    @staticmethod
    def confirm_department_payroll(manager_id: int, salary_id: int, note: str | None = None) -> dict:
        """
        Xác nhận bảng lương: Gọi 4 hàm tính toán để lấy dữ liệu thực tế, 
        cập nhật vào record, sau đó phê duyệt.
        """
        subordinates = Manager_Payroll_Service._get_subordinates(manager_id)
        sub_ids = [e.id for e in subordinates]
        row = Salary.query.filter_by(id=salary_id, is_deleted=False).first()
        if not row:
            raise ValueError("Không tìm thấy bản ghi lương.")
        is_self = (row.employee_id == manager_id)
        if row.employee_id not in sub_ids and not is_self:
            raise ValueError("Bạn không có quyền phê duyệt bảng lương này.")
        if row.status != SalaryStatus.PENDING:
            raise ValueError(f"Bảng lương đang ở trạng thái '{SalaryStatus.get_label(row.status)}', không thể duyệt.")
        emp_ids = [row.employee_id]
        month, year = row.month, row.year
        reg_days_dict = Manager_Payroll_Service.get_department_regular_work_days(emp_ids, month, year)
        ot_stats_dict = Manager_Payroll_Service.get_department_overtime_stats(emp_ids, month, year)
        late_stats_dict = Manager_Payroll_Service.count_department_late_occurrences(emp_ids, month, year)
        leave_summary_dict = Manager_Payroll_Service.get_leave_summary(month=month, year=year, employee_ids=emp_ids)
        emp_id = row.employee_id
        real_work_days = reg_days_dict.get(emp_id, 0.0)
        real_ot_hours = ot_stats_dict.get(emp_id, 0.0)
        real_late = late_stats_dict.get(emp_id, 0)
        real_leave = leave_summary_dict.get(emp_id, {"paid_leave_days": 0, "unpaid_leave_days": 0})
        row.total_work_days = real_work_days
        current_dep_count = BasePayrollService._dependent_count(row.employee_id)
        dep_warning = ""
        if current_dep_count != row.number_of_dependents:
            dep_warning = (f"\n⚠️ CẢNH BÁO: Số người phụ thuộc thay đổi! "
                          f"({row.number_of_dependents} -> {current_dep_count}). "
                          f"Manager xác nhận dùng dữ liệu cũ.")
        row.status = SalaryStatus.APPROVED
        action_prefix = "[Manager Verified - SELF]" if is_self else "[Manager Verified]"
        check_summary = (
            f"{action_prefix} Công: {float(real_work_days)} | "
            f"OT: {float(real_ot_hours)} | "
            f"NPT: {row.number_of_dependents}"
        )
        row.note = f"{(row.note or '').strip()}\n{check_summary}{dep_warning}\nLời nhắn: {note or 'Hợp lệ'}".strip()
        db.session.add(HistoryLog(
            employee_id=row.employee_id,
            action="MANAGER_PAYROLL_CONFIRMED",
            entity_type="salary",
            entity_id=row.id,
            description=f"{'Tự chốt' if is_self else 'Duyệt'} lương tháng {row.month}/{row.year}. {dep_warning.strip()}",
            performed_by=manager_id,
        ))
        if row.employee and row.employee.user_id:
            msg_content = "Bạn đã tự xác nhận dữ liệu công/phạt của mình." if is_self else f"Quản lý đã phê duyệt công và phạt tháng {row.month}/{row.year}."
            db.session.add(Notification(
                user_id=row.employee.user_id,
                title="Dữ liệu lương đã gửi lên HR",
                content=msg_content,
                type="salary"
            ))
        db.session.commit()
        return {
            "message": "Đã gửi dữ liệu lên HR thành công.",
            "is_self_approved": is_self,
            "has_discrepancy": current_dep_count != row.number_of_dependents,
            "hr_data_snapshot": {
                "work_days": real_work_days,
                "ot_hours": real_ot_hours,
                "late_count": real_late,
                "leave": real_leave
            }
        }

    @staticmethod
    def handle_salary_complaint(manager_id: int, complaint_id: int, action: str, note: str) -> dict:
        complaint = Complaint.query.filter_by(id=complaint_id, is_deleted=False).first()
        if not complaint:
            raise ValueError("Khiếu nại không tồn tại.")
        sub_ids = [e.id for e in Manager_Payroll_Service._get_subordinates(manager_id)]
        if complaint.employee_id not in sub_ids:
            raise ValueError("Bạn không có quyền xử lý khiếu nại này.")
        salary = complaint.salary 
        if action == 'approve':
            # Phê duyệt: Khiếu nại được chấp nhận là hợp lệ
            complaint.status = SalaryComplaintStatus.RESOLVED
            complaint.admin_reply = f"Manager phê duyệt: {note}"
            complaint.resolved_at = get_current_time()
        elif action == 'reject':
            # Từ chối: Khiếu nại không hợp lệ, trả phiếu lương về trạng thái cũ
            complaint.status = SalaryComplaintStatus.REJECTED
            complaint.admin_reply = f"Manager từ chối: {note}"
            complaint.resolved_at = get_current_time()
            # Mở khóa phiếu lương
            if salary:
                salary.status = SalaryStatus.SENT # Trả về trạng thái đã gửi để bình thường hóa
        else:
            raise ValueError("Hành động không hợp lệ.")
        complaint.handled_by = manager_id
        db.session.add(HistoryLog(
            employee_id=complaint.employee_id,
            action=f"MANAGER_{action.upper()}_COMPLAINT",
            entity_type="complaint",
            entity_id=complaint.id,
            description=f"Manager {action.capitalize()}: {note}",
            performed_by=manager_id
        ))
        Manager_Payroll_Service._trigger_complaint_notifications(complaint, action, note)
        db.session.commit()
        return {
            "status": complaint.status, 
            "message": f"Khiếu nại đã được {action} thành công."
        }
    @staticmethod
    def get_payroll_complaints(
        manager_id: int,  
        month: int | None = None, 
        year: int | None = None, 
        status: str | None = None
    ) -> list[dict]:
        """
        Chỉ lấy khiếu nại của nhân viên thuộc phòng ban của Manager.
        """
        subordinates = BasePayrollService._get_subordinates(manager_id)
        if not subordinates:
            return []
        subordinate_ids = [emp.id for emp in subordinates]
        query = Complaint.query.join(Employee, Complaint.employee_id == Employee.id).filter(
            Complaint.employee_id.in_(subordinate_ids), # CHỐT CHẶN: Chỉ lấy nhân viên của phòng ban
            or_(Complaint.salary_id.isnot(None), Complaint.type.ilike("%salary%"))
        )
        if status:
            query = query.filter(Complaint.status == status)
        if month and year:
            query = query.join(Salary, Complaint.salary_id == Salary.id, isouter=True).filter(
                or_(Salary.id.is_(None), and_(Salary.month == month, Salary.year == year))
            )
        complaints = query.order_by(Complaint.created_at.desc()).limit(100).all()
        return [
            {
                "id": item.id,
                "employee": item.employee.full_name if item.employee else "--",
                "title": item.title,
                "status": item.status,
                "admin_reply": item.admin_reply,
                "handled_by": item.handled_by,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
            }
            for item in complaints
        ]

    @staticmethod
    def manager_complaint_detail(manager_id: int, complaint_id: int) -> dict:
        """Xem chi tiết khiếu nại (Dành cho Manager - Chỉ xem được đơn của nhân viên thuộc phòng ban quản lý)"""
        
        # 1. Truy vấn khiếu nại
        complaint = Complaint.query.filter_by(
            id=complaint_id, 
            is_deleted=False
        ).first()
        
        if not complaint:
            raise ValueError("Không tìm thấy khiếu nại")

        # 2. Kiểm tra quyền sở hữu (Lấy danh sách subordinates của manager)
        subordinates = Manager_Payroll_Service._get_subordinates(manager_id)
        subordinate_ids = [e.id for e in subordinates]

        # Nếu employee_id của khiếu nại không nằm trong danh sách cấp dưới
        if complaint.employee_id not in subordinate_ids:
            raise ValueError("Bạn không có quyền xem khiếu nại này.")

        # 3. Format dữ liệu trả về
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

    @staticmethod
    def _trigger_complaint_notifications(complaint: Complaint, action: str, note: str):
        """
        Helper gửi thông báo cho Nhân viên và HR (nếu cần).
        """
        # 1. Luôn thông báo cho nhân viên (cả approve và reject)
        msg = "đã được quản lý xác nhận và chuyển sang HR xử lý" if action == 'approve' else "đã bị từ chối"
        
        if complaint.employee and complaint.employee.user_id:
            db.session.add(Notification(
                user_id=complaint.employee.user_id,
                title="🔔 Cập nhật khiếu nại lương",
                content=f"Khiếu nại của bạn {msg}. Lời nhắn: {note}",
                type="complaint",
                link=f"/employee/complaints/{complaint.id}"
            ))

        # 2. Chỉ thông báo cho HR nếu Manager phê duyệt
        if action == 'approve':
            hr_users = User.query.filter(User.role == RoleName.HR).all()
            for hr in hr_users:
                db.session.add(Notification(
                    user_id=hr.id,
                    title="📣 Cần xử lý khiếu nại lương",
                    content=f"Quản lý đã phê duyệt khiếu nại của {complaint.employee.full_name}. Vui lòng kiểm tra và quyết toán.",
                    type="complaint",
                    link=f"/hr/complaints/{complaint.id}"
                ))