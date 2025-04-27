# pixabit/helpers/_json.py
# ─── Helper ───────────────────────────────────────────────────────────────────
#                JSON Save/Load Utilities
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Provides utility functions for saving and loading Python data to/from JSON files.

Includes pretty printing, UTF-8 encoding, directory creation, and error handling.
Uses the application's configured logger. Supports saving/loading Pydantic models.
"""

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
JSONSerializable = dict[str, Any] | list[Any]  # Consistent typing
LoadResult = JSONSerializable | None

# SECTION: HELPER FUNCTIONS


# FUNC: _resolve_path
def _resolve_path(filepath: str | Path, folder: str | Path | None = None) -> Path:
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
            json.dump(
                data, f, indent=indent, ensure_ascii=ensure_ascii, default=str
            )  # Added default=str for non-serializable types like datetime if not handled by caller

        log.info(f"Successfully saved JSON data to: '{output_path}'")
        return True

    except TypeError as e:
        log.error(f"Data structure not JSON serializable for '{output_path}'. Check for non-standard types (like datetime). Error: {e}")
        return False
    except OSError as e:
        log.error(f"Could not write file '{output_path}'. Error: {e}")
        return False
    except Exception as e:
        log.exception(f"An unexpected error occurred saving to '{output_path}': {e}")  # Log full traceback for unexpected errors
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
            log.warning(f"Invalid data type ({type(data).__name__}) in JSON file: '{input_path}'. Expected dict or list.")
            return None

    except (OSError, json.JSONDecodeError) as e:
        log.error(f"Failed to load or parse JSON file '{input_path}'. Error: {e}")
        return None
    except Exception as e:
        log.exception(f"An unexpected error occurred loading '{input_path}': {e}")  # Log full traceback for unexpected errors
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
        log.error("Invalid input: 'model' must be a Pydantic BaseModel instance.")
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

    except ValidationError as e:  # Should not happen during dump, but belt-and-suspenders
        log.error(f"Pydantic validation error during model dump for '{output_path}'. Error: {e}")
        return False
    except TypeError as e:
        log.error(f"Data structure from model dump not JSON serializable for '{output_path}'. Error: {e}")
        return False
    except OSError as e:
        log.error(f"Could not write file '{output_path}'. Error: {e}")
        return False
    except Exception as e:
        log.exception(f"An unexpected error occurred saving Pydantic model to '{output_path}': {e}")  # Log full traceback for unexpected errors
        return False


# FUNC: load_pydantic_model
def load_pydantic_model(
    model_class: Type[T_BaseModel],
    filepath: str | Path,
    folder: str | Path | None = None,
    context: dict[str, Any] | None = None,  # Added context parameter
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
        log.warning(f"JSON data loaded from '{input_path}' is not a dictionary, cannot parse into {model_class.__name__}.")
        return None

    log.debug(f"Attempting to validate JSON into Pydantic model {model_class.__name__} from '{input_path}'")
    try:
        # Use model_validate for Pydantic V2
        instance = model_class.model_validate(data, context=context)  # Pass context here

        log.debug(f"Successfully validated JSON into Pydantic model {model_class.__name__}")
        return instance

    except ValidationError as e:
        log.error(f"Pydantic validation failed for {model_class.__name__} from '{input_path}':\n{e}")
        return None
    except Exception as e:
        log.exception(f"An unexpected error occurred parsing JSON into Pydantic model {model_class.__name__} from '{input_path}': {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
