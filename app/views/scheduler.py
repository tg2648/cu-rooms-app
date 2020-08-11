"""
Scheduler
"""

# Standard library imports
from decimal import Decimal
from uuid import uuid4
from operator import itemgetter

# Third party imports
import arrow
from flask import Blueprint
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from flask import current_app
from flask import abort
from flask import jsonify
from flask.json import dumps as json_dumps
from flask_cas import login_required

from boto3.dynamodb.conditions import Attr
from itsdangerous.exc import BadSignature

# Local application imports
from app.users import User
from app.logger import DynamoAccessLogger
from app.extensions import dynamo


bp = Blueprint('scheduler', __name__)
logger = DynamoAccessLogger('room_scheduler')


def decimal_conversion(obj):
    """
    Conversion function for json.dumps to convert Decimal objects to integers
    https://stackoverflow.com/questions/31202956/json-typeerror-decimal34-3-is-not-json-serializable
    """
    if isinstance(obj, Decimal):
        return int(obj)
    raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)


def get_timestamp():
    """Returns current time converted to EDT/EST in ISO8601"""
    return arrow.utcnow().to('US/Eastern').format('YYYY-MM-DDTHH:mm:ssZZ')


# @login_required
@bp.route('/')
def index():
    current_user = User()
    logger.log_access(has_access=True)

    table_name = current_app.config['DB_SCHEDULING']
    resp_events = dynamo.tables[table_name].query(
        IndexName='uni-index',
        KeyConditionExpression='uni = :uni',
        ExpressionAttributeValues={
            ':uni': current_user.uni,
        },
    )

    # Sort by start time
    events = sorted(resp_events['Items'], key=itemgetter('start'))

    return render_template('scheduler.html', events=events)


@bp.route('/event_data')
def event_data():

    if not ('start' in request.args and 'end' in request.args):
        return redirect(url_for('scheduler.index'))

    # events = [
    #     {
    #         "title": "John Appleseed",
    #         "start": "2020-08-06T12:30:00",
    #         "end": "2020-08-06T13:30:00",
    #         'resourceId': 'a'
    #     },
    #     {
    #         'groupId': 'notAvailable',
    #         'startTime': '10:30:00',
    #         'endTime': '14:30:00',
    #         'overlap': False,
    #         'display': 'background',
    #         'color': '#ff9f89',
    #         'resourceId': 'b',
    #         'daysOfWeek': [1, 2, 3, 4, 5]
    #     },
    #     {
    #         'groupId': 'notAvailable',
    #         'overlap': False,
    #         'display': 'background',
    #         'color': '#ff9f89',
    #         'resourceId': 'b',
    #         'daysOfWeek': [0, 6]
    #     },
    # ]

    # return jsonify(events)

    table_name = current_app.config['DB_SCHEDULING']
    resp_events = dynamo.tables[table_name].query(
        IndexName='start-index',
        KeyConditionExpression='PK = :pk AND #s BETWEEN :lower AND :upper',
        ExpressionAttributeValues={
            ':pk': 'EVENT',
            ':lower': f"{request.args.get('start')}",
            ':upper': f"{request.args.get('end')}",
        },
        ExpressionAttributeNames={
            '#s': 'start',
        },
        FilterExpression=Attr('active').eq(True)
    )

    resp_notavailable = dynamo.tables[table_name].scan(
        IndexName='notAvailable-index',
    )

    resp_events['Items'].extend(resp_notavailable['Items'])

    # Dynamo returns numbers as Decimal objects, convert to integers with the default functions
    return json_dumps(resp_events['Items'], default=decimal_conversion)


@bp.route('/resource_data')
def resource_data():

    # print(f'resource_data headers: {request.headers}')
    # print(f'resource_data args: {request.args}')

    # resources = [
    #     {'id': 'a', 'room': '100 Dodge', 'title': 'Space A'},
    #     {'id': 'b', 'room': '100 Dodge', 'title': 'Space B'},
    #     {'id': 'c', 'room': '100 Dodge', 'title': 'Space C'},
    #     {'id': 'd', 'room': '200 Dodge', 'title': 'Space A'},
    #     {'id': 'e', 'room': '200 Dodge', 'title': 'Space B'},
    #     {'id': 'f', 'room': '200 Dodge', 'title': 'Space C'},
    # ]

    dept = 'ECON'

    table_name = current_app.config['DB_SCHEDULING']
    resp_resources = dynamo.tables[table_name].query(
        KeyConditionExpression='PK = :pk AND begins_with(SK, :dept)',
        ExpressionAttributeValues={
            ':pk': 'RESOURCE',
            ':dept': dept,
        },
    )

    return jsonify(resp_resources['Items'])


@bp.route('/event_drop', methods=['POST'])
def event_drop():
    """
    Application logic for moving an event to a different time/day/resource.
    Request payload should contain:
        PK: Primary key of the event,
        SK: Sort key of the event,
        uni: Event owner's uni,
        start: Start time of the modified event,
        end: End time of the modified event,
        newResourceId: Resource of ID of the modified event,
    """

    data = request.json
    current_user = User()

    if data['uni'] != current_user.uni:
        return 'You can only modify your own reservations.', 403

    expr = 'SET #s = :s, #e = :e, changedOn = :t'
    vals = {
        ':s': data['start'],
        ':e': data['end'],
        ':t': get_timestamp(),
    }

    if 'newResourceId' in data:
        expr = f'{expr}, resourceId = :r, resourceName = :n'
        vals[':r'] = data['newResourceId']
        vals[':n'] = data['newResourceName']

    try:
        table_name = current_app.config['DB_SCHEDULING']
        dynamo.tables[table_name].update_item(
            Key={'PK': data['PK'], 'SK': data['SK']},
            UpdateExpression=expr,
            ExpressionAttributeValues=vals,
            ExpressionAttributeNames={
                '#s': 'start',
                '#e': 'end',
            }
        )
    except Exception as e:
        print(e)
        return 'Unexpected error occured', 500

    return 'Success', 200


@bp.route('/event_select', methods=['POST'])
def event_select():

    current_user = User()
    data = request.json

    uni = current_user.uni

    item = {
        'PK': 'EVENT',
        'SK': f"{data.get('resourceId')}#{uuid4()}",
        'start': data.get('start'),
        'end': data.get('end'),
        'resourceId': data.get('resourceId'),
        'resourceName': data.get('resourceName'),
        'title': uni,
        'uni': uni,
        'active': True,
        'createdOn': get_timestamp(),
        'changedOn': '',
    }

    try:
        table_name = current_app.config['DB_SCHEDULING']
        dynamo.tables[table_name].put_item(Item=item)
    except Exception:
        return 'Unexpected error occured', 500

    return 'Success', 200


@bp.route('/event_delete', methods=['POST'])
def event_delete():
    logger = DynamoAccessLogger('room_scheduler_event_delete')

    s = current_app.config['SERIALIZER']

    try:
        PK = s.loads(request.form['PK'])
        SK = s.loads(request.form['SK'])
    except BadSignature:
        logger.log_access(has_access=False)
        abort(400)

    try:
        table_name = current_app.config['DB_SCHEDULING']
        dynamo.tables[table_name].update_item(
            Key={'PK': PK, 'SK': SK},
            UpdateExpression='SET active = :f',
            ExpressionAttributeValues={':f': False}
        )
    except Exception as e:
        print(e)
        abort(400)

    return redirect(url_for('scheduler.index'))
