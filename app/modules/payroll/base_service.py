from app.models.employee import Employee
from app.models.complaint import Complaint
from app.models.dependent import Dependent
from app.constants.payroll import PayrollIssueType, SalaryComplaintStatus, SalaryStatus
from app.models.salary import Salary
from app.utils.time import get_current_time
class BasePayrollService:
    @staticmethod
    def _get_employee(user_id: int | None) -> Employee:
        employee = Employee.query.filter_by(user_id=user_id, is_deleted=False).first()
        if not employee:
            raise ValueError("Không tìm thấy hồ sơ nhân viên")
        return employee
    
    @staticmethod
    def _dependent_count(employee_id: int) -> int:
        return Dependent.query.filter_by(employee_id=employee_id, is_deleted=False, is_valid=True).count()

    @staticmethod
    def _latest_salary_complaint(employee_id: int, salary_id: int) -> Complaint | None:
        return (
            Complaint.query.filter_by(
                employee_id=employee_id, 
                salary_id=salary_id,
                type='salary'  
            )
            .order_by(Complaint.created_at.desc())
            .first()
        )
    @staticmethod
    def _format_complaints(complaints) -> list[dict]:
        """Helper để format dữ liệu khiếu nại (DRY - Don't Repeat Yourself)"""
        results = []
        for c in complaints:
            results.append({
                "id": c.id,
                "title": c.title,
                "type_label": PayrollIssueType.LABELS.get(c.type, "Khác"),
                "status": c.status,
                "status_label": SalaryComplaintStatus.LABELS.get(c.status, "⏳ Chờ xử lý"),
                "priority": c.priority,
                "created_at": c.created_at.strftime("%d/%m/%Y %H:%M"),
                "employee_name": c.employee.full_name if c.employee else "N/A",
                "admin_reply": c.admin_reply or "Chưa có phản hồi"
            })
        return results
    
    @staticmethod
    def get_salary_history(employee_id: int, year: int) -> list[dict]:
        """Lấy lịch sử lương của 1 nhân viên để xem danh sách hoặc vẽ biểu đồ."""
        salaries = (
            Salary.query
            .filter_by(employee_id=employee_id, year=year, is_deleted=False)
            .order_by(Salary.month.asc())
            .all()
        )
        return [
            {
                "id": s.id,
                "month": s.month,
                "year": s.year,
                "net_salary": float(s.net_salary),
                "status": s.status,
                "status_label": SalaryStatus.get_label(s.status),
                "created_at": s.created_at.strftime("%d/%m/%Y")
            } for s in salaries
        ]

    @staticmethod
    def _latest_salary(employee_id: int) -> Salary | None:
        """
        Lấy bản ghi lương mới nhất (Snapshot) để hiển thị Dashboard hoặc tham chiếu.
        """
        return (
            Salary.query.filter_by(employee_id=employee_id, is_deleted=False)
            .order_by(Salary.year.desc(), Salary.month.desc())
            .first()
        )
    
class PersonalPayrollService:
    @staticmethod
    def payroll_history(user_id: int | None, filters: dict) -> dict:
        employee = BasePayrollService._get_employee(user_id)
        year = int(filters.get("year") or get_current_time().year)
        payroll_status = (filters.get("status") or "").strip()
        paid_state = (filters.get("paid_state") or "").strip()
        complaint_only = str(filters.get("has_complaint") or "").lower() in {"1", "true", "yes"}
        
        query = Salary.query.filter_by(employee_id=employee.id, year=year, is_deleted=False)
        if payroll_status:
            query = query.filter(Salary.status == payroll_status)
        if paid_state == "paid":
            query = query.filter(Salary.status == SalaryStatus.PAID)
        elif paid_state == "unpaid":
            query = query.filter(Salary.status != SalaryStatus.PAID)
            
        rows = query.order_by(Salary.month.desc()).all()
        current_dependent_count = BasePayrollService._dependent_count(employee.id)
        payload = []
        for row in rows:
            complaint = BasePayrollService._latest_salary_complaint(employee.id, row.id)
            if complaint_only and not complaint:
                continue
            payload.append(
                {
                    "id": row.id,
                    "month": row.month,
                    "year": row.year,
                    "basic_salary": float(row.basic_salary or 0),
                    "allowance": float(row.total_allowance or 0),
                    "overtime": float(row.overtime_salary or 0),  # Sửa từ gán cứng số 0 sang lấy tĩnh từ DB
                    "deduction": float(row.penalty or 0),
                    "insurance": float(row.insurance or 0),       # Lấy tĩnh từ cột insurance mới
                    "tax": float(row.tax or 0),                   # Lấy tĩnh từ cột tax mới
                    "net_salary": float(row.net_salary or 0),
                    "status": row.status,
                    "status_label": SalaryStatus.get_label(row.status),
                    "payment_date": row.updated_at.strftime("%d/%m/%Y") if (row.status == SalaryStatus.PAID and row.updated_at) else None,
                    "has_complaint": bool(complaint),
                    "complaint_status": complaint.status if complaint else None,
                    "complaint_status_label": SalaryComplaintStatus.LABELS.get(complaint.status, "Không rõ") if complaint else "Không có khiếu nại",
                    "number_of_dependents": row.number_of_dependents, # Trả thêm trường này ra nếu FE cần hiện chi tiết từng tháng
                }
            )
        latest = payload[0] if payload else None
        return {
            "summary": {
                "period": f"{latest['month']:02d}/{latest['year']}" if latest else "--",
                "net_salary": latest["net_salary"] if latest else 0,
                "status": latest["status_label"] if latest else "--",
                "payment_date": latest["payment_date"] if latest else "--",
                "complaint_status": latest["complaint_status_label"] if latest else "Không có",
                "title": f"Lương tháng {latest['month']:02d}/{latest['year']}" if latest else "Chưa có kỳ lương",
            },
            "items": payload,
            "number_of_dependents": current_dependent_count,  
        }

    @staticmethod
    def payroll_detail(user_id: int | None, salary_id: int) -> dict:
        employee = BasePayrollService._get_employee(user_id)
        row = Salary.query.filter_by(id=salary_id, employee_id=employee.id, is_deleted=False).first()
        if not row:
            raise ValueError("Không tìm thấy phiếu lương hoặc bạn không có quyền xem phiếu lương này")
            
        complaint = BasePayrollService._latest_salary_complaint(employee.id, row.id)
        
        # Trả dữ liệu sạch về cho Frontend vẽ giao diện hóa đơn lương bằng cách đọc trực tiếp snapshot tĩnh từ DB
        return {
            "id": row.id,
            "month": row.month,
            "year": row.year,
            "employee_name": employee.full_name,
            
            # Các khoản cộng vào thu nhập (Lấy chuẩn từ các cột tĩnh)
            "basic_salary": float(row.basic_salary or 0),
            "standard_work_days": row.standard_work_days,
            "total_work_days": float(row.total_work_days or 0),
            "lunch_allowance": float(row.lunch_allowance or 0),                  # Lấy tĩnh từ DB, không chia đôi bừa nữa
            "responsibility_allowance": float(row.responsibility_allowance or 0),  # Lấy tĩnh từ DB, không chia đôi bừa nữa
            "total_allowance": float(row.total_allowance or 0),                  # Trả thêm tổng phụ cấp gộp nếu FE cần
            "bonus": float(row.bonus or 0),
            "overtime": float(row.overtime_salary or 0),                         # Lấy chuẩn từ cột overtime_salary tĩnh
            
            # Các khoản trừ đi (Lấy tĩnh từ thời điểm chốt lương)
            "deduction": float(row.penalty or 0),
            "insurance": float(row.insurance or 0),                              # Lấy tĩnh từ cột insurance
            "tax": float(row.tax or 0),                                          # Lấy tĩnh từ cột tax
            
            # Thông tin giảm trừ gia cảnh thuế TNCN tại thời điểm chốt lương
            "number_of_dependents": row.number_of_dependents,                    # Lấy tĩnh từ cột number_of_dependents
            "family_deduction": float(row.family_deduction or 0),                # Lấy tĩnh từ cột family_deduction
            
            # Thực lĩnh cuối cùng
            "net_salary": float(row.net_salary or 0),
            "note": row.note,
            
            # Khớp chuẩn Label trạng thái lương từ file Constants của ông
            "status": row.status,
            "status_label": SalaryStatus.get_label(row.status),
            
            # Đổ thêm dữ liệu khiếu nại để Frontend xử lý logic hiển thị nút bấm hành động
            "has_complaint": bool(complaint),
            "complaint_status": complaint.status if complaint else None,
            "complaint_status_label": SalaryComplaintStatus.LABELS.get(complaint.status, "Không có") if complaint else "Chưa có khiếu nại",
            "complaint_title": complaint.title if complaint else None,
            "complaint_description": complaint.description if complaint else None,
        }