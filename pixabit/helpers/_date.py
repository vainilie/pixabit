# pixabit/helpers/_date.py

# SECTION: MODULE DOCSTRING
"""Provides utility functions for date and time manipulation, especially for Habitica timestamps.

Includes functions for handling ISO 8601 timestamps, converting between UTC
and local time, checking if dates are past, and formatting timedeltas.
Requires `python-dateutil` and `tzlocal`.
"""

# SECTION: IMPORTS
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Optional

import dateutil.parser
from dateutil.tz import tzlocal  # Preferred import for local timezone object

# Use themed console/print if available from ._rich
try:
    from ._rich import console

    # No need to redefine print if console.print is used directly
except ImportError:
    import logging  # Use standard logging if rich isn't available

    # Define a basic console object for logging if rich fails
    class FallbackConsole:
        def print(self, *args, style: str = "", **kwargs):
            level = logging.WARNING if style == "warning" else logging.INFO
            logging.log(level, " ".join(map(str, args)))

        def log(self, *args, style: str = "", **kwargs):
            level = logging.WARNING if style == "warning" else logging.INFO
            logging.log(level, " ".join(map(str, args)))

    console = FallbackConsole()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# SECTION: FUNCTIONS


def convert_unix_to_utc(timestamp_ms):
    timestamp_s = timestamp_ms / 1000
    dt_utc = datetime.datetime.fromtimestamp(timestamp_s, datetime.timezone.utc)
    return dt_utc


# FUNC: convert_timestamp_to_utc
def convert_timestamp_to_utc(timestamp: str | None) -> datetime | None:
    """Converts an ISO 8601 timestamp string to a timezone-aware datetime object in UTC.

    Handles timestamps with or without timezone information (assumes UTC if naive).
    Also handles potential integer/float timestamps (assumed seconds).

    Args:
        timestamp: The timestamp string (e.g., "2023-10-27T10:00:00.000Z"),
                   a number (seconds since epoch), or None.

    Returns:
        A timezone-aware datetime object in UTC, or None if parsing fails or input is None.
    """
    if timestamp is None:
        return None

    dt_object: datetime | None = None
    try:
        if isinstance(timestamp, (int, float)):
            # Assume seconds since epoch if it's a number
            dt_object = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        elif isinstance(timestamp, str):
            # Use dateutil.parser which handles various ISO 8601 formats including 'Z'
            dt_object = dateutil.parser.isoparse(timestamp)
            # If isoparse results in a naive datetime, assume it was UTC
            if (
                dt_object.tzinfo is None
                or dt_object.tzinfo.utcoffset(dt_object) is None
            ):
                dt_object = dt_object.replace(tzinfo=timezone.utc)
            # Ensure the final object is in UTC timezone
            dt_object = dt_object.astimezone(timezone.utc)
        elif isinstance(timestamp, datetime):
            # If already a datetime object, ensure it's UTC
            dt_object = timestamp
            if dt_object.tzinfo is None:
                dt_object = dt_object.replace(tzinfo=timezone.utc)
            else:
                dt_object = dt_object.astimezone(timezone.utc)
        else:
            # Handle unexpected types
            raise TypeError(
                f"Unsupported timestamp type: {type(timestamp).__name__}"
            )

        return dt_object

    except (ValueError, TypeError, OverflowError) as e:
        console.print(
            f"Error parsing timestamp '{timestamp}' to UTC: {e}",
            style="warning",
        )
        return None


# FUNC: is_date_passed
def is_date_passed(
    timestamp_input: str | datetime | int | float | None,
) -> bool | None:
    """Checks if the date/time represented by the timestamp is in the past.

    Compares the timestamp (converted to UTC) against the current UTC time.

    Args:
        timestamp_input: The timestamp string, datetime object, epoch seconds, or None.

    Returns:
        True if the timestamp is strictly in the past, False if it's now or in the future.
        Returns None if the timestamp is invalid or None.
    """
    utc_time = convert_timestamp_to_utc(timestamp_input)  # type: ignore[arg-type] # Handled inside
    if utc_time is None:
        return None  # Invalid or None timestamp input

    # Get the current time in UTC
    now_utc = datetime.now(timezone.utc)

    # Perform the comparison
    return utc_time < now_utc


# FUNC: get_local_timezone
def get_local_timezone() -> tzinfo:
    """Safely gets the local timezone object using tzlocal."""
    try:
        # tzlocal() is the function to get the tzinfo object
        local_tz = tzlocal()
        if local_tz is None:  # tzlocal *might* return None in rare cases
            raise ValueError("tzlocal returned None")
        return local_tz
    except Exception as e:
        console.print(
            f"Error getting local timezone: {e}. Falling back to UTC.",
            style="warning",
        )
        return timezone.utc  # Fallback safely to UTC


# FUNC: convert_to_local_time
def convert_to_local_time(
    timestamp_input: str | datetime | int | float | None,
) -> datetime | None:
    """Converts a timestamp (UTC or with offset) to a timezone-aware datetime in the local system timezone.

    Args:
        timestamp_input: The timestamp string (ISO 8601), datetime object, epoch seconds, or None.

    Returns:
        A timezone-aware datetime object in the local timezone, with microseconds
        removed for cleaner display, or None on error or None input.
    """
    utc_time = convert_timestamp_to_utc(timestamp_input)  # type: ignore[arg-type] # Handled inside
    if utc_time is None:
        return None  # Handle invalid input from the start

    try:
        local_timezone = get_local_timezone()
        # Convert the UTC datetime object to the local timezone
        local_time = utc_time.astimezone(local_timezone)
        # Remove microseconds for cleaner display
        return local_time.replace(microsecond=0)
    except Exception as e:  # Catch potential errors during timezone conversion
        local_tz_name = getattr(
            local_timezone, "zone", "Unknown"
        )  # Try to get zone name
        console.print(
            f"Error converting UTC time '{utc_time}' to local zone '{local_tz_name}': {e}",
            style="warning",
        )
        return None


# FUNC: format_timedelta
def format_timedelta(delta: timedelta) -> str:
    """Formats a timedelta into a human-readable string like "in 2d 03:15:30" or "1d 10:05:00 ago".

    Args:
        delta: The timedelta object to format.

    Returns:
        A human-readable string representation of the timedelta.
    """
    total_seconds_float = delta.total_seconds()

    if abs(total_seconds_float) < 1:  # Handle very small durations near zero
        return "now"

    is_past = total_seconds_float < 0
    abs_delta = abs(delta)
    total_abs_seconds = int(abs_delta.total_seconds())

    days = total_abs_seconds // (24 * 3600)
    seconds_within_day = total_abs_seconds % (24 * 3600)

    hours, remainder = divmod(seconds_within_day, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts: list[str] = []
    if days > 0:
        parts.append(f"{days}d")

    # Always show HH:MM:SS for the time part, padding with zeros
    parts.append(f"{hours:02}:{minutes:02}:{seconds:02}")

    time_str = " ".join(parts)

    if is_past:
        return f"{time_str} ago"
    else:
        return f"in {time_str}"


# FUNC: format_datetime_with_diff
def format_datetime_with_diff(
    timestamp_input: str | datetime | int | float | None,
) -> str:
    """Converts a timestamp to local time and returns a formatted string indicating time difference.

    Args:
        timestamp_input: The timestamp string (ISO 8601), datetime object, epoch seconds, or None.

    Returns:
        A string like "YYYY-MM-DD HH:MM:SS (in Xd HH:MM:SS)" or "... ago".
        Returns "Invalid Timestamp" or similar on parsing error.
        Returns "N/A" if input is None.
    """
    if timestamp_input is None:
        return "N/A"

    local_time = convert_to_local_time(timestamp_input)
    if local_time is None:
        # Use repr for better debugging of the original input
        return f"Invalid Timestamp ({repr(timestamp_input)})"

    try:
        # Get current time in the *same* local timezone for accurate comparison
        local_timezone = get_local_timezone()  # Get local tz again
        now_local = datetime.now(local_timezone).replace(microsecond=0)

        # Calculate the difference
        time_difference = local_time - now_local

        # Format the difference and the local time
        formatted_diff = format_timedelta(time_difference)
        # Format local time without microseconds
        local_time_str = local_time.strftime("%Y-%m-%d %H:%M:%S")

        return f"{local_time_str} ({formatted_diff})"
    except Exception as e:
        console.print(
            f"Error formatting local time difference for '{timestamp_input}': {e}",
            style="warning",
        )
        # Fallback if formatting fails but conversion worked
        try:
            return (
                local_time.strftime("%Y-%m-%d %H:%M:%S")
                + " (Error formatting diff)"
            )
        except Exception:
            return f"Invalid Timestamp ({repr(timestamp_input)})"  # Fallback if strftime fails too
