from app.models.base import BaseModel, db
from sqlalchemy.orm import relationship

class User(BaseModel):
    """
    Model quản lý tài khoản đăng nhập hệ thống.
    Kết nối 1-1 với thông tin nhân viên (Employee).
    """
    __tablename__ = 'users'

    # Thông tin đăng nhập
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Phân quyền (Liên kết với bảng Role)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)
    
    # Trạng thái tài khoản (Cho phép hoặc khóa truy cập)
    is_active = db.Column(db.Boolean, default=True, server_default='true')

    # Relationships
    # Mối quan hệ 1-1 với Employee (uselist=False đảm bảo tính duy nhất)
    # back_populates giúp truy cập ngược từ employee.user
    employee_profile = relationship('Employee', back_populates='user', uselist=False)
    
    # Mối quan hệ với bảng Role
    role = relationship('Role', backref='users')

    # Mối quan hệ với bảng Notification
    notifications = relationship('Notification', backref='user', lazy='dynamic')

    def __repr__(self):
        return f"<User {self.username}>"

    def set_password(self, password):
        """Sử dụng thư viện werkzeug.security để hash password"""
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Kiểm tra password khi login"""
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)