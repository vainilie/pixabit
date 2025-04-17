# pixabit/models/user.py
# MARK: - MODULE DOCSTRING
"""Defines the main User data class, aggregating stats, preferences, timing, etc."""

# MARK: - IMPORTS
from typing import Any, Dict, Optional

# Import other model classes from the same package level
from .skill import UserSkills
from .user_timing import UserPreferences, UserTimestamps

# Import API client type hint for methods if needed
# from ..api import HabiticaAPI


# KLASS: - User
class User:
    """Represents the core Habitica User data, aggregating related info.

    Attributes:
        id: The unique User ID (_id).
        username: User's login name.
        display_name: User's profile display name.
        level: User's current level.
        klass: User's selected class ('warrior', 'mage', 'healer', 'rogue').
        hp: Current health points.
        max_hp: Maximum health points.
        mp: Current mana points.
        max_mp: Maximum mana points.
        exp: Current experience points.
        exp_to_next_level: Experience needed for the next level.
        gp: Current gold points.
        gems: Current gem count (calculated from balance).
        login_incentives: Number of consecutive logins (for Tavern).
        stats: A UserStats object holding STR, INT, CON, PER, and buffs.
        preferences: A UserPreferences object holding sleep, dayStart, etc.
        timestamps: A UserTimestamps object holding loggedIn, lastCron, etc.
        party_id: ID of the user's current party, if any.
        # Add other core user attributes as needed: profile, items, gear, etc.
    """

    # FUNC: - __init__
    def __init__(self, user_data: Dict[str, Any]):
        """Initializes a User object from the full API user data response.

        Args:
            user_data: The dictionary representing the user object from the API.
                       Expected to contain keys like 'id', 'auth', 'stats',
                       'preferences', 'party', 'items', etc.
        """
        if not isinstance(user_data, dict):
            raise TypeError("user_data must be a dictionary.")

        # --- Core Identifiers & Profile ---
        self.id: Optional[str] = user_data.get("id") or user_data.get("_id")
        auth_local = user_data.get("auth", {}).get("local", {})
        self.username: Optional[str] = auth_local.get("username")
        profile = user_data.get("profile", {})
        self.display_name: Optional[str] = profile.get("name")

        # --- Core Stats ---
        stats_data = user_data.get("stats", {})
        self.level: int = stats_data.get("lvl", 0)
        self.klass: Optional[str] = stats_data.get("class")
        self.hp: float = float(stats_data.get("hp", 0.0))
        self.max_hp: int = stats_data.get("maxHealth", 50)  # Default 50
        self.mp: float = float(stats_data.get("mp", 0.0))
        self.max_mp: int = stats_data.get("maxMP", 0)
        self.exp: float = float(stats_data.get("exp", 0.0))
        self.exp_to_next_level: int = stats_data.get("toNextLevel", 0)
        self.gp: float = float(stats_data.get("gp", 0.0))

        # --- Calculated Stats ---
        balance = user_data.get("balance", 0.0)
        self.gems: int = int(balance * 4) if balance > 0 else 0

        self.login_incentives: int = user_data.get("loginIncentives", 0)

        # --- Aggregated Data Classes ---
        self.stats: UserSkills = UserSkills(stats_data)  # Holds STR, INT, CON, PER, buffs
        self.preferences: UserPreferences = UserPreferences(user_data.get("preferences", {}))
        self.timestamps: UserTimestamps = UserTimestamps(
            user_data.get("auth", {}).get("timestamps", {}),  # Pass timestamps dict
            user_data,  # Pass root user dict for lastCron
        )

        # --- Party Info ---
        party_data = user_data.get("party", {})
        self.party_id: Optional[str] = (
            party_data.get("_id") if isinstance(party_data, dict) else None
        )
        # Quest info could be its own class or accessed via party_data if needed externally

        # --- Items/Gear (Optional - Can be large, maybe load on demand) ---
        # self.items = user_data.get("items", {}) # Store raw items dict

        # Add methods like needs_cron(), can_cast(skill_key), etc. later if needed
        self.gear: Optional[Any] = user_data.get("items", {}).get("gear", {}).get("equipped")

    # FUNC: - __repr__
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"User(id='{self.id}', username='{self.username}', class='{self.klass}', level={self.level})"
