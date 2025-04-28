# pixabit/tui/task_processor.py

# SECTION: MODULE DOCSTRING
"""Processes raw Habitica task data into specific data model objects.

Populates calculated fields (status, damage, tag names), and categorizes tasks based
on type and status. Also includes the function to calculate aggregate user statistics
using the processed task data and user context.
"""

# SECTION: IMPORTS
import logging
import math
from typing import Any, Dict, List, Optional, Type  # Keep Dict/List, add Type

from rich.logging import RichHandler
from textual import log

from pixabit.helpers._rich import console

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

# Local Imports
try:
    # Import the data models
    # Import utilities
    # Import the GameContent manager for context data

    from pixabit.helpers._date_helper import (
        convert_timestamp_to_utc,
    )  # Only used by get_user_stats here
    from pixabit.helpers._rich import console, print
    from pixabit.models.task import (
        ChallengeData,
        ChecklistItem,
        Daily,
        Habit,
        Reward,
        Task,
        Todo,
    )
    from pixabit.tui.game_content import GameContent
except ImportError:
    # Fallback for standalone testing or import issues

    # Define dummy models/classes if imports fail
    class Task:
        pass  # type: ignore

    class Habit(Task):
        pass  # type: ignore

    class Daily(Task):
        pass  # type: ignore

    class Todo(Task):
        pass  # type: ignore

    class Reward(Task):
        pass  # type: ignore

    class ChecklistItem:
        pass  # type: ignore

    class ChallengeData:
        pass  # type: ignore

    class GameContent:  # type: ignore
        def get_gear_data(self) -> Dict:
            return {}

        def get_quest_data(self) -> Dict:
            return {}

    def convert_timestamp_to_utc(ts: Any) -> Any:
        return None

    log.warning(
        "Warning: Could not import models/GameContent/utils in data_processor.py. Using fallbacks."
    )


# SECTION: TaskProcessor Class
# KLASS: TaskProcessor
class TaskProcessor:
    """Processes raw task dictionaries into Task data model objects.

    Adds calculated fields like status, value color, tag names, and potential damage.
    Requires pre-fetched context data (user, party, tags, content) for accuracy.
    """

    # Mapping from API task type string to the corresponding Task subclass constructor
    _TASK_TYPE_MAP: dict[str, Type[Task]] = {
        "habit": Habit,
        "daily": Daily,
        "todo": Todo,
        "reward": Reward,
    }

    # FUNC: __init__
    def __init__(
        self,
        user_data: dict[str, Any],
        party_data: dict[str, Any] | None,
        all_tags_list: list[dict[str, Any]],
        # Accept pre-fetched dicts instead of the manager
        gear_data_lookup: dict[str, Any],
        quests_data_lookup: dict[str, Any],
    ):
        """Initializes TaskProcessor with necessary context data.

        Args:
            user_data: Raw user data dictionary from API.
            party_data: Raw party data dictionary from API, or None.
            all_tags_list: Raw list of tag dictionaries from API.
            gear_data_lookup: Pre-fetched 'gear.flat' dictionary from game content.
            quests_data_lookup: Pre-fetched 'quests' dictionary from game content.
        """
        self.console = console
        log.info("Initializing TaskProcessor...")

        # Validate critical context
        if not isinstance(user_data, dict) or not user_data:
            raise ValueError("TaskProcessor requires valid user_data.")
        # Basic validation for lookups
        if not isinstance(gear_data_lookup, dict):
            log.warning("Warning: gear_data_lookup is not a dict.")
        if not isinstance(quests_data_lookup, dict):
            log.warning("Warning: quests_data_lookup is not a dict.")

        # Store context needed for processing
        self.user_data = user_data
        self.party_data = party_data if isinstance(party_data, dict) else {}
        self.all_tags_list = (
            all_tags_list if isinstance(all_tags_list, list) else []
        )

        # Store the pre-fetched lookup dictionaries directly
        self.gear_stats_lookup = gear_data_lookup
        self.tags_lookup = self._prepare_tags_lookup(self.all_tags_list)
        self.quests_lookup = quests_data_lookup

        # Calculate and store context values needed internally for processing tasks
        self.user_con: float = 0.0
        self.user_stealth: int = 0
        self.is_sleeping: bool = False
        self.is_on_boss_quest: bool = False
        self.boss_str: float = 0.0
        self._calculate_user_context()  # Calculate based on stored raw data

        log.info("TaskProcessor Context Initialized.")

    # FUNC: _prepare_tags_lookup
    def _prepare_tags_lookup(
        self, tags_list: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Creates a tag ID -> tag name lookup dictionary."""
        if not tags_list:
            return {}
        lookup = {
            tag["id"]: tag.get("name", f"ID:{tag['id'][:6]}")
            for tag in tags_list
            if isinstance(tag, dict) and "id" in tag
        }  # Use ID prefix fallback
        # log.info(f"Prepared lookup for {len(lookup)} tags.")
        return lookup

    # FUNC: _calculate_user_context
    def _calculate_user_context(self) -> None:
        """Calculates effective CON, stealth, sleep, quest status from instance data."""
        # log.info("Calculating user context...")
        try:
            # --- User Stats Context ---
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

            if self.gear_stats_lookup:  # Ensure gear lookup is available
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

            # --- Party/Quest Context ---
            quest_info = (
                self.party_data.get("quest", {}) if self.party_data else {}
            )
            self.is_on_boss_quest = False
            self.boss_str = 0.0
            if isinstance(quest_info, dict) and quest_info.get("active"):
                quest_key = quest_info.get("key")
                if quest_key and self.quests_lookup:
                    # Look up quest details in the content cache
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
                                self.boss_str = (
                                    0.0  # Handle invalid strength value
                                )
            # Log calculated context
            # log.subtle(f"Context: CON={self.user_con:.1f}, Stealth={self.user_stealth}, Sleep={self.is_sleeping}, BossQuest={self.is_on_boss_quest}, BossStr={self.boss_str:.1f}")

        except Exception as e:
            log.error(
                f"[red]Error calculating user/party context:[/red] {e}. Using defaults."
            )
            # Reset defaults on error
            self.user_con, self.user_stealth, self.is_sleeping = 0.0, 0, False
            self.is_on_boss_quest, self.boss_str = False, 0.0

    # FUNC: _value_color
    def _value_color(self, value: float | None) -> str:
        """Determines a semantic style name based on task value."""
        if value is None:
            return "neutral"
        # Use the same color mapping as before
        if value > 15:
            return "rosewater"
        elif value > 8:
            return "flamingo"
        elif value > 1:
            return "peach"
        elif value >= 0:
            return "text"  # Default text color for slightly positive/neutral
        elif value > -9:
            return "lavender"
        elif value > -16:
            return "rp_iris"
        else:
            return "red"  # Very negative

    # FUNC: _calculate_checklist_done
    def _calculate_checklist_done(
        self, checklist: list[ChecklistItem]
    ) -> float:
        """Calculates proportion (0.0-1.0) of checklist items done."""
        # Expects list of ChecklistItem objects
        if not checklist or not isinstance(checklist, list):
            return 1.0  # Treat no checklist as fully "done" for mitigation
        try:
            completed = sum(
                1
                for item in checklist
                if isinstance(item, ChecklistItem) and item.completed
            )
            total = len(checklist)
            return (
                completed / total if total > 0 else 1.0
            )  # Avoid division by zero
        except Exception as e:
            log.warning(f"Error calculating checklist progress: {e}")
            return 1.0  # Default to max mitigation on error

    # FUNC: _create_task_object
    def _create_task_object(self, task_data: dict[str, Any]) -> Task | None:
        """Factory method to create the appropriate Task subclass instance."""
        task_type = task_data.get("type")
        task_class = self._TASK_TYPE_MAP.get(task_type) if task_type else None

        if task_class:
            try:
                return task_class(task_data)  # Instantiate specific subclass
            except (TypeError, ValueError) as e:  # Catch model init errors
                log.error(
                    f"Error instantiating {task_type} task {task_data.get('_id', 'N/A')}: {e}",
                )
                return None
            except Exception as e:  # Catch unexpected errors
                log.error(
                    f"Unexpected error instantiating {task_type} task {task_data.get('_id', 'N/A')}: {e}",
                )
                return None
        else:
            # Handle unknown type - create base Task object if possible
            log.warning(
                f"Unknown task type '{task_type}' for task {task_data.get('_id', 'N/A')}. Creating base Task.",
            )
            try:
                # Need to ensure base Task init handles missing ID gracefully or check here
                if "_id" not in task_data:
                    return None
                base_task = Task(task_data)
                base_task.type = task_type  # Store original type if known
                return base_task
            except (TypeError, ValueError) as e:
                log.error(
                    f"Error instantiating base Task for {task_data.get('_id', 'N/A')}: {e}",
                )
                return None
            except Exception as e:
                log.error(
                    f"Unexpected error instantiating base Task for {task_data.get('_id', 'N/A')}: {e}",
                )
                return None

    # FUNC: _process_and_calculate_task
    def _process_and_calculate_task(self, task_instance: Task) -> None:
        """Performs post-instantiation processing on a Task object.

        Calculates status, value color, assigns tag names, and calculates
        potential damage (for Dailies). Modifies the task_instance directly.
        """
        # 1. Assign Tag Names using lookup
        task_instance.tag_names = [
            self.tags_lookup.get(tag_id, f"ID:{tag_id}")
            for tag_id in task_instance.tags
        ]

        # 2. Determine Value Color
        task_instance.value_color = self._value_color(task_instance.value)

        # 3. Status Calculation & Damage (Type Specific Logic)
        dmg_user: float | None = None
        dmg_party: float | None = None
        calculated_status = "unknown"  # Default status

        if isinstance(task_instance, Daily):
            # Calculate Daily status
            status = "grey"  # Default if not due
            if task_instance.is_due:
                status = "success" if task_instance.completed else "due"
            calculated_status = status

            # Calculate Damage ONLY if due, not completed, not sleeping, not stealthed
            if (
                task_instance.is_due
                and not task_instance.completed
                and not self.is_sleeping
                and self.user_stealth <= 0
            ):
                try:
                    task_value = task_instance.value
                    checklist = (
                        task_instance.checklist
                    )  # List of ChecklistItem objects
                    priority_val = task_instance.priority

                    # Habitica Damage Formula components:
                    v_min, v_max = -47.27, 21.27
                    clamped_value = max(v_min, min(task_value, v_max))
                    base_delta = abs(math.pow(0.9747, clamped_value))
                    checklist_mitigation = 1.0 - self._calculate_checklist_done(
                        checklist
                    )
                    effective_delta = base_delta * checklist_mitigation
                    con_mitigation = max(0.1, 1.0 - (self.user_con / 250.0))
                    prio_map = {0.1: 0.1, 1.0: 1.0, 1.5: 1.5, 2.0: 2.0}
                    priority_multiplier = prio_map.get(priority_val, 1.0)

                    # Calculate User HP Damage
                    hp_mod = (
                        effective_delta
                        * con_mitigation
                        * priority_multiplier
                        * 2.0
                    )
                    dmg_user_calc = round(hp_mod, 1)
                    dmg_user = (
                        dmg_user_calc if dmg_user_calc > 0 else None
                    )  # Store None if zero

                    # Calculate Party Damage (Boss Quest Only)
                    if self.is_on_boss_quest and self.boss_str > 0:
                        # Boss delta might adjust slightly for trivial tasks
                        boss_delta = (
                            effective_delta * priority_multiplier
                            if priority_multiplier < 1.0
                            else effective_delta
                        )
                        dmg_party_calc = round(boss_delta * self.boss_str, 1)
                        dmg_party = (
                            dmg_party_calc if dmg_party_calc > 0 else None
                        )  # Store None if zero

                except Exception as e_dmg:
                    log.error(
                        f"[red]Error calculating damage for Daily {task_instance.id}:[/red] {e_dmg}"
                    )
                    # Leave dmg_user and dmg_party as None on error

        elif isinstance(task_instance, Todo):
            # Calculate Todo status
            status = "grey"  # Default if no due date
            if task_instance.completed:
                status = "done"  # Mark completed Todos distinctly
            elif task_instance.due_date:  # Has a due date
                # Use the is_past_due property for check
                status = "red" if task_instance.is_past_due else "due"
            calculated_status = status

        elif isinstance(task_instance, Habit):
            calculated_status = "habit"  # Simple status for habits
        elif isinstance(task_instance, Reward):
            calculated_status = "reward"  # Simple status for rewards

        # 4. Assign Calculated Status and Damage to Task Object
        task_instance._status = calculated_status
        task_instance.damage_user = dmg_user
        task_instance.damage_party = dmg_party

        # 5. Emoji processing is now handled in Task model __init__.

    # FUNC: process_and_categorize_all
    def process_and_categorize_all(
        self, raw_task_list: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Processes a list of raw task data into Task objects and categorizes them.

        Args:
            raw_task_list: The list of raw task dictionaries from the API.

        Returns:
            A dictionary containing:
            - 'data': dict[str, Task] - Processed Task objects keyed by ID.
            - 'cats': dict[str, Any] - Categorized task IDs and metadata.
        """
        tasks_dict: dict[str, Task] = {}  # Store {task_id: TaskObject}
        # Initialize categories structure
        cats_dict: dict[str, Any] = {
            "tasks": {
                "habits": [],
                "todos": {
                    "due": [],
                    "grey": [],
                    "red": [],
                    "done": [],
                },  # Added done
                "dailys": {
                    "success": [],
                    "due": [],
                    "grey": [],
                },  # Use 'success' for done
                "rewards": [],
            },
            "tags": set(),  # Use set for unique tags
            "broken": [],  # List of IDs of broken tasks
            "challenge": set(),  # Use set for unique challenge IDs tasks belong to
        }

        if not isinstance(raw_task_list, list):
            log.error("[red]Invalid raw_task_list provided to processor.[/red]")
            # Return empty structure on invalid input
            return {"data": {}, "cats": cats_dict}

        log.info(
            f"Processing {len(raw_task_list)} raw tasks into objects...",
        )
        processed_count = 0
        skipped_count = 0

        for task_data in raw_task_list:
            if not isinstance(task_data, dict):
                skipped_count += 1
                continue

            # 1. Create Task object instance (handles subclassing)
            task_instance = self._create_task_object(task_data)
            if not task_instance or not task_instance.id:
                skipped_count += 1
                continue  # Skip if object creation failed or ID missing

            # 2. Perform calculations and update the instance directly
            self._process_and_calculate_task(task_instance)

            # 3. Store processed object
            tasks_dict[task_instance.id] = task_instance
            processed_count += 1

            # 4. Categorization using the processed task_instance
            cats_dict["tags"].update(task_instance.tags)  # Add all raw tag IDs
            # Check challenge info on the Task object
            if task_instance.challenge and task_instance.challenge.id:
                cats_dict["challenge"].add(task_instance.challenge.id)
                if task_instance.challenge.is_broken:
                    cats_dict["broken"].append(task_instance.id)

            task_type = task_instance.type
            status = task_instance._status  # Use the calculated status

            # Append ID to the correct category/status list
            if task_type == "habit":
                cats_dict["tasks"]["habits"].append(task_instance.id)
            elif task_type == "reward":
                cats_dict["tasks"]["rewards"].append(task_instance.id)
            elif task_type == "todo" and status in cats_dict["tasks"]["todos"]:
                cats_dict["tasks"]["todos"][status].append(task_instance.id)
            elif (
                task_type == "daily" and status in cats_dict["tasks"]["dailys"]
            ):
                cats_dict["tasks"]["dailys"][status].append(task_instance.id)
            # else: Status might be 'unknown' or category doesn't exist, ignore for categorization

        # Finalize categories: convert sets to sorted lists
        cats_dict["tags"] = sorted(list(cats_dict["tags"]))
        cats_dict["challenge"] = sorted(list(cats_dict["challenge"]))

        log.info(
            f"Task processing complete. Processed: {processed_count}, Skipped: {skipped_count}",
        )
        return {"data": tasks_dict, "cats": cats_dict}


# SECTION: User Stats Function
# FUNC: get_user_stats
def get_user_stats(
    cats_dict: dict[str, Any],  # Expects 'cats' dictionary from TaskProcessor
    processed_tasks_dict: dict[
        str, Task
    ],  # Expects 'data' dictionary (Task objects)
    user_data: dict[str, Any],  # Expects raw user data dict
) -> dict[str, Any] | None:
    """Generates user statistics dict using categorized tasks and raw user data.

    Args:
        cats_dict: The 'cats' dictionary from TaskProcessor results.
        processed_tasks_dict: The 'data' dictionary from TaskProcessor results (Task objects).
        user_data: The raw user data dictionary from the API.

    Returns:
        A dictionary containing combined user/task statistics, or None on critical failure.
    """
    # console.log("Calculating user stats from processed data...", style="info")
    # Validate inputs
    if not isinstance(user_data, dict) or not user_data:
        log.error(
            "[red]Cannot calculate stats: Valid user_data required.[/red]"
        )
        return None
    if not isinstance(cats_dict, dict):
        log.error(
            "[red]Cannot calculate stats: Valid cats_dict required.[/red]"
        )
        return None
    if not isinstance(processed_tasks_dict, dict):
        log.error(
            "[red]Cannot calculate stats: Valid processed_tasks_dict required.[/red]"
        )
        return None

    try:
        # --- Extract from User Data ---
        stats = user_data.get("stats", {})
        party = user_data.get("party", {})
        prefs = user_data.get("preferences", {})
        auth = user_data.get("auth", {})
        ts = auth.get("timestamps", {})
        local_auth = auth.get("local", {})
        balance = user_data.get("balance", 0.0)
        gems = int(balance * 4) if balance > 0 else 0
        u_class_raw = stats.get("class", "warrior")
        u_class = (
            "mage" if u_class_raw == "wizard" else u_class_raw
        )  # Normalize wizard -> mage?
        last_login_utc_str = ts.get("loggedin")
        last_login_local_str = "N/A"
        # Use utility for local time conversion
        # if last_login_utc_str and (local_dt := convert_to_local_time(last_login_utc_str)):
        #      last_login_local_str = local_dt.isoformat(sep=" ", timespec="minutes")
        # elif last_login_utc_str:
        #      last_login_local_str = f"Error ({last_login_utc_str})"
        quest = party.get("quest", {}) if isinstance(party, dict) else {}

        # --- Calculate Task Counts from cats_dict ---
        task_counts: dict[str, Any] = {}
        task_cats_data = cats_dict.get("tasks", {})
        if isinstance(task_cats_data, dict):
            for category, cat_data in task_cats_data.items():
                if category not in ["habits", "dailys", "todos", "rewards"]:
                    continue
                if isinstance(
                    cat_data, dict
                ):  # dailys/todos with status sub-keys
                    status_counts = {
                        k: len(v)
                        for k, v in cat_data.items()
                        if isinstance(v, list)
                    }
                    status_counts["_total"] = sum(status_counts.values())
                    task_counts[category] = status_counts
                elif isinstance(
                    cat_data, list
                ):  # habits/rewards (just a list of IDs)
                    task_counts[category] = len(cat_data)
        else:
            log.warning(
                "[warning]Invalid 'tasks' structure in cats_dict during stats calculation.[/warning]"
            )

        # --- Calculate Total Damage (Sums pre-calculated values from Task objects) ---
        dmg_user_total, dmg_party_total = 0.0, 0.0
        # Get IDs of dailies currently marked as 'due'
        due_daily_ids = (
            cats_dict.get("tasks", {}).get("dailys", {}).get("due", [])
        )
        if isinstance(due_daily_ids, list):
            for task_id in due_daily_ids:
                task_obj = processed_tasks_dict.get(task_id)
                # Check if it's a Task object and has damage attributes
                if isinstance(task_obj, Task):
                    dmg_user_total += task_obj.damage_user or 0.0
                    dmg_party_total += task_obj.damage_party or 0.0

        # --- Assemble Output Dict ---
        output_stats = {
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
            "stats": {  # Base allocated points
                "str": int(stats.get("str", 0)),
                "int": int(stats.get("int", 0)),
                "con": int(stats.get("con", 0)),
                "per": int(stats.get("per", 0)),
            },
            "sleeping": bool(prefs.get("sleep", False)),
            "day_start": int(prefs.get("dayStart", 0)),
            # "last_login_local": last_login_local_str, # Local time formatted string
            "quest_active": bool(quest.get("active", False)),
            "quest_key": quest.get("key"),  # Quest key string
            "task_counts": task_counts,  # Nested dict of counts by type/status
            "broken_challenge_tasks": len(cats_dict.get("broken", [])),
            "joined_challenges_count": len(
                cats_dict.get("challenge", [])
            ),  # Count of unique challenge IDs
            "tags_in_use_count": len(
                cats_dict.get("tags", [])
            ),  # Count of unique tag IDs used
            "potential_daily_damage_user": round(dmg_user_total, 2),
            "potential_daily_damage_party": round(dmg_party_total, 2),
        }
        # console.log("User stats calculation complete.", style="success")
        return output_stats

    except Exception as e_stat:
        log.error(f"[red]Error calculating user stats:[/red] {e_stat}")
        log.exception(show_locals=False)
        return None  # Return None on critical failure
