# pixabit/data_processor.py
# MARK: - MODULE DOCSTRING
"""Processes raw Habitica data (Tasks, User, Party, Content) into structured formats,
categorizes tasks, calculates derived stats (like effective CON), and computes
potential daily damage. Includes functions to get combined user statistics.
"""

# MARK: - IMPORTS
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import emoji_data_python

# Local Imports
from .api import HabiticaAPI
from .utils.dates import convert_to_local_time, is_date_passed
from .utils.display import console  # Use themed display
from .utils.save_json import save_json  # Keep for saving processed data if needed

# MARK: - CONSTANTS
CACHE_FILE_CONTENT = "content_cache.json"  # Cache file for game content


# MARK: - TaskProcessor Class
class TaskProcessor:
    """Processes raw task data, user data, and game content from Habitica.

    Fetches data if not provided, calculates derived stats, processes tasks,
    calculates potential damage, and categorizes tasks.
    """

    # MARK: - Initialization
    # & - def __init__(...)
    def __init__(
        self,
        api_client: HabiticaAPI,
        user_data: Optional[Dict[str, Any]] = None,
        party_data: Optional[Dict[str, Any]] = None,
        all_tags_list: Optional[List[Dict[str, Any]]] = None,
        content_data: Optional[Dict[str, Any]] = None,
    ):
        """Initializes TaskProcessor. Fetches required data only if not provided.

        Args:
            api_client: Authenticated HabiticaAPI client.
            user_data: Optional pre-fetched user data.
            party_data: Optional pre-fetched party data.
            all_tags_list: Optional pre-fetched list of all tags.
            content_data: Optional pre-fetched game content.
        """
        self.api_client = api_client
        self.console = console
        self.console.log("Initializing TaskProcessor...", style="info")

        # Store or Fetch Required Data (Reduces API calls if data passed in)
        self.user_data = user_data if user_data is not None else self._fetch_user_data()
        self.party_data = party_data if party_data is not None else self._fetch_party_data()
        _tags_list = all_tags_list if all_tags_list is not None else self._fetch_tags_list()
        self.tags_lookup = self._prepare_tags_lookup(_tags_list)
        self.game_content = (
            content_data if content_data is not None else self._fetch_or_load_content()
        )
        self.gear_stats_lookup = self.game_content.get("gear", {}).get("flat", {})
        if not self.gear_stats_lookup:
            self.console.log("Could not find gear data in game content.", style="warning")

        # Initialize Derived Stats
        self.user_con: float = 0.0
        self.user_stealth: int = 0
        self.is_sleeping: bool = False
        self.is_on_boss_quest: bool = False
        self.boss_str: float = 0.0

        # Calculate context from the fetched/provided data
        self._calculate_user_context()
        self.console.log("TaskProcessor Initialized.", style="info")

    # MARK: - Private Data Fetching Helpers
    # & - def _fetch_user_data(self) -> Dict[str, Any]:
    def _fetch_user_data(self) -> Dict[str, Any]:
        """Fetches user data. Returns {} on failure."""
        self.console.log("Fetching user data for TaskProcessor context...", style="info")
        try:
            data = self.api_client.get_user_data()
            return data if data else {}
        except Exception as e:
            self.console.log(f"Exception fetching user data: {e}", style="error")
            return {}

    # & - def _fetch_party_data(self) -> Dict[str, Any]:
    def _fetch_party_data(self) -> Dict[str, Any]:
        """Fetches party data. Returns {} on failure or if not in party."""
        self.console.log("Fetching party data for TaskProcessor context...", style="info")
        try:
            data = self.api_client.get_party_data()
            return data if data else {}
        except Exception as e:
            self.console.log(f"Exception fetching party data: {e}", style="error")
            return {}

    # & - def _fetch_tags_list(self) -> List[Dict[str, Any]]:
    def _fetch_tags_list(self) -> List[Dict[str, Any]]:
        """Fetches all tags. Returns [] on failure."""
        self.console.log("Fetching all tags for lookup...", style="info")
        try:
            return self.api_client.get_tags()  # Returns list or []
        except Exception as e:
            self.console.log(f"Exception fetching tags list: {e}", style="error")
            return []

    # & - def _fetch_or_load_content(self) -> Dict[str, Any]:
    def _fetch_or_load_content(self) -> Dict[str, Any]:
        """Fetches game content from API or loads from cache. Returns {} on failure."""
        self.console.log("Fetching/Loading game content...", style="info")
        raw_content = None
        # --- 1. Try Cache ---
        if Path(CACHE_FILE_CONTENT).exists():
            self.console.log(
                f"Attempting load from cache: '{CACHE_FILE_CONTENT}'...", style="subtle"
            )
            try:
                with open(CACHE_FILE_CONTENT, encoding="utf-8") as f:
                    raw_content = json.load(f)
                if isinstance(raw_content, dict) and raw_content:
                    self.console.log("Successfully loaded content from cache.", style="success")
                else:
                    self.console.log(
                        f"Cache file '{CACHE_FILE_CONTENT}' invalid. Refetching.", style="warning"
                    )
                    raw_content = None
            except (OSError, json.JSONDecodeError, Exception) as e:
                self.console.log(
                    f"Failed load/parse cache '{CACHE_FILE_CONTENT}': {e}. Refetching.",
                    style="warning",
                )
                raw_content = None
        # --- 2. Fetch API if Needed ---
        if raw_content is None:
            self.console.log("Fetching game content from API...")
            try:
                raw_content = self.api_client.get_content()  # Returns dict or None
                if isinstance(raw_content, dict) and raw_content:
                    self.console.log("Successfully fetched content from API.", style="success")
                    # --- 3. Save to Cache ---
                    try:
                        with open(CACHE_FILE_CONTENT, "w", encoding="utf-8") as f:
                            json.dump(raw_content, f, ensure_ascii=False, indent=2)
                        self.console.log(
                            f"Saved content to cache: '{CACHE_FILE_CONTENT}'", style="info"
                        )
                    except (OSError, Exception) as e_save:
                        self.console.log(
                            f"Failed to save content cache '{CACHE_FILE_CONTENT}': {e_save}",
                            style="warning",
                        )
                else:
                    self.console.log("Failed to fetch valid content from API.", style="error")
                    raw_content = {}
            except Exception as e_fetch:
                self.console.log(f"Exception fetching content: {e_fetch}", style="error")
                raw_content = {}
        return raw_content if isinstance(raw_content, dict) else {}

    # MARK: - Private Calculation & Preparation Helpers
    # & - def _prepare_tags_lookup(...)
    def _prepare_tags_lookup(self, tags_list: List[Dict[str, Any]]) -> Dict[str, str]:
        """Creates tag ID -> name lookup dict."""
        if not tags_list:
            self.console.log("Tag list empty. Tag lookup will be empty.", style="warning")
            return {}
        lookup = {
            tag["id"]: tag.get("name", f"Unnamed_{tag['id'][:6]}")  # More descriptive fallback
            for tag in tags_list
            if isinstance(tag, dict) and "id" in tag
        }
        self.console.log(f"Prepared lookup for {len(lookup)} tags.", style="info")
        return lookup

    # & - def _calculate_user_context(self) -> None:
    def _calculate_user_context(self) -> None:
        """Calculates effective CON, stealth, sleep, quest status from instance data."""
        self.console.log("Calculating user context (CON, Stealth, etc.)...", style="info")
        if not self.user_data:
            self.console.log("Cannot calculate context: User data missing.", style="warning")
            return

        try:
            # --- Calculate Effective CON ---
            stats = self.user_data.get("stats", {})
            level = stats.get("lvl", 0)
            user_class = stats.get("class")
            buffs = stats.get("buffs", {})
            equipped_gear = self.user_data.get("items", {}).get("gear", {}).get("equipped", {})

            level_bonus = min(50.0, math.floor(level / 2.0))
            alloc_con = float(stats.get("con", 0.0))
            buff_con = float(buffs.get("con", 0.0))
            gear_con = 0.0
            class_bonus_con = 0.0

            if isinstance(equipped_gear, dict) and self.gear_stats_lookup:
                for key in equipped_gear.values():
                    if not key:
                        continue
                    item_stats = self.gear_stats_lookup.get(key)
                    if isinstance(item_stats, dict):
                        item_base_con = float(item_stats.get("con", 0.0))
                        gear_con += item_base_con
                        if item_stats.get("klass") == user_class:
                            class_bonus_con += item_base_con * 0.5

            self.user_con = level_bonus + alloc_con + gear_con + class_bonus_con + buff_con

            # --- Other Context ---
            self.user_stealth = int(buffs.get("stealth", 0))
            self.is_sleeping = self.user_data.get("preferences", {}).get("sleep", False)
            self.console.log(
                f"User Context: CON={self.user_con:.2f}, Stealth={self.user_stealth}, Sleeping={self.is_sleeping}",
                style="success",
            )

        except (ValueError, TypeError, KeyError, AttributeError) as e:
            self.console.log(
                f"Error calculating user stats context: {e}. Using defaults.", style="warning"
            )
            self.user_con, self.user_stealth, self.is_sleeping = 0.0, 0, False

        # --- Party Context ---
        if not self.party_data:
            self.console.log(
                "Cannot calculate party context: Party data missing.", style="warning"
            )
            self.is_on_boss_quest, self.boss_str = False, 0.0
            return

        try:
            quest = self.party_data.get("quest", {})
            if isinstance(quest, dict) and quest.get("active"):
                boss = quest.get("boss")  # V3 API structure
                if isinstance(boss, dict) and boss.get("str") is not None:
                    self.is_on_boss_quest = True
                    try:
                        self.boss_str = float(boss.get("str", 0.0))
                    except (ValueError, TypeError):
                        self.boss_str = 0.0  # Default if conversion fails
                    self.console.log(
                        f"Party Context: On active BOSS quest (Str={self.boss_str:.2f}).",
                        style="info",
                    )
                else:  # Active quest, but not a boss or no boss strength
                    self.is_on_boss_quest, self.boss_str = False, 0.0
                    quest_key = quest.get("key", "Unknown")
                    self.console.log(
                        f"Party Context: On active quest '{quest_key}' (not boss/no str).",
                        style="info",
                    )
            else:  # Not on an active quest
                self.is_on_boss_quest, self.boss_str = False, 0.0
                self.console.log("Party Context: Not on active quest.", style="info")
        except Exception as e:
            self.console.log(
                f"Error calculating party context: {e}. Assuming no active boss.", style="warning"
            )
            self.is_on_boss_quest, self.boss_str = False, 0.0

    # & - def _value_color(self, value: Optional[float]) -> str: ... (Keep previous theme mapping)
    def _value_color(self, value: Optional[float]) -> str:
        """Determines a semantic style name based on task value."""
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

    # & - def _process_task_tags(...) (Keep previous implementation)
    def _process_task_tags(self, task_data: Dict) -> List[str]:
        """Retrieves tag names using lookup."""
        tag_ids = task_data.get("tags", [])
        if not isinstance(tag_ids, list):
            task_id = task_data.get("id", "N/A")
            self.console.log(
                f"Task {task_id} has non-list tags: {tag_ids}. Processing as empty.",
                style="warning",
            )
            return []
        return [self.tags_lookup.get(tag_id, f"ID:{tag_id}") for tag_id in tag_ids]

    # & - def _calculate_checklist_done(...) (Keep previous implementation)
    def _calculate_checklist_done(self, checklist: Optional[List[Dict]]) -> float:
        """Calculates proportion (0.0-1.0) of checklist items done."""
        if not checklist or not isinstance(checklist, list) or len(checklist) == 0:
            return 1.0
        try:
            completed = sum(
                1 for item in checklist if isinstance(item, dict) and item.get("completed", False)
            )
            total = len(checklist)
            return completed / total if total > 0 else 1.0
        except Exception as e:
            self.console.log(
                f"Error calculating checklist progress: {e}. Defaulting to 1.0.", style="warning"
            )
            return 1.0

    # MARK: - Private Task Type Processors
    # & - def _process_habit(...)
    def _process_habit(self, task_data: Dict) -> Dict[str, Any]:
        """Processes Habit-specific fields."""
        processed = {}
        up, down = task_data.get("up", False), task_data.get("down", False)
        cup, cdown = task_data.get("counterUp", 0), task_data.get("counterDown", 0)
        if up and down:
            processed["direction"], processed["counter"] = (
                "both",
                f"[#A6E3A1]+{cup}[/] / [#F38BA8]-{cdown}[/]",
            )
        elif up:
            processed["direction"], processed["counter"] = "up", f"[#A6E3A1]+{cup}[/]"
        elif down:
            processed["direction"], processed["counter"] = "down", f"[#F38BA8]-{cdown}[/]"
        else:
            processed["direction"], processed["counter"] = "none", "[dim]N/A[/]"
        processed["frequency"] = task_data.get("frequency", "daily")
        val = task_data.get("value", 0.0)
        processed["value"], processed["value_color"] = val, self._value_color(val)
        return processed

    # & - def _process_todo(...)
    def _process_todo(self, task_data: Dict) -> Dict[str, Any]:
        """Processes To-Do-specific fields."""
        processed = {}
        deadline = task_data.get("date")
        processed["is_due"], processed["date"] = bool(deadline), deadline or ""
        if deadline:
            try:
                processed["_status"] = "red" if is_date_passed(deadline) else "due"
            except Exception as e:
                self.console.log(
                    f"Error checking To-Do date '{deadline}' for task {task_data.get('id', 'N/A')}: {e}. Status grey.",
                    style="error",
                )
                processed["_status"] = "grey"
        else:
            processed["_status"] = "grey"
        processed["checklist"] = task_data.get("checklist", [])
        val = task_data.get("value", 0.0)
        processed["value"], processed["value_color"] = val, self._value_color(val)
        return processed

    # & - def _process_daily(...)
    def _process_daily(self, task_data: Dict) -> Dict[str, Any]:
        """Processes Daily-specific fields, including damage."""
        processed = {}
        is_due, completed = task_data.get("isDue", False), task_data.get("completed", False)
        checklist = task_data.get("checklist", [])
        next_due = task_data.get("nextDue", [])
        val = task_data.get("value", 0.0)

        status = "grey"
        if is_due:
            status = "success" if completed else "due"  # Use 'success' for done
        processed["_status"] = status
        processed["checklist"] = checklist
        processed["date"] = next_due[0] if isinstance(next_due, list) and next_due else ""
        processed["is_due"] = is_due
        processed["streak"] = task_data.get("streak", 0)
        processed["value"], processed["value_color"] = val, self._value_color(val)

        # --- Damage Calculation ---
        dmg_user, dmg_party = 0.0, 0.0
        if is_due and not completed and not self.is_sleeping and self.user_stealth <= 0:
            try:
                v_min, v_max = -47.27, 21.27
                c_val = max(v_min, min(val, v_max))
                delta = abs(math.pow(0.9747, float(c_val)))

                if isinstance(checklist, list):
                    check_ratio = self._calculate_checklist_done(checklist)
                    eff_delta = delta * 1.0 - check_ratio
                else:
                    eff_delta = delta

                con_mult = max(0.1, 1.0 - (float(self.user_con) / 250.0))
                prio = task_data.get("priority", 1.0)
                prio_map = {0.1: 0.1, 1.0: 1.0, 1.5: 1.5, 2.0: 2.0}
                prio_mult = (
                    prio_map.get(float(prio), 1.0) if isinstance(prio, (int, float)) else 1.0
                )
                hp_mod = delta * con_mult * prio_mult * 2.0
                dmg_user = round(hp_mod * 10) / 10
                if self.is_on_boss_quest and self.boss_str > 0:
                    boss_delta = eff_delta * prio_mult if prio_mult < 1.0 else eff_delta
                    dmg_party = round(boss_delta * self.boss_str, 1)
            except Exception as e_dmg:
                self.console.log(
                    f"Error calculating damage for Daily {task_data.get('id', 'N/A')}: {e_dmg}",
                    style="error",
                )
        if dmg_user > 0:
            processed["damage_to_user"] = dmg_user
        if dmg_party > 0:
            processed["damage_to_party"] = dmg_party
        return processed

    # & - def _process_reward(...)
    def _process_reward(self, task_data: Dict) -> Dict[str, Any]:
        """Processes Reward-specific fields."""
        return {"value": task_data.get("value", 0)}  # Cost

    # MARK: - Public Processing Methods
    # & - def process_single_task(...)
    def process_single_task(self, task_data: Dict) -> Optional[Dict[str, Any]]:
        """Processes a single raw task into standardized format."""
        if not isinstance(task_data, dict) or not task_data.get("id"):
            self.console.log(f"Skipping invalid task data: {task_data}", style="warning")
            return None
        task_id = task_data["id"]
        task_type = task_data.get("type")
        challenge = task_data.get("challenge", {})
        if not isinstance(challenge, dict):
            challenge = {}
        notes = task_data.get("notes", "")
        text = task_data.get("text", "")
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
            "challenge_id": challenge.get("id", ""),
            "challenge_name": emoji_data_python.replace_colons(challenge.get("shortName", "")),
        }

        type_processor = getattr(self, f"_process_{task_type}", None)
        if callable(type_processor):
            processed.update(type_processor(task_data))
        else:
            self.console.log(
                f"Unknown task type '{task_type}' for task {task_id}", style="warning"
            )
            val = task_data.get("value", 0.0)
            processed.update({"value": val, "value_color": self._value_color(val)})
        return processed

    # & - def process_and_categorize_all(...)
    def process_and_categorize_all(self) -> Dict[str, Any]:
        """Fetches all tasks, processes, and categorizes them."""
        self.console.print("Fetching all tasks...", style="info")
        all_tasks_raw = []
        try:
            all_tasks_raw = self.api_client.get_tasks()  # Returns list or []
            if not isinstance(all_tasks_raw, list):
                self.console.print(
                    f"Failed fetch: Expected list, got {type(all_tasks_raw)}.", style="error"
                )
                all_tasks_raw = []
        except Exception as e:
            self.console.print(f"Fatal Error fetching tasks: {e}", style="error")
            return {"data": {}, "cats": {"tasks": {}, "tags": [], "broken": [], "challenge": []}}

        self.console.print(f"Processing {len(all_tasks_raw)} raw tasks...", style="info")
        tasks_dict: Dict[str, Dict] = {}
        cats_dict: Dict[str, Any] = {
            "tasks": {
                "habits": [],
                "todos": {"due": [], "grey": [], "red": []},
                "dailys": {"success": [], "due": [], "grey": []},
                "rewards": [],
            },
            "tags": set(),
            "broken": [],
            "challenge": set(),
        }

        for task_data in all_tasks_raw:
            processed = self.process_single_task(task_data)
            if not processed:
                continue
            task_id = processed["id"]
            tasks_dict[task_id] = processed
            cats_dict["tags"].update(processed.get("tags", []))
            challenge = task_data.get("challenge", {})  # Use raw data for broken flag
            if isinstance(challenge, dict):
                if challenge.get("broken"):
                    cats_dict["broken"].append(task_id)
                if challenge.get("id"):
                    cats_dict["challenge"].add(challenge.get("id"))
            t_type, t_status = processed.get("_type"), processed.get("_status")
            if t_type == "habit":
                cats_dict["tasks"]["habits"].append(task_id)
            elif t_type == "reward":
                cats_dict["tasks"]["rewards"].append(task_id)
            elif t_type == "todo":
                cats_dict["tasks"]["todos"].setdefault(t_status or "grey", []).append(task_id)
            elif t_type == "daily":
                cats_dict["tasks"]["dailys"].setdefault(t_status or "grey", []).append(task_id)

        cats_dict["tags"] = sorted(list(cats_dict["tags"]))
        cats_dict["challenge"] = sorted(list(cats_dict["challenge"]))
        self.console.print("Task processing and categorization complete.", style="success")
        return {"data": tasks_dict, "cats": cats_dict}

    # MARK: - File Saving (Optional)
    # & - def save_processed_data(...)
    def save_processed_data(
        self, processed_results: Dict, base_filename: str = "processed_output"
    ) -> None:
        """Saves processed task data and categories to separate JSON files."""
        if (
            not isinstance(processed_results, dict)
            or "data" not in processed_results
            or "cats" not in processed_results
        ):
            self.console.print("Invalid processed data provided to save.", style="error")
            return
        try:
            self.console.print("Saving processed data...", style="info")
            save_json(processed_results["data"], f"{base_filename}_data.json")
            save_json(processed_results["cats"], f"{base_filename}_cats.json")
        except Exception as e:
            self.console.print(f"Error saving processed files: {e}", style="error")


# MARK: - User Stats Function
# & - def get_user_stats(...)
def get_user_stats(
    api_client: HabiticaAPI,
    cats_dict: Dict[str, Any],
    processed_tasks_dict: Dict[str, Dict[str, Any]],
    user_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generates a dictionary of user statistics combined with task counts and potential damage.

    Uses pre-fetched user data if provided, otherwise fetches it. Calculates task
    counts from `cats_dict` and sums potential damage from `processed_tasks_dict`.

    Returns:
        Combined user/task statistics dict, or {} on critical error.
    """
    console.print("Calculating user stats...", style="info")
    if user_data is None:
        console.print("User data not provided to get_user_stats, fetching...", style="info")
        try:
            user_data = api_client.get_user_data()
        except Exception as e:
            console.print(f"Failed to fetch user data for stats: {e}", style="error")
            user_data = None
    if not isinstance(user_data, dict) or not user_data:
        console.print("Cannot calculate stats: Valid user data required.", style="error")
        return {}
    if not isinstance(cats_dict, dict) or not cats_dict:
        console.print("Cannot calculate stats: Valid categories data required.", style="error")
        return {}
    if not isinstance(processed_tasks_dict, dict):
        console.print(
            "Cannot calculate stats: Valid processed tasks data required.", style="error"
        )
        return {}

    try:
        # --- Extract Data Safely ---
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
        last_login_utc = ts.get("loggedin")
        last_login_local = "N/A"
        if last_login_utc:
            local_dt = convert_to_local_time(last_login_utc)
            if local_dt:
                last_login_local = local_dt.isoformat(sep=" ", timespec="minutes")
            else:
                last_login_local = f"Error ({last_login_utc})"
        quest = party.get("quest", {})

        # --- Calculate Task Counts ---
        task_counts: Dict[str, Any] = {}
        task_cats_data = cats_dict.get("tasks", {})
        if isinstance(task_cats_data, dict):
            for cat, data in task_cats_data.items():
                if isinstance(data, dict):  # dailys/todos
                    total = sum(len(ids) for ids in data.values() if isinstance(ids, list))
                    task_counts[cat] = {
                        status: len(ids) for status, ids in data.items() if isinstance(ids, list)
                    }
                    task_counts[cat]["_total"] = total
                elif isinstance(data, list):  # habits/rewards
                    task_counts[cat] = len(data)
        else:
            console.print("Invalid 'tasks' structure in cats_dict.", style="warning")

        # --- Calculate Damage ---
        dmg_user, dmg_party = 0.0, 0.0
        due_dailies = cats_dict.get("tasks", {}).get("dailys", {}).get("due", [])
        for task_id in due_dailies:
            task = processed_tasks_dict.get(task_id)
            if isinstance(task, dict):
                dmg_user += float(task.get("damage_to_user", 0.0))
                dmg_party += float(task.get("damage_to_party", 0.0))

        # --- Assemble Final Dict ---
        output = {
            "username": local_auth.get("username", "N/A"),
            "class": u_class,
            "level": stats.get("lvl", 0),
            "hp": float(stats.get("hp", 0.0)),
            "maxHealth": stats.get("maxHealth", 50),
            "mp": float(stats.get("mp", 0.0)),
            "maxMP": stats.get("maxMP", 0),
            "exp": float(stats.get("exp", 0.0)),
            "toNextLevel": stats.get("toNextLevel", 0),
            "gp": float(stats.get("gp", 0.0)),
            "gems": gems,
            "stats": {
                "str": stats.get("str", 0),
                "int": stats.get("int", 0),
                "con": stats.get("con", 0),
                "per": stats.get("per", 0),
            },
            "sleeping": prefs.get("sleep", False),
            "day_start": prefs.get("dayStart", 0),
            "last_login_local": last_login_local,
            "quest_active": quest.get("active", False),
            "quest_key": quest.get("key"),
            "task_counts": task_counts,
            "broken_challenge_tasks": len(cats_dict.get("broken", [])),
            "joined_challenges_count": len(cats_dict.get("challenge", [])),
            "tags_in_use_count": len(cats_dict.get("tags", [])),
            "potential_daily_damage_user": round(dmg_user, 2),
            "potential_daily_damage_party": round(dmg_party, 2),
        }
        console.print("User stats calculation complete.", style="success")
        return output

    except Exception as e_stat:
        console.print(f"Error calculating user stats: {e_stat}", style="error")
        console.print_exception(show_locals=False)
        return {}  # Return empty dict on failure
