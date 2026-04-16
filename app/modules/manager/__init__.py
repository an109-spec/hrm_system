from flask import Blueprint

manager_bp = Blueprint(
    "manager",
    __name__,
    url_prefix="/api/manager"
)

from . import routes