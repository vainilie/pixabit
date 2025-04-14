# pixabit/exports.py
# MARK: - MODULE DOCSTRING
"""Provides functions for exporting various Habitica data structures to JSON files.

Includes functions to fetch specific data types (tags, raw tasks, full user data)
using the HabiticaAPI client and save them into well-formatted JSON files.
Uses the shared `save_json` utility.
"""

# MARK: - IMPORTS
from pathlib import Path
from typing import Any, Dict, Union

import emoji_data_python
import requests  # For API error handling

# Local Imports
from .api import HabiticaAPI
from .utils.display import console  # Use themed display
from .utils.save_json import save_json  # Use shared save utility

# MARK: - EXPORT FUNCTIONS


# --- Tag Exports ---
# & - def save_tags_into_json(...)
def save_tags_into_json(
    api_client: HabiticaAPI, output_filename: Union[str, Path] = "tags_all.json"
) -> None:
    """Fetches all user tags and saves categorized (challenge/personal) to JSON."""
    filepath = Path(output_filename)  # Ensure Path object
    console.print(f"🏷️ Fetching and saving tags to [file]'{filepath}'[/]...")
    try:
        tags_list = api_client.get_tags()
        if not isinstance(tags_list, list):
            console.print(
                f"API Error: Expected list of tags, got {type(tags_list)}.", style="error"
            )
            return
        if not tags_list:
            console.print("ℹ️ No tags found in Habitica account.", style="info")
            save_json({"challenge": {}, "personal": {}}, filepath)  # Save empty structure
            return

        category: Dict[str, Dict[str, str]] = {"challenge": {}, "personal": {}}
        processed_count, skipped_count = 0, 0
        for tag in tags_list:
            if not isinstance(tag, dict):
                console.print(f"Skipping invalid item in tags list: {tag}", style="warning")
                skipped_count += 1
                continue
            tag_id = tag.get("id")
            if not tag_id:
                console.print(
                    f"Skipping tag with missing ID: {tag.get('name', 'Unnamed')}", style="warning"
                )
                skipped_count += 1
                continue
            tag_name = tag.get("name", f"Unnamed_{tag_id[:6]}")
            # Categorize based on presence of 'challenge' key
            if tag.get("challenge"):
                category["challenge"][tag_id] = tag_name
            else:
                category["personal"][tag_id] = tag_name
            processed_count += 1

        console.print(f"Processed {processed_count} tags ({skipped_count} skipped).")
        save_json(data=category, filepath=filepath)

    except requests.exceptions.RequestException as api_err:
        console.print(f"API Error fetching tags: {api_err}", style="error")
    except Exception as e:
        console.print(f"Unexpected error in save_tags_into_json: {e}", style="error")


# --- Raw Task Exports ---
# & - def save_tasks_without_processing(...)
def save_tasks_without_proccessing(  # Keep typo for consistency if called elsewhere
    api_client: HabiticaAPI, output_filename: Union[str, Path] = "tasks_raw.json"
) -> None:
    """Fetches all raw tasks, processes emojis in text, saves to JSON."""
    filepath = Path(output_filename)
    console.print(f"📝 Fetching raw tasks (emoji processing) -> [file]'{filepath}'[/]...")
    try:
        raw_tasks = api_client.get_tasks()
        if not isinstance(raw_tasks, list):
            console.print(
                f"API Error: Expected list of tasks, got {type(raw_tasks)}.", style="error"
            )
            return

        console.print(f"Fetched {len(raw_tasks)} tasks. Processing emojis...")
        processed_count, skipped_count = 0, 0
        tasks_to_save = []
        for task in raw_tasks:
            if not isinstance(task, dict):
                console.print(f"Skipping invalid item in tasks list: {task}", style="warning")
                skipped_count += 1
                continue
            # Process text and notes for emojis
            if "text" in task:
                task["text"] = emoji_data_python.replace_colons(str(task.get("text", "")))
            if "notes" in task:
                task["notes"] = emoji_data_python.replace_colons(str(task.get("notes", "")))
            tasks_to_save.append(task)
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
# & - def save_processed_tasks_into_json(...)
def save_processed_tasks_into_json(
    processed_tasks_dict: Dict[str, Dict[str, Any]],
    output_filename: Union[str, Path] = "tasks_processed.json",
) -> None:
    """Saves an already processed task dictionary to JSON."""
    filepath = Path(output_filename)
    console.print(f"💾 Saving processed tasks dictionary -> [file]'{filepath}'[/]...")
    if not isinstance(processed_tasks_dict, dict):
        console.print(
            f"Error: Invalid input `processed_tasks_dict` (must be dict), got {type(processed_tasks_dict)}.",
            style="error",
        )
        return
    if not processed_tasks_dict:
        console.print("No processed tasks data provided. Saving empty file.", style="info")
        save_json({}, filepath)
        return
    save_json(processed_tasks_dict, filepath)


# --- User Data Exports ---
# & - def save_all_userdata_into_json(...)
def save_all_userdata_into_json(
    api_client: HabiticaAPI, output_filename: Union[str, Path] = "user_data_full.json"
) -> None:
    """Fetches the full user data object (/user endpoint) and saves it to JSON."""
    filepath = Path(output_filename)
    console.print(f"👤 Fetching full user data -> [file]'{filepath}'[/]...")
    try:
        # get_user_data returns the 'data' part directly or None
        user_data_content = api_client.get_user_data()

        if user_data_content is None:
            console.print("Error: Failed to fetch user data from API.", style="error")
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
