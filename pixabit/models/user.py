# pixabit/models/user.py

# ─── Model ────────────────────────────────────────────────────────────────────
#            Habitica User Model and Subcomponents
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for the Habitica User object and its complex nested
structures like profile, auth, preferences, stats, items, achievements, etc.
Includes methods for calculating derived stats like effective attributes and max HP/MP.
"""

# SECTION: IMPORTS
from __future__ import annotations  # Allow forward references

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal  # Use standard types

# External Libs
import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,  # For internal storage
    ValidationError,
    ValidationInfo,
    computed_field,  # For calculated fields in dumps
    field_validator,
    model_validator,
)

# Local Imports
try:
    from pixabit.api.client import HabiticaClient
    from pixabit.config import HABITICA_DATA_PATH, USER_ID  # If USER_ID needed as fallback
    from pixabit.helpers._json import load_pydantic_model, save_json, save_pydantic_model
    from pixabit.helpers._logger import log
    from pixabit.helpers.DateTimeHandler import DateTimeHandler

    # Dependent models (use TYPE_CHECKING if circularity is a risk)
    from .game_content import Gear, StaticContentManager  # Need Gear model + manager for stats
    from .message import Message, MessageList  # For inbox
    from .party import QuestInfo  # For user's view of party quest
    from .tag import Tag, TagList  # For user tags
except ImportError:
    # Fallbacks
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    USER_ID = "fallback_user_id"
    HABITICA_DATA_PATH = Path("./pixabit_cache")

    def save_json(d, p, **k):
        pass

    def save_pydantic_model(m, p, **k):
        pass

    def load_pydantic_model(cls, p, **k):
        return None

    class DateTimeHandler:
        def __init__(self, timestamp):
            self._ts = timestamp

        @property
        def utc_datetime(self):
            return None

    log.warning("user.py: Could not import dependencies. Using fallbacks.")

# SECTION: USER SUBCOMPONENT MODELS


# KLASS: UserProfile
class UserProfile(BaseModel):
    """Represents user profile information like display name and blurb."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str = Field("", description="User's display name (parsed).")
    blurb: str | None = Field(None, description="User's profile description (parsed).")  # Blurb can be absent

    @field_validator("name", "blurb", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any) -> str | None:
        """Parse text and replace emoji shortcodes, strips whitespace."""
        if isinstance(value, str):
            parsed = emoji_data_python.replace_colons(value).strip()
            return parsed  # Return potentially empty string or None
        # Handle name default elsewhere if needed
        return None


# KLASS: UserAuthLocal (Nested under UserAuth)
class UserAuthLocal(BaseModel):
    """Nested local authentication details."""

    model_config = ConfigDict(extra="ignore")
    username: str | None = Field(None)
    # email: str | None = None # Ignore email for privacy unless needed


# KLASS: UserAuthTimestamps (Nested under UserAuth)
class UserAuthTimestamps(BaseModel):
    """Nested timestamp information for authentication."""

    model_config = ConfigDict(extra="ignore")
    created: datetime | None = None
    updated: datetime | None = None
    loggedin: datetime | None = None

    @field_validator("created", "updated", "loggedin", mode="before")
    @classmethod
    def parse_datetime_utc(cls, value: Any) -> datetime | None:
        """Parses timestamp using DateTimeHandler."""
        # Allow null values through
        if value is None:
            return None
        handler = DateTimeHandler(timestamp=value)
        if handler.utc_datetime is None and value is not None:
            log.warning(f"Could not parse auth timestamp: {value!r}")
        return handler.utc_datetime


# KLASS: UserAuth
class UserAuth(BaseModel):
    """Represents user authentication details (wrapping local and timestamps)."""

    model_config = ConfigDict(extra="ignore")

    local: UserAuthLocal | None = Field(default_factory=UserAuthLocal)
    timestamps: UserAuthTimestamps | None = Field(default_factory=UserAuthTimestamps)

    # Convenience properties for easier access
    @property
    def username(self) -> str | None:
        return self.local.username if self.local else None

    @property
    def created_at(self) -> datetime | None:
        return self.timestamps.created if self.timestamps else None

    @property
    def updated_at(self) -> datetime | None:
        return self.timestamps.updated if self.timestamps else None

    @property
    def logged_in_at(self) -> datetime | None:
        return self.timestamps.loggedin if self.timestamps else None


# KLASS: UserPreferences
class UserPreferences(BaseModel):
    """User-specific preferences and settings."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    sleep: bool = Field(False, description="Whether user is resting in the Inn.")
    day_start: int = Field(0, alias="dayStart", description="User's preferred day start hour (0–23).")
    timezone_offset: int | None = Field(None, alias="timezoneOffset", description="User's current timezone offset from UTC in minutes.")
    timezone_offset_at_last_cron: int | None = Field(None, alias="timezoneOffsetAtLastCron", description="User's timezone offset at the time of the last cron.")
    # Other preferences like: email, language, chatRevoked, background, costume, shirt etc. ignored by default

    @field_validator("day_start", mode="before")
    @classmethod
    def parse_day_start(cls, value: Any) -> int:
        """Validate and clamp day start hour."""
        try:
            ds = int(value)
            return max(0, min(23, ds))  # Clamp between 0 and 23
        except (ValueError, TypeError):
            log.debug(f"Invalid dayStart value '{value}'. Using default 0.")
            return 0


# KLASS: Buffs (Used within UserStats)
class Buffs(BaseModel):
    """Temporary stat increases/decreases from spells, food, etc."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)  # Allow extra buffs like seafoam

    # Use aliases for fields conflicting with built-ins/types
    con: float = Field(0.0)  # Buffs can be floats (gear sets)
    int_: float = Field(0.0, alias="int")
    per: float = Field(0.0)
    str_: float = Field(0.0, alias="str")
    stealth: int = Field(0)  # Stealth usually integer buff stacks

    @field_validator("con", "int_", "per", "str_", mode="before")
    @classmethod
    def ensure_float(cls, value: Any) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("stealth", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0


# KLASS: Training (Used within UserStats)
class Training(BaseModel):
    """Permanent stat increases from leveling/resets (can have fractions)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)  # Ignore rev, assigned etc.

    con: float = Field(0.0)
    int_: float = Field(0.0, alias="int")
    per: float = Field(0.0)
    str_: float = Field(0.0, alias="str")

    @field_validator("con", "int_", "per", "str_", mode="before")
    @classmethod
    def ensure_float(cls, value: Any) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0


# KLASS: EquippedGear (Used within UserItems)
class EquippedGear(BaseModel):
    """Represents gear currently equipped by the user."""

    model_config = ConfigDict(extra="allow")  # Allow other potential slots

    # Define known slots explicitly
    weapon: str | None = Field(None)
    armor: str | None = Field(None)
    head: str | None = Field(None)
    shield: str | None = Field(None)  # Can be None if weapon is two-handed
    headAccessory: str | None = Field(None, alias="headAccessory")
    eyewear: str | None = Field(None)
    body: str | None = Field(None)  # e.g., Robe
    back: str | None = Field(None)  # e.g., Cape

    def get_equipped_item_keys(self) -> list[str]:
        """Returns a list of non-None gear keys currently equipped."""
        # Use model_dump to get values respecting aliases, exclude None
        return [val for val in self.model_dump(exclude_none=True).values() if isinstance(val, str)]

    def calculate_total_bonus(self, user_class: str | None, gear_data: dict[str, Gear]) -> dict[str, float]:
        """Calculates total stat bonuses from equipped gear, considering class match.

        Args:
             user_class: User's character class (e.g., 'warrior').
             gear_data: Dict mapping gear keys to validated Gear objects.

        Returns:
             Dictionary {'str': bonus, 'con': bonus, 'int': bonus, 'per': bonus}.
        """
        total_bonus = {"str": 0.0, "con": 0.0, "int": 0.0, "per": 0.0}
        # Note: Gear model fields are already corrected (strength, intelligence etc.)
        # Mapping direct gear field names to the bonus keys
        stats_map_gear_to_bonus = {"strength": "str", "constitution": "con", "intelligence": "int", "perception": "per"}

        for gear_key in self.get_equipped_item_keys():
            item: Gear | None = gear_data.get(gear_key)
            # Check if item exists and is a validated Gear model
            if item and isinstance(item, Gear):
                # --- CORRECTED CLASS CHECK ---
                # Class bonus multiplier (1.5x if item class matches user class)
                # Habitica defines 'base' sometimes for general gear? Including 'base' match here too.
                # Check if item.special_class is not None before comparing
                is_class_match = item.special_class is not None and (item.special_class == user_class)
                bonus_multiplier = 1.5 if is_class_match else 1.0
                # --- END CORRECTION ---

                # Add item stats to total, applying multiplier
                for gear_stat_field, bonus_key in stats_map_gear_to_bonus.items():
                    # Get stat value directly from the item model field
                    stat_value = getattr(item, gear_stat_field, 0.0)
                    total_bonus[bonus_key] += stat_value * bonus_multiplier
            # else: log.debug(f"Gear key '{gear_key}' not found in provided gear_data or is not a Gear object.")
        print(total_bonus)
        return total_bonus


# KLASS: UserItems
class UserItems(BaseModel):
    """Holds user's inventory: gear, consumables, pets, mounts, etc."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    gear_equipped: EquippedGear = Field(default_factory=EquippedGear, alias="equipped")
    gear_costume: EquippedGear = Field(default_factory=EquippedGear, alias="costume")
    # gear.owned maps key -> True/False
    # gear_owned: dict[str, bool] = Field(default_factory=dict, alias="owned")
    # Consumables
    # eggs: dict[str, int] = Field(default_factory=dict)
    # food: dict[str, int] = Field(default_factory=dict)
    # hatchingPotions: dict[str, int] = Field(default_factory=dict, alias="hatchingPotions")
    # Companions
    # pets: dict[str, int] = Field(default_factory=dict, description="{Pet-SpeciesKey: feed_count}")  # e.g. {"BearCub-Base": 5}
    # mounts: dict[str, bool] = Field(default_factory=dict, description="{Mount-SpeciesKey: True}")  # e.g. {"BearCub-Base": True}
    # Special items & Quest scrolls
    # special: dict[str, int] = Field(default_factory=dict)  # Orbs, Cards etc. {itemKey: count}
    quests: dict[str, int] = Field(default_factory=dict)  # {questKey: count}

    @model_validator(mode="before")
    @classmethod
    def structure_gear_data(cls, data: Any) -> dict[str, Any]:
        """Ensure gear keys (equipped, costume, owned) exist from gear sub-dict."""
        if not isinstance(data, dict):
            return data
        values = data.copy()
        # Check if fields are already top-level (might happen if processing elsewhere)
        if "equipped" not in values and "gear" in values and isinstance(values["gear"], dict):
            gear_data = values["gear"]
            values["equipped"] = gear_data.get("equipped", {})
            values["costume"] = gear_data.get("costume", {})
            values["owned"] = gear_data.get("owned", {})
            # Optionally remove the original 'gear' key if desired
            # values.pop("gear")
        # Ensure defaults if keys are still missing
        for key in ["equipped", "costume", "owned"]:
            if key not in values:
                values[key] = {}

        # Validate counts for items? Pydantic handles dict[str, int] usually
        return values


# KLASS: UserAchievements
class UserAchievements(BaseModel):
    """Holds user's achievements progress."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    challenges: list[str] = Field(default_factory=list, description="List of challenge IDs completed.")
    quests: dict[str, int] = Field(default_factory=dict, description="{quest_key: completion_count}.")
    perfect_days: int = Field(0, alias="perfect", description="Count of perfect days.")
    streak: int = Field(0, description="Max consecutive perfect days streak.")
    loginIncentives: int = Field(0, alias="loginIncentives", description="Count of login incentives claimed for achievements.")
    ultimateGearSets: dict[str, bool] = Field(default_factory=dict, alias="ultimateGearSets")
    # Store other achievements found directly under 'achievements'
    other_achievements: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def separate_other_achievements(cls, data: Any) -> dict[str, Any]:
        """Separates known fields from arbitrary others under 'achievements'."""
        if not isinstance(data, dict):
            return data
        values = {}
        known_keys = {"challenges", "quests", "perfect", "streak", "loginIncentives", "ultimateGearSets"}
        other_achievements_dict = {}
        for k, v in data.items():
            if k in known_keys:
                values[k] = v  # Keep known keys
            else:
                other_achievements_dict[k] = v  # Put others into separate dict
        values["other_achievements"] = other_achievements_dict
        return values

    @field_validator("perfect_days", "streak", "loginIncentives", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0


# KLASS: UserPartyInfo (User's perspective)
class UserPartyInfo(BaseModel):
    """Holds information about the user's current party membership and quest status."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    party_id: str | None = Field(None, alias="_id", description="The unique ID of the party the user is in.")
    # The user object often contains a snapshot of the party quest status relevant *to the user*.
    quest: QuestInfo | None = Field(None, description="User's view of the active party quest status and progress.")

    @model_validator(mode="before")
    @classmethod
    def ensure_party_id_mapping(cls, data: Any) -> dict[str, Any]:
        """Map party._id to party_id if structure is party:{_id: ...}."""
        if not isinstance(data, dict):
            return data  # Or {}
        values = data.copy()
        # If raw data looks like user.party = {_id: ..., quest: ...}
        if "_id" in values and "party_id" not in values:
            values["party_id"] = values["_id"]
        return values


# KLASS: UserInboxInfo
class UserInboxInfo(BaseModel):
    """Holds information about the user's inbox."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    newMessages: int = Field(0, alias="newMessages", description="Count of unread private messages.")
    hasNew: bool = Field(False, alias="hasNew", description="Flag indicating a new gift message.")  # Less informative, count is better
    optOut: bool = Field(False, alias="optOut", description="Whether the user has opted out of receiving new PMs.")
    blocks: list[str] = Field(default_factory=list, description="List of user IDs blocked by this user.")
    # Optional: Can embed received messages directly if API provides them here
    messages: MessageList | None = None  # Type hint

    @field_validator("newMessages", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    @field_validator("messages", mode="before")  # Example if API embeds messages as dict {msgId: data}
    @classmethod
    def messages_dict_to_list(cls, value: Any) -> list[dict] | None:
        """Converts message dict to list for MessageList validation."""
        if isinstance(value, dict):
            return list(value.values())
        elif isinstance(value, list):
            return value  # Already a list
        return None  # Return None or empty list if invalid format


# KLASS: UserStats (Main Stats Container) - Continuing from previous section
class UserStats(BaseModel):
    """Represents the user's core numerical stats and attributes."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    # --- Resources ---
    hp: float = Field(default=50.0)
    mp: float = Field(default=0.0)
    exp: float = Field(default=0.0)
    gp: float = Field(default=0.0)
    lvl: int = Field(default=1)
    klass: Literal["warrior", "rogue", "healer", "wizard"] | None = Field(None, alias="class")

    # --- Base Attributes (Allocated Points) ---
    base_con: int = Field(0, alias="con")
    base_int_: int = Field(0, alias="int")
    base_per: int = Field(0, alias="per")
    base_str_: int = Field(0, alias="str")

    # --- Base Max Values (Before CON/INT bonuses) ---
    max_hp_base: int = Field(50, alias="maxHealth")
    max_mp_base: int = Field(10, alias="maxMP")  # Base before INT bonus
    exp_to_next_level: int = Field(0, alias="toNextLevel")

    # --- Modifiers (Nested Models) ---
    buffs: Buffs = Field(default_factory=Buffs)
    training: Training = Field(default_factory=Training)

    # --- Validators ---
    @field_validator("hp", "mp", "exp", "gp", mode="before")
    @classmethod
    def ensure_float_resources(cls, value: Any) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("lvl", "max_hp_base", "max_mp_base", "exp_to_next_level", "base_con", "base_int_", "base_per", "base_str_", mode="before")  # Add base stats here
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensures integer fields are parsed correctly."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    # No separate calculation class needed. Calculations happen on User or here if self-contained.

    def calculate_level_bonus(self) -> float:
        """Calculate stat bonus from level."""
        return min(50.0, math.floor(self.lvl / 2.0))  # Max bonus of +50 from levels

    def calculate_stats_before_gear(self) -> dict[str, float]:
        """Calculates stats combining base, buffs, and level bonus."""
        level_bonus = self.calculate_level_bonus()
        return {
            "con": float(self.base_con) + self.buffs.con + level_bonus,
            "int": float(self.base_int_) + self.buffs.int_ + level_bonus,
            "per": float(self.base_per) + self.buffs.per + level_bonus,
            "str": float(self.base_str_) + self.buffs.str_ + level_bonus,
        }


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MAIN USER MODEL


# KLASS: User
class User(BaseModel):
    """Represents the complete Habitica User object, aggregating data from the API."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, validate_assignment=True)

    # --- Top-Level Fields ---
    id: str = Field(..., alias="_id", description="Unique User UUID.")
    balance: float = Field(default=0.0, description="User's gem balance / 4.")
    needs_cron: bool = Field(False, alias="needsCron", description="Flag indicating cron needs to run.")
    last_cron: datetime | None = Field(None, alias="lastCron", description="Timestamp of the last cron run (UTC).")
    login_incentives: int = Field(0, alias="loginIncentives", description="Current login incentive count for rewards.")

    # --- Nested Subcomponent Models ---
    profile: UserProfile = Field(default_factory=UserProfile)
    auth: UserAuth = Field(default_factory=UserAuth)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    items: UserItems = Field(default_factory=UserItems)
    achievements: UserAchievements = Field(default_factory=UserAchievements)
    party: UserPartyInfo = Field(default_factory=UserPartyInfo)
    inbox: UserInboxInfo = Field(default_factory=UserInboxInfo)
    stats: UserStats = Field(default_factory=UserStats)
    tags: TagList | None = Field(default_factory=TagList, description="User's defined tags.")  # Populate from separate endpoint typically
    challenges: list[str] | None = Field([], description="List of Challenges")
    # --- Calculated Fields (Storage) ---
    # Store results of expensive calculations here, mark Private or Exclude
    _calculated_stats: dict[str, Any] = PrivateAttr(default_factory=dict)

    # --- Validators ---
    @model_validator(mode="before")
    @classmethod
    def ensure_id_mapping(cls, data: Any) -> dict[str, Any]:
        """Map _id to id if needed."""
        if isinstance(data, dict):
            if "_id" in data and "id" not in data:
                data["id"] = data["_id"]
            # Handle tags being directly in user data vs loaded separately
            if "tags" in data and isinstance(data["tags"], list):
                # Pydantic will validate the list against the TagList model
                pass
            else:
                data["tags"] = []  # Ensure tags field exists for TagList parsing

        return data if isinstance(data, dict) else {}

    @field_validator("last_cron", mode="before")
    @classmethod
    def parse_last_cron_utc(cls, value: Any) -> datetime | None:
        """Parse lastCron timestamp using DateTimeHandler."""
        handler = DateTimeHandler(timestamp=value)
        return handler.utc_datetime

    @field_validator("balance", mode="before")
    @classmethod
    def ensure_float_balance(cls, value: Any) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("login_incentives", mode="before")
    @classmethod
    def ensure_int_login(cls, value: Any) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    @field_validator("tags", mode="before")
    @classmethod
    def tags_list_to_taglist(cls, value: Any) -> dict[str, list]:
        """Ensure tags input is structured correctly for TagList model."""
        if isinstance(value, list):
            # Wrap list in a dict for Pydantic to parse into TagList(tags=...)
            return {"tags": value}
        elif isinstance(value, dict) and "tags" in value:
            return value  # Already structured
        return {"tags": []}  # Default empty

    # --- Convenience Properties (Accessing nested data) ---
    @property
    def username(self) -> str | None:
        return self.auth.username

    @property
    def display_name(self) -> str:
        return self.profile.name or self.username or "N/A"  # Fallback display

    @property
    def level(self) -> int:
        return self.stats.lvl

    @property
    def klass(self) -> str | None:
        return self.stats.klass

    @property
    def hp(self) -> float:
        return self.stats.hp

    @property
    def mp(self) -> float:
        return self.stats.mp

    @property
    def gp(self) -> float:
        return self.stats.gp

    @property
    def exp(self) -> float:
        return self.stats.exp

    @property
    def party_id(self) -> str | None:
        return self.party.party_id

    @property
    def is_sleeping(self) -> bool:
        return self.preferences.sleep

    @property
    def exp_to_next_level(self) -> int:
        return self.stats.exp_to_next_level

    @computed_field(description="Calculated Gem count.")
    @property
    def gems(self) -> int:
        """Calculated gem count from balance (balance = gems / 4)."""
        return int(self.balance * 4) if self.balance > 0 else 0

    @property
    def stealth(self) -> int:
        """Shortcut to the stealth buff value."""
        return self.stats.buffs.stealth

    @property
    def is_on_boss_quest(self) -> bool:
        """Check if user is currently on an active boss quest."""
        if self.party.quest and self.party.quest.is_active_and_ongoing:
            # Requires fetching static data and checking quest type
            static_details = self.party.static_quest_details  # Access cached static data
            if static_details and getattr(static_details, "is_boss_quest", False):
                return True
        return False

    # --- Accessing Calculated Stats ---

    @property
    def effective_stats(self) -> dict[str, float]:
        """Returns the pre-calculated effective stats (STR, CON, INT, PER). Call `calculate_effective_stats` first."""
        return self._calculated_stats.get("effective_stats", {})

    @property
    def max_hp(self) -> float:
        """Returns the pre-calculated maximum HP. Call `calculate_effective_stats` first."""
        return self._calculated_stats.get("max_hp", 50.0)  # Default 50

    @property
    def max_mp(self) -> float:
        """Returns the pre-calculated maximum MP. Call `calculate_effective_stats` first."""
        # Base MP depends on class - needs logic or rely on calculated value
        return self._calculated_stats.get("max_mp", 10.0)  # Default base

    # --- Calculation Method ---

    def calculate_effective_stats(self, gear_data: dict[str, Gear] | None = None) -> None:
        """Calculates total effective stats (base, buffs, training, level, gear)
        and max HP/MP. Stores the results in the internal `_calculated_stats` dict.

        Args:
            gear_data: A dictionary mapping gear keys to **validated Gear objects**.
                       Required for accurate calculations. If None, gear bonus will be 0.
        """
        log.debug(f"Calculating effective stats for user {self.id}...")
        if gear_data is None:
            log.warning("No gear_data provided to calculate_effective_stats. Gear bonus will be zero.")
            gear_data = {}  # Use empty dict

        # 1. Get stats before gear bonus (base + buffs + training + level)
        stats_before_gear = self.stats.calculate_stats_before_gear()

        # 2. Calculate gear bonus
        gear_bonus = self.items.gear_equipped.calculate_total_bonus(self.klass, gear_data)

        # 3. Combine for final effective stats
        eff_stats: dict[str, float] = {}
        for stat in ["str", "con", "int", "per"]:
            eff_stats[stat] = stats_before_gear.get(stat, 0.0) + gear_bonus.get(stat, 0.0)
        log.debug(f" -> StatsBeforeGear: {stats_before_gear}")
        log.debug(f" -> GearBonus: {gear_bonus}")
        log.debug(f" -> EffectiveStats: {eff_stats}")

        # 4. Calculate Max HP/MP using effective CON/INT
        effective_con = eff_stats.get("con", 0.0)
        effective_int = eff_stats.get("int", 0.0)
        # Base HP + 2HP per Effective CON point (floor CON first?) Habitica math can be subtle. Assume direct multiplier for now.
        max_hp_calc = float(self.stats.max_hp_base + (effective_con * 2.0))
        # Base MP + 2MP per Effective INT point? (or mana multiplier based on class?) Need accurate formula. Using +2/INT for now.
        # Example: Wizard MP: 30 + 2.5*INT + Lvl/2; Healer MP: 30 + 2*INT + Lvl/4 ? Research needed.
        # Using a simplified base + INT multiplier
        max_mp_calc = float(self.stats.max_mp_base + (effective_int * 2.0))
        log.debug(f" -> Calculated MaxHP: {max_hp_calc} (Base: {self.stats.max_hp_base}, EffCON: {effective_con:.1f})")
        log.debug(f" -> Calculated MaxMP: {max_mp_calc} (Base: {self.stats.max_mp_base}, EffINT: {effective_int:.1f})")

        # 5. Store all calculated values internally
        self._calculated_stats["effective_stats"] = eff_stats
        self._calculated_stats["max_hp"] = round(max_hp_calc, 1)
        self._calculated_stats["max_mp"] = round(max_mp_calc, 1)
        # Can store other derived values here too if needed
        # self._calculated_stats["gems"] = self.gems

    # --- Factory & Serialization ---
    @classmethod
    def create_from_raw_data(cls, raw_data: dict) -> User | None:
        """Validates raw API data into a User object."""
        if not isinstance(raw_data, dict):
            log.error("Invalid raw data type for User creation: Expected dict.")
            return None
        try:
            user_instance = cls.model_validate(raw_data)
            log.info(f"User model created successfully for ID: {user_instance.id}")
            return user_instance
        except ValidationError as e:
            log.error(f"Validation failed creating User model: {e}", exc_info=False)
            return None
        except Exception as e:
            log.exception("Unexpected error creating User from raw data.")
            return None

    # Default model_dump/model_dump_json are sufficient now


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MAIN EXECUTION (Example/Test)
async def main():
    """Demo function to retrieve, process, and display user data."""
    log.info("--- User Model Demo ---")
    user_instance: User | None = None

    try:
        cache_dir = HABITICA_DATA_PATH / "user"
        cache_dir.mkdir(exist_ok=True, parents=True)
        raw_path = cache_dir / "user_raw.json"
        processed_path = cache_dir / "user_processed.json"

        # 1. Fetch raw data
        log.info("Fetching user data from API...")
        api = HabiticaClient()  # Assumes configured
        raw_data = await api.get_user_data()
        if not raw_data:
            log.error("Failed to fetch user data. Exiting demo.")
            return None
        log.success("Fetched raw user data.")
        save_json(raw_data, raw_path.name, folder=raw_path.parent)  # Save raw

        # 2. Create User model
        log.info("Validating raw data into User model...")
        user_instance = User.create_from_raw_data(raw_data)
        if not user_instance:
            log.error("Failed to create User model from raw data.")
            return None

        # 3. Load Static Gear Data (needed for calculation)
        log.info("Loading static gear data for stat calculation...")
        content_manager = StaticContentManager()  # Assumes it can load/cache
        static_gear_data = await content_manager.get_gear()  # Returns dict[str, Gear]
        if not static_gear_data:
            log.warning("Could not load static gear data. Effective stats will exclude gear bonus.")

        # 4. Calculate Effective Stats
        log.info("Calculating effective stats...")
        user_instance.calculate_effective_stats(gear_data=static_gear_data)
        log.success("Effective stats calculated.")

        # 5. Display Data
        print("\n--- Basic Info ---")
        print(f"ID          : {user_instance.id}")
        print(f"Username    : {user_instance.username}")
        print(f"Display Name: {user_instance.display_name}")
        print(f"Level       : {user_instance.level}")
        print(f"Class       : {user_instance.klass}")
        print(f"Sleeping    : {user_instance.is_sleeping}")
        print(f"Party ID    : {user_instance.party_id}")
        print(f"Gems        : {user_instance.gems}")

        print("\n--- Core Resources ---")
        # Use calculated max values now
        print(f"HP          : {user_instance.hp:.1f} / {user_instance.max_hp:.1f}")
        print(f"MP          : {user_instance.mp:.1f} / {user_instance.max_mp:.1f}")
        print(f"EXP         : {user_instance.exp:.0f} / {user_instance.exp_to_next_level}")
        print(f"Gold        : {user_instance.gp:.2f}")

        print("\n--- Effective Stats (incl. Gear) ---")
        for stat, value in user_instance.effective_stats.items():
            # Access base/training/buff for breakdown (optional)
            base_stat = getattr(user_instance.stats, f"base_{'int_' if stat=='int' else ('str_' if stat=='str' else stat)}", 0)
            train_stat = getattr(user_instance.stats.training, f"{'int_' if stat=='int' else ('str_' if stat=='str' else stat)}", 0.0)
            buff_stat = getattr(user_instance.stats.buffs, f"{'int_' if stat=='int' else ('str_' if stat=='str' else stat)}", 0.0)
            # Gear bonus = effective - (base + train + buff + level)
            level_bonus = user_instance.stats.calculate_level_bonus()
            gear_b = value - (base_stat + buff_stat + level_bonus)
            print(f"{stat.upper():<4}: {value:>5.1f}   (Base:{base_stat} Train:{train_stat:.1f} Buff:{buff_stat:.1f} Lvl:{level_bonus:.0f} Gear:{gear_b:+.1f})")

        print("\n--- User Tags ---")
        if user_instance.tags:
            print(f"Tag Count   : {len(user_instance.tags.tags)}")
            print(f"Sample Tags : {[t.name for t in user_instance.tags.tags[:5]]}...")
        else:
            print("No tags found/loaded.")

        # 6. Save processed data (including calculated stats if needed)
        # By default, PrivateAttr (_calculated_stats) isn't dumped.
        # If you want to save them, make _calculated_stats a regular Field or modify dumping.
        log.info(f"Saving processed user data to {processed_path}...")
        # save_pydantic_model(user_instance, processed_path) # Standard dump
        # Or to include calculated stats:
        user_data_dict = user_instance.model_dump(mode="json")
        user_data_dict["calculated"] = user_instance._calculated_stats  # Manually add private attr
        save_json(user_data_dict, processed_path.name, folder=processed_path.parent)  # Save merged dict
        log.success("Processed user data (with calculated) saved.")

    except ConnectionError as e:
        log.error(f"API Connection error: {e}")
    except ValidationError as e:
        log.error(f"Pydantic Validation Error: {e}")
    except Exception as e:
        log.exception(f"An unexpected error occurred in the user demo: {e}")

    return user_instance


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(main())

# ──────────────────────────────────────────────────────────────────────────────
