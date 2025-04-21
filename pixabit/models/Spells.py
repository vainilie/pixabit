# pixabit/models/spell.py

# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for Habitica spells (skills).

Includes:
- `Spell`: Represents a single spell/skill definition from game content.
- `SpellList`: Processes raw game content and manages a collection of Spell objects,
  providing filtering capabilities.
"""

# SECTION: IMPORTS
from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional  # Added Literal

import emoji_data_python

# Use standard logger
# from textual import log # Replaced with standard logger
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# Assuming RichHandler is primarily for top-level script execution,
# library code typically uses standard logging.
# from rich.logging import RichHandler
# FORMAT = "%(message)s"
# logging.basicConfig(level="INFO", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True, show_path=False)])
logger = logging.getLogger(__name__)  # Use standard Python logger

# SECTION: PYDANTIC MODELS


class Spell(BaseModel):
    """Represents a single Habitica spell/skill definition (e.g., from game content)."""

    # Allow population by alias, ignore extra fields from content
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    # --- Fields ---
    # Key is essential, comes from the dict key in the original content
    key: str = Field(..., description="The unique identifier for the spell (e.g., 'fireball').")
    # Klass is passed during processing, not directly in spell_data
    klass: Optional[Literal["wizard", "rogue", "warrior", "healer", "special"]] = Field(
        None, description="The class the spell belongs to."
    )

    # Map content fields using aliases
    name: str = Field(alias="text", description="The display name of the spell (emoji parsed).")
    description: str = Field(
        "", alias="notes", description="The descriptive text for the spell (emoji parsed)."
    )
    mana_cost: Optional[float] = Field(
        None, alias="mana", description="MP cost to cast (can be float/int)."
    )
    target: Optional[Literal["self", "user", "party", "task"]] = Field(
        None, description="Target type."
    )
    level_required: int = Field(
        0, alias="lvl", description="Minimum user level required."
    )  # Default to 0 if not present

    # Other flags from content data
    is_bulk: Optional[bool] = Field(None, alias="bulk")
    is_immediate_use: Optional[bool] = Field(None, alias="immediateUse")
    is_limited: Optional[bool] = Field(None, alias="limited")
    is_previous_purchase: Optional[bool] = Field(None, alias="previousPurchase")
    purchase_type: Optional[str] = Field(None, alias="purchaseType")
    is_silent: Optional[bool] = Field(None, alias="silent")
    value: Optional[int] = Field(None, description="Gold cost/value (if applicable).")

    # --- Validators ---
    @field_validator("name", "description", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any) -> str:
        """Parses text and replaces emoji shortcodes."""
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value)
        return ""  # Return empty string if not valid text

    @field_validator("mana_cost", mode="before")
    @classmethod
    def parse_mana_cost(cls, value: Any) -> Optional[float]:
        """Ensures mana cost is a float if present."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse mana cost: {value}. Setting to None.")
            return None

    @field_validator("level_required", "value", mode="before")
    @classmethod
    def parse_optional_int(cls, value: Any) -> Optional[int]:
        """Ensures optional integer fields are ints if present."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse integer field: {value}. Setting to None.")
            return None  # Or return 0 depending on desired behaviour

    @model_validator(mode="before")
    @classmethod
    def handle_name_fallback(cls, data: Any) -> Any:
        """If 'text' (name) is missing or empty, use the 'key' as fallback."""
        if isinstance(data, dict):
            if not data.get("text"):  # Check if 'text' (source of name) is missing/empty
                data["text"] = data.get("key")  # Use 'key' if name is missing
        return data

    # --- Methods ---
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        return f"Spell(key='{self.key}', class='{self.klass}', name='{self.name}')"


# --- CONTAINER CLASS ---


# Keep as a plain class responsible for processing the specific
# nested structure of content['spells']
class SpellList:
    """Container for managing Spell objects loaded from game content.

    Processes the nested dictionary structure from `content['spells']` into a
    flat list of `Spell` Pydantic models and provides filtering methods.
    """

    def __init__(
        self,
        raw_content_spells: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
        current_user_class: Optional[str] = None,
    ):
        """Initializes the SpellList.

        Args:
            raw_content_spells: The dictionary from `content['spells']`.
                                Format: {class_name: {spell_key: spell_data}}.
                                If None or empty, the list will be empty.
            current_user_class: The class ('warrior', etc.) of the current user.
                                Used by `get_available_spells` as a default.
        """
        self.spells: List[Spell] = []
        self.current_user_class: Optional[str] = current_user_class
        logger.debug(
            f"Initializing SpellList with raw data type: {type(raw_content_spells).__name__}"
        )

        if raw_content_spells:
            self._process_list(raw_content_spells)
        logger.info(f"Processed {len(self.spells)} spells.")

    def _process_list(self, raw_content_spells: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
        """Processes the raw content dictionary, creating Spell Pydantic instances."""
        processed_spells: List[Spell] = []
        if not isinstance(raw_content_spells, dict):
            logger.error("raw_content_spells data must be a dictionary. Cannot process spells.")
            self.spells = []
            return

        for klass, class_spells_dict in raw_content_spells.items():
            if not isinstance(class_spells_dict, dict):
                logger.warning(f"Invalid spell data structure for class '{klass}'. Skipping.")
                continue

            for spell_key, raw_spell_data in class_spells_dict.items():
                if not isinstance(raw_spell_data, dict):
                    logger.warning(
                        f"Invalid spell data for key '{spell_key}' in class '{klass}'. Skipping."
                    )
                    continue
                try:
                    # Prepare data for Pydantic model validation
                    # Include key and klass alongside the spell's own data
                    model_data = {
                        "key": spell_key,
                        "klass": klass,
                        **raw_spell_data,  # Unpack the spell's specific attributes
                    }
                    spell_instance = Spell.model_validate(model_data)
                    processed_spells.append(spell_instance)
                except ValidationError as e:
                    logger.error(
                        f"Validation failed for spell: Key='{spell_key}', Class='{klass}'.\n{e}"
                    )
                except Exception as e:
                    logger.error(
                        f"Unexpected error processing spell: Key='{spell_key}', Class='{klass}'. Error: {e}",
                        exc_info=True,
                    )

        # Optional: Sort spells after processing
        processed_spells.sort(key=lambda s: s.name)
        self.spells = processed_spells

    # --- Access and Filtering Methods ---
    # Note: Filter methods now return List[Spell] for standard Python behavior

    def __len__(self) -> int:
        """Returns the total number of spells processed."""
        return len(self.spells)

    def __iter__(self) -> iter[Spell]:
        """Allows iterating over the Spell objects."""
        return iter(self.spells)

    def __getitem__(self, index: int) -> Spell:
        """Allows accessing spells by index."""
        if not isinstance(index, int):
            raise TypeError("Index must be an integer")
        if not 0 <= index < len(self.spells):
            raise IndexError("Spell index out of range")
        return self.spells[index]

    def get_by_key(self, spell_key: str) -> Optional[Spell]:
        """Finds a spell by its unique key (e.g., 'fireball')."""
        return next((spell for spell in self.spells if spell.key == spell_key), None)

    def filter_by_class(self, klass: str) -> List[Spell]:
        """Returns all spells belonging to a specific class."""
        return [spell for spell in self.spells if spell.klass == klass]

    def filter_by_target(self, target: str) -> List[Spell]:
        """Returns spells that affect a specific target type."""
        return [spell for spell in self.spells if spell.target == target]

    def filter_by_mana_cost(self, max_cost: float, min_cost: float = 0.0) -> List[Spell]:
        """Returns spells within a specified mana cost range (inclusive)."""
        return [
            spell
            for spell in self.spells
            if spell.mana_cost is not None and min_cost <= spell.mana_cost <= max_cost
        ]

    def filter_by_level(self, max_level: int, min_level: int = 0) -> List[Spell]:
        """Returns spells within a specified level requirement range (inclusive)."""
        return [
            spell
            for spell in self.spells
            if spell.level_required is not None and min_level <= spell.level_required <= max_level
        ]

    def get_available_spells(
        self, user_level: int, user_class: Optional[str] = None
    ) -> List[Spell]:
        """Gets spells available to a user based on their level and class."""
        target_class = user_class or self.current_user_class
        if not target_class and "special" not in {s.klass for s in self.spells if s.klass}:
            logger.warning(
                "Cannot determine available spells without a user class or 'special' spells."
            )
            return []

        available_spells: List[Spell] = []
        for spell in self.spells:
            level_ok = spell.level_required is None or spell.level_required <= user_level
            if not level_ok:
                continue

            class_ok = spell.klass == "special"
            if target_class:
                class_ok = class_ok or spell.klass == target_class

            if class_ok:
                available_spells.append(spell)

        available_spells.sort(key=lambda s: (s.level_required or 0, s.name))
        return available_spells

    def __repr__(self) -> str:
        """Simple representation."""
        return f"SpellList(count={len(self.spells)})"
