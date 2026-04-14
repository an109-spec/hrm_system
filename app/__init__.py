import os
from flask import Flask
from datetime import datetime
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash

from app.config import config_by_name
from app.extensions import init_extensions, db
from app.extensions.jwt import jwt
from app.extensions.socketio import socketio
from flask_migrate import Migrate
from flask_mail import Mail

# --- IMPORT BLUEPRINTS HRM ---
from app.modules.auth import auth_bp
from app.modules.employee import employee_bp
# Dự kiến các module mới cho HRM
# from app.modules.employee import employee_bp 
# from app.modules.payroll import payroll_bp
# from app.modules.attendance import attendance_bp

from app.cli import register_cli

mail = Mail()
migrate = Migrate()

def create_app():
    app = Flask(__name__)

    env = os.getenv("FLASK_ENV", "development")
    config_class = config_by_name.get(env)

    if not config_class:
        raise RuntimeError(f"Invalid environment: {env}")

    app.config.from_object(config_class)

    # Init extensions
    init_extensions(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    # Dev auto create tables (Dành cho SQLite hoặc chạy test nhanh)
    if env == "development" and app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        with app.app_context():
            from app import models
            db.create_all()

    # Register blueprints & CLI
    register_blueprints(app)
    register_cli(app)
    ensure_default_admin(app)

    @app.context_processor
    def inject_globals():
        """Truyền các biến dùng chung ra toàn bộ template HRM"""
        from flask import session
        from app.models import User, Notification
        
        current_user = None
        header_notifications = []
        unread_notifications = 0

        user_id = session.get("user_id")

        if user_id:
            current_user = User.query.get(user_id)
            if current_user:
                # Lấy thông báo nội bộ hệ thống
                header_notifications = (
                    Notification.query
                    .filter_by(user_id=current_user.id)
                    .order_by(Notification.created_at.desc())
                    .limit(5)
                    .all()
                )
                unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()

        return {
            "current_year": datetime.now().year,
            "current_user": current_user,
            "header_notifications": header_notifications,
            "unread_notifications": unread_notifications,
            "system_name": "HRM System"
        }

    return app

def ensure_default_admin(app):
    """Khởi tạo tài khoản quản trị hệ thống mặc định nếu chưa có"""
    from sqlalchemy import text 
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            if not inspector.has_table("users"):
                return

            exists = db.session.execute(
                text("SELECT 1 FROM users WHERE username = 'admin'")
            ).first()
            if exists:
                return

            db.session.execute(
                text(
                    """
                    INSERT INTO users (username, email, password_hash)
                    VALUES (:username, :email, :password_hash)
                    """
                ),
                {
                    "username": "admin",
                    "email": "admin@hrm.local",
                    "password_hash": generate_password_hash("admin123"),
                },
            )
            db.session.commit()
            print("--- Đã tạo tài khoản Admin mặc định thành công! ---")
        except Exception as e:
            db.session.rollback()
            print(
                "Không thể khởi tạo admin mặc định ở bước startup. "
                "Kiểm tra kết nối DB/schema (SQLALCHEMY_DATABASE_URI, APP_DB_NAME) hoặc chạy flask init-db. "
                f"Chi tiết: {e}"
            )

def register_blueprints(app):
    app.register_blueprint(auth_bp) # Đăng nhập/Đăng ký
    app.register_blueprint(employee_bp) # Nhân viên
 
    # Duy An sẽ bổ sung các Blueprint dưới đây khi code xong module tương ứng:
    # app.register_blueprint(employee_bp, url_prefix='/employees')
    # app.register_blueprint(payroll_bp, url_prefix='/payroll')