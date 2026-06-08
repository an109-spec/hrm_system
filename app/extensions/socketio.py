from flask_socketio import SocketIO
import os
def _allowed_origins():
    origins = os.getenv("SOCKETIO_CORS_ALLOWED_ORIGINS")
    if origins:
        return [origin.strip() for origin in origins.split(",") if origin.strip()]
    if os.getenv("FLASK_ENV", "development") == "production":
        return []
    return "*"


socketio = SocketIO(cors_allowed_origins=_allowed_origins(), async_mode="threading")

