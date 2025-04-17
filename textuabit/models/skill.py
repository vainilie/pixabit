# pixabit/models/skill.py
# MARK: - MODULE DOCSTRING
"""Defines data classes related to Habitica skills and user skill attributes."""

# MARK: - IMPORTS
from typing import Any, Dict, Optional


# KLASS: - Skill
class Skill:
    """Represents a single Habitica skill definition (e.g., from game content).

    Attributes:
        key: The unique identifier string for the skill (e.g., "fireball", "healAll").
        name: The display name of the skill.
        description: The description of the skill's effect.
        mana_cost: The amount of MP required to cast the skill.
        target: The type of target the skill affects ('self', 'user', 'party', 'task').
        skill_type: The general type of skill ('buff', 'spell', 'special').
        notes: Additional notes or details about the skill.
    """

    # FUNC: - __init__
    def __init__(self, skill_data: Dict[str, Any]):
        """Initializes a Skill object from API data.

        Args:
            skill_data: A dictionary containing skill data, typically from the
                        `/content` endpoint's `spells` section.
        """
        # Note: Habitica content uses 'key' for the skill ID, but often refers to it as 'spellId' in actions.
        self.key: Optional[str] = skill_data.get("key")
        self.name: Optional[str] = skill_data.get("text")  # Content uses 'text' for name
        self.description: Optional[str] = skill_data.get(
            "notes"
        )  # Content uses 'notes' for description
        self.mana_cost: Optional[float] = skill_data.get("mana")  # Mana cost can be float
        self.target: Optional[str] = skill_data.get("target")
        self.skill_type: Optional[str] = skill_data.get("type")
        # Add other relevant attributes if needed from the content data
        # self.lvl: Optional[int] = skill_data.get("lvl")
        # self.klass: Optional[str] = skill_data.get("class") # If class-specific

    # FUNC: - __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly representation of the Skill."""
        return f"Skill(key='{self.key}', name='{self.name}', cost={self.mana_cost})"


# KLASS: - UserSkills
class UserSkills:
    """Represents the skill-related stats and learned skills of a specific user.

    Attributes:
        strength: User's base Strength attribute points.
        intelligence: User's base Intelligence attribute points.
        constitution: User's base Constitution attribute points.
        perception: User's base Perception attribute points.
        buff_strength: Additional Strength from buffs.
        buff_intelligence: Additional Intelligence from buffs.
        buff_constitution: Additional Constitution from buffs.
        buff_perception: Additional Perception from buffs.
        # Note: Habitica API doesn't directly list *learned* skills on the user object.
        # Skill availability depends on class and level, typically checked against /content.
        # This class mainly holds the base stats influencing skills.
    """

    # FUNC: - __init__
    def __init__(self, stats_data: Dict[str, Any]):
        """Initializes UserSkills from the 'stats' part of the user object.

        Args:
            stats_data: The 'stats' dictionary from the Habitica User object API response.
                       Should include 'str', 'int', 'con', 'per', and 'buffs'.
        """
        # Base attribute points allocated by the user
        self.strength: float = float(stats_data.get("str", 0.0))
        self.intelligence: float = float(stats_data.get("int", 0.0))
        self.constitution: float = float(stats_data.get("con", 0.0))
        self.perception: float = float(stats_data.get("per", 0.0))

        # Points from active buffs
        buffs = stats_data.get("buffs", {})
        self.buff_strength: float = float(buffs.get("str", 0.0))
        self.buff_intelligence: float = float(buffs.get("int", 0.0))
        self.buff_constitution: float = float(buffs.get("con", 0.0))
        self.buff_perception: float = float(buffs.get("per", 0.0))

    # FUNC: - get_total_stat
    def get_total_stat(self, stat_name: str) -> float:
        """Calculates the total effective value for a given stat (base + buff)."""
        base_value = getattr(self, stat_name.lower(), 0.0)
        buff_value = getattr(self, f"buff_{stat_name.lower()}", 0.0)
        return base_value + buff_value

    # FUNC: - __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly representation."""
        return (
            f"UserSkills(STR={self.strength}+{self.buff_strength}, "
            f"INT={self.intelligence}+{self.buff_intelligence}, "
            f"CON={self.constitution}+{self.buff_constitution}, "
            f"PER={self.perception}+{self.buff_perception})"
        )
