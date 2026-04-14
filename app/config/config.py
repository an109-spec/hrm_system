import os
from datetime import timedelta

PERMANENT_SESSION_LIFETIME = timedelta(days=30)

class BaseConfig:
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

    # ======================
    # DATABASE
    # ======================
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    DB_USER = os.getenv("APP_DB_USER")
    DB_PASSWORD = os.getenv("APP_DB_PASSWORD")
    DB_NAME = os.getenv("APP_DB_NAME")
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

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 3600))
    )

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


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    #MAIL_SUPPRESS_SEND = True

    # Nếu không set PostgreSQL thì fallback SQLite (DEV ONLY)
    if not BaseConfig.SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI = "sqlite:///hrm_db.db"


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = (
        os.getenv("DATABASE_URL") or BaseConfig.SQLALCHEMY_DATABASE_URI
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