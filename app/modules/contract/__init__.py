from flask import Blueprint

contract_bp = Blueprint(
    'contract',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/static/contract'
)

from . import routes
