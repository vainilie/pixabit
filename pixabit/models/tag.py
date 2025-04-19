# pixabit/models/tag.py

# SECTION: MODULE DOCSTRING
"""Defines data model classes for representing Habitica Tags.

Includes:
- `Tag`: Represents a single tag with its metadata.
- `TagList`: A container class to manage a collection of Tag objects,
  providing processing based on configuration maps and filtering capabilities.
"""

# SECTION: IMPORTS
import logging
import re
from typing import Any, Dict, List, Optional  # Keep Dict/List, added Set

import emoji_data_python
from rich.logging import RichHandler
from textual import log

from pixabit.utils.display import console

FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)])


# Local Imports (assuming config and utils are siblings or configured in path)
try:
    # Import the configuration maps directly
    from pixabit.cli.config import ATTRIBUTE_MAP, TAG_MAP

    # Placeholder for potential console usage, though models usually don't print
    # from pixabit.utils.display import console
except ImportError:
    log.warning("Warning: Could not import config maps in tag.py. Tag processing might be limited.")
    ATTRIBUTE_MAP: Dict[str, str] = {}
    TAG_MAP: Dict[str, str] = {}
    # Define dummy maps if import fails

# SECTION: CONSTANTS (Moved attribute_string here for clarity)

# Mapping from attribute symbols (potentially in names) to attribute keys
# This seems specific to a personal naming convention, ensure it's robust.
ATTRIBUTE_SYMBOL_MAP: Dict[str, str] = {
    "🜄": "con",  # Water/Constitution?
    "🜂": "str",  # Fire/Strength?
    "🜁": "int",  # Air/Intelligence?
    "🜃": "per",  # Earth/Perception?
    "᛭": "legacy",  # Nordic cross symbol?
}
# Precompile regex for finding attribute symbols
ATTRIBUTE_SYMBOL_REGEX = re.compile(f"([{ ''.join(ATTRIBUTE_SYMBOL_MAP.keys()) }])")

# SECTION: DATA CLASSES


# KLASS: Tag
class Tag:
    """Represents a single Habitica Tag entity.

    Attributes are parsed from the API tag object format. Additional context
    like tag type, parent, and children can be populated during processing.

    Attributes:
        id: Unique identifier of the tag (UUID string).
        name: Display name of the tag (emojis processed).
        challenge: Boolean indicating if the tag is associated with a challenge creation.
                   (Note: This might not mean it's *only* for challenge tasks).
        position: The user-defined sort order position (if available/processed).
        tag_type: Processed type ('parent', 'child', 'basic').
        attr: Associated attribute ('str', 'int', etc.) if determined during processing.
        origin: Associated origin ('challenge', 'personal', etc.) if determined.
        parent_id: ID of the logical parent tag based on processing rules.
        children: List of child Tag objects (populated if linking is done).
    """

    # FUNC: __init__
    def __init__(
        self,
        tag_data: Dict[str, Any],
        tag_type: str = "basic",  # Default type before processing
        attr: Optional[str] = None,
        origin: Optional[str] = None,
        position: Optional[int] = None,
        parent_id: Optional[str] = None,
        children: Optional[List["Tag"]] = None,  # Forward reference for type hint
    ):
        """Initializes a Tag object.

        Args:
            tag_data: A dictionary containing the raw tag data from the API.
            tag_type: Initial type classification (default: 'basic').
            attr: Optional pre-assigned attribute string.
            origin: Optional pre-assigned origin string.
            position: Optional sort position index.
            parent_id: Optional ID of the parent tag.
            children: Optional list of child Tag objects.

        Raises:
            TypeError: If tag_data is not a dictionary.
        """
        if not isinstance(tag_data, dict):
            raise TypeError("tag_data must be a dictionary.")

        self.id: Optional[str] = tag_data.get("id")
        _name = tag_data.get("name")
        self.name: str = emoji_data_python.replace_colons(_name) if _name else "Unnamed Tag"
        # API sometimes returns 'challenge': <challenge_id_string> or 'challenge': True/False
        # Normalize to boolean based on presence/truthiness
        self.challenge: bool = bool(tag_data.get("challenge"))

        # Attributes populated during processing or passed in
        self.position: Optional[int] = position
        self.tag_type: str = tag_type  # Use provided type or default
        self.attr: Optional[str] = attr
        self.origin: Optional[str] = origin
        self.parent_id: Optional[str] = parent_id
        self.children: List[Tag] = children if children is not None else []  # Ensure list

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        return f"Tag(id='{self.id}', name='{self.name}', type='{self.tag_type}', attr='{self.attr}')"


# KLASS: TagList
class TagList:
    """Container for managing a list of Tag objects.

    Processes raw tag data using configuration maps (TAG_MAP, ATTRIBUTE_MAP)
    and symbol conventions (ATTRIBUTE_SYMBOL_MAP) to determine tag types,
    attributes, origins, and parent relationships. Provides filtering methods.
    """

    # FUNC: __init__
    def __init__(
        self,
        raw_tag_list: List[Dict[str, Any]],
        # Optionally pass maps if they shouldn't be global/imported from config
        # tag_map: Optional[Dict[str, str]] = None,
        # attribute_map: Optional[Dict[str, str]] = None,
    ):
        """Initializes the TagList container.

        Args:
            raw_tag_list: A list of dictionaries, where each dictionary represents
                          a raw tag from the Habitica API.
        """
        self.tags: List[Tag] = []  # Holds the processed Tag objects
        # Use maps imported from config by default
        self._tag_map = TAG_MAP
        self._attribute_map = ATTRIBUTE_MAP
        self._process_list(raw_tag_list)
        # Optional: Add explicit linking step if parent *objects* are needed
        # self._link_tags()

    # FUNC: _process_single_tag
    def _process_single_tag(self, i: int, tag_info: Dict[str, Any]) -> Optional[Tag]:
        """Processes a single raw tag dictionary into a Tag object with context.

        Determines `tag_type`, `attr`, `origin`, and `parent_id` based on config
        maps and symbol conventions.

        Args:
            i: The original index/position of the tag in the raw list.
            tag_info: The dictionary containing the raw tag data.

        Returns:
            A processed Tag object, or None if the input tag_info is invalid.
        """
        if not isinstance(tag_info, dict) or not tag_info.get("id"):
            log.warning(f"Skipping invalid tag data at index {i}: {tag_info}")
            return None

        # Create base Tag object
        tag = Tag(tag_info, position=i)
        tag_id = tag.id  # Should exist based on check above
        tag_name = tag.name  # Already processed emoji

        # --- Determine Tag Type, Attribute, Origin, Parent based on rules ---

        # 1. Check Config Maps for Parent Tags
        if tag_id in self._tag_map:
            tag.tag_type = "parent"
            tag.origin = self._tag_map[tag_id]
        elif tag_id in self._attribute_map:
            tag.tag_type = "parent"
            tag.attr = self._attribute_map[tag_id]

        # 2. Check Name for Attribute Symbols (Potential Children)
        # This assumes child tags are *not* also defined in the config maps as parents.
        symbol_match = ATTRIBUTE_SYMBOL_REGEX.search(tag_name)
        if symbol_match:
            symbol = symbol_match.group(1)
            if symbol in ATTRIBUTE_SYMBOL_MAP:
                potential_attr = ATTRIBUTE_SYMBOL_MAP[symbol]
                # If not already marked as a parent, assume it's a child
                if tag.tag_type == "basic":  # Only overwrite if not already a parent
                    tag.tag_type = "child"
                    tag.attr = potential_attr

                    # Find parent ID by matching the child's attribute to a parent's attribute
                    parent_id_found = None
                    # Iterate through the attribute map (parent tags defined by attribute)
                    for p_id, p_attr in self._attribute_map.items():
                        if tag.attr == p_attr:
                            parent_id_found = p_id
                            break  # Found the corresponding parent
                    if parent_id_found:
                        tag.parent_id = parent_id_found
                    else:
                        # Couldn't find a parent defined in ATTRIBUTE_MAP for this attribute symbol.
                        # It remains a 'child' type but without a parent_id link based on this rule.
                        log.warning(f"Warning: Tag '{tag_name}' (ID: {tag_id}) has symbol for '{potential_attr}' but no matching parent in ATTRIBUTE_MAP.")

        # If after checks, tag_type is still 'basic', it doesn't fit parent/child rules.
        return tag

    # FUNC: _process_list
    def _process_list(self, raw_tag_list: List[Dict[str, Any]]) -> None:
        """Processes a list of raw tag dictionaries into Tag objects.

        Iterates through the raw list, calls `_process_single_tag` for each,
        and populates the `self.tags` attribute.

        Args:
            raw_tag_list: A list of dictionaries representing raw tags.
        """
        processed_tags: List[Tag] = []
        if not isinstance(raw_tag_list, list):
            log.warning(f"Error: raw_tag_list must be a list, got {type(raw_tag_list)}. Cannot process tags.")
            self.tags = []
            return

        for i, tag_dict in enumerate(raw_tag_list):
            tag_object = self._process_single_tag(i, tag_dict)
            if tag_object:  # Only append if processing was successful
                processed_tags.append(tag_object)

        # Optional: Sort processed tags (e.g., by position, then name)
        # processed_tags.sort(key=lambda t: (t.position if t.position is not None else float('inf'), t.name))
        self.tags = processed_tags

    # --- Optional: Linking Parent/Child Objects ---
    # This method links the actual Tag objects, not just IDs. Requires changing
    # Tag.parent_id type hint to Optional["Tag"] and adding a Tag.parent attribute.
    # Call this at the end of __init__ if needed.
    # def _link_tags(self) -> None:
    #     """Links parent Tag objects and updates children lists."""
    #     tag_map_by_id: Dict[str, Tag] = {tag.id: tag for tag in self.tags if tag.id}
    #     for tag in self.tags:
    #         # Reset children list before potentially populating
    #         tag.children = []
    #         if tag.parent_id and tag.parent_id in tag_map_by_id:
    #             parent_tag = tag_map_by_id[tag.parent_id]
    #             # Assuming Tag class has `parent: Optional[Tag] = None` attribute
    #             # tag.parent = parent_tag
    #             # Add current tag to parent's children list if not already there
    #             if tag not in parent_tag.children:
    #                 parent_tag.children.append(tag)
    #         # else:
    #             # Optional: Clear parent object if ID exists but object not found?
    #             # tag.parent = None

    # SECTION: Filtering Methods

    # FUNC: by_id
    def by_id(self, tag_id: str) -> Optional[Tag]:
        """Retrieves a tag by its ID.

        Args:
            tag_id: The ID string of the tag to retrieve.

        Returns:
            The Tag object with the matching ID, or None if not found.
        """
        for tag in self.tags:
            if tag.id == tag_id:
                return tag
        return None

    # FUNC: by_type
    def by_type(self, tag_type: str) -> List[Tag]:
        """Returns all tags matching a given processed type ('parent', 'child', 'basic').

        Args:
            tag_type: The type string to filter by.

        Returns:
            A list of tags matching the specified type.
        """
        return [tag for tag in self.tags if tag.tag_type == tag_type]

    # FUNC: by_attr
    def by_attr(self, attr: str) -> List[Tag]:
        """Returns a list of tags that have a matching processed attribute.

        Args:
            attr: The attribute string ('str', 'int', 'con', 'per', etc.) to match.

        Returns:
            A list of tags matching the given attribute.
        """
        return [tag for tag in self.tags if tag.attr == attr]

    # FUNC: by_origin
    def by_origin(self, origin: str) -> List[Tag]:
        """Returns tags matching a given processed origin ('challenge', 'personal', etc.).

        Args:
            origin: The origin string to filter tags by.

        Returns:
            A list of tags matching the specified origin.
        """
        return [tag for tag in self.tags if tag.origin == origin]

    # FUNC: by_challenge
    def by_challenge(self, is_challenge_tag: bool = True) -> List[Tag]:
        """Returns tags filtered by the 'challenge' flag from the raw API data.

        Args:
            is_challenge_tag: Filter by challenge status (default: True).

        Returns:
            List of tags matching the challenge flag criteria.
        """
        # Filters based on the raw 'challenge' boolean flag from the API data
        return [tag for tag in self.tags if tag.challenge is is_challenge_tag]

    # FUNC: get_children
    def get_children(self, parent_id: str) -> List[Tag]:
        """Retrieves all child tags associated with a given parent ID (based on processed parent_id).

        Args:
            parent_id: The ID of the parent tag.

        Returns:
            A list of Tag objects whose `parent_id` matches the given ID.
        """
        return [tag for tag in self.tags if tag.parent_id == parent_id]

    # FUNC: get_parents
    def get_parents(self) -> List[Tag]:
        """Retrieves all tags identified as 'parent' type during processing."""
        return self.by_type("parent")

    # FUNC: get_tags_without_parent
    def get_tags_without_parent(self) -> List[Tag]:
        """Retrieves all tags that were not assigned a parent_id during processing."""
        return [tag for tag in self.tags if tag.parent_id is None]
