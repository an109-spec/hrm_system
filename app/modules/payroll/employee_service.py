from __future__ import annotations
from decimal import Decimal
import re

from sqlalchemy import extract
from app.constants.holidays import VN_FIXED_PUBLIC_HOLIDAYS, HolidayConfig
from app.models.attendance import Attendance
from app.models.leave import LeaveRequest, LeaveType
from app.constants.leave import LeaveStatus
from calendar import monthrange
from datetime import date, timedelta
from app.utils.time import get_current_time
from app.extensions.db import db
from app.models import Complaint, Notification, Salary, Employee, HistoryLog
from app.constants.payroll import SalaryStatus, SalaryComplaintStatus, PayrollIssueType
from app.modules.payroll.base_service import BasePayrollService, PersonalPayrollService
from app.utils.upload_service import UploadService
class EmployeePayrollService(PersonalPayrollService):

    @staticmethod
    def submit_complaint_from_noti(user_id: int | None, noti_id: int, issue_type: str, description: str, attachment=None) -> dict:
        """
        Gửi khiếu nại dựa trên ngữ cảnh từ một thông báo (Notification).
        Thường dùng khi nhân viên bấm 'Khiếu nại' ngay từ link trong thông báo nhận lương.
        """
        # 1. Kiểm tra thông báo có tồn tại và thuộc về user này không
        noti = Notification.query.filter_by(id=noti_id, user_id=user_id).first()
        if not noti:
            raise ValueError("Thông báo không tồn tại hoặc bạn không có quyền truy cập.")
            
        # 2. Kiểm tra link trong thông báo
        if not noti.link:
            raise ValueError("Thông báo này không chứa liên kết hợp lệ để thực hiện khiếu nại.")

        # 3. Sử dụng Regex để bóc tách salary_id từ link (ví dụ: /employee/payslip/123)
        match = re.search(r'/(\d+)$', noti.link)
        if not match:
            raise ValueError("Không tìm thấy mã phiếu lương hợp lệ từ thông báo này.")

        salary_id = int(match.group(1))

        # 4. Ủy quyền (Delegate) việc xử lý cho hàm submit_complaint đã có logic chốt chặn
        # Việc gọi lại hàm này giúp tái sử dụng logic kiểm tra phòng ban và manager
        return EmployeePayrollService.submit_complaint(
            user_id=user_id,
            salary_id=salary_id,
            issue_type=issue_type,
            description=description,
            attachment=attachment
        )

    @staticmethod
    def submit_complaint(user_id: int | None, salary_id: int, issue_type: str, description: str, attachment=None) -> dict:
        employee = BasePayrollService._get_employee(user_id)
        if not employee.department_id:
            raise ValueError("Tài khoản của bạn chưa được phân vào phòng ban nào. Vui lòng liên hệ bộ phận nhân sự để cập nhật thông tin trước khi gửi khiếu nại.")

        # 1. Kiểm tra sự tồn tại và quyền sở hữu phiếu lương
        salary = Salary.query.filter_by(id=salary_id, employee_id=employee.id, is_deleted=False).first()
        if not salary:
            raise ValueError("Không tìm thấy thông tin lương để khiếu nại.")

        # 2. Kiểm tra khiếu nại trùng lặp
        existing_complaint = Complaint.query.filter_by(
            salary_id=salary_id, 
            status=SalaryComplaintStatus.PENDING,
            is_deleted=False
        ).first()
        if existing_complaint:
            raise ValueError("Kỳ lương này đang có một khiếu nại chờ xử lý.")

        # --- CHỐT CHẶN 2: Xác định Quản lý (Manager) xử lý đơn ---
        target_manager_id = employee.manager_id
        if not target_manager_id and employee.department:
            target_manager_id = employee.department.manager_id
            
        if not target_manager_id:
            raise ValueError("Phòng ban của bạn hiện chưa có Quản lý phụ trách. Vui lòng báo cáo trực tiếp với nhân sự.")

        # 3. Khởi tạo đối tượng Complaint
        issue_label = PayrollIssueType.LABELS.get(issue_type, "Vấn đề khác")
        complaint_title = f"Khiếu nại lương {salary.month:02d}/{salary.year} - {issue_label}"

        new_complaint = Complaint(
            employee_id=employee.id,
            user_id=user_id,
            salary_id=salary_id,
            type='salary',
            title=complaint_title,
            description=description,
            status=SalaryComplaintStatus.PENDING,
            handled_by=target_manager_id
        )

        # 4. Cập nhật trạng thái bảng lương
        salary.status = SalaryStatus.COMPLAINT
        
        db.session.add(new_complaint)
        # Bắn dữ liệu xuống DB tạm thời để lấy ID cho Complaint
        db.session.flush() 

        # --- MỚI: XỬ LÝ FILE ĐÍNH KÈM ---
        if attachment:
            # Nếu attachment là danh sách nhiều file (khi dùng request.files.getlist)
            if isinstance(attachment, list):
                for file in attachment:
                    UploadService.save_file(
                        file=file,
                        user_id=user_id,
                        entity_type='complaint',
                        entity_id=new_complaint.id
                    )
            # Nếu chỉ là 1 file đơn lẻ
            else:
                UploadService.save_file(
                    file=attachment,
                    user_id=user_id,
                    entity_type='complaint',
                    entity_id=new_complaint.id
                )

        # 5. Thông báo cho Manager/Trưởng phòng
        manager_user = db.session.query(Employee.user_id).filter(Employee.id == target_manager_id).first()
        if manager_user and manager_user.user_id:
            db.session.add(Notification(
                user_id=manager_user.user_id,
                title="🔔 Khiếu nại lương cần duyệt",
                content=f"Nhân viên {employee.full_name} ({employee.department.name}) vừa gửi khiếu nại lương.",
                type="complaint",
                link=f"payroll/complaints/<int:complaint_id>"
            ))

        # 6. Ghi Log
        HistoryLog.append(
            employee_id=employee.id,
            action="SUBMIT_COMPLAINT",
            entity_type="salary",
            entity_id=salary.id,
            description=f"Gửi khiếu nại tới {employee.department.name}",
            performed_by=user_id
        )

        db.session.commit()
        
        return {
            "message": "Gửi khiếu nại thành công đến Quản lý phòng ban.",
            "complaint_id": new_complaint.id
        }
    @staticmethod
    def salary_complaints(user_id: int | None) -> list[dict]:
        """Hàm dành cho FE: Xem danh sách khiếu nại lương của chính mình."""
        employee = BasePayrollService._get_employee(user_id)
        results = (
            db.session.query(Complaint, Salary)
            .join(Salary, Complaint.salary_id == Salary.id)
            .filter(
                Complaint.employee_id == employee.id,
                Complaint.is_deleted == False,
                Complaint.salary_id.isnot(None)
            )
            .order_by(Complaint.created_at.desc())
            .all()
        )
        return [
            {
                "id": complaint.id,
                "salary_id": complaint.salary_id,
                "title": complaint.title,
                "salary_period": f"Tháng {salary.month:02d}/{salary.year}",
                "status": complaint.status,
                "status_label": SalaryComplaintStatus.LABELS.get(
                    complaint.status, "💬 Đã có phản hồi"
                ),
                "created_at": complaint.created_at.strftime("%d/%m/%Y %H:%M") if complaint.created_at else None,
                "closed": bool(complaint.closed_by_employee),
                "net_salary_impacted": float(salary.net_salary or 0)
            } for complaint, salary in results
        ]
    
    @staticmethod
    def complaint_detail(user_id: int | None, complaint_id: int) -> dict:
        """Xem chi tiết một đơn khiếu nại cụ thể (Dành cho cá nhân)"""
        employee = BasePayrollService._get_employee(user_id)
        complaint = Complaint.query.filter_by(
            id=complaint_id, 
            employee_id=employee.id, 
            is_deleted=False
        ).first()
        
        if not complaint:
            raise ValueError("Không tìm thấy khiếu nại hoặc bạn không có quyền xem đơn này")
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
            "description": complaint.description,  # Đã sửa: content -> description
            "type": complaint.type,
            "status": complaint.status,
            "status_label": SalaryComplaintStatus.LABELS.get(complaint.status),
            "priority": complaint.priority,
            "created_at": complaint.created_at.strftime("%d/%m/%Y %H:%M"),
            "admin_reply": complaint.admin_reply,
            "resolved_at": complaint.resolved_at.strftime("%d/%m/%Y %H:%M") if complaint.resolved_at else None,
            "handler_name": complaint.handler.full_name if complaint.handler else "Đang chờ phân công",
            "attachments": file_list,
            
            # Thông tin lương liên quan (nếu có)
            "salary_period": f"Tháng {complaint.salary.month:02d}/{complaint.salary.year}" if complaint.salary else "N/A"
        }
    @staticmethod
    def close_salary_complaint(user_id: int | None, complaint_id: int) -> dict:
        employee = BasePayrollService._get_employee(user_id)
        
        # 1. Lấy thông tin khiếu nại
        complaint = Complaint.query.filter_by(id=complaint_id, employee_id=employee.id).first()
        if not complaint:
            raise ValueError("Không tìm thấy khiếu nại")
            
        # Chỉ cho phép hủy khi đơn còn đang ở trạng thái Chờ (Pending)
        if complaint.status != SalaryComplaintStatus.PENDING:
            current_label = SalaryComplaintStatus.LABELS.get(complaint.status, complaint.status)
            raise ValueError(f"Không thể hủy đơn vì khiếu nại đang ở trạng thái: {current_label}")

        # 2. Cập nhật trạng thái khiếu nại
        complaint.closed_by_employee = True
        complaint.closed_at = get_current_time()
        complaint.status = SalaryComplaintStatus.RESOLVED  # Hoặc ông có thể dùng một status 'CANCELLED' nếu muốn phân biệt
        
        # 3. CẬP NHẬT TRẠNG THÁI PHIẾU LƯƠNG (MỚI)
        # Nếu khiếu nại này gắn với một phiếu lương, ta trả lương về trạng thái 'SENT' (Đã gửi)
        if complaint.salary:
            complaint.salary.status = SalaryStatus.SENT 
            # Note: Sau khi trả về SENT, Manager có thể tiếp tục bấm Duyệt/Trả lương như bình thường.

        # 4. Bắn thông báo (Giữ nguyên logic của ông)
        db.session.add(Notification(
            user_id=employee.user_id, 
            title="✅ Đã đóng khiếu nại", 
            content=f"Bạn đã đóng khiếu nại #{complaint.id}", 
            type="complaint", 
            link="payroll/complaints/<int:complaint_id>/close"
        ))
        
        if employee.manager and employee.manager.user_id:
            db.session.add(Notification(
                user_id=employee.manager.user_id,
                title="Đơn khiếu nại đã hủy",
                content=f"{employee.full_name} đã tự đóng đơn khiếu nại #{complaint.id}",
                type="complaint",
                link="/manager/payroll"
            ))

        db.session.commit()
        return {"message": "Đóng khiếu nại thành công, phiếu lương đã được mở khóa."}

    @staticmethod
    def calculate_total_raw_overtime(employee_id: int, month: int, year: int) -> Decimal:
        """
        Tính tổng số giờ tăng ca thực tế (Raw) của nhân viên trong tháng.
        Không nhân hệ số (multiplier).
        """
        from app.models.overtime_request import OvertimeRequest
        approved_requests = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.status == "approved",
            db.extract("month", OvertimeRequest.overtime_date) == month,
            db.extract("year", OvertimeRequest.overtime_date) == year,
            OvertimeRequest.is_deleted.is_(False)
        ).all()
        total_raw = sum([req.approved_hours or Decimal("0.00") for req in approved_requests], Decimal("0.00"))
        return total_raw.quantize(Decimal("0.01"))
    
    @staticmethod
    def calculate_total_weighted_overtime(employee_id: int, month: int, year: int) -> Decimal:
        """
        Tính tổng số giờ tăng ca đã nhân hệ số (weighted) của nhân viên trong tháng.
        Chỉ tính các đơn đã có trạng thái 'approved'.
        """
        from app.models.overtime_request import OvertimeRequest
        approved_requests = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.status == "approved", # Chỉ lấy đơn đã duyệt
            db.extract("month", OvertimeRequest.overtime_date) == month,
            db.extract("year", OvertimeRequest.overtime_date) == year,
            OvertimeRequest.is_deleted.is_(False)
        ).all()
        total_weighted = Decimal("0.00")
        for req in approved_requests:
            hours = req.approved_hours or Decimal("0.00")
            multiplier = req.holiday_multiplier or Decimal("1.00")
            total_weighted += (hours * multiplier)
        return total_weighted.quantize(Decimal("0.01"))
    
    @staticmethod
    def count_late_occurrences(employee_id: int, month: int, year: int) -> int:
        """
        Đếm số lần nhân viên đi muộn trong tháng.
        Chỉ tính các bản ghi có late_minutes > 0.
        """
        count = db.session.query(Attendance).filter(
            Attendance.employee_id == employee_id,
            Attendance.late_minutes > 0,
            extract("month", Attendance.date) == month,
            extract("year", Attendance.date) == year
        ).count()
        
        return count

    @staticmethod
    def get_leave_summary(month: int = None, year: int = None, employee_ids: list = None) -> dict:
        """
        Tính tổng ngày nghỉ có lương và không lương, tự động trừ T7, CN và Ngày lễ.
        Kết quả trả về dạng: { emp_id: {"paid_leave_days": X, "unpaid_leave_days": Y} }
        """
        now = get_current_time()
        month = month if month is not None else now.month
        year = year if year is not None else now.year
        lunar_holidays = HolidayConfig.get_lunar_holidays(year)
        month_start = date(year, month, 1)
        _, last_day = monthrange(year, month)
        month_end = date(year, month, last_day)
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
        summary = {}
        if employee_ids:
            summary = {emp_id: {"paid_leave_days": 0, "unpaid_leave_days": 0} for emp_id in employee_ids}
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
    def get_full_monthly_report(employee_id: int, month: int, year: int) -> dict:
        """
        Hàm tổng hợp tất cả chỉ số (OT, Đi muộn, Ngày nghỉ) thành 1 báo cáo duy nhất cho 1 nhân viên.
        """
        raw_ot = EmployeePayrollService.calculate_total_raw_overtime(employee_id, month, year)
        weighted_ot = EmployeePayrollService.calculate_total_weighted_overtime(employee_id, month, year)
        late_count = EmployeePayrollService.count_late_occurrences(employee_id, month, year)
        leave_data = EmployeePayrollService.get_leave_summary(month=month, year=year, employee_ids=[employee_id])
        employee_leave = leave_data.get(employee_id, {"paid_leave_days": 0, "unpaid_leave_days": 0})
        return {
            "employee_id": employee_id,
            "period": f"{month}/{year}",
            "attendance_metrics": {
                "late_occurrences": late_count,
            },
            "overtime_metrics": {
                "total_raw_hours": raw_ot,
                "total_weighted_hours": weighted_ot,
            },
            "leave_metrics": {
                "paid_leave_days": employee_leave["paid_leave_days"],
                "unpaid_leave_days": employee_leave["unpaid_leave_days"],
            }
        }