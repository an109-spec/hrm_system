from app.models.base import db, BaseModel
# Xóa import datetime vì đã có trong BaseModel

class Notification(BaseModel): # Kế thừa BaseModel để có sẵn id, created_at, updated_at, is_deleted
    """
    Model quản lý thông báo hệ thống.
    Gửi thông báo tới User khi có các sự kiện: Duyệt phép, Chốt lương, Thông báo chung.
    """
    __tablename__ = 'notifications'

    # Không cần khai báo lại id vì đã có trong BaseModel
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text)
    
    # Liên kết tới tài khoản nhận thông báo (Sử dụng BigInteger cho đồng bộ)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Trạng thái đọc
    is_read = db.Column(db.Boolean, default=False, server_default='false', nullable=False)
    
    # Điều hướng: Link dẫn tới đơn nghỉ phép hoặc phiếu lương cụ thể
    link = db.Column(db.String(255), nullable=True)
    
    # Phân loại: 'salary', 'leave', 'system', 'reminder'
    type = db.Column(db.String(20), nullable=True)
    
    # created_at và updated_at đã có sẵn từ BaseModel và chuẩn UTC

    def __repr__(self):
        return f"<Notification {self.title} to User:{self.user_id}>"

    def mark_as_read(self):
        """Hàm helper để đánh dấu thông báo đã đọc"""
        self.is_read = True
        # Không nên commit ở đây, để Service tầng trên quản lý transaction