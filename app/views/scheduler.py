"""
Scheduler
"""
# Standard library imports
from uuid import uuid4
from operator import itemgetter
from datetime import datetime, timedelta

# Third party imports
from flask import (Blueprint,
                   render_template,
                   request,
                   redirect,
                   url_for,
                   current_app,
                   abort,
                   jsonify)
from flask.json import dumps as json_dumps
from flask_cas import login_required

from boto3.dynamodb.conditions import Attr
from itsdangerous.exc import BadSignature

# Local application imports
from app.users import User
from app.logger import DynamoAccessLogger
from app.extensions import dynamo

from app.utils.scheduler import decimal_conversion, datetime_to_EST, get_local_ISO_timestamp, is_overlapping

bp = Blueprint('scheduler', __name__)
logger = DynamoAccessLogger('room_scheduler')

BOOKING_LIMIT_PER_WEEK = 5


# ROUTES
@bp.route('/')
@login_required
def index():
    current_user = User()
    logger.log_access(has_access=True)

    dept = 'ECON'

    table_name = current_app.config['DB_SCHEDULING']
    resp_events = dynamo.tables[table_name].query(
        IndexName='uni-PK-index',
        KeyConditionExpression='uni = :uni AND PK = :pk',
        ExpressionAttributeValues={
            ':uni': current_user.uni,
            ':pk': f'EVENT#{dept}',
        },
    )

    # Sort by start time
    events = sorted(resp_events['Items'], key=itemgetter('start'))

    return render_template('scheduler.html', events=events)


@bp.route('/event_data')
def event_data():

    if not ('start' in request.args and 'end' in request.args):
        return redirect(url_for('scheduler.index'))

    dept = 'ECON'

    table_name = current_app.config['DB_SCHEDULING']
    resp_events = dynamo.tables[table_name].query(
        IndexName='start-index',
        KeyConditionExpression='PK = :pk AND #s BETWEEN :lower AND :upper',
        ExpressionAttributeValues={
            ':pk': f'EVENT#{dept}',
            ':lower': f"{request.args.get('start')}",
            ':upper': f"{request.args.get('end')}",
        },
        ExpressionAttributeNames={
            '#s': 'start',
        },
        FilterExpression=Attr('active').eq(True)
    )

    resp_notavailable = dynamo.tables[table_name].query(
        KeyConditionExpression='PK = :pk',
        ExpressionAttributeValues={
            ':pk': f'BLOCK#{dept}',
        },
    )

    resp_events['Items'].extend(resp_notavailable['Items'])

    # Dynamo returns numbers as Decimal objects, convert to integers with the default functions
    return json_dumps(resp_events['Items'], default=decimal_conversion)


@bp.route('/resource_data')
def resource_data():

    dept = 'ECON'

    table_name = current_app.config['DB_SCHEDULING']
    resp_resources = dynamo.tables[table_name].query(
        KeyConditionExpression='PK = :pk',
        ExpressionAttributeValues={
            ':pk': f'RESOURCE#{dept}',
        },
    )

    return jsonify(resp_resources['Items'])


@bp.route('/event_modify', methods=['POST'])
def event_modify():
    """
    Application logic for moving an event to a different time/day/resource.
    Payload should contain the following attributes:
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
        ':t': get_local_ISO_timestamp(),
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


@bp.route('/event_create', methods=['POST'])
def event_create():
    """
    Server response to the `select` fullcalendar callback.

    Payload should contain the following attributes:
        - start: event start timestamp
        - end: event end timestamp
        - resourceId: id of the resource where event was scheduled
        - resourceName: name of the resource where event was scheduled
        - viewStart: the start of the interval the calendar currently represents
        - viewEnd: the end of the interval the calendar currently represents

    viewStart and viewEnd are used to check for overlapping events by getting all
    events between the two timestamps for the resourceId. The are in UTC time so
    they are first converted to EDT/EST.

    If no overlaps are present, event metadata is recorded to DynamoDB.
    """

    table_name = current_app.config['DB_SCHEDULING']
    current_user = User()
    uni = current_user.uni
    dept = 'ECON'

    request_data = request.json
    resourceId = request_data.get('resourceId')
    event_start = request_data.get('start')
    event_end = request_data.get('end')

    view_start = datetime_to_EST(request_data['viewStart'])
    view_end = datetime_to_EST(request_data['viewEnd'])

    event_start_obj = datetime.strptime(event_start[:-6], '%Y-%m-%dT%H:%M:%S')
    start_of_week = event_start_obj - timedelta(days=event_start_obj.weekday())  # Monday
    end_of_week = start_of_week + timedelta(days=6)  # Sunday

    resp_events_week = dynamo.tables[table_name].query(
        IndexName='uni-start-index',
        KeyConditionExpression='uni = :uni AND #s BETWEEN :lower AND :upper',
        ExpressionAttributeValues={
            ':uni': uni,
            ':lower': start_of_week.strftime('%Y-%m-%d'),
            ':upper': end_of_week.strftime('%Y-%m-%d'),
        },
        ExpressionAttributeNames={
            '#s': 'start',
        },
        FilterExpression=Attr('active').eq(True),
        ProjectionExpression='SK',  # Don't need actual data
    )

    if (resp_events_week['Count'] >= BOOKING_LIMIT_PER_WEEK):
        return "You've exceeded your booking limit for this week.", 500

    resp_events_view = dynamo.tables[table_name].query(
        IndexName='resourceId-start-index',
        KeyConditionExpression='resourceId = :r AND #s BETWEEN :lower AND :upper',
        ExpressionAttributeValues={
            ':r': resourceId,
            ':lower': view_start,
            ':upper': view_end,
        },
        ExpressionAttributeNames={
            '#s': 'start',
        },
        FilterExpression=Attr('active').eq(True)
    )

    if (is_overlapping(resp_events_view['Items'], request_data)):
        return 'Your booking overlaps with another booking or a reserved time.', 500

    item = {
        'PK': f'EVENT#{dept}',
        'SK': f"{request_data.get('resourceId')}#{uuid4()}",
        'start': event_start,
        'end': event_end,
        'resourceId': resourceId,
        'resourceName': request_data.get('resourceName'),
        'title': uni,
        'uni': uni,
        'active': True,
        'createdOn': get_local_ISO_timestamp(),
        'changedOn': '',
        'dept': dept,
    }

    try:
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
