# pixabit/utils/save_json.py

# SECTION: MODULE DOCSTRING
"""Provides utility functions for saving and loading Python data to/from JSON files.

Includes pretty printing, UTF-8 encoding, directory creation, and error handling.
Uses the themed console for status messages if available.
"""

# SECTION: IMPORTS
import builtins
import json
import logging
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
)  # Kept Dict/List for clarity

from rich.logging import RichHandler
from textual import log

from pixabit.utils.display import console

FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)])

# Use themed console/print if available
try:
    from .display import console, print  # Import print wrapper too

    LOG_FUNC = log.error  # Use the themed print for logging success/errors
    LOG_DETAIL = log.info  # Use log for less critical info like cache hits/misses
except ImportError:  # Fallback
    # Provide a dummy console object
    class DummyConsole:  # noqa: D101
        def print(self, *args: Any, **kwargs: Any) -> None:  # noqa: D102
            builtins.print(*args)

        def log(self, *args: Any, **kwargs: Any) -> None:  # noqa: D102
            builtins.print("LOG:", *args)

    console = DummyConsole()
    print = builtins.print  # Fallback print
    LOG_FUNC = builtins.print  # Fallback logging function
    LOG_DETAIL = lambda *args, **kwargs: None  # No detailed logging in fallback
    builtins.print("Warning: pixabit.utils.display not found, using standard print for save/load messages.")

# SECTION: FUNCTIONS


# FUNC: save_json
def save_json(
    data: Union[Dict[str, Any], List[Any]],  # Use Dict/List for clarity
    filepath: Union[str, Path],
) -> bool:
    """Saves Python data (dict or list) to a JSON file with pretty printing (indent=4).

    Ensures the output directory exists. Handles potential JSON serialization
    errors and file I/O errors, logging messages.

    Args:
        data: The Python dictionary or list to save.
        filepath: The full path (including filename and .json extension) for
                  the output file, as a string or Path object.

    Returns:
        True if saving was successful, False otherwise.
    """
    output_path = Path(filepath) if not isinstance(filepath, Path) else filepath

    try:
        # Create parent directory(ies) if they don't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file with UTF-8 encoding and indentation
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        LOG_FUNC(f"[success]Successfully saved data to:[/success] [file]'{output_path}'[/]")
        return True

    except TypeError as e:  # Handle non-serializable data
        msg = f"Data structure not JSON serializable for '{output_path}'. Error: {e}"
        LOG_FUNC(f"[error]Save Error:[/error] {msg}", style="error")
        return False
    except OSError as e:  # Handle file system errors
        msg = f"Could not write file '{output_path}'. Error: {e}"
        LOG_FUNC(f"[error]Save Error:[/error] {msg}", style="error")
        return False
    except Exception as e:  # Catch any other unexpected errors
        msg = f"An unexpected error occurred saving to '{output_path}'. Error: {e}"
        LOG_FUNC(f"[error]Save Error:[/error] {msg}", style="error")
        # Consider logging traceback here if needed: console.print_exception()
        return False


# FUNC: load_json
def load_json(
    filepath: Union[str, Path],
) -> Optional[Union[Dict[str, Any], List[Any]]]:
    """Loads data from a JSON file.

    Args:
        filepath: The path to the JSON file, as a string or Path object.

    Returns:
        The loaded Python dictionary or list, or None if the file doesn't exist,
        cannot be read, or contains invalid JSON.
    """
    input_path = Path(filepath) if not isinstance(filepath, Path) else filepath

    if not input_path.is_file():  # Check if it exists and is a file
        LOG_DETAIL(f"JSON file not found: [file]'{input_path}'[/]", style="subtle")
        return None

    try:
        with input_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Basic validation of loaded data type
        if isinstance(data, (dict, list)):
            LOG_DETAIL(f"Loaded JSON data from: [file]'{input_path}'[/]", style="info")
            return data
        else:
            LOG_FUNC(f"[warning]Warning:[/warning] Invalid data type ({type(data).__name__}) in JSON file: [file]'{input_path}'[/]")
            return None

    except (OSError, json.JSONDecodeError) as e:
        msg = f"Failed to load/parse JSON file '{input_path}'. Error: {e}"
        LOG_FUNC(f"[warning]Load Warning:[/warning] {msg}")
        return None
    except Exception as e:  # Catch unexpected errors during loading
        msg = f"An unexpected error occurred loading '{input_path}'. Error: {e}"
        LOG_FUNC(f"[error]Load Error:[/error] {msg}")
        # Consider logging traceback here if needed: console.print_exception()
        return None
