# pixabit/models/spell.py
"""Defines Pydantic models for Habitica spells (skills)."""

# SECTION: IMPORTS
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional  # Added Literal

import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# SECTION: PYDANTIC MODELS


class Spell(BaseModel):
    """Represents a single Habitica spell/skill definition (e.g., from game content)."""

    key: str
    text: str
    klass: Literal["healer", "warrior", "wizard", "rogue", "special"]
    description: str = Field(alias="notes")
    mana_cost: float = Field(alias="mana")
    target: Literal["self", "task", "party", "tasks", "user"]
    level_required: int = Field(alias="lvl")
    bulk: bool = False

    model_config = {
        "extra": "ignore",  # Ignore extra fields
        "validate_assignment": True,  # Validate when attributes are assigned
        "populate_by_name": True,  # Allow Aliases
    }


class SpellFactory:
    """Factory for creating Spells."""

    @staticmethod
    def create_spell(spell_key: str, klass: str, raw_data: dict) -> Spell:
        data = {
            "key": spell_key,
            "klass": klass,
            **raw_data,  # includes text, notes, mana, lvl, etc.
        }
        return Spell.model_validate(data)


# --- CONTAINER CLASS ---
class SpellList:
    """Container for managing Spell objects loaded from game content."""

    def __init__(
        self,
        raw_content_spells: Optional[
            Dict[str, Dict[str, Dict[str, Any]]]
        ] = None,
    ):

        self.spells: List[Spell] = []
        print(
            f"Initializing SpellList with raw data type: {type(raw_content_spells).__name__}"
        )
        if raw_content_spells:
            self._process_list(raw_content_spells)
        print(f"Processed {len(self.spells)} spells.")

    def _process_list(
        self, raw_content_spells: Dict[str, Dict[str, Dict[str, Any]]]
    ) -> None:
        """Processes the raw content dictionary, creating Spell Pydantic instances."""
        processed_spells: List[Spell] = []

        if not isinstance(raw_content_spells, dict):
            print("raw_content_spells must be a dictionary.")
            return

        for klass, class_spells_dict in raw_content_spells.items():
            if not isinstance(class_spells_dict, dict):
                print(f"Invalid spell structure for class '{klass}'. Skipping.")
                continue

            for spell_key, raw_spell in class_spells_dict.items():
                if not isinstance(raw_spell, dict):
                    print(
                        f"Invalid data for spell '{spell_key}' in class '{klass}'. Skipping."
                    )
                    continue
                try:
                    # Prepare data for Pydantic model validation
                    spell = SpellFactory.create_spell(
                        spell_key, klass, raw_spell
                    )
                    processed_spells.append(spell)
                except ValidationError as e:
                    print(
                        f"Validation failed for '{spell_key}' in class '{klass}':\n{e}"
                    )
                except Exception as e:
                    print(
                        f"Unexpected error processing '{spell_key}' in '{klass}': {e}",
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

    @classmethod
    def from_raw_data(
        cls,
        raw_data: Dict[str, Dict[str, Dict[str, Any]]],
        factory: SpellFactory,
    ) -> SpellList:
        """Constructs a SpellList from raw spell data using the given factory."""
        instance = cls()
        for klass, spells in raw_data.items():
            for spell_key, spell_info in spells.items():
                try:
                    spell = factory.create_spell(spell_key, klass, spell_info)
                    instance.spells.append(spell)
                except ValidationError as e:
                    print(f"Validation error for {klass}.{spell_key}:\n{e}")
                except Exception as e:
                    print(f"Unexpected error with {klass}.{spell_key}: {e}")
        return instance

    @classmethod
    def from_json(cls, path: str | Path, factory: SpellFactory) -> SpellList:
        with open(path, encoding="utf-8") as f:
            full_data = json.load(f)
            del full_data.get("spells")["special"]
        if "spells" not in full_data:
            raise ValueError("Missing 'spells' key in JSON file")

        return cls.from_raw_data(full_data["spells"], factory)

    def get_by_key(self, spell_key: str) -> Optional[Spell]:
        """Finds a spell by its unique key (e.g., 'fireball')."""
        return next(
            (spell for spell in self.spells if spell.key == spell_key), None
        )

    def filter_by_class(self, klass: str) -> List[Spell]:
        """Returns all spells belonging to a specific class."""
        return [spell for spell in self.spells if spell.klass == klass]

    def filter_by_target(self, target: str) -> List[Spell]:
        """Returns spells that affect a specific target type."""
        return [spell for spell in self.spells if spell.target == target]

    def filter_by_mana_cost(
        self, max_cost: float, min_cost: float = 0.0
    ) -> List[Spell]:
        """Returns spells within a specified mana cost range (inclusive)."""
        return [
            spell
            for spell in self.spells
            if min_cost <= spell.mana_cost <= max_cost
        ]

    def filter_by_level(
        self, max_level: int, min_level: int = 0
    ) -> List[Spell]:
        """Returns spells within a specified level requirement range (inclusive)."""
        return [
            spell
            for spell in self.spells
            if spell.level_required is not None
            and min_level <= spell.level_required <= max_level
        ]

    def get_available_spells(
        self, user_level: int, user_class: Optional[str] = None
    ) -> List[Spell]:
        """Gets spells available to a user based on their level and class."""
        target_class = user_class or self.current_user_class
        if not target_class and "special" not in {
            s.klass for s in self.spells if s.klass
        }:
            print(
                "Cannot determine available spells without a user class or 'special' spells."
            )
            return []

        available_spells: List[Spell] = []
        for spell in self.spells:
            if spell.level_required > user_level:
                continue
            if spell.klass == "special" or (
                target_class and spell.klass == target_class
            ):
                available_spells.append(spell)

        available_spells.sort(key=lambda s: (s.level_required, s.text))
        return available_spells

    def __repr__(self) -> str:
        """Simple representation."""
        return f"SpellList(count={len(self.spells)})"


# SECTION: DEMO CONTEXT MANAGER

from contextlib import contextmanager


@contextmanager
def spell_loading_context(json_path: str | Path):
    """Context manager for safely loading spells with error handling."""
    try:
        # Setup
        print(f"Loading spells from {json_path}...")

        # Create factory
        factory = SpellFactory()

        # Load JSON data
        if isinstance(json_path, str):
            json_path = Path(json_path)

        with json_path.open(encoding="utf-8") as f:
            spells_data = json.load(f)

        if not isinstance(spells_data, dict):
            raise TypeError("Expected a dictionary from JSON file")

        # Yield data and factory
        spells_data = spells_data.get("spells")
        if not isinstance(spells_data, dict):
            raise ValueError("'spells' key not found or is not a dict")

        del spells_data.get("spells")["special"]
        yield spells_data["spells"], SpellFactory

    except FileNotFoundError as e:
        print(f"Error: Required file not found: {e.filename}")
        yield None, None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON file: {json_path}")
        yield None, None

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        yield None, None
    finally:
        print("spell loading operation completed.")


# --- Main Execution Example ---


def load_spells_from_json(json_path: str | Path) -> SpellList:
    """Load and process spells from JSON file using configuration."""
    try:
        # Create factory
        factory = SpellFactory()

        # Create SpellList directly from JSON file
        return SpellList.from_json(json_path, factory)

    except FileNotFoundError as e:
        print(f"Error: Required file not found: {e.filename}")
        raise
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON file: {json_path}")
        raise
    except (KeyError, TypeError) as e:
        print(f"Error processing configuration or data structure: {e}")
        raise


# Define file paths using pathlib
spell_JSON_PATH = Path("content.json")

# Example 1: Using direct function
try:
    # Load spells directly
    SpellList = load_spells_from_json(json_path=spell_JSON_PATH)
    print(f"--- Successfully loaded SpellList with {len(SpellList)} spells ---")

    # Using enhanced SpellList properties and methods
    print("\n--- Parent spells ---")
    for Spell in SpellList:
        print(f"{Spell}")

except Exception as e:
    print(f"Error loading spells: {e}")

# Example 2: Using context manager
print("\n--- Using Context Manager ---")
with spell_loading_context(spell_JSON_PATH) as (data, factory):
    if data and factory:
        SpellList = SpellList.from_raw_data(data, factory)
        print(f"Successfully loaded {len(SpellList)} spells")

        # Example of cached lookup
        spell_id = data[0]["id"]  # Get first spell ID
        spell = SpellList.get_spell_by_id(spell_id)
        print(f"First spell: {spell.display_name}")
    else:
        print("Failed to load spell data")
