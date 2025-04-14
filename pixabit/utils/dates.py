# pixabit/utils/dates.py
# MARK: - MODULE DOCSTRING

"""Provides utility functions for date and time manipulation.

Provides utility functions for date and time manipulation, specifically for
handling timestamps from the Habitica API.
Includes functions for converting timestamps to UTC or local time, and checking
if a timestamp represents a date/time in the past. Requires dateutil and tzlocal.
"""

# MARK: - IMPORTS
from datetime import datetime, timedelta, timezone
from typing import Optional

# Third-party libraries
import dateutil.parser
from tzlocal import get_localzone  # Gets local system timezone

# Use themed console/print if available
try:
    from .display import console, print
except ImportError:  # Fallback
    import builtins

    print = builtins.print

    # Provide a dummy console object to avoid AttributeErrors if console methods are called
    class DummyConsole:
        def print(self, *args, **kwargs):
            builtins.print(*args)

        def log(self, *args, **kwargs):
            builtins.print(*args)

    console = DummyConsole()

# MARK: - FUNCTIONS


# & - def convert_timestamp_to_utc(timestamp: str) -> Optional[datetime]:
def convert_timestamp_to_utc(timestamp: Optional[str]) -> Optional[datetime]:
    """Converts an ISO 8601 timestamp string to a timezone-aware datetime object in UTC.

    Args:
        timestamp: The timestamp string (e.g., "2023-10-27T10:00:00.000Z") or None.

    Returns:
        A timezone-aware datetime object in UTC, or None if parsing fails or input is None.
    """
    if not timestamp:
        return None
    try:
        dt_object = dateutil.parser.isoparse(timestamp)
        # Ensure timezone-aware and converted to UTC
        return dt_object.astimezone(timezone.utc)
    except (ValueError, TypeError) as e:
        console.print(f"Invalid timestamp format '{timestamp}': {e}", style="warning")
        return None


# & - def is_date_passed(timestamp: str) -> Optional[bool]:
def is_date_passed(timestamp: Optional[str]) -> Optional[bool]:
    """Checks if the date/time represented by the timestamp string is in the past.

    Args:
        timestamp: The timestamp string to check, or None.

    Returns:
        True if the timestamp is in the past, False if it's now or in the future.
        Returns None if the timestamp is invalid or None.
    """
    if not timestamp:
        return None
    utc_time = convert_timestamp_to_utc(timestamp)
    if utc_time is None:
        return None  # Invalid timestamp

    now_utc = datetime.now(timezone.utc)
    return utc_time < now_utc


# & - def convert_to_local_time(utc_dt_str: str) -> Optional[datetime]:
def convert_to_local_time(utc_dt_str: Optional[str]) -> Optional[datetime]:
    """Converts a UTC timestamp string to a timezone-aware datetime object in the local system timezone.

    Args:
        utc_dt_str: The timestamp string (assumed UTC or ISO 8601 with tzinfo), or None.

    Returns:
        A timezone-aware datetime object in local timezone, microseconds removed, or None on error/None input.
    """
    if not utc_dt_str:
        return None
    try:
        utc_time = dateutil.parser.isoparse(utc_dt_str)
        if utc_time.tzinfo is None:
            # If naive, assume UTC
            utc_time = utc_time.replace(tzinfo=timezone.utc)

        local_timezone = get_localzone()
        return utc_time.astimezone(local_timezone).replace(microsecond=0)
    except (ValueError, TypeError) as e:
        console.print(
            f"Invalid timestamp format '{utc_dt_str}' for local conversion: {e}",
            style="warning",
        )
        return None


# & - def format_timedelta(delta: timedelta) -> str:
def format_timedelta(delta: timedelta) -> str:
    """Formats a timedelta into a human-readable string (e.g., "in 2d 03:15:30" or "1d 10:05:00 ago")."""
    is_past = delta.total_seconds() < 0
    if is_past:
        delta = -delta  # Work with positive duration
        suffix = "ago"
    else:
        suffix = "in"

    days = delta.days
    total_seconds = delta.seconds
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    # Always show H:M:S for consistency, even if days > 0
    parts.append(f"{hours:02}:{minutes:02}:{seconds:02}")

    if not parts:  # Should not happen with H:M:S always present
        return "now"

    if is_past:
        return f"{' '.join(parts)} {suffix}"
    else:
        return f"{suffix} {' '.join(parts)}"


# & - def convert_and_check_timestamp(timestamp: str) -> Optional[str]:
def convert_and_check_timestamp(timestamp: Optional[str]) -> Optional[str]:
    """Converts timestamp to local time, checks if past/future, returns formatted string.

    Args:
        timestamp: The timestamp to check (ISO 8601 format) or None.

    Returns:
        A string like "YYYY-MM-DD HH:MM:SS (in Xd HH:MM:SS)" or "... ago", or None on error.
    """
    if not timestamp:
        return None
    local_time = convert_to_local_time(timestamp)
    if local_time is None:
        return f"Invalid Timestamp ({timestamp})"  # Return indication of error

    now_local = datetime.now(get_localzone()).replace(microsecond=0)
    time_difference = local_time - now_local
    formatted_diff = format_timedelta(time_difference)
    local_time_str = local_time.strftime("%Y-%m-%d %H:%M:%S")

    return f"{local_time_str} ({formatted_diff})"
