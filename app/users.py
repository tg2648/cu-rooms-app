"""
User class
"""

# Third party imports
from flask import current_app
from flask import session
from flask import has_request_context

# Local application imports
from app.extensions import dynamo


class User(object):
    """User class that interfaces with the session cookie and DynamoDB. Represents a single user.

    DynamoDB is queried if:
        1. Request context exists AND session contains CAS login info
        OR
        2. User was initialized with a UNI

    Args:
        uni (str, optional): user's UNI.
            If used, then flask session is ignored. Otherwise, uni is obtained from flask session.

    Example:
            user_1 = User() # Will use session to obtain UNI from CAS login
            user_2 = User('abc123') # UNI is set to 'abc123'

    """

    def __init__(self, uni=None):
        """
        If provided, initialize with a given UNI
        """
        self._uni = uni

    @property
    def app(self):
        """
        Current FLask instance
        """
        return current_app

    @property
    def table_name(self):
        """
        Name of the DynamoDB table to use
        """
        return self.app.config['DB_SCHEDULING']

    @property
    def uni(self):
        """
        Returns:
            If initialized without a UNI - returns user's UNI from session cookie
                after logging in with CAS
            If initialized with a UNI - returns provided UNI
        """

        if self._uni is None:
            if has_request_context() and 'CAS_USERNAME' in session:
                return session.get('CAS_USERNAME', 'None')
            else:
                return 'None'
        else:
            return str(self._uni)

    @property
    def dept(self):
        """
        Returns user's department. If user is not registered to use the application, returns an empty string.
        """
        if (has_request_context() and 'CAS_USERNAME' in session) or (self._uni is not None):

            response = dynamo.tables[self.table_name].query(
                KeyConditionExpression='PK = :pk',
                ExpressionAttributeValues={
                    ':pk': f'USER#{self.uni}',
                },
            )

            try:
                return response['Items'][0]['SK']
            except IndexError:
                return ''

        else:

            return ''

    def is_admin(self):
        if (has_request_context() and 'CAS_USERNAME' in session) or (self._uni is not None):

            response = dynamo.tables[self.table_name].query(
                KeyConditionExpression='PK = :pk',
                ExpressionAttributeValues={
                    ':pk': f'USER#{self.uni}',
                },
            )

            try:
                return response['Items'][0]['SK'] == 'ADMIN'
            except IndexError:
                return False

        else:

            return False

    def is_dept_admin(self):
        if (has_request_context() and 'CAS_USERNAME' in session) or (self._uni is not None):

            response = dynamo.tables[self.table_name].query(
                KeyConditionExpression='PK = :pk',
                ExpressionAttributeValues={
                    ':pk': f'USER#{self.uni}',
                },
            )

            try:
                return response['Items'][0]['type'] in ['Staff', 'Chair']
            except IndexError:
                return False

        else:

            return False
