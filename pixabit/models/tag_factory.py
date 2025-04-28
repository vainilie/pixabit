# pixabit/models/tag_factory.py

# ─── Model ────────────────────────────────────────────────────────────────────
#       Advanced Habitica Tag Models & Factory (Config-Driven)
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Defines advanced Pydantic models for representing Habitica Tags with hierarchy
(Parent/Subtag) and a factory (`TagFactory`) to create them based on a TOML
configuration file mapping specific tag IDs/symbols to attributes and types.
Provides an enhanced `TagList` optimized for these hierarchical tags.
"""

# SECTION: IMPORTS
from __future__ import annotations

# --- Python Standard Library Imports ---
import json
import re
from collections import defaultdict
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar, Iterator, Literal  # Use standard lowercase list etc below

import emoji_data_python
import tomllib  # Python 3.11+, use tomli library for < 3.11

# --- Third-Party Library Imports ---
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,  # For direct JSON parsing if needed
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
    log.warning("tag_factory.py: Could not import helpers. Using fallbacks.")
    # Provide simple fallbacks if imports fail during refactoring/testing
    CACHE_DIR = Path("./pixabit_cache")
    log.warning("tag.py: Could not import helpers/api/config. Using fallbacks.")
from pathlib import Path
from typing import Dict, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

CACHE_SUBDIR = "content"
TAGS_FILENAME = "tags.json"
PROCESSED_TAGS_FILENAME = "processed_tags.json"
from pathlib import Path

# Maps special symbols found in tag text to short attribute names
ATTRIBUTE_SYMBOL_MAP: dict[str, str] = {
    "🜄": "con",  # Water symbol maps to Constitution
    "🜂": "str",  # Fire symbol maps to Strength
    "🜁": "int",  # Air symbol maps to Intelligence
    "🜃": "per",  # Earth symbol maps to Perception
    "᛭": "legacy",  # Nordic cross symbol maps to Legacy
}

# Maps configuration *keys* from the TOML file to internal attribute short names
# These MUST match the keys used in your `tags.toml` file
ATTRIBUTE_CONFIG_KEY_MAP: dict[str, str] = {
    "TAG_ID_ATTR_STR": "str",
    "TAG_ID_ATTR_INT": "int",
    "TAG_ID_ATTR_CON": "con",
    "TAG_ID_ATTR_PER": "per",
    "TAG_ID_LEGACY": "legacy",
    "TAG_ID_CHALLENGE": "challenge",
    "TAG_ID_PERSONAL": "personal",
    # Add other specific tag IDs you want to map if needed
}

# Precompile regex for efficiency (matches any *single* symbol from the map)
# Ensures symbols are treated individually if multiple appear in text
ATTRIBUTE_SYMBOL_REGEX = re.compile(f"({'|'.join(re.escape(s) for s in ATTRIBUTE_SYMBOL_MAP.keys())})")

DEFAULT_ATTRIBUTE = "str"  # Default attribute if none detected


class TagsConfig(BaseSettings):
    # Mapeos de ID de tag a atributo
    TAG_ID_ATTR_STR: str
    TAG_ID_ATTR_INT: str
    TAG_ID_ATTR_CON: str
    TAG_ID_ATTR_PER: str
    TAG_ID_NO_ATTR: str
    TAG_ID_LEGACY: Optional[str] = None
    TAG_ID_CHALLENGE: Optional[str] = None
    TAG_ID_PERSONAL: Optional[str] = None

    # Configuración adicional
    DEFAULT_ATTRIBUTE: str = "str"
    CACHE_DIR: Path = Path("./pixabit_cache")

    # Configuración para cargar desde archivo
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def get_id_to_attribute_map(self) -> Dict[str, str]:
        """Genera el mapeo de ID a atributo basado en la configuración actual."""
        mapping = {}
        # Agrega mappings para todos los campos TAG_ID_*
        for field_name, field_value in self.model_dump().items():
            if field_name.startswith("TAG_ID_") and field_value:
                # Extrae la parte después de TAG_ID_ y conviértela a lowercase
                attr_name = field_name[7:].lower()
                mapping[field_value] = attr_name
        return mapping


# SECTION: BASE MODELS (for TagFactory context)


# KLASS: BaseTag
class BaseTag(BaseModel):
    """Base model for tags created by the TagFactory."""

    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields from raw data
        frozen=False,  # Allow modification (e.g., position)
        validate_assignment=True,  # Validate on assignment
    )

    id: str = Field(..., description="Unique tag ID.")
    name: str = Field("", description="Tag name (parsed emoji).")  # Renamed from text for consistency
    challenge: bool = Field(False, description="Is this a challenge tag?")
    group: str | None = Field(None, description="Associated group ID (if any).")  # If API provides it

    # --- Factory-assigned fields ---
    tag_type: Literal["base", "parent", "subtag"] = Field("base", description="Type determined by factory (base, parent, subtag).")
    parent_id: str | None = Field(None, description="ID of the parent tag if this is a subtag.")
    attribute: str | None = Field(None, description="Associated attribute (str, con, etc.) determined by factory.")
    # --- End Factory-assigned ---

    position: int | None = Field(None, description="Calculated position within the list.", exclude=True)

    # --- Validators ---
    @field_validator("name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> str:
        """Parses tag name, replaces emoji shortcodes, strips whitespace."""
        if isinstance(value, str):
            parsed = emoji_data_python.replace_colons(value)
            return parsed.strip()
        log.debug(f"Received non-string for tag name: {value!r}. Using empty string.")
        return ""

    # --- Properties & Methods ---
    @property
    def display_name(self) -> str:
        """Returns the primary name for display."""
        return self.name  # Can be overridden in subclasses

    def is_parent(self) -> bool:
        """Checks if this tag is classified as a parent."""
        return self.tag_type == "parent"

    def is_subtag(self) -> bool:
        """Checks if this tag is classified as a subtag."""
        return self.tag_type == "subtag"

    def __repr__(self) -> str:
        """Concise representation."""
        props = f"type={self.tag_type}"
        if self.parent_id:
            props += f", parent={self.parent_id}"
        if self.attribute:
            props += f", attr={self.attribute}"
        chal = " (Chal)" if self.challenge else ""
        return f"BaseTag(id='{self.id}', name='{self.name}'{chal}, {props})"

    def __str__(self) -> str:
        """User-friendly representation."""
        return self.display_name


# KLASS: ParentTag
class ParentTag(BaseTag):
    """Represents a parent tag (e.g., an attribute category), determined by TagFactory."""

    tag_type: Literal["parent"] = "parent"  # Override default

    @property
    def display_name(self) -> str:
        """Display name for Parent tag (usually just its name)."""
        # Optionally add prefix/suffix like "[ATTR] Name" if needed
        return self.name


# KLASS: SubTag
class SubTag(BaseTag):
    """Represents a subtag associated with a ParentTag, determined by TagFactory."""

    tag_type: Literal["subtag"] = "subtag"  # Override default

    @property
    def display_name(self) -> str:
        """Display name for SubTag. Maybe remove prefix symbol if present."""
        # Example: Remove the first symbol if it's mapped
        match = ATTRIBUTE_SYMBOL_REGEX.match(self.name)
        if match and match.group(1) in ATTRIBUTE_SYMBOL_MAP:
            # Return name after the symbol, stripped
            return self.name[len(match.group(1)) :].strip()
        return self.name  # Return original name otherwise


# Type alias for clarity
AnyTag = ParentTag | SubTag | BaseTag

# ──────────────────────────────────────────────────────────────────────────────


# SECTION: TAG FACTORY


class TagFactory:
    """Factory for creating specialized Tag objects (ParentTag, SubTag, BaseTag)
    based on rules defined in a TOML configuration file and detected symbols/IDs.
    """

    def __init__(self, config: TagsConfig = None):
        """Initialize factory with configuration from a TOML file.

        The TOML file should contain a [tags] section mapping
        configuration keys (like 'TAG_ID_ATTR_STR') to actual Habitica tag IDs.

        Args:
            config_path: Path to the TOML configuration file.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            tomllib.TOMLDecodeError: If the config file is invalid TOML.
            KeyError: If essential keys are missing in the config.
            TypeError: If config values are of unexpected types.
        """
        # Cargar config si no se proporciona
        self.config = config or TagsConfig()

        # Configura los mapeos usando los métodos de la config
        self.id_to_attribute = self.config.get_id_to_attribute_map()

        # 2. attribute_to_parent_id: Maps attribute names back to their *primary* Tag ID (for finding parents)
        self.attribute_to_parent_id: dict[str, str] = {v: k for k, v in self.id_to_attribute.items()}

        # 3. all_configured_ids: Set of all tag IDs mentioned in the config mapping.
        self.all_configured_ids = set(self.id_to_attribute.keys())

        log.info(f"TagFactory initialized. Mapped {len(self.id_to_attribute)} attributes to tag IDs.")
        log.debug(f"Attribute Map: {self.id_to_attribute}")

    def _detect_attribute_from_symbol(self, tag_name: str) -> str | None:
        """Detects attribute based on the *first* recognized symbol in the name."""
        match = ATTRIBUTE_SYMBOL_REGEX.search(tag_name)
        return ATTRIBUTE_SYMBOL_MAP.get(match.group(1)) if match else None

    def determine_tag_properties(self, tag_id: str, tag_name: str) -> tuple[Literal["parent", "subtag", "base"], str | None, str | None]:
        """Determines tag type, parent ID, and attribute based on factory rules.

        Returns:
            tuple: (tag_type, parent_id, attribute)
        """
        tag_type: Literal["parent", "subtag", "base"] = "base"
        parent_id: str | None = None
        attribute: str | None = None

        # 1. Check if the ID directly maps to a configured attribute (potential parent)
        if tag_id in self.id_to_attribute:
            tag_type = "parent"
            attribute = self.id_to_attribute[tag_id]
            parent_id = None  # Parents don't have parents
            return tag_type, parent_id, attribute

        # 2. If not a parent, check for symbols in the name to infer attribute and find parent
        else:
            detected_attribute = self._detect_attribute_from_symbol(tag_name)
            if detected_attribute:
                # Find the parent ID corresponding to this attribute
                parent_id = self.attribute_to_parent_id.get(detected_attribute)
                if parent_id:
                    tag_type = "subtag"
                    attribute = detected_attribute
                else:
                    # Symbol found, but no configured parent for that attribute
                    log.warning(f"Tag '{tag_name}' (ID:{tag_id}) has symbol for '{detected_attribute}' but no parent tag configured for that attribute.")
                    attribute = detected_attribute  # Still assign attribute, but maybe type='base'
                    tag_type = "base"  # Or keep 'subtag' without parent? Let's make it base.

        # 3. Assign default attribute if none found so far
        if attribute is None:
            attribute = DEFAULT_ATTRIBUTE

        return tag_type, parent_id, attribute

    def create_tag(self, raw_data: dict[str, Any], position: int | None = None) -> AnyTag:
        """Creates the appropriate Tag (ParentTag, SubTag, BaseTag) from raw data.

        Args:
            raw_data: A dictionary containing raw tag data (must have 'id', should have 'name').
            position: Optional list index for the tag.

        Returns:
            An instance of ParentTag, SubTag, or BaseTag.

        Raises:
            ValidationError: If raw_data fails validation against the base model.
            KeyError: If 'id' is missing in raw_data.
        """
        if "id" not in raw_data:
            raise KeyError("Tag data must contain an 'id' field.")

        tag_id = raw_data["id"]
        # Prioritize 'name', fallback to 'text' if Habitica API uses that sometimes
        tag_name = raw_data.get("name", raw_data.get("text", ""))
        raw_data["name"] = tag_name  # Ensure 'name' field exists for validation

        tag_type, parent_id, attribute = self.determine_tag_properties(tag_id, tag_name)

        # Prepare data for model validation
        model_data = {
            **raw_data,
            "tag_type": tag_type,
            "parent_id": parent_id,
            "attribute": attribute,
            "position": position,
        }

        # Validate and instantiate the correct model type
        try:
            if tag_type == "parent":
                return ParentTag.model_validate(model_data)
            elif tag_type == "subtag":
                return SubTag.model_validate(model_data)
            else:  # 'base'
                return BaseTag.model_validate(model_data)
        except ValidationError as e:
            log.error(f"Validation failed creating tag ID '{tag_id}' with type '{tag_type}': {e}")
            raise  # Re-raise validation error


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: TAG LIST (for TagFactory context)


# KLASS: TagList (Factory-Aware)
class TagList(BaseModel):
    """A Pydantic-based list-like collection for managing advanced Tag objects
    (ParentTag, SubTag, BaseTag) created by a TagFactory. Provides methods
    for hierarchical access and manipulation.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,  # List itself can be modified
        arbitrary_types_allowed=True,  # Needed because list contains Union[ParentTag, ...]
    )

    # Holds the tags created by the factory
    tags: list[AnyTag] = Field(default_factory=list)
    factory: TagFactory | None = Field(None, exclude=True)  # Keep reference if needed

    # --- Model Lifecycle ---
    @model_validator(mode="after")
    def _update_positions(self) -> TagList:
        """Ensure positions are set correctly after validation/modification."""
        for i, tag in enumerate(self.tags):
            # Only update if BaseTag (factory adds position during creation,
            # but this ensures it's updated after potential list manipulation)
            if isinstance(tag, BaseTag):
                tag.position = i
        return self

    # --- Factory Methods ---
    @classmethod
    def from_raw_data(cls, raw_list: list[dict], factory: TagFactory) -> TagList:
        """Creates TagList from raw API data using the provided TagFactory."""
        if not isinstance(raw_list, list):
            log.error(f"Invalid input for TagList.from_raw_data: Expected list, got {type(raw_list)}.")
            return cls(tags=[], factory=factory)

        processed_tags: list[AnyTag] = []
        for i, item in enumerate(raw_list):
            if not isinstance(item, dict):
                log.warning(f"Skipping invalid item at index {i} in raw tag data (expected dict).")
                continue
            try:
                tag_instance = factory.create_tag(item, position=i)
                processed_tags.append(tag_instance)
            except (ValidationError, KeyError) as e:
                # create_tag logs the specific error
                log.warning(f"Skipping tag at index {i} due to creation error: {e}")
                continue  # Skip invalid items

        # Create TagList instance (positions set by model_validator)
        return cls(tags=processed_tags, factory=factory)

    @classmethod
    def from_json_file(cls, json_path: str | Path, factory: TagFactory) -> TagList:
        """Loads TagList directly from a JSON file using the factory."""
        json_path = Path(json_path)
        log.debug(f"Loading tags from JSON file: {json_path}")
        raw_data = load_json(json_path)  # Use helper

        if raw_data is None or not isinstance(raw_data, list):
            log.error(f"Failed to load valid tag list data from {json_path}.")
            return cls(tags=[], factory=factory)  # Return empty on failure

        return cls.from_raw_data(raw_data, factory)

    # --- Accessors & Filters ---
    @property
    def parents(self) -> list[ParentTag]:
        """Get all ParentTag instances."""
        # Need to filter by instance type
        return [tag for tag in self.tags if isinstance(tag, ParentTag)]

    @property
    def subtags(self) -> list[SubTag]:
        """Get all SubTag instances."""
        return [tag for tag in self.tags if isinstance(tag, SubTag)]

    @property
    def base_tags(self) -> list[BaseTag]:
        """Get all BaseTag instances (not Parent or SubTag)."""
        # Exclude ParentTag and SubTag instances
        return [tag for tag in self.tags if type(tag) is BaseTag]

    def get_subtags_for_parent(self, parent_id: str) -> list[SubTag]:
        """Get all subtags explicitly linked to a specific parent ID."""
        return [tag for tag in self.tags if isinstance(tag, SubTag) and tag.parent_id == parent_id]

    def get_subtags_for_parent_attribute(self, attribute: str) -> list[SubTag]:
        """Get all subtags associated with a specific attribute (e.g., 'str')."""
        # Find parent ID for attribute first
        if not self.factory:
            return []  # Factory needed
        parent_id = self.factory.attribute_to_parent_id.get(attribute)
        if not parent_id:
            return []
        return self.get_subtags_for_parent(parent_id)

    def group_by_parent_id(self) -> dict[str, list[SubTag]]:
        """Groups SubTags by their parent ID."""
        grouped = defaultdict(list)
        for tag in self.subtags:  # Iterate only over subtags
            if tag.parent_id:
                grouped[tag.parent_id].append(tag)
        return dict(grouped)

    def group_by_attribute(self) -> dict[str, list[AnyTag]]:
        """Groups all tags by their detected attribute."""
        grouped = defaultdict(list)
        for tag in self.tags:
            if isinstance(tag, BaseTag) and tag.attribute:  # Check type and attribute existence
                grouped[tag.attribute].append(tag)
        return dict(grouped)

    @lru_cache(maxsize=128)
    def get_tag_by_id(self, tag_id: str) -> AnyTag | None:
        """Finds a tag by ID (cached for performance)."""
        # Ensure tag is BaseTag or subclass before checking id
        return next((tag for tag in self.tags if isinstance(tag, BaseTag) and tag.id == tag_id), None)

    def filter_by_challenge(self, is_challenge: bool) -> list[AnyTag]:
        """Filter tags by the 'challenge' flag."""
        return [tag for tag in self.tags if isinstance(tag, BaseTag) and tag.challenge == is_challenge]

    def filter_by_type(self, tag_type: Literal["parent", "subtag", "base"]) -> list[AnyTag]:
        """Filter tags by their factory-determined type."""
        return [tag for tag in self.tags if isinstance(tag, BaseTag) and tag.tag_type == tag_type]

    def sorted_by_position(self) -> list[AnyTag]:
        """Returns tags sorted by their calculated position."""
        # Ensure tags have a position and handle None gracefully
        return sorted([t for t in self.tags if isinstance(t, BaseTag)], key=lambda t: t.position if t.position is not None else float("inf"))

    # --- List-like Methods ---
    def __len__(self) -> int:
        return len(self.tags)

    def __iter__(self) -> Iterator[AnyTag]:
        return iter(self.tags)

    def __getitem__(self, index: int | slice) -> AnyTag | list[AnyTag]:
        return self.tags[index]

    def __contains__(self, item: AnyTag | str) -> bool:
        if isinstance(item, str):
            return self.get_tag_by_id(item) is not None
        elif isinstance(item, BaseTag):
            return item in self.tags  # Instance check
        return False

    # --- Mutating Methods ---
    def add_tag(self, tag: AnyTag) -> None:
        """Adds a tag to the list if it doesn't exist (by ID). Updates positions."""
        if not isinstance(tag, BaseTag):
            log.warning(f"Attempted to add invalid type to TagList: {type(tag)}")
            return
        if tag.id not in self:
            self.tags.append(tag)
            self._update_positions()  # Recalculate positions after add
        else:
            log.debug(f"Tag with ID '{tag.id}' already exists. Skipping add.")

    def remove_tag(self, tag_id: str) -> bool:
        """Removes a tag by ID and updates positions. Returns True if removed."""
        initial_len = len(self.tags)
        self.tags = [tag for tag in self.tags if tag.id != tag_id]
        removed = len(self.tags) < initial_len
        if removed:
            self._update_positions()  # Recalculate positions after remove
        return removed

    def update_tag(self, tag_id: str, update_data: dict[str, Any]) -> bool:
        """Update a tag by ID. Returns True if updated."""
        tag = self.get_by_id(tag_id)
        try:
            updated_tag = tag.model_validate(update_data, update=True)
            if not updated_tag:
                log.warning(f"Failed to process metadata for edited tag {tag_id[:8]}")
            log.info(f"Edited task: {tag_id[:8]})")

            return updated_tag

        except ValidationError as e:
            log.error(f"Validation error editing tag {tag_id[:8]}: {e}")
            return None
        except Exception as e:
            log.exception(f"Error editing tag {tag_id[:8]}: {e}")
            return None

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
            self._update_positions()
            return True
        except ValueError:  # Should not happen if get_by_id worked, but safety
            log.error(f"Error finding index for tag ID '{tag_id}' during reorder.")
            return False

    # --- Filtering/Access Methods ---
    def get_by_id(self, tag_id: str) -> AnyTag | None:
        """Finds a tag by its unique ID."""
        return next((tag for tag in self.tags if tag.id == tag_id), None)

    def get_user_tags(self) -> list[AnyTag]:
        """Returns only the user-created tags (non-challenge tags)."""
        return [tag for tag in self.tags if not tag.challenge]

    def get_challenge_tags(self) -> list[AnyTag]:
        """Returns only the challenge-associated tags."""
        return [tag for tag in self.tags if tag.challenge]

    def filter_by_name(self, name_part: str, case_sensitive: bool = False) -> list[AnyTag]:
        """Filters tags by name containing a substring."""
        if not case_sensitive:
            name_part_lower = name_part.lower()
            return [tag for tag in self.tags if name_part_lower in tag.name.lower()]
        else:
            return [tag for tag in self.tags if name_part in tag.name]

    # --- Serialization ---
    def save(self, filename: str = PROCESSED_TAGS_FILENAME, folder: str | Path = CACHE_DIR / CACHE_SUBDIR) -> bool:
        """Saves the TagList model to a JSON file using the helper."""
        log.info(f"Saving {len(self.tags)} tags...")
        return save_pydantic_model(self, filename, folder=folder, indent=2)

    # --- Representation ---
    def __repr__(self) -> str:
        """Detailed representation including counts by type."""
        counts = defaultdict(int)
        for tag in self.tags:
            if isinstance(tag, BaseTag):
                counts[tag.tag_type] += 1
        counts_str = ", ".join(f"{k}={v}" for k, v in counts.items())
        return f"TagList(total={len(self.tags)}, {counts_str})"


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: LOADING FUNCTION & CONTEXT MANAGER


# FUNC: load_tags_from_json_with_factory
def load_tags_from_json_with_factory(json_path: str | Path, config_path: str | Path) -> TagList:
    """Loads and processes tags from a JSON file using a TagFactory based on TOML config."""
    log.info(f"Loading tags from '{json_path}' using config '{config_path}'...")
    try:
        factory = TagFactory(config_path=config_path)
        taglist = TagList.from_json_file(json_path, factory)
        log.success(f"Successfully loaded and processed {len(taglist)} tags.")
        return taglist
    except FileNotFoundError as e:
        log.error(f"File not found during tag loading: {e}")
        raise  # Re-raise for caller to handle
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, ValidationError, KeyError, TypeError) as e:
        log.error(f"Error loading or processing tags: {e}")
        raise  # Re-raise for caller to handle
    except Exception as e:
        log.exception(f"An unexpected error occurred during tag loading: {e}")
        raise


@contextmanager
def tag_loading_context(json_path: str | Path, config_path: str | Path):
    """Context manager for safely loading tags via factory with error handling."""
    factory: TagFactory | None = None
    taglist: TagList | None = None
    error: Exception | None = None
    try:
        log.info(f"Entering tag loading context for '{json_path}'...")
        factory = TagFactory(config_path=config_path)
        taglist = TagList.from_json_file(json_path, factory)
        yield taglist, factory  # Yield the results
    except (FileNotFoundError, json.JSONDecodeError, tomllib.TOMLDecodeError, ValidationError, KeyError, TypeError) as e:
        log.error(f"Error within tag loading context: {e}")
        error = e
        yield None, factory  # Yield None on error, factory might be partially init
    except Exception as e:
        log.exception(f"An unexpected error occurred in tag loading context: {e}")
        error = e
        yield None, factory  # Yield None on unexpected error
    finally:
        if error:
            log.warning("Tag loading context finished with errors.")
        else:
            log.success("Tag loading context finished successfully.")


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MAIN EXECUTION (Example/Test)
async def main():
    """Demo function showing usage patterns of TagFactory and TagList."""
    # Define file paths relative to this script or using absolute paths
    log.info("Starting Tag Processing Demo...")

    # Configuration paths
    EXAMPLE_TAGS_CONFIG = Path("./tags_config.toml")  # Assumes file exists
    OUTPUT_PROCESSED_JSON = Path("./output/processed_tags.json")

    tag_list_instance: TagList | None = None

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

    # Save raw data
    save_json(raw_tags, raw_json_path)
    log.info(f"Raw tag data saved to {raw_json_path}")

    # 2. Create factory and process raw data into TagList model
    log.info("Creating TagFactory and processing raw data...")
    factory = TagFactory(EXAMPLE_TAGS_CONFIG)
    tag_list_instance = TagList.from_raw_data(raw_list=raw_tags, factory=factory)
    log.success(f"Processed into TagList: {tag_list_instance}")
    tag_list_instance.save()
    # 3. Example: Accessing data
    user_tags = tag_list_instance.get_user_tags()
    print(f"User tags count: {len(user_tags)}")

    if tag_list_instance.tags:
        first_tag = tag_list_instance.tags[0]
        print(f"First tag: {first_tag}")
        found_tag = tag_list_instance.get_by_id(first_tag.id)
        print(f"Found by ID: {found_tag is not None}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
