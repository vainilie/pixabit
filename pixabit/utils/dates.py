"""
>> ─── Date and Time Utilities ──────────────────────────────────────────────────
This module provides utility functions for date and time manipulation, including converting timestamps to UTC, checking if a date has passed, and formatting dates.
"""

from datetime import datetime, timezone

import dateutil.parser
from tzlocal import get_localzone

from .display import console, print


# >> Convert timestamp to UTC
def convert_timestamp(timestamp):
    """Convert timestamp to a datetime object in UTC timezone"""
    try:
        utc_time = dateutil.parser.isoparse(timestamp).astimezone(timezone.utc)
        return utc_time

    except ValueError as e:
        console.print(f"[error]Invalid timestamp format:[/] {e}")


# >> Check if date has passed
def is_date_passed(timestamp):
    try:
        # Convert timestamp to a datetime object in UTC timezone
        utc_time = dateutil.parser.isoparse(timestamp).astimezone(timezone.utc)

        # Get the current datetime in UTC timezone
        now = datetime.now(timezone.utc)

        # Check if the date has already passed
        return utc_time < now

    except ValueError:
        # Invalid timestamp format
        return False


# >> Convert UTC to local time
def convert_to_local_time(utc):

    utc_time = dateutil.parser.parse(utc)
    local_timezone = get_localzone()
    return utc_time.astimezone(local_timezone).replace(microsecond=0)


# >> Convert timestamp to local time and check if the date has passed
def convert_and_check_timestamp(timestamp):
    """Convert a timestamp to local time and check if the date has passed.
    Args:
        timestamp (str): The timestamp to convert, in ISO 8601 format.
    Returns:
        str: A message indicating the time left or how long ago the date was.
    """

    try:
        # Convert timestamp to a datetime object in UTC timezone
        utc_time = dateutil.parser.isoparse(timestamp).astimezone(timezone.utc)

        # Convert UTC time to your local timezone
        local_tz = get_localzone()
        local_time = utc_time.astimezone(local_tz)

        # Check if the date has already passed
        now = datetime.now(local_tz)

        if local_time < now:
            past_time = now - local_time
            days = past_time.days
            hours, remainder = divmod(past_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            console.print(
                f"The date {local_time.strftime('%Y-%m-%d %H:%M:%S')} was {days} days, {hours} hours, {minutes} minutes, and {seconds} seconds ago."
            )

        # Calculate the time left to the date
        time_left = local_time - now
        days = time_left.days
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        console.print(
            f"The date {local_time.strftime('%Y-%m-%d %H:%M:%S')} is in {days} days, {hours} hours, {minutes} minutes, and {seconds} seconds."
        )

    except ValueError as e:
        console.print(f"[error]Invalid timestamp format:[/] {e}")
