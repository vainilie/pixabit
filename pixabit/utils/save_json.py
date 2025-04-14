# pixabit/utils/save_json.py
# MARK: - MODULE DOCSTRING
"""Provides a utility function for saving Python data structures (dictionaries or lists)
into JSON files with pretty printing and proper encoding. Includes directory
creation and error handling.
"""

# MARK: - IMPORTS
import builtins  # For fallback print
import json
from pathlib import Path
from typing import Any, List, Union

# Import console/print if needed for messages, assuming from .display
try:
    # Use the themed console instance if available
    from .display import console, print

    LOG_FUNC = console.print  # Prioritize themed console.print
except ImportError:
    # Fallback if display utils are missing or run standalone
    builtins.print(
        "Warning: Console/theme not found, using standard print for save_json messages."
    )
    LOG_FUNC = builtins.print
    console = None  # Indicate console is not available


# MARK: - SAVE JSON FUNCTION


# & - def save_json(data: Union[dict[str, Any], List[Any]], filepath: Union[str, Path]) -> bool:
def save_json(data: Union[dict[str, Any], List[Any]], filepath: Union[str, Path]) -> bool:
    """Saves Python data (dict or list) to a JSON file with pretty printing.

    Ensures the output directory exists. Handles potential JSON serialization
    errors and file I/O errors, printing messages using the themed console if
    available, otherwise standard print.

    Args:
        data: The Python dictionary or list to save.
        filepath: The full path (including filename and .json extension) for
                  the output file, as a string or Path object.

    Returns:
        bool: True if saving was successful, False otherwise.
    """
    if not isinstance(filepath, Path):
        filepath = Path(filepath)  # Convert string path to Path object

    try:
        # Create parent directory(ies) if they don't exist
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Write the file with UTF-8 encoding and indentation
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # Use LOG_FUNC (either console.print or builtins.print)
        if console:
            # Use theme style 'success' and 'file'
            LOG_FUNC(f"[success]Successfully saved data to:[/success] [file]'{filepath}'[/]")
        else:
            LOG_FUNC(f"Successfully saved data to: '{filepath}'")
        return True

    except TypeError as e:
        # Handle non-serializable data
        msg = f"Data structure not JSON serializable for '{filepath}'. {e}"
        if console:
            LOG_FUNC(f"[error]Error:[/error] {msg}", style="error")
        else:
            LOG_FUNC(f"ERROR: {msg}")
        return False

    except OSError as e:
        # Handle file system errors
        msg = f"Could not write file '{filepath}': {e}"
        if console:
            LOG_FUNC(f"[error]Error:[/error] {msg}", style="error")
        else:
            LOG_FUNC(f"ERROR: {msg}")
        return False

    except Exception as e:
        # Catch any other unexpected errors
        msg = f"An unexpected error occurred saving to '{filepath}': {e}"
        if console:
            LOG_FUNC(f"[error]Error:[/error] {msg}", style="error")
            # Optional: Print traceback for unexpected errors if console exists
            # console.print_exception(show_locals=False)
        else:
            LOG_FUNC(f"ERROR: {msg}")
        return False
