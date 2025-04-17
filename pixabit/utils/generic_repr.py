import inspect
from typing import Any, List, Optional, get_type_hints


def generic_repr(obj: Any) -> str:
    """Generates a string representation of an object, including its class name
    and attributes.

    Args:
        obj: The object to represent.

    Returns:
        A string representation of the object.
    """
    class_name = obj.__class__.__name__
    attributes = []
    type_hints = get_type_hints(obj.__class__)  # Get type hints for attributes

    for name, value in inspect.getmembers(obj):
        if name.startswith("_") or inspect.ismethod(value) or inspect.isfunction(value):
            continue  # Skip private attributes and methods

        if name in type_hints:
            hint = type_hints[name]
        else:
            hint = None

        try:
            # Handle different data types for better representation
            if isinstance(value, str):
                attributes.append(f"{name}='{value}'")
            elif isinstance(value, (list, tuple)):
                attributes.append(f"{name}={value}")
            elif isinstance(value, dict):
                attributes.append(f"{name}={value}")
            else:
                attributes.append(f"{name}={repr(value)}")  # Use repr for other types
        except Exception:
            attributes.append(f"{name}=<unknown>")  # Safe fallback

    return f"{class_name}({', '.join(attributes)})"


class MyClass:
    def __init__(self, name: str, age: int, data: Optional[List[str]] = None):
        self.name = name
        self.age = age
        self.data = data
        self._private = "secret"  # Private attribute (will be skipped)

    def my_method(self):
        pass  # Method (will be skipped)


if __name__ == "__main__":
    my_object = MyClass("Alice", 30, ["a", "b"])
    print(generic_repr(my_object))
