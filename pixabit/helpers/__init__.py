# pixabit/helpers/__init__.py

"""Pixabit Helper Utilities Package.

Exports commonly used helper functions and classes for tasks like:
- Date/Time manipulation (_date.py)
- JSON handling (_json.py)
- Logging setup (_logger.py)
- Rich console setup (_rich.py)
- Pydantic utilities (_pydantic.py)
- Filename cleaning (_clean_name.py)
- Generic object representation (_repr.py)
- Markdown rendering (_md_to_rich.py)
- Textual component access (_textual.py)
"""

# Selectively expose key functions/classes from helper modules
# This makes imports cleaner in other parts of the application

from . import (
    _md_to_rich,  # Import the module itself
    _textual,  # Import the module itself
)
from ._clean_name import (
    replace_illegal_filename_characters,
    replace_illegal_filename_characters_leading_underscores,
    replace_illegal_filename_characters_prefix_underscore,
)
from ._date import (
    convert_timestamp_to_utc,
    convert_to_local_time,
    format_datetime_with_diff,
    format_timedelta,
    get_local_timezone,
    is_date_passed,
)
from ._json import (
    load_json,
    load_pydantic_model,
    save_json,
    save_pydantic_model,
)
from ._logger import (  # Expose the configured log instance and getter
    get_logger,
    log,
)
from ._md_to_rich import (  # Add MarkdownStatic if used
    MarkdownRenderer,
    escape_rich,
)
from ._pydantic import (
    PYDANTIC_V2,
    BaseModel,  # Re-export Pydantic BaseModel
    Field,  # Re-export Pydantic Field
    PixabitBaseModel,
    ValidationError,  # Re-export Pydantic ValidationError
    create_from_dict,
    model_to_dict,
    # Add version specific decorators if needed frequently
    # model_validator, field_validator, validator
)
from ._repr import generic_repr
from ._rich import console, print  # Expose the console and themed print

# Optionally re-export common Rich components from _rich if desired
# from ._rich import Panel, Table, Text, ...
from ._textual import *  # Re-export most Textual components for convenience

# Define __all__ for explicit public API of the helpers package
__all__ = [
    # Logging
    "log",
    "get_logger",
    # Rich Console / Print
    "console",
    "print",
    # JSON Handling
    "save_json",
    "load_json",
    "save_pydantic_model",
    "load_pydantic_model",
    # Pydantic Utilities
    "PixabitBaseModel",
    "BaseModel",  # Re-export
    "Field",  # Re-export
    "ValidationError",  # Re-export
    "PYDANTIC_V2",
    "create_from_dict",
    "model_to_dict",
    # Date Utilities
    "convert_timestamp_to_utc",
    "convert_to_local_time",
    "format_timedelta",
    "is_date_passed",
    "format_datetime_with_diff",
    "get_local_timezone",
    # Filename Cleaning
    "replace_illegal_filename_characters",
    "replace_illegal_filename_characters_leading_underscores",
    "replace_illegal_filename_characters_prefix_underscore",
    # Representation
    "generic_repr",
    # Markdown
    "MarkdownRenderer",
    "escape_rich",
    # Textual (Re-exported from _textual via *)
    # Add specific Textual exports here if preferred over '*'
]

# --- CORRECTED CONDITIONAL EXPORT ---
# Check flags defined WITHIN the respective modules
if (
    hasattr(_md_to_rich, "TEXTUAL_AVAILABLE")
    and _md_to_rich.TEXTUAL_AVAILABLE
    and hasattr(_md_to_rich, "MARKDOWN_IT_AVAILABLE")
    and _md_to_rich.MARKDOWN_IT_AVAILABLE
):
    try:
        # Import MarkdownStatic from the correct module
        from ._md_to_rich import MarkdownStatic

        # Check if it was actually imported successfully (in case of other issues)
        if "MarkdownStatic" in locals():
            __all__.append("MarkdownStatic")
    except ImportError:
        # This shouldn't normally happen if the flags are True, but good to be safe
        pass
