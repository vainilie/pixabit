# pixabit/processing.py

# --- Standard Imports ---
import time  # Potentially needed if adding delays or logging timestamps
from typing import Any, Dict, List, Optional

# --- Third-party Imports ---
import emoji_data_python

from .api import HabiticaAPI
from .utils.dates import convert_to_local_time, is_date_passed
from .utils.display import console, print
from .utils.save_file import save_file


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
        print("Initializing TaskProcessor...")
        self.api_client = api_client
        print("Fetching tags for lookup...")
        self.tags_lookup = self._fetch_and_prepare_tags()
        if not self.tags_lookup:
            print(
                "Warning: Tag lookup is empty. Tag names may not be processed correctly."
            )
        else:
            print(f"Fetched {len(self.tags_lookup)} tags.")

    # --- Private Helper Methods ---
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
                tag["id"]: tag.get("name", tag["id"])  # Use ID as fallback name
                for tag in tags_list
                if "id" in tag  # Only include tags that have an ID
            }
        except Exception as e:
            print(f"Error fetching or processing tags: {e}")
            return {}

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
            print(
                f"Warning: Task {task_data.get('id', 'N/A')} has non-list tags: {tag_ids}"
            )
            return []  # Handle unexpected type
        # Use tags_lookup, fallback to tag_id if name not found
        return [self.tags_lookup.get(tag_id, tag_id) for tag_id in tag_ids]

    # --- Private Task Type Processors ---
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
                print(
                    f"Error checking To-Do date ({deadline_str}) for task {task_data.get('id', 'N/A')}: {e}. Status set to 'grey'."
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

    # --- Public Processing Methods ---
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
            print(
                f"Warning: Skipping invalid task data (missing ID or not a dict): {task_data}"
            )
            return None

        task_id = task_data["id"]  # ID is confirmed to exist here
        task_type = task_data.get("type")

        # --- Process common fields safely ---
        challenge_info = task_data.get(
            "challenge", {}
        )  # Default to empty dict if missing
        if not isinstance(challenge_info, dict):
            print(
                f"Warning: Task {task_id} has non-dict challenge info: {challenge_info}"
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
            print(f"Warning: Unknown task type '{task_type}' for task ID {task_id}")
            # Add minimal common fields if type is unknown?
            processed["value"] = task_data.get("value", 0.0)
            processed["value_color"] = self._value_color(processed["value"])

        processed.update(type_specific_data)
        return processed

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
        print("Fetching all tasks via API client...")
        try:
            all_tasks_raw = self.api_client.get_tasks()
        except Exception as e:
            print(f"Fatal Error: Could not fetch tasks: {e}")
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

        print(f"Processing {len(all_tasks_raw)} tasks...")
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
                    print(
                        f"Warning: Could not categorize task {task_id} - invalid type/status ({type_key}/{status})"
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

        print("Processing complete.")
        return {"data": tasks_dict, "cats": cats_dict}

    # --- File Saving ---
    def save_processed_data(self, processed_data: Dict):
        """
        Saves the processed task data and category dictionaries to separate files.

        Uses the `save_file` utility function. Expects the input dictionary
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
            print("Error: No valid processed data provided to save.")
            return
        try:
            print("Saving processed data...")
            # Use the imported save_file function
            # Save main task data (ID -> processed task)
            save_file(
                processed_data["data"], "tasks_data", "_processed"
            )  # e.g., tasks_data_processed.json
            # Save category data (lists/dicts of task IDs)
            save_file(
                processed_data["cats"], "tasks_cats", "_processed"
            )  # e.g., tasks_cats_processed.json
            print("Processed data saved successfully.")
        except Exception as e:
            print(f"Error saving processed files: {e}")


# ==============================================================================
# Example Usage (Intended for main script/CLI)
# ==============================================================================
# from pixabit.api import HabiticaAPI
# from pixabit.processing import TaskProcessor
# # from pixabit.get_user_stats import get_user_stats # If separate
#
# if __name__ == "__main__": # Example guard
#     try:
#         print("--- Starting Pixabit Processing ---")
#         # Assume API client is configured via environment variables or .env file
#         api = HabiticaAPI()
#         processor = TaskProcessor(api_client=api)
#
#         print("\nProcessing and categorizing all tasks...")
#         processed_results = processor.process_and_categorize_all()
#
#         if processed_results:
#             processor.save_processed_data(processed_results)
#
#             # Example: Calculate stats if needed (assuming get_user_stats exists)
#             # if 'cats' in processed_results:
#             #      user_stats = get_user_stats(api_client=api, cats_dict=processed_results['cats'])
#             #      print("\n--- User Stats ---")
#             #      import json
#             #      print(json.dumps(user_stats, indent=2))
#             #      # Save stats if needed
#             #      # from pixabit.utils.save_file import save_file
#             #      # save_file(user_stats, "user_stats", "_calculated")
#             # else:
#             #      print("Skipping user stats calculation: 'cats' data missing.")
#         else:
#              print("Processing failed, no results to save or analyze.")
#
#         print("\n--- Pixabit Processing Finished ---")
#
#     except Exception as e:
#         print(f"\n--- An error occurred in the main processing script ---")
#         print(f"{type(e).__name__}: {e}")
#         # Optionally re-raise or log traceback for debugging
#         # import traceback
#         # traceback.print_exc()

# User Stats ───────────────────────────────────────────────────────────────


def get_user_stats(
    api_client: HabiticaAPI, cats_dict: Dict[str, Any]
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
    print("Fetching user data for stats...")
    output_stats: Dict[str, Any] = {}  # Initialize empty dict

    try:
        # Fetch user data including stats, party, preferences, auth timestamps
        user_data = api_client.get_user_data()  # Fetches /user endpoint data
        if not isinstance(user_data, dict) or not user_data:  # More robust check
            print(
                "[bold red]Error:[/bold red] Failed to fetch valid user data from API."
            )
            return {}  # Return empty dict on failure

        # --- Safely extract data from nested dictionaries ---
        stats: Dict[str, Any] = user_data.get("stats", {})
        party: Dict[str, Any] = user_data.get("party", {})
        preferences: Dict[str, Any] = user_data.get("preferences", {})
        auth: Dict[str, Any] = user_data.get("auth", {})
        timestamps: Dict[str, Any] = auth.get("timestamps", {})
        local_auth: Dict[str, Any] = auth.get("local", {})  # Contains username

    except Exception as e:
        print(f"[bold red]Error fetching or parsing user data:[/bold red] {e}")
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
            print(
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
        print(
            "[yellow]Warning:[/yellow] 'cats_dict' missing or has invalid 'tasks' structure. Task counts will be inaccurate."
        )

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
        # Add any other relevant stats extracted from user_data if needed
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
#         print("--- Running Example: Get User Stats ---")
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
#         print("Note: Using placeholder task categorization data for stats calculation.")
#
#         if processed_results and 'cats' in processed_results:
#             # Call get_user_stats with the API client and the categories
#             user_stats = get_user_stats(api_client=api, cats_dict=processed_results['cats'])
