import os
import uuid
from werkzeug.datastructures import FileStorage

from app.extensions.db import db
from app.models.file_upload import FileUpload


class UploadService:
    UPLOAD_FOLDER = "uploads"

    @staticmethod
    def _ensure_folder():
        os.makedirs(UploadService.UPLOAD_FOLDER, exist_ok=True)

    @staticmethod
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

        UploadService._ensure_folder()

        filename = UploadService._generate_filename(file.filename)
        path = os.path.join(UploadService.UPLOAD_FOLDER, filename)

        file.save(path)

        file_record = FileUpload(
            file_name=file.filename,
            file_url=path,
            file_type=UploadService.detect_type(file.filename),
            file_size=os.path.getsize(path),
            uploaded_by=user_id,
            entity_type=entity_type,
            entity_id=entity_id
        )

        db.session.add(file_record)
        db.session.commit()

        return file_record

    @staticmethod
    def detect_type(filename: str) -> str:
        ext = filename.lower().split(".")[-1]
        if ext in ["png", "jpg", "jpeg", "gif"]:
            return "image"
        if ext == "pdf":
            return "pdf"
        return "doc"