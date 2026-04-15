from datetime import datetime, timezone

from app.extensions.db import db
from app.models.complaint import Complaint, ComplaintMessage
from app.models.notification import Notification
from app.models.history import HistoryLog
from app.models.file_upload import FileUpload
from app.modules.complaint.dto import CreateComplaintDTO, SendMessageDTO, UpdateComplaintStatusDTO

class ComplaintService:

    @staticmethod
    def create_complaint(dto: CreateComplaintDTO):
        complaint = Complaint(
            employee_id=dto.employee_id,
            type=dto.type,
            title=dto.title,
            description=dto.description,
            salary_id=dto.salary_id,
            leave_request_id=dto.leave_request_id,
            priority=dto.priority
        )

        db.session.add(complaint)

        # 🔔 Notification cho HR (giả sử role HR)
        notification = Notification(
            user_id=dto.employee_id,  # TODO: replace bằng HR user
            title="Khiếu nại mới",
            content=f"{dto.title}",
            type="complaint",
            link=f"/complaints/{complaint.id}"
        )
        db.session.add(notification)

        # 📝 History log
        history = HistoryLog(
            employee_id=dto.employee_id,
            action="CREATE_COMPLAINT",
            entity_type="complaint",
            entity_id=complaint.id,
            description=f"Tạo khiếu nại: {dto.title}"
        )
        db.session.add(history)

        db.session.commit()
        return complaint
    
    @staticmethod
    def get_complaints(employee_id=None):
        query = Complaint.query.filter_by(is_deleted=False)

        if employee_id:
            query = query.filter_by(employee_id=employee_id)

        return query.order_by(Complaint.created_at.desc()).all()
    
    @staticmethod
    def get_detail(complaint_id: int):
        complaint = Complaint.query.get_or_404(complaint_id)

        messages = ComplaintMessage.query.filter_by(
            complaint_id=complaint_id
        ).order_by(ComplaintMessage.created_at.asc()).all()

        attachments = FileUpload.query.filter_by(
            entity_type='complaint',
            entity_id=complaint_id
        ).all()

        return {
            "complaint": complaint,
            "messages": messages,
            "attachments": attachments
        }
    
    @staticmethod
    def send_message(dto: SendMessageDTO):
        message = ComplaintMessage(
            complaint_id=dto.complaint_id,
            sender_id=dto.sender_id,
            message=dto.message
        )

        db.session.add(message)

        complaint = Complaint.query.get(dto.complaint_id)

        # 🔔 Notify người còn lại
        notify_user_id = complaint.employee_id
        if dto.sender_id == complaint.employee_id:
            notify_user_id = complaint.handled_by

        if notify_user_id:
            notification = Notification(
                user_id=notify_user_id,
                title="Phản hồi khiếu nại",
                content=dto.message[:100],
                type="complaint",
                link=f"/complaints/{complaint.id}"
            )
            db.session.add(notification)

        db.session.commit()
        return message
    
    @staticmethod
    def update_status(dto: UpdateComplaintStatusDTO):
        complaint = Complaint.query.get_or_404(dto.complaint_id)

        complaint.status = dto.status
        complaint.handled_by = dto.handled_by

        if dto.status == "resolved":
            complaint.resolved_at = datetime.now(timezone.utc)

        # 🔔 Notify employee
        notification = Notification(
            user_id=complaint.employee_id,
            title="Cập nhật khiếu nại",
            content=f"Khiếu nại '{complaint.title}' đã chuyển sang {dto.status}",
            type="complaint",
            link=f"/complaints/{complaint.id}"
        )

        db.session.add(notification)

        db.session.commit()
        return complaint
    
    @staticmethod
    def attach_file(user_id, complaint_id, file_url, file_name, file_type):
        file = FileUpload(
            file_name=file_name,
            file_url=file_url,
            file_type=file_type,
            uploaded_by=user_id,
            entity_type='complaint',
            entity_id=complaint_id
        )

        db.session.add(file)
        db.session.commit()

        return file