import math
from typing import Any, Optional, dict


class User:
    def __init__(self, user_data: dict[str, Any]):
        self.username: Optional[str] = user_data.get("auth", {}).get("local", {}).get("username")
        self.name: Optional[str] = user_data.get("profile", {}).get("name")
        self.user_id: Optional[str] = user_data.get("id")
        self.gear: Optional[Any] = user_data.get("items", {}).get("gear", {}).get("equipped")
        self.klass: Optional[str] = user_data.get("stats", {}).get("class")
        self.level: Optional[int] = user_data.get("stats", {}).get("lvl")


class UserStats:
    def __init__(self, user_data: dict[str, Any]):
        self.gems: int = user_data.get("balance", 0) * 4  # Default to 0
        self.health: Optional[int] = user_data.get("stats", {}).get("hp")
        self.gold: Optional[int] = user_data.get("stats", {}).get("gp")
        self.exp: Optional[int] = user_data.get("stats", {}).get("exp")
        self.mana: Optional[int] = user_data.get("stats", {}).get("mp")
        self.max_health: Optional[int] = user_data.get("stats", {}).get("maxHealth")
        self.max_exp: Optional[int] = user_data.get("stats", {}).get("toNextLevel")
        self.max_mana: Optional[int] = user_data.get("stats", {}).get("maxMP")
        self.strength: Optional[int] = user_data.get("stats", {}).get("str")
        self.intelligence: Optional[int] = user_data.get("stats", {}).get("int")
        self.constitution: Optional[int] = user_data.get("stats", {}).get("con")
        self.perception: Optional[int] = user_data.get("stats", {}).get("per")
        self.buff_con: Optional[int] = user_data.get("stats", {}).get("buffs", {}).get("con")
        self.stealth: Optional[int] = user_data.get("stats", {}).get("buffs", {}).get("stealth")
        self.effective_constitution: Optional[int] = None  # To store the calculated value


class UserParty:
    def __init__(self, user_data: dict[str, Any], all_boss: dict[str, Any]):  # Pass all_boss in
        self.party_id: Optional[str] = user_data.get("party", {}).get("id")
        self.quest: Optional[str] = user_data.get("party", {}).get("quest", {}).get("key")
        self.progress_up: Optional[int] = (
            user_data.get("party", {}).get("quest", {}).get("progress", {}).get("up")
        )
        self.progress_down: Optional[int] = (
            user_data.get("party", {}).get("quest", {}).get("progress", {}).get("down")
        )
        self.collected_items: Optional[int] = (
            user_data.get("party", {}).get("quest", {}).get("progress", {}).get("collectedItems")
        )
        if self.quest:  # Only access all_boss if quest exists
            boss_info = all_boss.get(self.quest, {})  # Safe access to all_boss
            self.boss_value: Optional[int] = boss_info.get("value")
            self.boss_str: Optional[int] = boss_info.get("boss", {}).get("str")
            self.boss_hp: Optional[int] = boss_info.get("boss", {}).get("hp")
            self.boss_def: Optional[int] = boss_info.get("boss", {}).get("def")
        else:
            self.boss_value = None
            self.boss_str = None
            self.boss_hp = None
            self.boss_def = None


class UserCron:
    def __init__(self, user_data: dict[str, Any]):
        self.updated: Optional[str] = (
            user_data.get("auth", {}).get("timestamps", {}).get("updated")
        )
        self.logged_in: Optional[str] = (
            user_data.get("auth", {}).get("timestamps", {}).get("loggedIn")
        )
        self.last_cron: Optional[str] = user_data.get("lastCron")
        self.cron: Optional[str] = user_data.get("cron")
        self.daystart: Optional[str] = user_data.get("preferences", {}).get("dayStart")
        self.sleep: Optional[str] = user_data.get("preferences", {}).get("sleep")


class UserData:
    def __init__(
        self, user_data: dict[str, Any], all_gear: dict[str, Any], all_boss: dict[str, Any]
    ):  # Pass all_gear and all_boss
        self.user = User(user_data)
        self.stats = UserStats(user_data)
        self.party = UserParty(user_data, all_boss)  # Pass all_boss
        self.cron = UserCron(user_data)
        self.calculate_effective_constitution(all_gear)  # Call the method here

    def calculate_effective_constitution(
        self, all_gear: dict[str, Any]
    ) -> None:  # all_gear as argument
        """Calculates the user's effective constitution based on gear and buffs."""
        gear_con = 0
        gear_bonus = 0
        if self.user.gear and all_gear:  # Check if gear and all_gear exist
            for key in self.user.gear:
                if not key:
                    continue
                item = all_gear.get("flat", {}).get(key)
                if item:  # Check if item exists
                    item_con = item.get("con", 0)  # Default to 0 if con is missing
                    if item.get("Klass") == self.user.klass:
                        bonus_con = item_con * 0.5
                    else:
                        bonus_con = 0
                    gear_con += item_con
                    gear_bonus += bonus_con
        level_bonus = (
            min(50, math.floor(self.user.level / 2)) if self.user.level else 0
        )  # Safe level access
        self.stats.effective_constitution = (
            level_bonus
            + (self.stats.constitution or 0)
            + gear_con
            + gear_bonus
            + (self.stats.buff_con or 0)
        )  # Safe attribute access


# Example Usage (assuming 'raw_user_data' is your API response, all_gear, and all_boss are available)
raw_user_data = {
    "auth": {
        "local": {"username": "testuser"},
        "timestamps": {"updated": "...", "loggedIn": "..."},
    },
    "profile": {"name": "Test User"},
    "id": "123",
    "items": {"gear": {"equipped": "sword"}},
    "stats": {
        "class": "warrior",
        "lvl": 10,
        "hp": 50,
        "gp": 100,
        "exp": 200,
        "mp": 30,
        "maxHealth": 100,
        "toNextLevel": 300,
        "maxMP": 50,
        "str": 5,
        "int": 3,
        "con": 4,
        "per": 2,
        "buffs": {"con": 2, "stealth": 1},
    },
    "balance": 20,
    "cron": "...",
    "lastCron": "...",
    "preferences": {"dayStart": "...", "sleep": "..."},
    "party": {
        "id": "party1",
        "quest": {"key": "slayDragon", "progress": {"up": 10, "down": 5, "collectedItems": 3}},
    },
}

all_gear_data = {"flat": {"sword": {"con": 3, "Klass": "warrior"}}}
all_boss_data = {"slayDragon": {"value": 100, "boss": {"str": 10, "hp": 200, "def": 5}}}

user_data = UserData(raw_user_data, all_gear_data, all_boss_data)

print(f"Username: {user_data.user.username}")
print(user_data.stats.constitution)
print(f"Effective Constitution: {user_data.stats.effective_constitution}")
print(user_data.user.username)
print(user_data.stats.health)
print(user_data.party.quest)
print(user_data.cron.updated)

print(f"Username: {user_data.user.username}")
print(f"Effective Constitution: {user_data.stats.effective_constitution}")
