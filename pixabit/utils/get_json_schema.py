import json
from pprint import pprint

# Load your JSON data
with open("content_cache_extracted.json", encoding="utf-8") as f:
    data = json.load(f)

# Access the gear_flat dictionary
gear_flat = data["gear_flat"]

# Initialize empty schema to build up
all_fields = set()
field_counts = {}

# First pass: collect all possible fields and count occurrences
for item_key, item in gear_flat.items():
    for field in item.keys():
        all_fields.add(field)
        field_counts[field] = field_counts.get(field, 0) + 1

# Create schema with type information and required status
schema = {}
total_items = len(gear_flat)

for item_key, item in gear_flat.items():
    for field, value in item.items():
        if field not in schema:
            schema[field] = {"type": type(value).__name__, "required": False}
        elif type(value).__name__ != schema[field]["type"]:
            schema[field][
                "type"
            ] = f"mixed ({schema[field]['type']}, {type(value).__name__})"

# Mark fields as required or optional
for field in all_fields:
    # If field appears in all items, mark as required
    schema[field]["required"] = field_counts.get(field, 0) == total_items

# Sort fields by required status (required first, then optional)
sorted_schema = {
    k: v
    for k, v in sorted(
        schema.items(), key=lambda x: (not x[1]["required"], x[0])
    )
}

# Output the schema with required information
print(f"Schema for equipment items (total items: {total_items}):")
print(
    "Required fields are present in all items, optional fields may be missing in some items."
)
print()

# Display fields grouped
print("REQUIRED FIELDS:")
for field, info in sorted_schema.items():
    if info["required"]:
        print(f"  {field}: {info['type']}")

print("\nOPTIONAL FIELDS:")
for field, info in sorted_schema.items():
    if not info["required"]:
        coverage = field_counts.get(field, 0) / total_items * 100
        print(
            f"  {field}: {info['type']} (present in {field_counts.get(field, 0)}/{total_items} items, {coverage:.1f}%)"
        )

# Generate formal JSON Schema
json_schema = {
    "type": "object",
    "required": [field for field, info in schema.items() if info["required"]],
    "properties": {
        key: {
            "type": (
                "string"
                if info["type"] == "str"
                else (
                    "integer"
                    if info["type"] == "int"
                    else (
                        "number"
                        if info["type"] in ["float", "int"]
                        else "boolean" if info["type"] == "bool" else "object"
                    )
                )
            )
        }
        for key, info in schema.items()
    },
}

print("\nJSON Schema format:")
pprint(json_schema)
import json
from pprint import pprint
from typing import Any, Dict, Set


def analyze_field_types(
    data_dict: Dict[str, Any], field_counts: Dict[str, int] = None
) -> Dict[str, Any]:
    """Recursively analyze a dictionary to build a schema.
    Returns a dictionary with schema information including nested objects.
    """
    schema = {}

    for key, value in data_dict.items():
        if isinstance(value, dict):
            # Recursively analyze nested objects
            schema[key] = {
                "type": "object",
                "properties": analyze_field_types(value),
            }
        elif isinstance(value, list):
            # Handle arrays
            if value and all(isinstance(item, dict) for item in value):
                # If array of objects, analyze the structure of objects
                array_schema = {}
                for item in value:
                    item_schema = analyze_field_types(item)
                    # Merge schemas from different array items
                    for field, field_info in item_schema.items():
                        if field not in array_schema:
                            array_schema[field] = field_info
                schema[key] = {
                    "type": "array",
                    "items": {"type": "object", "properties": array_schema},
                }
            elif value:
                # Determine type of first item for non-empty arrays
                item_type = type(value[0]).__name__
                schema[key] = {"type": "array", "items": {"type": item_type}}
            else:
                # Empty array
                schema[key] = {"type": "array", "items": {"type": "unknown"}}
        else:
            # Simple values
            schema[key] = {"type": type(value).__name__}

    return schema


def determine_required_fields(items: Dict[str, Dict]) -> Dict[str, Dict]:
    """Determine which fields are required by analyzing multiple dictionary items."""
    all_fields = set()
    field_counts = {}
    total_items = len(items)

    # First collect all possible fields
    for item_key, item in items.items():
        for field in item.keys():
            all_fields.add(field)
            field_counts[field] = field_counts.get(field, 0) + 1

    # Build schema with required information
    schema = {}
    for field in all_fields:
        is_required = field_counts.get(field, 0) == total_items
        schema[field] = {
            "required": is_required,
            "count": field_counts.get(field, 0),
        }

    return schema, total_items


def merge_type_and_required_info(
    type_schema: Dict, required_info: Dict, total: int
) -> Dict:
    """Merge type information with required field information."""
    merged_schema = {}

    for field, type_info in type_schema.items():
        required_data = required_info.get(
            field, {"required": False, "count": 0}
        )

        if isinstance(type_info, dict) and "type" in type_info:
            # Simple field
            merged_schema[field] = {
                **type_info,
                "required": required_data["required"],
                "coverage": f"{required_data['count']}/{total} ({required_data['count']/total*100:.1f}%)",
            }
        else:
            # This field's value is already a complex structure (object/array)
            merged_schema[field] = {
                **type_info,
                "required": required_data["required"],
                "coverage": f"{required_data['count']}/{total} ({required_data['count']/total*100:.1f}%)",
            }

    return merged_schema


# Main process
def get_complete_schema(data):
    # Get the gear items from the structure
    gear_flat = data["gear_flat"]

    # First analyze the field requirements
    required_info, total_items = determine_required_fields(gear_flat)

    # Then analyze first item for type info (including nested objects)
    first_item_key = next(iter(gear_flat))
    first_item = gear_flat[first_item_key]
    type_schema = analyze_field_types(first_item)

    # For each field that is an object, check across other items as well
    for item_key, item in gear_flat.items():
        if item_key == first_item_key:
            continue
        for field, value in item.items():
            if field in type_schema and isinstance(value, dict):
                # If it's not already represented as an object, update it
                if (
                    isinstance(type_schema[field], dict)
                    and type_schema[field].get("type") != "object"
                ):
                    nested_schema = analyze_field_types({field: value})
                    type_schema[field] = nested_schema[field]

    # Merge type and required info
    complete_schema = merge_type_and_required_info(
        type_schema, required_info, total_items
    )

    return complete_schema, total_items


# Load data and get schema
with open("content_Cache_Extracted.json", encoding="utf-8") as f:
    data = json.load(f)

schema, total_items = get_complete_schema(data)

# Format and display results
print(f"Complete schema analysis (total items: {total_items}):")
pprint(schema)
