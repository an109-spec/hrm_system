from flask import Blueprint, app

home_bp = Blueprint("home", __name__, url_prefix="/")

from . import routes