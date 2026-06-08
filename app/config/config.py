import os
from datetime import timedelta

PERMANENT_SESSION_LIFETIME = timedelta(days=30)

class BaseConfig:
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = False
    SECRET_KEY = os.getenv("SECRET_KEY") or ("dev-secret" if ENV != "production" else None)

    # ======================
    # DATABASE
    # ======================
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
 
    # Build URI nếu đủ biến
    _BUILT_URI = None
    if all([DB_USER, DB_PASSWORD, DB_NAME]):
        _BUILT_URI = (
            f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
            f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    SQLALCHEMY_DATABASE_URI = (
        os.getenv("SQLALCHEMY_DATABASE_URI")
        or os.getenv("DATABASE_URL")
        or _BUILT_URI
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True
    }

    # ======================
    # JWT
    # ======================
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or ("dev-jwt-secret" if ENV != "production" else None)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 3600))
    )
    JWT_COOKIE_CSRF_PROTECT = os.getenv("JWT_COOKIE_CSRF_PROTECT", "True") == "True"

    # ======================
    # MAIL
    # ======================
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "False") == "True"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER") or os.getenv("MAIL_USERNAME")
    MAIL_SUPPRESS_SEND = os.getenv("MAIL_SUPPRESS_SEND", "False") == "True"

    # ======================
    # SOCKET.IO
    # ======================
    SOCKETIO_MESSAGE_QUEUE = os.getenv("SOCKETIO_MESSAGE_QUEUE")
    SOCKETIO_CORS_ALLOWED_ORIGINS = os.getenv("SOCKETIO_CORS_ALLOWED_ORIGINS", "*")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    # URI mặc định cho local nếu không tìm thấy biến môi trường

    SQLALCHEMY_DATABASE_URI = (
        os.getenv("SQLALCHEMY_DATABASE_URI")
        or os.getenv("DATABASE_URL")
        or BaseConfig.SQLALCHEMY_DATABASE_URI
        or "sqlite:///hrm_dev.db"  # Lựa chọn cuối cùng nếu không tìm thấy gì khác
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    # Trong production, ưu tiên dùng DATABASE_URL từ môi trường
    SQLALCHEMY_DATABASE_URI = (
        os.getenv("DATABASE_URL") or BaseConfig.SQLALCHEMY_DATABASE_URI
    )

    @classmethod
    def validate(cls):
        missing = [
            key for key, value in {
                "SECRET_KEY": cls.SECRET_KEY,
                "JWT_SECRET_KEY": cls.JWT_SECRET_KEY,
                "SQLALCHEMY_DATABASE_URI": cls.SQLALCHEMY_DATABASE_URI,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing required production config: " + ", ".join(missing)
            )
        
class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    MAIL_SUPPRESS_SEND = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}