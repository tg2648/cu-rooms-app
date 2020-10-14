"""
Scheduler
"""
# Standard library imports
from uuid import uuid4
from operator import itemgetter

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

from app.utils.scheduler import (decimal_conversion,
                                 datetime_to_EST,
                                 get_local_ISO_timestamp,
                                 is_overlapping,
                                 natmultisort)

bp = Blueprint('scheduler', __name__)
logger = DynamoAccessLogger('room_scheduler')


# ROUTES
@bp.route('/')
@login_required
def index():
    current_user = User()
    dept = current_user.dept

    if dept:

        logger.log_access(success=True, route='index')

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

    table_name = current_app.config['DB_SCHEDULING']
    resp_events = dynamo.tables[table_name].query(
        IndexName='start-index',
        KeyConditionExpression='PK = :pk AND #s BETWEEN :lower AND :upper',
        ExpressionAttributeValues={
            ':pk': f'EVENT#{current_user.dept}',
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
            ':pk': f'BLOCK#{current_user.dept}',
        },
    )

    resp_events['Items'].extend(resp_notavailable['Items'])

    # Dynamo returns numbers as Decimal objects, convert to integers with the default functions
    return json_dumps(resp_events['Items'], default=decimal_conversion)


@bp.route('/resource_data', methods=['POST'])
def resource_data():
    """
    Returns all resources for the user's department
    """
    current_user = User()

    table_name = current_app.config['DB_SCHEDULING']
    resp_resources = dynamo.tables[table_name].query(
        KeyConditionExpression='PK = :pk',
        ExpressionAttributeValues={
            ':pk': f'RESOURCE#{current_user.dept}',
        },
    )

    # Use natural sorting to make sure 900 comes before 1000, etc.
    return jsonify(natmultisort(resp_resources['Items'], (('room', False), ('title', False))))


@bp.route('/event_modify', methods=['POST'])
def event_modify():
    """
    Application logic for moving an event to a different time/day/resource.
    Called by `eventResize` and `eventDrop` fullcalendar callbacks

    Payload should contain the following attributes:
        PK: Primary key of the event,
        SK: Sort key of the event,
        uni: Event owner's uni,
        start: Start time of the modified event,
        end: End time of the modified event

    If the event is moved to a new resource, the payload should also contain:
        newResourceId: Resource ID of the modified event,
        newResourceName: Resource name of the modified event
    """

    data = request.json
    current_user = User()

    if data['uni'] != current_user.uni:
        logger.log_access(success=False, route='event_modify', error='NotOwnReservation')
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

    logger.log_access(success=True, route='event_modify')
    return 'Success', 200


@bp.route('/event_create', methods=['POST'])
def event_create():
    """
    Application logic for creating an event.
    Called by the `select` fullcalendar callback.

    Payload should contain the following attributes:
        - start: event start timestamp
        - end: event end timestamp
        - resourceId: id of the resource where event was scheduled
        - resourceName: name of the resource where event was scheduled
        - viewStart: the start of the interval the calendar currently represents
        - viewEnd: the end of the interval the calendar currently represents

    viewStart and viewEnd are used to check for overlapping events by getting all
    events between the two timestamps for the resourceId. They are in UTC time so
    they are first converted to EDT/EST.

    If no overlaps are present, event metadata is recorded to DynamoDB.
    """

    table_name = current_app.config['DB_SCHEDULING']
    current_user = User()
    uni = current_user.uni
    dept = current_user.dept

    request_data = request.json
    resourceId = request_data.get('resourceId')
    event_start = request_data.get('start')
    event_end = request_data.get('end')

    view_start = datetime_to_EST(request_data['viewStart'])
    view_end = datetime_to_EST(request_data['viewEnd'])

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
        logger.log_access(success=False, route='event_create', error='Overlap')
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
        logger.log_access(success=False, route='event_create', error='Unexpected 500')
        return 'Unexpected error occured', 500

    logger.log_access(success=True, route='event_create')
    return 'Success', 200


@bp.route('/event_delete', methods=['POST'])
def event_delete():
    """
    Application logic for deleting an event.
    """

    s = current_app.config['SERIALIZER']

    try:
        PK = s.loads(request.form['PK'])
        SK = s.loads(request.form['SK'])
    except BadSignature:
        logger.log_access(success=False, route='event_delete', error='BadSignature')
        abort(400)

    try:
        table_name = current_app.config['DB_SCHEDULING']
        dynamo.tables[table_name].update_item(
            Key={'PK': PK, 'SK': SK},
            UpdateExpression='SET active = :f, changedOn = :t',
            ExpressionAttributeValues={
                ':f': False,
                ':t': get_local_ISO_timestamp(),
            }
        )
    except Exception:
        logger.log_access(success=False, route='event_delete', error='Unexpected 500')
        return 'Unexpected error occured', 500

    logger.log_access(success=True, route='event_delete')
    return redirect(url_for('scheduler.index', _anchor='history'))


@bp.route('/ping')
def ping():
    """
    ELB health checks fail because accessing the root of the app redirects to CAS login.
    This route simply returns the 200 code for the health check
    """
    return 'Success', 200
