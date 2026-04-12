from app.extensions.db import db
from app.extensions.jwt import jwt
from app.extensions.mail import mail
from app.extensions.socketio import socketio

def init_extensions(app):
    db.init_app(app)#gắn extension vào app
    jwt.init_app(app)
    mail.init_app(app)
    socketio.init_app(app)