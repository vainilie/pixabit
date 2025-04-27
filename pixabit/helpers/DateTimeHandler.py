# pixabit/helpers/DateTimeHandler.py

# ─── Helper ───────────────────────────────────────────────────────────────────
#          DateTime Handling Utility based on Pydantic
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: IMPORTS
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import dateutil.parser
from dateutil.tz import tzlocal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

# Local Imports (assuming logger is available)
try:
    from ._logger import log
except ImportError:
    import logging

    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())

# SECTION: DateTimeHandler MODEL


# KLASS: DateTimeHandler
class DateTimeHandler(BaseModel):
    """Handles date/time operations with consistent timezone handling and formatting.

    Processes various timestamp inputs (ISO string, Unix seconds/ms, datetime)
    into timezone-aware UTC and local datetime objects.

    Attributes:
        timestamp: The original input timestamp (raw).
        utc_datetime: The timestamp converted to a timezone-aware UTC datetime.
        local_datetime: The timestamp converted to the system's local timezone.
        local_timezone: The detected local timezone.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Raw input
    timestamp: str | datetime | int | float | None = Field(None, description="Original input timestamp.")

    # Processed outputs
    utc_datetime: datetime | None = Field(None, description="Timestamp converted to aware UTC datetime.")
    local_datetime: datetime | None = Field(None, description="Timestamp converted to local timezone.")

    # Configuration
    local_timezone: Any = Field(default_factory=tzlocal, description="System's local timezone.", exclude=True)  # Exclude from dump

    @model_validator(mode="before")
    @classmethod
    def process_timestamps(cls, values: Any) -> dict[str, Any]:
        """Parses the input timestamp into UTC and then converts to local time.
        Handles initialization logic based on the 'timestamp' input.
        """
        if not isinstance(values, dict):
            # Handle direct instantiation like DateTimeHandler(timestamp=...)
            if "timestamp" in values:
                timestamp_input = values["timestamp"]
            else:
                # Or handle if only the value is passed, assume it's the timestamp
                timestamp_input = values
                values = {"timestamp": timestamp_input}  # Structure it as a dict for processing
        else:
            # Handle dict input from model_validate, etc.
            timestamp_input = values.get("timestamp")

        if timestamp_input is None:
            # Allow initialization without timestamp for using class methods like now()
            return values  # Pass through existing values if any

        # --- Parse to UTC ---
        utc_dt: datetime | None = None
        try:
            if isinstance(timestamp_input, (int, float)):
                # Treat as Unix timestamp (auto-detect ms vs s)
                if abs(timestamp_input) > 2e9:  # Likely milliseconds
                    ts_sec = timestamp_input / 1000.0
                else:
                    ts_sec = float(timestamp_input)
                utc_dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc)

            elif isinstance(timestamp_input, str):
                # Try parsing as ISO 8601 string
                parsed_dt = dateutil.parser.isoparse(timestamp_input)
                # Ensure timezone-aware UTC
                if parsed_dt.tzinfo is None:
                    # Assume UTC if timezone is naive (common practice for ISO strings without tz)
                    utc_dt = parsed_dt.replace(tzinfo=timezone.utc)
                else:
                    # Convert explicitly to UTC
                    utc_dt = parsed_dt.astimezone(timezone.utc)

            elif isinstance(timestamp_input, datetime):
                # If already a datetime, ensure it's UTC
                if timestamp_input.tzinfo is None:
                    # Assume UTC if naive
                    utc_dt = timestamp_input.replace(tzinfo=timezone.utc)
                else:
                    utc_dt = timestamp_input.astimezone(timezone.utc)

            else:
                raise TypeError(f"Unsupported timestamp type: {type(timestamp_input).__name__}")

        except (ValueError, TypeError, OverflowError) as e:
            log.warning(f"Could not parse timestamp '{timestamp_input}': {e}. Setting UTC datetime to None.")
            utc_dt = None
            # Raise validation error? Or just log and set None? For now, None.
            # raise ValueError(f"Invalid timestamp format: {timestamp_input}") from e

        values["utc_datetime"] = utc_dt

        # --- Convert UTC to Local ---
        local_tz = values.get("local_timezone", tzlocal())  # Use existing or default
        if utc_dt:
            try:
                values["local_datetime"] = utc_dt.astimezone(local_tz).replace(microsecond=0)
            except Exception as e:
                log.error(f"Could not convert UTC time {utc_dt} to local time zone {local_tz}: {e}")
                values["local_datetime"] = None  # Set None on conversion failure
        else:
            values["local_datetime"] = None  # If UTC is None, local must be None

        # Ensure local_timezone is set in the output dict if not already present
        values["local_timezone"] = local_tz

        return values

    # --- Class Methods for Instantiation ---
    @classmethod
    def from_iso(cls, iso_timestamp: str) -> DateTimeHandler:
        """Creates DateTimeHandler instance from an ISO 8601 timestamp string."""
        return cls(timestamp=iso_timestamp)

    @classmethod
    def from_unix_ms(cls, unix_ms: int) -> DateTimeHandler:
        """Creates DateTimeHandler instance from a Unix timestamp in milliseconds."""
        return cls(timestamp=unix_ms)

    @classmethod
    def from_unix_seconds(cls, unix_seconds: float | int) -> DateTimeHandler:
        """Creates DateTimeHandler instance from a Unix timestamp in seconds."""
        return cls(timestamp=unix_seconds)

    @classmethod
    def now(cls) -> DateTimeHandler:
        """Creates DateTimeHandler instance with the current time."""
        return cls(timestamp=datetime.now(timezone.utc))

    # --- Formatting and Utility Methods ---
    def is_past(self) -> bool | None:
        """Checks if the UTC datetime is in the past. Returns None if datetime is unknown."""
        if self.utc_datetime is None:
            return None
        return self.utc_datetime < datetime.now(timezone.utc)

    def format_time_difference(self) -> str:
        """Formats the time difference between the local datetime and now.

        Returns:
            A human-readable string like "in 5m", "2h ago", "now", or "N/A".
        """
        if self.local_datetime is None:
            return "N/A"

        now_local = datetime.now(self.local_timezone).replace(microsecond=0)
        delta = self.local_datetime - now_local
        return self._format_timedelta(delta)

    def _format_timedelta(self, delta: timedelta) -> str:
        """Formats a timedelta into a human-readable string."""
        total_seconds_float = delta.total_seconds()

        if abs(total_seconds_float) < 1:
            return "now"

        is_past = total_seconds_float < 0
        abs_delta = abs(delta)
        total_abs_seconds = int(abs_delta.total_seconds())

        days, day_seconds = divmod(total_abs_seconds, 86400)  # 24 * 3600
        hours, hour_seconds = divmod(day_seconds, 3600)
        minutes, seconds = divmod(hour_seconds, 60)

        parts = []
        if days > 1:
            parts.append(f"{days}d")
        elif days == 1:
            # If it's between 1 and 2 days, show hours instead for more precision
            total_hours = hours + 24
            parts.append(f"{total_hours}h")
        elif hours > 0:
            parts.append(f"{hours}h")
        elif minutes > 0:
            parts.append(f"{minutes}m")
        elif seconds > 0:
            # Show seconds only if it's the largest unit
            parts.append(f"{seconds}s")

        time_str = "".join(parts)  # Combine directly without spaces

        if is_past:
            return f"{time_str} ago"
        else:
            return f"in {time_str}"

    def format_local(self, format_str: str = "%Y-%m-%d %H:%M") -> str:
        """Formats the local datetime using a specified format string.

        Args:
            format_str: The strftime format string.

        Returns:
            The formatted local time string, or "N/A".
        """
        if self.local_datetime is None:
            return "N/A"
        return self.local_datetime.strftime(format_str)

    def format_utc(self, format_str: str = "%Y-%m-%d %H:%M UTC") -> str:
        """Formats the UTC datetime using a specified format string.

        Args:
            format_str: The strftime format string.

        Returns:
            The formatted UTC time string, or "N/A".
        """
        if self.utc_datetime is None:
            return "N/A"
        return self.utc_datetime.strftime(format_str)

    def format_with_diff(self, format_str: str = "%Y-%m-%d %H:%M") -> str:
        """Formats the local date/time followed by the relative time difference.

        Args:
            format_str: The strftime format string for the date/time part.

        Returns:
            Combined string like "2023-10-27 15:30 (in 5m)", or "N/A".
        """
        local_fmt = self.format_local(format_str)
        if local_fmt == "N/A":
            return "N/A"
        diff = self.format_time_difference()
        return f"{local_fmt} ({diff})"

    # --- Conversion Methods ---
    def to_iso(self) -> str | None:
        """Converts the UTC datetime back to ISO 8601 format string."""
        if self.utc_datetime is None:
            return None
        # Ensure Z for UTC timezone indication
        return self.utc_datetime.isoformat().replace("+00:00", "Z")

    def to_unix_ms(self) -> int | None:
        """Converts the UTC datetime to a Unix timestamp in milliseconds."""
        if self.utc_datetime is None:
            return None
        return int(self.utc_datetime.timestamp() * 1000)

    def to_unix_seconds(self) -> float | None:
        """Converts the UTC datetime to a Unix timestamp in seconds."""
        if self.utc_datetime is None:
            return None
        return self.utc_datetime.timestamp()


# ──────────────────────────────────────────────────────────────────────────────
# Example Usage (Optional)
if __name__ == "__main__":

    # Example Usage
    print("--- Examples ---")

    # From ISO String
    iso_str = "2023-10-26T10:00:00Z"
    dt_handler_iso = DateTimeHandler.from_iso(iso_str)
    print(f"ISO Input : {iso_str}")
    print(f"UTC       : {dt_handler_iso.format_utc('%Y-%m-%d %H:%M:%S %Z%z')}")
    print(f"Local     : {dt_handler_iso.format_local('%Y-%m-%d %H:%M:%S %Z%z')}")
    print(f"Formatted : {dt_handler_iso.format_with_diff('%b %d, %H:%M')}")
    print(f"Is Past?  : {dt_handler_iso.is_past()}")
    print("-" * 10)

    # From Unix Milliseconds (approx now)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    dt_handler_ms = DateTimeHandler.from_unix_ms(now_ms)
    print(f"Unix MS   : {now_ms}")
    print(f"Formatted : {dt_handler_ms.format_with_diff()}")
    print("-" * 10)

    # Future Date (Unix Seconds)
    future_sec = datetime.now(timezone.utc).timestamp() + 3600 * 3  # 3 hours from now
    dt_handler_future = DateTimeHandler.from_unix_seconds(future_sec)
    print(f"Unix Secs : {future_sec:.0f} (future)")
    print(f"Formatted : {dt_handler_future.format_with_diff()}")
    print("-" * 10)

    # From existing datetime object (naive, assumed UTC)
    naive_dt = datetime(2023, 1, 1, 12, 0, 0)
    dt_handler_naive = DateTimeHandler(timestamp=naive_dt)
    print(f"Naive DT  : {naive_dt}")
    print(f"UTC       : {dt_handler_naive.format_utc('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Local     : {dt_handler_naive.format_local('%Y-%m-%d %H:%M:%S %Z')}")
    print("-" * 10)

    # Current time
    dt_handler_now = DateTimeHandler.now()
    print("Now       :")
    print(f"Formatted : {dt_handler_now.format_with_diff()}")
    print(f"ISO       : {dt_handler_now.to_iso()}")
    print(f"Unix MS   : {dt_handler_now.to_unix_ms()}")


# ──────────────────────────────────────────────────────────────────────────────
