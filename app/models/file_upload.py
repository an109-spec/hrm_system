from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ENUM


class FileUpload(BaseModel):
    """
    Model lưu file upload (ảnh, pdf, chứng từ).
    """
    __tablename__ = 'file_uploads'

    file_type_enum = ENUM(
        'image', 'pdf', 'doc',
        name='file_type_enum',
        create_type=True
    )

    file_name = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(500), nullable=False)
    file_type = db.Column(file_type_enum, nullable=False)
    file_size = db.Column(db.Integer, nullable=True)

    # Người upload
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # ✅ FK chuẩn (QUAN TRỌNG)
    complaint_id = db.Column(
        db.Integer,
        db.ForeignKey('complaints.id'),
        nullable=True
    )

    def __repr__(self):
        return f"<FileUpload {self.file_name}>"