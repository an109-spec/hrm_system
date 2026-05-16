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
    def __repr__(self):
        return f"<Notification {self.title} to User:{self.user_id}>"
    def mark_as_read(self):
        """Hàm helper để đánh dấu thông báo đã đọc"""
        self.is_read = True