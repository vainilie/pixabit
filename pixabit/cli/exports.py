# pixabit/cli/exports.py (Utility)

# SECTION: MODULE DOCSTRING
"""Provides functions for exporting various Habitica data structures to JSON files (Sync).

Includes functions to fetch specific data types (tags, raw tasks, full user data)
using the synchronous HabiticaAPI client and save them into well-formatted JSON files.
Uses the shared `save_json` utility. These functions might be adaptable for async
use within the TUI by wrapping them with `run_in_thread`.
"""

# SECTION: IMPORTS
from pathlib import Path
from typing import Any, Dict, List, Union  # Keep Dict/List

import emoji_data_python
import requests  # For API error handling

# Local Imports (Adjust path based on structure)
try:
    from ..utils.display import console, print  # Use ..
    from ..utils.save_json import save_json  # Use ..
    from .api import HabiticaAPI  # Import sync API
except ImportError:
    # Fallback imports
    import builtins

    print = builtins.print

    class DummyConsole:
        def print(self, *args: Any, **kwargs: Any) -> None:
            builtins.print(*args)

        def log(self, *args: Any, **kwargs: Any) -> None:
            builtins.print("LOG:", *args)

    console = DummyConsole()

    class HabiticaAPI:
        pass  # type: ignore

    def save_json(data: Any, filepath: Any) -> bool:
        return False

    print("Warning: Using fallback imports in cli/exports.py")

# SECTION: EXPORT FUNCTIONS (Sync)

# --- Tag Exports ---


# FUNC: save_tags_into_json
def save_tags_into_json(
    api_client: HabiticaAPI, output_filename: Union[str, Path] = "tags_all.json"
) -> None:
    """Fetches all user tags sync and saves categorized (challenge/personal) to JSON."""
    filepath = Path(output_filename)
    console.print(
        f"🏷️ Fetching and saving tags to [file]'{filepath}'[/] (Sync)..."
    )
    try:
        tags_list = api_client.get_tags()  # Sync call
        if not isinstance(tags_list, list):
            console.print(
                f"API Error: Expected list of tags, got {type(tags_list)}.",
                style="error",
            )
            return
        if not tags_list:
            console.print(
                "ℹ️ No tags found. Saving empty structure.", style="info"
            )
            save_json({"challenge": {}, "personal": {}}, filepath)
            return

        category: Dict[str, Dict[str, str]] = {"challenge": {}, "personal": {}}
        processed_count, skipped_count = 0, 0
        for tag in tags_list:
            if not isinstance(tag, dict):
                skipped_count += 1
                continue
            tag_id = tag.get("id")
            if not tag_id:
                skipped_count += 1
                continue
            tag_name = tag.get("name", f"Unnamed_{tag_id[:6]}")
            # API 'challenge' key can be challenge ID string or boolean - normalize
            is_challenge_tag = bool(tag.get("challenge"))
            category["challenge" if is_challenge_tag else "personal"][
                tag_id
            ] = tag_name
            processed_count += 1

        console.print(
            f"Processed {processed_count} tags ({skipped_count} skipped)."
        )
        save_json(data=category, filepath=filepath)
    except requests.exceptions.RequestException as api_err:
        console.print(f"API Error fetching tags: {api_err}", style="error")
    except Exception as e:
        console.print(f"Unexpected error saving tags: {e}", style="error")


# --- Raw Task Exports ---


# FUNC: save_tasks_without_proccessing (Note: Keep typo if referenced elsewhere)
def save_tasks_without_proccessing(
    api_client: HabiticaAPI,
    output_filename: Union[str, Path] = "tasks_raw.json",
) -> None:
    """Fetches all raw tasks sync, processes emojis, saves to JSON."""
    filepath = Path(output_filename)
    console.print(
        f"📝 Fetching raw tasks (emoji processing) -> [file]'{filepath}'[/] (Sync)..."
    )
    try:
        raw_tasks = api_client.get_tasks()  # Sync call
        if not isinstance(raw_tasks, list):
            console.print(
                f"API Error: Expected list of tasks, got {type(raw_tasks)}.",
                style="error",
            )
            return

        console.print(f"Fetched {len(raw_tasks)} tasks. Processing emojis...")
        processed_count, skipped_count = 0, 0
        tasks_to_save: List[Dict[str, Any]] = []
        for task in raw_tasks:
            if not isinstance(task, dict):
                skipped_count += 1
                continue
            task_copy = task.copy()  # Avoid modifying original list if reused
            # Process text and notes for emojis
            if "text" in task_copy and task_copy["text"]:
                task_copy["text"] = emoji_data_python.replace_colons(
                    str(task_copy["text"])
                )
            if "notes" in task_copy and task_copy["notes"]:
                task_copy["notes"] = emoji_data_python.replace_colons(
                    str(task_copy["notes"])
                )
            # Process checklist items too
            if "checklist" in task_copy and isinstance(
                task_copy["checklist"], list
            ):
                for item in task_copy["checklist"]:
                    if (
                        isinstance(item, dict)
                        and "text" in item
                        and item["text"]
                    ):
                        item["text"] = emoji_data_python.replace_colons(
                            str(item["text"])
                        )

            tasks_to_save.append(task_copy)
            processed_count += 1

        console.print(
            f"Emoji processing complete for {processed_count} tasks ({skipped_count} skipped)."
        )
        save_json(tasks_to_save, filepath)
    except requests.exceptions.RequestException as api_err:
        console.print(f"API Error fetching tasks: {api_err}", style="error")
    except Exception as e:
        console.print(f"Unexpected error saving raw tasks: {e}", style="error")


# --- Processed Task Exports ---


# FUNC: save_processed_tasks_into_json
def save_processed_tasks_into_json(
    processed_tasks_dict: Dict[
        str, Dict[str, Any]
    ],  # Expects dict of processed task dicts
    output_filename: Union[str, Path] = "tasks_processed.json",
) -> None:
    """Saves an already processed task dictionary (from sync processor) to JSON."""
    filepath = Path(output_filename)
    console.print(
        f"💾 Saving processed tasks dictionary -> [file]'{filepath}'[/]..."
    )
    if not isinstance(processed_tasks_dict, dict):
        console.print(
            f"Error: Invalid input (must be dict), got {type(processed_tasks_dict)}.",
            style="error",
        )
        return
    if not processed_tasks_dict:
        console.print(
            "No processed tasks data provided. Saving empty file.", style="info"
        )
        save_json({}, filepath)
        return
    save_json(processed_tasks_dict, filepath)


# --- User Data Exports ---


# FUNC: save_all_userdata_into_json
def save_all_userdata_into_json(
    api_client: HabiticaAPI,
    output_filename: Union[str, Path] = "user_data_full.json",
) -> None:
    """Fetches the full user data object sync (/user endpoint) and saves it to JSON."""
    filepath = Path(output_filename)
    console.print(
        f"👤 Fetching full user data -> [file]'{filepath}'[/] (Sync)..."
    )
    try:
        user_data_content = api_client.get_user_data()  # Sync call
        if user_data_content is None:
            console.print(
                "Error: Failed to fetch user data from API.", style="error"
            )
            return
        if not isinstance(user_data_content, dict):
            console.print(
                f"Error: Expected dict for user data, got {type(user_data_content)}.",
                style="error",
            )
            return
        save_json(user_data_content, filepath)
    except requests.exceptions.RequestException as api_err:
        console.print(f"API Error fetching user data: {api_err}", style="error")
    except Exception as e:
        console.print(f"Unexpected error saving user data: {e}", style="error")
