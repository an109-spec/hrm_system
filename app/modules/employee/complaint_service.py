from __future__ import annotations

from datetime import datetime
import os
import uuid

from werkzeug.utils import secure_filename

from app.extensions.db import db
from app.models import (
    Complaint,
    Employee,
    Notification,
    User,
)
from app.models.file_upload import FileUpload

from app.utils.time import get_current_time


class EmployeeComplaintService:
    COMPLAINT_ISSUES = {
        "salary_data_error",
        "content_question",
        "system_error",
        "other",
    }

    @staticmethod
    def _employee_by_user(
        user_id: int | None
    ) -> Employee:
        employee = Employee.query.filter_by(
            user_id=user_id,
            is_deleted=False
        ).first()
        if not employee:
            raise ValueError(
                "Không tìm thấy hồ sơ nhân viên"
            )
        return employee
    
    @staticmethod
    def create_complaint_from_notification(
        user: User,
        employee: Employee,
        noti_id: int,
        issue_type: str,
        description: str,
        attachment,
    ) -> dict:
        now = get_current_time()
        noti = Notification.query.filter_by(
            id=noti_id,
            user_id=user.id,
            is_deleted=False
        ).first()
        if not noti:
            raise ValueError(
                "Notification không tồn tại"
            )
        if issue_type not in (
            EmployeeComplaintService.COMPLAINT_ISSUES
        ):
            raise ValueError(
                "Loại vấn đề không hợp lệ"
            )
        if not description.strip():
            raise ValueError(
                "Nội dung phản hồi là bắt buộc"
            )
        complaint = Complaint(
            employee_id=employee.id,
            user_id=user.id,
            notification_id=noti.id,
            type=noti.type or issue_type,
            title=(
                f"[Notification #{noti.id}] "
                f"{noti.title}"
            ),
            description=description.strip(),
            status="pending",
            created_at=now,
        )
        db.session.add(complaint)
        db.session.flush()
        if attachment and attachment.filename:
            filename = secure_filename(
                attachment.filename
            )
            ext = (
                filename.rsplit(".", 1)[-1].lower()
                if "." in filename
                else ""
            )
            allowed_exts = {
                "jpg",
                "jpeg",
                "png",
                "pdf",
                "doc",
                "docx",
            }
            if ext not in allowed_exts:
                raise ValueError(
                    "File đính kèm không hợp lệ"
                )
            save_dir = os.path.join(
                "app",
                "static",
                "uploads",
                "complaint",
            )
            os.makedirs(
                save_dir,
                exist_ok=True
            )
            unique_name = (
                f"{uuid.uuid4().hex}_{filename}"
            )
            fullpath = os.path.join(
                save_dir,
                unique_name
            )
            attachment.save(fullpath)
            file_type = (
                "image"
                if ext in {
                    "jpg",
                    "jpeg",
                    "png",
                }
                else (
                    "pdf"
                    if ext == "pdf"
                    else "doc"
                )
            )
            db.session.add(
                FileUpload(
                    file_name=filename,
                    file_url=(
                        "/static/uploads/"
                        f"complaint/{unique_name}"
                    ),
                    file_type=file_type,
                    uploaded_by=user.id,
                    complaint_id=complaint.id,
                    created_at=now,
                )
            )
        db.session.add(
            Notification(
                user_id=user.id,
                title="Tiếp nhận khiếu nại",
                content=(
                    "Đã ghi nhận phản hồi cho "
                    f"thông báo #{noti.id}. "
                    f"Mã khiếu nại #{complaint.id}"
                ),
                type="complaint",
                link="/employee/notifications",
                created_at=now,
            )
        )
        db.session.commit()
        return {
            "message": "Gửi phản hồi thành công",
            "complaint_id": complaint.id,
        }

    @staticmethod
    def close_complaint(
        user_id: int | None,
        complaint_id: int,
    ) -> dict:
        now = get_current_time()
        employee = (
            EmployeeComplaintService
            ._employee_by_user(user_id)
        )
        complaint = Complaint.query.filter_by(
            id=complaint_id,
            employee_id=employee.id,
        ).first()
        if not complaint:
            raise ValueError(
                "Không tìm thấy khiếu nại"
            )
        if complaint.closed_by_employee:
            raise ValueError(
                "Khiếu nại đã được đóng"
            )
        complaint.closed_by_employee = True
        complaint.closed_at = now
        complaint.status = "resolved"
        db.session.add(
            Notification(
                user_id=employee.user_id,
                title="Khiếu nại đã đóng",
                content=(
                    f"Bạn đã đóng khiếu nại "
                    f"#{complaint.id}"
                ),
                type="complaint",
                created_at=now,
            )
        )
        db.session.commit()
        return {
            "message": "Đóng khiếu nại thành công"
        }