from flask import render_template
from flask_jwt_extended import jwt_required

from app.modules.home import home_bp


@home_bp.route("/")
@jwt_required(locations=["headers", "cookies"])
def home():
    return render_template(
        "modules/home/home.html"
    )