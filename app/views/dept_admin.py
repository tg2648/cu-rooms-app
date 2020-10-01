"""
Provides administrators with a way to export scheduler data.
"""

# Third party imports
from flask import (Blueprint,
                   render_template,
                   current_app)
from flask_cas import login_required

# Local application imports
from app.users import User
from app.logger import DynamoAccessLogger
from app.extensions import dynamo

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

        logger.log_access(success=True, route='index')
        return render_template('dept_admin.html', events=resp_events['Items'])

    else:

        logger.log_access(success=False, route='index')
        return render_template('403.html')
