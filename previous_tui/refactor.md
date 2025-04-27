Okay, let's refactor these Habitica TUI models according to your specifications. I'll go through each file, provide explanations for the changes, and then present the refactored code in Markdown format.

**Overall Philosophy:**

- **Pydantic First:** Leverage Pydantic V2 features (`model_config`, `field_validator`, `model_validator`, `computed_field`, context passing) extensively. Models will validate incoming raw data and can generate processed/calculated fields.
- **Encapsulation:** Models should contain logic related to their data (validation, simple calculations, formatting). Complex orchestration belongs elsewhere (like `DataManager`).
- **Clarity & Readability:** Use descriptive names, clear types (Python 3.10+), and adhere to PEP 8 / Zen of Python. Consistent formatting and comments.
- **Immutability (where appropriate):** Use `model_config = ConfigDict(frozen=True)` if a model represents static or immutable data. For dynamic data like User or TaskList, keep it mutable.
- **Helper Integration:** Use your custom `DateTimeHandler`, `log`, `load_json`, `save_json` where applicable.
- **Data Enrichment:** Static data (like `Quest` details) will be looked up when needed but potentially _stored_ within the dynamic model (like `Party.quest_details`) after lookup, rather than constantly re-fetching. Tasks/User stats calculation will happen _after_ loading necessary base and static data.
- **TagFactory:** Preserved as a distinct, more complex way to handle tags, likely alongside the simpler `Tag/TagList`.

---

## File: `pixabit/helpers/DateTimeHandler.py`

**Suggestions:**

1.  **Pydantic V2:** Update to use `model_config` and `FieldValidationInfo`.
2.  **Clarity:** Improve the validator logic slightly for clarity. The `model_validator` approach is cleaner for dependent fields.
3.  **Error Handling:** Ensure ValueError propagation is clear.
4.  **Type Hints:** Standardize typing.

**Refactored Code:**

```python
# pixabit/helpers/DateTimeHandler.py

# ─── Title ────────────────────────────────────────────────────────────────────
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
    FieldValidationInfo,
    ValidationError,
    field_validator,
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
    local_timezone: Any = Field(default_factory=tzlocal, description="System's local timezone.", exclude=True) # Exclude from dump

    @model_validator(mode="before")
    @classmethod
    def process_timestamps(cls, values: Any) -> dict[str, Any]:
        """
        Parses the input timestamp into UTC and then converts to local time.
        Handles initialization logic based on the 'timestamp' input.
        """
        if not isinstance(values, dict):
            # Handle direct instantiation like DateTimeHandler(timestamp=...)
            if "timestamp" in values:
                 timestamp_input = values["timestamp"]
            else:
                # Or handle if only the value is passed, assume it's the timestamp
                 timestamp_input = values
                 values = {"timestamp": timestamp_input} # Structure it as a dict for processing
        else:
            # Handle dict input from model_validate, etc.
            timestamp_input = values.get("timestamp")

        if timestamp_input is None:
            # Allow initialization without timestamp for using class methods like now()
            return values # Pass through existing values if any

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


        values['utc_datetime'] = utc_dt

        # --- Convert UTC to Local ---
        local_tz = values.get('local_timezone', tzlocal()) # Use existing or default
        if utc_dt:
             try:
                 values['local_datetime'] = utc_dt.astimezone(local_tz).replace(microsecond=0)
             except Exception as e:
                 log.error(f"Could not convert UTC time {utc_dt} to local time zone {local_tz}: {e}")
                 values['local_datetime'] = None # Set None on conversion failure
        else:
             values['local_datetime'] = None # If UTC is None, local must be None


        # Ensure local_timezone is set in the output dict if not already present
        values['local_timezone'] = local_tz


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

        days, day_seconds = divmod(total_abs_seconds, 86400) # 24 * 3600
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


        time_str = "".join(parts) # Combine directly without spaces

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
    future_sec = datetime.now(timezone.utc).timestamp() + 3600 * 3 # 3 hours from now
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
```

---

## File: `pixabit/helpers/_json.py`

**Suggestions:**

1.  **Pydantic V2 Integration:** Update `save_pydantic_model` and `load_pydantic_model` to explicitly use V2 methods (`model_dump`, `model_validate`) as Pydantic V1 support is less critical now. Remove the `PYDANTIC_V2` check unless backward compatibility is strictly needed.
2.  **Type Safety:** Use `Type[T_BaseModel]` for model class hints.
3.  **Clarity:** Refine log messages slightly.
4.  **No Changes Needed:** The core `save_json` and `load_json` are already quite solid and use the logger well.

**Refactored Code:**

```python
# pixabit/helpers/_json.py

# ─── Title ────────────────────────────────────────────────────────────────────
#                JSON Save/Load Utilities
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: IMPORTS
import json
from pathlib import Path
from typing import Any, Type, TypeVar, cast  # Use Type for model classes

# Use | for Union is implied by Python 3.10+ target
from pydantic import BaseModel, ValidationError

# Assume logger is available one level up
try:
    from ._logger import log
except ImportError:
    import logging
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())

# SECTION: TYPE VARIABLES
T_BaseModel = TypeVar("T_BaseModel", bound=BaseModel)
JSONSerializable = dict[str, Any] | list[Any] # Consistent typing
LoadResult = JSONSerializable | None

# SECTION: HELPER FUNCTIONS


# FUNC: _resolve_path
def _resolve_path(
    filepath: str | Path, folder: str | Path | None = None
) -> Path:
    """Helper function to resolve the final file path."""
    if folder is not None:
        folder_path = Path(folder).resolve()
        # Extract just the filename from filepath if folder is given
        filename = Path(filepath).name
        return folder_path / filename
    else:
        return Path(filepath).resolve()


# SECTION: CORE FUNCTIONS


# FUNC: save_json
def save_json(
    data: JSONSerializable,
    filepath: str | Path,
    folder: str | Path | None = None,
    indent: int = 4,
    ensure_ascii: bool = False,
) -> bool:
    """Saves Python data (dict or list) to a JSON file with pretty printing.

    Ensures the output directory exists. Handles potential JSON serialization
    errors and file I/O errors, logging messages.

    Args:
        data: The Python dictionary or list to save.
        filepath: The full path (including filename and .json extension) for
                  the output file, or just the filename if folder is specified.
        folder: Optional folder path where the file should be saved.
                If provided, filepath will be treated as just the filename.
        indent: JSON indentation level.
        ensure_ascii: If True, escape non-ASCII characters.

    Returns:
        True if saving was successful, False otherwise.
    """
    output_path = _resolve_path(filepath, folder)
    log.debug(f"Attempting to save JSON data to: '{output_path}'")

    try:
        # Create parent directory(ies) if they don't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file with UTF-8 encoding and specified indentation
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii, default=str) # Added default=str for non-serializable types like datetime if not handled by caller

        log.info(f"Successfully saved JSON data to: '{output_path}'")
        return True

    except TypeError as e:
        log.error(
            f"Data structure not JSON serializable for '{output_path}'. Check for non-standard types (like datetime). Error: {e}"
        )
        return False
    except OSError as e:
        log.error(f"Could not write file '{output_path}'. Error: {e}")
        return False
    except Exception as e:
        log.exception(  # Log full traceback for unexpected errors
            f"An unexpected error occurred saving to '{output_path}': {e}"
        )
        return False


# FUNC: load_json
def load_json(
    filepath: str | Path,
    folder: str | Path | None = None,
) -> LoadResult:
    """Loads data from a JSON file.

    Args:
        filepath: The path to the JSON file, or just the filename if folder is specified.
        folder: Optional folder path where the file is located.
                If provided, filepath will be treated as just the filename.

    Returns:
        The loaded Python dictionary or list, or None if the file doesn't exist,
        cannot be read, or contains invalid JSON.
    """
    input_path = _resolve_path(filepath, folder)

    if not input_path.is_file():
        log.warning(f"JSON file not found at '{input_path}'")
        return None

    log.debug(f"Attempting to load JSON from: '{input_path}'")
    try:
        with input_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Basic validation of loaded data type
        if isinstance(data, (dict, list)):
            log.debug(f"Successfully loaded JSON data from: '{input_path}'")
            return data
        else:
            log.warning(
                f"Invalid data type ({type(data).__name__}) in JSON file: '{input_path}'. Expected dict or list."
            )
            return None

    except (OSError, json.JSONDecodeError) as e:
        log.error(
            f"Failed to load or parse JSON file '{input_path}'. Error: {e}"
        )
        return None
    except Exception as e:
        log.exception(  # Log full traceback for unexpected errors
            f"An unexpected error occurred loading '{input_path}': {e}"
        )
        return None


# SECTION: PYDANTIC INTEGRATION


# FUNC: save_pydantic_model
def save_pydantic_model(
    model: BaseModel,
    filepath: str | Path,
    folder: str | Path | None = None,
    exclude_none: bool = True,
    indent: int = 4,
) -> bool:
    """Saves a Pydantic V2 model to a JSON file using model_dump.

    Args:
        model: The Pydantic model instance to save.
        filepath: The path where the JSON file will be saved, or just the filename
                  if folder is specified.
        folder: Optional folder path where the file should be saved.
        exclude_none: Whether to exclude fields with None values from the output.
        indent: JSON indentation level.

    Returns:
        True if saving was successful, False otherwise.
    """
    if not isinstance(model, BaseModel):
        log.error(
            "Invalid input: 'model' must be a Pydantic BaseModel instance."
        )
        return False

    output_path = _resolve_path(filepath, folder)
    log.debug(f"Attempting to save Pydantic model {type(model).__name__} to JSON: '{output_path}'")

    try:
        # Use model_dump_json for direct JSON string output
        json_str = model.model_dump_json(exclude_none=exclude_none, indent=indent)

        # Create parent directory(ies) if they don't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the JSON string to the file
        with output_path.open("w", encoding="utf-8") as f:
            f.write(json_str)

        log.info(f"Successfully saved Pydantic model to: '{output_path}'")
        return True

    except ValidationError as e: # Should not happen during dump, but belt-and-suspenders
         log.error(f"Pydantic validation error during model dump for '{output_path}'. Error: {e}")
         return False
    except TypeError as e:
        log.error(
            f"Data structure from model dump not JSON serializable for '{output_path}'. Error: {e}"
        )
        return False
    except OSError as e:
        log.error(f"Could not write file '{output_path}'. Error: {e}")
        return False
    except Exception as e:
        log.exception(  # Log full traceback for unexpected errors
            f"An unexpected error occurred saving Pydantic model to '{output_path}': {e}"
        )
        return False


# FUNC: load_pydantic_model
def load_pydantic_model(
    model_class: Type[T_BaseModel],
    filepath: str | Path,
    folder: str | Path | None = None,
    context: dict[str, Any] | None = None, # Added context parameter
) -> T_BaseModel | None:
    """Loads a JSON file into a Pydantic V2 model instance using model_validate.

    Args:
        model_class: The Pydantic model class (e.g., User, Task).
        filepath: The path to the JSON file, or just the filename if folder is specified.
        folder: Optional folder path where the file is located.
        context: Optional dictionary context to pass to `model_validate`.

    Returns:
        An instance of the model_class populated with data if successful, None otherwise.
    """
    data = load_json(filepath, folder=folder)
    if data is None:
        # load_json already logged the reason (not found or parse error)
        return None

    input_path = _resolve_path(filepath, folder)
    if not isinstance(data, dict):
        log.warning(
            f"JSON data loaded from '{input_path}' is not a dictionary, cannot parse into {model_class.__name__}."
        )
        return None

    log.debug(f"Attempting to validate JSON into Pydantic model {model_class.__name__} from '{input_path}'")
    try:
        # Use model_validate for Pydantic V2
        instance = model_class.model_validate(data, context=context) # Pass context here

        log.debug(
            f"Successfully validated JSON into Pydantic model {model_class.__name__}"
        )
        return instance

    except ValidationError as e:
        log.error(
            f"Pydantic validation failed for {model_class.__name__} from '{input_path}':\n{e}"
        )
        return None
    except Exception as e:
        log.exception(
            f"An unexpected error occurred parsing JSON into Pydantic model {model_class.__name__} from '{input_path}': {e}"
        )
        return None


# ──────────────────────────────────────────────────────────────────────────────
```

---

## File: `pixabit/models/tag.py`

**Suggestions:**

1.  **Simplify `TagList`:** Make `TagList` a `BaseModel` containing `list[Tag]` for better integration and validation. Remove manual `to_json`, use `model_dump`/`model_dump_json`.
2.  **Pydantic V2:** Update `Tag` model config.
3.  **Clarity:** Ensure docstrings and comments are clear. Remove `TagManager` stub as it's not fully defined and conflicts with `TagList` purpose here. `TagFactory` is the advanced manager.
4.  **Async Main:** Keep the async main for demonstration/testing.
5.  **Helper Integration:** Use `save_pydantic_model`.

**Refactored Code:**

```python
# pixabit/models/tag.py

# ─── Title ────────────────────────────────────────────────────────────────────
#            Habitica Tag Models (Simple Version)
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Defines basic Pydantic models for representing Habitica Tags."""

# SECTION: IMPORTS
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator # Changed List -> list etc below

import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# Local Imports (assuming helpers and api are accessible)
# Assuming logger, json helper, client, and config are setup
try:
    from pixabit.api.client import HabiticaClient
    from pixabit.config import CACHE_DIR
    from pixabit.helpers._json import load_json, save_pydantic_model
    from pixabit.helpers._logger import log
except ImportError:
    import logging
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    # Provide simple fallbacks if imports fail during refactoring/testing
    CACHE_DIR = Path("./pixabit_cache")
    def save_pydantic_model(model, path, **kwargs): log.warning(f"Skipping save, helper missing: {path}")
    class HabiticaClient: async def get_tags(self): return [] # Mock client
    log.warning("tag.py: Could not import helpers/api/config. Using fallbacks.")

CACHE_SUBDIR = "content"
TAGS_FILENAME = "tags.json"
PROCESSED_TAGS_FILENAME = "processed_tags.json"


# SECTION: TAG MODEL


# KLASS: Tag
class Tag(BaseModel):
    """Represents a single Habitica Tag."""

    model_config = ConfigDict(
        extra="ignore",          # Ignore extra fields from API
        frozen=False,            # Tags might be editable (name, etc.)
        validate_assignment=True,# Re-validate on attribute assignment
    )

    id: str = Field(..., description="Unique tag ID.") # Make ID mandatory
    name: str = Field("", description="Tag name (parsed emoji).") # Default to empty string
    challenge: bool = Field(False, description="True if tag is associated with a challenge.")
    # group: str | None = Field(None, description="Group ID if it's a group tag?") # Check API if needed
    # user: str | None = Field(None, description="User ID of creator?") # Check API if needed

    # Optional internal tracking, not directly from API typically
    position: int | None = Field(None, description="Order/position within the tag list.", exclude=True) # Exclude from dumps


    # --- Validators ---
    @field_validator("name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> str:
        """Parses tag name and replaces emoji shortcodes."""
        if isinstance(value, str):
            parsed = emoji_data_python.replace_colons(value)
            # Optional: Strip leading/trailing whitespace
            return parsed.strip()
        log.debug(f"Received non-string value for tag name: {value!r}. Using empty string.")
        return "" # Return empty string if name is not a string or None

    # --- Methods ---
    def __repr__(self) -> str:
        """Concise representation."""
        chal_flag = " (Challenge)" if self.challenge else ""
        name_preview = self.name.replace("\n", " ") # Avoid newlines in repr
        return f"Tag(id='{self.id}', name='{name_preview}'{chal_flag})"

    def __str__(self) -> str:
        """User-friendly string representation (often just the name)."""
        return self.name

# ──────────────────────────────────────────────────────────────────────────────


# SECTION: TAG LIST MODEL


# KLASS: TagList
class TagList(BaseModel):
    """Container for managing a list of Tag objects, adhering to Pydantic."""

    model_config = ConfigDict(
         extra="forbid", # No extra fields expected on the list itself
         frozen=False,   # Allow adding/removing tags
         arbitrary_types_allowed=False,
    )

    tags: list[Tag] = Field(default_factory=list, description="The list of Tag objects.")

    # Optional: Add validation context if needed later
    # current_user_id: str | None = Field(None, description="Contextual user ID", exclude=True)

    @model_validator(mode='after')
    def update_tag_positions(self) -> TagList:
        """Updates the position attribute for each tag based on its order."""
        for i, tag in enumerate(self.tags):
            tag.position = i # Assign position based on current order
        return self

    # --- Factory Methods ---
    @classmethod
    def from_raw_data(cls, raw_list: list[dict[str, Any]]) -> TagList:
        """Creates a TagList by validating raw dictionary data."""
        if not isinstance(raw_list, list):
            log.error(f"Invalid input for TagList.from_raw_data: Expected list, got {type(raw_list)}.")
            return cls(tags=[]) # Return empty list on error

        validated_tags: list[Tag] = []
        for i, tag_data in enumerate(raw_list):
             if not isinstance(tag_data, dict):
                 log.warning(f"Skipping invalid item at index {i} in raw tag data (expected dict, got {type(tag_data)}).")
                 continue
             try:
                 # Validate each item into a Tag model
                 tag_instance = Tag.model_validate(tag_data)
                 validated_tags.append(tag_instance)
             except ValidationError as e:
                 tag_id = tag_data.get('id', 'N/A')
                 log.error(f"Validation failed for tag data (ID: {tag_id}) at index {i}: {e}")
                 # Optionally skip invalid tags or raise error depending on strictness

        # Instantiate TagList with validated tags (positions are handled by model_validator)
        return cls(tags=validated_tags)


    # --- List-like Methods ---
    def __len__(self) -> int:
        """Return the number of tags."""
        return len(self.tags)

    def __iter__(self) -> Iterator[Tag]:
        """Return an iterator over the tags."""
        return iter(self.tags)

    def __getitem__(self, index: int | slice) -> Tag | list[Tag]:
        """Get tag(s) by index or slice."""
        return self.tags[index]

    def __contains__(self, item: Tag | str) -> bool:
        """Check if a tag (by instance or ID) is in the list."""
        if isinstance(item, str): # Check by ID
            return any(tag.id == item for tag in self.tags)
        elif isinstance(item, Tag): # Check by instance (object equality)
            return item in self.tags
        return False


    # --- Mutating Methods ---
    def add_tag(self, tag: Tag) -> None:
        """Adds a tag to the list if it doesn't exist (by ID). Updates positions."""
        if not isinstance(tag, Tag):
            log.warning(f"Attempted to add invalid type to TagList: {type(tag)}")
            return
        if tag.id not in self:
             self.tags.append(tag)
             self.update_tag_positions() # Recalculate positions after add
        else:
            log.debug(f"Tag with ID '{tag.id}' already exists. Skipping add.")


    def remove_tag(self, tag_id: str) -> bool:
        """Removes a tag by ID and updates positions. Returns True if removed."""
        initial_len = len(self.tags)
        self.tags = [tag for tag in self.tags if tag.id != tag_id]
        removed = len(self.tags) < initial_len
        if removed:
            self.update_tag_positions() # Recalculate positions after remove
        return removed

    def reorder_tags(self, tag_id: str, new_position: int) -> bool:
        """Moves a tag to a new position index and updates all positions."""
        tag_to_move = self.get_by_id(tag_id)
        if not tag_to_move:
            log.warning(f"Cannot reorder: Tag with ID '{tag_id}' not found.")
            return False

        try:
            current_index = self.tags.index(tag_to_move)
            # Ensure position is within bounds (0 to len)
            new_position_clamped = max(0, min(new_position, len(self.tags) - 1))

            # Remove and insert at the new position
            self.tags.pop(current_index)
            self.tags.insert(new_position_clamped, tag_to_move)

            # Update all positions after reordering
            self.update_tag_positions()
            return True
        except ValueError: # Should not happen if get_by_id worked, but safety
             log.error(f"Error finding index for tag ID '{tag_id}' during reorder.")
             return False

    # --- Filtering/Access Methods ---
    def get_by_id(self, tag_id: str) -> Tag | None:
        """Finds a tag by its unique ID."""
        return next((tag for tag in self.tags if tag.id == tag_id), None)

    def get_user_tags(self) -> list[Tag]:
        """Returns only the user-created tags (non-challenge tags)."""
        return [tag for tag in self.tags if not tag.challenge]

    def get_challenge_tags(self) -> list[Tag]:
        """Returns only the challenge-associated tags."""
        return [tag for tag in self.tags if tag.challenge]

    def filter_by_name(self, name_part: str, case_sensitive: bool = False) -> list[Tag]:
         """Filters tags by name containing a substring."""
         if not case_sensitive:
             name_part_lower = name_part.lower()
             return [tag for tag in self.tags if name_part_lower in tag.name.lower()]
         else:
             return [tag for tag in self.tags if name_part in tag.name]

    # --- Serialization ---
    # No custom save_to_json needed, use the helper function
    # No custom model_dump needed, Pydantic handles it

    def save(self, filename: str = PROCESSED_TAGS_FILENAME, folder: str | Path = CACHE_DIR / CACHE_SUBDIR) -> bool:
        """Saves the TagList model to a JSON file using the helper."""
        log.info(f"Saving {len(self.tags)} tags...")
        return save_pydantic_model(self, filename, folder=folder, indent=2)


    # --- Representation ---
    def __repr__(self) -> str:
        """Detailed representation showing counts."""
        user_count = len(self.get_user_tags())
        chal_count = len(self.get_challenge_tags())
        return f"TagList(total={len(self.tags)}, user={user_count}, challenge={chal_count})"

# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MAIN EXECUTION (Example/Test)
async def main():
    """Demo function to retrieve, process, and save tags."""
    log.info("Starting Tag Processing Demo...")
    tag_list_instance: TagList | None = None
    try:
        # Ensure cache directory exists
        cache_path = Path(CACHE_DIR) / CACHE_SUBDIR
        cache_path.mkdir(exist_ok=True, parents=True)
        raw_json_path = cache_path / TAGS_FILENAME
        processed_json_path = cache_path / PROCESSED_TAGS_FILENAME

        # 1. Fetch tags from API
        log.info("Fetching tags from API...")
        api = HabiticaClient() # Assumes client is configured
        raw_tags = await api.get_tags()
        log.success(f"Fetched {len(raw_tags)} tags from API.")

        # Optionally save raw data (using generic save_json)
        # save_json(raw_tags, raw_json_path)
        # log.info(f"Raw tag data saved to {raw_json_path}")

        # 2. Process raw data into TagList model
        log.info("Processing raw data into TagList model...")
        tag_list_instance = TagList.from_raw_data(raw_tags)
        log.success(f"Processed into TagList: {tag_list_instance}")

        # 3. Example: Accessing data
        print(f"  - User tags count: {len(tag_list_instance.get_user_tags())}")
        if tag_list_instance.tags:
             first_tag = tag_list_instance.tags[0]
             print(f"  - First tag: {first_tag}")
             found_tag = tag_list_instance.get_by_id(first_tag.id)
             print(f"  - Found by ID: {found_tag is not None}")


        # 4. Save the processed TagList model
        log.info(f"Saving processed TagList to {processed_json_path}...")
        if tag_list_instance.save(filename=processed_json_path.name, folder=processed_json_path.parent):
            log.success("Processed tags saved successfully.")
        else:
            log.error("Failed to save processed tags.")

    except ValidationError as e:
        log.error(f"Pydantic Validation Error during tag processing: {e}")
    except ConnectionError as e: # Example API error
         log.error(f"API Connection Error: Failed to fetch tags - {e}")
    except Exception as e:
        log.exception(f"An unexpected error occurred in the tag processing demo: {e}") # Log full trace

    log.info("Tag Processing Demo Finished.")
    return tag_list_instance # Return for potential further use

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

# ──────────────────────────────────────────────────────────────────────────────

```

---

## File: `pixabit/models/tag_factory.py`

**Suggestions:**

1.  **Purpose:** Keep this clearly distinct from the simple `tag.py`. This is the "advanced, config-driven" tag management. The `TagList` here _uses_ the `TagFactory`.
2.  **Model Structure:** The `Tag`, `MomTag`, `SubTag` inheritance seems fine. Use Pydantic V2 config.
3.  **Factory Logic:** The factory logic seems okay but ensure robustness (handle missing keys in config, potential errors).
4.  **TagList (Factory Version):** Make this `TagList` use the `TagFactory` for creation. It provides _different_ functionalities than the basic `TagList` (grouping by parent, etc.). Clarify this distinction. Use Pydantic V2. Use `lru_cache`.
5.  **Loading Function:** Refine `load_tags_from_json` error handling.
6.  **Context Manager:** Seems useful for demos/specific loading scenarios, keep it.
7.  **Naming:** Perhaps rename `TagList` in this file to `AdvancedTagList` or `HierarchicalTagList` to avoid confusion with `tag.TagList`, but the user wants `TagFactory` optional, so maybe keeping the name but loading it _conditionally_ is better. Let's stick to `TagList` _within this module_ for now, assuming the _user_ of the library chooses which system (`tag` or `tag_factory`) to use.
8.  **Comments/Style:** Apply consistent styling and comments.

**Refactored Code:**

```python
# pixabit/models/tag_factory.py

# ─── Title ────────────────────────────────────────────────────────────────────
#       Advanced Habitica Tag Models & Factory (Config-Driven)
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""
Defines advanced Pydantic models for representing Habitica Tags with hierarchy
(Parent/Subtag) and a factory (`TagFactory`) to create them based on a TOML
configuration file mapping specific tag IDs/symbols to attributes and types.
Provides an enhanced `TagList` optimized for these hierarchical tags.
"""

# SECTION: IMPORTS
from __future__ import annotations

# --- Python Standard Library Imports ---
import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar, Iterator # Use standard lowercase list etc below

import emoji_data_python
import tomllib # Python 3.11+, use tomli library for < 3.11

# --- Third-Party Library Imports ---
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
    TypeAdapter, # For direct JSON parsing if needed
)

# Local Imports (assuming helpers are available)
try:
    from pixabit.helpers._logger import log
    from pixabit.helpers._json import load_json, save_pydantic_model # Can use these helpers
except ImportError:
    import logging
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    log.warning("tag_factory.py: Could not import helpers. Using fallbacks.")


# SECTION: CONSTANTS

# Maps special symbols (likely found in tag names) to internal attribute short names
ATTRIBUTE_SYMBOL_MAP: dict[str, str] = {
    "💎": "str",  # Example: Diamond for Strength
    "❤️": "con",  # Example: Heart for Constitution
    "💡": "int",  # Example: Lightbulb for Intelligence
    "⭐": "per",  # Example: Star for Perception
    "👑": "legacy", # Example: Crown for Legacy/Special
    # Add symbols relevant to your TUI's visual language if needed
    "⚙️": "challenge", # Example: Gear for challenge-related
}

# Maps configuration *keys* from the TOML file to internal attribute short names
# These MUST match the keys used in your `tags.toml` file
ATTRIBUTE_CONFIG_KEY_MAP: dict[str, str] = {
    "TAG_ID_ATTR_STR": "str",
    "TAG_ID_ATTR_INT": "int",
    "TAG_ID_ATTR_CON": "con",
    "TAG_ID_ATTR_PER": "per",
    "TAG_ID_LEGACY": "legacy",
    "TAG_ID_CHALLENGE": "challenge",
    # Add other specific tag IDs you want to map if needed
}

# Precompile regex for efficiency (matches any *single* symbol from the map)
# Ensures symbols are treated individually if multiple appear in text
ATTRIBUTE_SYMBOL_REGEX = re.compile(
    f"({'|'.join(re.escape(s) for s in ATTRIBUTE_SYMBOL_MAP.keys())})"
)

DEFAULT_ATTRIBUTE = "str" # Default attribute if none detected


# SECTION: BASE MODELS (for TagFactory context)


# KLASS: BaseTag
class BaseTag(BaseModel):
    """Base model for tags created by the TagFactory."""

    model_config = ConfigDict(
        extra="ignore",             # Ignore extra fields from raw data
        frozen=False,               # Allow modification (e.g., position)
        validate_assignment=True,   # Validate on assignment
    )

    id: str = Field(..., description="Unique tag ID.")
    name: str = Field("", description="Tag name (parsed emoji).") # Renamed from text for consistency
    challenge: bool = Field(False, description="Is this a challenge tag?")
    group: str | None = Field(None, description="Associated group ID (if any).") # If API provides it

    # --- Factory-assigned fields ---
    tag_type: Literal["base", "parent", "subtag"] = Field("base", description="Type determined by factory (base, parent, subtag).")
    parent_id: str | None = Field(None, description="ID of the parent tag if this is a subtag.")
    attribute: str | None = Field(None, description="Associated attribute (str, con, etc.) determined by factory.")
    # --- End Factory-assigned ---

    position: int | None = Field(None, description="Calculated position within the list.", exclude=True)

    # --- Validators ---
    @field_validator("name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> str:
        """Parses tag name, replaces emoji shortcodes, strips whitespace."""
        if isinstance(value, str):
            parsed = emoji_data_python.replace_colons(value)
            return parsed.strip()
        log.debug(f"Received non-string for tag name: {value!r}. Using empty string.")
        return ""

    # --- Properties & Methods ---
    @property
    def display_name(self) -> str:
        """Returns the primary name for display."""
        return self.name # Can be overridden in subclasses

    def is_parent(self) -> bool:
        """Checks if this tag is classified as a parent."""
        return self.tag_type == "parent"

    def is_subtag(self) -> bool:
        """Checks if this tag is classified as a subtag."""
        return self.tag_type == "subtag"

    def __repr__(self) -> str:
        """Concise representation."""
        props = f"type={self.tag_type}"
        if self.parent_id: props += f", parent={self.parent_id}"
        if self.attribute: props += f", attr={self.attribute}"
        chal = " (Chal)" if self.challenge else ""
        return f"BaseTag(id='{self.id}', name='{self.name}'{chal}, {props})"

    def __str__(self) -> str:
        """User-friendly representation."""
        return self.display_name


# KLASS: ParentTag
class ParentTag(BaseTag):
    """Represents a parent tag (e.g., an attribute category), determined by TagFactory."""
    tag_type: Literal["parent"] = "parent" # Override default

    @property
    def display_name(self) -> str:
        """Display name for Parent tag (usually just its name)."""
        # Optionally add prefix/suffix like "[ATTR] Name" if needed
        return self.name


# KLASS: SubTag
class SubTag(BaseTag):
    """Represents a subtag associated with a ParentTag, determined by TagFactory."""
    tag_type: Literal["subtag"] = "subtag" # Override default

    @property
    def display_name(self) -> str:
        """Display name for SubTag. Maybe remove prefix symbol if present."""
        # Example: Remove the first symbol if it's mapped
        match = ATTRIBUTE_SYMBOL_REGEX.match(self.name)
        if match and match.group(1) in ATTRIBUTE_SYMBOL_MAP:
             # Return name after the symbol, stripped
             return self.name[len(match.group(1)):].strip()
        return self.name # Return original name otherwise


# Type alias for clarity
AnyTag = ParentTag | SubTag | BaseTag

# ──────────────────────────────────────────────────────────────────────────────


# SECTION: TAG FACTORY


# KLASS: TagFactory
class TagFactory:
    """
    Factory for creating specialized Tag objects (ParentTag, SubTag, BaseTag)
    based on rules defined in a TOML configuration file and detected symbols/IDs.
    """
    def __init__(self, config_path: str | Path):
        """Initialize factory with configuration from a TOML file.

        The TOML file should contain a [tags] section mapping
        configuration keys (like 'TAG_ID_ATTR_STR') to actual Habitica tag IDs.

        Args:
            config_path: Path to the TOML configuration file.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            tomllib.TOMLDecodeError: If the config file is invalid TOML.
            KeyError: If essential keys are missing in the config.
            TypeError: If config values are of unexpected types.
        """
        config_path = Path(config_path)
        if not config_path.is_file():
            raise FileNotFoundError(f"TagFactory config file not found: {config_path}")

        log.debug(f"Loading TagFactory configuration from: {config_path}")
        try:
            with config_path.open("rb") as f:
                config_data = tomllib.load(f)

            # --- Process Config Mappings ---
            toml_tag_ids = config_data.get("tags", {})
            if not isinstance(toml_tag_ids, dict):
                 raise TypeError("Expected '[tags]' section with key-value pairs in TOML config.")

            # 1. id_to_attribute: Maps specific Tag IDs to their attribute (str, con...)
            self.id_to_attribute: dict[str, str] = {}
            for config_key, attribute_name in ATTRIBUTE_CONFIG_KEY_MAP.items():
                tag_id = toml_tag_ids.get(config_key)
                if tag_id and isinstance(tag_id, str):
                    self.id_to_attribute[tag_id] = attribute_name
                else:
                    # Log warning if a mapped key is missing in TOML, might be intentional
                    log.debug(f"Config key '{config_key}' not found or invalid in TOML [tags] section.")

            # 2. attribute_to_parent_id: Maps attribute names back to their *primary* Tag ID (for finding parents)
            self.attribute_to_parent_id: dict[str, str] = {v: k for k, v in self.id_to_attribute.items()}

            # 3. all_configured_ids: Set of all tag IDs mentioned in the config mapping.
            self.all_configured_ids = set(self.id_to_attribute.keys())

            log.info(f"TagFactory initialized. Mapped {len(self.id_to_attribute)} attributes to tag IDs.")
            log.debug(f"Attribute Map: {self.id_to_attribute}")

        except tomllib.TOMLDecodeError as e:
            log.error(f"Error decoding TOML config file '{config_path}': {e}")
            raise
        except (TypeError, KeyError) as e:
            log.error(f"Error processing TagFactory config data from '{config_path}': {e}")
            raise

    def _detect_attribute_from_symbol(self, tag_name: str) -> str | None:
        """Detects attribute based on the *first* recognized symbol in the name."""
        match = ATTRIBUTE_SYMBOL_REGEX.search(tag_name)
        if match:
            symbol = match.group(1)
            return ATTRIBUTE_SYMBOL_MAP.get(symbol)
        return None

    def determine_tag_properties(self, tag_id: str, tag_name: str) -> tuple[Literal["parent", "subtag", "base"], str | None, str | None]:
        """Determines tag type, parent ID, and attribute based on factory rules.

        Returns:
            tuple: (tag_type, parent_id, attribute)
        """
        tag_type: Literal["parent", "subtag", "base"] = "base"
        parent_id: str | None = None
        attribute: str | None = None

        # 1. Check if the ID directly maps to a configured attribute (potential parent)
        if tag_id in self.id_to_attribute:
            tag_type = "parent"
            attribute = self.id_to_attribute[tag_id]
            parent_id = None # Parents don't have parents

        # 2. If not a parent, check for symbols in the name to infer attribute and find parent
        else:
            detected_attribute = self._detect_attribute_from_symbol(tag_name)
            if detected_attribute:
                 # Find the parent ID corresponding to this attribute
                 parent_id = self.attribute_to_parent_id.get(detected_attribute)
                 if parent_id:
                     tag_type = "subtag"
                     attribute = detected_attribute
                 else:
                     # Symbol found, but no configured parent for that attribute
                     log.warning(f"Tag '{tag_name}' (ID:{tag_id}) has symbol for '{detected_attribute}' but no parent tag configured for that attribute.")
                     attribute = detected_attribute # Still assign attribute, but maybe type='base'
                     tag_type = "base" # Or keep 'subtag' without parent? Let's make it base.


        # 3. Assign default attribute if none found so far
        if attribute is None:
            attribute = DEFAULT_ATTRIBUTE

        return tag_type, parent_id, attribute


    def create_tag(self, raw_data: dict[str, Any], position: int | None = None) -> AnyTag:
        """Creates the appropriate Tag (ParentTag, SubTag, BaseTag) from raw data.

        Args:
            raw_data: A dictionary containing raw tag data (must have 'id', should have 'name').
            position: Optional list index for the tag.

        Returns:
            An instance of ParentTag, SubTag, or BaseTag.

        Raises:
            ValidationError: If raw_data fails validation against the base model.
            KeyError: If 'id' is missing in raw_data.
        """
        if 'id' not in raw_data:
             raise KeyError("Tag data must contain an 'id' field.")

        tag_id = raw_data['id']
        # Prioritize 'name', fallback to 'text' if Habitica API uses that sometimes
        tag_name = raw_data.get('name', raw_data.get('text', ''))
        raw_data['name'] = tag_name # Ensure 'name' field exists for validation

        tag_type, parent_id, attribute = self.determine_tag_properties(tag_id, tag_name)

        # Prepare data for model validation
        model_data = {
            **raw_data,
            "tag_type": tag_type,
            "parent_id": parent_id,
            "attribute": attribute,
            "position": position,
        }

        # Validate and instantiate the correct model type
        try:
            if tag_type == "parent":
                return ParentTag.model_validate(model_data)
            elif tag_type == "subtag":
                return SubTag.model_validate(model_data)
            else: # 'base'
                return BaseTag.model_validate(model_data)
        except ValidationError as e:
             log.error(f"Validation failed creating tag ID '{tag_id}' with type '{tag_type}': {e}")
             raise # Re-raise validation error

# ──────────────────────────────────────────────────────────────────────────────


# SECTION: TAG LIST (for TagFactory context)


# KLASS: TagList (Factory-Aware)
class TagList(BaseModel):
    """
    A Pydantic-based list-like collection for managing advanced Tag objects
    (ParentTag, SubTag, BaseTag) created by a TagFactory. Provides methods
    for hierarchical access and manipulation.
    """
    model_config = ConfigDict(
         extra="forbid",
         frozen=False, # List itself can be modified
         arbitrary_types_allowed=True, # Needed because list contains Union[ParentTag, ...]
    )

    # Holds the tags created by the factory
    tags: list[AnyTag] = Field(default_factory=list)
    factory: TagFactory | None = Field(None, exclude=True) # Keep reference if needed

    # --- Model Lifecycle ---
    @model_validator(mode='after')
    def _update_positions(self) -> TagList:
        """Ensure positions are set correctly after validation/modification."""
        for i, tag in enumerate(self.tags):
            # Only update if BaseTag (factory adds position during creation,
            # but this ensures it's updated after potential list manipulation)
            if isinstance(tag, BaseTag):
                 tag.position = i
        return self


    # --- Factory Methods ---
    @classmethod
    def from_raw_data(cls, raw_list: list[dict], factory: TagFactory) -> TagList:
        """Creates TagList from raw API data using the provided TagFactory."""
        if not isinstance(raw_list, list):
            log.error(f"Invalid input for TagList.from_raw_data: Expected list, got {type(raw_list)}.")
            return cls(tags=[], factory=factory)

        processed_tags: list[AnyTag] = []
        for i, item in enumerate(raw_list):
            if not isinstance(item, dict):
                log.warning(f"Skipping invalid item at index {i} in raw tag data (expected dict).")
                continue
            try:
                tag_instance = factory.create_tag(item, position=i)
                processed_tags.append(tag_instance)
            except (ValidationError, KeyError) as e:
                # create_tag logs the specific error
                log.warning(f"Skipping tag at index {i} due to creation error: {e}")
                continue # Skip invalid items

        # Create TagList instance (positions set by model_validator)
        return cls(tags=processed_tags, factory=factory)

    @classmethod
    def from_json_file(cls, json_path: str | Path, factory: TagFactory) -> TagList:
        """Loads TagList directly from a JSON file using the factory."""
        json_path = Path(json_path)
        log.debug(f"Loading tags from JSON file: {json_path}")
        raw_data = load_json(json_path) # Use helper

        if raw_data is None or not isinstance(raw_data, list):
            log.error(f"Failed to load valid tag list data from {json_path}.")
            return cls(tags=[], factory=factory) # Return empty on failure

        return cls.from_raw_data(raw_data, factory)

    # --- Accessors & Filters ---
    @property
    def parents(self) -> list[ParentTag]:
        """Get all ParentTag instances."""
        # Need to filter by instance type
        return [tag for tag in self.tags if isinstance(tag, ParentTag)]

    @property
    def subtags(self) -> list[SubTag]:
        """Get all SubTag instances."""
        return [tag for tag in self.tags if isinstance(tag, SubTag)]

    @property
    def base_tags(self) -> list[BaseTag]:
        """Get all BaseTag instances (not Parent or SubTag)."""
        # Exclude ParentTag and SubTag instances
        return [tag for tag in self.tags if type(tag) is BaseTag]


    def get_subtags_for_parent(self, parent_id: str) -> list[SubTag]:
        """Get all subtags explicitly linked to a specific parent ID."""
        return [
            tag for tag in self.tags
            if isinstance(tag, SubTag) and tag.parent_id == parent_id
        ]

    def get_subtags_for_parent_attribute(self, attribute: str) -> list[SubTag]:
        """Get all subtags associated with a specific attribute (e.g., 'str')."""
        # Find parent ID for attribute first
        if not self.factory: return [] # Factory needed
        parent_id = self.factory.attribute_to_parent_id.get(attribute)
        if not parent_id: return []
        return self.get_subtags_for_parent(parent_id)

    def group_by_parent_id(self) -> dict[str, list[SubTag]]:
        """Groups SubTags by their parent ID."""
        grouped = defaultdict(list)
        for tag in self.subtags: # Iterate only over subtags
            if tag.parent_id:
                grouped[tag.parent_id].append(tag)
        return dict(grouped)

    def group_by_attribute(self) -> dict[str, list[AnyTag]]:
         """Groups all tags by their detected attribute."""
         grouped = defaultdict(list)
         for tag in self.tags:
             if isinstance(tag, BaseTag) and tag.attribute: # Check type and attribute existence
                 grouped[tag.attribute].append(tag)
         return dict(grouped)

    @lru_cache(maxsize=128)
    def get_tag_by_id(self, tag_id: str) -> AnyTag | None:
        """Finds a tag by ID (cached for performance)."""
        # Ensure tag is BaseTag or subclass before checking id
        return next((tag for tag in self.tags if isinstance(tag, BaseTag) and tag.id == tag_id), None)

    def filter_by_challenge(self, is_challenge: bool) -> list[AnyTag]:
        """Filter tags by the 'challenge' flag."""
        return [tag for tag in self.tags if isinstance(tag, BaseTag) and tag.challenge == is_challenge]

    def filter_by_type(self, tag_type: Literal["parent", "subtag", "base"]) -> list[AnyTag]:
        """Filter tags by their factory-determined type."""
        return [tag for tag in self.tags if isinstance(tag, BaseTag) and tag.tag_type == tag_type]

    def sorted_by_position(self) -> list[AnyTag]:
        """Returns tags sorted by their calculated position."""
        # Ensure tags have a position and handle None gracefully
        return sorted(
            [t for t in self.tags if isinstance(t, BaseTag)], # Only sort tags with position
            key=lambda t: t.position if t.position is not None else float('inf')
        )

    # --- List-like Methods ---
    def __len__(self) -> int: return len(self.tags)
    def __iter__(self) -> Iterator[AnyTag]: return iter(self.tags)
    def __getitem__(self, index: int | slice) -> AnyTag | list[AnyTag]: return self.tags[index]
    def __contains__(self, item: AnyTag | str) -> bool:
        if isinstance(item, str):
            return self.get_tag_by_id(item) is not None
        elif isinstance(item, BaseTag):
             return item in self.tags # Instance check
        return False

    # --- Representation ---
    def __repr__(self) -> str:
        """Detailed representation including counts by type."""
        counts = defaultdict(int)
        for tag in self.tags:
             if isinstance(tag, BaseTag): counts[tag.tag_type] += 1
        counts_str = ", ".join(f"{k}={v}" for k,v in counts.items())
        return f"TagList(total={len(self.tags)}, {counts_str})"

    # --- Serialization ---
    def save(self, filename: str, folder: str | Path) -> bool:
        """Saves the TagList model to a JSON file using the helper."""
        log.info(f"Saving {len(self.tags)} factory-processed tags...")
        return save_pydantic_model(self, filename, folder=folder, indent=2)


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: LOADING FUNCTION & CONTEXT MANAGER


# FUNC: load_tags_from_json_with_factory
def load_tags_from_json_with_factory(json_path: str | Path, config_path: str | Path) -> TagList:
    """Loads and processes tags from a JSON file using a TagFactory based on TOML config."""
    log.info(f"Loading tags from '{json_path}' using config '{config_path}'...")
    try:
        factory = TagFactory(config_path=config_path)
        taglist = TagList.from_json_file(json_path, factory)
        log.success(f"Successfully loaded and processed {len(taglist)} tags.")
        return taglist
    except FileNotFoundError as e:
        log.error(f"File not found during tag loading: {e}")
        raise # Re-raise for caller to handle
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, ValidationError, KeyError, TypeError) as e:
        log.error(f"Error loading or processing tags: {e}")
        raise # Re-raise for caller to handle
    except Exception as e:
        log.exception(f"An unexpected error occurred during tag loading: {e}")
        raise

# --- Context Manager Example (optional) ---
# (Your context manager seems fine, keeping it structurally similar)
from contextlib import contextmanager

@contextmanager
def tag_loading_context(json_path: str | Path, config_path: str | Path):
    """Context manager for safely loading tags via factory with error handling."""
    factory: TagFactory | None = None
    taglist: TagList | None = None
    error: Exception | None = None
    try:
        log.info(f"Entering tag loading context for '{json_path}'...")
        factory = TagFactory(config_path=config_path)
        taglist = TagList.from_json_file(json_path, factory)
        yield taglist, factory # Yield the results
    except (FileNotFoundError, json.JSONDecodeError, tomllib.TOMLDecodeError, ValidationError, KeyError, TypeError) as e:
        log.error(f"Error within tag loading context: {e}")
        error = e
        yield None, factory # Yield None on error, factory might be partially init
    except Exception as e:
        log.exception(f"An unexpected error occurred in tag loading context: {e}")
        error = e
        yield None, factory # Yield None on unexpected error
    finally:
        if error:
            log.warning("Tag loading context finished with errors.")
        else:
            log.success("Tag loading context finished successfully.")


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MAIN EXECUTION (Example/Test)
if __name__ == "__main__":
    # Define file paths relative to this script or using absolute paths
    EXAMPLE_TAGS_JSON = Path("./example_tags.json") # Assumes file exists
    EXAMPLE_TAGS_CONFIG = Path("./tags_config.toml") # Assumes file exists
    OUTPUT_PROCESSED_JSON = Path("./processed_factory_tags.json")

    # Create dummy files if they don't exist for testing
    if not EXAMPLE_TAGS_CONFIG.exists():
         print("Creating dummy tags_config.toml...")
         EXAMPLE_TAGS_CONFIG.write_text("""
[tags]
# Map config keys to actual Habitica tag IDs
TAG_ID_ATTR_STR = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx0" # Replace with REAL ID
TAG_ID_ATTR_CON = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx1" # Replace with REAL ID
TAG_ID_ATTR_INT = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx2" # Replace with REAL ID
TAG_ID_ATTR_PER = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx3" # Replace with REAL ID
TAG_ID_LEGACY   = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx4" # Replace with REAL ID
# Add others if needed
         """, encoding="utf-8")

    if not EXAMPLE_TAGS_JSON.exists():
         print("Creating dummy example_tags.json...")
         EXAMPLE_TAGS_JSON.write_text(json.dumps([
             {"id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx0", "name": "Strength", "challenge": False},
             {"id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyy1", "name": "💎 Daily Workout", "challenge": False, "group": None},
             {"id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx1", "name": "Constitution", "challenge": False},
             {"id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyy3", "name": "❤️ Eat Veggies", "challenge": False},
             {"id": "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzz4", "name": "Challenge Tag", "challenge": True, "group":"some_group_id"},
             {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa5", "name": "Uncategorized Tag", "challenge": False},
             {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb6", "name": "👑 Legacy Project", "challenge": False}, # Matches legacy config + symbol
             {"id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx4", "name": "LEGACY Parent", "challenge": False}, # Explicit legacy parent ID
         ], indent=2), encoding="utf-8")


    print("--- Example 1: Loading via Function ---")
    try:
        taglist_func = load_tags_from_json_with_factory(
             json_path=EXAMPLE_TAGS_JSON,
             config_path=EXAMPLE_TAGS_CONFIG
         )
        print(f"Loaded TagList: {taglist_func}")

        print("\n--- Parent Tags ---")
        for parent in taglist_func.parents:
            print(f"- {parent.name} (ID: {parent.id}, Attr: {parent.attribute})")
            subtags = taglist_func.get_subtags_for_parent(parent.id)
            print(f"  Subtags ({len(subtags)}): {[sub.name for sub in subtags[:3]]}...")

        print("\n--- Subtags By Attribute ---")
        con_subtags = taglist_func.get_subtags_for_parent_attribute("con")
        print(f"CON Subtags ({len(con_subtags)}): {[tag.name for tag in con_subtags]}")

        # Save processed data
        if taglist_func.save(filename=OUTPUT_PROCESSED_JSON.name, folder=OUTPUT_PROCESSED_JSON.parent):
            print(f"\nProcessed tags saved to {OUTPUT_PROCESSED_JSON}")
        else:
            print("\nFailed to save processed tags.")


    except Exception as e:
        print(f"\nError loading tags via function: {e}")


    print("\n\n--- Example 2: Loading via Context Manager ---")
    with tag_loading_context(EXAMPLE_TAGS_JSON, EXAMPLE_TAGS_CONFIG) as (taglist_ctx, factory_ctx):
        if taglist_ctx and factory_ctx:
            print(f"Loaded TagList via context: {taglist_ctx}")
            # Example: Find a tag by ID using the cached method
            first_tag_id = taglist_ctx.tags[0].id if taglist_ctx.tags else None
            if first_tag_id:
                found = taglist_ctx.get_tag_by_id(first_tag_id)
                print(f"\nFound first tag by ID ({first_tag_id}): {found.name if found else 'Not Found'}")
                # Call again to test cache (won't print anything but uses cached result)
                taglist_ctx.get_tag_by_id(first_tag_id)
        else:
            print("Failed to load tag data or factory within context manager.")

# ──────────────────────────────────────────────────────────────────────────────
```

---

## File: `pixabit/models/challenge.py`

**Suggestions:**

1.  **Pydantic V2:** Convert to `model_config`, `field_validator`, `model_validator`.
2.  **Required Fields:** Make `id` non-optional on `Challenge` and ensure the validator handles `_id` mapping _before_ base validation. Pydantic will raise the error if 'id' is missing after the validator runs.
3.  **Defaults:** Set sensible defaults (e.g., `""` for text fields, `0` for numeric) in `Field` definitions.
4.  **Consolidate Validators:** Combine emoji parsing for multiple text fields into one validator. Combine datetime parsing. Combine int parsing.
5.  **Task Linking:** The `ChallengeList` should manage linking. The `link_tasks` method looks good. Ensure `TaskList` is used consistently (or a simple `list[Task]`). Using the defined `TaskList` model is better for type safety.
6.  **`ChallengeList` Model:** Make `ChallengeList` a `BaseModel` containing `list[Challenge]`. This allows validation of the list content and using `model_dump`.
7.  **Initialization:** The `ChallengeList.__init__` should primarily focus on validating the input list into `list[Challenge]`. The task linking should happen separately via the `link_tasks` method _after_ both `ChallengeList` and `TaskList` are created.
8.  **Helper Integration:** Use `DateTimeHandler`.
9.  **Error Handling:** Improve logging in `_process_list` (within `ChallengeList`) to show failing item details.

**Refactored Code:**

```python
# pixabit/models/challenge.py

# ─── Title ────────────────────────────────────────────────────────────────────
#            Habitica Challenge Models
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""
Defines Pydantic models for representing Habitica Challenges, their associated
metadata (leader, group), and provides a container (`ChallengeList`) for managing
collections of challenges and linking them to tasks.
"""

# SECTION: IMPORTS
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterator # Use standard lowercase list etc.

# External Libs
import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# Local Imports
try:
    # Assuming Task models are in the same models directory or accessible via __init__
    from .task import Task, TaskList # Use the actual TaskList class/type
    from pixabit.helpers.DateTimeHandler import DateTimeHandler # Use the helper
    from pixabit.helpers._logger import log # Use shared logger
except ImportError:
    # Define fallback types for isolated testing / type checking without full structure
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    log.warning("Using placeholder Task/TaskList/DateTimeHandler in challenge.py.")

    class Task(BaseModel): # Simple placeholder
        id: str | None = None
        challenge: dict | None = None # Match potential raw task data structure
        type: str = "unknown"

    class TaskList: # Simple placeholder
        def __init__(self, tasks: list[Any] | None = None):
            # Store raw task dicts or placeholder Task objects
            self.tasks_data = tasks or []
        def __iter__(self) -> Iterator[Any]: # Yield raw dicts or Tasks
            return iter(self.tasks_data)
        def __len__(self) -> int:
            return len(self.tasks_data)
        def get_tasks_by_challenge_id(self, challenge_id: str) -> list[Any]:
            # Filter raw data based on challenge info within the task data
            return [
                 t for t in self.tasks_data
                 if isinstance(t, dict) and isinstance(t.get("challenge"), dict) and t["challenge"].get("id") == challenge_id
            ]

    class DateTimeHandler: # Simple placeholder
        def __init__(self, timestamp: Any): self._ts = timestamp
        @property
        def utc_datetime(self) -> datetime | None:
             try: return datetime.fromisoformat(str(self._ts).replace("Z", "+00:00")) # Basic parse
             except: return None


# SECTION: PYDANTIC SUB-MODELS


# KLASS: ChallengeLeader
class ChallengeLeader(BaseModel):
    """Represents the leader info potentially nested within challenge data."""

    # Ignore extra fields like 'auth', 'profile' by default
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(..., alias="_id", description="Leader's user ID.") # Require ID
    # Get name directly or from nested profile
    name: str | None = Field(None, description="Leader's display name (parsed).")

    # Validator to extract name from potential nesting BEFORE field validation
    @model_validator(mode="before")
    @classmethod
    def extract_profile_name(cls, data: Any) -> dict[str, Any]:
        if isinstance(data, dict):
            # Check if name is already top-level
            if "name" in data:
                pass # Use existing name
            # If not, check profile
            elif "profile" in data and isinstance(data["profile"], dict):
                data["name"] = data["profile"].get("name") # Extract from profile
            # Handle case where 'name' might only be in 'auth'.'local'.'username'? Less common.
            # elif "auth" in data ... etc.

            # Map _id to id if needed (Pydantic handles alias automatically if _id exists)
            if "_id" in data and "id" not in data: # Ensure Pydantic maps correctly if only _id is present
                 data["id"] = data["_id"] # Help Pydantic if alias logic isn't sufficient alone

        # Always return dict for Pydantic validation
        return data if isinstance(data, dict) else {}


    # Parse name AFTER potentially extracting it
    @field_validator("name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> str | None:
        """Parses name field and replaces emoji shortcodes."""
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value).strip()
        return None # Name can be optional


# KLASS: ChallengeGroup
class ChallengeGroup(BaseModel):
    """Represents the group info nested within challenge data."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(..., alias="_id", description="Group ID.") # Require ID
    name: str = Field("Unnamed Group", description="Group name (parsed).") # Default name
    # Use Literal for known group types if applicable, otherwise str
    type: Literal["party", "guild", "tavern"] | str | None = Field(
        None, description="Group type (party, guild, etc.)."
    )

    @field_validator("name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> str:
        """Parses name field, replaces emoji shortcodes, provides default."""
        if isinstance(value, str):
             parsed = emoji_data_python.replace_colons(value).strip()
             return parsed if parsed else "Unnamed Group" # Ensure non-empty name
        return "Unnamed Group" # Default for non-string input

    @model_validator(mode="before")
    @classmethod
    def map_id(cls, data: Any) -> dict[str, Any]:
         """Ensure ID mapping if needed."""
         if isinstance(data, dict):
             if "_id" in data and "id" not in data:
                 data["id"] = data["_id"]
         return data if isinstance(data, dict) else {}

# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MAIN CHALLENGE MODEL


# KLASS: Challenge
class Challenge(BaseModel):
    """Represents a single Habitica Challenge entity."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    # --- Core Identification & Text ---
    id: str = Field(..., description="Unique challenge ID (mapped from _id if necessary).")
    name: str = Field("Unnamed Challenge", description="Challenge name (parsed emoji).")
    short_name: str | None = Field(
        None, alias="shortName", description="Short name/slug (parsed emoji)."
    )
    summary: str = Field("", description="Summary text (parsed emoji).") # Default to empty string
    description: str = Field("", description="Full description (parsed emoji).") # Default to empty string

    # --- Relationships ---
    # Nested models, validated internally
    leader: ChallengeLeader | None = Field(None, description="Challenge leader details.")
    group: ChallengeGroup | None = Field(None, description="Associated group details (party/guild).")

    # --- Metadata & Status ---
    prize: int = Field(0, description="Gem prize for the winner (if any).")
    member_count: int = Field(0, alias="memberCount", description="Number of participants.")
    official: bool = Field(False, description="Is this an official Habitica challenge?")
    created_at: datetime | None = Field(None, alias="createdAt", description="Timestamp created (UTC).")
    updated_at: datetime | None = Field(None, alias="updatedAt", description="Timestamp updated (UTC).")
    # 'broken' indicates a problem (e.g., 'CHALLENGE_DELETED')
    broken: str | None = Field(None, description="Status if broken, e.g., 'CHALLENGE_DELETED'.")
    # Status flag derived from 'broken' field
    is_broken: bool = Field(False, description="True if the 'broken' field has a value.")

    # --- TUI Context Specific ---
    # Populated externally based on context (e.g., user's participation)
    owned: bool | None = Field(None, description="Is challenge owned by the fetching user? (Set externally)", exclude=True)
    joined: bool | None = Field(None, description="Has the fetching user joined this challenge? (Set externally)", exclude=True)

    # --- Linked Data ---
    # Populated externally by ChallengeList.link_tasks()
    tasks: list[Task] = Field(default_factory=list, description="Tasks belonging to this challenge.", exclude=True)


    # --- Validators ---

    # Map _id to id BEFORE standard validation occurs
    @model_validator(mode="before")
    @classmethod
    def check_and_assign_id(cls, data: Any) -> dict[str, Any]:
        """Map '_id' to 'id' if necessary. Sets 'is_broken' based on 'broken'."""
        if not isinstance(data, dict):
             # If input isn't a dict, let Pydantic handle the type error
             # or return empty dict if we want to try to recover. Empty dict seems safer.
             return {}

        if "_id" in data and "id" not in data:
            data["id"] = data["_id"]

        # Set is_broken derived field
        data["is_broken"] = bool(data.get("broken"))

        # Return modified dict for Pydantic validation
        return data


    # Consolidate emoji parsing for all relevant text fields
    @field_validator("name", "short_name", "summary", "description", mode="before")
    @classmethod
    def parse_text_fields(cls, value: Any, info: FieldValidationInfo) -> str | None:
        """Parses text fields: replaces emoji, strips whitespace. Handles optional fields."""
        if isinstance(value, str):
            parsed = emoji_data_python.replace_colons(value).strip()
            # Handle defaults for required fields if parsing results in empty
            if info.field_name == "name" and not parsed:
                return "Unnamed Challenge" # Ensure name has a default
            if info.field_name in ["summary", "description"] and value is None:
                 return "" # Explicitly return empty string if input is None
            return parsed
        else:
            # Handle non-string input based on field requirements
            if info.field_name == "name": return "Unnamed Challenge"
            if info.field_name in ["summary", "description"]: return ""
            return None # For optional fields like short_name


    # Consolidate datetime parsing using the helper
    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetimes_utc(cls, value: Any) -> datetime | None:
        """Parses timestamp strings/datetimes into timezone-aware UTC datetime objects."""
        handler = DateTimeHandler(timestamp=value)
        # Log warning if parsing failed but return None
        if value is not None and handler.utc_datetime is None:
            log.warning(f"Could not parse timestamp for challenge datetime field: {value!r}")
        return handler.utc_datetime


    # Consolidate integer parsing
    @field_validator("prize", "member_count", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensures numeric fields are integers, defaulting to 0 on error."""
        if value is None: return 0
        try:
            # Handle potential floats coming from API
            return int(float(value))
        except (ValueError, TypeError):
            log.debug(f"Could not parse challenge integer field: {value!r}. Using 0.")
            return 0


    # --- Methods ---
    def add_task(self, task: Task) -> None:
        """Adds a single Task object associated with this challenge."""
        if isinstance(task, Task) and task not in self.tasks:
            self.tasks.append(task)

    def add_tasks(self, tasks_to_add: list[Task]) -> None:
        """Adds multiple Task objects associated with this challenge."""
        if not isinstance(tasks_to_add, list):
             log.warning(f"add_tasks expected a list, got {type(tasks_to_add)}. Skipping.")
             return
        for task in tasks_to_add:
             self.add_task(task) # Reuse single add method


    def get_tasks_by_type(self, task_type: Literal["habit", "daily", "todo", "reward"]) -> list[Task]:
        """Returns linked tasks of a specific type."""
        return [task for task in self.tasks if hasattr(task, 'task_type') and task.task_type == task_type]


    # --- Representation ---
    def __repr__(self) -> str:
        """Concise representation."""
        status = f" (BROKEN: {self.broken})" if self.is_broken else ""
        owner_flag = " (Owned)" if self.owned else ""
        joined_flag = " (Joined)" if self.joined else ""
        official_flag = " (Official)" if self.official else ""
        task_count = len(self.tasks)
        # Ensure name is string before slicing
        name_str = self.name if isinstance(self.name, str) else "Unnamed"
        name_preview = name_str[:30].replace("\n", " ") + ("..." if len(name_str) > 30 else "")
        return f"Challenge(id='{self.id}', name='{name_preview}', tasks={task_count}{status}{owner_flag}{joined_flag}{official_flag})"

    def __str__(self) -> str:
         """User-friendly representation (name)."""
         return self.name if isinstance(self.name, str) else "Unnamed Challenge"


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: CHALLENGE LIST CONTAINER


# KLASS: ChallengeList
class ChallengeList(BaseModel):
    """Pydantic model container for managing Challenge objects and linking tasks."""

    model_config = ConfigDict(
         extra="forbid", # No extra fields allowed on the list itself
         frozen=False,
         arbitrary_types_allowed=False, # Should only contain Challenge objects
    )

    challenges: list[Challenge] = Field(default_factory=list, description="List of Challenge objects.")

    # No __init__ needed, Pydantic handles initialization from list

    # Factory method for easier creation from raw API list
    @classmethod
    def from_raw_data(cls, raw_challenge_list: list[dict[str, Any]]) -> ChallengeList:
         """Processes raw API data, validating into Challenge models."""
         if not isinstance(raw_challenge_list, list):
              log.error(f"ChallengeList input must be a list, got {type(raw_challenge_list)}.")
              return cls(challenges=[]) # Return empty

         validated_challenges: list[Challenge] = []
         for raw_challenge in raw_challenge_list:
              if not isinstance(raw_challenge, dict):
                   log.warning(f"Skipping invalid non-dict entry in challenge list: {raw_challenge}")
                   continue
              try:
                   challenge_instance = Challenge.model_validate(raw_challenge)
                   validated_challenges.append(challenge_instance)
              except ValidationError as e:
                   # Log details about the failing item
                   failed_id = raw_challenge.get("id") or raw_challenge.get("_id", "N/A")
                   failed_name = raw_challenge.get("name", "N/A")
                   log.error(f"Validation failed for challenge (ID: {failed_id}, Name: {failed_name}):\n{e}")
              except Exception as e:
                   failed_id = raw_challenge.get("id") or raw_challenge.get("_id", "N/A")
                   log.error(f"Unexpected error processing challenge data (ID: {failed_id}): {e}", exc_info=True)

         return cls(challenges=validated_challenges)


    # --- Linking Method ---
    def link_tasks(self, task_list_obj: TaskList) -> int:
        """Links Task objects from a TaskList to the corresponding Challenges.

        Assumes `task.challenge.id` holds the link ID on the Task object.

        Args:
            task_list_obj: A TaskList instance containing processed Task objects.

        Returns:
            The number of tasks successfully linked.
        """
        if not isinstance(task_list_obj, TaskList):
            log.warning(f"link_tasks requires a TaskList object, got {type(task_list_obj)}. Skipping linking.")
            return 0
        if not self.challenges:
            log.info("No challenges in the list to link tasks to.")
            return 0

        log.info(f"Linking tasks from TaskList (count={len(task_list_obj)}) to {len(self.challenges)} challenges...")

        # Build lookup dictionary for efficient challenge access by ID
        challenges_by_id: dict[str, Challenge] = {chal.id: chal for chal in self.challenges}

        # Clear existing task links first (important if re-linking)
        for challenge in self.challenges:
            challenge.tasks = []

        linked_count = 0
        skipped_no_link = 0
        skipped_not_found = 0

        # Iterate through tasks provided in the TaskList instance
        for task in task_list_obj: # TaskList should be iterable yielding Task objects
            # Ensure task is a valid Task object with necessary linking info
            if not isinstance(task, Task) or not hasattr(task, 'challenge') or not task.challenge:
                 skipped_no_link += 1
                 continue # Skip tasks without challenge link info

            # Check if challenge link is broken - skip linking broken tasks? Optional.
            # if task.challenge.is_broken:
            #      skipped_broken += 1
            #      continue

            challenge_id_from_task = task.challenge.challenge_id # Access the ID from the nested ChallengeLinkData
            if not challenge_id_from_task:
                 skipped_no_link += 1
                 continue # Skip task if ID is missing in challenge link

            target_challenge = challenges_by_id.get(challenge_id_from_task)

            if target_challenge:
                target_challenge.add_task(task) # Use the method on Challenge
                linked_count += 1
            else:
                # Log if a task points to a challenge not in *this specific* ChallengeList
                # This might happen if the ChallengeList was pre-filtered.
                log.debug(f"Task '{getattr(task, 'id', 'N/A')}' links to challenge '{challenge_id_from_task}', but challenge not found in this ChallengeList.")
                skipped_not_found += 1

        log.success(f"Task linking complete. Linked: {linked_count}, Skipped (No Link Info): {skipped_no_link}, Skipped (Challenge Not Found): {skipped_not_found}.")

        # Optional: Sort tasks within each challenge after linking if needed
        # for challenge in self.challenges: challenge.tasks.sort(...)

        return linked_count

    # --- Access and Filtering Methods ---

    def __len__(self) -> int:
        return len(self.challenges)

    def __iter__(self) -> Iterator[Challenge]:
        return iter(self.challenges)

    def __getitem__(self, index: int | slice) -> Challenge | list[Challenge]:
        if isinstance(index, int):
             if not 0 <= index < len(self.challenges):
                  raise IndexError("Challenge index out of range")
        # Slicing works inherently on the list
        return self.challenges[index]

    def get_by_id(self, challenge_id: str) -> Challenge | None:
        """Finds a challenge by its ID."""
        # Can optimize with the lookup dict if created/stored persistently, but linear scan is fine too
        return next((c for c in self.challenges if c.id == challenge_id), None)

    def filter_by_name(self, name_part: str, case_sensitive: bool = False) -> ChallengeList:
        """Filters challenges by name containing a substring. Returns a new ChallengeList."""
        name_part_toMatch = name_part if case_sensitive else name_part.lower()
        filtered = [
            c for c in self.challenges
            if name_part_toMatch in (c.name if case_sensitive else c.name.lower())
        ]
        return ChallengeList(challenges=filtered) # Return a new list instance


    # Add other filter methods similar to the original, ensuring they return ChallengeList
    def filter_by_leader(self, leader_id: str) -> ChallengeList:
        """Filters challenges by leader's user ID."""
        filtered = [
            c for c in self.challenges if c.leader and c.leader.id == leader_id
        ]
        return ChallengeList(challenges=filtered)

    def filter_by_group(
        self, group_id: str | None = None, group_type: str | None = None
    ) -> ChallengeList:
        """Filters challenges by group ID and/or group type."""
        filtered = self.challenges
        if group_id is not None:
            filtered = [c for c in filtered if c.group and c.group.id == group_id]
        if group_type is not None:
            filtered = [c for c in filtered if c.group and c.group.type == group_type]
        return ChallengeList(challenges=filtered)

    def filter_official(self, official: bool = True) -> ChallengeList:
        """Filters for official or unofficial challenges."""
        filtered = [c for c in self.challenges if c.official is official]
        return ChallengeList(challenges=filtered)

    def filter_broken(self, is_broken: bool = True) -> ChallengeList:
        """Filters challenges based on whether they are broken."""
        # Use the derived is_broken flag
        filtered = [c for c in self.challenges if c.is_broken is is_broken]
        return ChallengeList(challenges=filtered)

    # --- Representation ---
    def __repr__(self) -> str:
        """Simple representation showing the count."""
        return f"ChallengeList(count={len(self.challenges)})"


# ──────────────────────────────────────────────────────────────────────────────

```

---

## File: `pixabit/models/game_content.py`

**Suggestions:**

1.  **Model Naming:** `GameContentCache` isn't accurate, it _manages_ access to content, possibly fetching/caching. Rename to `StaticContentManager`.
2.  **Pydantic Focus:**
    - Make `Quest`, `Spell`, `Gear` fully Pydantic, handling nested structures (`BossModel`, `DropModel`) properly. Use aliases for API field names.
    - `GameContent` should be a `BaseModel` container holding `dict[str, Quest]`, etc.
    - Leverage `model_config` (`populate_by_name`, `extra='ignore'`).
3.  **Data Structure:** Store processed gear/quests/spells in simple dictionaries within `GameContent` (`gear: dict[str, Gear]`). The raw `/content` structure is complex; parse into usable flat structures or structured dicts within `GameContent`.
4.  **Manager Logic:**
    - `StaticContentManager` should orchestrate loading: check processed cache -> check raw cache -> fetch from API.
    - Use `DateTimeHandler` for cache expiry checks.
    - Use `save_pydantic_model`/`load_pydantic_model` (or `save_json`/`load_json` for raw) from helpers.
    - The manager holds the `GameContent` instance (`_content`).
    - `get_X` methods should return the processed dictionaries directly from `self._content`.
5.  **Dependency:** Pass `HabiticaClient` _instance_ to the manager if it needs to fetch data, or let it instantiate its own client specifically for `/content`. Instantiating its own is simpler for static content.
6.  **Error Handling:** Improve error logging during loading and processing.
7.  **Paths:** Use `Path` objects consistently. Use paths from `config.py`.
8.  **Async:** Ensure async usage is correct for API calls and `load_content`.

**Refactored Code:**

```python
# pixabit/models/game_content.py

# ─── Title ────────────────────────────────────────────────────────────────────
#          Habitica Static Game Content Models & Manager
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""
Manages Habitica's static game content (spells, gear, quests, etc.).
Provides Pydantic models for content items and a manager class (`StaticContentManager`)
for fetching, caching (raw and processed), and accessing this data efficiently.
"""

# SECTION: IMPORTS
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Type # Use standard lowercase etc.

# External Libs
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# Local Imports (assuming helpers and api are accessible)
try:
    from pixabit.api.client import HabiticaClient # Needed to fetch content
    from pixabit.config import (
        HABITICA_DATA_PATH, # Main cache dir
        DEFAULT_CACHE_DURATION_DAYS, # Default expiry
    )
    from pixabit.helpers._json import load_json, save_json, load_pydantic_model, save_pydantic_model
    from pixabit.helpers._logger import log
    from pixabit.helpers.DateTimeHandler import DateTimeHandler
except ImportError:
    import logging
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    # Fallbacks for isolated testing
    HABITICA_DATA_PATH = Path("./pixabit_cache")
    DEFAULT_CACHE_DURATION_DAYS = 7
    def load_json(p, **k): return None
    def save_json(d, p, **k): log.warning("Save skipped, helper missing.")
    def load_pydantic_model(m, p, **k): return None
    def save_pydantic_model(m, p, **k): log.warning("Save skipped, helper missing.")
    class HabiticaClient: async def get_content(self): return {"test": True} # Mock
    class DateTimeHandler: pass # Placeholder
    log.warning("game_content.py: Could not import helpers/api/config. Using fallbacks.")


# SECTION: CONSTANTS & CONFIG
CACHE_SUBDIR_STATIC = "static_content"
RAW_CONTENT_FILENAME = "habitica_content_raw.json"
PROCESSED_CONTENT_FILENAME = "habitica_content_processed.json"

# Ensure base path exists
HABITICA_DATA_PATH.mkdir(parents=True, exist_ok=True)
STATIC_CACHE_DIR = HABITICA_DATA_PATH / CACHE_SUBDIR_STATIC
STATIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# SECTION: PYDANTIC MODELS FOR CONTENT ITEMS

# --- Gear Models ---
class GearStats(BaseModel):
    """Nested stats within gear items."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    strength: float = Field(0.0, alias="str")
    intelligence: float = Field(0.0, alias="int")
    constitution: float = Field(0.0, alias="con")
    perception: float = Field(0.0, alias="per")

    @field_validator("strength", "intelligence", "constitution", "perception", mode="before")
    @classmethod
    def ensure_float(cls, v: Any) -> float:
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

class GearEvent(BaseModel):
     """Nested event info within gear items."""
     model_config = ConfigDict(extra="ignore")
     start_date: datetime | None = Field(None, alias="startDate")
     end_date: datetime | None = Field(None, alias="endDate")
     # season: str | None = None # Season can also be top-level

     @field_validator("start_date", "end_date", mode="before")
     @classmethod
     def parse_datetime_utc(cls, v: Any) -> datetime | None:
         handler = DateTimeHandler(timestamp=v)
         return handler.utc_datetime

# KLASS: Gear
class Gear(BaseModel):
    """Habitica gear model (parsed from content.gear.flat)."""
    model_config = ConfigDict(
        extra="ignore",          # Ignore unused fields like 'purchase', 'canDrop', etc.
        populate_by_name=True,   # Use aliases for API fields
        frozen=True,             # Gear definitions are static
    )

    key: str = Field(..., description="Unique identifier key (e.g., 'weapon_warrior_1').")
    text: str = Field(..., description="Display name of the gear.")
    notes: str = Field("", description="Description or flavor text.")
    value: float = Field(0, description="Purchase price in Gold (sometimes Gems for special).") # Often int, use float for safety
    type: Literal["weapon", "armor", "head", "shield", "back", "body", "eyewear", "headAccessory"] | None = Field(None, description="Slot type.")
    klass: str | None = Field(None, description="Class required to get bonus ('warrior', 'rogue', etc.), or 'special'.") # 'base'? -> Should check API content
    two_handed: bool = Field(False, alias="twoHanded", description="Whether the weapon is two-handed.")
    gear_set: str | None = Field(None, alias="set", description="Gear set key ('base', 'golden', 'seasonal', etc.).") # Changed from sett -> set to avoid python keyword conflict

    # Nested stats model
    stats: GearStats = Field(default_factory=GearStats)

    # Event info (if applicable)
    event: GearEvent | None = None
    # Season directly on item (sometimes overrides event.season?)
    season: str | None = None

    # Index/Order within set? Seems less useful.
    # index: str | None = None

    @field_validator("text", "notes", mode="before")
    @classmethod
    def parse_text_emoji(cls, v: Any) -> str:
        if isinstance(v, str):
             return emoji_data_python.replace_colons(v).strip()
        return ""

    @field_validator("value", mode="before")
    @classmethod
    def parse_value(cls, v: Any) -> float:
         # Sometimes value is gold, sometimes gems - often represented * 4 for gold value
         # Treat as float for flexibility. Raw might be integer gold amount.
        try:
             return float(v)
        except (ValueError, TypeError):
             return 0.0

# --- Spell Models ---
# KLASS: Spell
class Spell(BaseModel):
    """Habitica spell/skill model."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)

    key: str = Field(..., description="Unique skill key (e.g., 'fireball').")
    text: str = Field(..., description="Display name of the skill.")
    notes: str = Field("", description="In-game description/notes.")
    mana: float = Field(0.0, description="Mana cost.")
    target: Literal["self", "user", "party", "task", "certainUsers"] | str | None = Field(
        None, description="Target type (e.g., 'self', 'user', 'party', 'task')."
    )
    klass: Literal["wizard", "healer", "warrior", "rogue", "special"] | None = Field(
        None, description="Associated class or 'special'."
    )
    lvl: int = Field(1, description="Level required to learn/use.")

    # Optional API fields
    immediate_use: bool = Field(False, alias="immediateUse")
    purchase_type: str | None = Field(None, alias="purchaseType") # Typically null for class skills
    value: int | None = Field(0) # Gold value if purchasable (usually 0 for skills)

    @field_validator("text", "notes", mode="before")
    @classmethod
    def parse_text_emoji(cls, v: Any) -> str:
        if isinstance(v, str):
             return emoji_data_python.replace_colons(v).strip()
        return ""

    @field_validator("mana", mode="before")
    @classmethod
    def ensure_float(cls, v: Any) -> float:
        try:
            return float(v)
        except (ValueError, TypeError): return 0.0

    @field_validator("lvl", "value", mode="before")
    @classmethod
    def ensure_int(cls, v: Any) -> int:
        if v is None: return 0
        try:
            return int(v)
        except (ValueError, TypeError): return 0


# --- Quest Models ---
class QuestBoss(BaseModel):
    """Model for boss properties within a quest."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)
    name: str = Field(..., description="Boss display name.")
    hp: float = Field(0.0, description="Initial HP of the boss.")
    strength: float = Field(0.0, alias="str", description="Boss strength (influences damage to party).")
    defense: float = Field(0.0, alias="def", description="Boss defense (influences damage dealt).")
    # rage: float? # Maybe add if needed

    @field_validator("hp", "strength", "defense", mode="before")
    @classmethod
    def ensure_float(cls, v: Any) -> float:
        try:
            return float(v)
        except (ValueError, TypeError): return 0.0


class QuestDropItem(BaseModel):
    """Individual item details within quest drops."""
    model_config = ConfigDict(extra="ignore", frozen=True)
    type: str = Field(...) # e.g., "Food", "Eggs", "HatchingPotions"
    key: str = Field(...) # Item key


class QuestDrop(BaseModel):
    """Model for drop properties within a quest."""
    model_config = ConfigDict(extra="ignore", frozen=True)
    exp: int = Field(0, description="Experience points awarded.")
    gp: float = Field(0.0, description="Gold awarded.") # Can be float? Let's assume so.
    # Can be a list of Item dicts or a dict mapping Item Type -> List of Item Keys
    # We'll simplify to a list of specific item drops for now
    items: list[QuestDropItem] = Field(default_factory=list)

    @field_validator("exp", mode="before")
    @classmethod
    def ensure_int(cls, v: Any) -> int:
        try: return int(v)
        except (ValueError, TypeError): return 0

    @field_validator("gp", mode="before")
    @classmethod
    def ensure_float(cls, v: Any) -> float:
        try: return float(v)
        except (ValueError, TypeError): return 0.0

    @model_validator(mode="before")
    @classmethod
    def structure_drop_items(cls, data: Any) -> dict[str, Any]:
        """Standardizes the 'items' field into a list of QuestDropItem."""
        if not isinstance(data, dict): return data if isinstance(data, dict) else {}

        items_data = data.get("items", {}) # API response might have items directly
        if isinstance(items_data, dict):
             standardized_items = []
             for item_type, keys in items_data.items():
                 if isinstance(keys, list):
                     for item_key in keys:
                          if isinstance(item_key, str):
                               standardized_items.append(QuestDropItem(type=item_type, key=item_key))
             data['items'] = standardized_items
        elif isinstance(items_data, list):
             # Assume list is already in {type:..., key:...} format? Adapt if needed.
             # For now, let validation handle it, or parse explicitly here if structure is known.
             pass # Let Pydantic try parsing list of dicts into list[QuestDropItem]
        else:
            data['items'] = [] # Ensure items is a list

        return data

class QuestCollect(BaseModel):
     """Model for item collection goals within a quest."""
     model_config = ConfigDict(extra="allow", frozen=True) # Allow any item keys
     # Stores {item_key: count_needed}
     # Pydantic will populate this dict directly from the API response.
     # Example: {"petal": 10, "shiny_seed": 5}

class QuestUnlockCondition(BaseModel):
    """Model for quest unlock condition."""
    model_config = ConfigDict(extra="ignore", frozen=True)
    condition: str | None = None # Textual description or key? API seems inconsistent
    text: str | None = None # Unlock message

# KLASS: Quest
class Quest(BaseModel):
    """Habitica quest model (parsed from content.quests)."""
    model_config = ConfigDict(
        extra="ignore",          # Ignore other fields like wiki link, previous quest etc.
        populate_by_name=True,
        frozen=True,             # Quest definitions are static
    )

    key: str = Field(..., description="Unique quest key (e.g., 'atom1').")
    text: str = Field(..., description="Quest title/name.")
    notes: str = Field("", description="Quest description.")
    completion_msg: str = Field("", alias="completion", description="Message shown on completion.")
    category: str | None = Field(None, description="Quest category (e.g., 'boss', 'collect', 'pet').")

    # Nested models
    boss: QuestBoss | None = None
    collect: QuestCollect | None = None # Holds item keys and counts needed
    drop: QuestDrop = Field(default_factory=QuestDrop)

    # Other important flags/info
    is_boss_quest: bool = Field(False, description="Derived: True if quest has boss data.")
    is_collect_quest: bool = Field(False, description="Derived: True if quest has collection data.")

    # Gold cost to buy quest scroll
    value: int = Field(0, description="Scroll cost in Gold (Gems*4?)") # Seems to be Gold
    # Level required to start? Seems absent in static content, maybe implied by category/key?
    # lvl: int | None = Field(None, description="Minimum level required?")

    # Group quest can be started in
    # group: dict? # Seems complex, ignoring for now

    # Unlock conditions / Prerequisites (simplified)
    unlock_condition: str | None = Field(None, alias="unlockCondition", description="Text explaining how to unlock.")
    # prereqQuests: list[str] = [] # List of previous quest keys needed

    # --- Validators ---
    @field_validator("text", "notes", "completion_msg", mode="before")
    @classmethod
    def parse_text_emoji(cls, v: Any) -> str:
        if isinstance(v, str):
             return emoji_data_python.replace_colons(v).strip()
        return ""

    @field_validator("value", mode="before")
    @classmethod
    def ensure_int(cls, v: Any) -> int:
        try: return int(v)
        except (ValueError, TypeError): return 0

    @field_validator("unlock_condition", mode="before")
    @classmethod
    def parse_unlock(cls, v: Any) -> str | None:
         """Handles unlockCondition being object or string."""
         if isinstance(v, dict):
              return v.get("text") # Prefer text if object
         elif isinstance(v, str):
              return v
         return None

    @model_validator(mode="after")
    def set_derived_quest_types(self) -> Quest:
        """Sets boolean flags based on presence of boss/collect data."""
        self.is_boss_quest = self.boss is not None and (self.boss.hp > 0 or self.boss.strength > 0)
        # Collect dict is non-empty if there are collection items
        self.is_collect_quest = self.collect is not None and bool(self.collect.model_dump())
        return self


# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MAIN CONTENT CONTAINER MODEL

# KLASS: GameContent
class GameContent(BaseModel):
    """Container for processed static game content."""
    model_config = ConfigDict(frozen=True) # Content is static once loaded

    gear: dict[str, Gear] = Field(default_factory=dict)
    quests: dict[str, Quest] = Field(default_factory=dict)
    spells: dict[str, Spell] = Field(default_factory=dict) # Store all spells flat for easy lookup
    # Add other categories if needed (e.g., pets, mounts, backgrounds)
    # pets: dict[str, PetInfo] = Field(default_factory=dict)
    # mounts: dict[str, MountInfo] = Field(default_factory=dict)

    last_fetched_at: datetime | None = Field(None, description="Timestamp when the raw content was last fetched.")
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when this processed model was created.")


    @classmethod
    def from_raw_content(cls, raw_content: dict[str, Any], fetched_at: datetime) -> GameContent:
        """Parses the raw '/content' API response into structured models."""
        processed_gear: dict[str, Gear] = {}
        processed_quests: dict[str, Quest] = {}
        processed_spells: dict[str, Spell] = {}

        # --- Process Gear (from gear.flat) ---
        raw_gear_flat = raw_content.get("gear", {}).get("flat", {})
        if isinstance(raw_gear_flat, dict):
            for key, data in raw_gear_flat.items():
                if not isinstance(data, dict): continue
                try:
                    # Inject key into data dict for validation
                    data['key'] = key
                    processed_gear[key] = Gear.model_validate(data)
                except ValidationError as e:
                    log.warning(f"Validation failed for gear '{key}': {e}")
                except Exception as e:
                     log.exception(f"Unexpected error processing gear '{key}': {e}")


        # --- Process Quests ---
        raw_quests = raw_content.get("quests", {})
        if isinstance(raw_quests, dict):
            for key, data in raw_quests.items():
                if not isinstance(data, dict): continue
                try:
                    data['key'] = key # Ensure key is present
                    processed_quests[key] = Quest.model_validate(data)
                except ValidationError as e:
                    log.warning(f"Validation failed for quest '{key}': {e}")
                except Exception as e:
                     log.exception(f"Unexpected error processing quest '{key}': {e}")

        # --- Process Spells (flatten all classes into one dict) ---
        raw_spells = raw_content.get("spells", {})
        if isinstance(raw_spells, dict):
            for spell_class, spells_in_class in raw_spells.items():
                 if isinstance(spells_in_class, dict):
                     for key, data in spells_in_class.items():
                          if not isinstance(data, dict): continue
                          try:
                              data['key'] = key # Ensure key is present
                              data['klass'] = spell_class # Inject class
                              processed_spells[key] = Spell.model_validate(data)
                          except ValidationError as e:
                              log.warning(f"Validation failed for spell '{key}' (class: {spell_class}): {e}")
                          except Exception as e:
                              log.exception(f"Unexpected error processing spell '{key}': {e}")


        log.info(f"Processed static content: {len(processed_gear)} gear items, {len(processed_quests)} quests, {len(processed_spells)} spells.")

        return cls(
            gear=processed_gear,
            quests=processed_quests,
            spells=processed_spells,
            last_fetched_at=fetched_at
        )


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: STATIC CONTENT MANAGER


# KLASS: StaticContentManager
class StaticContentManager:
    """Manages fetching, caching, and access to Habitica's static game content."""

    def __init__(
        self,
        cache_dir: Path = STATIC_CACHE_DIR,
        raw_filename: str = RAW_CONTENT_FILENAME,
        processed_filename: str = PROCESSED_CONTENT_FILENAME,
        cache_duration_days: int = DEFAULT_CACHE_DURATION_DAYS,
        api_client: HabiticaClient | None = None, # Optional: provide existing client
    ):
        """Initialize the content manager.

        Args:
            cache_dir: Directory for storing cached files.
            raw_filename: Filename for the raw API response cache.
            processed_filename: Filename for the processed GameContent model cache.
            cache_duration_days: How long processed cache is considered fresh.
            api_client: Optional HabiticaClient instance to use for fetching.
                        If None, a new instance will be created internally.
        """
        self.cache_dir = cache_dir
        self.raw_cache_path = cache_dir / raw_filename
        self.processed_cache_path = cache_dir / processed_filename
        self.cache_duration = timedelta(days=cache_duration_days)
        self.api_client = api_client or HabiticaClient() # Create client if not provided

        self._content: GameContent | None = None # In-memory cache
        self._lock = asyncio.Lock() # Prevent race conditions during load

        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _is_cache_fresh(self, cache_model: GameContent) -> bool:
        """Check if the processed cache file is still fresh."""
        if not cache_model or not cache_model.processed_at:
             return False
        # Ensure processed_at is timezone-aware for comparison
        processed_at_aware = cache_model.processed_at
        if processed_at_aware.tzinfo is None:
             processed_at_aware = processed_at_aware.replace(tzinfo=timezone.utc)

        return (datetime.now(timezone.utc) - processed_at_aware) < self.cache_duration

    async def load_content(self, force_refresh: bool = False) -> GameContent | None:
        """Loads game content, using cache or fetching from API as needed.

        Handles locking to prevent simultaneous loads.

        Args:
            force_refresh: If True, bypass all caches and fetch directly from API.

        Returns:
            The processed GameContent model, or None if loading fails.
        """
        async with self._lock: # Acquire lock before proceeding
            # 1. Check in-memory cache first (unless forcing refresh)
            if self._content and not force_refresh:
                # Optional: Re-check freshness even for in-memory? Only needed if long-running process
                # if self._is_cache_fresh(self._content): # Can add this check if desired
                log.debug("Using in-memory static content cache.")
                return self._content

            # 2. Try loading from processed Pydantic model cache (if not forcing refresh)
            if not force_refresh and self.processed_cache_path.exists():
                 log.debug(f"Attempting to load processed content from: {self.processed_cache_path}")
                 cached_model = load_pydantic_model(GameContent, self.processed_cache_path)
                 if cached_model and self._is_cache_fresh(cached_model):
                     log.info("Using fresh processed static content cache.")
                     self._content = cached_model
                     return self._content
                 elif cached_model:
                     log.info("Processed static content cache is stale.")
                 else:
                      log.warning("Failed to load processed static content cache.")

            # 3. Try loading from raw JSON cache (parse if available)
            raw_content_data = None
            raw_fetch_time = None
            if self.raw_cache_path.exists():
                log.debug(f"Attempting to load raw content from: {self.raw_cache_path}")
                raw_content_data = load_json(self.raw_cache_path)
                if raw_content_data:
                     # Try to get modification time as fallback fetch time
                     try:
                         mtime = self.raw_cache_path.stat().st_mtime
                         raw_fetch_time = datetime.fromtimestamp(mtime, timezone.utc)
                         log.info(f"Using raw static content cache (fetched around {raw_fetch_time}). Processing...")
                     except Exception:
                         raw_fetch_time = datetime.now(timezone.utc) # Fallback
                         log.info("Using raw static content cache (fetch time unknown). Processing...")

                     # Process the raw data loaded from cache
                     try:
                          self._content = GameContent.from_raw_content(raw_content_data, raw_fetch_time)
                          # Save the newly processed data back to processed cache
                          self.save_processed_content()
                          return self._content
                     except Exception as e:
                          log.exception(f"Error processing raw content from cache: {e}")
                          self._content = None # Ensure content is cleared on error
                else:
                      log.warning("Failed to load raw static content cache file.")


            # 4. Fetch from API as last resort (or if force_refresh is True)
            log.info(f"{'Forcing refresh' if force_refresh else 'Fetching new'} static content from Habitica API...")
            try:
                 current_time = datetime.now(timezone.utc)
                 fetched_data = await self.api_client.get_content()
                 log.success("Successfully fetched raw content from API.")

                 # Save the newly fetched raw data
                 save_json(fetched_data, self.raw_cache_path)

                 # Process the fetched data
                 self._content = GameContent.from_raw_content(fetched_data, current_time)

                 # Save the newly processed data
                 self.save_processed_content()
                 return self._content

            except Exception as e:
                 log.exception(f"Failed to fetch or process static content from API: {e}")
                 # If fetch fails, try to return potentially stale in-memory cache if it exists
                 if self._content:
                      log.warning("API fetch failed. Returning potentially stale in-memory content.")
                      return self._content
                 else:
                      # If absolutely no content could be loaded/fetched
                      log.error("Could not load static content from any source.")
                      return None # Indicate failure

    def save_processed_content(self) -> None:
        """Saves the current in-memory _content model to the processed cache file."""
        if not self._content:
            log.warning("No processed content available in memory to save.")
            return

        if save_pydantic_model(self._content, self.processed_cache_path):
            log.info(f"Saved processed static content to {self.processed_cache_path}")
        else:
            log.error(f"Failed to save processed static content to {self.processed_cache_path}")

    async def refresh_from_api(self) -> GameContent | None:
        """Convenience method to force a refresh from the API."""
        return await self.load_content(force_refresh=True)

    # --- Accessor Methods ---
    # These methods ensure content is loaded before returning data
    # They return the specific dictionaries directly.

    async def get_gear(self) -> dict[str, Gear]:
        """Returns the dictionary of all processed gear items."""
        content = await self.load_content()
        return content.gear if content else {}

    async def get_gear_item(self, key: str) -> Gear | None:
         """Gets a specific gear item by key."""
         gear_dict = await self.get_gear()
         return gear_dict.get(key)

    async def get_quests(self) -> dict[str, Quest]:
        """Returns the dictionary of all processed quest items."""
        content = await self.load_content()
        return content.quests if content else {}

    async def get_quest(self, key: str) -> Quest | None:
         """Gets a specific quest by key."""
         quest_dict = await self.get_quests()
         return quest_dict.get(key)

    async def get_spells(self) -> dict[str, Spell]:
        """Returns the dictionary of all processed spell items."""
        content = await self.load_content()
        return content.spells if content else {}

    async def get_spell(self, key: str) -> Spell | None:
         """Gets a specific spell by key."""
         spell_dict = await self.get_spells()
         return spell_dict.get(key)

# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MAIN EXECUTION (Example/Test)
import asyncio # Needed for running async main

async def main():
    """Demo function to initialize and use the StaticContentManager."""
    log.info("--- Static Content Manager Demo ---")

    # Initialize manager (will create client internally)
    content_manager = StaticContentManager(cache_dir=STATIC_CACHE_DIR)

    try:
        # --- Load Content (uses cache or fetches) ---
        log.info("Loading content (initial load)...")
        content_loaded = await content_manager.load_content()

        if not content_loaded:
             log.error("Failed to load initial content. Exiting demo.")
             return

        log.success("Initial content loaded.")
        print(f"  Gear items: {len(content_loaded.gear)}")
        print(f"  Quests: {len(content_loaded.quests)}")
        print(f"  Spells: {len(content_loaded.spells)}")

        # --- Access specific data types ---
        log.info("Accessing specific data...")
        all_gear = await content_manager.get_gear()
        all_quests = await content_manager.get_quests()
        # print(f"  Fetched all gear again: {len(all_gear)} items")

        # Example: Get a specific item
        test_gear_key = "weapon_warrior_1" # Change if needed
        gear_item = await content_manager.get_gear_item(test_gear_key)
        if gear_item:
            print(f"  Found Gear '{test_gear_key}': {gear_item.text} (STR: {gear_item.stats.strength})")
        else:
            print(f"  Gear '{test_gear_key}' not found.")

        test_quest_key = "atom1" # Change if needed
        quest_item = await content_manager.get_quest(test_quest_key)
        if quest_item:
            print(f"  Found Quest '{test_quest_key}': {quest_item.text} (Category: {quest_item.category})")
            if quest_item.is_boss_quest:
                 print(f"    Boss Quest: Name={quest_item.boss.name}, HP={quest_item.boss.hp}")
        else:
            print(f"  Quest '{test_quest_key}' not found.")

        # --- Force Refresh ---
        # log.info("Forcing content refresh from API...")
        # await content_manager.refresh_from_api()
        # log.success("Content refreshed.")

    except Exception as e:
        log.exception(f"An error occurred during the content manager demo: {e}")


if __name__ == "__main__":
    # Basic logging config if running standalone
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(main())

# ──────────────────────────────────────────────────────────────────────────────

```

---

## File: `pixabit/models/message.py`

**Suggestions:**

1.  **Pydantic V2:** Convert models. Use `ValidationInfo` to get context (`current_user_id`) in `MessageList` validator.
2.  **`MessageList` as `BaseModel`:** Make `MessageList` a `BaseModel` itself. This improves consistency and allows validation of the incoming list directly.
3.  **Context-Dependent Fields:** Calculate `sent_by_me` and `conversation_id` within a `model_validator(mode="before")` on `MessageList`. This validator will receive the _raw_ list of message dicts and the context. It will validate each message dict into a `Message` object, calculate the derived fields, sort them, and return the final `list[Message]` wrapped in a dictionary like `{"messages": processed_list}` for Pydantic to assign to the `messages` field.
4.  **Robust Timestamp Parsing:** Enhance `parse_timestamp_robust` in `Message` to be more resilient, potentially using the `DateTimeHandler` helper.
5.  **Emoji Parsing:** Consolidate emoji parsing in `Message`.
6.  **`determine_conversation_id`:** Refine this logic based on the `Message` model's fields (sender_id, recipient_id, group_id, sent_by_me) and the `current_user_id` from context.
7.  **`Config`:** Import `USER_ID` from `config` instead of hardcoding it. Pass it via context during `MessageList` validation where needed (like in `Party`).
8.  **Representations:** Ensure `__repr__` is informative. Standard `model_dump`/`model_dump_json` should replace custom serialization.

**Refactored Code:**

```python
# pixabit/models/message.py

# ─── Title ────────────────────────────────────────────────────────────────────
#            Habitica Message Models (Inbox & Group Chat)
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for Habitica messages (Inbox/PM and Group Chat).

Includes:
- `MessageSenderStyles`: Represents nested sender style information.
- `Message`: Represents an individual message entity with improved parsing.
- `MessageList`: A Pydantic `BaseModel` container class to manage a collection
  of Message objects, providing context-aware processing (like conversation IDs),
  sorting, and filtering.
"""

# SECTION: IMPORTS
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterator # Use standard lowercase etc.

# External Libs
import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo, # For context access
    field_validator,
    model_validator,
)

# Local Imports
try:
    from pixabit.config import USER_ID # Import the actual user ID from config
    from pixabit.helpers.DateTimeHandler import DateTimeHandler
    from pixabit.helpers._logger import log
except ImportError:
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    USER_ID = "fallback_user_id_from_config" # Fallback if config not found
    class DateTimeHandler:
        def __init__(self, timestamp: Any): self._ts = timestamp
        @property
        def utc_datetime(self) -> datetime | None:
             try: return datetime.fromisoformat(str(self._ts).replace("Z", "+00:00"))
             except: return None
    log.warning("message.py: Could not import config/helpers. Using fallbacks.")


# SECTION: HELPER FUNCTIONS

# FUNC: determine_conversation_id
def determine_conversation_id(message: Message, current_user_id: str | None) -> str | None:
    """Calculates conversation ID based on processed Message object and current user context.

    Args:
        message: The validated Message object.
        current_user_id: The ID of the user viewing the messages.

    Returns:
        A string identifying the conversation (group ID, other user's ID, 'system',
        or a special ID for messages to self/unknown), or None if indeterminate.
    """
    # 1. Group Chats are simplest
    if message.group_id:
        return message.group_id

    # 2. System messages
    if message.sender_id == "system":
        return "system" # Dedicated ID for system messages

    # 3. Private Messages - requires current_user_id context
    if not current_user_id:
        # Cannot determine PM partner without knowing 'me'
        log.debug(f"Cannot determine PM conversation ID for msg {message.id}: current_user_id missing.")
        # Return None or a placeholder? None seems cleaner for grouping logic.
        return None # Or perhaps f"unknown_context_{message.id[:6]}"

    sender = message.sender_id
    recipient = message.recipient_id # User ID of the inbox owner (present for inbox msgs)

    # Logic refinement based on message origin (inbox vs. sent)
    if message.sent_by_me:
        # Message was sent BY current_user
        # Check who it was sent TO. Often recipient_id is *not* populated for sent PMs in raw data.
        # The 'ownerId' (recipient_id) usually points to the *inbox owner*.
        # We need to rely on OTHER information if available (e.g., endpoint context or `userV` field)
        # For now, assume recipient_id IS the *other* person if populated and not 'me'.
        if recipient and recipient != current_user_id:
            return recipient # Conversation with the recipient
        else:
            # Recipient is missing or is myself on a sent message. Cannot determine partner.
            log.debug(f"Cannot determine conversation partner for SENT message {message.id}. Sender: {sender}, Recipient: {recipient}")
            # Need a way to distinguish 'message sent to self' from 'cannot determine recipient'.
            # If recipient == current_user_id -> it's a message to self.
            if recipient == current_user_id:
                 return f"self:{current_user_id}" # Special ID for messages to self
            else:
                 return f"unknown_recipient:{message.id[:8]}" # Placeholder for unknown

    else:
        # Message was received BY current_user (sent_by_me is False)
        # The conversation partner is the sender (unless it's system).
        if sender and sender != current_user_id:
             return sender # Conversation is with the sender
        elif sender == current_user_id:
             # This means sender=me, but sent_by_me=False? Inconsistent data?
             # Could happen if viewing own messages in someone else's shared party/guild view?
             # Or if `sent_by_me` logic failed. Assume it's a message *I* sent.
             log.warning(f"Inconsistent state for message {message.id}: Sender is current user, but sent_by_me is False. Treating as 'sent to self' for conversation ID.")
             return f"self:{current_user_id}"
        else:
            # Sender is missing or invalid, and not sent by me.
            log.debug(f"Could not determine conversation partner for RECEIVED message {message.id}. Sender: {sender}, Recipient: {recipient}")
            return f"unknown_sender:{message.id[:8]}" # Placeholder for unknown


# SECTION: PYDANTIC SUB-MODELS


# KLASS: MessageSenderStyles
class MessageSenderStyles(BaseModel):
    """Represents nested user style information potentially in message data."""

    # Allow other fields related to styles but ignore them for now
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    # Explicitly model fields we might care about (like class)
    klass: str | None = Field(None, alias="class", description="Sender's class ('rogue', 'wizard', etc.)")

    @model_validator(mode="before")
    @classmethod
    def extract_nested_class(cls, data: Any) -> dict[str, Any]:
        """Extracts 'class' from a nested 'stats' dictionary if present."""
        if not isinstance(data, dict):
            return data if isinstance(data, dict) else {}
        values = data.copy()
        # If 'class' is already top-level, use it
        if 'class' not in values:
            stats_data = data.get("stats")
            if isinstance(stats_data, dict):
                # Map stats.class -> class (for alias 'klass')
                values["class"] = stats_data.get("class")
        return values


# SECTION: MAIN MESSAGE MODEL


# KLASS: Message
class Message(BaseModel):
    """Represents an individual message in Habitica (Inbox or Group Chat)."""

    # Allow fields like userV, _v which we ignore
    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    # --- Core IDs & Context ---
    id: str = Field(..., description="Unique message document ID (mapped from _id).")
    # Sender ID ('uuid'): 'system' for system messages, user UUID otherwise
    sender_id: str | None = Field(None, alias="uuid", description="UUID of the sender ('system' for system messages).")
    # Group ID ('groupId'): 'party', guild ID, 'tavern', etc. Null for PMs.
    group_id: str | None = Field(
        None, alias="groupId", description="ID of the group chat context, if any."
    )
    # Recipient ID ('ownerId'): Primarily for inbox messages, user ID of the inbox owner.
    # Crucial for determining conversation partner in PMs.
    recipient_id: str | None = Field(
        None, alias="ownerId", description="User ID of the inbox owner (recipient context)."
    )

    # --- Sender Info (Partially from direct fields, partially nested) ---
    # 'user' field often holds display name in chat messages
    sender_display_name: str | None = Field(None, alias="user", description="Sender's display name (parsed).")
    # 'username' field often holds login name
    sender_username: str | None = Field(None, alias="username", description="Sender's login name.")
    # Nested style information (optional)
    sender_styles: MessageSenderStyles | None = Field(None, alias="userStyles", description="Sender's style info.")

    # --- Content & Timestamp ---
    text: str = Field("", description="Formatted message text (parsed).")
    # Raw markdown source (less common in API now, but can be useful if present)
    unformatted_text: str | None = Field(None, alias="unformattedText", description="Raw markdown source text (parsed).")
    timestamp: datetime | None = Field(None, description="Timestamp message sent/received (UTC).")

    # --- Engagement & Flags ---
    # Store likes/flags as dict {user_id: bool/timestamp} - Use bool for simplicity
    # Default factory ensures these are initialized as empty dicts
    likes: dict[str, bool] = Field(default_factory=dict, description="Dictionary of user IDs who liked the message.")
    flags: dict[str, bool] = Field(default_factory=dict, description="Dictionary of user IDs who flagged the message.")
    flag_count: int = Field(0, alias="flagCount", description="Reported count of flags.")

    # --- System Message Info ---
    # 'info' field contains structured data for system messages (spell casts, quest progress, etc.)
    info: dict[str, Any] | None = Field(None, description="Structured data for system messages.")

    # --- Fields Calculated during MessageList Processing ---
    # These depend on context (current_user_id)
    sent_by_me: bool | None = Field(
        None,
        exclude=True, # Exclude from model dump as it's context-dependent runtime info
        description="Derived: True if message was sent by the current user context.",
    )
    conversation_id: str | None = Field(
        None,
        exclude=True, # Exclude from dump
        description="Derived: Grouping ID (group_id or other user's ID in PMs, 'system', etc.).",
    )
    is_pm: bool | None = Field(
         None,
         exclude=True, # Exclude from dump
         description="Derived: True if message is likely a Private Message.",
    )

    # --- Validators ---

    @model_validator(mode="before")
    @classmethod
    def prepare_data(cls, data: Any) -> dict[str, Any]:
        """Map '_id' to 'id' before other validation."""
        if not isinstance(data, dict):
             # Let Pydantic raise type error
             return data

        values = data.copy()
        # Map _id if needed
        if "_id" in values and "id" not in values:
            values["id"] = values["_id"]

        # Default sender display name from username if needed?
        # This is tricky as 'user' field often contains the display name.
        # if not values.get('user') and values.get('username'):
        #      values['user'] = values['username'] # Risky, 'user' is primary

        return values


    @field_validator("id", mode="after")
    @classmethod
    def check_id(cls, v: str) -> str:
         """Ensure ID is a non-empty string after potential mapping."""
         if not v or not isinstance(v, str):
             raise ValueError("Message ID (_id) is required and must be a string.")
         return v


    # Consolidate text parsing for all relevant fields
    @field_validator("text", "unformatted_text", "sender_display_name", "sender_username", mode="before")
    @classmethod
    def parse_text_fields(cls, value: Any, info: FieldValidationInfo) -> str | None:
        """Parses text fields: replaces emoji, strips whitespace. Handles None for optional."""
        if isinstance(value, str):
             parsed = emoji_data_python.replace_colons(value).strip()
             # Defaulting behavior handled by Field(default=...)
             return parsed if parsed else None # Return None if strip results in empty for optional fields
        # Allow None for optional fields like unformatted_text, sender_username, sender_display_name
        return None


    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp_utc(cls, value: Any) -> datetime | None:
        """Parses timestamp using DateTimeHandler."""
        handler = DateTimeHandler(timestamp=value)
        if value is not None and handler.utc_datetime is None:
             log.warning(f"Could not parse timestamp for message field: {value!r}")
        return handler.utc_datetime


    @field_validator("flag_count", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensures flag_count is an integer, defaulting to 0."""
        if value is None: return 0
        try:
            return int(float(value)) # Handle potential float input
        except (ValueError, TypeError):
            log.debug(f"Could not parse message flag_count: {value!r}. Using 0.")
            return 0

    # --- Computed Properties / Methods ---

    @property
    def is_system_message(self) -> bool:
        """Checks if this is likely a system message."""
        # Check sender_id explicitly or presence of 'info' field
        return self.sender_id == "system" or bool(self.info)

    @property
    def sender_class(self) -> str | None:
        """Extracts sender's class from sender_styles, if available."""
        return self.sender_styles.klass if self.sender_styles else None


    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        sender = "System" if self.is_system_message else (self.sender_username or self.sender_id or "Unknown")
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M") if self.timestamp else "NoTime"
        # Show derived conversation_id if available
        conv = f" (ConvID: {self.conversation_id})" if self.conversation_id else ""
        pm_flag = " (PM)" if self.is_pm else ""
        sent_flag = " (Sent)" if self.sent_by_me else (" (Rcvd)" if self.sent_by_me is False else "")
        text_preview = self.text[:30].replace("\n", " ") + ("..." if len(self.text) > 30 else "")
        return f"Message(id='{self.id}', from='{sender}', time='{ts}{sent_flag}{pm_flag}{conv}', text='{text_preview}')"


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MESSAGE LIST CONTAINER


# KLASS: MessageList
class MessageList(BaseModel):
    """BaseModel container for managing Message objects.

    Handles validation, context-dependent field calculation (sent_by_me,
    conversation_id, is_pm), sorting, and provides filtering methods.
    """
    model_config = ConfigDict(
        extra="forbid",            # No unexpected fields
        arbitrary_types_allowed=False,
    )

    # The main data field: list of validated Message objects
    messages: list[Message] = Field(default_factory=list, description="Validated list of Message objects.")

    # Add context field directly? No, use ValidationInfo during validation.

    @model_validator(mode="before")
    @classmethod
    def process_raw_messages(cls, data: Any, info: ValidationInfo) -> dict[str, Any]:
        """
        Validates raw message data, calculates derived fields using context, sorts,
        and returns the structured data for the MessageList model.

        Expects 'current_user_id' in validation context (`info.context`).
        Expects input `data` to be the raw list of message dicts.
        """
        # --- Get Context ---
        # Fetch current_user_id from the validation context passed during instantiation.
        # Use the globally imported USER_ID as a fallback if context is missing (e.g., during tests).
        current_user_id: str | None = None
        if info.context and isinstance(info.context, dict):
            current_user_id = info.context.get("current_user_id")

        # If still None, maybe use the global USER_ID (consider implications)
        if current_user_id is None:
            # Use the one imported from config as a last resort, might not be right context always
             current_user_id = USER_ID # Requires USER_ID to be imported from pixabit.config
             if not current_user_id or current_user_id == "fallback_user_id_from_config": # Check if it's a real ID
                 log.warning("'current_user_id' not found in context or config. Derived message fields (sent_by_me, conversation_id) may be inaccurate.")
                 current_user_id = None # Explicitly set to None if unusable

        # --- Process Input ---
        # This validator receives the *entire* input intended for the model.
        # If called like `MessageList.model_validate(raw_list, context=...)`, data is raw_list.
        # If called like `MessageList.model_validate({"messages": raw_list}, context=...)`, data is the dict.
        raw_message_list: list[Any] | None = None
        if isinstance(data, list):
            raw_message_list = data
        elif isinstance(data, dict):
            # Assume the list is under the 'messages' key if input is dict
            raw_message_list = data.get("messages")
            if not isinstance(raw_message_list, list):
                raise ValidationError.from_exception_data(
                    title=cls.__name__,
                    line_errors=[{"loc": ("messages",), "input": data.get("messages"), "type": "list_expected"}],
                 )
        else:
             raise ValidationError.from_exception_data(
                 title=cls.__name__,
                 line_errors=[{"loc": (), "input": data, "type": "list_or_dict_expected"}],
             )

        # --- Validate, Enrich, and Collect Messages ---
        processed_messages: list[Message] = []
        validation_errors = []

        for index, item in enumerate(raw_message_list):
            if not isinstance(item, dict):
                log.warning(f"Skipping non-dict item at index {index} in message list.")
                validation_errors.append(f"Item at index {index} is not a dictionary.")
                continue

            try:
                # 1. Validate raw dict into Message model
                msg = Message.model_validate(item)

                # 2. Calculate context-dependent fields if user_id is known
                if current_user_id:
                     # Determine if sent by current user
                     # Explicit check against sender ID is primary.
                     # The old 'sent' flag from raw data is less reliable.
                     msg.sent_by_me = msg.sender_id == current_user_id
                     # Check if recipient is me when sent by someone else
                     # sent_to_me = not msg.sent_by_me and msg.recipient_id == current_user_id

                     # Determine conversation ID using the helper function
                     msg.conversation_id = determine_conversation_id(msg, current_user_id)

                     # Determine if PM (no group_id and not system message)
                     msg.is_pm = not msg.group_id and not msg.is_system_message
                else:
                     # Cannot reliably determine these without user context
                     msg.sent_by_me = None
                     msg.conversation_id = msg.group_id or ("system" if msg.is_system_message else None) # Fallback
                     msg.is_pm = not msg.group_id and not msg.is_system_message # Can still guess PM structure


                processed_messages.append(msg)

            except ValidationError as e:
                item_id = item.get("id", item.get("_id", f"index_{index}"))
                log.error(f"Validation failed for message ID '{item_id}': {e}")
                # Collect detailed errors if needed
                validation_errors.extend(e.errors(include_input=False)) # Pydantic v2 way
            except Exception as e:
                item_id = item.get("id", item.get("_id", f"index_{index}"))
                log.exception(f"Unexpected error processing message ID '{item_id}': {e}")
                validation_errors.append(f"Unexpected error processing message {item_id}")

        if validation_errors:
             # Decide how to handle errors: log, raise summary error, or continue
             # For robustness, log and continue is often preferred for lists.
             log.warning(f"Encountered {len(validation_errors)} errors during message list processing.")
             # Example: raise ValidationError.from_exception_data(...) if strictness needed


        # 3. Sort messages by timestamp (most recent last)
        # Use a safe default time for messages lacking a timestamp
        default_time = datetime.min.replace(tzinfo=timezone.utc)
        processed_messages.sort(key=lambda m: m.timestamp or default_time)
        log.debug(f"Processed and sorted {len(processed_messages)} messages.")


        # --- Return Structured Data for Model ---
        # Pydantic expects the validator to return a dictionary matching the model fields
        return {"messages": processed_messages}

    # --- Access and Filtering Methods ---
    # Operate on the validated `self.messages` list

    def __len__(self) -> int:
        return len(self.messages)

    def __iter__(self) -> Iterator[Message]:
        return iter(self.messages)

    def __getitem__(self, index: int | slice) -> Message | list[Message]:
        if isinstance(index, int):
            if not 0 <= index < len(self.messages):
                raise IndexError("Message index out of range")
        # Slicing works inherently
        return self.messages[index]

    def get_by_id(self, message_id: str) -> Message | None:
        """Finds a message by its unique ID."""
        return next((m for m in self.messages if m.id == message_id), None)

    def filter_by_sender(self, sender_id_or_name: str, case_sensitive: bool = False) -> MessageList:
        """Returns messages sent by a specific user ID or username. Returns new MessageList."""
        if not case_sensitive:
             sender_id_or_name_lower = sender_id_or_name.lower()
             filtered = [m for m in self.messages if
                          (m.sender_id and m.sender_id.lower() == sender_id_or_name_lower) or
                          (m.sender_username and m.sender_username.lower() == sender_id_or_name_lower)
                         ]
        else:
             filtered = [m for m in self.messages if
                         m.sender_id == sender_id_or_name or
                         m.sender_username == sender_id_or_name
                        ]
        return MessageList(messages=filtered) # Return new instance


    def filter_by_conversation(self, conversation_id: str) -> MessageList:
        """Returns messages belonging to a specific conversation ID (group or PM partner). Returns new MessageList."""
        # Uses the derived conversation_id field
        filtered = [m for m in self.messages if m.conversation_id == conversation_id]
        return MessageList(messages=filtered)


    def filter_by_group(self, group_id: str) -> MessageList:
        """Returns messages belonging to a specific group ID. Returns new MessageList."""
        filtered = [m for m in self.messages if m.group_id == group_id]
        return MessageList(messages=filtered)


    def filter_private_messages(self) -> MessageList:
        """Returns likely Private Messages (uses derived 'is_pm' flag). Returns new MessageList."""
        filtered = [m for m in self.messages if m.is_pm]
        return MessageList(messages=filtered)


    def filter_system_messages(self) -> MessageList:
        """Returns only system messages. Returns new MessageList."""
        filtered = [m for m in self.messages if m.is_system_message]
        return MessageList(messages=filtered)


    def filter_non_system_messages(self) -> MessageList:
        """Returns only non-system messages. Returns new MessageList."""
        filtered = [m for m in self.messages if not m.is_system_message]
        return MessageList(messages=filtered)


    # ... Add other filter methods from original code, ensuring they return MessageList ...

    def get_conversations(self) -> dict[str, list[Message]]:
        """Groups messages by their calculated conversation ID.

        Returns:
            A dictionary where keys are conversation IDs and values are lists
            of Message objects belonging to that conversation, sorted chronologically.
            Conversations themselves are ordered by the timestamp of the latest message.
        """
        grouped = defaultdict(list)
        valid_conv_ids = set()
        for msg in self.messages:
            # Group only messages that have a valid conversation_id
            if msg.conversation_id:
                 grouped[msg.conversation_id].append(msg)
                 valid_conv_ids.add(msg.conversation_id) # Keep track of keys added


        # Sort by most recent activity (using timestamp of the last message in each group)
        default_time = datetime.min.replace(tzinfo=timezone.utc)
        sorted_ids = sorted(
            valid_conv_ids, # Sort only the keys we actually added to grouped dict
            key=lambda cid: grouped[cid][-1].timestamp or default_time,
            reverse=True, # Most recent conversations first
        )

        # Return ordered dictionary
        return {cid: grouped[cid] for cid in sorted_ids}


    def __repr__(self) -> str:
        """Simple representation."""
        return f"MessageList(count={len(self.messages)})"


# ──────────────────────────────────────────────────────────────────────────────
```

---

## File: `pixabit/models/party.py`

**Suggestions:**

1.  **Pydantic V2:** Convert models (`QuestProgress`, `QuestInfo`, `PartyMember`, `Party`).
2.  **`QuestInfo` & `QuestProgress`:** Make these robust. `QuestProgress` should handle potential `None` values for hp/rage. `QuestInfo` `is_active_and_ongoing` property is useful.
3.  **`PartyMember`:** Keep this basic as full member details require separate API calls. Just include essential identifiers if available in the party endpoint data (`_id`). Display names often require merging with User data.
4.  **`Party` Model:**
    - Make `id` required.
    - Use `model_validator` to extract `leader_id` and handle `_id`.
    - Handle `chat` by validating it as `MessageList` (nested Pydantic validation). Pass `current_user_id` via _context_ when validating the `Party` model.
    - Add placeholder for `members: list[PartyMember]` (Pydantic will validate this if member data is included). Exclude `chat` and `members` from default dumps unless explicitly requested.
    - Consolidate emoji parsing.
5.  **Static Quest Details:** Add a _method_ to `Party` (e.g., `fetch_and_set_static_quest_details`) that takes the `StaticContentManager` as input. This method fetches the static details for `self.quest.key` and _stores_ them on the `Party` instance (e.g., in a `_static_quest_data: Quest | None = None` field marked with `exclude=True`). Avoid doing the fetch during initial validation.
6.  **Factory Method (`create_from_raw_data`)**: This is essential for passing the `current_user_id` context needed by `MessageList` validation.
7.  **Serialization:** Remove custom `to_json`. Use `model_dump`/`model_dump_json` and rely on the nested models' serialization. Add parameters like `exclude`/`include` to control output.
8.  **Main Function:** Update `main` to demonstrate context passing and static data fetching.

**Refactored Code:**

```python
# pixabit/models/party.py

# ─── Title ────────────────────────────────────────────────────────────────────
#            Habitica Party & Quest Models
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for Habitica Parties, including nested quest progress,
chat messages (via MessageList), and basic member information.
"""

# SECTION: IMPORTS
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator # Use standard lowercase etc.

# External Libs
import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo, # For context
    field_validator,
    model_validator,
    PrivateAttr, # For internal, non-dumped attributes
)

# Local Imports
try:
    from pixabit.api.client import HabiticaClient
    from pixabit.config import USER_ID, HABITICA_DATA_PATH # Import USER_ID
    from pixabit.helpers._json import save_pydantic_model, load_pydantic_model
    from pixabit.helpers._logger import log
    from pixabit.helpers.DateTimeHandler import DateTimeHandler
    # Import models used within Party
    from .message import Message, MessageList
    from .game_content import Quest as StaticQuestData # Rename to avoid clash
    from .game_content import StaticContentManager
except ImportError:
    # Fallbacks for isolated testing
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    USER_ID = "fallback_user_id_from_config"
    HABITICA_DATA_PATH = Path("./pixabit_cache")
    def save_pydantic_model(m, p, **kwargs): pass
    def load_pydantic_model(cls, p, **kwargs): return None
    class HabiticaClient: async def get_party_data(self): return {} # Mock
    class DateTimeHandler: pass
    class Message: pass
    class MessageList(BaseModel): messages: list = [] # Basic placeholder
    class StaticQuestData: pass # Placeholder
    class StaticContentManager: async def get_quest(self, key: str): return None # Mock
    log.warning("party.py: Could not import dependencies. Using fallbacks.")

CACHE_SUBDIR = "party"
PARTY_RAW_FILENAME = "party_raw.json"
PARTY_PROCESSED_FILENAME = "party_processed.json"


# SECTION: PYDANTIC SUB-MODELS


# KLASS: QuestProgress
class QuestProgress(BaseModel):
    """Represents the progress within an active party quest."""

    model_config = ConfigDict(
        extra="ignore",         # Ignore fields like quest key/leader here
        populate_by_name=True,
        frozen=False,           # Progress changes
    )

    # Boss quest progress
    up: float = Field(0.0, description="Boss damage dealt or positive habit progress.")
    down: float = Field(0.0, description="Damage taken or negative habit progress.")
    hp: float | None = Field(None, description="Boss current HP (if applicable).") # Boss HP can be None
    rage: float | None = Field(None, description="Boss current Rage (if applicable).") # Rage can be None

    # Collection quest progress
    # Raw collect goals are dict like {item_key: count_needed} - Use extra='allow'? Or explicit model?
    # Pydantic can parse dicts directly, 'extra=allow' is simplest if keys vary widely
    # collect: dict[str, int] = Field(default_factory=dict, description="Item collection goals (key: count needed).")
    # Prefer defining if structure is consistent from API
    collect_goals: dict[str, int] = Field(default_factory=dict, alias="collect", description="Item collection goals (key: count needed).")

    # Actual collected count (often separate field from goals)
    collected_items_count: int = Field(0, alias="collectedItems", description="Items collected so far for collection quests.")


    # Validator for numeric fields
    @field_validator("up", "down", "hp", "rage", mode="before")
    @classmethod
    def ensure_float_or_none(cls, value: Any) -> float | None:
        """Ensures numeric progress fields are floats if present, else None."""
        if value is None: return None
        try:
            return float(value)
        except (ValueError, TypeError):
            log.debug(f"Could not parse quest progress value: {value!r}. Defaulting.")
            # Defaulting to 0 might be wrong if None meant "not applicable"
            # Return 0 for up/down, None for hp/rage might be better? Let's default to 0.0 for now.
            return 0.0 # Or decide based on field if None is more appropriate default

    @field_validator("collected_items_count", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensures collected_items is an integer, defaulting to 0."""
        if value is None: return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            log.debug(f"Could not parse collected_items value: {value!r}. Setting to 0.")
            return 0

    # Collect goals validation? Could ensure keys are str, values are int.
    # Pydantic dict validation usually handles basic types.

    def __repr__(self) -> str:
        """Concise representation."""
        parts = []
        if self.hp is not None: parts.append(f"hp={self.hp:.1f}")
        if self.rage is not None: parts.append(f"rage={self.rage:.1f}")
        # Only show up/down if non-zero or hp exists (relevant for boss quests)
        if self.hp is not None or self.up != 0.0: parts.append(f"up={self.up:.1f}")
        if self.hp is not None or self.down != 0.0: parts.append(f"down={self.down:.1f}")
        if self.collect_goals:
             goal_str = ",".join(f"{k}:{v}" for k, v in self.collect_goals.items())
             parts.append(f"collect={self.collected_items_count}/[{goal_str}]")
        progress_str = ", ".join(parts) if parts else "No Progress"
        return f"QuestProgress({progress_str})"


# KLASS: QuestInfo
class QuestInfo(BaseModel):
    """Represents the metadata about the party's current quest."""

    model_config = ConfigDict(
        extra="ignore",          # Ignore fields like webhook url etc.
        populate_by_name=True,
        frozen=False,            # Status changes (active, completed)
    )

    key: str | None = Field(None, description="Unique key for the quest (e.g., 'basilisk'). Null if no quest.")
    active: bool = Field(False, description="Is the quest active (invitation sent/accepted)?")
    # Use alias for API's `RSVPNeeded`
    rsvp_needed: bool = Field(False, alias="RSVPNeeded", description="Does leader need to accept invites?")
    # Completion status: Can be timestamp string, 'allGuilds', or null/absent. Store as string.
    completed_status: str | None = Field(None, alias="completed", description="Completion status or timestamp string.")
    leader_id: str | None = Field(None, alias="leader", description="User ID of the quest leader/inviter.")

    # Member RSVP status {userId: bool | null} - Null means pending? bool means accepted/declined?
    # API might use `true` for accepted, `false` for declined?, absence=pending?
    # Using bool | None for flexibility.
    member_rsvp: dict[str, bool | None] = Field(default_factory=dict, alias="members")

    # Nested progress model
    progress: QuestProgress = Field(default_factory=QuestProgress)


    # --- Derived Properties ---
    @property
    def completed_timestamp(self) -> datetime | None:
        """Parses completed_status into a datetime if possible."""
        if self.completed_status:
             handler = DateTimeHandler(timestamp=self.completed_status)
             return handler.utc_datetime # Returns None if parsing fails
        return None

    @property
    def is_active_and_ongoing(self) -> bool:
        """Calculates if the quest is active AND not yet completed."""
        # Active flag must be true AND completed_status must be missing/null/empty
        return self.active and not self.completed_status


    # --- Representation ---
    def __repr__(self) -> str:
        """Concise representation."""
        status = "Inactive"
        if self.completed_status:
            completion_time = self.completed_timestamp
            status = f"Completed ({completion_time.strftime('%Y-%m-%d')})" if completion_time else f"Completed ({self.completed_status})"
        elif self.active:
            status = "Active/Ongoing" if self.is_active_and_ongoing else "Active/Pending?" # Or Invited?

        key_str = f"key='{self.key}'" if self.key else "No Quest"
        return f"QuestInfo({key_str}, status={status})"


# KLASS: PartyMember (Basic info available directly in party data)
class PartyMember(BaseModel):
    """Represents basic info about a member as found in party data (usually just ID)."""
    # API `/groups/{groupId}` returns a list of member *IDs*.
    # Full member details require additional calls.
    # So this model primarily just holds the ID found in the party structure itself.
    # If the API endpoint DOES provide more nested details, expand this model.

    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)
    # Assuming the list contains just IDs, not full member objects
    id: str # This would be validated from the list of strings if members = ['id1', 'id2']

    # If API returns list of member objects:
    # id: str = Field(..., alias="_id") # Map from _id if needed
    # display_name: str | None = None # Often requires separate fetch
    # username: str | None = None     # Often requires separate fetch


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MAIN PARTY MODEL


# KLASS: Party
class Party(BaseModel):
    """Represents a Habitica Party group object, including quest and chat."""

    model_config = ConfigDict(
        extra="ignore",           # Ignore fields like leader message, leader object details
        populate_by_name=True,
        validate_assignment=True, # Re-validate on assignment if needed
        arbitrary_types_allowed=True, # Needed for MessageList initially, might be removable if MessageList validation works directly
    )

    # --- Core Identification & Info ---
    id: str = Field(..., description="Unique party ID (mapped from _id).")
    name: str = Field("Unnamed Party", description="Party name (parsed emoji).")
    description: str = Field("", description="Party description (parsed emoji).")
    # summary: str | None = Field(None, description="Party summary/tagline (parsed emoji).") # Less common

    # --- Leader & Members ---
    leader_id: str | None = Field(None, description="User ID of the party leader.") # Extracted by validator
    # The raw API has `memberCount` and a separate `members` list (usually just IDs).
    # We store the count directly. Member objects would need separate loading/linking.
    member_count: int = Field(0, alias="memberCount", description="Number of members in the party.")
    # Optional: store member IDs if useful
    # member_ids: list[str] = Field(default_factory=list)

    # --- Quest ---
    quest: QuestInfo = Field(default_factory=QuestInfo, description="Details of the current party quest.")

    # --- Chat ---
    # Use the MessageList Pydantic model. Validation will happen here.
    # Context (`current_user_id`) is needed for MessageList validation.
    # Exclude from default serialization unless explicitly included.
    chat: MessageList | None = Field(None, description="Party chat messages.", exclude=True)

    # --- Sorting Info ---
    # order: str | None = Field(None, description="Field used for sorting members.") # Less commonly used?
    # order_ascending: bool | None = Field(None, alias="orderAscending")

    # --- Internal attribute for storing fetched static quest data ---
    _static_quest_details: StaticQuestData | None = PrivateAttr(default=None)


    # --- Validators ---

    @model_validator(mode="before")
    @classmethod
    def prepare_data(cls, data: Any) -> dict[str, Any]:
        """Prepare raw data: Map IDs, extract leader ID."""
        if not isinstance(data, dict):
            return data # Let Pydantic handle type error

        values = data.copy()

        # Map _id -> id
        if "_id" in values and "id" not in values:
            values["id"] = values["_id"]

        # Extract leader ID from potentially nested structure
        leader_info = values.get("leader")
        if isinstance(leader_info, str):
            # Leader is just an ID string
            values["leader_id"] = leader_info
        elif isinstance(leader_info, dict):
             # Leader is an object, get ID from it
             values["leader_id"] = leader_info.get("_id") or leader_info.get("id")
        # 'leader' key itself might be absent

        # Handle potential direct 'chat' list/dict from API
        # Pydantic handles validating `chat` key against `MessageList` type hint

        # Extract member IDs? Assuming API provides `members` as list of IDs
        # member_data = values.get("members")
        # if isinstance(member_data, list) and all(isinstance(m, str) for m in member_data):
        #      values["member_ids"] = member_data

        return values

    # Ensure ID exists after potential mapping
    @field_validator("id", mode="after")
    @classmethod
    def check_id(cls, v: str) -> str:
         if not v or not isinstance(v, str):
             raise ValueError("Party ID (_id) is required and must be a string.")
         return v

    # Consolidate text parsing
    @field_validator("name", "description", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any, info: FieldValidationInfo) -> str:
        """Parses text fields, replaces emoji, handles defaults."""
        default = "Unnamed Party" if info.field_name == "name" else ""
        if isinstance(value, str):
            parsed = emoji_data_python.replace_colons(value).strip()
            return parsed if parsed else default
        return default


    @field_validator("member_count", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
         """Ensure member_count is an integer."""
         if value is None: return 0
         try: return int(value)
         except (ValueError, TypeError): return 0


    # --- Methods ---

    @classmethod
    def create_from_raw_data(cls, raw_data: dict, current_user_id: str | None = None) -> Party:
        """Factory method to create Party, passing context for chat validation."""
        if not isinstance(raw_data, dict):
            log.error(f"Invalid raw data type for Party creation: Expected dict, got {type(raw_data)}")
            raise TypeError("Invalid input data for Party creation.")

        # Define the context required by MessageList validation
        validation_context = {"current_user_id": current_user_id}

        log.debug(f"Creating Party from raw data with context: {validation_context}")
        try:
            # Validate the raw data using the context
            # Pydantic will automatically pass this context down when validating nested models
            # like 'chat: MessageList' if the nested model's validator requests it.
            party_instance = cls.model_validate(raw_data, context=validation_context)
            log.debug(f"Party instance created successfully: {party_instance.id}")
            return party_instance
        except ValidationError as e:
            log.error(f"Validation failed creating Party model: {e}", exc_info=False) # Log less verbose error
            log.debug(f"Failed raw data keys: {list(raw_data.keys())}") # Log keys for debugging
            # Optionally log parts of the data that failed, be mindful of size/privacy
            # log.debug(f"Failing quest data: {raw_data.get('quest')}")
            # log.debug(f"Failing chat data sample: {raw_data.get('chat', [])[:2]}")
            raise # Re-raise the specific Pydantic error
        except Exception as e:
            log.exception("Unexpected error creating Party from raw data.") # Log full trace
            raise


    def get_chat_messages(self) -> list[Message]:
        """Returns the validated list of chat messages, or an empty list."""
        # Access validated messages from the nested MessageList model
        return self.chat.messages if self.chat else []


    async def fetch_and_set_static_quest_details(self, content_manager: StaticContentManager) -> StaticQuestData | None:
        """Fetches static quest details using the content manager and caches it internally.

        Args:
            content_manager: An instance of StaticContentManager.

        Returns:
            The fetched static quest data, or None if not found or no quest active.
        """
        if not self.quest or not self.quest.key:
            log.debug("Party has no active quest key. Cannot fetch static details.")
            self._static_quest_details = None
            return None

        log.debug(f"Fetching static quest details for key: '{self.quest.key}'")
        try:
            # Use the provided manager instance to get quest details
            static_data = await content_manager.get_quest(self.quest.key)
            if static_data:
                 log.success(f"Successfully fetched static details for quest '{self.quest.key}'.")
                 self._static_quest_details = static_data # Store internally
                 return static_data
            else:
                 log.warning(f"Static details not found for quest key '{self.quest.key}'.")
                 self._static_quest_details = None
                 return None
        except Exception as e:
             log.exception(f"Error fetching static quest details for '{self.quest.key}': {e}")
             self._static_quest_details = None
             return None


    @property
    def static_quest_details(self) -> StaticQuestData | None:
         """Returns the internally cached static quest details (if fetched)."""
         return self._static_quest_details

    # --- Representation ---
    def __repr__(self) -> str:
        """Concise representation."""
        quest_repr = repr(self.quest) if self.quest else "No Quest"
        chat_len = len(self.chat.messages) if self.chat and self.chat.messages else 0
        name_preview = self.name[:30].replace("\n", " ") + ("..." if len(self.name) > 30 else "")

        return f"Party(id='{self.id}', name='{name_preview}', members={self.member_count}, chat={chat_len}, {quest_repr})"

    def __str__(self) -> str:
         """User-friendly representation (name)."""
         return self.name

# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MAIN EXECUTION (Example/Test)

async def main():
    """Demo function to retrieve, process, and save party data."""
    log.info("--- Party Model Demo ---")
    party_instance: Party | None = None

    # Use USER_ID from config for context
    user_id_context = USER_ID
    if not user_id_context or user_id_context == "fallback_user_id_from_config":
         log.warning("Cannot run demo effectively: Valid USER_ID not found in config.")
         # Provide a dummy ID for testing if absolutely necessary
         user_id_context = "test-user-id-123"
         log.info(f"Using dummy USER_ID for context: {user_id_context}")


    try:
        # Ensure cache directory exists
        cache_dir = HABITICA_DATA_PATH / CACHE_SUBDIR
        cache_dir.mkdir(exist_ok=True, parents=True)
        raw_path = cache_dir / PARTY_RAW_FILENAME
        processed_path = cache_dir / PARTY_PROCESSED_FILENAME

        # 1. Get data from API
        log.info("Fetching party data from API...")
        api = HabiticaClient() # Assumes configured
        raw_data = await api.get_party_data()

        if not raw_data:
             log.error("Failed to fetch party data from API. Exiting.")
             return None

        # Optionally save raw data
        # save_json(raw_data, raw_path)

        # 2. Create Party model using the factory method with context
        log.info(f"Processing raw party data (using user ID '{user_id_context}' for chat context)...")
        party_instance = Party.create_from_raw_data(raw_data, current_user_id=user_id_context)
        log.success("Party model created successfully.")

        # 3. Example Data Access
        print(f"  Party Name: {party_instance.name}")
        print(f"  Party ID: {party_instance.id}")
        print(f"  Leader ID: {party_instance.leader_id}")
        print(f"  Member Count: {party_instance.member_count}")
        print(f"  Quest Info: {party_instance.quest}")
        print(f"  Quest Progress: {party_instance.quest.progress}")
        print(f"  Chat Message Count: {len(party_instance.get_chat_messages())}")

        # 4. Example: Fetch and store static quest data
        log.info("Attempting to fetch static quest details...")
        # Requires StaticContentManager to be instantiated
        content_manager = StaticContentManager() # Use default paths
        static_details = await party_instance.fetch_and_set_static_quest_details(content_manager)
        if static_details:
             print(f"  Fetched Static Quest Title: {static_details.text}") # Access field from StaticQuestData
        elif party_instance.quest.key:
              print(f"  Could not fetch static details for quest '{party_instance.quest.key}'.")
        else:
              print("  No active quest to fetch details for.")

        # 5. Save processed data (using pydantic helper)
        # Choose whether to include chat by controlling the dump excludes manually if needed,
        # or rely on the exclude=True in the Field definition. model_dump respects exclude=True by default.
        log.info(f"Saving processed party data to {processed_path}...")
        if save_pydantic_model(party_instance, processed_path): # Chat excluded by default
             log.success("Processed party data saved.")
             # To explicitly include chat:
             # data_to_save = party_instance.model_dump(mode='json', exclude_none=True) # Pydantic handles exclude=True
             # save_json(data_to_save, cache_dir / "party_with_chat.json")
        else:
            log.error("Failed to save processed party data.")

    except ValidationError as e:
        log.error(f"Pydantic validation error during party processing: {e}")
    except ConnectionError as e:
        log.error(f"API connection error fetching party data: {e}")
    except Exception as e:
        log.exception(f"An unexpected error occurred in the party demo: {e}")

    return party_instance


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(main())

# ──────────────────────────────────────────────────────────────────────────────
```

---

## File: `pixabit/models/task.py`

**Suggestions:**

1.  **Pydantic V2 & Typing:** Convert models, use consistent Python 3.10+ typing.
2.  **Nested Models:** Ensure `ChecklistItem` and `ChallengeLinkData` are correct. `ChallengeLinkData` should clearly define `challenge_id` and handle the `broken` status interpretation.
3.  **Base `Task`:** Consolidate common validators (datetime, text). Make `id` required, handle `_id` mapping. Ensure `type` is validated using `Literal`.
4.  **Subclasses (`Habit`, `Daily`, `Todo`, `Reward`):** Define specific fields and ensure types/defaults are correct.
5.  **Calculated Status:** Use a `calculated_status` field, populated during processing. Rename `status` property to avoid confusion.
6.  **Tag Linking:** Use a `tag_names: list[str]` field on `Task`, populated _after_ initial validation by `TaskList.process_task_statuses` using a `TagList` provider. Make `tags_id` the field for raw API IDs.
7.  **Damage Calculation (`Daily`):**
    - Add `user_damage` and `party_damage` properties to `Daily`. Mark them with `@computed_field` so they are included in `model_dump`.
    - These properties should return values stored in private attributes (e.g., `_calculated_user_damage`).
    - The _calculation_ logic itself should be in a method (`calculate_and_store_damage`?) or triggered externally (like in `TaskList.process_task_statuses`). The method needs access to the `User` object (containing stats).
    - Refine the damage formula based on the provided logic and user stats structure. Ensure checklist mitigation is applied correctly.
8.  **`TaskList`:**
    - Keep `TaskList` as a _plain class_ for managing the list, not a `BaseModel` itself (unlike `ChallengeList`/`MessageList`). This aligns better with its role as a _manager_ that orchestrates processing. It receives _validated_ `Task` objects.
    - `from_api_data` becomes the crucial factory method for validating raw data into the correct `Task` subclasses. Improve its error handling.
    - `process_task_statuses` is the central place to calculate statuses, link tags, and _trigger_ damage calculation (which updates the `_calculated_...` attributes on the `Daily` instances). It needs `User` and `TagList` instances passed to it.
9.  **Helper Integration:** Use `DateTimeHandler`, `log`, `MarkdownRenderer`.
10. **Representations:** Clean up `__repr__` methods.

**Refactored Code:**

```python
# pixabit/models/task.py

# ─── Title ────────────────────────────────────────────────────────────────────
#         Habitica Task Models (Habits, Dailies, Todos, Rewards)
# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for representing Habitica Tasks (Habits, Dailies,
Todos, Rewards), including nested structures like ChecklistItem and
ChallengeLinkData. Provides a TaskList container for managing and processing
collections of Task objects.
"""

# SECTION: IMPORTS
from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Literal  # Use standard types

# External Libs
import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    computed_field, # For computed properties in dumps
    field_validator,
    model_validator,
    ValidationInfo, # For field context
    PrivateAttr, # For internal state
)

# Local Imports
try:
    # Helpers
    from pixabit.helpers._logger import log
    from pixabit.helpers._md_to_rich import MarkdownRenderer # Assuming already instantiated if needed globally
    from pixabit.helpers.DateTimeHandler import DateTimeHandler
    from pixabit.helpers._rich import Text # Type hint for styled text
    from pixabit.helpers._json import save_json # For demo

    # Required Models for processing/linking
    from pixabit.config import HABITICA_DATA_PATH
    from pixabit.api.client import HabiticaClient
    # Use TYPE_CHECKING to avoid runtime circular imports if TagList/User import Task
    if TYPE_CHECKING:
        from .tag import TagList
        from .user import User
        from .game_content import StaticContentManager, Quest as StaticQuestData # Need for Daily dmg calc context


except ImportError:
    # Fallbacks for isolated testing
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    HABITICA_DATA_PATH = Path("./pixabit_cache")
    class MarkdownRenderer: def markdown_to_rich_text(self, s: str) -> str: return s # Simple fallback
    class DateTimeHandler:
        def __init__(self, timestamp: Any): self._ts = timestamp
        @property
        def utc_datetime(self) -> datetime | None: return None # Fallback
    class Text: pass # Placeholder type
    class HabiticaClient: async def get_tasks(self): return [] # Mock
    def save_json(d, p, **k): pass
    if TYPE_CHECKING: # Still provide types for checking
        class TagList: def get_by_id(self, tid: str) -> Any: return None
        class User: pass
        class StaticContentManager: pass
        class StaticQuestData: pass
    log.warning("task.py: Could not import dependencies. Using fallbacks.")


# Create one instance of the renderer if used frequently
md_renderer = MarkdownRenderer()


# SECTION: NESTED DATA MODELS


# KLASS: ChecklistItem
class ChecklistItem(BaseModel):
    """Represents a single item within a task's checklist."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=False) # Checklist items can be changed

    id: str = Field(..., description="Checklist item ID.") # Habitica assigns UUIDs
    text: str = Field("", description="Text content of the item (parsed).")
    completed: bool = Field(False, description="Whether the item is checked off.")
    # progress: int = Field(0, description="Progress value for the item.") # Less common, ignore?

    @model_validator(mode="before")
    @classmethod
    def ensure_id(cls, data: Any) -> dict[str, Any]:
         """Ensure ID exists (API usually provides 'id')."""
         if isinstance(data, dict) and "id" not in data:
              # Maybe log or generate a placeholder? For now, let validation fail if required.
              # If ID *can* be missing, make `id: str | None = None`
              log.warning(f"Checklist item data missing 'id': {data.get('text', 'N/A')}")
         return data if isinstance(data, dict) else {}

    @field_validator("text", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any) -> str:
        """Parse text, replace emoji, strip whitespace."""
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value).strip()
        return ""

    def __repr__(self) -> str:
        status = "[x]" if self.completed else "[ ]"
        text_preview = self.text[:30].replace("\n", " ") + ("..." if len(self.text) > 30 else "")
        # Shorten ID for repr
        id_preview = self.id[:8] if self.id else "NoID"
        return f"ChecklistItem(id={id_preview}, status='{status}', text='{text_preview}')"

    def __str__(self) -> str:
         return f"{'[x]' if self.completed else '[ ]'} {self.text}"


# KLASS: ChallengeLinkData
class ChallengeLinkData(BaseModel):
    """Represents the challenge link information potentially within a task."""
    # Comes from task.challenge field in API response

    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True) # Links are usually static

    task_id: str | None = Field(None, alias="taskId", description="Original task ID within the challenge (if cloned).")
    challenge_id: str = Field(..., alias="id", description="Challenge ID the task belongs to.") # Require ID
    short_name: str | None = Field(None, alias="shortName", description="Challenge short name (parsed).")
    # Reason if the link is broken (e.g., "CHALLENGE_DELETED")
    broken_reason: str | None = Field(None, alias="broken", description="Reason if the challenge link is broken.")
    # Flag derived from broken_reason
    is_broken: bool = Field(False, description="True if the challenge link is broken.")
    # Simplified status category based on broken_reason
    broken_status: Literal["task_deleted", "challenge_deleted", "unsubscribed", "challenge_closed", "unknown"] | None = Field(None, description="Categorized reason for breakage.")


    @field_validator("short_name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> str | None:
        """Parse short_name, replace emoji, strip."""
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value).strip()
        return None


    @model_validator(mode="before")
    @classmethod
    def process_broken_status(cls, data: Any) -> dict[str, Any]:
        """Sets is_broken and broken_status based on the raw 'broken' field."""
        if not isinstance(data, dict):
            return data if isinstance(data, dict) else {}

        values = data.copy()
        broken_raw = values.get("broken") # Alias handles getting data['broken']
        is_broken_flag = bool(broken_raw)
        broken_status_val = None

        if is_broken_flag and isinstance(broken_raw, str):
            reason = broken_raw.upper().strip()
            # Map known reasons to standardized statuses
            if reason in ("TASK_DELETED", "CHALLENGE_TASK_NOT_FOUND"):
                broken_status_val = "task_deleted"
            elif reason == "CHALLENGE_DELETED":
                broken_status_val = "challenge_deleted"
            elif reason == "UNSUBSCRIBED":
                broken_status_val = "unsubscribed"
            elif reason == "CHALLENGE_CLOSED":
                broken_status_val = "challenge_closed"
            else:
                broken_status_val = "unknown"
                log.debug(f"Unknown task challenge 'broken' reason encountered: {broken_raw}")

        # Add derived fields to the data dict *before* Pydantic validates them
        values["is_broken"] = is_broken_flag
        values["broken_status"] = broken_status_val
        return values


    def __repr__(self) -> str:
        status = f", BROKEN='{self.broken_status}' ({self.broken_reason})" if self.is_broken else ""
        name = f", name='{self.short_name}'" if self.short_name else ""
        chid = self.challenge_id[:8] if self.challenge_id else "NoChalID"
        return f"ChallengeLinkData(challenge_id={chid}{name}{status})"


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: BASE TASK MODEL


# KLASS: Task
class Task(BaseModel):
    """Base model representing common attributes of a Habitica Task."""

    # Allow extra fields from API (_v, userId sometimes etc.) but ignore them
    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    # --- Core Attributes ---
    id: str = Field(..., alias="_id", description="Unique task ID.")
    text: str = Field("", description="Main text content of the task (parsed emoji).")
    notes: str = Field("", description="Additional notes/description (parsed emoji).")
    task_type: Literal["habit", "daily", "todo", "reward"] = Field(..., alias="type", description="Type of the task.") # Type is required
    # API provides list of tag IDs
    tags_id: list[str] = Field(default_factory=list, alias="tags", description="List of associated tag UUIDs.")

    # --- Value & Difficulty ---
    value: float = Field(0.0, description="Task value (influences gold/exp/damage).")
    priority: float = Field(1.0, description="Task priority (0.1 Trivial to 2.0 Hard).") # Habitica values: Trivial(.1), Easy(1), Medium(1.5), Hard(2)
    attribute: Literal["str", "int", "con", "per"] | None = Field("str", description="Associated attribute for stat gains (can be null).") # Null allowed? Default to STR

    # --- Timestamps & Metadata ---
    created_at: datetime | None = Field(None, alias="createdAt", description="Timestamp created (UTC).")
    updated_at: datetime | None = Field(None, alias="updatedAt", description="Timestamp last updated (UTC).")
    # reminders: list[dict[str, Any]] = Field(default_factory=list, description="List of reminder objects.") # Less commonly used, ignoring for simplicity? Add back if needed.
    challenge: ChallengeLinkData | None = Field(None, description="Challenge linkage information, if any.")
    alias: str | None = Field(None, description="User-defined task alias (slug).") # Sometimes present

    # --- Calculated/Externally Populated Fields ---
    # Position relative to other tasks of same type within a TaskList
    position: int | None = Field(None, exclude=True, description="Calculated display position.")
    # Overall status string for display (e.g., 'due', 'complete', 'neutral')
    calculated_status: str = Field("unknown", description="Calculated display status string.")
    # Cached rich text versions
    _styled_text: Text | None = PrivateAttr(default=None)
    _styled_notes: Text | None = PrivateAttr(default=None)
    # Cached tag names, populated by TaskList.process_task_statuses
    _tag_names: list[str] = PrivateAttr(default_factory=list)
    _task_list_ref: TaskList | None = PrivateAttr(default=None) # Optional weakref back to parent list?


    # --- Validators ---

    @model_validator(mode="before")
    @classmethod
    def prepare_data(cls, data: Any) -> dict[str, Any]:
        """Prepare raw data: Map _id."""
        if not isinstance(data, dict):
            return data # Let Pydantic handle type error

        values = data.copy()
        # Map _id -> id
        if "_id" in values and "id" not in values:
            values["id"] = values["_id"]

        # Ensure 'type' exists
        if "type" not in values:
            # Let validation fail, or assign a default? Failing is safer.
             pass # Pydantic will require 'type' due to Literal[...] hint


        # Convert priority from API values (1, 1.5, 2, 0.1) to internal floats if needed
        # Keep as float, but maybe clamp/validate here?
        # prio = values.get("priority", 1.0)
        # values["priority"] = float(prio) if prio is not None else 1.0

        return values

    # Ensure ID exists after potential mapping
    @field_validator("id", mode="after")
    @classmethod
    def check_id(cls, v: str) -> str:
         if not v or not isinstance(v, str):
             raise ValueError("Task ID (_id) is required and must be a string.")
         return v

    @field_validator("text", "notes", "alias", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any, info: ValidationInfo) -> str | None:
        """Parse text fields, replace emoji, strip."""
        is_optional = info.field_name == 'alias' # Example if alias is the only optional one
        default = "" if not is_optional else None

        if isinstance(value, str):
            parsed = emoji_data_python.replace_colons(value).strip()
            return parsed if parsed else default
        # Return default (empty str or None) for non-string/None input
        return default


    # Consolidate datetime parsing using helper
    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_utc(cls, value: Any) -> datetime | None:
        """Parses various timestamp formats into UTC datetime."""
        handler = DateTimeHandler(timestamp=value)
        if value is not None and handler.utc_datetime is None:
            log.warning(f"Could not parse task timestamp field: {value!r}")
        return handler.utc_datetime


    @field_validator("value", "priority", mode="before")
    @classmethod
    def ensure_float(cls, value: Any, info: ValidationInfo) -> float:
        """Ensure value/priority are floats."""
        default = 0.0 if info.field_name == 'value' else 1.0
        try:
            # Explicitly handle None case
            if value is None:
                 return default
            return float(value)
        except (ValueError, TypeError):
            log.debug(f"Could not parse {info.field_name} float: {value!r}. Using default {default}.")
            return default


    @field_validator("attribute", mode="before")
    @classmethod
    def validate_attribute(cls, value: Any) -> str | None:
         """Validate attribute string."""
         allowed = {"str", "int", "con", "per"}
         if value in allowed:
              return value
         # Allow null/None or default? API might send empty string sometimes.
         if value is None or value == "":
             return None # Treat null/empty as None internally
         log.warning(f"Invalid attribute value '{value}'. Setting to None.")
         return None # Return None for invalid values


    # --- Computed Fields & Properties for Display/Export ---

    @computed_field(repr=False) # Exclude from default __repr__
    @property
    def styled_text(self) -> Text:
        """Returns the task text rendered as Rich Text (handles Markdown). Caches result."""
        if self._styled_text is None:
            self._styled_text = md_renderer.markdown_to_rich_text(self.text or "")
        return self._styled_text


    @computed_field(repr=False)
    @property
    def styled_notes(self) -> Text:
        """Returns the task notes rendered as Rich Text (handles Markdown). Caches result."""
        if self._styled_notes is None:
            self._styled_notes = md_renderer.markdown_to_rich_text(self.notes or "")
        return self._styled_notes


    @computed_field
    @property
    def tag_names(self) -> list[str]:
        """Returns the cached list of resolved tag names."""
        # If you need dynamic lookup, modify set_tag_names to use TaskList ref
        return self._tag_names

    # --- Methods ---
    def set_tag_names_from_provider(self, tags_provider: TagList | None) -> None:
        """Resolves tag IDs to tag names using the provided TagList. Populates _tag_names."""
        resolved_names = []
        if tags_provider and hasattr(tags_provider, 'get_by_id'):
            for tag_id in self.tags_id:
                tag = tags_provider.get_by_id(tag_id)
                if tag and hasattr(tag, 'name'):
                    resolved_names.append(tag.name)
                else:
                    log.debug(f"Tag ID '{tag_id}' not found in provider for task {self.id}.")
                    resolved_names.append(f"Unknown:{tag_id[:6]}") # Placeholder for unknown
        else:
            # If no provider, just show IDs? Or empty list?
            resolved_names = [f"ID:{tid[:6]}" for tid in self.tags_id]

        self._tag_names = resolved_names

    @staticmethod # Static as it doesn't depend on task instance state besides checklist
    def calculate_checklist_progress(checklist: list[ChecklistItem]) -> float:
        """Calculates proportion (0.0-1.0) of checklist items completed."""
        if not checklist or not isinstance(checklist, list):
            return 1.0 # Treat no checklist as "complete" for damage mitigation

        completed_count = sum(1 for item in checklist if isinstance(item, ChecklistItem) and item.completed)
        total_count = len(checklist)
        return completed_count / total_count if total_count > 0 else 1.0

    def calculate_value_color(self) -> str:
         """Calculate the color style based on task value (e.g., for display)."""
         value = self.value
         if value <= -20: return "red"       # Very detrimental
         elif value <= -10: return "orange"    # Moderately detrimental
         elif value < 0: return "yellow"       # Slightly detrimental
         elif value == 0: return "grey"       # Neutral
         elif value < 5: return "bright_blue" # Slightly beneficial
         elif value <= 10: return "blue"      # Moderately beneficial
         else: return "green"    # Highly beneficial

    # --- Representation ---
    def __repr__(self) -> str:
        """Concise developer representation."""
        text_preview = self.text[:25].replace("\n", " ") + ("..." if len(self.text) > 25 else "")
        prio = f"P{self.priority}" if self.priority != 1.0 else ""
        attr = f"A:{self.attribute or '?'}"
        status = f"S:{self.calculated_status}"
        return f"{self.__class__.__name__}(id='{self.id[:8]}', {prio} {attr} {status} text='{text_preview}')"

    def __str__(self) -> str:
         """User-friendly representation (text)."""
         return self.text


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: TASK SUBCLASSES


# KLASS: Habit
class Habit(Task):
    """Represents a Habit task with up/down counters and frequency."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    task_type: Literal["habit"] = Field("habit", frozen=True) # Type is fixed

    up: bool = Field(True, description="Does this habit have a positive scoring direction (+)?")
    down: bool = Field(True, description="Does this habit have a negative scoring direction (-)?")
    counter_up: int = Field(0, alias="counterUp", description="Current positive counter.")
    counter_down: int = Field(0, alias="counterDown", description="Current negative counter.")
    frequency: str = Field("daily", description="Frequency for counter resets ('daily', 'weekly', 'monthly').") # Seems less used now? Keep for info.
    # history: list[dict[str, Any]] = Field(default_factory=list) # Large, exclude by default?

    @field_validator("counter_up", "counter_down", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensures counters are integers, defaulting to 0."""
        if value is None: return 0
        try:
            return int(float(value)) # Allow float input like 1.0
        except (ValueError, TypeError):
            return 0

    def update_calculated_status(self):
         """Sets the status based on directionality."""
         if self.up and self.down: self.calculated_status = "good_bad"
         elif self.up: self.calculated_status = "good"
         elif self.down: self.calculated_status = "bad"
         else: self.calculated_status = "neutral"


    def __repr__(self) -> str:
        """Concise representation for Habit."""
        up_str = f"⬆️{self.counter_up}" if self.up else ""
        down_str = f"⬇️{self.counter_down}" if self.down else ""
        counters = f"{up_str} / {down_str}" if self.up and self.down else (up_str or down_str or "No Score")
        text_preview = self.text[:20].replace("\n", " ") + ("..." if len(self.text) > 20 else "")
        prio = f"P{self.priority}" if self.priority != 1.0 else ""
        return f"Habit(id='{self.id[:8]}' {prio} ctr='{counters}', text='{text_preview}')"


# KLASS: Daily
class Daily(Task):
    """Represents a Daily task with schedule, completion status, streak, and checklist."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    task_type: Literal["daily"] = Field("daily", frozen=True)

    # --- Status ---
    completed: bool = Field(False, description="Whether the Daily is completed for the current period.")
    is_due: bool = Field(False, alias="isDue", description="Is the Daily currently due according to its schedule?")
    streak: int = Field(0, description="Current completion streak.")
    yesterday_completed: bool = Field(False, alias="yesterDaily", description="Was completed yesterday?")

    # --- Checklist ---
    collapse_checklist: bool = Field(False, alias="collapseChecklist", description="UI hint to collapse checklist.")
    checklist: list[ChecklistItem] = Field(default_factory=list)

    # --- Scheduling Fields ---
    frequency: Literal["daily", "weekly", "monthly", "yearly"] = Field("weekly", description="Repeat frequency.")
    every_x: int = Field(1, alias="everyX", description="Repeat interval (e.g., every 'X' weeks).")
    # Repeat on specific days (M, T, W, Th, F, Sa, Su)
    repeat: dict[Literal["m", "t", "w", "th", "f", "s", "su"], bool] = Field(default_factory=dict)
    # For monthly repeats
    days_of_month: list[int] = Field(default_factory=list, alias="daysOfMonth", description="Specific days of month to repeat (e.g., [1, 15]).")
    weeks_of_month: list[int] = Field(default_factory=list, alias="weeksOfMonth", description="Specific weeks of month to repeat (e.g., [0, 2] for 1st, 3rd week).")

    start_date: datetime | None = Field(None, alias="startDate", description="Date the daily started affecting schedule (UTC).")
    # next_due: list[datetime] = Field(default_factory=list) # Often large/complex, calculate if needed? Skip for now.
    # history: list[dict[str, Any]] = Field(default_factory=list) # Exclude large history

    # --- Internal Damage Calculation Cache ---
    _calculated_user_damage: float | None = PrivateAttr(default=None)
    _calculated_party_damage: float | None = PrivateAttr(default=None)

    # --- Validators ---
    @field_validator("streak", "every_x", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensures streak/every_x are non-negative integers."""
        default = 1 if value is None else 0 # Default every_x=1, streak=0
        try:
             val = int(float(value))
             return max(0, val) # Ensure non-negative
        except (ValueError, TypeError):
             return default

    @field_validator("start_date", mode="before")
    @classmethod
    def parse_start_date_utc(cls, value: Any) -> datetime | None:
        """Parse start_date into UTC datetime."""
        handler = DateTimeHandler(timestamp=value)
        return handler.utc_datetime


    # --- Calculated Status & Damage ---

    def update_calculated_status(self):
         """Sets the calculated status based on due and completed."""
         if self.completed:
             self.calculated_status = "complete"
         elif self.is_due:
             self.calculated_status = "due"
         else:
             self.calculated_status = "not_due"

    @computed_field(description="Potential damage to user if missed.")
    @property
    def user_damage(self) -> float | None:
        """Returns the calculated user damage (requires external calculation)."""
        return self._calculated_user_damage

    @computed_field(description="Potential damage to party/boss if missed.")
    @property
    def party_damage(self) -> float | None:
        """Returns the calculated party damage (requires external calculation)."""
        return self._calculated_party_damage

    def calculate_and_store_damage(self, user: User, static_content: StaticContentManager | None = None) -> None:
        """
        Calculates potential damage if this daily is missed and stores it internally.
        Requires the User object for stats and context (sleep, quest).
        Optionally uses StaticContentManager for quest boss details.
        """
        # Reset stored damage
        self._calculated_user_damage = None
        self._calculated_party_damage = None

        # --- Conditions for No Damage ---
        if not self.is_due: return # Not due, no damage
        if self.completed: return # Completed, no damage
        if user.is_sleeping: return # Sleeping, no damage
        # Stealth check (User needs an `effective_stealth` property ideally)
        stealth = user.stats.buffs.stealth # Access stealth buff directly
        if stealth > 0 :
             log.debug(f"Daily {self.id}: No damage due to user stealth ({stealth})")
             return # Stealth negates damage

        try:
            # --- Calculate Base Delta ---
            value = self.value # Negative value means more damage
            priority_multiplier = self.priority # 0.1, 1, 1.5, 2

            # Habitica formula component: pow(0.9747, value)
            # Clamping value might be needed if formula behaves unexpectedly at extremes
            # clamped_value = max(-47.27, min(self.value, 21.27)) # Official clamp? Research needed. Use raw for now.
            base_delta = math.pow(0.9747, value) # Larger for negative values

            # Apply checklist mitigation (0.0 to 1.0, where 1.0 means full damage)
            checklist_progress = self.calculate_checklist_progress(self.checklist)
            checklist_mitigation = 1.0 - checklist_progress
            effective_delta = base_delta * checklist_mitigation

            # --- Calculate User HP Damage ---
            # Mitigation from effective CON (Base + Buffs + Train + Level + Gear)
            # User model should have an 'effective_stats' property/method
            eff_stats = user.calculate_effective_stats() # Assumes gear data loaded/passed to user calc
            effective_con = eff_stats.get("con", 0.0)
            con_mitigation = max(0.1, 1.0 - (effective_con / 250.0))

            # Combine factors for user HP damage
            hp_damage = effective_delta * con_mitigation * priority_multiplier * 2.0
            # Round to 1 decimal place, ensure non-negative
            self._calculated_user_damage = max(0.0, round(hp_damage, 1))

            # --- Calculate Party Damage (Boss Quests Only) ---
            # Need user's quest status and boss details from static content
            party_quest_info = getattr(user, 'party', {}).get('quest')
            quest_active = isinstance(party_quest_info, dict) and party_quest_info.get('active', False)

            if quest_active:
                quest_key = party_quest_info.get('key')
                static_quest = None
                if quest_key and static_content:
                    # TODO: This needs async resolution if main processing is sync
                    # static_quest = await static_content.get_quest(quest_key) # Requires async context
                    # Placeholder sync lookup (adjust based on actual implementation)
                    log.warning("Sync lookup for static quest in calculate_damage - refactor if needed.")
                    # Assuming content_manager has a synchronous cache access method or data is pre-loaded
                    if hasattr(static_content, "_content") and static_content._content:
                        static_quest = static_content._content.quests.get(quest_key)


                if static_quest and getattr(static_quest, 'is_boss_quest', False) and getattr(static_quest, 'boss', None):
                     boss_strength = getattr(static_quest.boss, 'strength', 0.0)
                     if boss_strength > 0:
                          # Priority multiplier applied differently for party damage? Assume same for now.
                          party_delta = effective_delta * priority_multiplier
                          party_damage = party_delta * boss_strength
                          # Round to 1 decimal, ensure non-negative
                          self._calculated_party_damage = max(0.0, round(party_damage, 1))


            log.debug(f"Daily {self.id}: UserDmg={self._calculated_user_damage}, PartyDmg={self._calculated_party_damage} (Value:{value:.1f}, Prio:{priority_multiplier:.1f}, Chk:{checklist_progress:.2f}, EffCON:{effective_con:.1f})")


        except Exception as e:
            log.exception(f"Error calculating damage for daily {self.id}: {e}")
            # Leave stored damage as None on error


    # --- Representation ---
    def __repr__(self) -> str:
        """Concise representation for Daily."""
        status = self.calculated_status.upper()
        streak_str = f" (Strk:{self.streak})" if self.streak > 0 else ""
        dmg_str = f" (DmgU:{self.user_damage or 0:.1f}|P:{self.party_damage or 0:.1f})" if self.is_due and not self.completed else ""
        checklist_str = f" Chk:{len(self.checklist)}" if self.checklist else ""
        text_preview = self.text[:15].replace("\n", " ") + ("..." if len(self.text) > 15 else "")
        prio = f"P{self.priority}" if self.priority != 1.0 else ""

        return f"Daily(id='{self.id[:8]}' {prio} S:{status}{streak_str}{checklist_str}{dmg_str}, text='{text_preview}')"


# KLASS: Todo
class Todo(Task):
    """Represents a To-Do task with completion status, due date, and checklist."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    task_type: Literal["todo"] = Field("todo", frozen=True)

    completed: bool = Field(False, description="Whether the To-Do is marked complete.")
    completed_date: datetime | None = Field(None, alias="dateCompleted", description="Timestamp completed (UTC).")
    due_date: datetime | None = Field(None, alias="date", description="Due date timestamp (UTC).") # API uses 'date'

    collapse_checklist: bool = Field(False, alias="collapseChecklist", description="UI hint to collapse checklist.")
    checklist: list[ChecklistItem] = Field(default_factory=list, description="Sub-items for the To-Do.")


    @field_validator("completed_date", "due_date", mode="before")
    @classmethod
    def parse_todo_datetime_utc(cls, value: Any) -> datetime | None:
        """Parse date fields into UTC datetime objects."""
        # Ensure we handle empty strings, common from API if date not set
        if value == "": return None
        handler = DateTimeHandler(timestamp=value)
        return handler.utc_datetime


    @property
    def is_past_due(self) -> bool:
        """Checks if the To-Do is past its due date and not completed."""
        if self.completed or not self.due_date:
            return False
        # Ensure comparison is timezone-aware
        now_utc = datetime.now(timezone.utc)
        return self.due_date < now_utc


    def update_calculated_status(self):
        """Sets the calculated status based on completion and due date."""
        if self.completed:
             self.calculated_status = "complete"
        elif not self.due_date:
             self.calculated_status = "no_due_date"
        elif self.is_past_due:
             self.calculated_status = "past_due"
        else:
             self.calculated_status = "due" # Has due date, not completed, not past due


    def calculate_progress(self) -> float:
        """Calculates overall progress (0.0-1.0) based on checklist or completion."""
        if self.completed:
            return 1.0
        # If not complete, progress depends only on checklist
        return self.calculate_checklist_progress(self.checklist)


    def __repr__(self) -> str:
        """Concise representation for Todo."""
        status = self.calculated_status.upper()
        due_str = f", due={self.due_date.strftime('%y-%m-%d')}" if self.due_date else ""
        checklist_str = f" Chk:{len(self.checklist)}" if self.checklist else ""
        progress = self.calculate_progress()
        prog_str = f" Prg:{progress:.0%}" if progress < 1.0 and self.checklist else ""
        text_preview = self.text[:15].replace("\n", " ") + ("..." if len(self.text) > 15 else "")
        prio = f"P{self.priority}" if self.priority != 1.0 else ""

        return f"Todo(id='{self.id[:8]}' {prio} S:{status}{due_str}{checklist_str}{prog_str}, text='{text_preview}')"


# KLASS: Reward
class Reward(Task):
    """Represents a Reward task that users can purchase with gold."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    task_type: Literal["reward"] = Field("reward", frozen=True)

    # Rewards use 'value' for gold cost
    value: float = Field(..., description="Gold cost of the reward.") # Cost is required for reward

    def update_calculated_status(self):
         """Sets the calculated status for Rewards."""
         self.calculated_status = "available"


    def __repr__(self) -> str:
        """Concise representation for Reward."""
        cost_str = f"(Cost: {self.value:.1f} GP)" # Show cost
        text_preview = self.text[:25].replace("\n", " ") + ("..." if len(self.text) > 25 else "")
        return f"Reward(id='{self.id[:8]}' {cost_str} text='{text_preview}')"


# Type alias for tasks
AnyTask = Habit | Daily | Todo | Reward

# ──────────────────────────────────────────────────────────────────────────────


# SECTION: TASK LIST CONTAINER / MANAGER


# KLASS: TaskList
class TaskList:
    """Container for managing a list of Task objects, handling validation, processing, and filtering."""

    # This is NOT a Pydantic model itself, but manages a list of Pydantic Task models.
    # It encapsulates the logic of creating and processing the list.

    def __init__(self, tasks: list[AnyTask]):
        """Initializes the TaskList with a list of *already validated* Task objects."""
        if not isinstance(tasks, list):
            raise TypeError("TaskList requires a list of Task objects.")
        # Store the validated tasks
        self.tasks: list[AnyTask] = tasks
        # Assign relative positions upon initialization
        self._assign_relative_positions()

    def _assign_relative_positions(self) -> None:
        """Assigns a 'position' attribute relative to other tasks of the same type."""
        type_position_counters: dict[str, int] = defaultdict(int)
        for task in self.tasks:
            type_key = task.task_type # Should always have a type by now
            task.position = type_position_counters[type_key]
            type_position_counters[type_key] += 1

    # --- Factory Method: Create from Raw API Data ---
    @classmethod
    def from_api_data(cls, raw_task_list: list[dict[str, Any]]) -> TaskList:
        """Validates raw API task data and creates the appropriate Task subclass instances."""
        if not isinstance(raw_task_list, list):
            log.error(f"Invalid input for TaskList.from_api_data: Expected list, got {type(raw_task_list)}.")
            return cls([]) # Return empty TaskList

        processed_tasks: list[AnyTask] = []
        task_map: dict[Literal["habit", "daily", "todo", "reward"], type[Task]] = {
            "habit": Habit,
            "daily": Daily,
            "todo": Todo,
            "reward": Reward,
        }

        for index, task_data in enumerate(raw_task_list):
            if not isinstance(task_data, dict):
                 log.warning(f"Skipping non-dict item at index {index} in raw task data.")
                 continue

            task_type = task_data.get("type")
            model_class = task_map.get(task_type) # type: ignore[arg-type] # Literal matches keys

            if not model_class:
                 task_id = task_data.get("_id", f"index_{index}")
                 log.warning(f"Unknown or missing task type '{task_type}' for task ID '{task_id}'. Skipping.")
                 # Or potentially validate as Base 'Task' if that's desired? No, skip.
                 continue

            try:
                 # Validate the raw data against the determined subclass model
                 task_instance = model_class.model_validate(task_data)
                 processed_tasks.append(task_instance)
            except ValidationError as e:
                task_id = task_data.get("_id", f"index_{index}")
                log.error(f"Validation failed for task '{task_id}' (Type: {task_type}): {e}")
            except Exception as e:
                 task_id = task_data.get("_id", f"index_{index}")
                 log.exception(f"Unexpected error processing task '{task_id}' (Type: {task_type}): {e}")


        log.info(f"Validated {len(processed_tasks)} tasks from raw API data.")
        # Instantiate TaskList with the validated tasks
        return cls(processed_tasks)


    # --- Processing Method ---
    def process_task_statuses_and_damage(
            self,
            user: User | None = None,
            tags_provider: TagList | None = None,
            content_manager: StaticContentManager | None = None, # Needed for Daily Damage calc
        ) -> None:
        """Processes all tasks: updates calculated status, resolves tag names, calculates daily damage."""
        log.info(f"Processing statuses and damage for {len(self.tasks)} tasks...")
        if not user:
             log.warning("User object not provided to process_task_statuses. Cannot calculate Daily damage.")

        processed_count = 0
        for task in self.tasks:
            try:
                # 1. Resolve Tag Names
                task.set_tag_names_from_provider(tags_provider)

                # 2. Update Calculated Status (delegated to subclass method)
                if hasattr(task, 'update_calculated_status'):
                    task.update_calculated_status()

                # 3. Calculate and Store Damage (for Dailies, requires User)
                if isinstance(task, Daily) and user:
                     task.calculate_and_store_damage(user, content_manager) # Pass context needed

                processed_count += 1
            except Exception as e:
                log.exception(f"Error processing task {task.id}: {e}")

        log.success(f"Finished processing {processed_count} tasks.")


    # --- Standard Container Methods ---
    def __len__(self) -> int: return len(self.tasks)
    def __iter__(self) -> Iterator[AnyTask]: return iter(self.tasks)

    def __getitem__(self, index: int | slice) -> AnyTask | list[AnyTask]:
        """Get task(s) by index or slice."""
        if isinstance(index, int):
            if not 0 <= index < len(self.tasks):
                 raise IndexError("TaskList index out of range")
        return self.tasks[index]

    def __contains__(self, item: AnyTask | str) -> bool:
        """Check if a task (by instance or ID) is in the list."""
        if isinstance(item, str): # Check by ID
            return any(task.id == item for task in self.tasks)
        elif isinstance(item, Task): # Check by instance
            return item in self.tasks
        return False

    def __repr__(self) -> str:
        """Detailed representation showing counts per type."""
        counts = defaultdict(int)
        for task in self.tasks:
            counts[task.task_type or "unknown"] += 1
        count_str = ", ".join(f"{t}:{c}" for t, c in sorted(counts.items()))
        return f"TaskList(count={len(self.tasks)}, types=[{count_str}])"


    # --- Access and Filtering ---
    # Methods now return new TaskList instances for immutability of results

    def get_by_id(self, task_id: str) -> AnyTask | None:
        """Finds a task by its unique ID."""
        return next((task for task in self.tasks if task.id == task_id), None)


    def filter(self, criteria_func: callable[[AnyTask], bool]) -> TaskList:
        """Generic filter method using a criteria function. Returns new TaskList."""
        filtered_tasks = [task for task in self.tasks if criteria_func(task)]
        return TaskList(filtered_tasks)

    def filter_by_type(self, task_type: Literal["habit", "daily", "todo", "reward"]) -> TaskList:
        """Returns a new TaskList containing only tasks of the specified type."""
        return self.filter(lambda task: task.task_type == task_type)

    def filter_by_status(self, status: str) -> TaskList:
        """Returns a new TaskList containing only tasks with the specified calculated status."""
        return self.filter(lambda task: task.calculated_status == status)

    def filter_by_tag_id(self, tag_id: str) -> TaskList:
        """Returns a new TaskList containing tasks associated with the given tag ID."""
        return self.filter(lambda task: tag_id in task.tags_id)

    def filter_by_tag_name(self, tag_name: str, case_sensitive: bool = False) -> TaskList:
        """Returns a new TaskList containing tasks associated with the given tag name."""
        if not case_sensitive:
            tag_name_lower = tag_name.lower()
            criteria = lambda task: any(tag_name_lower in tn.lower() for tn in task.tag_names)
        else:
            criteria = lambda task: tag_name in task.tag_names
        return self.filter(criteria)

    def filter_by_text(self, text_part: str, case_sensitive: bool = False) -> TaskList:
        """Returns a new TaskList containing tasks whose text includes the substring."""
        if not case_sensitive:
             text_part_lower = text_part.lower()
             criteria = lambda task: text_part_lower in task.text.lower()
        else:
             criteria = lambda task: text_part in task.text
        return self.filter(criteria)

    def get_habits(self) -> TaskList: return self.filter_by_type("habit")
    def get_dailies(self) -> TaskList: return self.filter_by_type("daily")
    def get_todos(self) -> TaskList: return self.filter_by_type("todo")
    def get_rewards(self) -> TaskList: return self.filter_by_type("reward")

    # --- Serialization ---
    def to_dicts(self) -> list[dict[str, Any]]:
         """Converts all tasks in the list to dictionaries using model_dump."""
         # Use model_dump(mode='json') to ensure datetimes etc. are serialized correctly
         return [task.model_dump(mode='json') for task in self.tasks]

    def save_to_json(self, filename: str, folder: Path) -> bool:
         """Saves the list of task dictionaries to a JSON file."""
         data_to_save = self.to_dicts()
         log.info(f"Saving {len(data_to_save)} processed tasks to {folder / filename}")
         return save_json(data_to_save, filename, folder=folder)

# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MAIN EXECUTION (Example/Test)

async def main():
    """Demo function to retrieve, process, and save tasks."""
    log.info("--- Task Models Demo ---")
    tasks_list_instance: TaskList | None = None
    try:
        cache_dir = HABITICA_DATA_PATH / "tasks"
        cache_dir.mkdir(exist_ok=True, parents=True)
        raw_path = cache_dir / "tasks_raw.json"
        processed_path = cache_dir / "tasks_processed.json"

        # 1. Fetch raw data
        log.info("Fetching tasks from API...")
        api = HabiticaClient() # Assumes configured
        raw_data = await api.get_tasks()
        log.success(f"Fetched {len(raw_data)} raw task items.")
        save_json(raw_data, raw_path.name, folder=raw_path.parent) # Save raw data

        # 2. Validate and create TaskList
        log.info("Validating raw data into TaskList...")
        tasks_list_instance = TaskList.from_api_data(raw_data)
        log.success(f"Created TaskList: {tasks_list_instance}")

        # 3. Process Tasks (Requires User, TagList, ContentManager - Mocked for demo if needed)
        log.info("Processing task statuses (requires User/Tags/Content)...")
        # --- MOCKING DEPENDENCIES FOR DEMO ---
        # In a real app, these would come from DataManager
        mock_user = None # Needs a User instance ideally
        mock_tags = None # Needs a TagList instance ideally
        mock_content = None # Needs a StaticContentManager instance ideally
        log.warning("Using MOCK dependencies for task processing demo.")
        # --- END MOCKING ---

        tasks_list_instance.process_task_statuses_and_damage(
             user=mock_user,
             tags_provider=mock_tags,
             content_manager=mock_content,
         )
        log.success("Task processing complete.")

        # 4. Example Access/Filtering
        dailies = tasks_list_instance.get_dailies()
        print(f"  - Number of Dailies: {len(dailies)}")
        if dailies:
             first_daily = dailies[0]
             print(f"  - First Daily: {first_daily}")
             # Access calculated damage (will be None if User was missing)
             print(f"    -> Calculated User Damage: {getattr(first_daily, 'user_damage', 'N/A')}")


        # 5. Save processed data
        log.info(f"Saving processed tasks to {processed_path}...")
        if tasks_list_instance.save_to_json(processed_path.name, folder=processed_path.parent):
             log.success("Processed tasks saved.")
        else:
             log.error("Failed to save processed tasks.")

    except ConnectionError as e:
         log.error(f"API Connection error: {e}")
    except ValidationError as e:
         log.error(f"Pydantic Validation Error: {e}")
    except Exception as e:
         log.exception(f"An unexpected error occurred in the task demo: {e}")

    return tasks_list_instance

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(main())

# ──────────────────────────────────────────────────────────────────────────────

```

---

## File: `pixabit/models/user.py`

**Suggestions:**

1.  **Pydantic V2 & Typing:** Convert all models.
2.  **Nested Models:** Clean up nested models (`UserProfile`, `UserAuth`, `UserPreferences`, `Buffs`, `Training`, `EquippedGear`, `UserStats`, `UserItems`, `UserAchievements`, `UserPartyInfo`, `UserInboxInfo`). Use aliases effectively. Define defaults in `Field`.
3.  **Stat Calculation:**
    - Remove the separate `UserStatsCalculations` class. Move the calculation logic into methods within `User` or `UserStats`.
    - `User.calculate_effective_stats` method is appropriate. It should _take_ the `gear_data` (preferably the `dict[str, Gear]` from `StaticContentManager`) as an argument.
    - This method calculates and _stores_ the result in a private attribute or a dedicated `calculated_stats: dict` field within the `User` model (marked with `exclude=True` if it shouldn't be dumped by default unless requested).
    - Properties like `effective_stats`, `max_hp`, `max_mp` on the `User` model can then return the stored calculated values.
4.  **Gear Bonus:** Ensure `EquippedGear.calculate_total_bonus` uses the correct user class and accesses the static gear data properly (passed as an argument).
5.  **Model Structure:** Simplify `UserAuth` and `UserStats` using `model_validator(mode='before')` or by relying on Pydantic's nested model parsing where possible, instead of manual extraction in validators.
6.  **Inbox Messages:** Validate `inbox.messages` using `MessageList` (passing context might be complex here, maybe inbox messages don't need `sent_by_me`?). The validator currently just transforms dict -> list; Pydantic can handle nested `MessageList` directly if the `inbox` field is typed correctly (`inbox: UserInboxInfo | None = None`).
7.  **Factory Method:** Use `User.create_from_raw_data` to centralize instantiation and potential future pre-processing. `calculate_effective_stats` should be called _after_ instantiation.
8.  **Serialization:** Rely on `model_dump` and `model_dump_json`. Provide options to include/exclude calculated fields if needed.

_(Self-correction: Initially thought about making `UserStats` handle all calcs, but `User` needs `UserItems` and `UserStats` for the full calculation, so the main `User.calculate_effective_stats` method taking `gear_data` is better.)_

**Refactored Code:**

```python
# pixabit/models/user.py

# ─── Title ────────────────────────────────────────────────────────────────────
#            Habitica User Model and Subcomponents
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for the Habitica User object and its complex nested
structures like profile, auth, preferences, stats, items, achievements, etc.
Includes methods for calculating derived stats like effective attributes and max HP/MP.
"""

# SECTION: IMPORTS
from __future__ import annotations  # Allow forward references

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal # Use standard types

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
    PrivateAttr, # For internal storage
    computed_field # For calculated fields in dumps
)

# External Libs
import emoji_data_python

# Local Imports
try:
    from pixabit.api.client import HabiticaClient
    from pixabit.config import HABITICA_DATA_PATH, USER_ID # If USER_ID needed as fallback
    from pixabit.helpers._json import save_json, save_pydantic_model, load_pydantic_model
    from pixabit.helpers._logger import log
    from pixabit.helpers.DateTimeHandler import DateTimeHandler
    # Dependent models (use TYPE_CHECKING if circularity is a risk)
    from .game_content import Gear, StaticContentManager # Need Gear model + manager for stats
    from .message import Message, MessageList # For inbox
    from .party import QuestInfo # For user's view of party quest
    from .tag import Tag, TagList # For user tags
except ImportError:
     # Fallbacks
     log = logging.getLogger(__name__)
     log.addHandler(logging.NullHandler())
     USER_ID = "fallback_user_id"
     HABITICA_DATA_PATH = Path("./pixabit_cache")
     class HabiticaClient: async def get_user_data(self): return {}
     def save_json(d, p, **k): pass
     def save_pydantic_model(m, p, **k): pass
     def load_pydantic_model(cls, p, **k): return None
     class DateTimeHandler:
         def __init__(self, timestamp): self._ts = timestamp
         @property
         def utc_datetime(self): return None
     class Gear: pass
     class StaticContentManager: async def get_gear(self) -> dict: return {} # Mock
     class MessageList: pass
     class QuestInfo: pass
     class Tag: pass
     class TagList: tags: list = [] # Basic Mock
     log.warning("user.py: Could not import dependencies. Using fallbacks.")

# SECTION: USER SUBCOMPONENT MODELS


# KLASS: UserProfile
class UserProfile(BaseModel):
    """Represents user profile information like display name and blurb."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str = Field("", description="User's display name (parsed).")
    blurb: str | None = Field(None, description="User's profile description (parsed).") # Blurb can be absent

    @field_validator("name", "blurb", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any) -> str | None:
        """Parse text and replace emoji shortcodes, strips whitespace."""
        if isinstance(value, str):
             parsed = emoji_data_python.replace_colons(value).strip()
             return parsed # Return potentially empty string or None
        # Handle name default elsewhere if needed
        return None


# KLASS: UserAuthLocal (Nested under UserAuth)
class UserAuthLocal(BaseModel):
    """Nested local authentication details."""
    model_config = ConfigDict(extra="ignore")
    username: str | None = Field(None)
    # email: str | None = None # Ignore email for privacy unless needed

# KLASS: UserAuthTimestamps (Nested under UserAuth)
class UserAuthTimestamps(BaseModel):
    """Nested timestamp information for authentication."""
    model_config = ConfigDict(extra="ignore")
    created: datetime | None = None
    updated: datetime | None = None
    loggedin: datetime | None = None

    @field_validator("created", "updated", "loggedin", mode="before")
    @classmethod
    def parse_datetime_utc(cls, value: Any) -> datetime | None:
        """Parses timestamp using DateTimeHandler."""
        # Allow null values through
        if value is None: return None
        handler = DateTimeHandler(timestamp=value)
        if handler.utc_datetime is None and value is not None:
             log.warning(f"Could not parse auth timestamp: {value!r}")
        return handler.utc_datetime

# KLASS: UserAuth
class UserAuth(BaseModel):
    """Represents user authentication details (wrapping local and timestamps)."""
    model_config = ConfigDict(extra="ignore")

    local: UserAuthLocal | None = Field(default_factory=UserAuthLocal)
    timestamps: UserAuthTimestamps | None = Field(default_factory=UserAuthTimestamps)

    # Convenience properties for easier access
    @property
    def username(self) -> str | None: return self.local.username if self.local else None
    @property
    def created_at(self) -> datetime | None: return self.timestamps.created if self.timestamps else None
    @property
    def updated_at(self) -> datetime | None: return self.timestamps.updated if self.timestamps else None
    @property
    def logged_in_at(self) -> datetime | None: return self.timestamps.loggedin if self.timestamps else None


# KLASS: UserPreferences
class UserPreferences(BaseModel):
    """User-specific preferences and settings."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    sleep: bool = Field(False, description="Whether user is resting in the Inn.")
    day_start: int = Field(0, alias="dayStart", description="User's preferred day start hour (0–23).")
    timezone_offset: int | None = Field(None, alias="timezoneOffset", description="User's current timezone offset from UTC in minutes.")
    timezone_offset_at_last_cron: int | None = Field(None, alias="timezoneOffsetAtLastCron", description="User's timezone offset at the time of the last cron.")
    # Other preferences like: email, language, chatRevoked, background, costume, shirt etc. ignored by default

    @field_validator("day_start", mode="before")
    @classmethod
    def parse_day_start(cls, value: Any) -> int:
        """Validate and clamp day start hour."""
        try:
            ds = int(value)
            return max(0, min(23, ds)) # Clamp between 0 and 23
        except (ValueError, TypeError):
            log.debug(f"Invalid dayStart value '{value}'. Using default 0.")
            return 0


# KLASS: Buffs (Used within UserStats)
class Buffs(BaseModel):
    """Temporary stat increases/decreases from spells, food, etc."""
    model_config = ConfigDict(extra="allow", populate_by_name=True) # Allow extra buffs like seafoam

    # Use aliases for fields conflicting with built-ins/types
    con: float = Field(0.0) # Buffs can be floats (gear sets)
    int_: float = Field(0.0, alias="int")
    per: float = Field(0.0)
    str_: float = Field(0.0, alias="str")
    stealth: int = Field(0) # Stealth usually integer buff stacks

    @field_validator("con", "int_", "per", "str_", mode="before")
    @classmethod
    def ensure_float(cls, value: Any) -> float:
        try: return float(value)
        except (ValueError, TypeError): return 0.0

    @field_validator("stealth", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        try: return int(value)
        except (ValueError, TypeError): return 0


# KLASS: Training (Used within UserStats)
class Training(BaseModel):
    """Permanent stat increases from leveling/resets (can have fractions)."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True) # Ignore rev, assigned etc.

    con: float = Field(0.0)
    int_: float = Field(0.0, alias="int")
    per: float = Field(0.0)
    str_: float = Field(0.0, alias="str")

    @field_validator("con", "int_", "per", "str_", mode="before")
    @classmethod
    def ensure_float(cls, value: Any) -> float:
        try: return float(value)
        except (ValueError, TypeError): return 0.0


# KLASS: EquippedGear (Used within UserItems)
class EquippedGear(BaseModel):
    """Represents gear currently equipped by the user."""
    model_config = ConfigDict(extra="allow") # Allow other potential slots

    # Define known slots explicitly
    weapon: str | None = Field(None)
    armor: str | None = Field(None)
    head: str | None = Field(None)
    shield: str | None = Field(None) # Can be None if weapon is two-handed
    headAccessory: str | None = Field(None, alias="headAccessory")
    eyewear: str | None = Field(None)
    body: str | None = Field(None) # e.g., Robe
    back: str | None = Field(None) # e.g., Cape

    def get_equipped_item_keys(self) -> list[str]:
        """Returns a list of non-None gear keys currently equipped."""
        # Use model_dump to get values respecting aliases, exclude None
        return [
             val for val in self.model_dump(exclude_none=True).values()
             if isinstance(val, str)
        ]

    def calculate_total_bonus(
         self, user_class: str | None, gear_data: dict[str, Gear]
        ) -> dict[str, float]:
        """Calculates total stat bonuses from equipped gear, considering class match.

        Args:
             user_class: User's character class (e.g., 'warrior').
             gear_data: Dict mapping gear keys to validated Gear objects.

        Returns:
             Dictionary {'str': bonus, 'con': bonus, 'int': bonus, 'per': bonus}.
        """
        total_bonus = {"str": 0.0, "con": 0.0, "int": 0.0, "per": 0.0}
        stats_map_model_to_bonus = {"str_": "str", "con": "con", "int_": "int", "per": "per"} # Map Gear field to bonus key

        for gear_key in self.get_equipped_item_keys():
             item: Gear | None = gear_data.get(gear_key)
             if item and isinstance(item, Gear) and hasattr(item, 'stats'):
                 # Class bonus multiplier (1.5x if item class matches user class, or if item is classless)
                 # Habitica defines 'base' sometimes for general gear, check logic needed. Assume item.klass=None or 'special' don't get bonus.
                 is_class_match = (
                     item.klass is not None and
                     (item.klass == user_class or item.klass == 'base') # Define how 'base' gear works
                 )
                 bonus_multiplier = 1.5 if is_class_match else 1.0

                 # Add item stats to total, applying multiplier
                 for model_stat_field, bonus_key in stats_map_model_to_bonus.items():
                      stat_value = getattr(item.stats, model_stat_field, 0.0)
                      total_bonus[bonus_key] += stat_value * bonus_multiplier
             # else: log.debug(f"Gear key '{gear_key}' not found in provided gear_data.")

        return total_bonus

# KLASS: UserItems
class UserItems(BaseModel):
    """Holds user's inventory: gear, consumables, pets, mounts, etc."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    gear_equipped: EquippedGear = Field(default_factory=EquippedGear, alias="equipped")
    gear_costume: EquippedGear = Field(default_factory=EquippedGear, alias="costume")
    # gear.owned maps key -> True/False
    gear_owned: dict[str, bool] = Field(default_factory=dict, alias="owned")
    # Consumables
    eggs: dict[str, int] = Field(default_factory=dict)
    food: dict[str, int] = Field(default_factory=dict)
    hatchingPotions: dict[str, int] = Field(default_factory=dict, alias="hatchingPotions")
    # Companions
    pets: dict[str, int] = Field(default_factory=dict, description="{Pet-SpeciesKey: feed_count}") # e.g. {"BearCub-Base": 5}
    mounts: dict[str, bool] = Field(default_factory=dict, description="{Mount-SpeciesKey: True}") # e.g. {"BearCub-Base": True}
    # Special items & Quest scrolls
    special: dict[str, int] = Field(default_factory=dict) # Orbs, Cards etc. {itemKey: count}
    quests: dict[str, int] = Field(default_factory=dict) # {questKey: count}


    @model_validator(mode="before")
    @classmethod
    def structure_gear_data(cls, data: Any) -> dict[str, Any]:
        """Ensure gear keys (equipped, costume, owned) exist from gear sub-dict."""
        if not isinstance(data, dict):
             return data
        values = data.copy()
        # Check if fields are already top-level (might happen if processing elsewhere)
        if "equipped" not in values and "gear" in values and isinstance(values["gear"], dict):
             gear_data = values["gear"]
             values["equipped"] = gear_data.get("equipped", {})
             values["costume"] = gear_data.get("costume", {})
             values["owned"] = gear_data.get("owned", {})
             # Optionally remove the original 'gear' key if desired
             # values.pop("gear")
        # Ensure defaults if keys are still missing
        for key in ["equipped", "costume", "owned"]:
            if key not in values:
                values[key] = {}

        # Validate counts for items? Pydantic handles dict[str, int] usually
        return values


# KLASS: UserAchievements
class UserAchievements(BaseModel):
    """Holds user's achievements progress."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    challenges: list[str] = Field(default_factory=list, description="List of challenge IDs completed.")
    quests: dict[str, int] = Field(default_factory=dict, description="{quest_key: completion_count}.")
    perfect_days: int = Field(0, alias="perfect", description="Count of perfect days.")
    streak: int = Field(0, description="Max consecutive perfect days streak.")
    loginIncentives: int = Field(0, alias="loginIncentives", description="Count of login incentives claimed for achievements.")
    ultimateGearSets: dict[str, bool] = Field(default_factory=dict, alias="ultimateGearSets")
    # Store other achievements found directly under 'achievements'
    other_achievements: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def separate_other_achievements(cls, data: Any) -> dict[str, Any]:
        """Separates known fields from arbitrary others under 'achievements'."""
        if not isinstance(data, dict):
             return data
        values = {}
        known_keys = {"challenges", "quests", "perfect", "streak", "loginIncentives", "ultimateGearSets"}
        other_achievements_dict = {}
        for k, v in data.items():
            if k in known_keys:
                 values[k] = v # Keep known keys
            else:
                 other_achievements_dict[k] = v # Put others into separate dict
        values["other_achievements"] = other_achievements_dict
        return values


    @field_validator("perfect_days", "streak", "loginIncentives", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        try: return int(value)
        except (ValueError, TypeError): return 0


# KLASS: UserPartyInfo (User's perspective)
class UserPartyInfo(BaseModel):
    """Holds information about the user's current party membership and quest status."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    party_id: str | None = Field(None, alias="_id", description="The unique ID of the party the user is in.")
    # The user object often contains a snapshot of the party quest status relevant *to the user*.
    quest: QuestInfo | None = Field(None, description="User's view of the active party quest status and progress.")

    @model_validator(mode="before")
    @classmethod
    def ensure_party_id_mapping(cls, data: Any) -> dict[str, Any]:
        """Map party._id to party_id if structure is party:{_id: ...}."""
        if not isinstance(data, dict):
            return data # Or {}
        values = data.copy()
        # If raw data looks like user.party = {_id: ..., quest: ...}
        if "_id" in values and "party_id" not in values:
             values["party_id"] = values["_id"]
        return values


# KLASS: UserInboxInfo
class UserInboxInfo(BaseModel):
    """Holds information about the user's inbox."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    newMessages: int = Field(0, alias="newMessages", description="Count of unread private messages.")
    hasNew: bool = Field(False, alias="hasNew", description="Flag indicating a new gift message.") # Less informative, count is better
    optOut: bool = Field(False, alias="optOut", description="Whether the user has opted out of receiving new PMs.")
    blocks: list[str] = Field(default_factory=list, description="List of user IDs blocked by this user.")
    # Optional: Can embed received messages directly if API provides them here
    # messages: MessageList | None = None # Type hint

    @field_validator("newMessages", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        try: return int(value)
        except (ValueError, TypeError): return 0

    # @field_validator("messages", mode="before") # Example if API embeds messages as dict {msgId: data}
    # @classmethod
    # def messages_dict_to_list(cls, value: Any) -> list[dict] | None:
    #     """Converts message dict to list for MessageList validation."""
    #     if isinstance(value, dict):
    #         return list(value.values())
    #     elif isinstance(value, list):
    #          return value # Already a list
    #     return None # Return None or empty list if invalid format


# KLASS: UserStats (Main Stats Container) - Continuing from previous section
class UserStats(BaseModel):
    """Represents the user's core numerical stats and attributes."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    # --- Resources ---
    hp: float = Field(default=50.0)
    mp: float = Field(default=0.0)
    exp: float = Field(default=0.0)
    gp: float = Field(default=0.0)
    lvl: int = Field(default=1)
    klass: Literal["warrior", "rogue", "healer", "wizard"] | None = Field(None, alias="class")

    # --- Base Attributes (Allocated Points) ---
    base_con: int = Field(0, alias="con")
    base_int_: int = Field(0, alias="int")
    base_per: int = Field(0, alias="per")
    base_str_: int = Field(0, alias="str")

    # --- Base Max Values (Before CON/INT bonuses) ---
    max_hp_base: int = Field(50, alias="maxHealth")
    max_mp_base: int = Field(10, alias="maxMP") # Base before INT bonus
    exp_to_next_level: int = Field(0, alias="toNextLevel")

    # --- Modifiers (Nested Models) ---
    buffs: Buffs = Field(default_factory=Buffs)
    training: Training = Field(default_factory=Training)

    # --- Validators ---
    @field_validator("hp", "mp", "exp", "gp", mode="before")
    @classmethod
    def ensure_float_resources(cls, value: Any) -> float:
        try: return float(value)
        except (ValueError, TypeError): return 0.0

    @field_validator(
        "lvl", "max_hp_base", "max_mp_base", "exp_to_next_level",
        "base_con", "base_int_", "base_per", "base_str_", # Add base stats here
        mode="before"
    )
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensures integer fields are parsed correctly."""
        try: return int(value)
        except (ValueError, TypeError): return 0

    # No separate calculation class needed. Calculations happen on User or here if self-contained.

    def calculate_level_bonus(self) -> float:
        """Calculate stat bonus from level."""
        return min(50.0, math.floor(self.lvl / 2.0)) # Max bonus of +50 from levels

    def calculate_stats_before_gear(self) -> dict[str, float]:
         """Calculates stats combining base, buffs, training, and level bonus."""
         level_bonus = self.calculate_level_bonus()
         return {
              "con": float(self.base_con) + self.buffs.con + self.training.con + level_bonus,
              "int": float(self.base_int_) + self.buffs.int_ + self.training.int_ + level_bonus,
              "per": float(self.base_per) + self.buffs.per + self.training.per + level_bonus,
              "str": float(self.base_str_) + self.buffs.str_ + self.training.str_ + level_bonus,
         }

# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MAIN USER MODEL


# KLASS: User
class User(BaseModel):
    """Represents the complete Habitica User object, aggregating data from the API."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, validate_assignment=True)

    # --- Top-Level Fields ---
    id: str = Field(..., alias="_id", description="Unique User UUID.")
    balance: float = Field(default=0.0, description="User's gem balance / 4.")
    needs_cron: bool = Field(False, alias="needsCron", description="Flag indicating cron needs to run.")
    last_cron: datetime | None = Field(None, alias="lastCron", description="Timestamp of the last cron run (UTC).")
    login_incentives: int = Field(0, alias="loginIncentives", description="Current login incentive count for rewards.")

    # --- Nested Subcomponent Models ---
    profile: UserProfile = Field(default_factory=UserProfile)
    auth: UserAuth = Field(default_factory=UserAuth)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    items: UserItems = Field(default_factory=UserItems)
    achievements: UserAchievements = Field(default_factory=UserAchievements)
    party: UserPartyInfo = Field(default_factory=UserPartyInfo)
    inbox: UserInboxInfo = Field(default_factory=UserInboxInfo)
    stats: UserStats = Field(default_factory=UserStats)
    tags: TagList | None = Field(default_factory=TagList, description="User's defined tags.") # Populate from separate endpoint typically

    # --- Calculated Fields (Storage) ---
    # Store results of expensive calculations here, mark Private or Exclude
    _calculated_stats: dict[str, Any] = PrivateAttr(default_factory=dict)


    # --- Validators ---
    @model_validator(mode="before")
    @classmethod
    def ensure_id_mapping(cls, data: Any) -> dict[str, Any]:
         """Map _id to id if needed."""
         if isinstance(data, dict):
             if "_id" in data and "id" not in data:
                 data["id"] = data["_id"]
             # Handle tags being directly in user data vs loaded separately
             if "tags" in data and isinstance(data["tags"], list):
                 # Pydantic will validate the list against the TagList model
                 pass
             else:
                  data["tags"] = [] # Ensure tags field exists for TagList parsing

         return data if isinstance(data, dict) else {}


    @field_validator("last_cron", mode="before")
    @classmethod
    def parse_last_cron_utc(cls, value: Any) -> datetime | None:
        """Parse lastCron timestamp using DateTimeHandler."""
        handler = DateTimeHandler(timestamp=value)
        return handler.utc_datetime

    @field_validator("balance", mode="before")
    @classmethod
    def ensure_float_balance(cls, value: Any) -> float:
        try: return float(value)
        except (ValueError, TypeError): return 0.0

    @field_validator("login_incentives", mode="before")
    @classmethod
    def ensure_int_login(cls, value: Any) -> int:
        try: return int(value)
        except (ValueError, TypeError): return 0


    @field_validator("tags", mode="before")
    @classmethod
    def tags_list_to_taglist(cls, value: Any) -> dict[str, list]:
        """Ensure tags input is structured correctly for TagList model."""
        if isinstance(value, list):
             # Wrap list in a dict for Pydantic to parse into TagList(tags=...)
             return {"tags": value}
        elif isinstance(value, dict) and "tags" in value:
             return value # Already structured
        return {"tags": []} # Default empty


    # --- Convenience Properties (Accessing nested data) ---
    @property
    def username(self) -> str | None: return self.auth.username
    @property
    def display_name(self) -> str: return self.profile.name or self.username or "N/A" # Fallback display
    @property
    def level(self) -> int: return self.stats.lvl
    @property
    def klass(self) -> str | None: return self.stats.klass
    @property
    def hp(self) -> float: return self.stats.hp
    @property
    def mp(self) -> float: return self.stats.mp
    @property
    def gp(self) -> float: return self.stats.gp
    @property
    def exp(self) -> float: return self.stats.exp
    @property
    def party_id(self) -> str | None: return self.party.party_id
    @property
    def is_sleeping(self) -> bool: return self.preferences.sleep
    @property
    def exp_to_next_level(self) -> int: return self.stats.exp_to_next_level

    @computed_field(description="Calculated Gem count.")
    @property
    def gems(self) -> int:
        """Calculated gem count from balance (balance = gems / 4)."""
        return int(self.balance * 4) if self.balance > 0 else 0

    @property
    def stealth(self) -> int:
        """Shortcut to the stealth buff value."""
        return self.stats.buffs.stealth

    @property
    def is_on_boss_quest(self) -> bool:
         """Check if user is currently on an active boss quest."""
         if self.party.quest and self.party.quest.is_active_and_ongoing:
              # Requires fetching static data and checking quest type
              static_details = self.party.static_quest_details # Access cached static data
              if static_details and getattr(static_details, 'is_boss_quest', False):
                    return True
         return False

    # --- Accessing Calculated Stats ---

    @property
    def effective_stats(self) -> dict[str, float]:
        """Returns the pre-calculated effective stats (STR, CON, INT, PER). Call `calculate_effective_stats` first."""
        return self._calculated_stats.get("effective_stats", {})

    @property
    def max_hp(self) -> float:
        """Returns the pre-calculated maximum HP. Call `calculate_effective_stats` first."""
        return self._calculated_stats.get("max_hp", 50.0) # Default 50

    @property
    def max_mp(self) -> float:
        """Returns the pre-calculated maximum MP. Call `calculate_effective_stats` first."""
        # Base MP depends on class - needs logic or rely on calculated value
        return self._calculated_stats.get("max_mp", 10.0) # Default base

    # --- Calculation Method ---

    def calculate_effective_stats(self, gear_data: dict[str, Gear] | None = None) -> None:
        """
        Calculates total effective stats (base, buffs, training, level, gear)
        and max HP/MP. Stores the results in the internal `_calculated_stats` dict.

        Args:
            gear_data: A dictionary mapping gear keys to **validated Gear objects**.
                       Required for accurate calculations. If None, gear bonus will be 0.
        """
        log.debug(f"Calculating effective stats for user {self.id}...")
        if gear_data is None:
            log.warning("No gear_data provided to calculate_effective_stats. Gear bonus will be zero.")
            gear_data = {} # Use empty dict

        # 1. Get stats before gear bonus (base + buffs + training + level)
        stats_before_gear = self.stats.calculate_stats_before_gear()

        # 2. Calculate gear bonus
        gear_bonus = self.items.gear_equipped.calculate_total_bonus(self.klass, gear_data)

        # 3. Combine for final effective stats
        eff_stats: dict[str, float] = {}
        for stat in ["str", "con", "int", "per"]:
             eff_stats[stat] = stats_before_gear.get(stat, 0.0) + gear_bonus.get(stat, 0.0)
        log.debug(f" -> StatsBeforeGear: {stats_before_gear}")
        log.debug(f" -> GearBonus: {gear_bonus}")
        log.debug(f" -> EffectiveStats: {eff_stats}")

        # 4. Calculate Max HP/MP using effective CON/INT
        effective_con = eff_stats.get("con", 0.0)
        effective_int = eff_stats.get("int", 0.0)
        # Base HP + 2HP per Effective CON point (floor CON first?) Habitica math can be subtle. Assume direct multiplier for now.
        max_hp_calc = float(self.stats.max_hp_base + (effective_con * 2.0))
        # Base MP + 2MP per Effective INT point? (or mana multiplier based on class?) Need accurate formula. Using +2/INT for now.
        # Example: Wizard MP: 30 + 2.5*INT + Lvl/2; Healer MP: 30 + 2*INT + Lvl/4 ? Research needed.
        # Using a simplified base + INT multiplier
        max_mp_calc = float(self.stats.max_mp_base + (effective_int * 2.0))
        log.debug(f" -> Calculated MaxHP: {max_hp_calc} (Base: {self.stats.max_hp_base}, EffCON: {effective_con:.1f})")
        log.debug(f" -> Calculated MaxMP: {max_mp_calc} (Base: {self.stats.max_mp_base}, EffINT: {effective_int:.1f})")

        # 5. Store all calculated values internally
        self._calculated_stats["effective_stats"] = eff_stats
        self._calculated_stats["max_hp"] = round(max_hp_calc, 1)
        self._calculated_stats["max_mp"] = round(max_mp_calc, 1)
        # Can store other derived values here too if needed
        # self._calculated_stats["gems"] = self.gems


    # --- Factory & Serialization ---
    @classmethod
    def create_from_raw_data(cls, raw_data: dict) -> User | None:
        """Validates raw API data into a User object."""
        if not isinstance(raw_data, dict):
            log.error("Invalid raw data type for User creation: Expected dict.")
            return None
        try:
            user_instance = cls.model_validate(raw_data)
            log.info(f"User model created successfully for ID: {user_instance.id}")
            return user_instance
        except ValidationError as e:
            log.error(f"Validation failed creating User model: {e}", exc_info=False)
            return None
        except Exception as e:
            log.exception("Unexpected error creating User from raw data.")
            return None


    # Default model_dump/model_dump_json are sufficient now

# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MAIN EXECUTION (Example/Test)
async def main():
    """Demo function to retrieve, process, and display user data."""
    log.info("--- User Model Demo ---")
    user_instance: User | None = None

    try:
        cache_dir = HABITICA_DATA_PATH / "user"
        cache_dir.mkdir(exist_ok=True, parents=True)
        raw_path = cache_dir / "user_raw.json"
        processed_path = cache_dir / "user_processed.json"

        # 1. Fetch raw data
        log.info("Fetching user data from API...")
        api = HabiticaClient() # Assumes configured
        raw_data = await api.get_user_data()
        if not raw_data:
             log.error("Failed to fetch user data. Exiting demo.")
             return None
        log.success("Fetched raw user data.")
        # save_json(raw_data, raw_path.name, folder=raw_path.parent) # Save raw

        # 2. Create User model
        log.info("Validating raw data into User model...")
        user_instance = User.create_from_raw_data(raw_data)
        if not user_instance:
             log.error("Failed to create User model from raw data.")
             return None

        # 3. Load Static Gear Data (needed for calculation)
        log.info("Loading static gear data for stat calculation...")
        content_manager = StaticContentManager() # Assumes it can load/cache
        static_gear_data = await content_manager.get_gear() # Returns dict[str, Gear]
        if not static_gear_data:
            log.warning("Could not load static gear data. Effective stats will exclude gear bonus.")


        # 4. Calculate Effective Stats
        log.info("Calculating effective stats...")
        user_instance.calculate_effective_stats(gear_data=static_gear_data)
        log.success("Effective stats calculated.")


        # 5. Display Data
        print("\n--- Basic Info ---")
        print(f"ID          : {user_instance.id}")
        print(f"Username    : {user_instance.username}")
        print(f"Display Name: {user_instance.display_name}")
        print(f"Level       : {user_instance.level}")
        print(f"Class       : {user_instance.klass}")
        print(f"Sleeping    : {user_instance.is_sleeping}")
        print(f"Party ID    : {user_instance.party_id}")
        print(f"Gems        : {user_instance.gems}")

        print("\n--- Core Resources ---")
        # Use calculated max values now
        print(f"HP          : {user_instance.hp:.1f} / {user_instance.max_hp:.1f}")
        print(f"MP          : {user_instance.mp:.1f} / {user_instance.max_mp:.1f}")
        print(f"EXP         : {user_instance.exp:.0f} / {user_instance.exp_to_next_level}")
        print(f"Gold        : {user_instance.gp:.2f}")

        print("\n--- Effective Stats (incl. Gear) ---")
        for stat, value in user_instance.effective_stats.items():
             # Access base/training/buff for breakdown (optional)
             base_stat = getattr(user_instance.stats, f"base_{'int_' if stat=='int' else ('str_' if stat=='str' else stat)}", 0)
             train_stat = getattr(user_instance.stats.training, f"{'int_' if stat=='int' else ('str_' if stat=='str' else stat)}", 0.0)
             buff_stat = getattr(user_instance.stats.buffs, f"{'int_' if stat=='int' else ('str_' if stat=='str' else stat)}", 0.0)
             # Gear bonus = effective - (base + train + buff + level)
             level_bonus = user_instance.stats.calculate_level_bonus()
             gear_b = value - (base_stat + train_stat + buff_stat + level_bonus)
             print(f"{stat.upper():<4}: {value:>5.1f}   (Base:{base_stat} Train:{train_stat:.1f} Buff:{buff_stat:.1f} Lvl:{level_bonus:.0f} Gear:{gear_b:+.1f})")


        print("\n--- User Tags ---")
        if user_instance.tags:
             print(f"Tag Count   : {len(user_instance.tags.tags)}")
             print(f"Sample Tags : {[t.name for t in user_instance.tags.tags[:5]]}...")
        else:
             print("No tags found/loaded.")


        # 6. Save processed data (including calculated stats if needed)
        # By default, PrivateAttr (_calculated_stats) isn't dumped.
        # If you want to save them, make _calculated_stats a regular Field or modify dumping.
        log.info(f"Saving processed user data to {processed_path}...")
        # save_pydantic_model(user_instance, processed_path) # Standard dump
        # Or to include calculated stats:
        user_data_dict = user_instance.model_dump(mode='json')
        user_data_dict['calculated'] = user_instance._calculated_stats # Manually add private attr
        save_json(user_data_dict, processed_path.name, folder=processed_path.parent) # Save merged dict
        log.success("Processed user data (with calculated) saved.")

    except ConnectionError as e:
         log.error(f"API Connection error: {e}")
    except ValidationError as e:
         log.error(f"Pydantic Validation Error: {e}")
    except Exception as e:
         log.exception(f"An unexpected error occurred in the user demo: {e}")

    return user_instance

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(main())

# ──────────────────────────────────────────────────────────────────────────────
```

---

## File: `pixabit/models/data_manager.py`

**Suggestions:**

1.  **Focus:** The `DataManager` orchestrates loading, caching, and processing. It _uses_ the Pydantic models and the `StaticContentManager`.
2.  **Async:** Ensure all API calls (`load_X` methods) are `async`.
3.  **Static Content:** Delegate static content loading entirely to `StaticContentManager`. `DataManager` just calls `static_content_manager.load_content()` or specific getters like `static_content_manager.get_gear()`.
4.  **Pydantic Caching:** Use `load_pydantic_model` and `save_pydantic_model` for caching the _processed_ models (`User`, `TaskList`, `Party`, `TagList`, `GameContent`). Raw data caching uses `save_json`/`load_json`.
5.  **Cache Logic:** Implement `_is_cache_stale` for _live_ data based on `CACHE_TIMEOUT`. `StaticContentManager` handles its own cache duration internally. Add basic file-based caching for live data models.
6.  **Two-Phase Load/Process:**
    - `load_all_data(force_refresh=False)`: Concurrently calls `load_user`, `load_tasks`, `load_tags`, `load_party`, and triggers `static_content_manager.load_content()`. Handles cache checks internally based on `force_refresh`. It populates the internal attributes (`_user`, `_tasks`, etc.).
    - `process_loaded_data()`: This method is called _after_ `load_all_data`. It checks if required data (`_user`, `_tasks`, `_tags`, static data via manager properties) is loaded. Then, it calls the necessary processing methods:
      - `_user.calculate_effective_stats(gear_data=self.static_content_manager.get_gear_sync())` (assuming a sync getter or pre-loaded static data)
      - `_tasks.process_task_statuses_and_damage(user=_user, tags_provider=_tags, content_manager=self.static_content_manager)`
      - Potentially `_party.fetch_and_set_static_quest_details(self.static_content_manager)`
7.  **Error Handling:** Gracefully handle failures during loading or processing, logging appropriate errors.
8.  **Dependencies:** Inject `HabiticaClient` and `StaticContentManager`. `DataManager` should not instantiate these itself usually, promoting dependency inversion.
9.  **Properties:** Properties provide access to the _loaded and potentially processed_ models (`self.user`, `self.tasks`, `self.static_gear`).

**Refactored Code:**

```python
# pixabit/services/data_manager.py # Adjusted path based on intent

# ─── Title ────────────────────────────────────────────────────────────────────
#          Habitica Data Orchestration Manager
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""
Provides a centralized DataManager class for loading, caching, processing,
and accessing Habitica data models (User, Tasks, Tags, Party, Static Content).
Orchestrates interactions between the API client, static content manager,
and data models.
"""

# SECTION: IMPORTS
from __future__ import annotations

import asyncio
import json # For custom encoder only if needed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Type # Use standard lowercase

# Project Imports
try:
    from pixabit.api.client import HabiticaClient
    from pixabit.config import (
        HABITICA_DATA_PATH,
        DEFAULT_CACHE_DURATION_DAYS,
        USER_ID # Use USER_ID from config for Party context
    )
    from pixabit.helpers._json import save_json, load_json, save_pydantic_model, load_pydantic_model
    from pixabit.helpers._logger import log
    from pixabit.helpers.DateTimeHandler import DateTimeHandler # If used for cache timestamp parsing

    # Import all necessary models
    from pixabit.models.game_content import StaticContentManager, Gear, Quest # Type hints
    from pixabit.models.party import Party
    from pixabit.models.tag import TagList # Simple TagList
    # from pixabit.models.tag_factory import TagList as AdvancedTagList # If supporting advanced tags
    from pixabit.models.task import TaskList, Task, Daily, Todo, Habit, Reward # TaskList class
    from pixabit.models.user import User
    from pixabit.models.challenge import ChallengeList # If managing challenges

except ImportError as e:
     # Handle import errors gracefully, perhaps logging or raising config error
     import logging
     log = logging.getLogger(__name__)
     log.addHandler(logging.NullHandler())
     log.critical(f"DataManager failed to import critical dependencies: {e}. Check project structure and installations.")
     # Define placeholders if absolutely necessary for type checking fallback, but critical failure is better
     raise ImportError(f"DataManager could not load required modules: {e}") from e


# SECTION: CONSTANTS & CONFIG

# Live data cache timeout (e.g., 5 minutes)
# Static data timeout is handled by StaticContentManager internally
DEFAULT_LIVE_CACHE_TIMEOUT = timedelta(minutes=5)

CACHE_SUBDIR_RAW = "raw"
CACHE_SUBDIR_PROCESSED = "processed"


# SECTION: DATA MANAGER CLASS

# KLASS: DataManager
class DataManager:
    """
    Centralized manager for fetching, caching, processing, and accessing
    Habitica data models. Orchestrates API interaction and model processing.
    """

    def __init__(
        self,
        api_client: HabiticaClient,
        static_content_manager: StaticContentManager, # Inject StaticContentManager
        cache_dir: Path = HABITICA_DATA_PATH,
        live_cache_timeout: timedelta = DEFAULT_LIVE_CACHE_TIMEOUT,
    ):
        """Initializes the DataManager.

        Args:
            api_client: An instance of HabiticaClient.
            static_content_manager: An instance of StaticContentManager.
            cache_dir: Base directory for caching data.
            live_cache_timeout: Duration for which cached live data is considered fresh.
        """
        self.api = api_client
        self.static_content_manager = static_content_manager
        self.cache_dir = cache_dir
        self.live_cache_timeout = live_cache_timeout

        # Configure cache paths
        self.raw_cache_dir = self.cache_dir / CACHE_SUBDIR_RAW
        self.processed_cache_dir = self.cache_dir / CACHE_SUBDIR_PROCESSED
        self.raw_cache_dir.mkdir(parents=True, exist_ok=True)
        self.processed_cache_dir.mkdir(parents=True, exist_ok=True)

        # Internal storage for loaded data models
        self._user: User | None = None
        self._tasks: TaskList | None = None
        self._tags: TagList | None = None # Or AdvancedTagList if used
        self._party: Party | None = None
        # Add other models like challenges if managed here
        # self._challenges: ChallengeList | None = None

        # Store last refresh times for live data
        self._last_refresh_times: dict[str, datetime | None] = {
            "user": None, "tasks": None, "tags": None, "party": None, # "challenges": None,
        }

        log.info(f"DataManager initialized. Cache Dir: {self.cache_dir}")


    # --- Cache Helper ---
    def _is_live_cache_stale(self, data_key: str) -> bool:
        """Checks if the cache for a specific live data key is stale."""
        last_refresh = self._last_refresh_times.get(data_key)
        if last_refresh is None:
            return True # Cache is stale if never refreshed
        # Ensure comparison is timezone-aware
        now_utc = datetime.now(timezone.utc)
        if last_refresh.tzinfo is None:
            last_refresh = last_refresh.replace(tzinfo=timezone.utc) # Assume UTC if naive
        return (now_utc - last_refresh) > self.live_cache_timeout


    def _get_cache_path(self, filename: str, processed: bool) -> Path:
         """Gets the full path for a cached file."""
         dir_path = self.processed_cache_dir if processed else self.raw_cache_dir
         return dir_path / filename

    def _update_refresh_time(self, data_key: str):
         """Updates the last refresh time for a given key."""
         self._last_refresh_times[data_key] = datetime.now(timezone.utc)


    # --- Properties for Accessing Data ---
    # Provides controlled access to the managed models

    @property
    def user(self) -> User | None:
        """Returns the loaded User object."""
        return self._user

    @property
    def tasks(self) -> TaskList | None:
        """Returns the loaded TaskList object."""
        return self._tasks

    @property
    def tags(self) -> TagList | None: # Or AdvancedTagList
        """Returns the loaded TagList object."""
        return self._tags

    @property
    def party(self) -> Party | None:
        """Returns the loaded Party object."""
        return self._party

    # Access static data via the manager's properties/methods
    # Example: Direct access to potentially loaded static content
    @property
    def static_gear_data(self) -> dict[str, Gear] | None:
        """Returns cached static gear data directly from the StaticContentManager (if loaded)."""
        # Note: This doesn't trigger loading, assumes load_all_data or equivalent called first.
        if self.static_content_manager._content:
            return self.static_content_manager._content.gear
        return None

    @property
    def static_quest_data(self) -> dict[str, Quest] | None:
         """Returns cached static quest data directly from the StaticContentManager (if loaded)."""
         if self.static_content_manager._content:
              return self.static_content_manager._content.quests
         return None


    # --- Loading Methods for LIVE Data ---

    async def load_user(self, force_refresh: bool = False) -> User | None:
        """Loads User data from cache or API."""
        data_key = "user"
        filename = "user.json"
        model_class = User

        if not force_refresh and self._user and not self._is_live_cache_stale(data_key):
             log.debug("Using in-memory user data.")
             return self._user

        # Try loading from processed cache first
        processed_path = self._get_cache_path(filename, processed=True)
        if not force_refresh and processed_path.exists():
            # Check modification time against timeout for file cache
            mtime = datetime.fromtimestamp(processed_path.stat().st_mtime, timezone.utc)
            if (datetime.now(timezone.utc) - mtime) <= self.live_cache_timeout:
                log.debug(f"Attempting to load user from processed cache: {processed_path}")
                cached_model = load_pydantic_model(model_class, processed_path)
                if cached_model:
                    self._user = cached_model
                    self._update_refresh_time(data_key) # Update timestamp based on cache load
                    log.info("User loaded from fresh processed cache.")
                    return self._user
                else:
                    log.warning(f"Failed to load user model from presumably fresh cache file: {processed_path}")
            else:
                 log.info("User processed cache file is stale.")


        # Fetch from API
        log.info(f"{'Forcing refresh for' if force_refresh else 'Fetching'} user data from API...")
        try:
             raw_data = await self.api.get_user_data()
             if not raw_data:
                 log.error("Received empty data from user API endpoint.")
                 # Should we return stale cache if available? Or None? Return None for now.
                 self._user = None # Clear potentially stale user
                 return None

             # Validate raw data into model
             self._user = model_class.model_validate(raw_data)
             self._update_refresh_time(data_key)

             # Save raw and processed data
             save_json(raw_data, filename, folder=self.raw_cache_dir)
             save_pydantic_model(self._user, filename, folder=self.processed_cache_dir)
             log.success("User data fetched and processed.")
             return self._user

        except Exception as e:
             log.exception("Failed to fetch or process user data from API.")
             # Fallback to potentially stale in-memory data? Or clear? Clear is safer.
             self._user = None
             return None


    async def load_tasks(self, force_refresh: bool = False) -> TaskList | None:
        """Loads TaskList from cache or API."""
        data_key = "tasks"
        filename = "tasks.json"
        # Note: TaskList is a class, not a Pydantic model itself for saving/loading directly.
        # We cache the *list* of task dictionaries after TaskList validation.

        if not force_refresh and self._tasks and not self._is_live_cache_stale(data_key):
             log.debug("Using in-memory tasks data.")
             return self._tasks

        processed_path = self._get_cache_path(filename, processed=True)
        if not force_refresh and processed_path.exists():
            mtime = datetime.fromtimestamp(processed_path.stat().st_mtime, timezone.utc)
            if (datetime.now(timezone.utc) - mtime) <= self.live_cache_timeout:
                log.debug(f"Attempting to load tasks from processed cache: {processed_path}")
                # Load the *list* of task dicts from cache
                cached_task_dicts = load_json(processed_path)
                if isinstance(cached_task_dicts, list):
                    try:
                        # Re-create TaskList instance from cached dicts
                        # Use from_api_data to re-validate? Safer.
                        self._tasks = TaskList.from_api_data(cached_task_dicts)
                        self._update_refresh_time(data_key)
                        log.info("Tasks loaded from fresh processed cache.")
                        return self._tasks
                    except Exception as e:
                         log.exception(f"Error re-creating TaskList from cached data: {e}")
                else:
                    log.warning(f"Invalid data format in tasks cache file: {processed_path}. Expected list.")
            else:
                log.info("Tasks processed cache file is stale.")

        log.info(f"{'Forcing refresh for' if force_refresh else 'Fetching'} tasks data from API...")
        try:
            raw_data = await self.api.get_tasks() # Returns list[dict]
            if not isinstance(raw_data, list):
                 log.error(f"Received unexpected data type from tasks API: {type(raw_data)}")
                 self._tasks = None
                 return None

            # Create TaskList instance, which validates raw data into Task objects
            self._tasks = TaskList.from_api_data(raw_data)
            self._update_refresh_time(data_key)

            save_json(raw_data, filename, folder=self.raw_cache_dir)
            # Save the list of *processed* task dictionaries
            self._tasks.save_to_json(filename, folder=self.processed_cache_dir)
            log.success("Tasks data fetched and processed.")
            return self._tasks

        except Exception as e:
            log.exception("Failed to fetch or process tasks data from API.")
            self._tasks = None
            return None

    async def load_tags(self, force_refresh: bool = False) -> TagList | None:
        """Loads TagList from cache or API."""
        data_key = "tags"
        filename = "tags.json"
        model_class = TagList # Simple TagList BaseModel

        if not force_refresh and self._tags and not self._is_live_cache_stale(data_key):
             log.debug("Using in-memory tags data.")
             return self._tags

        processed_path = self._get_cache_path(filename, processed=True)
        if not force_refresh and processed_path.exists():
            mtime = datetime.fromtimestamp(processed_path.stat().st_mtime, timezone.utc)
            if (datetime.now(timezone.utc) - mtime) <= self.live_cache_timeout:
                 log.debug(f"Attempting to load tags from processed cache: {processed_path}")
                 cached_model = load_pydantic_model(model_class, processed_path)
                 if cached_model:
                     self._tags = cached_model
                     self._update_refresh_time(data_key)
                     log.info("Tags loaded from fresh processed cache.")
                     return self._tags
                 else:
                     log.warning(f"Failed to load tags model from cache: {processed_path}")
            else:
                log.info("Tags processed cache file is stale.")


        log.info(f"{'Forcing refresh for' if force_refresh else 'Fetching'} tags data from API...")
        try:
             raw_data = await self.api.get_tags() # Returns list[dict]
             if not isinstance(raw_data, list):
                 log.error(f"Received unexpected data type from tags API: {type(raw_data)}")
                 self._tags = None
                 return None

             # Validate raw data using TagList's factory method
             self._tags = model_class.from_raw_data(raw_data)
             self._update_refresh_time(data_key)

             save_json(raw_data, filename, folder=self.raw_cache_dir)
             # Save the processed TagList model
             save_pydantic_model(self._tags, filename, folder=self.processed_cache_dir)
             log.success("Tags data fetched and processed.")
             return self._tags

        except Exception as e:
             log.exception("Failed to fetch or process tags data from API.")
             self._tags = None
             return None

    async def load_party(self, force_refresh: bool = False) -> Party | None:
        """Loads Party data from cache or API."""
        data_key = "party"
        filename = "party.json"
        model_class = Party

        # Party data includes chat, needs user context for validation
        # Get current USER_ID from config - assumes it's correctly set
        user_id_context = USER_ID
        if not user_id_context:
            log.error("USER_ID not configured. Cannot accurately process party chat messages.")
            # Decide whether to proceed without context or fail. Proceeding with warning.

        # Pass context to load_pydantic_model if needed
        validation_context = {"current_user_id": user_id_context}


        if not force_refresh and self._party and not self._is_live_cache_stale(data_key):
             log.debug("Using in-memory party data.")
             return self._party

        processed_path = self._get_cache_path(filename, processed=True)
        if not force_refresh and processed_path.exists():
            mtime = datetime.fromtimestamp(processed_path.stat().st_mtime, timezone.utc)
            if (datetime.now(timezone.utc) - mtime) <= self.live_cache_timeout:
                log.debug(f"Attempting to load party from processed cache: {processed_path}")
                cached_model = load_pydantic_model(model_class, processed_path, context=validation_context)
                if cached_model:
                    self._party = cached_model
                    self._update_refresh_time(data_key)
                    log.info("Party loaded from fresh processed cache.")
                    return self._party
                else:
                     log.warning(f"Failed to load party model from cache: {processed_path}")
            else:
                 log.info("Party processed cache file is stale.")

        log.info(f"{'Forcing refresh for' if force_refresh else 'Fetching'} party data from API...")
        try:
             raw_data = await self.api.get_party_data() # Returns dict or None
             if not isinstance(raw_data, dict):
                  # Handle API returning null/empty if not in party
                  log.info("User is likely not in a party (API returned non-dict).")
                  self._party = None # Ensure party is None
                  # Cache this None state? Maybe cache an empty dict raw/processed? Cache None for now.
                  self._update_refresh_time(data_key) # Update timestamp even for None result
                  return None

             # Create Party model using factory method which handles context
             self._party = model_class.create_from_raw_data(raw_data, current_user_id=user_id_context)
             self._update_refresh_time(data_key)

             save_json(raw_data, filename, folder=self.raw_cache_dir)
             # Save the Party model (chat excluded by default based on field def)
             save_pydantic_model(self._party, filename, folder=self.processed_cache_dir)
             log.success("Party data fetched and processed.")
             return self._party

        except Exception as e:
             log.exception("Failed to fetch or process party data from API.")
             self._party = None # Clear party on error
             return None


    # --- Orchestration Methods ---

    async def load_all_data(self, force_refresh: bool = False) -> None:
        """
        Loads all relevant data concurrently: User, Tasks, Tags, Party, and Static Content.
        Uses caching unless `force_refresh` is True for live data. Static content
        cache policy is managed by StaticContentManager (refreshed if needed).

        Args:
            force_refresh: If True, forces refresh for User, Tasks, Tags, Party.
                           StaticContentManager decides independently unless forced there too.
        """
        log.info(f"Initiating load_all_data (force_refresh={force_refresh})...")

        # Tasks for fetching live data
        live_data_tasks = [
             self.load_user(force_refresh=force_refresh),
             self.load_tasks(force_refresh=force_refresh),
             self.load_tags(force_refresh=force_refresh),
             self.load_party(force_refresh=force_refresh),
             # Add other live data tasks here (e.g., challenges)
        ]

        # Task for loading static content (will use its own cache logic)
        # Optionally pass force_refresh to StaticContentManager if needed:
        # static_content_task = self.static_content_manager.load_content(force_refresh=force_refresh)
        static_content_task = self.static_content_manager.load_content()

        all_tasks = live_data_tasks + [static_content_task]

        # Run all loading tasks concurrently
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Log any errors encountered during loading
        for i, result in enumerate(results):
             if isinstance(result, Exception):
                  # Identify which task failed based on order (requires tasks list order to be consistent)
                  task_map = ["User", "Tasks", "Tags", "Party", "StaticContent"]
                  failed_task_name = task_map[i] if i < len(task_map) else f"UnknownTask_{i}"
                  log.error(f"Error loading {failed_task_name}: {result}")

        # Models (_user, _tasks, etc.) are populated by the load methods.
        # Static content is loaded within static_content_manager.
        log.info("load_all_data finished.")


    async def process_loaded_data(self) -> bool:
        """
        Orchestrates post-loading processing of models. Requires data to be loaded first.

        Processes:
        1. User effective stats (requires static gear data).
        2. Task statuses, tag names, and Daily damage (requires User, Tags, Static Quest data).
        3. Party static quest details (requires Party, Static Quest data).

        Returns:
            True if processing was successful, False otherwise.
        """
        log.info("Initiating process_loaded_data...")

        # --- Check Dependencies ---
        required_live = {"User": self._user, "Tasks": self._tasks, "Tags": self._tags}
        missing_live = [name for name, model in required_live.items() if model is None]

        # Static content check - does the manager have content loaded?
        static_content_loaded = self.static_content_manager._content is not None
        if not static_content_loaded:
             log.error("Cannot process data: Static game content is not loaded.")
             # Optionally attempt to load static content here? Or fail fast? Fail fast.

        if missing_live or not static_content_loaded:
             missing_str = ", ".join(missing_live)
             static_str = "" if static_content_loaded else "Static Content"
             log.error(f"Cannot process loaded data - Required data missing: {missing_str}{', ' if missing_live and not static_content_loaded else ''}{static_str}")
             return False


        success = True
        try:
            # --- Processing Steps ---

            # 1. Process User Stats (needs static gear)
            log.debug("Processing User: Calculating effective stats...")
            gear_data = self.static_content_manager._content.gear if self.static_content_manager._content else {}
            self._user.calculate_effective_stats(gear_data=gear_data) # This updates user._calculated_stats
            log.debug("-> User stats calculated.")


            # 2. Process Tasks (needs User, Tags, StaticContentManager for Daily damage)
            log.debug("Processing Tasks: Calculating statuses, tags, daily damage...")
            self._tasks.process_task_statuses_and_damage(
                user=self._user,
                tags_provider=self._tags,
                content_manager=self.static_content_manager # Pass the manager
            )
            log.debug("-> Tasks processed.")


            # 3. Process Party (fetch/set static quest details if needed)
            if self._party and self._party.quest and self._party.quest.key and not self._party.static_quest_details:
                 log.debug("Processing Party: Fetching static quest details...")
                 # Ensure content manager is passed correctly
                 await self._party.fetch_and_set_static_quest_details(self.static_content_manager)
                 log.debug("-> Party quest details fetched (if applicable).")


            # Add other processing steps here if needed (e.g., processing challenges)

        except Exception as e:
            log.exception("An error occurred during process_loaded_data.")
            success = False


        if success:
             log.success("process_loaded_data finished successfully.")
             # Optionally save processed models *again* after this step?
             # Depends if calculated fields need to be persisted across sessions.
             # For TUI, usually just need them in memory.
        else:
            log.error("process_loaded_data finished with errors.")

        return success


# ──────────────────────────────────────────────────────────────────────────────
```

---

## File: `pixabit/models/test.py`

**Suggestions:**

1.  **Reflect `DataManager` Usage:** Update the script to use the `load_all_data` and `process_loaded_data` workflow.
2.  **Dependencies:** Ensure `StaticContentManager` is instantiated and passed to `DataManager`.
3.  **Error Handling:** Basic `try...except` is good for a test script.
4.  **Access Processed Data:** Show accessing properties that rely on processed data (e.g., `user.effective_stats`).

**Refactored Code:**

```python
# pixabit/models/test.py

# ─── Title ────────────────────────────────────────────────────────────────────
#          DataManager Test/Example Script
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: IMPORTS
import asyncio
from pathlib import Path
import logging # Configure logging for the test

# Project Imports (adjust paths if needed)
try:
    from pixabit.api.client import HabiticaClient
    from pixabit.models.data_manager import DataManager
    from pixabit.models.game_content import StaticContentManager
    from pixabit.config import HABITICA_DATA_PATH # Import base cache path
    from pixabit.helpers._logger import log # Use the configured logger
except ImportError as e:
     print(f"Error importing modules for test script: {e}")
     print("Ensure pixabit is installed correctly or PYTHONPATH is set.")
     exit(1)


# SECTION: MAIN TEST FUNCTION
async def main():
    """Main test function for DataManager."""
    log.info("--- Starting DataManager Test Script ---")

    try:
        # 1. Setup Dependencies
        # --- API Client ---
        # Assumes HabiticaClient can be instantiated and picks up credentials
        api_client = HabiticaClient()
        log.info("Habitica API Client instantiated.")

        # --- Static Content Manager ---
        # Define where static content cache should live
        static_cache_dir = HABITICA_DATA_PATH / "static_content" # Use subfolder from config/static_manager
        content_manager = StaticContentManager(cache_dir=static_cache_dir)
        log.info(f"Static Content Manager instantiated (Cache: {static_cache_dir}).")


        # --- Data Manager ---
        # Use a dedicated cache folder for this test run if desired
        # test_cache_dir = Path("test_habitica_cache").resolve()
        # Or use the configured HABITICA_DATA_PATH
        test_cache_dir = HABITICA_DATA_PATH
        data_manager = DataManager(
             api_client=api_client,
             static_content_manager=content_manager,
             cache_dir=test_cache_dir
             )
        log.info(f"Data Manager instantiated (Cache: {test_cache_dir}).")


        # 2. Load All Data
        log.info("Loading all data using DataManager...")
        await data_manager.load_all_data(force_refresh=False) # Set force_refresh=True to bypass caches
        log.success("Data loading phase complete.")


        # 3. Process Loaded Data
        log.info("Processing loaded data...")
        processing_successful = await data_manager.process_loaded_data()
        if not processing_successful:
             log.error("Data processing phase failed. Results may be incomplete.")
             # Decide if script should exit or continue with potentially unprocessed data
             # exit(1)


        # 4. Access Data via Properties
        log.info("Accessing data through DataManager properties...")

        user = data_manager.user
        tasks = data_manager.tasks
        tags = data_manager.tags
        party = data_manager.party
        static_gear = data_manager.static_gear_data # Access loaded static data

        if user:
            print(f"\n--- User Info ---")
            print(f"Username: {user.username}")
            print(f"Display Name: {user.display_name}")
            print(f"Level: {user.level}")
            # Access calculated stats
            print(f"Effective STR: {user.effective_stats.get('str', 'N/A'):.1f}")
            print(f"Effective CON: {user.effective_stats.get('con', 'N/A'):.1f}")
            print(f"Max HP: {user.max_hp:.1f}")
            print(f"Gems: {user.gems}")
        else:
            print("\nUser data failed to load.")


        if tasks:
            print(f"\n--- Tasks Info ---")
            print(f"Total Tasks: {len(tasks)}")
            dailies = tasks.get_dailies()
            print(f"Dailies Count: {len(dailies)}")
            if dailies:
                first_daily = dailies[0]
                print(f"First Daily Text: {first_daily.text}")
                # Access processed info (tag names, status, damage)
                print(f"  -> Tags: {first_daily.tag_names}")
                print(f"  -> Status: {first_daily.calculated_status}")
                print(f"  -> User Damage: {first_daily.user_damage}") # Uses computed_field
        else:
            print("\nTasks data failed to load.")


        if tags:
             print(f"\n--- Tags Info ---")
             print(f"Total Tags: {len(tags.tags)}")
             # print(f"Sample Tag: {tags.tags[0].name if tags.tags else 'N/A'}")
        else:
             print("\nTags data failed to load.")


        if party:
            print(f"\n--- Party Info ---")
            print(f"Party Name: {party.name}")
            print(f"Member Count: {party.member_count}")
            if party.quest and party.quest.key:
                 print(f"Active Quest Key: {party.quest.key}")
                 # Check if static data was fetched and stored
                 if party.static_quest_details:
                      print(f"  -> Static Quest Title: {party.static_quest_details.text}")
                 else:
                      print(f"  -> Static Quest details not fetched/found.")
            else:
                 print("No active quest.")
        else:
            print("\nParty data failed to load or user not in a party.")

        log.info("\nData access demonstration complete.")
        log.info(f"Check cache folders '{test_cache_dir}/raw' and '{test_cache_dir}/processed' for saved files.")

    except Exception as e:
         log.exception("An unexpected error occurred in the test script.") # Log full traceback


# --- Script Execution ---
if __name__ == "__main__":
    # Setup basic logging for the script itself if run directly
    # The DataManager uses its own logger ('Pixabit' by default from helper)
    logging.basicConfig(
        level=logging.INFO, # Set console level for this script run
        format="%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    # Ensure the Pixabit logger also outputs to console during test run
    # (Assuming the helper already configures it, but this makes sure)
    logging.getLogger("Pixabit").setLevel(logging.DEBUG) # Or INFO


    asyncio.run(main())
    log.info("--- DataManager Test Script Finished ---")


# ──────────────────────────────────────────────────────────────────────────────

```

---

## File: `pixabit/models/__init__.py`

**Suggestions:**

1.  **Exports:** Export only the primary Pydantic models users are likely to import directly (`User`, `Task`, `Daily`, etc., `Party`, `Challenge`, `Tag`, `Quest`, `Gear`, `Spell`). Nested models (`UserProfile`, `Buffs`, `QuestProgress`, etc.) are typically accessed via their parent model.
2.  **Containers:** Export the list/manager classes (`TaskList`, `TagList`, `ChallengeList`, `MessageList`).
3.  **Managers:** Do _not_ export `DataManager` or `StaticContentManager` from the `models` package. These belong in a services/managers layer.
4.  **Simplicity:** Keep it clean and focused on the data structures.
5.  **TagFactory:** Exclude `TagFactory` and its specific models from the main `models` export list. It's an optional, advanced system to be imported explicitly if needed (`from pixabit.models.tag_factory import TagFactory, TagList as AdvancedTagList`).

**Refactored Code:**

```python
# pixabit/models/__init__.py

# ─── Title ────────────────────────────────────────────────────────────────────
#             Pixabit Data Models Package Index
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""
Exports the core Pydantic data models used to represent Habitica entities
within the Pixabit TUI application.

Provides structured representations for User, Tasks (Habits, Dailies, Todos, Rewards),
Tags, Challenges, Parties, Messages, and static Game Content items.
"""

# SECTION: EXPORTS

# --- User ---
from .user import (
    User,
    UserProfile,       # Often accessed directly
    UserStats,         # Often accessed directly
    EquippedGear,      # Useful sub-model
    Buffs, Training    # Less common direct access needed
)

# --- Task ---
from .task import (
    Task,              # Base Task (less used directly)
    Habit,
    Daily,
    Todo,
    Reward,
    TaskList,          # The manager/container class
    ChecklistItem,     # Nested item model
    ChallengeLinkData, # Nested challenge link model
)

# --- Tag ---
from .tag import Tag, TagList # The simple/default Tag models & list container

# --- Challenge ---
from .challenge import Challenge, ChallengeList, ChallengeGroup, ChallengeLeader

# --- Party ---
from .party import Party, QuestInfo, QuestProgress, PartyMember # Export main Party & key nested parts

# --- Message ---
from .message import Message, MessageList, MessageSenderStyles

# --- Game Content (Static) ---
from .game_content import (
    Gear,              # Primary item models
    Quest,
    Spell,
    QuestBoss,         # Key nested models
    QuestDrop,
    QuestCollect,
    GameContent        # The container for processed static data (usually via manager)
)

# --- Explicit Export List (__all__) ---
# Controls `from pixabit.models import *` behaviour
__all__ = [
    # User Models
    "User",
    "UserProfile",
    "UserStats",
    "EquippedGear",
    "Buffs",
    "Training",
    # Task Models & Container
    "Task", "Habit", "Daily", "Todo", "Reward",
    "TaskList",
    "ChecklistItem",
    "ChallengeLinkData",
    # Tag Models & Container (Simple)
    "Tag",
    "TagList",
    # Challenge Models & Container
    "Challenge",
    "ChallengeList",
    "ChallengeGroup",
    "ChallengeLeader",
    # Party Models
    "Party",
    "PartyMember", # Exporting basic member stub
    "QuestInfo",
    "QuestProgress",
    # Message Models & Container
    "Message",
    "MessageList",
    "MessageSenderStyles",
    # Static Game Content Models
    "GameContent", # Processed content container
    "Gear",
    "Quest",
    "Spell",
    "QuestBoss",
    "QuestDrop",
    "QuestCollect",
    # Add other static types like PetInfo, MountInfo here if modeled and exported
]

# Note: TagFactory models (ParentTag, SubTag) and the factory-specific TagList
# are NOT exported here by default. They should be imported explicitly via:
# `from pixabit.models.tag_factory import TagFactory, TagList as AdvancedTagList`

# Note: Manager classes (DataManager, StaticContentManager) are typically
# part of a 'services' or 'managers' package, not exported from 'models'.

# ──────────────────────────────────────────────────────────────────────────────
```

This completes the refactoring based on your detailed instructions. The code now heavily utilizes Pydantic V2 features, adheres to Python best practices, integrates your helpers, and provides a more structured and robust foundation for your TUI's data layer. Remember to test these refactored models thoroughly!
