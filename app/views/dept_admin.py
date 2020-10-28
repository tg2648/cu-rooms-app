"""
Provides administrators with a way to export scheduler data.
"""

# Third party imports
from flask import (Blueprint,
                   render_template,
                   current_app,
                   request,
                   jsonify)
from flask_cas import login_required
from boto3.dynamodb.conditions import Attr

# Local application imports
from app.users import User
from app.logger import DynamoAccessLogger
from app.extensions import dynamo
from app.utils.scheduler import get_local_ISO_timestamp

bp = Blueprint('dept_admin', __name__, url_prefix='/dept_admin')
logger = DynamoAccessLogger('dept_admin')


# ROUTES
@bp.route('/')
@login_required
def index():

    current_user = User()
    if current_user.is_dept_admin():

        table_name = current_app.config['DB_SCHEDULING']
        resp_events = dynamo.tables[table_name].query(
            IndexName='start-index',
            KeyConditionExpression='PK = :pk',
            ExpressionAttributeValues={
                ':pk': f'EVENT#{current_user.dept}',
            },
        )

        logger.log_access(success=True, route='booking_list')
        return render_template('dept_admin.html', events=resp_events['Items'])

    else:

        logger.log_access(success=False, route='booking_list')
        return render_template('403.html')


@bp.route('/user_management')
@login_required
def user_management():

    current_user = User()
    if current_user.is_dept_admin():

        table_name = current_app.config['DB_SCHEDULING']
        resp_users = dynamo.tables[table_name].query(
            IndexName='reverse-index',
            KeyConditionExpression='SK = :sk AND PK > :pk',
            ExpressionAttributeValues={
                ':sk': current_user.dept,
                ':pk': 'USER',
            },
        )

        logger.log_access(success=True, route='user_management')
        return render_template('user_management.html', users=resp_users['Items'])

    else:

        logger.log_access(success=False, route='user_management')
        return render_template('403.html')


def add_users(add_list):
    """
    Adds users after parsing the input. Errors are reported as string messages.
    """
    table_name = current_app.config['DB_SCHEDULING']
    table = dynamo.tables[table_name]
    connection = dynamo.connection

    current_user = User()
    dept = current_user.dept

    success = 0
    errors = []

    if add_list:
        try:
            with table.batch_writer() as batch:
                for user in add_list:
                    if user.strip():
                        user_params = dict(zip(('uni', 'first_name', 'last_name', 'type'), [s.strip() for s in user.split(',')]))
                        if not user_params.get('uni'):
                            errors.append(f'{user}\n')
                            continue
                        try:
                            user_item = {
                                'PK': f"USER#{user_params.get('uni').lower()}",
                                'SK': dept,
                                'last_name': user_params.get('last_name', ''),
                                'first_name': user_params.get('first_name', ''),
                                'type': user_params.get('type', ''),
                                'added_by': current_user.uni,
                                'added_on': get_local_ISO_timestamp()
                            }
                            batch.put_item(Item=user_item)
                            success += 1
                        except Exception:
                            errors.append(f'{user}\n')
        except connection.meta.client.exceptions.ClientError:
            return 'Unexpected error when adding.'

    output = f'Added {success} user(s).'
    if errors:
        output = f"{output}\nUNABLE TO ADD THE FOLLOWING LINES:\n{''.join(errors)}"

    return output


def remove_users(remove_list):
    """
    Removes users listed in the input. Errors are reported as string messages.
    User's PK needs exists in the table, otherwise reported as error.
    """
    table_name = current_app.config['DB_SCHEDULING']
    table = dynamo.tables[table_name]
    connection = dynamo.connection

    current_user = User()
    dept = current_user.dept

    success = 0
    errors = []

    if remove_list:
        try:
            for user in remove_list:
                if user.strip():
                    try:
                        user_item = {
                            'PK': f'USER#{user.lower()}',
                            'SK': dept
                        }
                        # Only delete user its PK exists
                        table.delete_item(Key=user_item, ConditionExpression=Attr('PK').exists())
                        success += 1
                    except Exception:
                        errors.append(f'{user}\n')
        except connection.meta.client.exceptions.ClientError:
            return 'Unexpected error when removing.'

    output = f'Removed {success} user(s).'
    if errors:
        output = f"{output}\nUNABLE TO REMOVE THE FOLLOWING UNIS:\n{''.join(errors)}"

    return output


@bp.route('/user_management/batch', methods=['POST'])
@login_required
def process_batch():
    """
    Input from two text fields are sent to this route for processing. HTML's <textarea>'s newlines are '\r\n'
    """

    current_user = User()
    if current_user.is_dept_admin():

        add_list = set(request.form['add'].split('\r\n')) if request.form['add'] else []
        remove_list = set(request.form['remove'].split('\r\n')) if request.form['remove'] else []

        add_output = add_users(add_list)
        remove_output = remove_users(remove_list)

        output_str = f'{add_output}\n{remove_output}'
        logger.log_access(success=True, route='user_management_batch')
        return jsonify(output=output_str), 200

    else:

        logger.log_access(success=False, route='user_management_batch')
        return render_template('403.html')
