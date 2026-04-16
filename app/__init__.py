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
from app.modules.jobs import register_jobs
from apscheduler.schedulers.background import BackgroundScheduler
# --- IMPORT BLUEPRINTS HRM ---
from app.modules.auth import auth_bp
from app.modules.employee import employee_bp
from app.modules.home import home_bp
from app.modules.notification import notification_bp
from app.modules.complaint import complaint_bp
from app.modules.leave import leave_bp
from app.modules.attendance import attendance_bp
from app.modules.dashboard import dashboard_bp  
from app.modules.history import history_bp
from app.modules.leave_type import leave_type_bp
from app.modules.salary import salary_bp
from app.modules.upload import upload_bp

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
            current_user = db.session.get(User, user_id)
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
    # ======================
    # Scheduler jobs
    # ======================
    scheduler = BackgroundScheduler()
    register_jobs(scheduler)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler.start()
    return app

def ensure_default_admin(app):
    from app.models import User

    with app.app_context():
        try:
            # Nếu chưa có bảng thì skip
            inspector = inspect(db.engine)
            if not inspector.has_table("users"):
                return

            # Check tồn tại
            exists = User.query.filter_by(username="admin").first()
            if exists:
                return

            # Tạo admin bằng ORM
            admin = User(
                username="admin",
                email="admin@hrm.local",
                password_hash=generate_password_hash("admin123"),
            )

            db.session.add(admin)
            db.session.commit()

            print("--- Đã tạo tài khoản Admin mặc định thành công! ---")

        except Exception as e:
            db.session.rollback()
            print(f"Lỗi tạo admin: {e}")

def register_blueprints(app):
    app.register_blueprint(auth_bp) # Đăng nhập/Đăng ký
    app.register_blueprint(employee_bp) # Nhân viên
    app.register_blueprint(home_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(complaint_bp)
    app.register_blueprint(leave_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(leave_type_bp)
    app.register_blueprint(salary_bp)
    app.register_blueprint(upload_bp)