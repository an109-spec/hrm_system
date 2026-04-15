from flask import Blueprint

complaint_bp = Blueprint(
    "complaint",
    __name__,
    url_prefix="/complaints"
)

# import routes để bind vào blueprint
from . import routes