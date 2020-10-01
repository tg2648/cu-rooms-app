"""
Jinja Template Filers
"""

# Third party imports
import arrow
from flask import current_app

# Local application imports
from app.users import User


def datetime_humanize(date_str):
    """
    Human-friendly format: Weekday, month day am/pm time
    """
    dt = arrow.get(date_str)
    return dt.to('US/Eastern').format('ddd, MMM D h:mma')


def datetime_custom(date_str):
    dt = arrow.get(date_str)
    return dt.to('US/Eastern').format('YYYY-MM-DD HH:mm')


def datetime_date(date_str):
    """
    Date part of the datetime string
    """
    dt = arrow.get(date_str)
    return dt.to('US/Eastern').format('YYYY-MM-DD')


def datetime_time(date_str):
    """
    Time part of the datetime string
    """
    dt = arrow.get(date_str)
    return dt.to('US/Eastern').format('HH:mm')


def user_is_dept_admin(uni):
    """
    Wrap `User`'s functionality to be available inside templates
    """
    return User(uni).is_dept_admin()


def serialize(key):
    """
    Return serialized version of key name
    """
    s = current_app.config['SERIALIZER']
    return s.dumps(key)
