from flask import Blueprint

personnel_bp = Blueprint("personnel", __name__, url_prefix="/personnel")

employee_bp = personnel_bp

from . import routes 