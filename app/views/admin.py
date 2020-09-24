"""
Read-only view of the scheduler for users with admin access
"""

# Third party imports
from flask import (Blueprint,
                   render_template,
                   request,
                   redirect,
                   url_for,
                   abort,
                   current_app,
                   jsonify)
from flask.json import dumps as json_dumps
from flask_cas import login_required

from boto3.dynamodb.conditions import Attr, Key

# Local application imports
from app.users import User
from app.logger import DynamoAccessLogger
from app.extensions import dynamo

from app.utils.scheduler import decimal_conversion, natmultisort

bp = Blueprint('admin', __name__, url_prefix='/admin')
logger = DynamoAccessLogger('admin')


# ROUTES
@bp.route('/')
@login_required
def index():
    current_user = User()

    if current_user.is_admin():

        logger.log_access(success=True, route='index')
        return render_template('admin.html')

    else:

        logger.log_access(success=False, route='index')
        return render_template('403.html')


@bp.route('/event_data')
def event_data():
    """
    Returns all existing event and blocked-off times for the user's department
    """
    if not ('start' in request.args and 'end' in request.args):
        logger.log_access(success=False, route='event_data', error='RequestArgs')
        return redirect(url_for('scheduler.index'))

    current_user = User()

    if current_user.is_admin():

        table_name = current_app.config['DB_SCHEDULING']
        resp_events = dynamo.tables[table_name].scan(
            FilterExpression=Attr('PK').begins_with('EVENT') &
                             Attr('start').between(request.args.get('start'), request.args.get('end')) &
                             Attr('active').eq(True)
        )

        resp_notavailable = dynamo.tables[table_name].scan(
            FilterExpression=Key('PK').begins_with('BLOCK')
        )

        resp_events['Items'].extend(resp_notavailable['Items'])

        # Dynamo returns numbers as Decimal objects, convert to integers with the default functions
        return json_dumps(resp_events['Items'], default=decimal_conversion)

    else:
        logger.log_access(success=False, route='event_data')
        abort(403)


@bp.route('/resource_data', methods=['POST'])
def resource_data():
    """
    Returns all resources for the user's department
    """
    current_user = User()

    if current_user.is_admin():

        table_name = current_app.config['DB_SCHEDULING']
        resp_resources = dynamo.tables[table_name].scan(
            FilterExpression=Key('PK').begins_with('RESOURCE')
        )

        # Use natural sorting to make sure 900 comes before 1000, etc.
        return jsonify(natmultisort(resp_resources['Items'], (('room', False), ('title', False))))

    else:
        logger.log_access(success=False, route='resource_data')
        abort(403)
