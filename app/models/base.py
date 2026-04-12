from datetime import datetime, timezone
from sqlalchemy import func
from app.extensions.db import db

class BaseModel(db.Model):
    __abstract__ = True

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    
    # ✅ Dùng lambda để đảm bảo lấy thời gian tại thời điểm tạo record
    # ✅ Sử dụng timezone=True để tương thích với PostgreSQL timestamptz
    created_at = db.Column(
        db.DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(), # Backup ở phía Database
        nullable=False
    )
    
    updated_at = db.Column(
        db.DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )

    # Quản lý xóa mềm
    is_deleted = db.Column(db.Boolean, default=False, index=True, nullable=False)

    def delete(self):
        """Phương thức xóa mềm"""
        self.is_deleted = True
        # Lưu ý: Đừng commit() ở đây, hãy để Service lo việc commit
        # self.is_deleted = True 

    def restore(self):
        """Khôi phục record"""
        self.is_deleted = False

    def to_dict(self):
        """Chuyển đổi object thành dictionary"""
        res = {}
        for c in self.__table__.columns:
            value = getattr(self, c.name)
            # Serialize datetime sang string để tránh lỗi JSON
            if isinstance(value, datetime):
                res[c.name] = value.isoformat()
            else:
                res[c.name] = value
        return res

class AuditLogMixin:
    """
    Mixin bổ sung nếu bạn muốn theo dõi ai là người tạo/sửa record đó.
    (Tùy chọn: Có thể tích hợp vào các bảng nhạy cảm như Lương/Hợp đồng)
    """
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)