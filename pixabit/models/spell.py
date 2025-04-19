# pixabit/models/spell.py

# SECTION: MODULE DOCSTRING
"""Defines data model classes related to Habitica spells (skills).

Includes:
- `Spell`: Represents a single spell/skill definition, typically from game content.
- `SpellList`: A container class to manage a collection of Spell objects,
  providing processing and filtering capabilities.
"""

# SECTION: IMPORTS
import logging
from typing import Any, Dict, List, Optional  # Keep Dict/List for clarity

import emoji_data_python
from rich.logging import RichHandler
from textual import log

from pixabit.utils.display import console

FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)])

# SECTION: DATA CLASSES


# KLASS: Spell
class Spell:
    """Represents a single Habitica spell/skill definition (e.g., from game content).

    Attributes:
        key: The unique identifier for the spell (e.g., 'fireball', 'stealth').
        klass: The class the spell belongs to ('wizard', 'rogue', 'warrior', 'healer', 'special').
        name: The display name of the spell.
        description: The descriptive text (notes) for the spell.
        mana_cost: The amount of MP required to cast.
        target: The type of target ('self', 'user', 'party', 'task').
        level_required: The minimum user level required to cast.
        is_bulk: Boolean indicating if it's a bulk action spell.
        is_immediate_use: Boolean indicating if used immediately on purchase/grant.
        # ... other flags potentially available in content data ...
    """

    # FUNC: __init__
    def __init__(
        self,
        spell_key: str,
        spell_data: Dict[str, Any],
        spell_class: Optional[str] = None,
    ):
        """Initializes a Spell object.

        Args:
            spell_key: The unique key identifying the spell (e.g., 'fireball').
            spell_data: A dictionary containing the spell's data from game content.
            spell_class: The class the spell belongs to (e.g., 'wizard', 'special').

        Raises:
            ValueError: If spell_key is empty.
            TypeError: If spell_data is not a dictionary.
        """
        if not spell_key:
            raise ValueError("spell_key cannot be empty.")
        if not isinstance(spell_data, dict):
            raise TypeError("spell_data must be a dictionary.")

        self.key: str = spell_key
        self.klass: Optional[str] = spell_class  # e.g., 'wizard', 'special'

        # Map content fields to attributes, handling potential missing keys gracefully
        _name = spell_data.get("text")
        self.name: str = emoji_data_python.replace_colons(_name) if _name else spell_key  # Fallback to key
        _desc = spell_data.get("notes")
        self.description: str = emoji_data_python.replace_colons(_desc) if _desc else ""
        self.mana_cost: Optional[float] = spell_data.get("mana")  # Can be float or int
        self.target: Optional[str] = spell_data.get("target")  # 'self', 'user', 'party', 'task'
        self.level_required: Optional[int] = spell_data.get("lvl")

        # Other potentially useful flags from content
        self.is_bulk: Optional[bool] = spell_data.get("bulk")
        self.is_immediate_use: Optional[bool] = spell_data.get("immediateUse")
        self.is_limited: Optional[bool] = spell_data.get("limited")
        self.is_previous_purchase: Optional[bool] = spell_data.get("previousPurchase")
        self.purchase_type: Optional[str] = spell_data.get("purchaseType")
        self.is_silent: Optional[bool] = spell_data.get("silent")
        self.value: Optional[int] = spell_data.get("value")  # Often gold cost/value

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        return f"Spell(key='{self.key}', class='{self.klass}', name='{self.name}')"


# KLASS: SpellList
class SpellList:
    """Container for managing a list of Spell objects, typically loaded from game content.

    Provides methods for filtering spells based on various criteria like class,
    target, level, and availability to a specific user.
    """

    # FUNC: __init__
    def __init__(
        self,
        # Expects the nested structure content['spells'] which is dict[class_name, dict[spell_key, spell_data]]
        raw_content_spells: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
        current_user_class: Optional[str] = None,
    ):
        """Initializes the SpellList by processing the spells section from game content.

        Args:
            raw_content_spells: The dictionary representing `content['spells']`.
                                Should be in the format {class: {spell_key: spell_data}}.
                                If None or empty, the list will be empty.
            current_user_class: The class ('warrior', 'rogue', etc.) of the current user.
                                Used by `get_available_spells` if no class is passed to it.
        """
        self.spells: List[Spell] = []
        self.current_user_class: Optional[str] = current_user_class
        log.info(f"!!! INSIDE SpellList.__init__: Type is {type(raw_content_spells).__name__}")

        if raw_content_spells:
            self._process_list(raw_content_spells)

    # FUNC: _process_list
    def _process_list(self, raw_content_spells: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
        """Processes the raw content dictionary, creating Spell instances.

        Iterates through each class ('rogue', 'warrior', 'special', etc.) and
        then through each spell within that class.

        Args:
            raw_content_spells: The dictionary structure from `content['spells']`.
        """
        processed_spells: List[Spell] = []
        log.info(f"!!! INSIDE SpellList._process_list: Type is {type(raw_content_spells).__name__}")

        # --- ADD THIS LINE ---
        is_dict_check_result = isinstance(raw_content_spells, dict)
        log.info(f"!!! INSIDE SpellList._process_list: isinstance(..., dict) result is: {is_dict_check_result}")
        # --- END ADD ---

        if not is_dict_check_result:  # Use the stored result
            # if not isinstance(raw_content_spells, dict): # Original check
            log.info("Error: raw_content_spells data must be a dictionary. Cannot process spells.")
            self.spells = []
            return

        # Iterate through each class ('rogue', 'warrior', 'special', etc.)
        for klass, class_spells_dict in raw_content_spells.items():
            if not isinstance(class_spells_dict, dict):
                log.info(f"Warning: Invalid spell data structure for class '{klass}'. Skipping.")
                continue

            # Iterate through each spell within that class
            for spell_key, raw_spell_data in class_spells_dict.items():
                if not isinstance(raw_spell_data, dict):
                    log.info(f"Warning: Invalid spell data for key '{spell_key}' in class '{klass}'. Skipping.")
                    continue
                try:
                    # Create the Spell instance, passing key, data, and class
                    spell_instance = Spell(spell_key, raw_spell_data, spell_class=klass)
                    processed_spells.append(spell_instance)
                except (ValueError, TypeError) as e:
                    log.info(f"Error instantiating Spell object: Key='{spell_key}', Class='{klass}'. Error: {e}")
                except Exception as e:
                    log.info(f"Unexpected error processing spell: Key='{spell_key}', Class='{klass}'. Error: {e}")

        # Sort spells, perhaps alphabetically by key or name? (Optional)
        # processed_spells.sort(key=lambda s: s.name)
        self.spells = processed_spells

    # SECTION: Access and Filtering Methods

    # FUNC: __len__
    def __len__(self) -> int:
        """Returns the total number of spells processed."""
        return len(self.spells)

    # FUNC: __iter__
    def __iter__(self):
        """Allows iterating over the Spell objects."""
        yield from self.spells

    # FUNC: __getitem__
    def __getitem__(self, index: int) -> Spell:
        """Allows accessing spells by index."""
        if not isinstance(index, int):
            raise TypeError("Index must be an integer")
        if not 0 <= index < len(self.spells):
            raise IndexError("Spell index out of range")
        return self.spells[index]

    # FUNC: get_by_key
    def get_by_key(self, spell_key: str) -> Optional[Spell]:
        """Finds a spell by its unique key (e.g., 'fireball').

        Args:
            spell_key: The key string of the spell to find.

        Returns:
            The Spell object if found, otherwise None.
        """
        for spell in self.spells:
            if spell.key == spell_key:
                return spell
        return None

    # FUNC: filter_by_class
    def filter_by_class(self, klass: str) -> List[Spell]:
        """Returns all spells belonging to a specific class.

        Args:
            klass: The class name string ('warrior', 'rogue', 'wizard', 'healer', 'special').

        Returns:
            A list of matching Spell objects.
        """
        # Consider case-insensitivity if needed: klass_lower = klass.lower()
        return [spell for spell in self.spells if spell.klass == klass]

    # FUNC: filter_by_target
    def filter_by_target(self, target: str) -> List[Spell]:
        """Returns spells that affect a specific target type.

        Args:
            target: The target type string ('self', 'user', 'party', 'task').

        Returns:
            A list of matching Spell objects.
        """
        return [spell for spell in self.spells if spell.target == target]

    # FUNC: filter_by_mana_cost
    def filter_by_mana_cost(self, max_cost: float, min_cost: float = 0.0) -> List[Spell]:
        """Returns spells within a specified mana cost range (inclusive).

        Args:
            max_cost: The maximum mana cost allowed.
            min_cost: The minimum mana cost allowed (default: 0.0).

        Returns:
            A list of matching Spell objects.
        """
        return [spell for spell in self.spells if spell.mana_cost is not None and min_cost <= spell.mana_cost <= max_cost]

    # FUNC: filter_by_level
    def filter_by_level(self, max_level: int, min_level: int = 0) -> List[Spell]:
        """Returns spells within a specified level requirement range (inclusive).

        Args:
            max_level: The maximum level requirement allowed.
            min_level: The minimum level requirement allowed (default: 0).

        Returns:
            A list of matching Spell objects.
        """
        return [spell for spell in self.spells if spell.level_required is not None and min_level <= spell.level_required <= max_level]

    # FUNC: get_available_spells
    def get_available_spells(self, user_level: int, user_class: Optional[str] = None) -> List[Spell]:
        """Gets spells available to a user based on their level and class.

        Includes spells matching the user's class AND 'special' spells,
        provided the level requirement is met.

        Args:
            user_level: The level of the user.
            user_class: The class of the user ('warrior', 'rogue', 'wizard', 'healer').
                        If None, uses the `current_user_class` set during SpellList initialization.

        Returns:
            A list of Spell objects the user can potentially cast.
        """
        target_class = user_class or self.current_user_class

        if not target_class and "special" not in {s.klass for s in self.spells}:
            # If no target class specified and no 'special' spells exist at all
            log.info("Warning: Cannot determine available spells without a user class or 'special' spells.")
            return []

        available_spells: List[Spell] = []
        for spell in self.spells:
            # 1. Check Level Requirement
            level_ok = spell.level_required is None or spell.level_required <= user_level
            if not level_ok:
                continue

            # 2. Check Class Requirement
            # Spell must be 'special' OR match the target user's class.
            # If no target_class is known, only 'special' spells are considered.
            class_ok = spell.klass == "special"
            if target_class:
                class_ok = class_ok or spell.klass == target_class

            if class_ok:
                available_spells.append(spell)

        # Optional: Sort available spells (e.g., by level, then name)
        available_spells.sort(key=lambda s: (s.level_required or 0, s.name))
        return available_spells
