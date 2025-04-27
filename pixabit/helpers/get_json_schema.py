# pixabit/helpers/_get_json_schema.py

# SECTION: MODULE DOCSTRING
"""Utility Script for Generating a Schema from Habitica Content Data.

NOTE: This script is likely intended for one-off schema generation or analysis
      based on an existing JSON file (e.g., 'content_cache_extracted.json').
      It's probably NOT part of the main runtime application logic.

Analyzes the structure of a nested dictionary (expected to be Habitica's
`gear_flat` data) to infer field types, required status, and generate a
basic JSON schema representation.
"""

# SECTION: IMPORTS
import json
from pprint import pprint
from typing import (  # Keep Dict/Set for internal hints if preferred
    Any,
    Dict,
    Set,
    cast,
)

# SECTION: FUNCTIONS


# FUNC: analyze_field_types
def analyze_field_types(data_dict: dict[str, Any]) -> dict[str, Any]:
    """Recursively analyzes a dictionary to build a schema with type information.

    Handles nested objects and arrays of objects or simple types.

    Args:
        data_dict: The dictionary item to analyze.

    Returns:
        A dictionary representing the inferred schema structure and types.
    """
    schema: dict[str, Any] = {}

    for key, value in data_dict.items():
        value_type = type(value).__name__

        if isinstance(value, dict):
            # Recursively analyze nested objects
            schema[key] = {
                "type": "object",
                "properties": analyze_field_types(value),
            }
        elif isinstance(value, list):
            # Handle arrays
            if value:
                # Get type of first item for non-empty arrays
                first_item_type = type(value[0]).__name__
                if first_item_type == "dict":
                    # If array of objects, analyze the structure of the *first* object
                    # Assumes homogeneous array structure for simplicity
                    item_schema = analyze_field_types(value[0])
                    schema[key] = {
                        "type": "array",
                        "items": {"type": "object", "properties": item_schema},
                    }
                else:
                    # Array of simple types
                    schema[key] = {
                        "type": "array",
                        "items": {"type": first_item_type},
                    }
            else:
                # Empty array - type unknown
                schema[key] = {"type": "array", "items": {"type": "unknown"}}
        else:
            # Simple scalar values
            schema[key] = {"type": value_type}

    return schema


# FUNC: determine_required_fields
def determine_required_fields(
    items: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], int]:
    """Determines which top-level fields are required by analyzing multiple dictionary items.

    A field is considered required if it exists in every item provided.

    Args:
        items: A dictionary where keys are item IDs and values are the item data dictionaries.

    Returns:
        A tuple containing:
            - A dictionary mapping field names to requirement info ({'required': bool, 'count': int}).
            - The total number of items analyzed.
    """
    all_fields: set[str] = set()
    field_counts: dict[str, int] = {}
    total_items = len(items)

    if total_items == 0:
        return {}, 0

    # First pass: collect all possible top-level fields and count occurrences
    for item_data in items.values():
        if not isinstance(item_data, dict):
            continue  # Skip invalid items
        for field in item_data.keys():
            all_fields.add(field)
            field_counts[field] = field_counts.get(field, 0) + 1

    # Build schema part with required information
    required_info: dict[str, dict[str, Any]] = {}
    for field in all_fields:
        count = field_counts.get(field, 0)
        is_required = count == total_items
        required_info[field] = {"required": is_required, "count": count}

    return required_info, total_items


# FUNC: merge_type_and_required_info
def merge_type_and_required_info(
    type_schema: dict[str, Any],
    required_info: dict[str, dict[str, Any]],
    total_items: int,
) -> dict[str, Any]:
    """Merges the inferred type schema with the required field information.

    Args:
        type_schema: The schema dictionary containing type information (from analyze_field_types).
        required_info: The dictionary containing required status and counts for fields.
        total_items: The total number of items analyzed.

    Returns:
        A merged schema dictionary containing type, requirement status, and coverage percentage.
    """
    merged_schema: dict[str, Any] = {}

    for field, type_info in type_schema.items():
        req_data = required_info.get(field, {"required": False, "count": 0})
        coverage_str = (
            f"{req_data['count']}/{total_items} ({req_data['count']/total_items*100:.1f}%)"
            if total_items > 0
            else "N/A"
        )

        # Combine the type info with required status and coverage
        merged_schema[field] = {
            **type_info,  # includes 'type' and potentially 'properties' or 'items'
            "required": req_data["required"],
            "coverage": coverage_str,
        }

    return merged_schema


# FUNC: get_complete_schema
def get_complete_schema(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Generates a comprehensive schema by analyzing item structure and requirement frequency.

    Args:
        data: The full loaded JSON data containing the target dictionary (e.g., 'gear_flat').

    Returns:
        A tuple containing:
            - The generated schema dictionary.
            - The total number of items analyzed.

    Raises:
        KeyError: If the expected data key (e.g., 'gear_flat') is not found.
        TypeError: If the data under the key is not a dictionary.
    """
    # --- Target the specific dictionary to analyze ---
    # Modify this key if analyzing a different part of the JSON
    target_key = "gear_flat"
    items_dict = data.get(target_key)

    if items_dict is None:
        raise KeyError(f"Key '{target_key}' not found in the input data.")
    if not isinstance(items_dict, dict):
        raise TypeError(f"Data under key '{target_key}' must be a dictionary.")
    # --- End Target ---

    # Analyze field requirements across all items
    required_info, total_items = determine_required_fields(items_dict)

    # Analyze the structure (types, nesting) based on the *first* item
    # Assumes structure is relatively consistent across items
    if not items_dict:
        return {}, 0  # Handle empty input dict

    first_item_key = next(iter(items_dict))
    first_item = items_dict[first_item_key]
    type_schema = analyze_field_types(first_item)

    # Merge the type information with requirement info
    complete_schema = merge_type_and_required_info(
        type_schema, required_info, total_items
    )

    return complete_schema, total_items


# SECTION: MAIN EXECUTION (EXAMPLE)


# FUNC: main_schema_generation
def main_schema_generation(
    input_json_path: str = "content_cache_extracted.json",
    output_schema_path: str | None = "generated_schema.json",
):
    """Loads data, generates schema, prints, and optionally saves the schema."""
    print("--- Schema Generation Utility ---")
    print(f"Input JSON: {input_json_path}")

    try:
        # Load the source JSON data
        with open(input_json_path, encoding="utf-8") as f:
            data = json.load(f)
        print("Input JSON loaded successfully.")

        # Generate the schema
        schema, total_items = get_complete_schema(data)
        print(f"\nSchema analysis complete. Analyzed {total_items} items.")

        # Display the schema using pprint
        print("\n--- Generated Schema ---")
        pprint(
            schema, sort_dicts=False
        )  # sort_dicts=False preserves order more often

        # Optionally save the schema to a file
        if output_schema_path:
            try:
                with open(output_schema_path, "w", encoding="utf-8") as f_out:
                    json.dump(schema, f_out, indent=2, ensure_ascii=False)
                print(f"\nSchema saved to: {output_schema_path}")
            except Exception as e:
                print(f"\nError saving schema to {output_schema_path}: {e}")

    except FileNotFoundError:
        print(f"\nError: Input JSON file not found at '{input_json_path}'")
    except (KeyError, TypeError) as e:
        print(f"\nError processing input data: {e}")
    except json.JSONDecodeError:
        print(f"\nError: Invalid JSON format in '{input_json_path}'")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")


if __name__ == "__main__":
    # --- Configuration ---
    INPUT_JSON_FILE = "content_cache_extracted.json"  # Source data file name
    OUTPUT_SCHEMA_FILE = (
        "generated_schema.json"  # Output file name (or None to just print)
    )
    # --- End Configuration ---

    main_schema_generation(
        input_json_path=INPUT_JSON_FILE, output_schema_path=OUTPUT_SCHEMA_FILE
    )
