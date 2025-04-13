# pixabit/export.py
# MARK: - MODULE DOCSTRING
"""
Provides functions for exporting various Habitica data structures to JSON files.
This module includes functions to fetch specific data types (like tags,
challenges with tasks, raw tasks, full user data) using the HabiticaAPI client
and save them into well-formatted JSON files. It leverages helper utilities
for file saving and potentially other classes like ChallengeBackupper for
more complex export processes.
Functions:
    save_user_stats_into_json: Fetches all user stats and saves them as JSON.
    save_tags_into_json: Fetches all user tags and saves them as JSON.
    save_full_challenges_into_json: Saves each challenge with its tasks as separate JSON files.
    save_tasks_without_proccessing: Fetches all raw tasks and saves as a single JSON file.
    save_processed_tasks_into_json: Saves an already processed task dictionary as JSON.
    save_all_userdata_into_json: Fetches the complete user object and saves as JSON.
Internal Helpers:
    _save_json: Helper function to save Python data to JSON with error handling.
"""
import json
import os
from typing import Any, Dict, List, Union

import emoji_data_python

# MARK: - IMPORTS
from . import config
from .api import HabiticaAPI
from .data_processor import TaskProcessor, get_user_stats
from .export_challenges import ChallengeBackupper
from .utils.display import console, print


# MARK: - INTERNAL HELPER FUNCTIONS
# & - def _save_json(data: Union[Dict[str, Any], List[Any]], filepath: str) -> None:
def _save_json(data: Union[Dict[str, Any], List[Any]], filepath: str) -> None:
    """
    Saves Python data (dict or list) to a JSON file with pretty printing.

    Ensures the output directory exists before writing. Handles potential
    JSON serialization errors and file I/O errors.

    Args:
        data (Union[Dict[str, Any], List[Any]]): The Python dictionary or list
                                                 to save.
        filepath (str): The full path (including filename) for the output JSON file.

    Returns:
        None

    Raises:
        Prints error messages to console upon failure (TypeError, IOError, Exception).
    """
    try:
        # Get the directory part of the filepath
        dir_name = os.path.dirname(filepath)

        # Create parent directories only if a path is specified (dir_name is not empty)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        # Write the file with UTF-8 encoding and nice indentation
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"[green]Successfully saved data to:[/green] [file]{filepath}[/]")

    except TypeError as e:
        # Handle cases where data cannot be serialized to JSON
        print(
            f"[error]Error:[/error] Data structure not JSON serializable for '{filepath}'. {e}"
        )
    except IOError as e:
        # Handle file system errors (permissions, disk full, etc.)
        print(f"[error]Error:[/error] Could not write file '{filepath}': {e}")
    except Exception as e:
        # Catch any other unexpected errors during saving
        print(
            f"[error]Error:[/error] An unexpected error occurred saving to '{filepath}': {e}"
        )


# MARK: - EXPORT FUNCTIONS


# --- Tag Exports ---
# & - def save_user_stats_into_json(
def save_user_stats_into_json(
    api_client: HabiticaAPI,
    tasks_processed: dict,
    output_filename: str = "tags_all.json",
) -> None:
    """
    Fetches all user tags from Habitica and saves them to a single JSON file.

    The saved JSON structure categorizes tags into 'challenge' and 'personal'
    based on whether the tag object contains a 'challenge' key. Within each
    category, it stores a dictionary mapping tag ID to tag name.

    Args:
        api_client (HabiticaAPI): An authenticated HabiticaAPI client instance.
        tasks_processed (dict): The generated dict from task processing.

        output_filename (str): The name (or path) of the JSON file to save the tags.
                               Defaults to "tags_all.json".

    Returns:
        None
    """
    print(f"Fetching tags to save to [file]{output_filename}[/]...")
    try:
        user_stats = get_user_stats(
            api_client, tasks_processed["cats"]
        )  # Should return List[Dict] or []

        if not isinstance(user_stats, dict):  # Check if API returned expected type
            print(
                "[error]Error:[/error] Failed to fetch tags or received unexpected data format from API."
            )
            return

        if not user_stats:
            print("[yellow]No stats for the account.[/yellow]")
            # Save an empty structure or just return
            # _save_json({"challenge": {}, "personal": {}}, output_filename)
            # return

        # Note: Sorting the dictionaries directly like the original code won't work
        # as intended. Dictionaries are inherently unordered (in older Python) or
        # insertion ordered (newer Python). If sorted output is required, you'd
        # sort the items *before* saving or save as a sorted list of objects.
        # Saving the categorized dictionaries as is:
        _save_json(user_stats, output_filename)

    except requests.exceptions.RequestException as api_err:
        print(f"[error]API Error fetching stats: {api_err}[/]")
    except Exception as e:
        # Catch any other exceptions during the process
        print(f"[error]Error in save_user_stats_into_json: {e}[/]")


# --- Tag Exports ---
# & - def save_tags_into_json(
def save_tags_into_json(
    api_client: HabiticaAPI, output_filename: str = "tags_all.json"
) -> None:
    """
    Fetches all user tags from Habitica and saves them to a single JSON file.

    The saved JSON structure categorizes tags into 'challenge' and 'personal'
    based on whether the tag object contains a 'challenge' key. Within each
    category, it stores a dictionary mapping tag ID to tag name.

    Args:
        api_client (HabiticaAPI): An authenticated HabiticaAPI client instance.
        output_filename (str): The name (or path) of the JSON file to save the tags.
                               Defaults to "tags_all.json".

    Returns:
        None
    """
    print(f"Fetching tags to save to [file]{output_filename}[/]...")
    try:
        tags_list = api_client.get_tags()  # Should return List[Dict] or []

        if not isinstance(tags_list, list):  # Check if API returned expected type
            print(
                "[error]Error:[/error] Failed to fetch tags or received unexpected data format from API."
            )
            return

        if not tags_list:
            print("[yellow]No tags found in the account.[/yellow]")
            # Save an empty structure or just return
            # _save_json({"challenge": {}, "personal": {}}, output_filename)
            # return

        # Categorize tags based on presence of 'challenge' key
        category: Dict[str, Dict[str, str]] = {"challenge": {}, "personal": {}}
        processed_count = 0
        for tag in tags_list:
            tag_id = tag.get("id")
            tag_name = tag.get("name", tag_id)  # Use ID as name if name is missing
            if not tag_id:
                print(f"[yellow]Warning:[/yellow] Skipping tag with missing ID: {tag}")
                continue

            # Check if 'challenge' key exists and is truthy (usually a string ID)
            if tag.get("challenge"):
                category["challenge"][tag_id] = tag_name
            else:
                category["personal"][tag_id] = tag_name
            processed_count += 1

        print(f"Processed {processed_count} tags into categories.")

        # Note: Sorting the dictionaries directly like the original code won't work
        # as intended. Dictionaries are inherently unordered (in older Python) or
        # insertion ordered (newer Python). If sorted output is required, you'd
        # sort the items *before* saving or save as a sorted list of objects.
        # Saving the categorized dictionaries as is:
        _save_json(category, output_filename)

    except requests.exceptions.RequestException as api_err:
        print(f"[error]API Error fetching tags: {api_err}[/]")
    except Exception as e:
        # Catch any other exceptions during the process
        print(f"[error]Error in save_tags_into_json: {e}[/]")


# --- Challenge Exports ---
# & - def save_full_challenges_into_json(
def save_full_challenges_into_json(
    api_client: HabiticaAPI, output_folder: str = "_challenge_backups"
) -> None:
    """
    Saves each challenge (with processed tasks) as a separate JSON file.

    Uses the `ChallengeBackupper` class to handle the fetching, processing,
    and saving logic for individual challenge backups.

    Args:
        api_client (HabiticaAPI): An authenticated HabiticaAPI client instance.
        output_folder (str): The directory where challenge backup JSON files
                             will be saved. Defaults to "_challenge_backups".

    Returns:
        None
    """
    print(f"Starting full challenge backup to folder: [file]{output_folder}[/]...")
    try:
        # Ensure ChallengeBackupper was imported successfully
        if "ChallengeBackupper" not in globals() or not callable(ChallengeBackupper):
            print(
                "[error]Error:[/error] ChallengeBackupper class is not available. Cannot perform backup."
            )
            return

        backupper = ChallengeBackupper(api_client=api_client)
        backupper.create_backups(output_folder=output_folder)
        # Success message is usually printed within create_backups
    except Exception as e:
        print(f"[error]Error occurred during challenge backup process: {e}[/]")
        # import traceback # Uncomment for detailed debug info
        # traceback.print_exc()


# --- Task Exports ---
# & - def save_tasks_without_proccessing(
def save_tasks_without_proccessing(
    api_client: HabiticaAPI, output_filename: str = "tasks_raw.json"
) -> None:
    """
    Fetches all raw task data from Habitica and saves it to a single JSON file.

    Retrieves habits, dailies, todos, and rewards. Processes the 'text' field
    of each task to convert emoji shortcodes (e.g., :tada:) to unicode emojis
    before saving.

    Args:
        api_client (HabiticaAPI): An authenticated HabiticaAPI client instance.
        output_filename (str): The name (or path) of the JSON file to save the raw tasks.
                               Defaults to "tasks_raw.json".

    Returns:
        None
    """
    print(f"Fetching raw tasks to save to [file]{output_filename}[/]...")
    try:
        raw_tasks = api_client.get_tasks()  # Fetches all task types

        if not isinstance(raw_tasks, list):  # Check API response type
            print(
                "[error]Error:[/error] Failed to fetch raw tasks or received unexpected data format."
            )
            return

        print(f"Processing {len(raw_tasks)} raw tasks (converting emojis in text)...")
        # Process emojis in task text before saving
        processed_count = 0
        for task in raw_tasks:
            if isinstance(task, dict) and "text" in task:
                original_text = task.get("text", "")
                # Ensure text is string before processing
                task["text"] = emoji_data_python.replace_colons(str(original_text))
                processed_count += 1

        print(f"Emoji processing complete for {processed_count} tasks.")
        _save_json(raw_tasks, output_filename)

    except requests.exceptions.RequestException as api_err:
        print(f"[error]API Error fetching tasks: {api_err}[/]")
    except Exception as e:
        print(f"[error]Error in save_tasks_without_proccessing: {e}[/]")


# & - def save_processed_tasks_into_json(
def save_processed_tasks_into_json(
    processed_tasks_dict: Dict[str, Dict[str, Any]],
    output_filename: str = "tasks_processed.json",
) -> None:
    """
    Saves a dictionary of already processed tasks to a JSON file.

    This function expects task data that has already been processed (e.g., by
    `TaskProcessor`) and is structured as a dictionary where keys are task IDs
    and values are the processed task data dictionaries.

    Args:
        processed_tasks_dict (Dict[str, Dict[str, Any]]):
            The dictionary `{task_id: processed_task_data, ...}` containing
            the task data to be saved.
        output_filename (str): The name (or path) for the output JSON file.
                               Defaults to "tasks_processed.json".

    Returns:
        None
    """
    print(f"Saving processed tasks dictionary to [file]{output_filename}[/]...")
    if not isinstance(processed_tasks_dict, dict):
        print(
            "[error]Error:[/error] Invalid data format: `processed_tasks_dict` must be a dictionary."
        )
        return
    if not processed_tasks_dict:
        print("[yellow]Warning:[/yellow] No processed tasks data provided to save.")
        # Decide whether to save an empty file or just return
        # _save_json({}, output_filename)
        # return

    # Use the internal helper to save the dictionary
    _save_json(processed_tasks_dict, output_filename)


# --- User Data Exports ---
# & - def save_all_userdata_into_json(
def save_all_userdata_into_json(
    api_client: HabiticaAPI, output_filename: str = "user_data_full.json"
) -> None:
    """
    Fetches the full user data object (/user endpoint) and saves it to a JSON file.

    This includes user profile, stats, preferences, inventory, equipment, etc.

    Args:
        api_client (HabiticaAPI): An authenticated HabiticaAPI client instance.
        output_filename (str): The name (or path) of the JSON file to save the user data.
                               Defaults to "user_data_full.json".

    Returns:
        None
    """
    print(f"Fetching full user data to save to [file]{output_filename}[/]...")
    try:
        user_data = api_client.get_user_data()  # Fetches the /user object

        if not isinstance(user_data, dict) or not user_data:  # Check API response
            print(
                "[error]Error:[/error] Failed to fetch user data from API or received empty/invalid data."
            )
            return

        _save_json(user_data, output_filename)

    except requests.exceptions.RequestException as api_err:
        print(f"[error]API Error fetching user data: {api_err}[/]")
    except Exception as e:
        print(f"[error]Error in save_all_userdata_into_json: {e}[/]")


# MARK: - EXAMPLE USAGE (Commented out)
# This shows how you might call these functions from another script
#
# import os
# from pixabit.api import HabiticaAPI
# from pixabit.export import (
# 	save_tags_into_json,
# 	save_full_challenges_into_json,
# 	save_tasks_without_proccessing,
# 	# save_processed_tasks_into_json, # Requires processed_tasks dict
# 	save_all_userdata_into_json
# )
# # Assuming TaskProcessor exists if needed for processed tasks
# # from pixabit.processing import TaskProcessor
#
# if __name__ == "__main__":
# 	print("[bold blue]--- Running Pixabit Export Functions ---[/]")
# 	EXPORT_DIR = "_exports" # Define a common output directory
#
# 	try:
# 		api = HabiticaAPI() # Initialize API client
#
# 		# Example calls:
# 		print("\n--- Exporting Tags ---")
# 		save_tags_into_json(api, os.path.join(EXPORT_DIR, "tags_all.json"))
#
# 		print("\n--- Exporting Raw Tasks ---")
# 		save_tasks_without_proccessing(api, os.path.join(EXPORT_DIR, "tasks_raw.json"))
#
# 		print("\n--- Exporting Full User Data ---")
# 		save_all_userdata_into_json(api, os.path.join(EXPORT_DIR, "user_data_full.json"))
#
# 		print("\n--- Exporting Challenges ---")
# 		save_full_challenges_into_json(api, os.path.join(EXPORT_DIR, "challenge_backups")) # Pass subfolder name
#
# 		# Example for processed tasks (requires running processor first)
# 		# print("\n--- Processing and Exporting Tasks ---")
# 		# processor = TaskProcessor(api)
# 		# results = processor.process_and_categorize_all()
# 		# processed_tasks = results.get("data", {})
# 		# if processed_tasks:
# 		# 	 save_processed_tasks_into_json(processed_tasks, os.path.join(EXPORT_DIR, "tasks_processed.json"))
# 		# else:
# 		#	 print("Skipping processed task export: No data from processor.")
#
# 	except ValueError as config_err: # Catch config errors during API init
# 		 print(f"[error]Configuration Error: {config_err}[/]")
# 	except Exception as e:
# 		 print(f"[error]An error occurred during export: {e}[/]")
# 		 # import traceback
# 		 # traceback.print_exc()
#
# 	print("\n[bold blue]--- Export Process Finished ---[/]")
