from flask import Blueprint

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")

from . import routes