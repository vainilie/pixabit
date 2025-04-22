"""Defines Pydantic models for Habitica tags."""

from __future__ import annotations

# --- Python Standard Library Imports ---
import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Union,
)

import tomllib  # Python 3.11+, use tomli for older versions

# --- Third-Party Library Imports ---
from pydantic import BaseModel, TypeAdapter, model_validator

from pixabit.utils.logger import log

# SECTION: CONSTANTS

# Maps special symbols found in tag text to short attribute names
ATTRIBUTE_SYMBOL_MAP: Dict[str, str] = {
    "🜄": "con",  # Water symbol maps to Constitution
    "🜂": "str",  # Fire symbol maps to Strength
    "🜁": "int",  # Air symbol maps to Intelligence
    "🜃": "per",  # Earth symbol maps to Perception
    "᛭": "legacy",  # Nordic cross symbol maps to Legacy
}

# Maps configuration keys to short attribute names
ATTRIBUTE_MAP: Dict[str, str] = {
    "ATTR_TAG_STR_ID": "str",
    "ATTR_TAG_INT_ID": "int",
    "ATTR_TAG_CON_ID": "con",
    "ATTR_TAG_PER_ID": "per",
    "LEGACY_TAG_ID": "legacy",
    "CHALLENGE_TAG_ID": "challenge",
    "PERSONAL_TAG_ID": "personal",
}

# Precompile regex for efficiency
ATTRIBUTE_SYMBOL_REGEX = re.compile(
    f"([{''.join(ATTRIBUTE_SYMBOL_MAP.keys())}])"
)


# SECTION: BASE MODELS


class Tag(BaseModel):
    """Represents a basic tag with common attributes."""

    id: str
    text: str
    tag_type: str = "base"
    challenge: bool = False
    parent: str | None = None
    category: str | None = None
    attribute: str = "str"
    position: int | None = None

    model_config = {
        "extra": "ignore",  # Ignore extra fields
        "validate_assignment": True,  # Validate when attributes are assigned
    }

    @model_validator(mode="before")
    @classmethod
    def _prepend_category_to_text(
        cls, values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepend category to text if not already bracketed."""
        if "category" in values and "text" in values:
            if not values["text"].startswith("["):
                values["text"] = f"[{values['category']}] {values['text']}"
        return values

    @property
    def display_name(self) -> str:
        """Return a formatted display name for the tag."""
        return self.text

    def is_parent(self) -> bool:
        """Check if this is a parent tag."""
        return self.tag_type == "parent"

    def is_subtag(self) -> bool:
        """Check if this is a subtag."""
        return self.tag_type == "sub"

    def get_parent_id(self) -> str | None:
        """Get the parent ID for this tag."""
        return self.parent


class MomTag(Tag):
    """Represents a parent tag, typically corresponding to a core attribute."""

    tag_type: str = "parent"  # Override default value

    @property
    def base_name(self) -> str:
        """Returns the text of the parent tag."""
        return self.text


class SubTag(Tag):
    """Represents a subtag, usually associated with a parent MomTag."""

    tag_type: str = "sub"  # Override default value


# SECTION: TAG FACTORY


class TagFactory:
    """Factory for creating Tag, MomTag, or SubTag instances."""

    def __init__(self, config_path: str | Path):
        """Initialize factory with configuration from TOML file."""
        # Convert to Path if string
        if isinstance(config_path, str):
            config_path = Path(config_path)

        # Load configuration
        with config_path.open("rb") as f:
            data = tomllib.load(f)

        # Store mappings
        self.name_to_id: Dict[str, str] = data.get("tags", {})

        # Create ID to attribute mapping
        self.id_to_attribute: Dict[str, str] = {
            self.name_to_id.get(config_name): attr
            for config_name, attr in ATTRIBUTE_MAP.items()
            if config_name in self.name_to_id
        }

        # Reverse mapping
        self.id_to_name: Dict[str, str] = {
            v: k for k, v in self.name_to_id.items()
        }

    def detect_type(self, tag_id: str, tag_text: str) -> tuple[str, str | None]:
        """Determine tag type and parent based on ID and text."""
        # Check if it's a parent tag
        if tag_id in self.id_to_attribute:
            return "mom", None

        # Check for attribute symbol in text
        match = ATTRIBUTE_SYMBOL_REGEX.search(tag_text)
        if match:
            symbol = match.group(1)
            attr = ATTRIBUTE_SYMBOL_MAP.get(symbol)
            if attr:
                # Find parent ID with matching attribute
                for parent_id, attr_name in self.id_to_attribute.items():
                    if attr_name == attr:
                        return "sub", parent_id

        # Default to base tag
        return "base", None

    def create_tag(self, data: dict, position: int | None = None) -> Tag:
        """Create appropriate Tag object from raw data."""
        # Extract basic data
        tag_id = data.get("id")
        data["text"] = data.get("text") or data.get("name", "")
        tag_text = data.get("text", "")

        # Add position if provided
        if position is not None:
            data["position"] = position

        # Determine tag type
        tag_type, parent_id = self.detect_type(tag_id, tag_text)

        # Set attribute if applicable
        attribute = self.id_to_attribute.get(tag_id)
        if attribute:
            data["attribute"] = attribute
            data["category"] = attribute

        # Create appropriate tag class
        if tag_type == "mom":
            return MomTag.model_validate(data)
        elif tag_type == "sub":
            return SubTag.model_validate({**data, "parent": parent_id})
        else:
            return Tag.model_validate(data)


# SECTION: TAG LIST


class TagList:
    """A list-like collection of Tag objects with additional utility methods."""

    def __init__(self, tags: List[Tag]):
        """Initialize with a list of tags."""
        self.tags = tags
        # Reset cache when creating new instance
        self.get_tag_by_id.cache_clear()

    @classmethod
    def from_raw_data(
        cls, raw_list: Iterable[dict], factory: TagFactory
    ) -> TagList:
        """Create TagList from raw data using a factory."""
        typed_tags = [
            factory.create_tag(item, i) for i, item in enumerate(raw_list)
        ]
        return cls(tags=typed_tags)

    @classmethod
    def from_json(cls, json_path: str | Path, factory: TagFactory) -> TagList:
        """Load TagList directly from a JSON file using a factory."""
        # Convert to Path if string
        if isinstance(json_path, str):
            json_path = Path(json_path)

        # Load JSON data
        with json_path.open(encoding="utf-8") as f:
            raw_data = json.load(f)

        # Validate data is a list
        if not isinstance(raw_data, list):
            raise TypeError(f"Expected list from JSON file {json_path}")

        # Create and return TagList
        return cls.from_raw_data(raw_data, factory)

    @classmethod
    def from_json_basic(cls, json_str: str) -> TagList:
        """Parse TagList directly from a JSON string using Pydantic."""
        parsed_tags = TypeAdapter(List[Tag]).validate_json(json_str)
        return cls(tags=parsed_tags)

    def as_dicts(self) -> List[dict]:
        """Convert tags to list of dictionaries."""
        return [tag.model_dump() for tag in self.tags]

    @property
    def parents(self) -> List[MomTag]:
        """Get all parent tags."""
        return [tag for tag in self.tags if isinstance(tag, MomTag)]

    def get_subtags_for_parent(self, parent_id: str) -> List[SubTag]:
        """Get all subtags for a specific parent ID."""
        return [
            tag
            for tag in self.tags
            if isinstance(tag, SubTag) and tag.parent == parent_id
        ]

    def get_subtags_by_parent_prefix(self, parent_text: str) -> List[SubTag]:
        """Find subtags whose text starts with given parent text."""
        parent_text = parent_text.strip().lower()
        return [
            tag
            for tag in self.tags
            if isinstance(tag, SubTag)
            and tag.text.lower().startswith(parent_text + " ")
        ]

    def group_by_parent(self) -> Dict[str, List[SubTag]]:
        """Group subtags by their parent ID."""
        grouped = defaultdict(list)
        for tag in self.tags:
            if isinstance(tag, SubTag) and tag.parent:
                grouped[tag.parent].append(tag)
        return dict(grouped)

    @lru_cache(maxsize=128)
    def get_tag_by_id(self, tag_id: str) -> Tag | None:
        """Find a tag by ID (cached for performance)."""
        return next((t for t in self.tags if t.id == tag_id), None)

    def filter_by_challenge(self, challenge: bool) -> List[Tag]:
        """Filter tags by challenge flag."""
        return [tag for tag in self.tags if tag.challenge == challenge]

    def filter_by_text(self, keyword: str) -> List[Tag]:
        """Filter tags by text content."""
        keyword_lower = keyword.lower()
        return [tag for tag in self.tags if keyword_lower in tag.text.lower()]

    def filter_by_type(self, tag_type: str) -> List[Tag]:
        """Filter tags by type."""
        return [tag for tag in self.tags if tag.tag_type == tag_type]

    def filter_by_attribute(self, attribute: str) -> List[Tag]:
        """Filter tags by attribute."""
        return [tag for tag in self.tags if tag.attribute == attribute]

    def sorted_by_position(self) -> List[Tag]:
        """Return tags sorted by position."""
        return sorted(
            self.tags, key=lambda t: t.position if t.position is not None else 0
        )

    # List-like methods
    def __iter__(self) -> Iterator[Tag]:
        """Make TagList iterable."""
        return iter(self.tags)

    def __getitem__(self, index) -> Tag:
        """Allow index access."""
        return self.tags[index]

    def __len__(self) -> int:
        """Get number of tags."""
        return len(self.tags)

    def __repr__(self) -> str:
        """String representation."""
        return f"TagList(count={len(self.tags)})"


# SECTION: LOADING FUNCTION


def load_tags_from_json(
    json_path: str | Path, config_path: str | Path
) -> TagList:
    """Load and process tags from JSON file using configuration."""
    try:
        # Create factory
        factory = TagFactory(config_path=config_path)

        # Create TagList directly from JSON file
        return TagList.from_json(json_path, factory)

    except FileNotFoundError as e:
        log.error(f"Error: Required file not found: {e.filename}")
        raise
    except json.JSONDecodeError:
        log.error(f"Error: Could not decode JSON file: {json_path}")
        raise
    except tomllib.TOMLDecodeError:
        log.error(f"Error: Could not decode TOML config file: {config_path}")
        raise
    except (KeyError, TypeError) as e:
        log.error(f"Error processing configuration or data structure: {e}")
        raise


# SECTION: DEMO CONTEXT MANAGER

from contextlib import contextmanager


@contextmanager
def tag_loading_context(json_path: str | Path, config_path: str | Path):
    """Context manager for safely loading tags with error handling."""
    try:
        # Setup
        log.info(f"Loading tags from {json_path}...")

        # Create factory
        factory = TagFactory(config_path=config_path)

        # Load JSON data
        if isinstance(json_path, str):
            json_path = Path(json_path)

        with json_path.open(encoding="utf-8") as f:
            tag_data = json.load(f)

        if not isinstance(tag_data, list):
            raise TypeError("Expected a list from JSON file")

        # Yield data and factory
        yield tag_data, factory

    except FileNotFoundError as e:
        log.error(f"Error: Required file not found: {e.filename}")
        yield None, None
    except json.JSONDecodeError:
        log.error(f"Error: Could not decode JSON file: {json_path}")
        yield None, None
    except tomllib.TOMLDecodeError:
        log.error(f"Error: Could not decode TOML config file: {config_path}")
        yield None, None
    except Exception as e:
        log.error(f"An unexpected error occurred: {e}")
        yield None, None
    finally:
        log.success("Tag loading operation completed.")


# --- Main Execution Example ---

# Define file paths using pathlib
TAG_JSON_PATH = Path("tags.json")
TAG_CONFIG_PATH = Path("tags.toml")

# Example 1: Using direct function
try:
    # Load tags directly
    taglist = load_tags_from_json(
        json_path=TAG_JSON_PATH, config_path=TAG_CONFIG_PATH
    )
    print(f"--- Successfully loaded TagList with {len(taglist)} tags ---")

    # Using enhanced TagList properties and methods
    print("\n--- Parent Tags ---")
    for parent_tag in taglist.parents:
        print(f"{parent_tag.id}: {parent_tag.text}")
        # Get and show subtags for this parent
        subtags = taglist.get_subtags_for_parent(parent_tag.id)
        print(f"  Subtags: {len(subtags)}")
        for subtag in subtags[:3]:  # Show first 3 subtags as example
            print(f"    - {subtag.text}")

except Exception as e:
    print(f"Error loading tags: {e}")

# Example 2: Using context manager
print("\n--- Using Context Manager ---")
with tag_loading_context(TAG_JSON_PATH, TAG_CONFIG_PATH) as (data, factory):
    if data and factory:
        taglist = TagList.from_raw_data(data, factory)
        print(f"Successfully loaded {len(taglist)} tags")

        # Example of cached lookup
        tag_id = data[0]["id"]  # Get first tag ID
        tag = taglist.get_tag_by_id(tag_id)
        print(f"First tag: {tag.display_name}")
    else:
        print("Failed to load tag data")
