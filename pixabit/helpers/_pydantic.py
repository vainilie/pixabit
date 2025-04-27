# pixabit/helpers/_pydantic.py

# SECTION: MODULE DOCSTRING
"""Helper utilities for working consistently with Pydantic models.

Provides a configured base model, common validators (if any added later),
enums, version detection, and utility functions compatible with Pydantic V1 & V2.
"""

# SECTION: IMPORTS
from datetime import datetime  # Keep if used by models or future validators
from enum import Enum
from pathlib import Path
from typing import (  # Use | in Python 3.10+
    Any,
    Generic,
    Type,
    TypeVar,
    Union,
    cast,
    get_type_hints,  # Keep if introspection needed later
)

# Import appropriate Pydantic version and handle potential ImportError
# SECTION: PYDANTIC VERSION HANDLING
try:
    # Pydantic V2+
    from pydantic import (
        BaseModel as PydanticBaseModel,  # Alias to avoid potential conflicts
    )
    from pydantic import (
        ConfigDict,
        Field,
        ValidationError,
        create_model,
        field_validator,
        model_validator,
        v1,  # Import v1 compatibility layer if needed elsewhere
    )
    from pydantic.json import pydantic_encoder  # V2 compatible

    PYDANTIC_V2 = True
    BaseModel = PydanticBaseModel  # Use the alias

except ImportError:
    # Pydantic V1 fallback
    from pydantic import (
        BaseConfig,  # V1 config class
        Field,
        ValidationError,
        create_model,
        validator,  # V1 validator decorator
    )
    from pydantic import BaseModel as PydanticBaseModel  # Alias
    from pydantic.json import pydantic_encoder  # V1 compatible

    PYDANTIC_V2 = False
    BaseModel = PydanticBaseModel  # Use the alias
    # Define ConfigDict for V1 compatibility if needed by type hints elsewhere
    ConfigDict = dict[str, Any]  # Simple dict type for V1 compatibility


# SECTION: BASE MODEL CONFIGURATION


# KLASS: PixabitBaseModel
class PixabitBaseModel(BaseModel):
    """Base model with consistent configuration for all Pixabit models."""

    if PYDANTIC_V2:
        model_config = ConfigDict(
            arbitrary_types_allowed=True,  # Allow complex types if needed
            extra="ignore",  # Ignore extra fields during parsing
            validate_assignment=True,  # Validate fields when assigned after init
            populate_by_name=True,  # Allow population by field name OR alias
            use_enum_values=True,  # Use enum values by default in serialization
        )
    else:  # Pydantic V1 Config

        class Config(BaseConfig):
            arbitrary_types_allowed = True
            extra = "ignore"  # V1 equivalent: Extra.ignore
            validate_assignment = True
            allow_population_by_field_name = (
                True  # V1 equivalent of populate_by_name
            )
            use_enum_values = True

    # Removed model_dump_safe as standard model_dump/dict() covers exclude


# SECTION: TYPE VARIABLES
T = TypeVar("T", bound=BaseModel)  # Generic type for model operations


# SECTION: COMMON VALIDATORS / UTILITIES


# FUNC: ensure_path (Example validator - keep or remove if unused)
def ensure_path(v: str | Path | Any) -> Path:
    """Converts a string to a Path object if necessary."""
    if isinstance(v, Path):
        return v
    if isinstance(v, str):
        return Path(v)
    # Raise error or return a default if type is wrong?
    raise TypeError("Value must be a string or Path object to ensure Path.")


# Example usage in a model:
# class MyModel(PixabitBaseModel):
#     file_path: Path
#     _validate_path = field_validator("file_path", mode="before")(ensure_path) if PYDANTIC_V2 else validator("file_path", pre=True, allow_reuse=True)(ensure_path)


# SECTION: COMMON ENUMS


# ENUM: StatusEnum
class StatusEnum(str, Enum):
    """Common status values used across models."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"
    UNKNOWN = "unknown"  # Added unknown state


# SECTION: HELPER FUNCTIONS


# FUNC: create_from_dict
def create_from_dict(model_class: Type[T], data: dict[str, Any]) -> T:
    """Creates a Pydantic model instance from a dictionary with validation.

    Handles version differences between Pydantic V1 (parse_obj) and V2+ (model_validate).

    Args:
        model_class: The Pydantic model class (e.g., User, Task).
        data: The dictionary containing data to populate the model.

    Returns:
        An instance of model_class populated with data.

    Raises:
        ValidationError: If the data fails validation against the model.
        TypeError: If 'data' is not a dictionary.
    """
    if not isinstance(data, dict):
        raise TypeError(
            f"Input data must be a dictionary to create {model_class.__name__}"
        )
    try:
        if PYDANTIC_V2:
            # Pydantic V2+ uses model_validate
            return model_class.model_validate(data)
        else:
            # Pydantic V1 uses parse_obj
            return model_class.parse_obj(data)  # type: ignore[attr-defined]
    except ValidationError as e:
        # Customize the error message slightly if desired
        # print(f"Validation Error for {model_class.__name__}: {e}") # Debug print
        raise e  # Re-raise the original validation error
    except Exception as e:
        # Catch other potential errors during instantiation
        raise TypeError(f"Error creating {model_class.__name__}: {e}") from e


# FUNC: model_to_dict
def model_to_dict(
    model: BaseModel,
    exclude_none: bool = True,
    by_alias: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """Converts a Pydantic model instance to a dictionary.

    Handles version differences between Pydantic V1 (dict) and V2+ (model_dump).

    Args:
        model: The Pydantic model instance.
        exclude_none: Whether to exclude fields with None values.
        by_alias: Whether to use field aliases in the output dictionary keys.
        **kwargs: Additional arguments passed to dict() or model_dump().

    Returns:
        A dictionary representation of the model.

    Raises:
        TypeError: If 'model' is not a Pydantic BaseModel instance.
    """
    if not isinstance(model, BaseModel):
        raise TypeError("Input must be a Pydantic BaseModel instance.")
    try:
        if PYDANTIC_V2:
            # Pydantic V2+ uses model_dump
            return model.model_dump(
                exclude_none=exclude_none, by_alias=by_alias, **kwargs
            )
        else:
            # Pydantic V1 uses dict
            # Note: V1's dict() doesn't have all the same kwargs as V2's model_dump
            return model.dict(  # type: ignore[attr-defined]
                exclude_none=exclude_none, by_alias=by_alias, **kwargs
            )
    except Exception as e:
        raise TypeError(
            f"Error converting model {type(model).__name__} to dict: {e}"
        ) from e


# SECTION: EXPORTS
__all__ = [
    # Pydantic Core Re-exports (for convenience)
    "BaseModel",
    "Field",
    "ValidationError",
    "create_model",
    # Custom Base Model
    "PixabitBaseModel",
    # Version detection and specific decorators/types
    "PYDANTIC_V2",
    "ConfigDict",  # Available for both V1 (as dict) and V2
    *(["model_validator", "field_validator"] if PYDANTIC_V2 else ["validator"]),
    # Common Utilities / Enums
    "ensure_path",  # Example validator
    "StatusEnum",
    "create_from_dict",
    "model_to_dict",
    "pydantic_encoder",  # JSON encoder helper
]
