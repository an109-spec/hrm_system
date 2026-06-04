from flask import Blueprint

resignation_bp = Blueprint("resignation", __name__)

from . import routes  