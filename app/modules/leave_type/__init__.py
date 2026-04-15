from flask import Blueprint

leave_type_bp = Blueprint("leave_type", __name__)

from . import routes  # noqa