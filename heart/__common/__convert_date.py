"""Date utils for converting timestamps to different timezones and checking if they are in the past or future."""

from datetime import datetime, timezone

import dateutil.parser
import pytz
import tzlocal  # For local timezone detection


def get_local_timezone():
    """
    Detect the system's local timezone.

    Returns:
        pytz.timezone: The local timezone object.
    """
    return tzlocal.get_localzone()


def get_actual_date(timezone_name=None):
    """
    Get the current date and time in the specified timezone (or local if None).

    Args:
        timezone_name (str, optional): Name of the timezone. Defaults to None, which uses local time.

    Returns:
        datetime: The current date and time in the specified or local timezone.
    """
    if timezone_name is None:
        timezone_name = get_local_timezone()

    local_timezone = pytz.timezone(str(timezone_name))
    return datetime.now(local_timezone)


def convert_timestamp_to_utc(timestamp):
    """
    Convert an ISO 8601 formatted timestamp to a datetime object in UTC.

    Args:
        timestamp (str): ISO 8601 formatted timestamp.

    Returns:
        datetime: Datetime object in UTC timezone.
        str: Error message if the format is invalid.
    """
    try:
        return dateutil.parser.isoparse(timestamp).astimezone(timezone.utc)
    except ValueError as e:
        return f"Invalid timestamp format: {e}"


def convert_timestamp_to_local(timestamp, timezone_name=None):
    """
    Convert an ISO 8601 formatted timestamp to a datetime object in a specific timezone.

    Args:
        timestamp (str): ISO 8601 formatted timestamp.
        timezone_name (str, optional): Name of the target timezone. Defaults to None.

    Returns:
        datetime: Datetime object in the target timezone.
        str: Error message if the format is invalid.
    """
    try:
        utc_time = dateutil.parser.isoparse(timestamp).astimezone(timezone.utc)
        target_timezone = pytz.timezone(timezone_name or str(get_local_timezone()))
        return utc_time.astimezone(target_timezone)
    except ValueError as e:
        return f"Invalid timestamp format: {e}"


def check_timestamp_status(timestamp, timezone_name=None):
    """
    Convert timestamp to a specified timezone and check if it's in the past or future.

    Args:
        timestamp (str): ISO 8601 formatted timestamp.
        timezone_name (str, optional): Name of the target timezone. Defaults to None.

    Returns:
        str: A message indicating whether the timestamp is in the past or future.
    """
    try:
        utc_time = dateutil.parser.isoparse(timestamp).astimezone(timezone.utc)
        target_timezone = pytz.timezone(timezone_name or str(get_local_timezone()))
        local_time = utc_time.astimezone(target_timezone)

        now = datetime.now(target_timezone)

        # Calculate the difference
        time_difference = now - local_time
        days = abs(time_difference.days)
        hours, remainder = divmod(abs(time_difference.seconds), 3600)
        minutes, seconds = divmod(remainder, 60)

        if local_time < now:
            return (
                f"The date {local_time.strftime('%Y-%m-%d %H:%M:%S')} was {days} days, "
                f"{hours} hours, {minutes} minutes, and {seconds} seconds ago."
            )
        else:
            return (
                f"The date {local_time.strftime('%Y-%m-%d %H:%M:%S')} is in {days} days, "
                f"{hours} hours, {minutes} minutes, and {seconds} seconds."
            )

    except ValueError as e:
        return f"Invalid timestamp format: {e}"


def is_past_timestamp(timestamp):
    """
    Check if the provided timestamp is in the past, based on UTC time.

    Args:
        timestamp (str): ISO 8601 formatted timestamp.

    Returns:
        bool: True if the timestamp is in the past, False otherwise.
    """
    try:
        utc_time = dateutil.parser.isoparse(timestamp).astimezone(timezone.utc)
        return utc_time < datetime.now(timezone.utc)
    except ValueError:
        return False


# Get the current local time and UTC time
local_time = get_actual_date()
print(f"Local time: {local_time}")

utc_time = get_actual_date("UTC")
print(f"UTC time: {utc_time}")

# Convert local time to ISO 8601 string and pass it to check_timestamp_status
local_time_str = local_time.isoformat()
utc_status = check_timestamp_status(local_time_str)
print(utc_status)
