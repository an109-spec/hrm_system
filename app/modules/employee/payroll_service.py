from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import os
import uuid

from werkzeug.utils import secure_filename

from app.extensions.db import db
from app.models import Complaint, Employee, Notification, Salary, User
from app.models.file_upload import FileUpload
from app.models.dependent import Dependent


class EmployeePayrollService:
    ISSUE_TYPES = {
        "attendance_issue",
        "ot_issue",
        "allowance_issue",
        "tax_issue",
        "insurance_issue",
        "deduction_issue",
        "other",
    }

    STATUS_LABELS = {
        "pending": "Chờ xử lý",
        "approved": "Đã duyệt",
        "paid": "Đã chuyển khoản",
        "finalized": "Đã chốt",
        "complaint": "Có khiếu nại",
    }

    COMPLAINT_STATUS_LABELS = {
        "pending": "⏳ Đang xử lý",
        "in_progress": "⏳ Đang xử lý",
        "resolved": "✅ Đã giải quyết",
        "rejected": "❌ Từ chối",
    }

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
    def _insurance_and_tax(salary: Salary, dependent_count: int) -> tuple[float, float, float]:
        gross = Decimal(str(salary.basic_salary or 0)) + Decimal(str(salary.total_allowance or 0)) + Decimal(str(salary.bonus or 0))
        deduction = Decimal(str(salary.penalty or 0))
        insurance = (gross * Decimal("0.105")).quantize(Decimal("1."))
        family_deduction = Decimal("11000000") + Decimal("4400000") * Decimal(dependent_count)
        taxable_income = max(Decimal("0"), gross - deduction - insurance - family_deduction)
        tax = (taxable_income * Decimal("0.1")).quantize(Decimal("1."))
        return float(insurance), float(tax), float(family_deduction)

    @staticmethod
    def _latest_salary_complaint(employee_id: int, salary_id: int) -> Complaint | None:
        return (
            Complaint.query.filter_by(employee_id=employee_id, salary_id=salary_id)
            .order_by(Complaint.created_at.desc())
            .first()
        )

    @staticmethod
    def payroll_history(user_id: int | None, filters: dict) -> dict:
        employee = EmployeePayrollService._get_employee(user_id)
        year = int(filters.get("year") or datetime.now(timezone.utc).year)
        payroll_status = (filters.get("status") or "").strip()
        paid_state = (filters.get("paid_state") or "").strip()
        complaint_only = str(filters.get("has_complaint") or "").lower() in {"1", "true", "yes"}

        query = Salary.query.filter_by(employee_id=employee.id, year=year, is_deleted=False)
        if payroll_status:
            query = query.filter(Salary.status == payroll_status)
        if paid_state == "paid":
            query = query.filter(Salary.status == "paid")
        if paid_state == "unpaid":
            query = query.filter(Salary.status != "paid")

        rows = query.order_by(Salary.month.desc()).all()
        dependent_count = EmployeePayrollService._dependent_count(employee.id)
        payload = []

        for row in rows:
            complaint = EmployeePayrollService._latest_salary_complaint(employee.id, row.id)
            if complaint_only and not complaint:
                continue
            insurance, tax, _ = EmployeePayrollService._insurance_and_tax(row, dependent_count)
            payload.append(
                {
                    "id": row.id,
                    "month": row.month,
                    "year": row.year,
                    "basic_salary": float(row.basic_salary or 0),
                    "allowance": float(row.total_allowance or 0),
                    "overtime": 0,
                    "deduction": float(row.penalty or 0),
                    "insurance": insurance,
                    "tax": tax,
                    "net_salary": float(row.net_salary or 0),
                    "status": row.status,
                    "status_label": EmployeePayrollService.STATUS_LABELS.get(row.status, row.status),
                    "payment_date": row.updated_at.strftime("%d/%m/%Y") if row.updated_at else None,
                    "has_complaint": bool(complaint),
                    "complaint_status": complaint.status if complaint else None,
                    "complaint_status_label": EmployeePayrollService.COMPLAINT_STATUS_LABELS.get(complaint.status, "💬 Đã phản hồi") if complaint else None,
                }
            )

        latest = payload[0] if payload else None
        return {
            "summary": {
                "period": f"{latest['month']:02d}/{latest['year']}" if latest else "--",
                "net_salary": latest["net_salary"] if latest else 0,
                "status": latest["status_label"] if latest else "--",
                "payment_date": latest["payment_date"] if latest else "--",
                "complaint_status": latest["complaint_status_label"] if latest and latest.get("complaint_status_label") else "Không có",
                "title": f"Lương tháng {latest['month']:02d}/{latest['year']}" if latest else "Chưa có kỳ lương",
            },
            "items": payload,
            "number_of_dependents": dependent_count,
        }

    @staticmethod
    def payroll_detail(user_id: int | None, salary_id: int) -> dict:
        employee = EmployeePayrollService._get_employee(user_id)
        row = Salary.query.filter_by(id=salary_id, employee_id=employee.id, is_deleted=False).first()
        if not row:
            raise ValueError("Không tìm thấy phiếu lương")

        dependent_count = EmployeePayrollService._dependent_count(employee.id)
        insurance, tax, family_deduction = EmployeePayrollService._insurance_and_tax(row, dependent_count)
        return {
            "id": row.id,
            "month": row.month,
            "year": row.year,
            "basic_salary": float(row.basic_salary or 0),
            "lunch_allowance": float(row.total_allowance or 0) * 0.5,
            "responsibility_allowance": float(row.total_allowance or 0) * 0.5,
            "bonus": float(row.bonus or 0),
            "overtime": 0,
            "deduction": float(row.penalty or 0),
            "insurance": insurance,
            "tax": tax,
            "number_of_dependents": dependent_count,
            "family_deduction": family_deduction,
            "net_salary": float(row.net_salary or 0),
            "status_label": EmployeePayrollService.STATUS_LABELS.get(row.status, row.status),
            "employee_name": employee.full_name,
        }

    @staticmethod
    def _pdf_content(lines: list[str]) -> bytes:
        y = 790
        text_lines = ["BT", "/F1 12 Tf"]
        for line in lines:
            safe = line.replace("(", "[").replace(")", "]")
            text_lines.append(f"50 {y} Td ({safe}) Tj")
            y -= 22
        text_lines.append("ET")
        stream = "\n".join(text_lines)
        pdf = f"""%PDF-1.1
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length {len(stream)} >>
stream
{stream}
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000117 00000 n 
0000000243 00000 n 
0000000500 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
570
%%EOF"""
        return pdf.encode("latin-1", "ignore")

    @staticmethod
    def payslip_pdf(user_id: int | None, salary_id: int) -> tuple[str, bytes]:
        detail = EmployeePayrollService.payroll_detail(user_id, salary_id)
        lines = [
            f"PHIEU LUONG {detail['month']:02d}/{detail['year']}",
            f"Nhan vien: {detail['employee_name']}",
            f"Luong co ban: {detail['basic_salary']:,.0f} VND",
            f"Phu cap an trua: {detail['lunch_allowance']:,.0f} VND",
            f"Phu cap trach nhiem: {detail['responsibility_allowance']:,.0f} VND",
            f"Thuong: {detail['bonus']:,.0f} VND",
            f"Khau tru: {detail['deduction']:,.0f} VND",
            f"Bao hiem: {detail['insurance']:,.0f} VND",
            f"Thue TNCN: {detail['tax']:,.0f} VND",
            f"So nguoi phu thuoc: {detail['number_of_dependents']}",
            f"Giam tru gia canh: {detail['family_deduction']:,.0f} VND",
            f"Tong thuc nhan: {detail['net_salary']:,.0f} VND",
        ]
        filename = f"payslip_{detail['month']:02d}_{detail['year']}.pdf"
        return filename, EmployeePayrollService._pdf_content(lines)

    @staticmethod
    def submit_complaint(user_id: int | None, salary_id: int, issue_type: str, description: str, attachment) -> dict:
        employee = EmployeePayrollService._get_employee(user_id)
        row = Salary.query.filter_by(id=salary_id, employee_id=employee.id, is_deleted=False).first()
        if not row:
            raise ValueError("Không tìm thấy phiếu lương")
        if issue_type not in EmployeePayrollService.ISSUE_TYPES:
            raise ValueError("Loại khiếu nại không hợp lệ")
        if not description.strip():
            raise ValueError("Nội dung chi tiết là bắt buộc")

        complaint = Complaint(
            employee_id=employee.id,
            salary_id=row.id,
            type="salary",
            title=f"Khiếu nại phiếu lương #{row.id}",
            description=description.strip(),
            status="pending",
            admin_reply=f"Issue type: {issue_type}",
        )
        db.session.add(complaint)
        db.session.flush()

        if attachment and attachment.filename:
            ext = attachment.filename.rsplit(".", 1)[-1].lower() if "." in attachment.filename else ""
            if ext not in {"jpg", "jpeg", "png", "pdf"}:
                raise ValueError("File đính kèm chỉ chấp nhận ảnh hoặc PDF")
            save_dir = os.path.join("app", "static", "uploads", "complaint")
            os.makedirs(save_dir, exist_ok=True)
            filename = secure_filename(attachment.filename)
            unique_name = f"{uuid.uuid4().hex}_{filename}"
            attachment.save(os.path.join(save_dir, unique_name))
            db.session.add(
                FileUpload(
                    file_name=filename,
                    file_url=f"/static/uploads/complaint/{unique_name}",
                    file_type="attachment",
                    uploaded_by=user_id,
                    complaint_id=complaint.id,
                )
            )

        db.session.add(Notification(user_id=employee.user_id, title="Đã tiếp nhận khiếu nại lương", content=f"Yêu cầu #{complaint.id} đang chờ Manager review bước 1", type="complaint", link="/employee/payslip"))
        if employee.manager and employee.manager.user_id:
            db.session.add(Notification(user_id=employee.manager.user_id, title="Complaint lương cần review", content=f"{employee.full_name} gửi khiếu nại payroll #{row.id}", type="complaint", link="/manager/payroll"))

        hr_users = User.query.join(User.role).filter(User.role.has(name="hr"), User.is_deleted.is_(False)).all()
        for hr in hr_users[:3]:
            db.session.add(Notification(user_id=hr.id, title="Complaint lương mới", content=f"Có complaint lương từ {employee.full_name}", type="complaint", link="/hr/payroll"))

        db.session.commit()
        return {"message": "Đã gửi khiếu nại lương", "complaint_id": complaint.id}

    @staticmethod
    def salary_complaints(user_id: int | None) -> list[dict]:
        employee = EmployeePayrollService._get_employee(user_id)
        rows = (
            Complaint.query.filter_by(employee_id=employee.id)
            .filter(Complaint.salary_id.isnot(None))
            .order_by(Complaint.created_at.desc())
            .all()
        )
        return [
            {
                "id": c.id,
                "salary_id": c.salary_id,
                "title": c.title,
                "status": c.status,
                "status_label": EmployeePayrollService.COMPLAINT_STATUS_LABELS.get(c.status, "💬 Đã phản hồi"),
                "created_at": c.created_at.strftime("%d/%m/%Y %H:%M") if c.created_at else None,
                "closed": bool(c.closed_by_employee),
            }
            for c in rows
        ]

    @staticmethod
    def close_salary_complaint(user_id: int | None, complaint_id: int) -> dict:
        employee = EmployeePayrollService._get_employee(user_id)
        complaint = Complaint.query.filter_by(id=complaint_id, employee_id=employee.id).first()
        if not complaint:
            raise ValueError("Không tìm thấy khiếu nại")
        complaint.closed_by_employee = True
        complaint.closed_at = datetime.now(timezone.utc)
        complaint.status = "resolved"
        db.session.add(Notification(user_id=employee.user_id, title="✅ Đã đóng khiếu nại", content=f"Bạn đã đóng khiếu nại #{complaint.id}", type="complaint", link="/employee/payslip"))
        db.session.commit()
        return {"message": "Đóng khiếu nại thành công"}