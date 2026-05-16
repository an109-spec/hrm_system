from __future__ import annotations
from app.extensions.db import db
from app.models import Notification
from app.utils.time import VN_TIMEZONE, get_current_time
from app.models import Notification, Complaint, FileUpload
from flask import current_app
from werkzeug.utils import secure_filename
import uuid
import os

class EmployeeNotificationService:

    @staticmethod
    def get_notifications(user_id: int, limit: int = 50) -> list[dict]:
        rows = Notification.query.filter_by(
            user_id=user_id,
            is_deleted=False
        ).order_by(Notification.created_at.desc()).limit(limit).all()
        result = []
        for noti in rows:
            received_at = noti.created_at
            if received_at:
                if received_at.tzinfo is None:
                    received_at = received_at.replace(tzinfo=VN_TIMEZONE)
                else:
                    received_at = received_at.astimezone(VN_TIMEZONE)
            result.append({
                "id": noti.id,
                "type": noti.type,
                "title": noti.title,
                "content": noti.content,
                "link": noti.link,
                "is_read": noti.is_read,
                "received_at": received_at, 
            })
        return result

    @staticmethod
    def notification_detail(user_id: int, noti_id: int) -> dict:
        """Lấy chi tiết và đánh dấu đã đọc một thông báo"""
        noti = Notification.query.filter_by(
            id=noti_id,
            user_id=user_id,
            is_deleted=False
        ).first()

        if not noti:
            raise ValueError("Không tìm thấy thông báo")

        # Đánh dấu đã đọc
        if not noti.is_read:
            noti.is_read = True
            db.session.commit()

        # Xử lý thời gian an toàn
        received_at = noti.created_at
        if received_at:
            if received_at.tzinfo is None:
                received_at = received_at.replace(tzinfo=VN_TIMEZONE)
            else:
                received_at = received_at.astimezone(VN_TIMEZONE)

        return {
            "id": noti.id,
            "type": noti.type,
            "title": noti.title,
            "content": noti.content,
            "link": noti.link,
            "received_at": received_at.isoformat() if received_at else None,
            "is_read": noti.is_read,
        }

    @staticmethod
    def get_unread_count(user_id: int) -> int:
        """Đếm số thông báo chưa đọc (để hiện badge trên UI)"""
        return Notification.query.filter_by(
            user_id=user_id, 
            is_read=False, 
            is_deleted=False
        ).count()

    @staticmethod
    def mark_all_as_read(user_id: int):
        """Đánh dấu tất cả thông báo của user là đã đọc"""
        Notification.query.filter_by(
            user_id=user_id, 
            is_read=False, 
            is_deleted=False
        ).update({"is_read": True})
        db.session.commit()

    @staticmethod
    def submit_notification_complaint(user, employee, noti_id: int, issue_type: str, description: str, attachment) -> dict:
        noti = Notification.query.filter_by(id=noti_id, user_id=user.id, is_deleted=False).first()
        if not noti:
            raise ValueError("Không tìm thấy dữ liệu thông báo hợp lệ để gửi phản hồi")
        if not description.strip():
            raise ValueError("Vui lòng nhập nội dung phản hồi chi tiết")
        current_time = get_current_time()
        complaint = Complaint(
            employee_id=employee.id,
            user_id=user.id,
            notification_id=noti.id,
            type=issue_type,
            title=f"Phản hồi về thông báo: {noti.title}",
            description=description.strip(),
            status='pending',    # Trạng thái ban đầu chờ HR/Manager duyệt
            priority='normal',   # Độ ưu tiên mặc định
            created_at=current_time,
            updated_at=current_time
        )
        db.session.add(complaint)
        db.session.flush()
        if attachment and attachment.filename:
            filename = secure_filename(attachment.filename)
            if filename:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in ['.jpg', '.jpeg', '.png', '.pdf', '.docx', '.xlsx']:
                    raise ValueError("Định dạng file đính kèm không được hệ thống hỗ trợ")
                unique_filename = f"complaint_{complaint.id}_{uuid.uuid4().hex}{ext}"
                upload_folder = current_app.config.get("UPLOAD_FOLDER", os.path.join(current_app.instance_path, "uploads"))
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                file_path = os.path.join(upload_folder, unique_filename)
                attachment.save(file_path)
                file_upload = FileUpload(
                    complaint_id=complaint.id,
                    file_name=filename,
                    file_path=f"/static/uploads/{unique_filename}", # Đường dẫn tương đối để frontend download/view
                    created_at=current_time,
                    updated_at=current_time
                )
                db.session.add(file_upload)
        confirmation_noti = Notification(
            user_id=user.id,
            title="📥 Đã tiếp nhận phản hồi thông báo",
            content=f"Hệ thống đã ghi nhận phản hồi của bạn về thông báo '{noti.title}'. Trạng thái hiện tại: Chờ xử lý.",
            link="/employee/notifications",
            type="complaint",
            is_read=False,
            created_at=current_time,
            updated_at=current_time
        )
        db.session.add(confirmation_noti)
        db.session.commit()
        return {
            "message": "Đã gửi phản hồi thành công và đang chờ ban nhân sự duyệt",
            "complaint_id": complaint.id,
            "status": complaint.status
        }