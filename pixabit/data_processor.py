# pixabit/processing.py

# --- Standard Imports ---
import json
import math
import os
import time  # Potentially needed if adding delays or logging timestamps
from typing import Any, Dict, List, Optional

# --- Third-party Imports ---
import emoji_data_python

from .api import HabiticaAPI
from .utils.dates import convert_to_local_time, is_date_passed
from .utils.display import console, print
from .utils.save_json import save_json


# ==============================================================================
# Task Processor Class
# ==============================================================================
class TaskProcessor:
    """
    Processes raw task data fetched from the Habitica API into a structured
    format and categorizes tasks based on type and status.

    Also handles fetching and utilizing tag information for enrichment.
    """

    # --- Initialization ---
    def __init__(self, api_client: HabiticaAPI):
        """
        Initializes the TaskProcessor.

        Fetches user tags upon initialization to create a lookup table used
        for processing task tag names efficiently.

        Args:
            api_client: An authenticated instance of the HabiticaAPI client.
        """
        # --- START OF METHOD --- (Level 0 Indent)
        # console.log("--- TaskProcessor __init__ START ---")  # Your debug line

        # --- Level 1 Indent (Inside __init__) ---
        # console.print("Initializing TaskProcessor...") # Original print, can be removed if using log
        CACHE_FILE_CONTENT = "content_cache.json"

        self.console = console
        self.api_client = api_client
        console.log("Fetching tags for lookup...", style="info")
        self.tags_lookup = self._fetch_and_prepare_tags()
        if not self.tags_lookup:
            console.log(
                "Warning: Tag lookup is empty. Tag names may not be processed correctly.",
                style="warning",
            )
        else:
            console.log(f"Fetched {len(self.tags_lookup)} tags.", style="success")

        # Initialize attributes
        self.user_data: Dict[str, Any] = {}
        self.party_data: Dict[str, Any] = {}
        self.game_content: Dict[str, Any] = {}
        self.gear_stats_lookup: Dict[str, Dict] = {}
        self.user_con: int = 0
        self.user_stealth: int = 0
        self.is_sleeping: bool = False
        self.is_on_boss_quest: bool = False
        self.boss_str: float = 0.0

        # --- Fetch/Load Game Content (with Caching) ---
        self.console.log("Fetching game content (for gear stats)...", style="info")
        # --- Fetch Game Content (ONCE) ---

        # The /content endpoint response is usually NOT wrapped in {success, data}
        # --- Fetch/Load Game Content (with Caching) ---
        raw_content = None

        # 1. Try loading from cache first (Level 1 Indent)
        if os.path.exists(CACHE_FILE_CONTENT):
            self.console.log(
                f"Found cache file: '{CACHE_FILE_CONTENT}'. Attempting to load..."
            )
            try:
                with open(CACHE_FILE_CONTENT, "r", encoding="utf-8") as f:
                    raw_content = json.load(f)
                self.console.log(
                    "Successfully loaded game content from cache.", style="success"
                )
            except (json.JSONDecodeError, IOError, Exception) as e:
                self.console.log(
                    f"[Warning] Failed to load or parse cache file '{CACHE_FILE_CONTENT}': {e}. Will fetch from API.",
                    style="warning",
                )
                raw_content = None  # Ensure raw_content is None so we fetch fresh

        # 2. If cache didn't load, fetch from API and save to cache
        if raw_content is None:
            self.console.log(
                "Cache not found or failed to load. Fetching game content from API...",
                style="warning",
            )
            try:
                # The /content endpoint response is usually NOT wrapped in {success, data}
                raw_content = self.api_client.get("/content")  # Use basic GET
                if (
                    isinstance(raw_content, dict) and raw_content
                ):  # Check if fetch was successful
                    self.console.log(
                        "Successfully fetched game content from API.", style="success"
                    )
                    # Save the fetched content to the cache file
                    try:
                        with open(CACHE_FILE_CONTENT, "w", encoding="utf-8") as f:
                            json.dump(
                                raw_content, f, ensure_ascii=False
                            )  # No indent for smaller file size maybe? Or indent=4
                        self.console.log(
                            f"Saved fetched game content to cache file: '{CACHE_FILE_CONTENT}'",
                            style="success",
                        )
                    except (IOError, Exception) as e:
                        self.console.log(
                            f"[Warning] Failed to save game content to cache file '{CACHE_FILE_CONTENT}': {e}",
                            style="warning",
                        )
                else:
                    self.console.log(
                        "[Warning] Failed to fetch valid game content from API.",
                        style="warning",
                    )
                    raw_content = {}  # Use empty dict to prevent errors later

            except Exception as e:
                self.console.log(
                    f"[Warning] Error during API fetch for game content: {e}",
                    style="warning",
                )
                raw_content = {}  # Use empty dict on error

        # 3. Process the raw_content (whether from cache or API)
        if isinstance(raw_content, dict):
            self.game_content = raw_content
            # Create a direct lookup for gear stats: gear_key -> {con: X, str: Y ...}
            self.gear_stats_lookup = self.game_content.get("gear", {}).get("flat", {})
            if not self.gear_stats_lookup:
                self.console.log(
                    "[Warning] Could not find gear data in game content.",
                    style="warning",
                )
        else:
            self.console.log(
                "[Warning] Game content is not a valid dictionary.", style="warning"
            )
            self.game_content = {}
            self.gear_stats_lookup = {}

        # --- Fetch User/Party Data and Calculate CON --- (Level 1 Indent)
        # This is the outer 'try' block where the error likely originated
        try:  # <<<<< Level 1 Indent
            # Level 2 Indent
            self.console.log("Fetching full user data for context...", style="info")
            self.user_data = self.api_client.get_user_data()
            if not self.user_data:
                raise ValueError("Failed to fetch user data", style="error")
            # -----------------------

            # --- Calculate EFFECTIVE CON (Using Content Lookup) ---
            base_stats = self.user_data.get("stats", {})
            level = self.user_data.get("stats", {}).get("lvl", 0)
            user_class = self.user_data.get("stats", {}).get(
                "class"
            )  # Get user's class
            buffs = base_stats.get("buffs", {})
            equipped_gear_keys = (
                self.user_data.get("items", {}).get("gear", {}).get("equipped", {})
            )
            # Component 1: Level Bonus
            level_bonus = min(50, math.floor(level / 2))

            # Component 2: Allocated Points (Assuming this is base_con from API)
            allocated_points_con = base_stats.get("con", 0)

            # Component 3: Buff CON
            buff_con = buffs.get("con", 0)

            # Components 4 & 5: Base Gear CON + Class Equip Bonus
            total_base_gear_con = 0  # Initialize accumulator
            total_class_equip_bonus = 0  # Initialize accumulator

            if isinstance(equipped_gear_keys, dict) and self.gear_stats_lookup:
                for gear_key in equipped_gear_keys.values():
                    if not gear_key:
                        continue
                    gear_item_stats = self.gear_stats_lookup.get(gear_key)
                    if isinstance(gear_item_stats, dict):
                        # Get THIS item's base CON
                        item_base_con = gear_item_stats.get("con", 0)
                        # Add to total base gear CON
                        total_base_gear_con += item_base_con

                        # Check for class bonus
                        gear_item_class = gear_item_stats.get(
                            "klass", None
                        )  # Habitica uses 'klass' in content data
                        if gear_item_class == user_class:
                            item_class_bonus = item_base_con * 0.5
                            total_class_equip_bonus += item_class_bonus

            # ---------------------------------------------------------

            # Calculate final effective CON using all 5 components
            self.user_con = (
                allocated_points_con
                + level_bonus
                + total_base_gear_con
                + total_class_equip_bonus
                + buff_con  # Component 4 (Allocated)  # Component 1 (Level)  # Component 2 (Equipment Base)  # Component 3 (Class Bonus)  # Component 5 (Buffs)
            )
            # --------------------------------------------------

            # --- Get other relevant context from user data ---
            self.user_stealth = buffs.get("stealth", 0)
            self.is_sleeping = self.user_data.get("preferences", {}).get("sleep", False)
            # -----------------------------------------------

            self.console.log(
                f"User Context: Effective CON={self.user_con}, Stealth={self.user_stealth}, Sleeping={self.is_sleeping}"
            )

            self.console.log("Fetching party data for context...")
            self.party_data = self.api_client.get_party_data()  # Use API client method
            quest_info = self.party_data.get("quest", {})

            if quest_info and quest_info.get("active"):
                boss_info = quest_info.get("content", {}).get("boss")
                if isinstance(boss_info, dict) and boss_info.get("str") is not None:
                    self.is_on_boss_quest = True
                    try:
                        self.boss_str = float(boss_info.get("str", 0.0))
                    except (ValueError, TypeError):
                        self.boss_str = 0.0
                    self.console.log(
                        f"Party Context: On active boss quest (Str={self.boss_str}).",
                        style="info",
                    )
                else:
                    self.console.log(
                        "Party Context: On active quest (not boss or no str).",
                        style="info",
                    )
            else:
                self.console.log("Party Context: Not on active quest.", style="info")

        except Exception as e:
            self.console.log(
                f"[Warning] Couldn't fetch all context for TaskProcessor: {e}",
                style="warning",
            )
            # Ensure defaults if fetches failed
            self.user_data = self.user_data or {}
            self.party_data = self.party_data or {}
            self.user_con = self.user_con or 0
            self.user_stealth = self.user_stealth or 0
            self.is_sleeping = self.is_sleeping or False
            self.is_on_boss_quest = self.is_on_boss_quest or False
            self.boss_str = self.boss_str or 0.0
        # ------------------------------------------------------------
        self.console.log("TaskProcessor Initialized.", style="info")

    # --- Private Helper Methods ---
    # & -     def _fetch_and_prepare_tags(self) -> Dict[str, str]:
    def _fetch_and_prepare_tags(self) -> Dict[str, str]:
        """
        Fetches all user tags from the Habitica API.

        Creates and returns a dictionary mapping tag IDs to tag names for quick lookup.
        If a tag doesn't have a name, its ID is used as the fallback name.
        Includes error handling for the API call.

        Returns:
            Dict[str, str]: A dictionary where keys are tag IDs and values are tag names.
                            Returns an empty dictionary if fetching fails.
        """
        try:
            tags_list = self.api_client.get_tags()
            # Ensure ID exists before adding to lookup
            return {
                tag["id"]: tag.get("name", tag["id"])
                for tag in tags_list
                if "id" in tag
            }  # Use ID as fallback name  # Only include tags that have an ID
        except Exception as e:
            console.print(f"Error fetching or processing tags: {e}", style="error")
            return {}

    # & -     def _value_color(self, value: Optional[float]) -> str:
    def _value_color(self, value: Optional[float]) -> str:
        """
        Determines a descriptive color string based on a numerical task value.

        Used for categorizing task value intensity (e.g., for display).
        Handles None values by returning 'neutral'.

        Args:
            value (Optional[float]): The numerical value of the task (can be positive, negative, or zero).

        Returns:
            str: A color category string ('best', 'better', 'good', 'neutral',
                 'bad', 'worse', 'worst').
        """
        if value is None:
            return "neutral"  # Default if value is missing

        color: str
        if value > 11:
            color = "best"
        elif value > 5:
            color = "better"
        elif value > 0:
            color = "good"
        elif value == 0:
            color = "neutral"
        elif value > -9:
            color = "bad"  # Value is negative
        elif value > -16:
            color = "worse"  # Value is more negative
        else:
            color = "worst"  # Value is -16 or lower
        return color

    # & -     def _process_task_tags(self, task_data: Dict) -> List[str]:
    def _process_task_tags(self, task_data: Dict) -> List[str]:
        """
        Retrieves the names of tags associated with a task using the pre-fetched lookup.

        Args:
            task_data (Dict): The raw dictionary for a single task.

        Returns:
            List[str]: A list of tag names corresponding to the tag IDs in the task data.
                       Returns the tag ID itself if a name is not found in the lookup.
                       Returns an empty list if 'tags' key is missing or not a list.
        """
        tag_ids = task_data.get("tags", [])
        if not isinstance(tag_ids, list):
            console.print(
                f"Warning: Task {task_data.get('id', 'N/A')} has non-list tags: {tag_ids}",
                style="warning",
            )
            return []  # Handle unexpected type
        # Use tags_lookup, fallback to tag_id if name not found
        return [self.tags_lookup.get(tag_id, tag_id) for tag_id in tag_ids]

    # --- Private Task Type Processors ---
    # & -     def _process_habit(self, task_data: Dict) -> Dict[str, Any]:
    def _process_habit(self, task_data: Dict) -> Dict[str, Any]:
        """
        Processes fields specific to Habit-type tasks.

        Extracts direction (up/down/both), combines counters into a display string,
        fetches frequency, and calculates value/value_color.

        Args:
            task_data (Dict): The raw dictionary for a single habit task.

        Returns:
            Dict[str, Any]: A dictionary containing processed habit-specific fields:
                            'direction', 'counter', 'frequency', 'value', 'value_color'.
        """
        processed = {}
        task_up = task_data.get("up", False)
        task_down = task_data.get("down", False)
        counter_up = task_data.get("counterUp", 0)
        counter_down = task_data.get("counterDown", 0)

        if task_up and task_down:
            processed["direction"] = "both"
            processed["counter"] = f"⧾{counter_up}, -{counter_down}"
        elif not task_up and not task_down:  # Should not happen often, but handle it
            processed["direction"] = "none"
            processed["counter"] = (
                f"⧾{counter_up}, -{counter_down}"  # Still show counters?
            )
        elif task_up:
            processed["direction"] = "up"
            processed["counter"] = f"⧾{counter_up}"
        else:  # Only down is true
            processed["direction"] = "down"
            processed["counter"] = f"-{counter_down}"

        processed["frequency"] = task_data.get(
            "frequency", "daily"
        )  # Default if missing
        task_value = task_data.get("value", 0.0)  # Default if missing
        processed["value"] = task_value
        processed["value_color"] = self._value_color(task_value)
        return processed

    # & -     def _process_todo(self, task_data: Dict) -> Dict[str, Any]:
    def _process_todo(self, task_data: Dict) -> Dict[str, Any]:
        """
        Processes fields specific to To-Do type tasks.

        Checks for a due date ('date'), determines if it's passed ('_status'),
        extracts the checklist, and calculates value/value_color.

        Args:
            task_data (Dict): The raw dictionary for a single todo task.

        Returns:
            Dict[str, Any]: A dictionary containing processed todo-specific fields:
                            'is_due', 'date', '_status', 'checklist', 'value', 'value_color'.
        """
        processed = {}
        deadline_str = task_data.get("date")  # Can be None or empty string

        if deadline_str:
            processed["is_due"] = True
            processed["date"] = deadline_str  # Store original string
            try:
                if is_date_passed(deadline_str):
                    processed["_status"] = "red"  # Past due
                else:
                    processed["_status"] = "due"  # Due in the future
            except Exception as e:
                console.print(
                    f"Error checking To-Do date ({deadline_str}) for task {task_data.get('id', 'N/A')}: {e}. Status set to 'grey'.",
                    style="error",
                )
                processed["_status"] = "grey"  # Fallback on date processing error
        else:
            processed["is_due"] = False
            processed["_status"] = "grey"  # Not due
            processed["date"] = ""  # Ensure empty string if no deadline

        processed["checklist"] = task_data.get("checklist", [])  # Default to empty list
        task_value = task_data.get("value", 0.0)
        processed["value"] = task_value
        processed["value_color"] = self._value_color(task_value)
        return processed

    # & -     def _process_daily(self, task_data: Dict) -> Dict[str, Any]:
    def _process_daily(self, task_data: Dict) -> Dict[str, Any]:
        """
        Processes fields specific to Daily-type tasks.

        Determines the status ('_status': done, due, grey) based on 'isDue' and 'completed'.
        Extracts checklist, next due date ('date'), streak, and value/value_color.

        Args:
            task_data (Dict): The raw dictionary for a single daily task.

        Returns:
            Dict[str, Any]: A dictionary containing processed daily-specific fields:
                            '_status', 'checklist', 'date' (next due), 'is_due',
                            'streak', 'value', 'value_color'.
        """
        processed = {}

        is_due_flag = task_data.get("isDue", False)  # Default if missing
        completed_flag = task_data.get("completed", False)  # Default if missing

        # Determine status
        if not is_due_flag:
            status = "grey"  # Not due today (e.g., repeats on specific days)
        elif completed_flag:
            status = "done"  # Due today and completed
        else:
            status = "due"  # Due today but not completed

        processed["_status"] = status

        processed["checklist"] = task_data.get("checklist", [])
        # Get nextDue safely, handle empty list or non-list
        next_due_list = task_data.get("nextDue", [])
        processed["date"] = (
            next_due_list[0]
            if isinstance(next_due_list, list) and len(next_due_list) > 0
            else ""
        )

        processed["is_due"] = is_due_flag
        processed["streak"] = task_data.get("streak", 0)  # Default if missing
        task_value = task_data.get("value", 0.0)
        processed["value"] = task_value
        processed["value_color"] = self._value_color(task_value)
        return processed

    # & -     def _process_reward(self, task_data: Dict) -> Dict[str, Any]:
    def _process_reward(self, task_data: Dict) -> Dict[str, Any]:
        """
        Processes fields specific to Reward-type tasks.

        Currently, only extracts the 'value' (cost) of the reward.

        Args:
            task_data (Dict): The raw dictionary for a single reward task.

        Returns:
            Dict[str, Any]: A dictionary containing processed reward-specific fields:
                            'value'.
        """
        # Rewards primarily have a value (cost)
        return {"value": task_data.get("value", 0)}  # Default cost to 0 if missing

    # --- NEW HELPER METHOD ---
    # & -     def _calculate_checklist_done(self, checklist: Optional[List[Dict]]) -> float:
    def _calculate_checklist_done(self, checklist: Optional[List[Dict]]) -> float:
        """Calculates the proportion (0.0 to 1.0) of checklist items done."""
        if not checklist or not isinstance(checklist, list) or len(checklist) == 0:
            # No checklist or empty = 100% "done" for damage reduction
            return 1.0
        completed_count = sum(1 for item in checklist if item.get("completed", False))
        total_count = len(checklist)
        return completed_count / total_count if total_count > 0 else 1.0

    # --- MODIFIED _process_daily ---
    # & -     def _process_daily(self, task_data: Dict) -> Dict[str, Any]:
    def _process_daily(self, task_data: Dict) -> Dict[str, Any]:
        """Processes Daily specific fields, including per-task damage calculation."""
        processed = {}
        # Status calculation
        is_due = task_data.get("isDue", False)
        completed = task_data.get("completed", False)
        status = "grey" if not is_due else ("done" if completed else "due")
        processed["_status"] = status

        # Other daily fields
        checklist_items = task_data.get("checklist", [])
        processed["checklist"] = checklist_items  # Keep raw items
        next_due_list = task_data.get("nextDue", [])
        processed["date"] = (
            next_due_list[0]
            if isinstance(next_due_list, list) and len(next_due_list) > 0
            else ""
        )
        processed["is_due"] = is_due
        processed["streak"] = task_data.get("streak", 0)
        task_value = task_data.get("value", 0.0)
        processed["value"] = task_value
        processed["value_color"] = self._value_color(task_value)

        # --- Damage Calculation Logic ---
        damage_to_user = 0.0
        damage_to_party = 0.0
        # Note: We check current stealth but don't modify it here.
        # If multiple tasks would be stealthed, this calculates damage as 0 for all,
        # which might slightly underestimate total damage if stealth runs out.
        # Accurate stealth accounting would require processing dailies in order.
        if is_due and not completed and not self.is_sleeping and self.user_stealth <= 0:
            # Value capping
            value_min = -47.27
            value_max = 21.27
            curr_val = max(value_min, min(task_value, value_max))

            # Base delta (~0-1, higher for more negative value)
            delta = abs(math.pow(0.9747, curr_val))

            # Checklist reduction (Full completion = 0 damage)
            checklist_items = task_data.get(
                "checklist"
            )  # Get checklist, could be None or []
            if isinstance(checklist_items, list) and checklist_items:

                checklist_done_ratio = self._calculate_checklist_done(checklist_items)
                delta *= 1.0 - checklist_done_ratio

            # User Damage
            con_bonus = max(0.1, 1.0 - (float(self.user_con) / 250.0))
            priority = task_data.get("priority", 1.0)
            try:  # Handle priority being string or number
                prio_float = float(priority)
                prio_map = {0.1: 0.1, 1.0: 1.0, 1.5: 1.5, 2.0: 2.0}
                priority_multiplier = prio_map.get(
                    prio_float, 1.0
                )  # Default to 1 if invalid
            except (ValueError, TypeError):
                priority_multiplier = 1.0

            hp_mod = delta * con_bonus * priority_multiplier * 2.0
            # damage_to_user = round(hp_mod, 2)  # Round
            damage_to_user = round(hp_mod * 10) / 10  # New version (1 decimal)

            # Party Damage (Boss Quests)
            if self.is_on_boss_quest and self.boss_str > 0:
                boss_delta = delta
                if priority_multiplier < 1.0:
                    boss_delta *= priority_multiplier  # Trivial adj
                damage_to_party_unrounded = boss_delta * self.boss_str
                damage_to_party = round(
                    damage_to_party_unrounded, 1
                )  # Round to 1 decimal
            else:
                damage_to_party = 0.0
        # else: damage remains 0 (sleeping, completed, not due, or stealthed)

        if damage_to_user != 0:
            processed["damage_to_user"] = damage_to_user
        if damage_to_party != 0:
            processed["damage_to_party"] = damage_to_party
        # -----------------------------

        return processed

    # --- Public Processing Methods ---
    # & -     def process_single_task(self, task_data: Dict) -> Optional[Dict[str, Any]]:
    def process_single_task(self, task_data: Dict) -> Optional[Dict[str, Any]]:
        """
        Processes a single raw task dictionary into a standardized, enriched format.

        Extracts common fields (ID, type, text, notes, tags, challenge info, etc.),
        replaces emoji codes, and calls the appropriate private processor
        (_process_habit, _process_todo, etc.) to add type-specific fields.

        Args:
            task_data (Dict): The raw dictionary representing a single task from the API.

        Returns:
            Optional[Dict[str, Any]]: The processed task dictionary with standardized
                                      and type-specific fields, or None if the input
                                      task data is invalid (e.g., missing 'id').
        """
        if not isinstance(task_data, dict) or not task_data.get("id"):
            console.print(
                f"Warning: Skipping invalid task data (missing ID or not a dict): {task_data}",
                style="warning",
            )
            return None

        task_id = task_data["id"]  # ID is confirmed to exist here
        task_type = task_data.get("type")

        # --- Process common fields safely ---
        challenge_info = task_data.get(
            "challenge", {}
        )  # Default to empty dict if missing
        if not isinstance(challenge_info, dict):
            console.print(
                f"Warning: Task {task_id} has non-dict challenge info: {challenge_info}",
                style="warning",
            )
            challenge_info = {}  # Ensure it's a dict

        notes = task_data.get("notes", "")  # Default to empty string
        text = task_data.get("text", "")  # Default to empty string

        processed = {
            "_type": task_type,
            "attribute": task_data.get(
                "attribute", "str"
            ),  # Default attribute if missing? Habitica default is str
            "challenge_id": challenge_info.get("id", ""),
            "challenge_task_id": challenge_info.get("taskId", ""),
            "challenge": emoji_data_python.replace_colons(
                challenge_info.get("shortName", "")
            ),
            "id": task_id,
            "note": emoji_data_python.replace_colons(notes if notes else ""),
            "priority": task_data.get("priority", 1),  # Habitica default is 1 (Medium)
            "tag_id": task_data.get("tags", []),  # Keep original list of IDs
            "tag_name": self._process_task_tags(task_data),  # Get list of names
            "text": emoji_data_python.replace_colons(text if text else ""),
            "created": task_data.get(
                "createdAt", ""
            ),  # Keep original ISO timestamp string
            # "_raw": task_data # Optional: uncomment to include raw data for debugging
        }

        # --- Add type-specific fields ---
        type_specific_data = {}
        if task_type == "habit":
            type_specific_data = self._process_habit(task_data)
        elif task_type == "todo":
            type_specific_data = self._process_todo(task_data)
        elif task_type == "daily":
            type_specific_data = self._process_daily(task_data)
        elif task_type == "reward":
            type_specific_data = self._process_reward(task_data)
        else:
            console.print(
                f"Warning: Unknown task type '{task_type}' for task ID {task_id}"
            )
            # Add minimal common fields if type is unknown?
            processed["value"] = task_data.get("value", 0.0)
            processed["value_color"] = self._value_color(processed["value"])

        processed.update(type_specific_data)
        return processed

    # & -     def process_and_categorize_all(self) -> Dict[str, Dict]:
    def process_and_categorize_all(self) -> Dict[str, Dict]:
        """
        Fetches all tasks using the API client, processes each task individually,
        and categorizes them based on type and status.

        Builds two main structures:
        1. `data`: A dictionary mapping task IDs to their fully processed task dictionaries.
        2. `cats`: A dictionary categorizing task IDs. Includes lists for habits/rewards,
           status-based dictionaries for todos/dailies (due, grey, red/done),
           a sorted list of unique tag IDs used across all tasks, a list of IDs for
           tasks belonging to broken challenges, and a sorted list of unique IDs for
           challenges the user is part of.

        Includes error handling for the initial task fetch.

        Returns:
            Dict[str, Dict]: A dictionary containing two keys:
                             'data': The dictionary of processed tasks (ID -> processed_task).
                             'cats': The dictionary containing categorized task IDs and metadata.
                             Returns a default empty structure if fetching tasks fails.
        """
        console.print("Fetching all tasks via API client...")
        try:
            all_tasks_raw = self.api_client.get_tasks()
        except Exception as e:
            console.print(f"Fatal Error: Could not fetch tasks: {e}", style="error")
            # Return empty but valid structure to prevent downstream errors
            return {
                "data": {},
                "cats": {
                    "tasks": {
                        "habits": [],
                        "todos": {"due": [], "grey": [], "red": []},
                        "dailys": {"done": [], "due": [], "grey": []},
                        "rewards": [],
                    },
                    "tags": [],
                    "broken": [],
                    "challenge": [],
                },
            }

        console.print(f"Processing {len(all_tasks_raw)} tasks...", style="info")
        tasks_dict = {}  # Stores {task_id: processed_task_dict}
        # Initialize categories structure fully
        cats_dict = {
            "tasks": {
                "habits": [],
                "todos": {"due": [], "grey": [], "red": []},  # Statuses for todos
                "dailys": {"done": [], "due": [], "grey": []},  # Statuses for dailys
                "rewards": [],
            },
            "tags": set(),  # Use set for efficient unique tracking of tag IDs
            "broken": [],  # List of task IDs from broken challenges
            "challenge": set(),  # Use set for unique joined challenge IDs
        }

        for task_data in all_tasks_raw:
            processed_task = self.process_single_task(task_data)
            if processed_task is None:
                continue  # Skip if processing failed (e.g., missing ID, logged in process_single_task)

            task_id = processed_task["id"]
            tasks_dict[task_id] = processed_task

            # --- Categorization Logic ---
            # Track unique tag IDs used
            cats_dict["tags"].update(
                processed_task.get("tag_id", [])
            )  # Add all tag IDs from the task

            # Check for broken challenges (using original task_data for direct access)
            challenge_info = task_data.get("challenge", {})
            if not isinstance(challenge_info, dict):
                challenge_info = {}  # Ensure dict
            if challenge_info.get("broken"):  # Check the 'broken' flag
                cats_dict["broken"].append(task_id)
            # Track unique challenge IDs joined
            if challenge_info.get("id"):
                cats_dict["challenge"].add(challenge_info["id"])

            # Categorize by type and status
            task_type = processed_task.get("_type")
            if task_type in ["todo", "daily"]:
                # Use status determined during processing (e.g., 'red', 'due', 'grey', 'done')
                status = processed_task.get(
                    "_status", "grey"
                )  # Default to 'grey' if missing
                type_key = task_type + "s"  # 'todos' or 'dailys'
                # Ensure the structure exists before appending
                if (
                    type_key in cats_dict["tasks"]
                    and status in cats_dict["tasks"][type_key]
                ):
                    cats_dict["tasks"][type_key][status].append(task_id)
                else:
                    # This should ideally not happen if _status is always set correctly
                    console.print(
                        f"Warning: Could not categorize task {task_id} - invalid type/status ({type_key}/{status})",
                        style="warning",
                    )
                    # Optionally add to a general 'uncategorized' list or just log
            elif task_type in ["habit", "reward"]:
                type_key = task_type + "s"  # 'habits' or 'rewards'
                if type_key in cats_dict["tasks"]:
                    cats_dict["tasks"][type_key].append(task_id)
            # else: handle unknown types if necessary, already logged in process_single_task

        # Convert sets back to sorted lists for JSON compatibility/final structure
        cats_dict["tags"] = sorted(list(cats_dict["tags"]))
        cats_dict["challenge"] = sorted(list(cats_dict["challenge"]))

        console.print("Processing complete.", style="success")
        return {"data": tasks_dict, "cats": cats_dict}

    # --- File Saving ---
    # & -     def save_processed_data(self, processed_data: Dict):
    def save_processed_data(self, processed_data: Dict):
        """
        Saves the processed task data and category dictionaries to separate files.

        Uses the `save_json` utility function. Expects the input dictionary
        to have 'data' and 'cats' keys.

        Args:
            processed_data (Dict): The dictionary returned by
                                   `process_and_categorize_all`, containing
                                   'data' and 'cats' keys.
        """
        if (
            not processed_data
            or "data" not in processed_data
            or "cats" not in processed_data
        ):
            console.print(
                "Error: No valid processed data provided to save.", style="error"
            )
            return
        try:
            console.print("Saving processed data...", style="info")
            # Use the imported save_json function
            # Save main task data (ID -> processed task)
            save_json(
                processed_data["data"], "tasks_data", "_processed"
            )  # e.g., tasks_data_processed.json
            # Save category data (lists/dicts of task IDs)
            save_json(
                processed_data["cats"], "tasks_cats", "_processed"
            )  # e.g., tasks_cats_processed.json
            console.print("Processed data saved successfully.", style="success")
        except Exception as e:
            console.print(f"Error saving processed files: {e}", style="error")


# ==============================================================================
# Example Usage (Intended for main script/CLI)
# ==============================================================================
# from pixabit.api import HabiticaAPI
# from pixabit.processing import TaskProcessor
# # from pixabit.get_user_stats import get_user_stats # If separate
#
# if __name__ == "__main__": # Example guard
#     try:
#         console.print("--- Starting Pixabit Processing ---")
#         # Assume API client is configured via environment variables or .env file
#         api = HabiticaAPI()
#         processor = TaskProcessor(api_client=api)
#
#         console.print("\nProcessing and categorizing all tasks...")
#         processed_results = processor.process_and_categorize_all()
#
#         if processed_results:
#             processor.save_processed_data(processed_results)
#
#             # Example: Calculate stats if needed (assuming get_user_stats exists)
#             # if 'cats' in processed_results:
#             #      user_stats = get_user_stats(api_client=api, cats_dict=processed_results['cats'])
#             #      console.print("\n--- User Stats ---")
#             #      import json
#             #      console.print(json.dumps(user_stats, indent=2))
#             #      # Save stats if needed
#             #      # from pixabit.utils.save_json import save_json
#             #      # save_json(user_stats, "user_stats", "_calculated")
#             # else:
#             #      console.print("Skipping user stats calculation: 'cats' data missing.")
#         else:
#              console.print("Processing failed, no results to save or analyze.")
#
#         console.print("\n--- Pixabit Processing Finished ---")
#
#     except Exception as e:
#         console.print(f"\n--- An error occurred in the main processing script ---")
#         console.print(f"{type(e).__name__}: {e}")
#         # Optionally re-raise or log traceback for debugging
#         # import traceback
#         # traceback.print_exc()

# User Stats ───────────────────────────────────────────────────────────────


# & - def get_user_stats(
def get_user_stats(
    api_client: HabiticaAPI, cats_dict: Dict[str, Any], processed_tasks_dict: Dict
) -> Dict[str, Any]:
    """
    Retrieves user stats from Habitica API and combines with task counts.

    Fetches the `/user` endpoint data, extracts relevant statistics (level,
    hp, mp, gp, class, preferences, etc.), calculates task counts per category
    and status from the provided `cats_dict`, and formats everything into a
    single dictionary. Also saves the resulting stats dictionary to a JSON file
    named `user_stats_processed.json`.

    Args:
        api_client (HabiticaAPI): An authenticated HabiticaAPI client instance.
        cats_dict (Dict[str, Any]): The 'cats' dictionary generated by TaskProcessor
                                    (or similar structure), containing categorized
                                    task IDs (e.g., `cats['tasks']['todos']['due']`)
                                    and other tracked info like `cats['broken']`,
                                    `cats['tags']`, `cats['challenge']`.

    Returns:
        Dict[str, Any]: A dictionary containing combined user and task statistics.
                        Keys include 'username', 'class', 'level', 'stats' (dict),
                        'hp', 'mp', 'exp', 'gp', 'quest_active', 'sleeping',
                        'day_start', 'last_login_local', 'task_counts' (dict),
                        'broken_challenge_tasks', 'joined_challenges_count',
                        'tags_in_use_count'. Returns an empty dictionary `{}`
                        if fetching user data fails.

    Raises:
        requests.exceptions.RequestException: If the API call to fetch user data fails.
        Exception: Catches and reports other unexpected errors during processing or saving.
    """
    console.print("Fetching user data for stats...")
    output_stats: Dict[str, Any] = {}  # Initialize empty dict

    try:
        # Fetch user data including stats, party, preferences, auth timestamps
        user_data = api_client.get_user_data()  # Fetches /user endpoint data
        if not isinstance(user_data, dict) or not user_data:  # More robust check
            console.print(
                "[error]Error:[/error] Failed to fetch valid user data from API."
            )
            return {}  # Return empty dict on failure

        # --- Safely extract data from nested dictionaries ---
        stats: Dict[str, Any] = user_data.get("stats", {})
        party: Dict[str, Any] = user_data.get("party", {})
        balance = user_data.get("balance", 0.0)
        gems_count = int(balance * 4)

        preferences: Dict[str, Any] = user_data.get("preferences", {})
        auth: Dict[str, Any] = user_data.get("auth", {})
        timestamps: Dict[str, Any] = auth.get("timestamps", {})
        local_auth: Dict[str, Any] = auth.get("local", {})  # Contains username

    except Exception as e:
        console.print(f"[error]Error fetching or parsing user data:[/error] {e}")
        return {}  # Return empty dict on failure

    # --- Process Raw Data ---
    user_class: str = stats.get("class", "warrior")  # Default class if missing
    if user_class == "wizard":  # Habitica API uses 'wizard', map to 'mage' if desired
        user_class = "mage"

    # Convert last login time
    last_login_utc: Optional[str] = timestamps.get("loggedin")
    last_login_local_str: str = "N/A"
    if last_login_utc:
        try:
            # Use the imported utility function (or fallback)
            last_login_local = convert_to_local_time(last_login_utc)
            # Format consistently, e.g., ISO 8601
            last_login_local_str = last_login_local.isoformat(
                sep=" ", timespec="minutes"
            )
        except Exception as e:
            console.print(
                f"[yellow]Warning:[/yellow] Could not convert last login time '{last_login_utc}': {e}"
            )
            last_login_local_str = (
                f"Error ({last_login_utc})"  # Indicate error but keep original
            )

    # --- Calculate task counts from cats_dict ---
    task_numbers: Dict[str, Any] = {}
    task_categories: Dict[str, Any] = cats_dict.get(
        "tasks", {}
    )  # Safely get tasks dict
    if isinstance(task_categories, dict):
        for category, cat_data in task_categories.items():
            if isinstance(cat_data, dict):  # For todos/dailys with statuses
                total_in_cat = 0
                status_counts = {}
                for status, id_list in cat_data.items():
                    count = len(id_list) if isinstance(id_list, list) else 0
                    status_counts[status] = count
                    total_in_cat += count
                # Store counts per status and optional total
                task_numbers[category] = status_counts
                task_numbers[category][
                    "_total"
                ] = total_in_cat  # Use underscore prefix for clarity
            elif isinstance(cat_data, list):  # For habits/rewards (flat lists)
                task_numbers[category] = len(cat_data)
            else:
                task_numbers[category] = (
                    f"Unknown format ({type(cat_data)})"  # Handle unexpected format
                )
    else:
        console.print(
            "[yellow]Warning:[/yellow] 'cats_dict' missing or has invalid 'tasks' structure. Task counts will be inaccurate."
        )
        # Convert last login time (ensure this logic is present)
    last_login_utc = timestamps.get("loggedin")
    last_login_local_str = "N/A"
    if last_login_utc:
        try:
            last_login_local = convert_to_local_time(last_login_utc)
            last_login_local_str = last_login_local.isoformat()
        except Exception as date_e:
            console.print(
                f"      - [Warning] Error converting last login time: {date_e}"
            )
            last_login_local_str = "(Time Error)"

        # --- START: New Damage Calculation ---
    total_potential_user_damage = 0.0
    total_potential_party_damage = 0.0
    console.print("      - Calculating potential daily damage...")
    try:
        # Get IDs of dailies marked 'due' by TaskProcessor
        # (Status reflects non-completion if task is due)
        due_daily_ids = cats_dict.get("tasks", {}).get("dailys", {}).get("due", [])

        for task_id in due_daily_ids:
            processed_task = processed_tasks_dict.get(task_id)
            if processed_task:
                total_potential_user_damage += processed_task.get("damage_to_user", 0.0)
                total_potential_party_damage += processed_task.get(
                    "damage_to_party", 0.0
                )
    except Exception as sum_e:
        console.print(f"Warning: Error summing damage from processed tasks: {sum_e}")
    # ------------------------------------------

    # --- END: New Damage Calculation ---
    # --- Prepare Final Stats Dictionary ---
    # Use .get() with defaults for all fields to prevent KeyErrors
    quest_info: Dict[str, Any] = party.get("quest", {})  # Safely get quest dict

    output_stats = {
        "username": local_auth.get("username", "N/A"),
        "class": user_class,
        "level": stats.get("lvl", 0),
        "stats": {  # Nested dictionary for core stats
            "str": stats.get("str", 0),
            "int": stats.get("int", 0),
            "con": stats.get("con", 0),
            "per": stats.get("per", 0),
        },
        "hp": stats.get("hp", 0.0),  # Use float for potential decimals
        "maxHealth": stats.get("maxHealth", 0),
        "mp": stats.get("mp", 0.0),  # Use float for potential decimals
        "maxMP": stats.get("maxMP", 0),
        "exp": stats.get("exp", 0.0),  # Use float for potential decimals
        "toNextLevel": stats.get("toNextLevel", 0),
        "gp": stats.get("gp", 0.0),  # Gold can have decimals
        "gems": gems_count,
        "quest_active": quest_info.get("active", False),
        "quest_key": quest_info.get("key"),  # Will be None if no quest or not active
        "sleeping": preferences.get("sleep", False),
        "day_start": preferences.get("dayStart", 0),  # Custom Day Start hour
        "last_login_local": last_login_local_str,
        "task_counts": task_numbers,
        "broken_challenge_tasks": len(
            cats_dict.get("broken", [])
        ),  # Count of broken task IDs
        "joined_challenges_count": len(
            cats_dict.get("challenge", [])
        ),  # Count of unique challenge IDs tasks belong to
        "tags_in_use_count": len(
            cats_dict.get("tags", [])
        ),  # Count of unique tag IDs used across tasks
        "potential_daily_damage_user": round(total_potential_user_damage, 2),
        "potential_daily_damage_party": round(
            total_potential_party_damage, 2
        ),  # Add any other relevant stats extracted from user_data if needed
    }

    return output_stats


# MARK: - EXAMPLE USAGE (Commented out)
# Example of how this function would be called from a main script or CLI app
#
# from pixabit.api import HabiticaAPI
# from pixabit.processing import TaskProcessor # Assuming TaskProcessor is defined elsewhere
# from pixabit.processing import get_user_stats # Import the function itself
#
# if __name__ == "__main__": # Example guard
#     try:
#         console.print("--- Running Example: Get User Stats ---")
#         api = HabiticaAPI()
#
#         # First, run the task processor to get the 'cats' dictionary
#         # This part needs the TaskProcessor class implementation
#         # processor = TaskProcessor(api_client=api)
#         # processed_results = processor.process_and_categorize_all()
#
#         # Placeholder for processed_results if TaskProcessor is not run here
#         processed_results = {
#             "data": {}, # Placeholder for processed task data
#             "cats": { # Example 'cats' structure needed by get_user_stats
#                 "tasks": {
#                     "habits": [], "dailys": {"due":[], "notDue":[]},
#                     "todos": {"due":[], "notDue":[]}, "rewards": []
#                 },
#                 "broken": [], "tags": [], "challenge": []
#             }
#         }
#         console.print("Note: Using placeholder task categorization data for stats calculation.")
#
#         if processed_results and 'cats' in processed_results:
#             # Call get_user_stats with the API client and the categories
#             user_stats = get_user_stats(api_client=api, cats_dict=processed_results['cats'])
