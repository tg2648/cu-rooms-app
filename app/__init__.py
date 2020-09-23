"""
Main application package

Contains the app factory function.
"""

# Third party imports
from flask import Flask
from flask.helpers import get_debug_flag

# Local application imports
from config import DevConfig, ProdConfig
from app.utils import jinja_filters


def create_app():
    """Application factory.

        - Creates a Flask object
        - Sets a config depending on the FLASK_DEBUG environment variable
        - Registers Flask extensions on routing (Flask blueprints)
        - Registers Dash applications

    Returns:
        Flask object
    """
    server = Flask(__name__)

    # Apply either development or production config
    Config = DevConfig if get_debug_flag() else ProdConfig
    server.config.from_object(Config)

    # Register Flask extensions and routing
    register_extensions(server)
    register_blueprints(server)

    # Register Jinja filters
    server.jinja_env.filters['datetime_humanize'] = jinja_filters.datetime_humanize
    server.jinja_env.filters['serialize'] = jinja_filters.serialize

    return server


def register_extensions(server):
    """
    Registers Flask extensions to the Flask server.

    Args:
        server (Flask object)

    Returns:
        None
    """
    from app.extensions import cas
    from app.extensions import dynamo

    cas.init_app(server)
    dynamo.init_app(server)


def register_blueprints(server):
    """
    Registers web routing to the Flask server.

    Args:
        server (Flask object)

    Returns:
        None
    """
    # from app.views import home
    from app.views import scheduler

    # server.register_blueprint(home.bp)
    server.register_blueprint(scheduler.bp)
