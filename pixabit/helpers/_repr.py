# pixabit/helpers/_repr.py

# SECTION: MODULE DOCSTRING
"""Provides a function to generate a generic, readable string representation for objects.

Includes the class name and non-private attributes with their values,
useful for debugging and simple object inspection.
"""

# SECTION: IMPORTS
import inspect
from typing import (  # Keep get_type_hints if potentially useful
    Any,
    get_type_hints,
)

# SECTION: FUNCTION


# FUNC: generic_repr
def generic_repr(obj: Any) -> str:
    """Generates a string representation of an object for debugging.

    Includes the class name and non-private/non-callable attributes.
    Limits the representation length of values for readability.

    Args:
        obj: The object to represent.

    Returns:
        A string in the format "ClassName(attr1=value1, attr2='value2', ...)"
        or "None" if the object is None.
    """
    if obj is None:
        return "None"

    class_name = obj.__class__.__name__
    attributes: list[str] = []
    max_repr_len = 50  # Max length for value representation

    # Inspect members of the object
    for name, value in inspect.getmembers(obj):
        # Skip private attributes (starting with '_')
        # Skip methods and functions
        if name.startswith("_") or inspect.isroutine(value):
            # isroutine covers methods, functions, built-in functions, etc.
            continue

        # Represent the value, handling potential errors and limiting length
        try:
            if isinstance(value, (list, tuple, dict, set)) and len(value) > 5:
                # Show length for long collections instead of full repr
                value_repr = f"{type(value).__name__}[len={len(value)}]"
            else:
                value_repr = repr(value)

            # Truncate long representations
            if len(value_repr) > max_repr_len:
                value_repr = value_repr[:max_repr_len] + "..."

            attributes.append(f"{name}={value_repr}")

        except Exception:
            # Fallback if getting repr fails
            attributes.append(f"{name}=<Error>")

    # Assemble the final string
    attributes_str = ", ".join(attributes)
    return f"{class_name}({attributes_str})"


# Example Usage (can be removed or kept for testing)
if __name__ == "__main__":

    class Sample:
        def __init__(self):
            self.public_attr = 123
            self.another = "hello world this is a long string"
            self._private_attr = 456
            self.list_attr = [1, 2, 3, 4, 5, 6, 7]
            self.dict_attr = {"a": 1, "b": 2}

        def method(self):
            pass

    s = Sample()
    print(generic_repr(s))
    print(generic_repr(None))
    print(generic_repr([1, 2, 3]))
