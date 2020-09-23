"""
Jinja Template Filers
"""

# Standard libary imports
import os
import mimetypes

# Third party imports
import arrow
from flask import current_app


def datetime_humanize(date_str):
    """
    ISO-ish date format (with timezone conversion from UTC to EST)
    """
    dt = arrow.get(date_str)
    return dt.to('US/Eastern').format('ddd, MMM D h:mma')


def serialize(key):
    """
    Return serialized version of key name
    """
    s = current_app.config['SERIALIZER']
    return s.dumps(key)
