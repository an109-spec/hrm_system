from flask import Blueprint

employee_bp = Blueprint("personnel", __name__, url_prefix="/personnel")

from . import routes