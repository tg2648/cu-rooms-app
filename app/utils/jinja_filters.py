"""
Jinja Template Filers
"""

# Standard libary imports
import os
import mimetypes

# Third party imports
import arrow
from flask import current_app


def datetimeformat(date_str):
    """
    Human-readable date format
    """
    dt = arrow.get(date_str)
    return dt.humanize()


def datetime_utc_to_est(date_str):
    """
    ISO-ish date format (with timezone conversion from UTC to EST)
    """
    dt = arrow.get(date_str)
    return dt.to('US/Eastern').format('YYYY-MM-DD h:mma')


def file_type(key):
    """
    Identifies type of a file based on the extension from object key
    """
    file_info = os.path.splitext(key)
    file_extension = file_info[1]
    return mimetypes.types_map.get(file_extension, 'Unknown')


def file_name(key):
    """
    Returns file name from object key
    """
    return os.path.basename(key)


def serialize(key):
    """
    Return serialized version of key name
    """
    s = current_app.config['SERIALIZER']
    return s.dumps(key)


def convert_to_list(iterable):
    return list(iterable)
