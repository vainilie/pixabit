# pixabit/models/user_timing.py
# MARK: - MODULE DOCSTRING
"""Defines data classes related to user timing, preferences, and cron status."""

# MARK: - IMPORTS
from datetime import datetime
from typing import Any, Dict, Optional

# Assuming utils.dates provides robust parsing
from ..utils.dates import convert_timestamp_to_utc


# KLASS: - UserPreferences
class UserPreferences:
    """Represents user-configurable preferences influencing timing and display.

    Attributes:
        sleep: Whether the user is currently sleeping (in the Inn).
        day_start: The user's Custom Day Start hour (0-23).
        timezone_offset: User's timezone offset from UTC in minutes.
        timezone_offset_etc: User's timezone offset string (e.g., "America/New_York") if available.
    """

    # FUNC: - __init__
    def __init__(self, preferences_data: Dict[str, Any]):
        """Initializes UserPreferences from the 'preferences' part of the user object."""
        self.sleep: bool = preferences_data.get("sleep", False)
        self.day_start: int = int(preferences_data.get("dayStart", 0))  # Ensure integer
        self.timezone_offset: Optional[int] = preferences_data.get("timezoneOffset")
        # Habitica might also have timezoneOffsetEtc
        self.timezone_offset_etc: Optional[str] = preferences_data.get("timezoneOffsetEtc")

    # FUNC: - __repr__
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"UserPreferences(sleep={self.sleep}, day_start={self.day_start})"


# KLASS: - UserTimestamps
class UserTimestamps:
    """Represents various timestamps related to user activity.

    Attributes:
        created: When the user account was created (UTC).
        updated: Last time the user object was updated (UTC).
        logged_in: Last login timestamp (UTC).
        last_cron: Last time cron ran successfully for the user (UTC).
    """

    # FUNC: - __init__
    def __init__(self, timestamps_data: Dict[str, Any], user_data: Dict[str, Any]):
        """Initializes UserTimestamps from 'auth.timestamps' and user root."""
        self.created: Optional[datetime] = convert_timestamp_to_utc(timestamps_data.get("created"))
        self.updated: Optional[datetime] = convert_timestamp_to_utc(timestamps_data.get("updated"))
        self.logged_in: Optional[datetime] = convert_timestamp_to_utc(
            timestamps_data.get("loggedin")
        )
        # lastCron is often at the root of the user object, not in timestamps
        self.last_cron: Optional[datetime] = convert_timestamp_to_utc(user_data.get("lastCron"))

    # FUNC: - __repr__
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        login_str = self.logged_in.isoformat() if self.logged_in else "None"
        cron_str = self.last_cron.isoformat() if self.last_cron else "None"
        return f"UserTimestamps(logged_in='{login_str}', last_cron='{cron_str}')"
