"""
Utils for the room scheduler.
"""
# Standard library imports
from decimal import Decimal
from datetime import datetime
from operator import itemgetter

# Third party imports
import arrow
from natsort import natsorted


def decimal_conversion(obj):
    """
    Conversion function for json.dumps to convert Decimal objects to integers
    https://stackoverflow.com/questions/31202956/json-typeerror-decimal34-3-is-not-json-serializable
    """
    if isinstance(obj, Decimal):
        return int(obj)
    raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)


def datetime_to_EST(dt):
    """Convert a datetime to EST/EDT formatted in ISO8601"""
    return arrow.get(dt).to('US/Eastern').format('YYYY-MM-DDTHH:mm:ssZZ')


def get_local_ISO_timestamp():
    """Returns current time converted to EDT/EST in ISO8601"""
    return datetime_to_EST(arrow.utcnow())


def is_overlapping(events, newEvent):
    """
    Checks if `newEvent` overlaps with any events in `events` by converting start/end
    timestamps to datetime objects and comparing.
    In python 3.6 datetime cannot parse timezones with a colon, ignore the last 6 characters.
    """

    newEventStart = datetime.strptime(newEvent.get('start')[:-6], '%Y-%m-%dT%H:%M:%S')
    newEventEnd = datetime.strptime(newEvent.get('end')[:-6], '%Y-%m-%dT%H:%M:%S')

    for event in events:
        eventStart = datetime.strptime(event['start'][:-6], '%Y-%m-%dT%H:%M:%S')
        eventEnd = datetime.strptime(event['end'][:-6], '%Y-%m-%dT%H:%M:%S')

        if (newEventStart > eventStart) & (newEventStart < eventEnd):
            # Start-time in between any of the events'
            return True

        if (newEventEnd > eventStart) & (newEventEnd < eventEnd):
            # End-time in between any of the events
            return True

        if (newEventStart <= eventStart) & (newEventEnd >= eventEnd):
            # Any of the events in between/on the start-time and end-time
            return True

    return False


def natmultisort(data, specs):
    """
    "Natural" multisort
    https://docs.python.org/3/howto/sorting.html#sort-stability-and-complex-sorts

    Args:
        data (list[dict])
        specs (Tuple[Tuple]): Each tuple consists of
            0: Attribute to sort by
            1: True for a descending sort

    Returns:
        Sorted list[dict]
    """

    temp = data
    for key, reverse in reversed(specs):
        temp = natsorted(temp, key=itemgetter(key), reverse=reverse)

    return temp
