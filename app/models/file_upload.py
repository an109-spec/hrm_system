from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ENUM


class FileUpload(BaseModel):
    __tablename__ = 'file_uploads'

    # 1. Cập nhật ENUM cho khớp với Service
    file_type_enum = ENUM(
        'image', 'pdf', 'document', 'other', 
        name='file_type_enum',
        create_type=True
    )

    file_name = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(500), nullable=False)
    file_type = db.Column(file_type_enum, nullable=False)
    file_size = db.Column(db.Integer, nullable=True)

    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # 2. Thay complaint_id bằng cặp bài trùng linh hoạt này:
    entity_type = db.Column(db.String(50), nullable=False) # Lưu 'complaint', 'employee', v.v.
    entity_id = db.Column(db.Integer, nullable=False)     # Lưu ID của bản ghi tương ứng

    def __repr__(self):
        return f"<FileUpload {self.file_name} for {self.entity_type}:{self.entity_id}>"