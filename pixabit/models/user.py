# pixabit/models/user.py

# SECTION: MODULE DOCSTRING
"""Defines data model classes for representing the Habitica User object and its nested structures.

Includes:
- Nested classes for Profile, Auth, Timestamps, Preferences, Stats, Achievements, Items, PartyInfo, InboxInfo.
- `User`: The main class aggregating all user-related information parsed from the API '/user' endpoint.
- `UserStats`: Handles detailed calculation of effective stats based on base stats, training, buffs, and gear.
"""

# SECTION: IMPORTS
import logging
import math
from datetime import datetime  # Ensure timezone imported
from typing import Any, Dict, List, Optional, Union  # Keep Dict/List

from rich.logging import RichHandler
from textual import log

from pixabit.utils.display import console

FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)])

import emoji_data_python

# Local Imports
try:
    from pixabit.utils.dates import convert_timestamp_to_utc
except ImportError:
    log.warning("Warning: Using placeholder convert_timestamp_to_utc in user.py.")

    def convert_timestamp_to_utc(ts: Any) -> Optional[datetime]:
        return None  # type: ignore


# Type Alias for nested gear content structure (adjust if structure is different)
# Example: {"weapon_warrior_1": {"text": "Sword", "str": 1, ...}, ...}
AllGearContent = Dict[str, Dict[str, Any]]

# SECTION: NESTED USER DATA CLASSES


# KLASS: UserProfile
class UserProfile:
    """Holds user's public profile information."""

    # FUNC: __init__
    def __init__(self, profile_data: Optional[Dict[str, Any]]):
        data = profile_data if isinstance(profile_data, dict) else {}
        _name = data.get("name")
        self.name: Optional[str] = emoji_data_python.replace_colons(_name) if _name else None
        _blurb = data.get("blurb")
        self.blurb: Optional[str] = emoji_data_python.replace_colons(_blurb) if _blurb else None
        # Add other profile fields if needed (imageUrl, etc.)
        # self.image_url: Optional[str] = data.get("imageUrl")

    # FUNC: __repr__
    def __repr__(self) -> str:
        return f"UserProfile(name='{self.name}')"


# KLASS: UserAuth
class UserAuth:
    """Holds user authentication and related info (e.g., username)."""

    # FUNC: __init__
    def __init__(self, auth_data: Optional[Dict[str, Any]]):
        data = auth_data if isinstance(auth_data, dict) else {}
        # Username is usually nested under 'local'
        local_auth = data.get("local", {})
        self.username: Optional[str] = local_auth.get("username") if isinstance(local_auth, dict) else None
        # Add other auth fields if needed (e.g., social IDs from auth_data root)

    # FUNC: __repr__
    def __repr__(self) -> str:
        return f"UserAuth(username='{self.username}')"


# KLASS: UserTimestamps
class UserTimestamps:
    """Holds various timestamps related to user activity."""

    # FUNC: __init__
    def __init__(
        self,
        timestamps_data: Optional[Dict[str, Any]],  # From auth.timestamps
        user_root_data: Optional[Dict[str, Any]],  # From user root object
    ):
        ts_data = timestamps_data if isinstance(timestamps_data, dict) else {}
        root_data = user_root_data if isinstance(user_root_data, dict) else {}

        self.created: Optional[datetime] = convert_timestamp_to_utc(ts_data.get("created"))
        self.updated: Optional[datetime] = convert_timestamp_to_utc(ts_data.get("updated"))
        self.logged_in: Optional[datetime] = convert_timestamp_to_utc(ts_data.get("loggedin"))
        # lastCron is often at the root of the user object
        self.last_cron: Optional[datetime] = convert_timestamp_to_utc(root_data.get("lastCron"))
        # needsCron might indicate if cron run is pending (often at root)
        self.needs_cron: Optional[bool] = root_data.get("needsCron")

    # FUNC: __repr__
    def __repr__(self) -> str:
        login_str = self.logged_in.strftime("%Y-%m-%d %H:%M") if self.logged_in else "None"
        cron_str = self.last_cron.strftime("%Y-%m-%d %H:%M") if self.last_cron else "None"
        return f"UserTimestamps(logged_in='{login_str}', last_cron='{cron_str}')"


# KLASS: UserPreferences
class UserPreferences:
    """Holds user-configurable preferences influencing timing, display, etc."""

    # FUNC: __init__
    def __init__(self, preferences_data: Optional[Dict[str, Any]]):
        data = preferences_data if isinstance(preferences_data, dict) else {}
        self.sleep: bool = data.get("sleep", False)  # Is user resting in the Inn?
        self.day_start: int = int(data.get("dayStart", 0))  # Custom Day Start hour (0-23)
        # Offset from UTC in minutes (e.g., -300 for EST)
        self.timezone_offset: Optional[int] = data.get("timezoneOffset")
        self.timezone_offset_at_last_cron: Optional[int] = data.get("timezoneOffsetAtLastCron")
        # Add other preferences: email, notifications, language, etc. if needed

    # FUNC: __repr__
    def __repr__(self) -> str:
        return f"UserPreferences(sleep={self.sleep}, day_start={self.day_start}, tzOffset={self.timezone_offset})"


# KLASS: UserStats
class UserStats:
    """Holds user core stats, buffs, training, and calculates effective values.

    Requires game content data (specifically gear definitions) for accurate
    calculation of effective stats incorporating gear bonuses.
    """

    # FUNC: __init__
    def __init__(
        self,
        stats_data: Optional[Dict[str, Any]],
        # Equipped gear keys: {"weapon": "weapon_wizard_1", ...}
        equipped_gear: Optional[Dict[str, str]] = None,
        # Game content for all gear: {gear_key: {stat: val, ...}}
        all_gear_content: Optional[AllGearContent] = None,
    ):
        """Initializes UserStats, parsing API data and calculating effective stats.

        Args:
            stats_data: The 'stats' dictionary from the user API object.
            equipped_gear: A dictionary mapping equipped slots ('weapon', 'armor', etc.)
                           to the gear key string currently equipped in that slot.
            all_gear_content: A dictionary containing definitions for all gear items,
                              keyed by the gear key string. Needed for stat bonuses.
        """
        stats = stats_data if isinstance(stats_data, dict) else {}
        self._equipped_gear_keys = equipped_gear if isinstance(equipped_gear, dict) else {}
        self._all_gear_content = all_gear_content if isinstance(all_gear_content, dict) else {}

        # --- Raw Stats from API ---
        self.hp: float = float(stats.get("hp", 0.0))
        self.mp: float = float(stats.get("mp", 0.0))
        self.exp: float = float(stats.get("exp", 0.0))
        self.gp: float = float(stats.get("gp", 0.0))
        self.level: int = int(stats.get("lvl", 0))
        self.klass: Optional[str] = stats.get("class")  # 'warrior', 'rogue', 'wizard', 'healer'
        # Attribute points available to spend
        self.points: int = int(stats.get("points", 0))

        # Base max values (before CON/INT scaling)
        self.max_hp_base: int = int(stats.get("maxHealth", 50))
        self.max_mp_base: int = int(stats.get("maxMP", 0))  # Varies by class
        # EXP needed to reach the next level
        self.exp_to_next_level: int = int(stats.get("toNextLevel", 0))

        # Base attributes (allocated points)
        self.strength: int = int(stats.get("str", 0))
        self.intelligence: int = int(stats.get("int", 0))
        self.constitution: int = int(stats.get("con", 0))
        self.perception: int = int(stats.get("per", 0))

        # Buffs (temporary increases/decreases from spells, food, etc.)
        buffs = stats.get("buffs", {}) if isinstance(stats.get("buffs"), dict) else {}
        self.buff_str: float = float(buffs.get("str", 0.0))
        self.buff_int: float = float(buffs.get("int", 0.0))
        self.buff_con: float = float(buffs.get("con", 0.0))
        self.buff_per: float = float(buffs.get("per", 0.0))
        # Stealth count (from Rogue skill)
        self.buff_stealth: int = int(buffs.get("stealth", 0))
        # Add other buffs if needed (e.g., seafoam, shinyseed directly?)

        # Training (permanent increases from leveling, usually 0 unless reset/legacy)
        training = stats.get("training", {}) if isinstance(stats.get("training"), dict) else {}
        self.train_str: int = int(training.get("str", 0))
        self.train_int: int = int(training.get("int", 0))
        self.train_con: int = int(training.get("con", 0))
        self.train_per: int = int(training.get("per", 0))

        # --- Calculated Effective Stats ---
        # These combine base + training + gear + buffs + level bonus
        self.effective_strength: float = self._calculate_total_stat("str")
        self.effective_intelligence: float = self._calculate_total_stat("int")
        self.effective_constitution: float = self._calculate_total_stat("con")
        self.effective_perception: float = self._calculate_total_stat("per")

        # Calculate Max HP/MP based on effective stats
        # Formulas based on Habitica source/wiki:
        self.max_hp: float = float(self.max_hp_base + math.floor(self.effective_constitution * 2.0))
        self.max_mp: float = float(self.max_mp_base + math.floor(self.effective_intelligence * 2.0))
        # TODO: Verify max MP formula if it differs significantly by class beyond base MP.

    # FUNC: _get_gear_stat_bonus
    def _get_gear_stat_bonus(self, stat_name: str) -> float:
        """Helper to calculate total stat bonus from equipped gear, including class bonus.

        Args:
            stat_name: The attribute key ('str', 'int', 'con', 'per').

        Returns:
            The total calculated bonus from all equipped gear for that stat.
        """
        total_gear_stat = 0.0
        class_bonus_stat = 0.0  # Bonus for wearing gear matching user's class

        # Iterate through the values (gear keys) of the equipped gear dictionary
        for gear_key in self._equipped_gear_keys.values():
            if not gear_key:
                continue  # Skip empty slots

            # Look up the gear definition in the provided content cache
            item_data = self._all_gear_content.get(gear_key)
            if isinstance(item_data, dict):
                # Get the base stat value for this item
                stat_value = float(item_data.get(stat_name, 0.0))
                total_gear_stat += stat_value

                # Add class bonus (50% of item stat) if item's class matches user's class
                if item_data.get("klass") == self.klass:
                    class_bonus_stat += stat_value * 0.5

        return total_gear_stat + class_bonus_stat

    # FUNC: _calculate_total_stat
    def _calculate_total_stat(self, stat_name: str) -> float:
        """Calculates total effective stat (base + train + gear + buff + level bonus).

        Formula: BaseStat + TrainingStat + GearBonus + BuffStat + LevelBonus

        Args:
            stat_name: The attribute key ('str', 'int', 'con', 'per').

        Returns:
            The total effective value for the specified stat.
        """
        # Fetch components using getattr for safety, default to 0 or 0.0
        base_stat = getattr(self, stat_name, 0)  # e.g., self.strength (int)
        train_stat = getattr(self, f"train_{stat_name}", 0)  # e.g., self.train_str (int)
        buff_stat = getattr(self, f"buff_{stat_name}", 0.0)  # e.g., self.buff_str (float)
        gear_stat = self._get_gear_stat_bonus(stat_name)  # Calculated float bonus

        # Level bonus: 1 point per 2 levels, capped at 50 points (at level 100+)
        level_bonus = min(50.0, math.floor(self.level / 2.0))

        # Summing components: ints will be promoted to float
        return float(base_stat + train_stat + gear_stat + buff_stat + level_bonus)

    # FUNC: __repr__
    def __repr__(self) -> str:
        # Use calculated max values in repr
        return f"UserStats(lvl={self.level}, class='{self.klass}', " f"hp={self.hp:.1f}/{self.max_hp:.1f}, mp={self.mp:.1f}/{self.max_mp:.1f}, " f"exp={self.exp:.0f}/{self.exp_to_next_level}, gp={self.gp:.2f})"


# KLASS: UserAchievements
class UserAchievements:
    """Holds user's achievements progress."""

    # FUNC: __init__
    def __init__(self, achievements_data: Optional[Dict[str, Any]]):
        data = achievements_data if isinstance(achievements_data, dict) else {}
        # Extract specific known achievements
        self.challenges_completed: List[str] = data.get("challenges", [])  # List of challenge IDs completed
        self.quests_completed: Dict[str, int] = data.get("quests", {})  # Dict {quest_key: completion_count}
        self.perfect_days: int = int(data.get("perfect", 0))  # Count of perfect days (all dailies done)
        self.streak: int = int(data.get("streak", 0))  # Max perfect day streak
        # Might be login incentive count? API docs unclear sometimes.
        self.login_incentives: int = int(data.get("loginIncentives", 0))
        # Add ultimate gear achievements,backer status, contributor level etc. if needed
        # self.ultimate_gear_achieved: bool = data.get("ultimateGearSets", {}).get("strength", False) # Example

        # Store all earned achievement keys if structure is {key: true/value}
        self.earned_map: Dict[str, Any] = {
            key: value
            for key, value in data.items()
            # Filter out the known complex structures if desired
            if key
            not in (
                "challenges",
                "quests",
                "perfect",
                "streak",
                "loginIncentives",
                "ultimateGearSets",
            )
        }
        self.earned_list: List[str] = list(self.earned_map.keys())

    # FUNC: __repr__
    def __repr__(self) -> str:
        quests_count = sum(self.quests_completed.values()) if self.quests_completed else 0
        return f"UserAchievements(earned={len(self.earned_list)}, " f"quests={quests_count}, perfect={self.perfect_days}, streak={self.streak})"


# KLASS: UserItems
class UserItems:
    """Holds user's inventory: gear, items, pets, mounts etc."""

    # FUNC: __init__
    def __init__(self, items_data: Optional[Dict[str, Any]]):
        data = items_data if isinstance(items_data, dict) else {}
        gear = data.get("gear", {}) if isinstance(data.get("gear"), dict) else {}
        # Currently equipped gear/costume {slot: item_key}
        self.gear_equipped: Dict[str, Optional[str]] = gear.get("equipped", {})
        self.gear_costume: Dict[str, Optional[str]] = gear.get("costume", {})
        # All gear owned {item_key: True/False} - Note: might not list *all* gear
        self.gear_owned: Dict[str, bool] = gear.get("owned", {})

        # Eggs, Food, HatchingPotions, Pets, Mounts, Special Items, Quests etc.
        self.eggs: Dict[str, int] = data.get("eggs", {})  # {egg_name: count}
        self.food: Dict[str, int] = data.get("food", {})  # {food_name: count}
        self.hatching_potions: Dict[str, int] = data.get("hatchingPotions", {})  # {potion_name: count}
        self.pets: Dict[str, int] = data.get("pets", {})  # {Pet-Species: feed_count} or {Pet-Name: feed_count}? Check API. Usually {Wolf-Base: 5}
        self.mounts: Dict[str, bool] = data.get("mounts", {})  # {Mount-Species: True} or {Mount-Name: True}? Usually {Wolf-Base: True}
        self.special: Dict[str, int] = data.get("special", {})  # {item_key: count} e.g., rebirthOrb, mysteryItem
        self.quests: Dict[str, int] = data.get("quests", {})  # {quest_scroll_key: count}

    # FUNC: __repr__
    def __repr__(self) -> str:
        # Count owned items for a simpler repr
        gear_count = sum(1 for owned in self.gear_owned.values() if owned)
        pet_count = len(self.pets)
        mount_count = len(self.mounts)
        return f"UserItems(gear={gear_count}, pets={pet_count}, mounts={mount_count}, ...)"


# KLASS: UserPartyInfo
class UserPartyInfo:
    """Holds information about the user's party membership."""

    # FUNC: __init__
    def __init__(self, party_data: Optional[Dict[str, Any]]):
        data = party_data if isinstance(party_data, dict) else {}
        # The party object in /user might just contain the ID
        self.party_id: Optional[str] = data.get("_id")
        # Or check for a 'party' key at the user root if structure differs
        # Add other party details if the API includes more here (unlikely for /user)

    # FUNC: __repr__
    def __repr__(self) -> str:
        return f"UserPartyInfo(party_id='{self.party_id}')"


# KLASS: UserInboxInfo
class UserInboxInfo:
    """Holds information about the user's inbox status."""

    # FUNC: __init__
    def __init__(self, inbox_data: Optional[Dict[str, Any]]):
        data = inbox_data if isinstance(inbox_data, dict) else {}
        # Count of unread messages (requires separate fetch for details)
        self.new_messages: int = int(data.get("newMessages", 0))
        # Has user opted out of receiving new PMs?
        self.opt_out: bool = data.get("optOut", False)
        # List of blocked user IDs
        self.blocks: List[str] = data.get("blocks", [])
        # Inbox messages - often just contains message IDs or is empty in /user response
        self.messages: Union[List[str], Dict[str, Any]] = data.get("messages", [])  # Type can vary

    # FUNC: __repr__
    def __repr__(self) -> str:
        opt = " (Opted Out)" if self.opt_out else ""
        return f"UserInboxInfo(new={self.new_messages}{opt}, blocks={len(self.blocks)})"


# SECTION: MAIN USER CLASS


# KLASS: User
class User:
    """Represents the core Habitica User object, aggregating nested data structures.

    Parses the full user data object from the API '/user' endpoint and provides
    access to profile, auth, stats, preferences, items, etc., via nested objects.
    """

    # FUNC: __init__
    def __init__(
        self,
        user_data: Dict[str, Any],
        all_gear_content: Optional[AllGearContent] = None,  # Pass gear content for UserStats
    ):
        """Initializes a User object from the full API user data response.

        Args:
            user_data: The dictionary representing the user object from the API.
            all_gear_content: Optional dictionary containing game content definitions
                              for all gear items (needed for accurate UserStats).

        Raises:
            TypeError: If user_data is not a dictionary.
            ValueError: If user_data is missing essential 'id' or '_id'.
        """
        if not isinstance(user_data, dict):
            raise TypeError("user_data must be a dictionary.")

        # --- Core User Identifier ---
        self.id: Optional[str] = user_data.get("id") or user_data.get("_id")
        if not self.id:
            raise ValueError("User data is missing 'id' or '_id'.")

        # --- Balance and Login ---
        # Balance is currency for gems (1 balance = 4 gems)
        self.balance: float = float(user_data.get("balance", 0.0))
        self.gems: int = int(self.balance * 4) if self.balance > 0 else 0
        # Consecutive check-ins count? (API docs vary)
        self.login_incentives: int = int(user_data.get("loginIncentives", 0))

        # --- Instantiate Nested Data Classes (passing relevant sub-dicts) ---
        self.profile: UserProfile = UserProfile(user_data.get("profile"))
        self.auth: UserAuth = UserAuth(user_data.get("auth"))
        self.preferences: UserPreferences = UserPreferences(user_data.get("preferences"))
        # Timestamps requires auth.timestamps and user root data
        self.timestamps: UserTimestamps = UserTimestamps(user_data.get("auth", {}).get("timestamps"), user_data)
        self.items: UserItems = UserItems(user_data.get("items"))
        self.achievements: UserAchievements = UserAchievements(user_data.get("achievements"))
        # Party info might be at root or nested, check common patterns
        self.party_info: UserPartyInfo = UserPartyInfo(user_data.get("party"))
        self.inbox_info: UserInboxInfo = UserInboxInfo(user_data.get("inbox"))

        # UserStats requires stats_data, equipped_gear from UserItems, and all_gear_content
        self.stats: UserStats = UserStats(
            stats_data=user_data.get("stats"),
            equipped_gear=self.items.gear_equipped,  # Get from UserItems instance
            all_gear_content=all_gear_content,  # Pass from constructor arg
        )

        # --- Convenience Accessors (Optional but useful) ---
        self.username: Optional[str] = self.auth.username
        self.display_name: Optional[str] = self.profile.name
        self.level: int = self.stats.level
        self.klass: Optional[str] = self.stats.klass
        self.hp: float = self.stats.hp
        self.max_hp: float = self.stats.max_hp
        self.mp: float = self.stats.mp
        self.max_mp: float = self.stats.max_mp
        self.exp: float = self.stats.exp
        self.exp_to_next_level: int = self.stats.exp_to_next_level
        self.gp: float = self.stats.gp
        self.party_id: Optional[str] = self.party_info.party_id
        self.is_sleeping: bool = self.preferences.sleep

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        return f"User(id='{self.id}', username='{self.username}', " f"class='{self.klass}', level={self.level})"
