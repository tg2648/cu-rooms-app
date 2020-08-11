"""
User class
"""

# Third party imports
from flask import current_app
from flask import session
from flask import has_request_context

from boto3.dynamodb.conditions import Attr

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
    def user_table_name(self):
        """
        Name of the DynamoDB table to use
        """
        return self.app.config['DB_USERS']

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
    def obj(self):
        """
        Returns the entire user object as a dictionary
        """
        if (has_request_context() and 'CAS_USERNAME' in session) or (self._uni is not None):

            try:
                response = dynamo.tables[self.user_table_name].get_item(Key={'UNI': self.uni})
                return response['Item']
            except KeyError:
                return None

        else:
            return None

    def fif_access(self, arg):
        """
        Get details about user's access to the FIF dashboard for a given argument.
        Argument options:
            - 'dept' returns a list of departments to which user has faculty-level access
            - 'chair_dept' returns a list of department codes for which user has chair-level access

        Returns:
            - If user has access: a list of department codes
            - If user does not have access (either not in DB or no access to dashboard): empty list
        """
        if (has_request_context() and 'CAS_USERNAME' in session) or (self._uni is not None):

            try:
                response = dynamo.tables[self.user_table_name].get_item(Key={'UNI': self.uni})
                return sorted(list(response['Item']['fif'][arg]))
            except KeyError:
                return []

        else:
            return []

    def searchcom_access(self):
        """
        Get details about user's access to the search dashboard
        Returns:
            - If user has access: a list of requisition numbers to which user has access to
            - If user does not have access (either not in DB or no access to dashboard): empty list
        """
        if (has_request_context() and 'CAS_USERNAME' in session) or (self._uni is not None):

            try:
                # TODO: can optimize by using ProjectionExpression to return only the requirements?
                response = dynamo.tables[self.user_table_name].get_item(Key={'UNI': self.uni})
                return sorted(list(response['Item']['searchcom']['reqs']))
            except KeyError:
                return []

        else:
            return []

    def admin_access(self):
        """
        Get details about user's access to the Admin dashboard
        Returns:
            - If user has access: True
            - If user does not have access (either not in DB or no admin access): False
        """
        if (has_request_context() and 'CAS_USERNAME' in session) or (self._uni is not None):

            try:
                response = dynamo.tables[self.user_table_name].get_item(Key={'UNI': self.uni})
                return response['Item']['admin_tag']
            except KeyError:
                return False

        else:
            return False


class UserBatch(object):
    """DynamoDB interface to query the users table. Batch user operations.
    """

    @property
    def app(self):
        """
        Current FLask instance
        """
        return current_app

    @property
    def user_table_name(self):
        """
        Name of the DynamoDB table to use
        """
        return self.app.config['DB_USERS']

    def attribute_contains_search(self, attribute, value):
        """
        Returns search results where an attribute contains a certain value.
        """
        table = dynamo.tables[self.user_table_name]

        response = table.scan(
            ConsistentRead=True,
            FilterExpression=Attr(attribute).contains(value)
        )
        return response['Items']

    def attribute_eq_search(self, attribute, value):
        """
        Returns search results where an attribute contains a certain value.
        """
        table = dynamo.tables[self.user_table_name]

        response = table.scan(
            ConsistentRead=True,
            FilterExpression=Attr(attribute).eq(value)
        )
        return response['Items']
