import os
import uuid
from werkzeug.datastructures import FileStorage

from app.extensions.db import db
from app.models.file_upload import FileUpload


class UploadService:
    UPLOAD_FOLDER = os.path.join("app", "static", "uploads")

    @staticmethod
    def _ensure_folder(entity_type=None):
        target_path = UploadService.UPLOAD_FOLDER
        if entity_type:
            target_path = os.path.join(target_path, entity_type)
            
        if not os.path.exists(target_path):
            os.makedirs(target_path, exist_ok=True)

    @staticmethod
    #biến một cái tên file bất kỳ thành một cái tên duy nhất và an toàn để lưu trữ
    def _generate_filename(original_filename: str) -> str:
        ext = original_filename.split(".")[-1] if "." in original_filename else ""
        return f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex

    @staticmethod
    def save_file(
        file: FileStorage,
        user_id: int,
        entity_type: str,
        entity_id: int
    ) -> FileUpload:
        base_folder = os.path.join(UploadService.UPLOAD_FOLDER, entity_type)
        os.makedirs(base_folder, exist_ok=True)
        filename = UploadService._generate_filename(file.filename)
        relative_path = os.path.join(entity_type, filename)
        full_path = os.path.join(UploadService.UPLOAD_FOLDER, relative_path)
        try:
            file.save(full_path)
            file_size = os.path.getsize(full_path)
            file_record = FileUpload(
                file_name=file.filename, # Tên gốc: "bang_luong.pdf"
                file_url=relative_path,  # Đường dẫn để FE truy cập: "complaint/uuid.pdf"
                file_type=UploadService.detect_type(file.filename),
                file_size=file_size,
                uploaded_by=user_id,
                entity_type=entity_type,
                entity_id=entity_id
            )
            db.session.add(file_record)
            db.session.flush() 
            return file_record
        except Exception as e:
            if os.path.exists(full_path):
                os.remove(full_path)
            raise ValueError(f"Không thể lưu file đính kèm: {str(e)}")

    @staticmethod
    def detect_type(filename: str) -> str:
        if not filename or "." not in filename:
            return "other"
        ext = filename.lower().split(".")[-1]
        if ext in ["png", "jpg", "jpeg", "gif", "webp"]:
            return "image"
        if ext == "pdf":
            return "pdf"
        if ext in ["doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv"]:
            return "document"
        return "other"