# pixabit/cli/data_processor.py (LEGACY - Sync Version)

# SECTION: MODULE DOCSTRING
"""Processes raw Habitica data (Sync Version).

Transforms raw task data, user data, and game content into structured formats,
categorizes tasks, calculates derived stats (like effective CON), and computes
potential daily damage. Used by the legacy Rich CLI.
"""

# SECTION: IMPORTS
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union  # Added List/Union

import emoji_data_python
import requests  # Added for exception type

# Local Imports (Adjust path based on execution context)
try:
    from pixabit.cli.api import HabiticaAPI  # Import sync API from .cli
    from pixabit.helpers._date_helper import (
        convert_to_local_time,
        is_date_passed,
    )  # Use ..
    from pixabit.helpers._json_helper import save_json  # Use ..
    from pixabit.helpers._rich import console, print  # Use ..

    from .config import CACHE_FILE_CONTENT  # Import cache filename from .cli
except ImportError:
    # Fallback imports
    import builtins

    print = builtins.print

    class DummyConsole:
        def print(self, *args: Any, **kwargs: Any) -> None:
            builtins.print(*args)

        def log(self, *args: Any, **kwargs: Any) -> None:
            builtins.print("LOG:", *args)

        def print_exception(self, *args: Any, **kwargs: Any) -> None:
            import traceback

            traceback.print_exc()

    console = DummyConsole()

    class HabiticaAPI:
        pass  # type: ignore

    def convert_to_local_time(ts: Any) -> Any:
        return None

    def is_date_passed(ts: Any) -> bool:
        return False

    def save_json(data: Any, filepath: Any) -> bool:
        return False

    CACHE_FILE_CONTENT = "content_cache_fallback.json"
    print("Warning: Using fallback imports in cli/data_processor.py")


# SECTION: TaskProcessor Class (Legacy Sync)
# KLASS: TaskProcessor
class TaskProcessor:
    """Processes raw task data, user data, and game content (Sync Version)."""

    # MARK: Initialization

    # FUNC: __init__
    def __init__(
        self,
        api_client: HabiticaAPI,
        user_data: dict[str, Any] | None = None,
        party_data: dict[str, Any] | None = None,
        all_tags_list: list[dict[str, Any]] | None = None,
        content_data: dict[str, Any] | None = None,
    ):
        """Initializes Sync TaskProcessor. Fetches data if not provided.

        Args:
            api_client: Initialized synchronous HabiticaAPI client.
            user_data: Optional pre-fetched user data.
            party_data: Optional pre-fetched party data.
            all_tags_list: Optional pre-fetched list of all tags.
            content_data: Optional pre-fetched game content.
        """
        self.api_client = api_client
        self.console = console
        self.console.log("Initializing TaskProcessor (Sync)...", style="info")

        # Store or Fetch Required Data (Sync)
        self.user_data = (
            user_data if user_data is not None else self._fetch_user_data()
        )
        self.party_data = (
            party_data if party_data is not None else self._fetch_party_data()
        )
        # Ensure party_data is a dict even if fetch failed
        if not isinstance(self.party_data, dict):
            self.party_data = {}

        _tags_list = (
            all_tags_list
            if all_tags_list is not None
            else self._fetch_tags_list()
        )
        self.tags_lookup = self._prepare_tags_lookup(_tags_list)

        self.game_content = (
            content_data
            if content_data is not None
            else self._fetch_or_load_content()
        )
        self.gear_stats_lookup = self.game_content.get("gear", {}).get(
            "flat", {}
        )
        if not self.gear_stats_lookup:
            self.console.log(
                "Warning: Could not find gear data in game content.",
                style="warning",
            )
        self.quests_lookup = self.game_content.get(
            "quests", {}
        )  # For boss lookup

        # Initialize Derived Stats
        self.user_con: float = 0.0
        self.user_stealth: int = 0
        self.is_sleeping: bool = False
        self.is_on_boss_quest: bool = False
        self.boss_str: float = 0.0

        self._calculate_user_context()  # Calculate context from fetched data
        self.console.log("TaskProcessor (Sync) Initialized.", style="info")

    # MARK: Private Data Fetching Helpers (Sync)

    # FUNC: _fetch_user_data
    def _fetch_user_data(self) -> dict[str, Any]:
        """Fetches user data sync. Returns {} on failure."""
        # self.console.log("Fetching user data (Sync)...", style="info")
        try:
            data = self.api_client.get_user_data()  # Sync call
            return data if data else {}
        except Exception as e:
            self.console.log(
                f"Exception fetching user data: {e}", style="error"
            )
            return {}

    # FUNC: _fetch_party_data
    def _fetch_party_data(self) -> dict[str, Any]:
        """Fetches party data sync. Returns {} on failure or if not in party."""
        # self.console.log("Fetching party data (Sync)...", style="info")
        try:
            data = self.api_client.get_party_data()  # Sync call
            return data if data else {}
        except Exception as e:
            self.console.log(
                f"Exception fetching party data: {e}", style="error"
            )
            return {}

    # FUNC: _fetch_tags_list
    def _fetch_tags_list(self) -> list[dict[str, Any]]:
        """Fetches all tags sync. Returns [] on failure."""
        # self.console.log("Fetching all tags (Sync)...", style="info")
        try:
            return self.api_client.get_tags()  # Sync call
        except Exception as e:
            self.console.log(
                f"Exception fetching tags list: {e}", style="error"
            )
            return []

    # FUNC: _fetch_or_load_content
    def _fetch_or_load_content(self) -> dict[str, Any]:
        """Fetches game content from API or loads from cache (Sync)."""
        # self.console.log("Fetching/Loading game content (Sync)...", style="info")
        raw_content: dict[str, Any] | None = None
        cache_path = Path(CACHE_FILE_CONTENT)

        # Try Cache
        if cache_path.exists():
            # self.console.log(f"Attempting load from cache: '{cache_path}'...", style="subtle")
            try:
                with cache_path.open(encoding="utf-8") as f:
                    raw_content = json.load(f)
                if isinstance(raw_content, dict) and raw_content:
                    # self.console.log("Successfully loaded content from cache.", style="success")
                    pass  # Use loaded content
                else:
                    self.console.log(
                        f"Cache file '{cache_path}' invalid. Refetching.",
                        style="warning",
                    )
                    raw_content = None
            except (OSError, json.JSONDecodeError, Exception) as e:
                self.console.log(
                    f"Failed load/parse cache '{cache_path}': {e}. Refetching.",
                    style="warning",
                )
                raw_content = None

        # Fetch API if Needed
        if raw_content is None:
            # self.console.log("Fetching game content from API (Sync)...")
            try:
                raw_content = self.api_client.get_content()  # Sync call
                if isinstance(raw_content, dict) and raw_content:
                    # self.console.log("Successfully fetched content from API.", style="success")
                    # Save to Cache
                    try:
                        save_json(raw_content, cache_path)  # Sync save
                    except Exception as e_save:
                        self.console.log(
                            f"Failed to save content cache: {e_save}",
                            style="warning",
                        )
                else:
                    self.console.log(
                        "Failed to fetch valid content from API.", style="error"
                    )
                    raw_content = {}
            except Exception as e_fetch:
                self.console.log(
                    f"Exception fetching content: {e_fetch}", style="error"
                )
                raw_content = {}

        return raw_content if isinstance(raw_content, dict) else {}

    # MARK: Private Calculation & Preparation Helpers (Sync)

    # FUNC: _prepare_tags_lookup
    def _prepare_tags_lookup(
        self, tags_list: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Creates tag ID -> name lookup dict."""
        # (Identical logic to async version)
        if not tags_list:
            return {}
        lookup = {
            tag["id"]: tag.get("name", f"ID:{tag['id'][:6]}")
            for tag in tags_list
            if isinstance(tag, dict) and "id" in tag
        }
        # self.console.log(f"Prepared lookup for {len(lookup)} tags.", style="info")
        return lookup

    # FUNC: _calculate_user_context
    def _calculate_user_context(self) -> None:
        """Calculates effective CON, stealth, sleep, quest status (Sync version)."""
        # (Identical logic to async version - relies on instance data)
        # self.console.log("Calculating user context (Sync)...", style="info")
        if not self.user_data:
            self.console.log(
                "Cannot calculate context: User data missing.", style="warning"
            )
            return
        try:
            stats = self.user_data.get("stats", {})
            level = int(stats.get("lvl", 0))
            user_class = stats.get("class")
            buffs = (
                stats.get("buffs", {})
                if isinstance(stats.get("buffs"), dict)
                else {}
            )
            equipped_gear = (
                self.user_data.get("items", {})
                .get("gear", {})
                .get("equipped", {})
            )
            if not isinstance(equipped_gear, dict):
                equipped_gear = {}

            level_bonus = min(50.0, math.floor(level / 2.0))
            alloc_con = float(stats.get("con", 0.0))
            buff_con = float(buffs.get("con", 0.0))
            gear_con, class_bonus_con = 0.0, 0.0

            if self.gear_stats_lookup:
                for key in equipped_gear.values():
                    if not key:
                        continue
                    item_stats = self.gear_stats_lookup.get(key)
                    if isinstance(item_stats, dict):
                        item_base_con = float(item_stats.get("con", 0.0))
                        gear_con += item_base_con
                        if item_stats.get("klass") == user_class:
                            class_bonus_con += item_base_con * 0.5

            self.user_con = (
                level_bonus + alloc_con + gear_con + class_bonus_con + buff_con
            )
            self.user_stealth = int(buffs.get("stealth", 0))
            self.is_sleeping = self.user_data.get("preferences", {}).get(
                "sleep", False
            )

            quest_info = (
                self.party_data.get("quest", {}) if self.party_data else {}
            )
            self.is_on_boss_quest = False
            self.boss_str = 0.0
            if isinstance(quest_info, dict) and quest_info.get("active"):
                quest_key = quest_info.get("key")
                if quest_key and self.quests_lookup:
                    quest_content = self.quests_lookup.get(quest_key, {})
                    if isinstance(quest_content, dict):
                        boss_content = quest_content.get("boss")
                        if (
                            isinstance(boss_content, dict)
                            and "str" in boss_content
                        ):
                            self.is_on_boss_quest = True
                            try:
                                self.boss_str = float(boss_content["str"])
                            except (ValueError, TypeError):
                                self.boss_str = 0.0
            # self.console.log(f"Sync Context: CON={self.user_con:.1f}, BossQuest={self.is_on_boss_quest}, BossStr={self.boss_str:.1f}", style="subtle")
        except Exception as e:
            self.console.log(
                f"[error]Error calculating user/party context (Sync):[/error] {e}"
            )
            self.user_con, self.user_stealth, self.is_sleeping = 0.0, 0, False
            self.is_on_boss_quest, self.boss_str = False, 0.0

    # FUNC: _value_color
    def _value_color(self, value: float | None) -> str:
        """Determines a semantic style name based on task value."""
        # (Identical logic)
        if value is None:
            return "neutral"
        if value > 15:
            return "rosewater"
        elif value > 8:
            return "flamingo"
        elif value > 1:
            return "peach"
        elif value >= 0:
            return "text"
        elif value > -9:
            return "lavender"
        elif value > -16:
            return "rp_iris"
        else:
            return "red"

    # FUNC: _process_task_tags
    def _process_task_tags(self, task_data: dict[str, Any]) -> list[str]:
        """Retrieves tag names using lookup."""
        # (Identical logic)
        tag_ids = task_data.get("tags", [])
        if not isinstance(tag_ids, list):
            return []
        return [
            self.tags_lookup.get(tag_id, f"ID:{tag_id}") for tag_id in tag_ids
        ]

    # FUNC: _calculate_checklist_done
    def _calculate_checklist_done(
        self, checklist: list[dict[str, Any]] | None
    ) -> float:
        """Calculates proportion (0.0-1.0) of checklist items done."""
        # (Identical logic - operates on raw checklist dicts)
        if (
            not checklist
            or not isinstance(checklist, list)
            or len(checklist) == 0
        ):
            return 1.0
        try:
            completed = sum(
                1
                for item in checklist
                if isinstance(item, dict) and item.get("completed", False)
            )
            total = len(checklist)
            return completed / total if total > 0 else 1.0
        except Exception as e:
            self.console.log(
                f"Error calculating checklist progress: {e}", style="warning"
            )
            return 1.0

    # MARK: Private Task Type Processors (Sync - Operate on Raw Dicts)

    # FUNC: _process_habit
    def _process_habit(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Processes Habit-specific fields (Sync)."""
        # (Identical logic, returns dict to merge)
        processed = {}
        up, down = task_data.get("up", False), task_data.get("down", False)
        cup, cdown = task_data.get("counterUp", 0), task_data.get(
            "counterDown", 0
        )
        if up and down:
            processed["direction"], processed["counter"] = (
                "both",
                f"[#A6E3A1]+{cup}[/] / [#F38BA8]-{cdown}[/]",
            )
        elif up:
            processed["direction"], processed["counter"] = (
                "up",
                f"[#A6E3A1]+{cup}[/]",
            )
        elif down:
            processed["direction"], processed["counter"] = (
                "down",
                f"[#F38BA8]-{cdown}[/]",
            )
        else:
            processed["direction"], processed["counter"] = "none", "[dim]N/A[/]"
        processed["frequency"] = task_data.get("frequency", "daily")
        val = task_data.get("value", 0.0)
        processed["value"], processed["value_color"] = val, self._value_color(
            val
        )
        return processed

    # FUNC: _process_todo
    def _process_todo(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Processes To-Do-specific fields (Sync)."""
        # (Identical logic, returns dict to merge)
        processed = {}
        deadline = task_data.get("date")
        processed["is_due"] = bool(deadline)
        processed["date"] = deadline or ""
        if deadline:
            try:
                processed["_status"] = (
                    "red" if is_date_passed(deadline) else "due"
                )
            except Exception:
                processed["_status"] = "grey"
        else:
            processed["_status"] = "grey"
        processed["checklist"] = task_data.get("checklist", [])
        val = task_data.get("value", 0.0)
        processed["value"], processed["value_color"] = val, self._value_color(
            val
        )
        return processed

    # FUNC: _process_daily
    def _process_daily(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Processes Daily-specific fields, including damage (Sync)."""
        # (Identical damage calculation logic, returns dict to merge)
        processed = {}
        is_due, completed = task_data.get("isDue", False), task_data.get(
            "completed", False
        )
        checklist = task_data.get("checklist", [])
        next_due = task_data.get("nextDue", [])
        val = task_data.get("value", 0.0)
        status = "grey"
        dmg_user, dmg_party = 0.0, 0.0
        if is_due:
            status = "success" if completed else "due"
        processed["_status"] = status
        processed["checklist"] = checklist
        processed["date"] = (
            next_due[0] if isinstance(next_due, list) and next_due else ""
        )
        processed["is_due"] = is_due
        processed["streak"] = task_data.get("streak", 0)
        processed["value"], processed["value_color"] = val, self._value_color(
            val
        )

        if (
            is_due
            and not completed
            and not self.is_sleeping
            and self.user_stealth <= 0
        ):
            try:
                v_min, v_max = -47.27, 21.27
                c_val = max(v_min, min(val, v_max))
                delta = abs(math.pow(0.9747, float(c_val)))
                check_ratio = self._calculate_checklist_done(checklist)
                eff_delta = delta * (1.0 - check_ratio)
                con_mult = max(0.1, 1.0 - (float(self.user_con) / 250.0))
                prio = task_data.get("priority", 1.0)
                prio_map = {0.1: 0.1, 1.0: 1.0, 1.5: 1.5, 2.0: 2.0}
                prio_mult = (
                    prio_map.get(float(prio), 1.0)
                    if isinstance(prio, (int, float))
                    else 1.0
                )
                hp_mod = eff_delta * con_mult * prio_mult * 2.0
                dmg_user = round(hp_mod, 1)  # Round to 1 decimal place
                if self.is_on_boss_quest and self.boss_str > 0:
                    boss_delta = (
                        eff_delta * prio_mult if prio_mult < 1.0 else eff_delta
                    )
                    dmg_party = round(
                        boss_delta * self.boss_str, 1
                    )  # Round to 1 decimal place
            except Exception as e_dmg:
                self.console.log(
                    f"Error calculating damage for Daily {task_data.get('_id', 'N/A')}: {e_dmg}",
                    style="error",
                )

        if dmg_user > 0:
            processed["damage_to_user"] = dmg_user
        if dmg_party > 0:
            processed["damage_to_party"] = dmg_party
        return processed

    # FUNC: _process_reward
    def _process_reward(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Processes Reward-specific fields (Sync)."""
        # (Identical logic, returns dict to merge)
        return {"value": task_data.get("value", 0)}  # Cost

    # MARK: Public Processing Methods (Sync)

    # FUNC: process_single_task
    def process_single_task(
        self, task_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Processes a single raw task into standardized format dict (Sync)."""
        # (Identical logic, operates on dicts)
        if not isinstance(task_data, dict) or not task_data.get("_id"):
            return None
        task_id = task_data["_id"]
        task_type = task_data.get("type")
        challenge = task_data.get("challenge", {})
        notes = task_data.get("notes", "")
        text = task_data.get("text", "")
        if not isinstance(challenge, dict):
            challenge = {}

        processed = {
            "id": task_id,
            "_type": task_type,
            "text": emoji_data_python.replace_colons(text or ""),
            "note": emoji_data_python.replace_colons(notes or ""),
            "priority": task_data.get("priority", 1.0),
            "attribute": task_data.get("attribute", "str"),
            "tags": task_data.get("tags", []),  # Keep raw IDs
            "tag_names": self._process_task_tags(task_data),  # Add names
            "created": task_data.get("createdAt", ""),
            "challenge_id": challenge.get(
                "id", ""
            ),  # Get ID from challenge dict
            "challenge_name": emoji_data_python.replace_colons(
                challenge.get("shortName", "")
            ),
        }
        # Add challenge broken status directly
        processed["challenge_broken"] = challenge.get("broken")

        type_processor = getattr(self, f"_process_{task_type}", None)
        if callable(type_processor):
            processed.update(type_processor(task_data))
        else:  # Handle unknown types or add base value processing
            val = task_data.get("value", 0.0)
            processed.update(
                {"value": val, "value_color": self._value_color(val)}
            )
            if task_type:
                self.console.log(
                    f"Warning: Unknown task type '{task_type}' for task {task_id}",
                    style="warning",
                )

        return processed

    # FUNC: process_and_categorize_all
    def process_and_categorize_all(self) -> dict[str, Any]:
        """Fetches all tasks sync, processes, and categorizes them. Returns dicts."""
        # self.console.print("Fetching all tasks (Sync)...", style="info")
        all_tasks_raw: list[dict[str, Any]] = []
        try:
            all_tasks_raw = self.api_client.get_tasks()  # Sync call
            if not isinstance(all_tasks_raw, list):
                raise TypeError("Expected list")
        except Exception as e:
            self.console.print(
                f"Fatal Error fetching tasks: {e}", style="error"
            )
            return {
                "data": {},
                "cats": {
                    "tasks": {},
                    "tags": [],
                    "broken": [],
                    "challenge": [],
                },
            }

        # self.console.print(f"Processing {len(all_tasks_raw)} raw tasks (Sync)...", style="info")
        tasks_dict: dict[str, dict[str, Any]] = {}  # Stores processed dicts
        cats_dict: dict[str, Any] = {
            "tasks": {
                "habits": [],
                "todos": {
                    "due": [],
                    "grey": [],
                    "red": [],
                    "done": [],
                },  # Add done
                "dailys": {"success": [], "due": [], "grey": []},
                "rewards": [],
            },
            "tags": set(),
            "broken": [],
            "challenge": set(),
        }
        processed_count, skipped_count = 0, 0
        for task_data in all_tasks_raw:
            processed = self.process_single_task(
                task_data
            )  # Process dict -> dict
            if not processed:
                skipped_count += 1
                continue
            task_id = processed["id"]
            tasks_dict[task_id] = processed
            processed_count += 1
            cats_dict["tags"].update(processed.get("tags", []))
            if processed.get("challenge_broken"):
                cats_dict["broken"].append(task_id)
            if processed.get("challenge_id"):
                cats_dict["challenge"].add(processed["challenge_id"])

            t_type, t_status = processed.get("_type"), processed.get("_status")
            if t_type == "habit":
                cats_dict["tasks"]["habits"].append(task_id)
            elif t_type == "reward":
                cats_dict["tasks"]["rewards"].append(task_id)
            elif t_type == "todo" and t_status in cats_dict["tasks"]["todos"]:
                cats_dict["tasks"]["todos"][t_status].append(task_id)
            elif t_type == "daily" and t_status in cats_dict["tasks"]["dailys"]:
                cats_dict["tasks"]["dailys"][t_status].append(task_id)

        cats_dict["tags"] = sorted(list(cats_dict["tags"]))
        cats_dict["challenge"] = sorted(list(cats_dict["challenge"]))
        # self.console.print(f"Task processing/categorization complete (Sync). Processed: {processed_count}, Skipped: {skipped_count}", style="success")
        return {"data": tasks_dict, "cats": cats_dict}


# SECTION: User Stats Function (Sync)
# FUNC: get_user_stats
def get_user_stats(
    api_client: HabiticaAPI,  # Requires sync API client
    cats_dict: dict[str, Any],
    processed_tasks_dict: dict[str, dict[str, Any]],  # Expects processed dicts
    user_data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:  # Return Optional
    """Generates user statistics dict (Sync version).

    Args:
        api_client: Initialized synchronous HabiticaAPI client.
        cats_dict: The 'cats' dictionary from TaskProcessor.
        processed_tasks_dict: The 'data' dictionary (processed task dicts).
        user_data: Optional pre-fetched raw user data dictionary.

    Returns:
        A dictionary containing combined user/task statistics, or None on failure.
    """
    # (Identical logic to async version, but uses sync API client if needed)
    # console.log("Calculating user stats (Sync)...", style="info")
    if user_data is None:
        # console.log("User data not provided, fetching (Sync)...", style="info")
        try:
            user_data = api_client.get_user_data()
        except Exception as e:
            console.print(f"Failed fetch user data: {e}", style="error")
            return None
    if not isinstance(user_data, dict) or not user_data:
        console.print("Valid user data required.", style="error")
        return None
    if not isinstance(cats_dict, dict):
        console.print("Valid categories data required.", style="error")
        return None
    if not isinstance(processed_tasks_dict, dict):
        console.print("Valid processed tasks required.", style="error")
        return None

    try:
        stats = user_data.get("stats", {})
        party = user_data.get("party", {})
        prefs = user_data.get("preferences", {})
        auth = user_data.get("auth", {})
        ts = auth.get("timestamps", {})
        local_auth = auth.get("local", {})
        balance = user_data.get("balance", 0.0)
        gems = int(balance * 4) if balance > 0 else 0
        u_class_raw = stats.get("class", "warrior")
        u_class = "mage" if u_class_raw == "wizard" else u_class_raw
        # last_login_utc = ts.get("loggedin"); last_login_local = "N/A"
        # if last_login_utc and (local_dt := convert_to_local_time(last_login_utc)):
        #      last_login_local = local_dt.isoformat(sep=" ", timespec="minutes")
        # elif last_login_utc: last_login_local = f"Error ({last_login_utc})"
        quest = party.get("quest", {}) if isinstance(party, dict) else {}

        task_counts: dict[str, Any] = {}
        task_cats_data = cats_dict.get("tasks", {})
        if isinstance(task_cats_data, dict):
            for cat, data in task_cats_data.items():
                if cat not in ["habits", "dailys", "todos", "rewards"]:
                    continue
                if isinstance(data, dict):
                    status_counts = {
                        k: len(v)
                        for k, v in data.items()
                        if isinstance(v, list)
                    }
                    status_counts["_total"] = sum(status_counts.values())
                    task_counts[cat] = status_counts
                elif isinstance(data, list):
                    task_counts[cat] = len(data)

        dmg_user, dmg_party = 0.0, 0.0
        due_dailies = (
            cats_dict.get("tasks", {}).get("dailys", {}).get("due", [])
        )
        if isinstance(due_dailies, list):
            for task_id in due_dailies:
                task = processed_tasks_dict.get(task_id)
                if isinstance(task, dict):
                    dmg_user += float(task.get("damage_to_user", 0.0))
                    dmg_party += float(task.get("damage_to_party", 0.0))

        output = {
            "username": local_auth.get("username", "N/A"),
            "class": u_class,
            "level": int(stats.get("lvl", 0)),
            "hp": float(stats.get("hp", 0.0)),
            "maxHealth": int(stats.get("maxHealth", 50)),
            "mp": float(stats.get("mp", 0.0)),
            "maxMP": int(stats.get("maxMP", 0)),
            "exp": float(stats.get("exp", 0.0)),
            "toNextLevel": int(stats.get("toNextLevel", 0)),
            "gp": float(stats.get("gp", 0.0)),
            "gems": gems,
            "stats": {
                "str": int(stats.get("str", 0)),
                "int": int(stats.get("int", 0)),
                "con": int(stats.get("con", 0)),
                "per": int(stats.get("per", 0)),
            },
            "sleeping": bool(prefs.get("sleep", False)),
            "day_start": int(prefs.get("dayStart", 0)),
            # "last_login_local": last_login_local,
            "quest_active": bool(quest.get("active", False)),
            "quest_key": quest.get("key"),
            "task_counts": task_counts,
            "broken_challenge_tasks": len(cats_dict.get("broken", [])),
            "joined_challenges_count": len(cats_dict.get("challenge", [])),
            "tags_in_use_count": len(cats_dict.get("tags", [])),
            "potential_daily_damage_user": round(dmg_user, 2),
            "potential_daily_damage_party": round(dmg_party, 2),
        }
        # console.log("User stats calculation complete (Sync).", style="success")
        return output
    except Exception as e_stat:
        console.print(f"Error calculating user stats: {e_stat}", style="error")
        # console.print_exception(show_locals=False)
        return None  # Return None on failure
