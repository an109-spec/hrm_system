from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship

class Position(BaseModel):
    """
    Model quản lý các chức danh/vị trí công việc trong công ty.
    Kế thừa từ BaseModel (id, created_at, updated_at, is_deleted).
    """
    __tablename__ = 'positions'

    # Tên chức danh (Ví dụ: Backend Developer, Project Manager)
    job_title = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Dải lương (Sử dụng Numeric để tránh sai số tiền tệ)
    min_salary = db.Column(db.Numeric(15, 2), nullable=True)
    max_salary = db.Column(db.Numeric(15, 2), nullable=True)
    
    # Trạng thái vị trí: active (đang áp dụng), hiring (đang tuyển), inactive (ngừng sử dụng)
    status = db.Column(db.String(20), default='active', server_default='active')
    
    # Mô tả/Yêu cầu công việc
    requirements = db.Column(db.Text, nullable=True)

    # Relationship
    # Liên kết với danh sách nhân viên đang giữ chức danh này
    employees = relationship('Employee', backref='position', lazy='dynamic')

    def __repr__(self):
        return f"<Position {self.job_title}>"

    def to_dict(self):
        """Hỗ trợ chuyển đổi dữ liệu sang dạng dict để dùng cho API/Frontend"""
        data = super().to_dict()
        data.update({
            'min_salary': float(self.min_salary) if self.min_salary else None,
            'max_salary': float(self.max_salary) if self.max_salary else None
        })
        return data