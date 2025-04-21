# Parse list of Tag models from JSON string
from __future__ import (
    annotations,  # Allows using type hints for classes defined later in the file
)

# --- Python Standard Library Imports ---
import inspect  # Used for introspection (getting object members) in generic_repr
import json  # Used for loading data from JSON files/strings
import re  # Used for regular expression operations (finding attribute symbols)
from collections import defaultdict  # Used for grouping tags by parent in TagList
from typing import (  # Provides type hinting capabilities
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    get_type_hints,
)

# --- Third-Party Library Imports ---
import tomllib  # Used for parsing TOML configuration files (introduced in Python 3.11, might need 'pip install tomli' for older versions)

# Use parse_raw_as to go straight from JSON string to list of Tags
# Pydantic is used for data validation and parsing
from pydantic import (  # Specific components from Pydantic
    BaseModel,
    TypeAdapter,
    model_validator,
    parse_obj_as,
)

# SECTION: UTILITY FUNCTION


# FUNC: generic_repr
def generic_repr(obj: Any) -> str:
    """Generates a concise string representation of an object for debugging.

    Includes the object's class name and its public attributes (those not
    starting with '_'). It excludes methods and functions associated with
    the object. Attempts to provide readable representations for common
    collection types and truncates long strings.

    Args:
        obj: The object to generate a representation for.

    Returns:
        A string in the format "ClassName(attr1=value1, attr2='value2', ...)".
        Returns "None" if the input object is None.
    """
    # Handle the case where the input object is None
    if obj is None:
        return "None"

    # Get the name of the object's class
    class_name = obj.__class__.__name__
    # Initialize an empty list to store attribute strings "name=value"
    attributes: list[str] = []

    # Attempt to get type hints for the class. This is optional and might fail
    # for some objects, so we wrap it in a try-except block.
    # Note: type_hints are not actually used in the current implementation but kept from original.
    try:
        type_hints = get_type_hints(obj.__class__)  # noqa: F841 - Variable assigned but not used
    except Exception:
        type_hints = {}  # Use an empty dict as a fallback

    # Iterate through all members (attributes, methods, etc.) of the object
    for name, value in inspect.getmembers(obj):
        # Skip members whose names start with an underscore (convention for private/internal)
        # Also skip members that are methods or functions
        if name.startswith("_") or inspect.ismethod(value) or inspect.isfunction(value):
            continue

        # Try to create a readable representation for the attribute's value
        try:
            if isinstance(value, str):
                # For strings, add quotes. If longer than 50 chars, truncate for readability.
                display_val = value[:50] + "..." if len(value) > 50 else value
                attributes.append(f"{name}='{display_val}'")
            elif isinstance(value, (list, tuple, dict, set)):
                # For common collections, use their standard repr (which might be long).
                attributes.append(f"{name}={repr(value)}")
            else:
                # For other types (int, float, bool, None, custom objects), use standard repr.
                attributes.append(f"{name}={repr(value)}")
        except Exception:
            # If getting the value's representation fails for any reason, add a placeholder.
            attributes.append(f"{name}=<Error getting value>")  # Safe fallback

    # Combine the class name and attribute strings into the final representation
    return f"{class_name}({', '.join(attributes)})"


# --- Configuration Maps and Constants ---

# Maps special symbols found in tag text to short attribute names
ATTRIBUTE_SYMBOL_MAP: dict[str, str] = {
    "🜄": "con",  # Example: Water symbol might map to Constitution
    "🜂": "str",  # Example: Fire symbol might map to Strength
    "🜁": "int",  # Example: Air symbol might map to Intelligence
    "🜃": "per",  # Example: Earth symbol might map to Perception
    "᛭": "legacy",  # Example: Nordic cross symbol might map to Legacy
}

# Maps configuration keys (expected in TOML file) to short attribute names
# These likely correspond to the IDs of parent tags representing core attributes.
ATTRIBUTE_MAP: dict[str, str] = {
    "ATTR_TAG_STR_ID": "str",
    "ATTR_TAG_INT_ID": "int",
    "ATTR_TAG_CON_ID": "con",
    "ATTR_TAG_PER_ID": "per",
    "LEGACY_TAG_ID": "legacy",
    "CHALLENGE_TAG_ID": "challenge",  # Note: 'challenge' is also a boolean field in Tag model
    "PERSONAL_TAG_ID": "personal",  # Note: 'personal' isn't directly used in the Tag model fields provided
}

# Precompile the regular expression for efficiency.
# This regex looks for any single character that is a key in ATTRIBUTE_SYMBOL_MAP.
ATTRIBUTE_SYMBOL_REGEX = re.compile(f"([{ ''.join(ATTRIBUTE_SYMBOL_MAP.keys()) }])")


# SECTION: PYDANTIC MODELS FOR TAGS


# KLASS TAG BASE MODEL
class Tag(BaseModel):
    """Represents a basic tag with common attributes.

    Attributes:
        id (str): The unique identifier for the tag.
        text (str): The display text of the tag.
        challenge (Optional[bool]): Flag indicating if the tag is a challenge (default: False).
        neko (Optional[bool]): A specific flag, purpose might be domain-specific (default: None).
        parent (Optional[str]): The ID of the parent tag, if this is a subtag (default: None).
        tag_type (Optional[str]): The type of the tag ('base', 'parent', 'sub') (default: 'base').
        attribute (Optional[str]): The associated attribute (e.g., 'str', 'int'), often inherited from parent (default: 'str').
        category (Optional[str]): A category for display/grouping (default: None).
        position (Optional[int]): An integer for sorting/ordering tags (default: None).
    """

    id: str
    text: str
    challenge: bool | None = False  # Default to False if not provided
    neko: bool | None = None  # Default to None if not provided
    parent: str | None = None  # Default to None if not provided
    tag_type: str | None = "base"  # Default type
    attribute: str | None = "str"  # Default attribute, might be overridden
    category: str | None = None  # Optional category for display
    position: int | None = None  # Optional position for ordering

    @model_validator(mode="before")
    @classmethod
    def _prepend_category_to_text(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pydantic validator run before creating the model instance.

        If a 'category' is provided and 'text' doesn't already start with
        a bracketed prefix (like '[Category]'), it prepends the category
        to the text field.

        Args:
            values (Dict[str, Any]): The dictionary of raw values before validation.

        Returns:
            Dict[str, Any]: The potentially modified dictionary of values.
        """
        # Check if 'category' and 'text' keys exist in the input data
        if "category" in values and "text" in values:
            # Check if the text doesn't already start with '[' (indicating a manual prefix)
            if not values["text"].startswith("["):
                # Prepend the category in brackets to the text
                values["text"] = f"[{values['category']}] {values['text']}"
        # Return the (potentially modified) values dictionary
        return values

    # Override the default __repr__ to use the custom generic_repr function
    def __repr__(self) -> str:
        """Returns a developer-friendly representation of the Tag object."""
        return generic_repr(self)


# KLASS SUBCLASSES (MOMTAG, SUBTAG)
class MomTag(Tag):
    """Represents a parent tag, typically corresponding to a core attribute.

    Inherits from Tag and overrides `tag_type` to 'parent'.
    """

    tag_type: str = "parent"  # Hardcode tag_type for MomTag instances

    def is_parent(self) -> bool:
        """Checks if this tag is a parent tag. Always returns True."""
        return True

    def get_base_name(self) -> str:
        """Returns the text of the parent tag, considered its base name."""
        return self.text


class SubTag(Tag):
    """Represents a subtag, usually associated with a parent MomTag.

    Inherits from Tag and overrides `tag_type` to 'sub'.
    Requires a `parent` ID.
    """

    tag_type: str = "sub"  # Hardcode tag_type for SubTag instances

    def is_subtag(self) -> bool:
        """Checks if this tag is a subtag. Always returns True."""
        return True

    def get_parent_id(self) -> str | None:
        """Returns the ID of the parent tag this subtag belongs to."""
        # The 'parent' attribute is inherited from the base Tag class
        return self.parent


# KLASS TAGFACTORY (BUILDS TAGS)
class TagFactory:
    """Factory class responsible for creating Tag, MomTag, or SubTag instances.

    Reads configuration from a TOML file to understand the relationships
    between tag IDs, names, and attributes. Determines the correct tag type
    based on ID or symbols in the text.

    Attributes:
        name_to_id (Dict[str, str]): Maps long configuration names (e.g., "ATTR_TAG_STR_ID") to tag IDs.
        attribute (Dict[str, str]): Maps configuration keys to short attribute names (e.g., "str").
        id_to_shortname (Dict[str, str]): Maps tag IDs back to short attribute names (redundant with id_to_attribute but present).
        id_to_attribute (Dict[str, str]): Maps tag IDs (specifically parent tag IDs) to their associated attribute name (e.g., 'abc123id' -> 'str').
        id_to_name (Dict[str, str]): Maps tag IDs back to long configuration names.
    """

    def __init__(self, config_path: str):
        """Initializes the TagFactory by loading configuration from a TOML file.

        Args:
            config_path (str): The path to the TOML configuration file (e.g., "tags.toml").

        Raises:
            FileNotFoundError: If the config_path does not exist.
            tomllib.TOMLDecodeError: If the TOML file is invalid.
        """
        # Open the configuration file in binary read mode ('rb') as required by tomllib
        with open(config_path, "rb") as f:
            # Load the TOML data into a dictionary
            data = tomllib.load(f)

        # Store the 'tags' section from the TOML file, mapping long names -> IDs
        # Example: {"ATTR_TAG_STR_ID": "tagid123", ...}
        self.name_to_id: Dict[str, str] = data.get("tags", {})  # Use .get for safety

        # Store the predefined mapping of config keys -> short attribute names
        self.attribute: Dict[str, str] = ATTRIBUTE_MAP

        # TODO: Redundancy: The self.id_to_shortname map seems entirely redundant given self.id_to_attribute. They are built almost identically and map the same IDs to the same short attribute names. I would remove self.id_to_shortname entirely.
        # Create a mapping from tag ID -> short attribute name (for parent tags)
        # Iterates through the attribute map, finds the corresponding ID from name_to_id,
        # and maps that ID to the short name (e.g., "tagid123": "str")
        # Note: This seems redundant with self.id_to_attribute
        self.id_to_shortname: Dict[str, str] = {
            self.name_to_id[long_name]: short_name
            for long_name, short_name in self.attribute.items()
            # Only include if the long_name exists in the loaded config tags
            if long_name in self.name_to_id
        }

        # Create a mapping from tag ID -> short attribute name (primary map used later)
        # Similar to id_to_shortname, but directly uses ATTRIBUTE_MAP
        # Example: {"tagid123": "str", "tagid456": "int", ...}
        self.id_to_attribute: Dict[str, str] = {
            # Get the ID associated with the config name (e.g., "ATTR_TAG_STR_ID")
            self.name_to_id.get(config_name): attr
            # Iterate through the predefined config name -> attribute mapping
            for config_name, attr in ATTRIBUTE_MAP.items()
            # Ensure the config name was actually found in the loaded TOML data
            if config_name in self.name_to_id
        }

        # Create a reverse mapping from tag ID -> long configuration name
        # Example: {"tagid123": "ATTR_TAG_STR_ID", ...}
        self.id_to_name: Dict[str, str] = {v: k for k, v in self.name_to_id.items()}

    # FUNC DETECT TYPE
    def detect_type(self, tag_id: str, tag_text: str) -> tuple[str, str | None]:
        """Determines if a tag should be a MomTag, SubTag, or base Tag.

        - If the tag_id corresponds to a known parent attribute ID, it's a 'mom'.
        - If the tag_text contains a recognized attribute symbol, it's a 'sub',
          and the corresponding parent ID is returned.
        - Otherwise, it's considered a 'base' tag.

        Args:
            tag_id (str): The ID of the tag.
            tag_text (str): The text content of the tag.

        Returns:
            tuple[str, str | None]: A tuple containing:
                - The detected tag type ('mom', 'sub', or 'base').
                - The parent ID if the type is 'sub', otherwise None.
        """
        # Check if the tag_id is a key in the id_to_attribute map (meaning it's a configured parent tag)
        if tag_id in self.id_to_attribute:
            return "mom", None  # It's a parent tag, no parent ID needed

        # If not a parent ID, search for attribute symbols (e.g., 🜄, 🜂) within the tag text
        match = ATTRIBUTE_SYMBOL_REGEX.search(tag_text)
        if match:
            # If a symbol is found, extract it
            symbol = match.group(1)
            # Get the short attribute name corresponding to the symbol (e.g., 'con', 'str')
            attr = ATTRIBUTE_SYMBOL_MAP.get(symbol)
            # If the symbol is valid and maps to an attribute name
            if attr:
                # Find the parent tag's ID by looking for which ID in id_to_attribute
                # maps to the *same* attribute name.
                for parent_id, attr_name in self.id_to_attribute.items():
                    if attr_name == attr:
                        # Found the parent ID based on shared attribute
                        return "sub", parent_id
        # If it's not a MomTag ID and no valid symbol was found, assume it's a base tag
        return "base", None

    def create_tag(self, data: dict, position: int | None = None) -> Tag:
        """Creates a Tag, MomTag, or SubTag instance from raw dictionary data.

        Uses `detect_type` to determine the correct class. Injects attribute
        and category information for parent tags. Assigns the provided position.

        Args:
            data (dict): The raw dictionary containing tag data (e.g., from JSON).
                         Expected keys: 'id', 'text' (or 'name'). Other keys matching
                         Tag model fields are also used.
            position (Optional[int]): The index/position of the tag in the original list,
                                     used for sorting. Defaults to None.

        Returns:
            Tag | MomTag | SubTag: An instance of the appropriate Tag subclass.
        """
        # Extract tag ID from the input dictionary
        tag_id = data.get("id")
        # Use 'text' if available, otherwise fallback to 'name', default to empty string if neither
        # Also update the 'text' field in the original dict for consistency
        data["text"] = data.get("text") or data.get("name", "")
        tag_text = data.get("text", "")  # Get the potentially updated text

        # If a position is provided, add it to the data dictionary
        if position is not None:
            data["position"] = position

        # Determine the tag type ('mom', 'sub', 'base') and potential parent ID
        tag_type, parent_id = self.detect_type(tag_id, tag_text)
        # Look up the attribute associated with this tag's ID (primarily for parent tags)
        attribute = self.id_to_attribute.get(tag_id)

        # If an attribute was found (meaning this is likely a parent tag based on its ID)
        if attribute:
            # Inject the 'attribute' field into the data dictionary
            data["attribute"] = attribute
            # Also use the attribute name as the 'category' by default (can be customized)
            data["category"] = attribute

        # Based on the detected type, create an instance of the corresponding Pydantic model
        if tag_type == "mom":
            # Use MomTag.model_validate (Pydantic v2+) to create and validate
            return MomTag.model_validate(data)
        elif tag_type == "sub":
            # For SubTags, add the determined parent_id to the data before validation
            # Use dictionary unpacking {**data, ...} to merge dictionaries
            return SubTag.model_validate({**data, "parent": parent_id})
        else:  # tag_type == "base"
            # Use the base Tag.model_validate for default tags
            return Tag.model_validate(data)


# KLASS TAGLIST
class TagList(BaseModel):
    """A Pydantic model representing a list of Tag objects.

    Provides utility methods for creating the list from different sources
    (raw data, JSON) and for querying and manipulating the list of tags.

    Attributes:
        tags (List[Tag]): The list containing Tag, MomTag, and SubTag instances.
    """

    # The main data field: a list where each element must be a Tag or its subclass
    tags: List[Tag]

    @classmethod
    def from_raw_data(cls, raw_list: Iterable[dict], factory: TagFactory) -> TagList:
        """Constructs a TagList from an iterable of raw dictionaries using a TagFactory.

        Each dictionary in the iterable is processed by the TagFactory to create
        the appropriate Tag, MomTag, or SubTag instance, including assigning position.

        Args:
            raw_list (Iterable[dict]): An iterable (e.g., list) of dictionaries,
                                       each representing a tag's raw data.
            factory (TagFactory): The TagFactory instance used to create typed tag objects.

        Returns:
            TagList: A new TagList instance containing the processed tags.
        """
        # Use a list comprehension to iterate through the raw data with index (for position)
        # For each item and its index (i), call factory.create_tag to get a typed Tag object
        typed_tags = [factory.create_tag(item, i) for i, item in enumerate(raw_list)]
        # Create and return a new TagList instance using the list of typed tags
        return cls(tags=typed_tags)

    @classmethod
    def from_json_basic(cls, json_str: str) -> TagList:
        """Constructs a TagList directly from a JSON string.

        Uses Pydantic's TypeAdapter for efficient parsing and validation of a list of Tags.
        Note: This method does *not* use the TagFactory and relies solely on Pydantic's
              default parsing based on the Tag model definition (including the validator).
              It might not correctly classify MomTags/SubTags unless `tag_type` is present
              in the JSON or inferred correctly by the base Tag validator.

        Args:
            json_str (str): A JSON string representing a list of tag objects.

        Returns:
            TagList: A new TagList instance parsed from the JSON.
        """
        # Create a Pydantic TypeAdapter for List[Tag]
        # This adapter knows how to parse a JSON list into Python list of Tag objects
        # validate_json parses the string and validates against the Tag model
        parsed_tags = TypeAdapter(List[Tag]).validate_json(json_str)
        # Create and return a new TagList instance using the parsed tags
        return cls(tags=parsed_tags)

    def as_dicts(self) -> List[dict]:
        """Serializes the list of tags back into a list of dictionaries.

        Returns:
            List[dict]: A list where each element is a dictionary representation
                       of a Tag object in the list.
        """
        # Use tag.model_dump() (Pydantic v2+) for each tag to get its dict representation
        return [tag.model_dump() for tag in self.tags]

    def get_parents(self) -> List[MomTag]:
        """Filters the list and returns only the tags that are instances of MomTag.

        Returns:
            List[MomTag]: A list containing only the MomTag objects.
        """
        # List comprehension filtering based on isinstance check
        return [tag for tag in self.tags if isinstance(tag, MomTag)]

    def get_subtags_by_parent_prefix(self, parent_text: str) -> List[SubTag]:
        """Finds subtags whose text starts with the given parent text (case-insensitive).

        This method relies on a naming convention where subtags often have text like
        "Parent Name - Subtag Specifics". It might not be reliable if text format varies.
        Consider using `group_by_parent` which uses the `parent` ID for a more robust link.

        Args:
            parent_text (str): The text of the parent tag to search for.

        Returns:
            List[SubTag]: A list of SubTag objects whose text starts with the parent_text.
        """
        # Normalize the search text to lowercase and remove leading/trailing whitespace
        parent_text = parent_text.strip().lower()
        # Filter tags: must be a SubTag and its lowercase text must start with the parent_text + " "
        # (Adding " " helps avoid partial matches like 'Fire' matching 'Firefighter') - Adjust if needed.
        return [
            tag
            for tag in self.tags
            if isinstance(tag, SubTag) and tag.text.lower().startswith(parent_text + " ")
        ]

    def group_by_parent(self) -> Dict[str, List[SubTag]]:
        """Groups SubTag instances by their `parent` ID.

        Returns:
            Dict[str, List[SubTag]]: A dictionary where keys are parent tag IDs
                                     and values are lists of SubTag objects associated
                                     with that parent.
        """
        # Initialize a defaultdict where each key will default to an empty list
        grouped = defaultdict(list)
        # Iterate through all tags in the list
        for tag in self.tags:
            # Check if the tag is a SubTag and has a parent ID assigned
            if isinstance(tag, SubTag) and tag.parent:
                # Append the subtag to the list associated with its parent ID
                grouped[tag.parent].append(tag)
        # Convert the defaultdict back to a regular dict before returning
        return dict(grouped)

    def get_tag_by_id(self, tag_id: str) -> Tag | None:
        """Finds a single tag by its unique ID.

        Args:
            tag_id (str): The ID of the tag to find.

        Returns:
            Optional[Tag]: The found Tag object, or None if no tag with that ID exists.
        """
        # Use next() with a generator expression for efficiency.
        # It stops searching as soon as the first match is found.
        # The second argument to next() is the default value (None) if no match is found.
        return next((t for t in self.tags if t.id == tag_id), None)

    def filter_by_challenge(self, challenge: bool) -> List[Tag]:
        """Filters tags based on the value of their `challenge` attribute.

        Args:
            challenge (bool): The boolean value to filter by (True or False).

        Returns:
            List[Tag]: A list of tags where the `challenge` attribute matches the input value.
        """
        # List comprehension filtering based on the challenge flag
        return [tag for tag in self.tags if tag.challenge == challenge]

    def filter_by_text(self, keyword: str) -> List[Tag]:
        """Filters tags whose text contains a given keyword (case-insensitive).

        Args:
            keyword (str): The substring to search for within the tag text.

        Returns:
            List[Tag]: A list of tags where the keyword is found in their text.
        """
        # Normalize keyword to lowercase for case-insensitive search
        keyword_lower = keyword.lower()
        # List comprehension: check if lowercase keyword is in the lowercase tag text
        return [tag for tag in self.tags if keyword_lower in tag.text.lower()]

    def filter_by_type(self, tag_type: str) -> List[Tag]:
        """Filters tags based on their `tag_type` attribute ('base', 'parent', 'sub').

        Args:
            tag_type (str): The tag type to filter by.

        Returns:
            List[Tag]: A list of tags matching the specified type.
        """
        # List comprehension filtering based on the tag_type attribute
        return [tag for tag in self.tags if tag.tag_type == tag_type]

    def filter_by_attribute(self, attribute: str) -> List[Tag]:
        """Filters tags based on their `attribute` attribute (e.g., 'str', 'int').

        Args:
            attribute (str): The attribute name to filter by.

        Returns:
            List[Tag]: A list of tags matching the specified attribute.
        """
        # List comprehension filtering based on the attribute attribute
        return [tag for tag in self.tags if tag.attribute == attribute]

    def sorted_by_position(self) -> List[Tag]:
        """Returns a new list of tags sorted by their `position` attribute.

        Tags with `position` set to None are treated as having position 0 for sorting.

        Returns:
            List[Tag]: A new list containing all tags sorted by position.
        """
        # Use the built-in sorted() function
        # Provide a lambda function as the key: extracts `position`, defaulting to 0 if None
        return sorted(self.tags, key=lambda t: (t.position if t.position is not None else 0))

    # --- Magic Methods for usability ---

    def __iter__(self):
        """Allows iterating directly over the TagList object (e.g., `for tag in taglist:`)."""
        # Return an iterator for the internal list of tags
        return iter(self.tags)

    def __getitem__(self, index):
        """Allows accessing tags by index (e.g., `taglist[0]`)."""
        # Delegate indexing to the internal list of tags
        return self.tags[index]

    def __len__(self):
        """Allows getting the number of tags using `len(taglist)`."""
        # Delegate length calculation to the internal list of tags
        return len(self.tags)

    def __repr__(self) -> str:
        """Returns a developer-friendly representation of the TagList object."""
        # Provide a simple representation showing the number of tags
        return f"TagList(count={len(self.tags)})"


# SECTION: LOADING FUNCTION


def load_tags_from_json(json_path: str, config_path: str) -> TagList:
    """Loads tag data from a JSON file and processes it using a TagFactory.

    This function handles the common workflow of:
    1. Creating a TagFactory using the specified TOML configuration.
    2. Reading tag data (expected to be a list of dictionaries) from the JSON file.
    3. Using the factory to create a TagList with fully typed and processed
       Tag, MomTag, and SubTag objects.

    Args:
        json_path (str): The file path to the JSON file containing the list of raw tag data.
        config_path (str): The file path to the TOML configuration file required by TagFactory.

    Returns:
        TagList: An instance of TagList containing the processed tags.

    Raises:
        FileNotFoundError: If either the json_path or config_path does not exist.
        json.JSONDecodeError: If the JSON file content is invalid.
        tomllib.TOMLDecodeError: If the TOML file content is invalid.
        KeyError: If the TOML file is missing expected keys (e.g., 'tags').
        # Other exceptions related to file reading or Pydantic validation might also occur.
    """
    # Step 1: Create the TagFactory using the configuration file
    # (Propagates FileNotFoundError, TOMLDecodeError, KeyError if config loading fails)
    factory = TagFactory(config_path=config_path)

    # Step 2: Read the raw tag data from the JSON file
    # (Propagates FileNotFoundError, JSONDecodeError if JSON loading fails)
    with open(json_path, encoding="utf-8") as f:
        tag_data = json.load(f)
        # Basic check: Ensure loaded data is a list
        if not isinstance(tag_data, list):
            raise TypeError(
                f"Expected a list of tags from JSON file '{json_path}', but got {type(tag_data).__name__}"
            )

    # Step 3: Use the factory and raw data to create the TagList
    # (Propagates Pydantic validation errors if data doesn't match models)
    taglist = TagList.from_raw_data(raw_list=tag_data, factory=factory)

    # Step 4: Return the processed TagList
    return taglist


# --- Main Execution Example ---

# Define file paths constants for clarity
TAG_JSON_PATH = "tags.json"
TAG_CONFIG_PATH = "tags.toml"

try:
    # Step 1: Call the function to load and process tags from files.
    # This single call performs factory creation, JSON loading, and TagList creation.
    taglist = load_tags_from_json(json_path=TAG_JSON_PATH, config_path=TAG_CONFIG_PATH)

    # Step 2: If the call succeeds, proceed to use the taglist.
    print(f"--- Successfully loaded TagList with {len(taglist)} tags ---")

    # Step 3: Iterate and print (or do other operations)
    for tag in taglist:
        # Using print(tag) will utilize the __repr__ you defined (via generic_repr)
        print(tag)
        # If you wanted the JSON representation instead, use:
        # print(tag.model_dump_json(indent=2)) # Pydantic v2+
        print("-" * 10)  # Separator for readability

    # --- Example Usage of TagList Methods (Optional) ---
    # (This part remains the same, keep it commented out or use as needed)
    # print("\n--- Parent Tags (MomTags) ---")
    # for parent_tag in taglist.get_parents():
    #     print(parent_tag)
    # ... etc ...


# Step 4: Handle potential errors from the loading function
except FileNotFoundError as e:
    # This catches if either tags.json OR tags.toml is missing
    print(f"Error: Required file not found: {e.filename}")
except json.JSONDecodeError:
    print(f"Error: Could not decode JSON file: {TAG_JSON_PATH}. Check its format.")
except tomllib.TOMLDecodeError:
    print(f"Error: Could not decode TOML config file: {TAG_CONFIG_PATH}. Check its format.")
except (KeyError, TypeError) as e:
    # Catches missing keys in TOML (KeyError) or if JSON isn't a list (TypeError)
    print(f"Error processing configuration or data structure: {e}")
except Exception as e:
    # Catch any other unexpected errors during loading/processing
    print(f"An unexpected error occurred: {e}")
