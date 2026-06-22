from flask import Blueprint

common_bp = Blueprint(
    'common',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/static/common'
)

from . import routes