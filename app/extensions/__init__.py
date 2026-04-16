from app.extensions.db import db
from app.extensions.jwt import jwt
from app.extensions.mail import mail
from app.extensions.socketio import socketio

from flask_login import LoginManager
from app.models import User

# 👉 THÊM
login_manager = LoginManager()


def init_extensions(app):
    db.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    socketio.init_app(app)

    # 👉 THÊM
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"  # route login của bạn


# 👉 THÊM (QUAN TRỌNG)
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))