from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import os
import re
import uuid

from werkzeug.utils import secure_filename

from app.extensions.db import db
from app.models import Attendance, Complaint, Dependent, Employee, HistoryLog, Notification, OvertimeRequest, Salary, User
from app.models.file_upload import FileUpload


class EmployeeESSService:
    RELATIONSHIPS = {"con", "vo_chong", "bo", "me", "khac"}
    COMPLAINT_ISSUES = {"salary_data_error", "content_question", "system_error", "other"}

    @staticmethod
    def _employee_by_user(user_id: int | None) -> Employee:
        employee = Employee.query.filter_by(user_id=user_id, is_deleted=False).first()
        if not employee:
            raise ValueError("Không tìm thấy hồ sơ nhân viên")
        return employee

    @staticmethod
    def _serialize_dependent(row: Dependent) -> dict:
        return {
            "id": row.id,
            "full_name": row.full_name,
            "dob": row.dob.isoformat() if row.dob else None,
            "relationship": row.relationship,
            "tax_code": row.tax_code,
            "is_valid": bool(row.is_valid),
            "note": getattr(row, "note", None),
        }

    @staticmethod
    def list_dependents(user_id: int | None) -> dict:
        employee = EmployeeESSService._employee_by_user(user_id)
        rows = Dependent.query.filter_by(employee_id=employee.id, is_deleted=False).order_by(Dependent.created_at.desc()).all()
        count = sum(1 for x in rows if x.is_valid and not x.is_deleted)
        return {"items": [EmployeeESSService._serialize_dependent(x) for x in rows], "number_of_dependents": count}

    @staticmethod
    def _validate_dependent(data: dict):
        if not (data.get("full_name") or "").strip():
            raise ValueError("Họ tên người phụ thuộc là bắt buộc")
        if data.get("relationship") not in EmployeeESSService.RELATIONSHIPS:
            raise ValueError("Quan hệ không hợp lệ")
        if data.get("tax_code") and not re.fullmatch(r"[0-9]{10,13}", str(data["tax_code"]).strip()):
            raise ValueError("Mã số thuế cá nhân phải có 10-13 chữ số")

    @staticmethod
    def create_dependent(user_id: int | None, payload: dict, actor_user_id: int | None = None) -> dict:
        employee = EmployeeESSService._employee_by_user(user_id)
        EmployeeESSService._validate_dependent(payload)
        dob = date.fromisoformat(payload.get("dob"))
        if dob > date.today():
            raise ValueError("Ngày sinh không hợp lệ")

        row = Dependent(
            employee_id=employee.id,
            full_name=payload["full_name"].strip(),
            dob=dob,
            relationship=payload["relationship"],
            tax_code=(payload.get("tax_code") or "").strip() or None,
            is_valid=bool(payload.get("is_valid", True)),
            note=(payload.get("note") or "").strip() or None,
        )
        db.session.add(row)
        db.session.flush()
        db.session.add(
            HistoryLog(
                employee_id=employee.id,
                action="EMPLOYEE_DEPENDENT_CREATED",
                entity_type="dependent",
                entity_id=row.id,
                description=f"Nhân viên tạo người phụ thuộc {row.full_name}",
                performed_by=actor_user_id,
            )
        )
        db.session.commit()
        return {"message": "Thêm người phụ thuộc thành công", "item": EmployeeESSService._serialize_dependent(row)}

    @staticmethod
    def update_dependent(user_id: int | None, dependent_id: int, payload: dict, actor_user_id: int | None = None) -> dict:
        employee = EmployeeESSService._employee_by_user(user_id)
        row = Dependent.query.filter_by(id=dependent_id, employee_id=employee.id, is_deleted=False).first()
        if not row:
            raise ValueError("Không tìm thấy người phụ thuộc")
        EmployeeESSService._validate_dependent(payload)
        row.full_name = payload["full_name"].strip()
        row.relationship = payload["relationship"]
        row.tax_code = (payload.get("tax_code") or "").strip() or None
        row.is_valid = bool(payload.get("is_valid", True))
        row.dob = date.fromisoformat(payload.get("dob"))
        row.note = (payload.get("note") or "").strip() or None
        db.session.add(
            HistoryLog(
                employee_id=employee.id,
                action="EMPLOYEE_DEPENDENT_UPDATED",
                entity_type="dependent",
                entity_id=row.id,
                description=f"Nhân viên cập nhật người phụ thuộc {row.full_name}",
                performed_by=actor_user_id,
            )
        )
        db.session.commit()
        return {"message": "Cập nhật người phụ thuộc thành công", "item": EmployeeESSService._serialize_dependent(row)}

    @staticmethod
    def delete_dependent(user_id: int | None, dependent_id: int, actor_user_id: int | None = None) -> dict:
        employee = EmployeeESSService._employee_by_user(user_id)
        row = Dependent.query.filter_by(id=dependent_id, employee_id=employee.id, is_deleted=False).first()
        if not row:
            raise ValueError("Không tìm thấy người phụ thuộc")
        used = Salary.query.filter_by(employee_id=employee.id, status="finalized").first()
        if used:
            raise ValueError("Không thể xóa người phụ thuộc đã dùng cho payroll finalized")
        row.is_deleted = True
        db.session.add(
            HistoryLog(
                employee_id=employee.id,
                action="EMPLOYEE_DEPENDENT_DELETED",
                entity_type="dependent",
                entity_id=row.id,
                description=f"Nhân viên xóa người phụ thuộc {row.full_name}",
                performed_by=actor_user_id,
            )
        )
        db.session.commit()
        return {"message": "Đã xóa người phụ thuộc"}

    @staticmethod
    def submit_overtime(user_id: int | None, payload: dict, actor_user_id: int | None = None) -> dict:
        employee = EmployeeESSService._employee_by_user(user_id)
        ot_date = date.fromisoformat(payload.get("overtime_date"))
        hours = Decimal(str(payload.get("overtime_hours") or "0"))
        if hours <= 0:
            raise ValueError("Số giờ OT phải lớn hơn 0")
        reason = (payload.get("reason") or "").strip()
        if not reason:
            raise ValueError("Lý do OT là bắt buộc")
        request_ot = OvertimeRequest(
            employee_id=employee.id,
            overtime_date=ot_date,
            overtime_hours=hours,
            reason=reason,
            note=(payload.get("note") or "").strip() or None,
            status="pending_manager",
        )
        db.session.add(request_ot)
        if employee.manager and employee.manager.user_id:
            db.session.add(Notification(user_id=employee.manager.user_id, title="Yêu cầu tăng ca mới", content=f"{employee.full_name} gửi OT {ot_date.isoformat()} ({hours}h)", type="overtime", link="/manager/attendance"))
        db.session.add(HistoryLog(employee_id=employee.id, action="OVERTIME_SUBMITTED", entity_type="overtime_request", entity_id=None, description=f"Gửi yêu cầu OT {ot_date} - {hours}h", performed_by=actor_user_id))
        db.session.commit()
        return {"message": "Đã gửi yêu cầu tăng ca thành công"}

    @staticmethod
    def notification_detail(user_id: int, noti_id: int) -> dict:
        noti = Notification.query.filter_by(id=noti_id, user_id=user_id, is_deleted=False).first()
        if not noti:
            raise ValueError("Không tìm thấy thông báo")
        noti.is_read = True
        db.session.commit()
        return {
            "id": noti.id,
            "type": noti.type,
            "title": noti.title,
            "content": noti.content,
            "link": noti.link,
            "received_at": noti.created_at.isoformat() if noti.created_at else None,
            "is_read": noti.is_read,
        }

    @staticmethod
    def submit_notification_complaint(user: User, employee: Employee, noti_id: int, issue_type: str, description: str, attachment) -> dict:
        noti = Notification.query.filter_by(id=noti_id, user_id=user.id, is_deleted=False).first()
        if not noti:
            raise ValueError("Notification không tồn tại")
        if issue_type not in EmployeeESSService.COMPLAINT_ISSUES:
            raise ValueError("Loại vấn đề không hợp lệ")
        if not description.strip():
            raise ValueError("Nội dung phản hồi là bắt buộc")

        complaint = Complaint(
            employee_id=employee.id,
            user_id=user.id,
            notification_id=noti.id,
            type=noti.type or issue_type,
            title=f"[Notification #{noti.id}] {noti.title}",
            description=description.strip(),
            status="pending",
        )
        db.session.add(complaint)
        db.session.flush()

        if attachment and attachment.filename:
            filename = secure_filename(attachment.filename)
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in {"jpg", "jpeg", "png", "pdf", "doc", "docx"}:
                raise ValueError("File đính kèm không hợp lệ")
            save_dir = os.path.join("app", "static", "uploads", "complaint")
            os.makedirs(save_dir, exist_ok=True)
            unique_name = f"{uuid.uuid4().hex}_{filename}"
            fullpath = os.path.join(save_dir, unique_name)
            attachment.save(fullpath)
            file_type = "image" if ext in {"jpg", "jpeg", "png"} else ("pdf" if ext == "pdf" else "doc")
            db.session.add(
                FileUpload(
                    file_name=filename,
                    file_url=f"/static/uploads/complaint/{unique_name}",
                    file_type=file_type,
                    uploaded_by=user.id,
                    complaint_id=complaint.id,
                )
            )

        db.session.add(Notification(user_id=user.id, title="Tiếp nhận khiếu nại", content=f"Đã ghi nhận phản hồi cho thông báo #{noti.id}. Mã khiếu nại #{complaint.id}", type="complaint", link="/employee/notifications"))
        db.session.commit()
        return {"message": "Gửi phản hồi thành công", "complaint_id": complaint.id}

    @staticmethod
    def close_complaint(user_id: int | None, complaint_id: int) -> dict:
        employee = EmployeeESSService._employee_by_user(user_id)
        complaint = Complaint.query.filter_by(id=complaint_id, employee_id=employee.id).first()
        if not complaint:
            raise ValueError("Không tìm thấy khiếu nại")
        if complaint.closed_by_employee:
            raise ValueError("Khiếu nại đã được đóng")
        complaint.closed_by_employee = True
        complaint.closed_at = datetime.now(timezone.utc)
        complaint.status = "resolved"
        db.session.add(Notification(user_id=employee.user_id, title="Khiếu nại đã đóng", content=f"Bạn đã đóng khiếu nại #{complaint.id}", type="complaint"))
        db.session.commit()
        return {"message": "Đóng khiếu nại thành công"}