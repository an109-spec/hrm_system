from flask import Blueprint

leave_bp = Blueprint("leave", __name__)

from . import routes  # noqa