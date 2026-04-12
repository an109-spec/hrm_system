from app.models.base import db

class SystemSetting(db.Model):
    """
    Bảng lưu trữ các cấu hình linh hoạt của hệ thống.
    Giúp Admin thay đổi tham số mà không cần sửa code.
    """
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    value = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    def __repr__(self):
        return f"<SystemSetting {self.key}: {self.value}>"