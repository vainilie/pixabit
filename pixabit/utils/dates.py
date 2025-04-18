# pixabit/utils/dates.py

# SECTION: MODULE DOCSTRING
"""Provides utility functions for date and time manipulation.

Includes functions for handling timestamps from the Habitica API, converting
between UTC and local time, checking if dates are past, and formatting
timedeltas. Requires `dateutil` and `tzlocal`.
"""

# SECTION: IMPORTS
from datetime import datetime, timedelta, timezone
from typing import Optional

import dateutil.parser
from tzlocal import (
    get_localzone,
    get_localzone_name,
)  # Import get_localzone_name too

# Use themed console/print if available
try:
    from .display import console, print
except ImportError:  # Fallback
    import builtins

    print = builtins.print

    # Provide a dummy console object to avoid AttributeErrors
    class DummyConsole:  # noqa: D101
        def print(self, *args, **kwargs):  # noqa: D102
            builtins.print(*args)

        def log(self, *args, **kwargs):  # noqa: D102
            builtins.print("LOG:", *args)  # Add LOG prefix

    console = DummyConsole()

# SECTION: FUNCTIONS


# FUNC: convert_timestamp_to_utc
def convert_timestamp_to_utc(timestamp: Optional[str]) -> Optional[datetime]:
    """Converts an ISO 8601 timestamp string to a timezone-aware datetime object in UTC.

    Handles timestamps with or without timezone information (assumes UTC if naive).

    Args:
        timestamp: The timestamp string (e.g., "2023-10-27T10:00:00.000Z") or None.

    Returns:
        A timezone-aware datetime object in UTC, or None if parsing fails or input is None.
    """
    if not timestamp:
        return None
    try:
        # Use dateutil.parser which handles various ISO 8601 formats including 'Z'
        dt_object = dateutil.parser.isoparse(timestamp)
        # If isoparse results in a naive datetime, assume it was UTC
        if (
            dt_object.tzinfo is None
            or dt_object.tzinfo.utcoffset(dt_object) is None
        ):
            dt_object = dt_object.replace(tzinfo=timezone.utc)
        # Ensure the final object is in UTC timezone
        return dt_object.astimezone(timezone.utc)
    except (ValueError, TypeError) as e:
        console.print(
            f"Error parsing timestamp '{timestamp}' to UTC: {e}",
            style="warning",
        )
        return None


# FUNC: is_date_passed
def is_date_passed(timestamp: Optional[str]) -> Optional[bool]:
    """Checks if the date/time represented by the timestamp string is in the past.

    Compares the timestamp (converted to UTC) against the current UTC time.

    Args:
        timestamp: The timestamp string to check (ISO 8601 format), or None.

    Returns:
        True if the timestamp is strictly in the past, False if it's now or in the future.
        Returns None if the timestamp is invalid or None.
    """
    utc_time = convert_timestamp_to_utc(timestamp)
    if utc_time is None:
        return None  # Invalid or None timestamp input

    # Get the current time in UTC
    now_utc = datetime.now(timezone.utc)

    # Perform the comparison
    return utc_time < now_utc


# FUNC: convert_to_local_time
def convert_to_local_time(utc_dt_str: Optional[str]) -> Optional[datetime]:
    """Converts a UTC timestamp string to a timezone-aware datetime in the local system timezone.

    Args:
        utc_dt_str: The timestamp string (assumed UTC or ISO 8601 with tzinfo), or None.

    Returns:
        A timezone-aware datetime object in the local timezone, with microseconds
        removed, or None on error or None input.
    """
    utc_time = convert_timestamp_to_utc(
        utc_dt_str
    )  # Use consistent UTC conversion first
    if utc_time is None:
        return None  # Handle invalid input from the start

    try:
        local_timezone = get_localzone()  # Get the local zone object
        # Convert the UTC datetime object to the local timezone
        local_time = utc_time.astimezone(local_timezone)
        # Remove microseconds for cleaner display
        return local_time.replace(microsecond=0)
    except Exception as e:  # Catch potential errors during timezone conversion
        local_tz_name = "Unknown"
        try:
            local_tz_name = get_localzone_name()
        except Exception:
            pass
        console.print(
            f"Error converting UTC time '{utc_dt_str}' to local zone '{local_tz_name}': {e}",
            style="warning",
        )
        return None


# FUNC: format_timedelta
def format_timedelta(delta: timedelta) -> str:
    """Formats a timedelta into a human-readable string.

    Examples: "in 2d 03:15:30", "1d 10:05:00 ago", "00:00:05 ago", "in 00:10:00".

    Args:
        delta: The timedelta object to format.

    Returns:
        A human-readable string representation of the timedelta.
    """
    total_seconds_float = delta.total_seconds()
    is_past = total_seconds_float < 0

    # Work with the absolute duration for calculations
    abs_delta = abs(delta)
    total_abs_seconds = int(abs_delta.total_seconds())  # Use int for divmod

    days = abs_delta.days  # Days part of the timedelta
    seconds_within_day = total_abs_seconds % (
        24 * 3600
    )  # Seconds part within the last day

    hours, remainder = divmod(seconds_within_day, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts: list[str] = []
    if days > 0:
        parts.append(f"{days}d")

    # Always show HH:MM:SS, padding with zeros
    parts.append(f"{hours:02}:{minutes:02}:{seconds:02}")

    time_str = " ".join(parts)

    if is_past:
        return f"{time_str} ago"
    else:
        # Handle the case where timedelta is exactly zero
        if total_seconds_float == 0:
            return "now"
        return f"in {time_str}"


# FUNC: convert_and_check_timestamp
def convert_and_check_timestamp(timestamp: Optional[str]) -> Optional[str]:
    """Converts a timestamp to local time and returns a formatted string indicating time difference.

    Args:
        timestamp: The timestamp string to check (ISO 8601 format) or None.

    Returns:
        A string like "YYYY-MM-DD HH:MM:SS (in Xd HH:MM:SS)" or "... ago",
        "Invalid Timestamp (...)" on parsing error, or None if input is None.
    """
    if not timestamp:
        return None

    local_time = convert_to_local_time(timestamp)
    if local_time is None:
        return f"Invalid Timestamp ({timestamp})"  # Indicate parsing/conversion error

    try:
        # Get current time in the *same* local timezone for accurate comparison
        local_timezone = get_localzone()
        now_local = datetime.now(local_timezone).replace(microsecond=0)

        # Calculate the difference
        time_difference = local_time - now_local

        # Format the difference and the local time
        formatted_diff = format_timedelta(time_difference)
        local_time_str = local_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )  # Format without microseconds

        return f"{local_time_str} ({formatted_diff})"
    except Exception as e:
        console.print(
            f"Error formatting local time difference for '{timestamp}': {e}",
            style="warning",
        )
        # Fallback if formatting fails but conversion worked
        try:
            return (
                local_time.strftime("%Y-%m-%d %H:%M:%S")
                + " (Error formatting diff)"
            )
        except Exception:
            return f"Invalid Timestamp ({timestamp})"  # Fallback if everything fails
