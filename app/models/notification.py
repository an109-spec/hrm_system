from app.models.base import db, BaseModel
from sqlalchemy.orm import relationship

class Notification(BaseModel): # Kế thừa BaseModel để có sẵn id, created_at, updated_at, is_deleted
    __tablename__ = 'notifications'
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False,
        index=True
    )
    is_read = db.Column(db.Boolean, default=False, server_default='false', nullable=False)
    link = db.Column(db.String(255), nullable=True)
    type = db.Column(db.String(20), nullable=True)
    user = relationship(
        'User',
        back_populates='notifications'
    )

    @classmethod
    def get_by_user(cls, user_id: int, limit: int = 20, only_unread: bool = False):
        query = cls.query.filter_by(user_id=user_id, is_deleted=False)
        if only_unread:
            query = query.filter_by(is_read=False)
        return query.order_by(cls.created_at.desc()).limit(limit).all()

    def __repr__(self):
        return f"<Notification {self.title} to User:{self.user_id}>"
    
    @classmethod
    def mark_as_read_by_user(cls, notification_id: int, user_id: int):
        """Hàm này vừa tìm, vừa đánh dấu, vừa lưu"""
        notification = cls.query.filter_by(
            id=notification_id, 
            user_id=user_id, 
            is_deleted=False
        ).first()

        if not notification:
            raise ValueError("Notification not found")

        notification.is_read = True
        db.session.commit() # Lưu thay đổi vào DB
        return notification
    
    @classmethod
    def mark_all_as_read(cls, user_id: int):
        rows_affected = cls.query.filter_by(
            user_id=user_id,
            is_read=False,
            is_deleted=False
        ).update({"is_read": True})
        
        db.session.commit()
        return rows_affected > 0
    
    @classmethod
    def get_unread_count(cls, user_id: int) -> int:
        """Đếm số thông báo chưa đọc (bao gồm check cả trạng thái đã xóa mềm)"""
        return cls.query.filter_by(
            user_id=user_id, 
            is_read=False, 
            is_deleted=False
        ).count()

    @classmethod
    def remove(cls, notification_id: int, user_id: int):
        notification = cls.query.filter_by(id=notification_id, user_id=user_id).first()
        if not notification:
            raise ValueError("Notification not found")
        notification.is_deleted = True 
        db.session.commit()
        return True