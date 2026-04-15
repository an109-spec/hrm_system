from flask import Blueprint

salary_bp = Blueprint("salary", __name__)

from . import routes  # noqa