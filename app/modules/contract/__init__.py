from flask import Blueprint

contract_bp = Blueprint(
    "contract",
    __name__,
    url_prefix="/contract"
)

from . import routes