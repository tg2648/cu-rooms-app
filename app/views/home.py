"""Home routing
/login/ and /logout/ routes are automatically added by flask-CAS extension
"""

# Third party imports
from flask import Blueprint
from flask import render_template

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    return render_template("index.html")
