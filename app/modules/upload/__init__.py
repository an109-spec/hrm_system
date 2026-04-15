from flask import Blueprint

upload_bp = Blueprint(
    "upload",
    __name__,
    url_prefix="/api/upload"
)

from . import routes  # noqa