# pixabit/models/tag.py

# ─── Model ────────────────────────────────────────────────────────────────────
#            Habitica Tag Models (Simple Version)
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Defines basic Pydantic models for representing Habitica Tags."""

# SECTION: IMPORTS
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator  # Changed List -> list etc below

import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from pixabit.api.client import HabiticaClient
from pixabit.helpers._json import load_json, save_json, save_pydantic_model

# Local Imports (assuming helpers and api are accessible)
# Assuming logger, json helper, client, and config are setup
try:
    from pixabit.config import CACHE_DIR
    from pixabit.helpers._logger import log
except ImportError:
    import logging

    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    # Provide simple fallbacks if imports fail during refactoring/testing
    CACHE_DIR = Path("./pixabit_cache")
    log.warning("tag.py: Could not import helpers/api/config. Using fallbacks.")

CACHE_SUBDIR = "content"
TAGS_FILENAME = "tags.json"
PROCESSED_TAGS_FILENAME = "processed_tags.json"


# SECTION: TAG MODEL


# KLASS: Tag
class Tag(BaseModel):
    """Represents a single Habitica Tag."""

    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields from API
        frozen=False,  # Tags might be editable (name, etc.)
        validate_assignment=True,  # Re-validate on attribute assignment
    )

    id: str = Field(..., description="Unique tag ID.")  # Make ID mandatory
    name: str = Field("", description="Tag name (parsed emoji).")  # Default to empty string
    challenge: bool = Field(False, description="True if tag is associated with a challenge.")
    # group: str | None = Field(None, description="Group ID if it's a group tag?") # Check API if needed
    # user: str | None = Field(None, description="User ID of creator?") # Check API if needed

    # Optional internal tracking, not directly from API typically
    position: int | None = Field(None, description="Order/position within the tag list.", exclude=True)  # Exclude from dumps

    # --- Validators ---
    @field_validator("name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> str:
        """Parses tag name and replaces emoji shortcodes."""
        if isinstance(value, str):
            parsed = emoji_data_python.replace_colons(value)
            # Optional: Strip leading/trailing whitespace
            return parsed.strip()
        log.debug(f"Received non-string value for tag name: {value!r}. Using empty string.")
        return ""  # Return empty string if name is not a string or None

    # --- Methods ---
    def __repr__(self) -> str:
        """Concise representation."""
        chal_flag = " (Challenge)" if self.challenge else ""
        name_preview = self.name.replace("\n", " ")  # Avoid newlines in repr
        return f"Tag(id='{self.id}', name='{name_preview}'{chal_flag})"

    def __str__(self) -> str:
        """User-friendly string representation (often just the name)."""
        return self.name


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: TAG LIST MODEL


# KLASS: TagList
class TagList(BaseModel):
    """Container for managing a list of Tag objects, adhering to Pydantic."""

    model_config = ConfigDict(
        extra="forbid",  # No extra fields expected on the list itself
        frozen=False,  # Allow adding/removing tags
        arbitrary_types_allowed=False,
    )

    tags: list[Tag] = Field(default_factory=list, description="The list of Tag objects.")

    # Optional: Add validation context if needed later
    # current_user_id: str | None = Field(None, description="Contextual user ID", exclude=True)

    @model_validator(mode="after")
    def update_tag_positions(self) -> TagList:
        """Updates the position attribute for each tag based on its order."""
        for i, tag in enumerate(self.tags):
            tag.position = i  # Assign position based on current order
        return self

    # --- Factory Methods ---
    @classmethod
    def from_raw_data(cls, raw_list: list[dict[str, Any]]) -> TagList:
        """Creates a TagList by validating raw dictionary data."""
        if not isinstance(raw_list, list):
            log.error(f"Invalid input for TagList.from_raw_data: Expected list, got {type(raw_list)}.")
            return cls(tags=[])  # Return empty list on error

        validated_tags: list[Tag] = []
        for i, tag_data in enumerate(raw_list):
            if not isinstance(tag_data, dict):
                log.warning(f"Skipping invalid item at index {i} in raw tag data (expected dict, got {type(tag_data)}).")
                continue
            try:
                # Validate each item into a Tag model
                tag_instance = Tag.model_validate(tag_data)
                validated_tags.append(tag_instance)
            except ValidationError as e:
                tag_id = tag_data.get("id", "N/A")
                log.error(f"Validation failed for tag data (ID: {tag_id}) at index {i}: {e}")
                # Optionally skip invalid tags or raise error depending on strictness

        # Instantiate TagList with validated tags (positions are handled by model_validator)
        return cls(tags=validated_tags)

    # --- List-like Methods ---
    def __len__(self) -> int:
        """Return the number of tags."""
        return len(self.tags)

    def __iter__(self) -> Iterator[Tag]:
        """Return an iterator over the tags."""
        return iter(self.tags)

    def __getitem__(self, index: int | slice) -> Tag | list[Tag]:
        """Get tag(s) by index or slice."""
        return self.tags[index]

    def __contains__(self, item: Tag | str) -> bool:
        """Check if a tag (by instance or ID) is in the list."""
        if isinstance(item, str):  # Check by ID
            return any(tag.id == item for tag in self.tags)
        elif isinstance(item, Tag):  # Check by instance (object equality)
            return item in self.tags
        return False

    # --- Mutating Methods ---
    def add_tag(self, tag: Tag) -> None:
        """Adds a tag to the list if it doesn't exist (by ID). Updates positions."""
        if not isinstance(tag, Tag):
            log.warning(f"Attempted to add invalid type to TagList: {type(tag)}")
            return
        if tag.id not in self:
            self.tags.append(tag)
            self.update_tag_positions()  # Recalculate positions after add
        else:
            log.debug(f"Tag with ID '{tag.id}' already exists. Skipping add.")

    def remove_tag(self, tag_id: str) -> bool:
        """Removes a tag by ID and updates positions. Returns True if removed."""
        initial_len = len(self.tags)
        self.tags = [tag for tag in self.tags if tag.id != tag_id]
        removed = len(self.tags) < initial_len
        if removed:
            self.update_tag_positions()  # Recalculate positions after remove
        return removed

    def update_tag(self, tag_id: str, name: str) -> bool:
        """Update a tag by ID. Returns True if updated."""
        tag = self.get_by_id(tag_id)
        tag["name"] = name
        if tag.name == name:
            return True
        else:
            return False

    def reorder_tags(self, tag_id: str, new_position: int) -> bool:
        """Moves a tag to a new position index and updates all positions."""
        tag_to_move = self.get_by_id(tag_id)
        if not tag_to_move:
            log.warning(f"Cannot reorder: Tag with ID '{tag_id}' not found.")
            return False

        try:
            current_index = self.tags.index(tag_to_move)
            # Ensure position is within bounds (0 to len)
            new_position_clamped = max(0, min(new_position, len(self.tags) - 1))

            # Remove and insert at the new position
            self.tags.pop(current_index)
            self.tags.insert(new_position_clamped, tag_to_move)

            # Update all positions after reordering
            self.update_tag_positions()
            return True
        except ValueError:  # Should not happen if get_by_id worked, but safety
            log.error(f"Error finding index for tag ID '{tag_id}' during reorder.")
            return False

    # --- Filtering/Access Methods ---
    def get_by_id(self, tag_id: str) -> Tag | None:
        """Finds a tag by its unique ID."""
        return next((tag for tag in self.tags if tag.id == tag_id), None)

    def get_user_tags(self) -> list[Tag]:
        """Returns only the user-created tags (non-challenge tags)."""
        return [tag for tag in self.tags if not tag.challenge]

    def get_challenge_tags(self) -> list[Tag]:
        """Returns only the challenge-associated tags."""
        return [tag for tag in self.tags if tag.challenge]

    def filter_by_name(self, name_part: str, case_sensitive: bool = False) -> list[Tag]:
        """Filters tags by name containing a substring."""
        if not case_sensitive:
            name_part_lower = name_part.lower()
            return [tag for tag in self.tags if name_part_lower in tag.name.lower()]
        else:
            return [tag for tag in self.tags if name_part in tag.name]

    # --- Serialization ---
    # No custom save_to_json needed, use the helper function
    # No custom model_dump needed, Pydantic handles it

    def save(self, filename: str = PROCESSED_TAGS_FILENAME, folder: str | Path = CACHE_DIR / CACHE_SUBDIR) -> bool:
        """Saves the TagList model to a JSON file using the helper."""
        log.info(f"Saving {len(self.tags)} tags...")
        return save_pydantic_model(self, filename, folder=folder, indent=2)

    # --- Representation ---
    def __repr__(self) -> str:
        """Detailed representation showing counts."""
        user_count = len(self.get_user_tags())
        chal_count = len(self.get_challenge_tags())
        return f"TagList(total={len(self.tags)}, user={user_count}, challenge={chal_count})"


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MAIN EXECUTION (Example/Test)
async def main():
    """Demo function to retrieve, process, and save tags."""
    log.info("Starting Tag Processing Demo...")
    tag_list_instance: TagList | None = None
    try:
        # Ensure cache directory exists
        cache_path = Path(CACHE_DIR) / CACHE_SUBDIR
        cache_path.mkdir(exist_ok=True, parents=True)
        raw_json_path = cache_path / TAGS_FILENAME
        processed_json_path = cache_path / PROCESSED_TAGS_FILENAME

        # 1. Fetch tags from API
        log.info("Fetching tags from API...")
        api = HabiticaClient()  # Assumes client is configured
        raw_tags = await api.get_tags()
        log.success(f"Fetched {len(raw_tags)} tags from API.")

        # Optionally save raw data (using generic save_json)
        save_json(raw_tags, raw_json_path)
        log.info(f"Raw tag data saved to {raw_json_path}")

        # 2. Process raw data into TagList model
        log.info("Processing raw data into TagList model...")
        tag_list_instance = TagList.from_raw_data(raw_tags)
        log.success(f"Processed into TagList: {tag_list_instance}")

        # 3. Example: Accessing data
        print(f"  - User tags count: {len(tag_list_instance.get_user_tags())}")
        if tag_list_instance.tags:
            first_tag = tag_list_instance.tags[0]
            print(f"  - First tag: {first_tag}")
            found_tag = tag_list_instance.get_by_id(first_tag.id)
            print(f"  - Found by ID: {found_tag is not None}")

        # 4. Save the processed TagList model
        log.info(f"Saving processed TagList to {processed_json_path}...")
        if tag_list_instance.save(filename=processed_json_path.name, folder=processed_json_path.parent):
            log.success("Processed tags saved successfully.")
        else:
            log.error("Failed to save processed tags.")

    except ValidationError as e:
        log.error(f"Pydantic Validation Error during tag processing: {e}")
    except ConnectionError as e:  # Example API error
        log.error(f"API Connection Error: Failed to fetch tags - {e}")
    except Exception as e:
        log.exception(f"An unexpected error occurred in the tag processing demo: {e}")  # Log full trace

    log.info("Tag Processing Demo Finished.")
    return tag_list_instance  # Return for potential further use


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

# ──────────────────────────────────────────────────────────────────────────────
