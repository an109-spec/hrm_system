# C:\HRM_TOTNGHIEP\app\__init__.py

import os
from importlib.util import find_spec
from flask import Flask, redirect, url_for, flash, request, jsonify
from datetime import datetime

from app.config import config_by_name
from app.extensions import init_extensions, db
from flask_migrate import Migrate
from flask_mail import Mail
from app.common.exceptions import UnauthorizedError, ForbiddenError
from app.utils.time import get_current_time
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
    if hasattr(config_class, "validate"):
        config_class.validate()

    # ── JWT config ────────────────────────────────────────────────────────
    app.config["JWT_TOKEN_LOCATION"]      = ["cookies", "headers"]
    app.config["JWT_ACCESS_COOKIE_NAME"]  = "access_token_cookie"
    app.config["JWT_COOKIE_CSRF_PROTECT"] = (
        os.getenv("JWT_COOKIE_CSRF_PROTECT", "True").lower() == "true"
    )

    # ── Extensions ────────────────────────────────────────────────────────
    init_extensions(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    from app import models
    register_blueprints(app)
    register_cli(app)

    # ── Context processor ─────────────────────────────────────────────────
    @app.context_processor
    def inject_globals():
        """Truyền các biến dùng chung ra toàn bộ template HRM."""
        from flask import session
        from app.models import User, Notification, Employee

        current_user        = None
        current_employee    = None
        avatar_url          = None
        header_notifications = []
        unread_notifications = 0
        now = get_current_time()
        user_id = session.get("user_id")
        try:
            normalized_user_id = int(user_id) if user_id is not None else None
        except (TypeError, ValueError):
            normalized_user_id = None

        if normalized_user_id:
            current_user = User.query.get(normalized_user_id)
            if current_user:
                current_employee = Employee.query.filter_by(
                    user_id=current_user.id
                ).first()

                if current_employee and current_employee.avatar:
                    version = int((current_employee.updated_at or now).timestamp())
                    avatar_url = f"{current_employee.avatar}?v={version}"

                header_notifications = (
                    Notification.query
                    .filter_by(user_id=current_user.id)
                    .order_by(Notification.created_at.desc())
                    .limit(5)
                    .all()
                )
                unread_notifications = Notification.query.filter_by(
                    user_id=current_user.id, is_read=False
                ).count()

        return {
            "current_year":          now.year,
            "current_user":          current_user,
            "current_employee":      current_employee,
            "avatar_url":            avatar_url,
            "header_notifications":  header_notifications,
            "unread_notifications":  unread_notifications,
            "system_name":           "HRM System",
        }

    # ── APScheduler ───────────────────────────────────────────────────────
    if not app.config.get("TESTING", False) and find_spec("apscheduler") is not None:
        from apscheduler.schedulers.background import BackgroundScheduler
        from app.modules.jobs import register_jobs

        scheduler = BackgroundScheduler()
        register_jobs(scheduler)

        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            scheduler.start()

    # ── Error handlers ────────────────────────────────────────────────────
    # Phân biệt API request (trả JSON) và web request (redirect)
    # để tránh redirect khi gọi /api/* bằng fetch/axios
    def _is_api_request() -> bool:
        """True nếu request đến từ API (path bắt đầu /api/ hoặc Accept: json)."""
        return request.path.startswith("/api/") or \
               request.accept_mimetypes.best == "application/json"

    @app.errorhandler(UnauthorizedError)
    def handle_unauthorized(e):
        if _is_api_request():
            return jsonify({
                "success": False,
                "icon":    "error",
                "title":   "Chưa xác thực",
                "text":    str(e) or "Vui lòng đăng nhập để tiếp tục.",
            }), 401
        flash("Vui lòng đăng nhập để tiếp tục.", "warning")
        return redirect(url_for("auth.login"))

    @app.errorhandler(ForbiddenError)
    def handle_forbidden(e):
        if _is_api_request():
            return jsonify({
                "success": False,
                "icon":    "error",
                "title":   "Không có quyền",
                "text":    str(e) or "Bạn không có quyền truy cập khu vực này.",
            }), 403
        flash("Bạn không có quyền truy cập khu vực này.", "danger")
        return redirect(url_for("auth.login"))

    return app


def register_blueprints(app):
    from app.modules.admin        import admin_bp
    from app.modules.attendance   import attendance_bp
    from app.modules.auth         import auth_bp
    from app.modules.contract     import contract_bp
    from app.modules.history      import history_bp
    from app.modules.hr           import hr_bp
    from app.modules.leave        import leave_bp
    from app.modules.manager      import manager_bp
    from app.modules.notification import notification_bp
    from app.modules.payroll      import payroll_bp
    from app.modules.personnel    import personnel_bp
    from app.modules.resignation  import resignation_bp

    blueprints = (
        auth_bp,
        personnel_bp,
        notification_bp,
        leave_bp,
        attendance_bp,
        history_bp,
        manager_bp,
        admin_bp,
        hr_bp,
        payroll_bp,        # url_prefix="/payroll" → /payroll/analytics/total-fund
        contract_bp,
        resignation_bp,
    )
    for blueprint in blueprints:
        app.register_blueprint(blueprint)