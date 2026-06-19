import os

from flask import Flask, redirect,request, url_for
from flask_migrate import Migrate

from app.config import config_by_name
from app.extensions import init_extensions, db, mail

migrate = Migrate()


def create_app():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Trỏ template_folder vào thư mục 'templates' nằm trong 'app'
    template_dir = os.path.join(app_dir, 'templates')
    
    # 3. Khởi tạo app với template_folder đã xác định
    app = Flask(__name__, template_folder=template_dir)

    # ── Config ────────────────────────────────────────────────────────────
    env          = os.getenv("FLASK_ENV", "development")
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
    # init_extensions phải gọi init_jwt(app) thay vì jwt.init_app(app)
    # để các custom loader (unauthorized, expired) được đăng ký đúng.
    init_extensions(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    # ── Models (phải import trước migrate/seed) ───────────────────────────
    from app import models  # noqa: F401

    # ── Blueprints ────────────────────────────────────────────────────────
    from app.blueprints import register_blueprints
    register_blueprints(app)

    # ── CLI commands ──────────────────────────────────────────────────────
    from app.cli import register_cli
    register_cli(app)

    # ── Context processors ────────────────────────────────────────────────
    from app.context_processors import register_context_processors
    register_context_processors(app)

    # ── Error handlers ────────────────────────────────────────────────────
    from app.errors import register_error_handlers
    register_error_handlers(app)

    # ── APScheduler ───────────────────────────────────────────────────────
    from app.scheduler import init_scheduler
    init_scheduler(app)
    @app.route("/")
    def index():
        """Tự động chuyển hướng về trang đăng nhập."""
        return redirect(url_for("auth.login_page"))
    @app.after_request
    def add_header(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return app