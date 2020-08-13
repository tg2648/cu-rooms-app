"""
Logger class
"""

# Standard library imports
import datetime

# Third party imports
from flask import current_app
from flask import session
from flask import has_request_context

# import boto3
# from boto3.dynamodb.conditions import Key, Attr

# Local application imports
from app.extensions import dynamo


class DynamoAccessLogger(object):
    """Access Logger

    Handles logging of user access to CAS-protected pages.

    Args:
        resource (str): Resource which the logger will log access to
            Each resource has its own instance of the logger class
    """

    def __init__(self, resource=None):
        self.resource = resource

    @property
    def app(self):
        """Current Flask instance."""
        return current_app

    @property
    def access_table_name(self):
        """str: Name of the DynamoDB table with access data."""
        return self.app.config['DB_ACCESS_LOGS']

    @property
    def user_table_name(self):
        """str: Name of the DynamoDB table with user data."""
        return self.app.config['DB_USERS']

    def log_access(self, has_access, **kwargs):
        """Logs users access.

            accessedBy: user's UNI, comes from the session.
            resource: which resource is being accessed, initialized at logger creation.
            timestamp: current UTC timestamp in ISO8601.

        Args:
            has_access (bool): Whether or not user is authorized to see the contents of a view at the time of access.
        """

        if has_request_context():

            access_table = dynamo.tables[self.access_table_name]
            timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

            # Default payload
            item = {
                'resource-timestamp': f'{self.resource}#{timestamp}',
                'resource': self.resource,
                'timestamp': timestamp,
                'has_access': has_access
            }

            # Additional payload based on keyword arguments
            for key, value in kwargs.items():
                item[key] = value

            if 'CAS_USERNAME' in session:

                item['accessedBy'] = session.get('CAS_USERNAME')
                access_table.put_item(Item=item)

            # else:

            #     item['accessedBy'] = 'DEBUG'
            #     access_table.put_item(Item=item)
