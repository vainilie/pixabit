# --- Imports ---
from __future__ import annotations  # Enable postponed evaluation of annotations

import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# --- Constants and Mock Data ---
ALL_GEAR_CONTENT: dict[str, dict[str, Any]] = {
    "weapon_warrior_1": {"str": 3, "klass": "warrior"},
    "armor_warrior_1": {"con": 2, "klass": "warrior"},
    "head_warrior_1": {"int": 1, "klass": "warrior"},
    "shield_warrior_1": {"per": 2, "klass": "warrior"},
    "weapon_base_0": {"str": 0},
}


# --- User Subcomponent Models ---


class UserProfile(BaseModel):
    """Represents user profile information like display name and blurb."""

    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = Field(
        None, description="User's display name (emoji shortcodes replaced)."
    )
    blurb: Optional[str] = Field(
        None, description="User's profile description (emoji shortcodes replaced)."
    )

    @field_validator("name", "blurb", mode="before")
    @classmethod
    def parse_emoji_shortcodes(cls, value: Optional[str]) -> Optional[str]:
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value)
        return None


class UserAuth(BaseModel):
    """Represents user authentication details, extracting username."""

    model_config = ConfigDict(extra="ignore")
    username: Optional[str] = Field(None, description="Username from local auth.")
    created_at: Optional[datetime] = Field(
        None, alias="created", description="Timestamp when user account was created."
    )
    updated_at: Optional[datetime] = Field(
        None, alias="updated", description="Timestamp when user account was last updated."
    )
    logged_in_at: Optional[datetime] = Field(
        None, alias="loggedin", description="Timestamp when user last logged in."
    )

    @model_validator(mode="before")
    @classmethod
    def extract_nested_fields(cls, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        values = data.copy()
        local_auth = data.get("local")
        values["username"] = local_auth.get("username") if isinstance(local_auth, dict) else None
        timestamps = data.get("timestamps", {})
        if isinstance(timestamps, dict):
            values["created"] = timestamps.get("created")
            values["updated"] = timestamps.get("updated")
            values["loggedin"] = timestamps.get("loggedin")
        else:
            values["created"] = values["updated"] = values["loggedin"] = None
        return values

    @field_validator("created_at", "updated_at", "logged_in_at", mode="before")
    @classmethod
    def parse_datetime_utc(cls, value: Any) -> Optional[datetime]:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return None
        elif isinstance(value, datetime):
            return value
        return None


class UserPreferences(BaseModel):
    """User-specific preferences and settings."""

    model_config = ConfigDict(extra="ignore")
    sleep: bool = Field(False, description="Whether user is resting in the Inn.")
    day_start: int = Field(
        default=0, alias="dayStart", description="User's preferred day start hour (0–23)."
    )
    timezone_offset: Optional[int] = Field(
        None,
        alias="timezoneOffset",
        description="User's current timezone offset from UTC in minutes.",
    )
    timezone_offset_at_last_cron: Optional[int] = Field(
        None,
        alias="timezoneOffsetAtLastCron",
        description="User's timezone offset at the time of the last cron.",
    )

    @field_validator("day_start", mode="before")
    @classmethod
    def parse_day_start(cls, value: Any) -> int:
        try:
            ds = int(value)
            return max(0, min(23, ds))
        except (ValueError, TypeError):
            return 0


class Buffs(BaseModel):
    """Temporary stat increases/decreases from spells, food, etc."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)  # Added populate_by_name

    con: int = 0
    # *** Renamed fields clashing with built-in types, added alias ***
    int_: int = Field(default=0, alias="int")
    per: int = 0
    str_: int = Field(default=0, alias="str")
    stealth: int = 0

    @model_validator(mode="before")
    @classmethod
    def extract_and_convert(cls, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        buffs_data = data.get("buffs", data) if isinstance(data.get("buffs"), dict) else data
        if not isinstance(buffs_data, dict):
            return {}

        parsed = {}
        # Use original key names ('int', 'str') here for parsing input data
        parsed["con"] = int(buffs_data.get("con", 0))
        parsed["int"] = int(buffs_data.get("int", 0))  # Pydantic uses alias to map this to int_
        parsed["per"] = int(buffs_data.get("per", 0))
        parsed["str"] = int(buffs_data.get("str", 0))  # Pydantic uses alias to map this to str_
        parsed["stealth"] = int(buffs_data.get("stealth", 0))
        # Keep allowing other buff keys
        parsed.update({k: v for k, v in buffs_data.items() if k not in parsed})
        return parsed


class Training(BaseModel):
    """Permanent stat increases from leveling/resets."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)  # Added populate_by_name

    con: float = 0.0
    # *** Renamed fields clashing with built-in types, added alias ***
    int_: float = Field(default=0.0, alias="int")
    per: float = 0.0
    str_: float = Field(default=0.0, alias="str")

    @model_validator(mode="before")
    @classmethod
    def extract_and_convert(cls, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        training_data = (
            data.get("training", data) if isinstance(data.get("training"), dict) else data
        )
        if not isinstance(training_data, dict):
            return {}

        parsed = {}
        # Use original key names ('int', 'str') here for parsing input data
        parsed["con"] = float(training_data.get("con", 0.0))
        parsed["int"] = float(
            training_data.get("int", 0.0)
        )  # Pydantic uses alias to map this to int_
        parsed["per"] = float(training_data.get("per", 0.0))
        parsed["str"] = float(
            training_data.get("str", 0.0)
        )  # Pydantic uses alias to map this to str_
        return parsed


class EquippedGear(BaseModel):
    """Represents the gear currently equipped by the user."""

    model_config = ConfigDict(extra="allow")
    weapon: Optional[str] = None
    armor: Optional[str] = None
    head: Optional[str] = None
    shield: Optional[str] = None

    def get_equipped_items(self) -> list[str]:
        return [
            item_key
            for item_key in [self.weapon, self.armor, self.head, self.shield]
            if item_key is not None
        ]

    def calculate_total_bonus(
        self, user_class: Optional[str], gear_content: dict[str, dict[str, Any]]
    ) -> dict[str, float]:
        """Calculates the total stat bonus (float) from equipped gear, including class bonus."""
        total_bonus: dict[str, float] = {"str": 0.0, "con": 0.0, "int": 0.0, "per": 0.0}
        stats_to_check = list(total_bonus.keys())  # Checks 'str', 'con', 'int', 'per'

        for gear_key in self.get_equipped_items():
            item_data = gear_content.get(gear_key)
            if isinstance(item_data, dict):
                item_class = item_data.get("klass")
                class_match_bonus_multiplier = (
                    1.5 if item_class and item_class == user_class else 1.0
                )
                for stat in stats_to_check:
                    # Use original stat names 'int', 'str' when looking up in gear_content
                    stat_value = float(item_data.get(stat, 0.0))
                    total_bonus[stat] += stat_value * class_match_bonus_multiplier
        return total_bonus


class UserStats(BaseModel):
    """Represents the user's core numerical stats and attributes."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)  # Added populate_by_name

    hp: int = Field(default=50, description="Current health points.")
    mp: int = Field(default=0, description="Current mana points.")
    exp: int = Field(default=0, description="Current experience points.")
    gp: int = Field(default=0, description="Current gold points.")
    lvl: int = Field(default=1, description="User's current level.")
    klass: Optional[str] = Field(default=None, alias="class", description="User's selected class.")

    # *** Renamed base stat fields clashing with built-in types, added alias ***
    base_con: int = Field(default=0, alias="con", description="Base Constitution attribute.")
    base_int_: int = Field(default=0, alias="int", description="Base Intelligence attribute.")
    base_per: int = Field(default=0, alias="per", description="Base Perception attribute.")
    base_str_: int = Field(default=0, alias="str", description="Base Strength attribute.")

    max_hp_base: int = Field(default=50, alias="maxHealth", description="Base maximum health.")
    max_mp_base: int = Field(default=10, alias="maxMP", description="Base maximum mana.")
    exp_to_next_level: int = Field(
        default=0, alias="toNextLevel", description="Experience points needed for the next level."
    )

    buffs: Buffs = Field(default_factory=Buffs)
    training: Training = Field(default_factory=Training)

    @model_validator(mode="before")
    @classmethod
    def parse_stats_data(cls, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        values = data.copy()
        values["buffs"] = Buffs.model_validate(data.get("buffs", data)).model_dump()
        values["training"] = Training.model_validate(data.get("training", data)).model_dump()

        # Use original key names ('int', 'str') for parsing input data
        values["con"] = int(data.get("con", 0))
        values["int"] = int(data.get("int", 0))  # Pydantic uses alias to map this to base_int_
        values["per"] = int(data.get("per", 0))
        values["str"] = int(data.get("str", 0))  # Pydantic uses alias to map this to base_str_
        values["hp"] = int(data.get("hp", 50))
        values["mp"] = int(data.get("mp", 0))
        values["exp"] = int(data.get("exp", 0))
        values["gp"] = int(data.get("gp", 0))
        values["lvl"] = int(data.get("lvl", 1))
        values["maxHealth"] = int(data.get("maxHealth", 50))
        values["maxMP"] = int(data.get("maxMP", 10))
        values["toNextLevel"] = int(data.get("toNextLevel", 0))
        return values

    def stats_before_gear(self) -> Dict[str, float]:
        """Returns stats including base, buffs, training + level_bonus. Result is float."""
        level_bonus = min(50.0, math.floor(self.lvl / 2.0))  # float
        # *** Use renamed attribute names internally ***
        return {
            "con": float(self.base_con + self.buffs.con) + self.training.con + level_bonus,
            "int": float(self.base_int_ + self.buffs.int_)
            + self.training.int_
            + level_bonus,  # Use int_
            "per": float(self.base_per + self.buffs.per) + self.training.per + level_bonus,
            "str": float(self.base_str_ + self.buffs.str_)
            + self.training.str_
            + level_bonus,  # Use str_
        }

    @property
    def calculated_max_hp(self) -> float:
        effective_con_before_gear = self.stats_before_gear()["con"]
        return float(self.max_hp_base + math.floor(effective_con_before_gear * 2.0))

    @property
    def calculated_max_mp(self) -> float:
        effective_int_before_gear = self.stats_before_gear()[
            "int"
        ]  # Use 'int' key from stats_before_gear dict
        return float(self.max_mp_base + math.floor(effective_int_before_gear * 2.0))


# --- Other User Subcomponents (UserItems, etc.) ---
# (Definitions remain the same as they didn't use clashing names like 'int' or 'str' as fields)
class UserItems(BaseModel):
    """Holds user's inventory: gear, items, pets, mounts etc."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)  # Added populate_by_name
    gear_equipped: EquippedGear = Field(default_factory=EquippedGear, alias="equipped")
    gear_costume: EquippedGear = Field(default_factory=EquippedGear, alias="costume")
    gear_owned: Dict[str, bool] = Field(default_factory=dict, alias="owned")
    eggs: Dict[str, int] = Field(default_factory=dict)
    food: Dict[str, int] = Field(default_factory=dict)
    hatching_potions: Dict[str, int] = Field(default_factory=dict, alias="hatchingPotions")
    pets: Dict[str, int] = Field(default_factory=dict, description="{Pet-SpeciesKey: feed_count}")
    mounts: Dict[str, bool] = Field(default_factory=dict, description="{Mount-SpeciesKey: True}")
    special: Dict[str, Any] = Field(
        default_factory=dict, description="Special items like Orb, Gear Sets"
    )
    quests: Dict[str, int] = Field(
        default_factory=dict, description="Quest scrolls owned {quest_key: count}"
    )

    @model_validator(mode="before")
    @classmethod
    def structure_gear_data(cls, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        values = data.copy()
        gear_data = data.get("gear", {})
        if isinstance(gear_data, dict):
            values["equipped"] = gear_data.get("equipped", {})
            values["costume"] = gear_data.get("costume", {})
            values["owned"] = gear_data.get("owned", {})
        else:
            values["equipped"], values["costume"], values["owned"] = {}, {}, {}
        # Use original key names when parsing the input data dict
        values["eggs"] = data.get("eggs", {})
        values["food"] = data.get("food", {})
        values["hatchingPotions"] = data.get("hatchingPotions", {})
        values["pets"] = data.get("pets", {})
        values["mounts"] = data.get("mounts", {})
        values["special"] = data.get("special", {})
        values["quests"] = data.get("quests", {})
        return values


class UserAchievements(BaseModel):
    """Holds user's achievements progress."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)  # Added populate_by_name
    challenges: List[str] = Field(
        default_factory=list, description="List of challenge IDs completed."
    )
    quests: Dict[str, int] = Field(
        default_factory=dict, description="{quest_key: completion_count}."
    )
    perfect_days: int = Field(default=0, alias="perfect", description="Count of perfect days.")
    streak: int = Field(default=0, description="Max consecutive perfect days streak.")
    login_incentives: int = Field(
        default=0, alias="loginIncentives", description="Count of login incentives claimed."
    )
    other_achievements: Dict[str, Any] = Field(
        default_factory=dict, description="Other earned achievements."
    )

    @model_validator(mode="before")
    @classmethod
    def structure_achievements(cls, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        values = {}
        known_keys = {
            "challenges",
            "quests",
            "perfect",
            "streak",
            "loginIncentives",
            "ultimateGearSets",
        }
        # Use original key names when parsing input data dict
        values["challenges"] = data.get("challenges", [])
        values["quests"] = data.get("quests", {})
        values["perfect"] = int(data.get("perfect", 0))
        values["streak"] = int(data.get("streak", 0))
        values["loginIncentives"] = int(data.get("loginIncentives", 0))
        values["other_achievements"] = {k: v for k, v in data.items() if k not in known_keys}
        return values


class UserPartyInfo(BaseModel):
    """Holds information about the user's party membership."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)  # Added populate_by_name
    party_id: Optional[str] = Field(
        None, alias="_id", description="The unique ID of the party the user is in."
    )


class UserInboxInfo(BaseModel):
    """Holds information about the user's inbox status."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)  # Added populate_by_name
    new_messages: int = Field(
        0, alias="newMessages", description="Count of unread private messages."
    )
    has_gift: bool = Field(False, alias="hasNew", description="Flag indicating a new gift message.")
    opt_out: bool = Field(
        False, alias="optOut", description="Whether the user has opted out of receiving new PMs."
    )
    blocks: List[str] = Field(
        default_factory=list, description="List of user IDs blocked by this user."
    )


# --- Main User Model ---


class User(BaseModel):
    """Represents the complete Habitica User object, aggregating data from the '/user' endpoint."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    id: str = Field(..., alias="_id")
    balance: float = Field(default=0.0)
    needs_cron: bool = Field(default=False, alias="needsCron")
    last_cron: Optional[datetime] = Field(default=None, alias="lastCron")
    login_incentives: int = Field(default=0, alias="loginIncentives")

    profile: UserProfile = Field(default_factory=UserProfile)
    auth: UserAuth = Field(default_factory=UserAuth)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    items: UserItems = Field(default_factory=UserItems)
    achievements: UserAchievements = Field(default_factory=UserAchievements)
    party: UserPartyInfo = Field(default_factory=UserPartyInfo)
    inbox: UserInboxInfo = Field(default_factory=UserInboxInfo)
    stats: UserStats = Field(default_factory=UserStats)

    @field_validator("last_cron", mode="before")
    @classmethod
    def parse_last_cron(cls, value: Any) -> Optional[datetime]:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return None
        elif isinstance(value, datetime):
            return value
        return None

    @model_validator(mode="before")
    @classmethod
    def check_and_assign_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "_id" not in data and "id" in data:
                data["_id"] = data["id"]
            elif "_id" not in data and "id" not in data:
                raise ValueError("User data must contain 'id' or '_id'")
        return data

    # --- Convenience Properties ---
    # Access internal fields using the renamed attributes (e.g., self.stats.base_int_)
    @property
    def username(self) -> Optional[str]:
        return self.auth.username

    @property
    def display_name(self) -> Optional[str]:
        return self.profile.name

    @property
    def level(self) -> int:
        return self.stats.lvl

    @property
    def klass(self) -> Optional[str]:
        return self.stats.klass

    @property
    def hp(self) -> int:
        return self.stats.hp

    @property
    def mp(self) -> int:
        return self.stats.mp

    @property
    def gp(self) -> int:
        return self.stats.gp

    @property
    def exp(self) -> int:
        return self.stats.exp

    @property
    def party_id(self) -> Optional[str]:
        return self.party.party_id

    @property
    def is_sleeping(self) -> bool:
        return self.preferences.sleep

    @property
    def gems(self) -> int:
        return int(self.balance * 4) if self.balance > 0 else 0

    @property
    def exp_to_next_level(self) -> int:
        return self.stats.exp_to_next_level

    # --- Methods for Calculated Values ---
    # These methods should remain largely the same as they operate on the results
    # from UserStats methods and EquippedGear methods, which return dicts keyed by 'int', 'str'.
    def calculate_effective_stats(
        self, gear_content: Optional[dict[str, dict[str, Any]]] = None
    ) -> dict[str, float]:
        """Calculates total effective stats (float) including base, buffs, training, level bonus, and gear."""
        if gear_content is None:
            gear_content = ALL_GEAR_CONTENT
        stats_before_gear = self.stats.stats_before_gear()  # dict keyed by 'int', 'str' etc.
        gear_bonus = self.items.gear_equipped.calculate_total_bonus(
            self.klass, gear_content
        )  # dict keyed by 'int', 'str' etc.
        effective_stats = {
            stat: stats_before_gear.get(stat, 0.0) + gear_bonus.get(stat, 0.0)
            for stat in ["str", "con", "int", "per"]  # Use standard stat names for keys
        }
        return effective_stats

    @property
    def max_hp(self) -> float:
        effective_con = self.calculate_effective_stats().get("con", 0.0)
        return float(self.stats.max_hp_base + math.floor(effective_con * 2.0))

    @property
    def max_mp(self) -> float:
        effective_int = self.calculate_effective_stats().get("int", 0.0)  # Use 'int' key
        return float(self.stats.max_mp_base + math.floor(effective_int * 2.0))


# --- Example Usage ---
# (The example usage block remains the same, it interacts via properties and methods
#  which handle the internal renaming)
if __name__ == "__main__":
    USER_DATA_JSON_PATH = "user.json"  # <-- Make sure this file exists
    raw_user_data = None
    user: Optional[User] = None

    try:
        print(f"Loading user data from: {USER_DATA_JSON_PATH}...")
        with open(USER_DATA_JSON_PATH, encoding="utf-8") as file_object:
            raw_user_data = json.load(file_object)
        print("...JSON data loaded successfully.")

        print("Validating loaded data against User model...")
        user = User.model_validate(raw_user_data)
        print("...User data validated successfully.")

        # Print statements access data via properties or methods,
        # so they don't need changing.
        print("\n--- Accessing data using the model ---")
        print(f"User ID: {user.id}")
        print(f"Username: {user.username}")
        # ... rest of prints ...
        print("\n--- Buffs ---")
        # Accessing the Buffs object will show the renamed fields internally if printed directly
        print(user.stats.buffs)  # Output might show int_=..., str_=...

        print("\n--- Training ---")
        print(user.stats.training)  # Output might show int_=..., str_=...

        print("\n--- Effective Stats (including gear) ---")
        effective_stats = user.calculate_effective_stats(ALL_GEAR_CONTENT)
        print(effective_stats)  # Output keys will be 'int', 'str'

        # ... rest of prints ...

    # (Keep error handling blocks the same)
    except FileNotFoundError:
        print("\n--- Error ---")
        print(f"FATAL: User data file not found at '{USER_DATA_JSON_PATH}'")
    except json.JSONDecodeError as e:
        print("\n--- Error ---")
        print(
            f"FATAL: Could not decode JSON from '{USER_DATA_JSON_PATH}'. Invalid JSON format. Details: {e}"
        )
    except ValidationError as e:
        print("\n--- Validation Error ---")
        print(f"FATAL: Loaded data failed validation against the User model.\n{e}")
    except Exception as e:
        print("\n--- Error ---")
        print(f"An unexpected error occurred: {e}")
