# pixabit/utils/generic_repr.py

# SECTION: MODULE DOCSTRING
"""Provides a function to generate a generic string representation for any object.

Includes the class name and non-private attributes with their values.
Useful for debugging and simple object inspection.
"""

# SECTION: IMPORTS
import inspect
from typing import Any, get_type_hints  # Added Optional

# SECTION: FUNCTION


# FUNC: generic_repr
def generic_repr(obj: Any) -> str:
    """Generates a string representation of an object, including its class name and attributes.

    Excludes methods, private attributes (starting with '_'), and functions.
    Attempts to represent common types like lists, tuples, and dicts clearly.

    Args:
        obj: The object to represent.

    Returns:
        A string representation in the format "ClassName(attr1=value1, attr2='value2', ...)".
    """
    if obj is None:
        return "None"

    class_name = obj.__class__.__name__
    attributes: list[str] = []  # Use built-in generic list[str]

    # Attempt to get type hints, but don't fail if it's not possible
    try:
        type_hints = get_type_hints(obj.__class__)
    except Exception:
        type_hints = {}  # noqa: F841

    # Iterate through members
    for name, value in inspect.getmembers(obj):
        # Skip private attributes, methods, and functions
        if (
            name.startswith("_")
            or inspect.ismethod(value)
            or inspect.isfunction(value)
        ):
            continue

        # Basic type representation
        try:
            if isinstance(value, str):
                # Add quotes for strings, limit length for readability
                display_val = value[:50] + "..." if len(value) > 50 else value
                attributes.append(f"{name}='{display_val}'")
            elif isinstance(value, (list, tuple, dict, set)):
                # Use standard repr for collections, might be long
                attributes.append(f"{name}={repr(value)}")
            else:
                # Use standard repr for other types (numbers, booleans, None, custom objects)
                attributes.append(f"{name}={repr(value)}")
        except Exception:
            attributes.append(f"{name}=<Error getting value>")  # Safe fallback

    return f"{class_name}({', '.join(attributes)})"
