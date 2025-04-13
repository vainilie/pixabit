# pixabit/challenge_backup.py
"""
Provides the ChallengeBackupper class for backing up Habitica challenges.
This module defines the `ChallengeBackupper` class, which utilizes an authenticated
HabiticaAPI client to fetch user challenges and associated tasks. It processes
this data by cleaning task information, handling emoji codes in text fields,
and then saves each challenge (along with its processed tasks) as an
individual JSON file in a specified output directory.
The process involves:
1. Fetching all challenges the user is a member of.
2. Fetching all user tasks (used to find tasks linked to challenges).
3. Grouping tasks by their parent challenge ID for efficient lookup.
4. Iterating through each challenge:
    a. Cleaning the associated tasks (removing transient/user-specific data).
    b. Processing challenge text fields (name, description, summary) for emojis.
    c. Generating a filesystem-safe filename based on the challenge name.
    d. Saving the processed challenge data (including cleaned tasks) as a JSON file.
Requires:
- An authenticated `HabiticaAPI` instance from `.api`.
- Utility functions `save_json` from `.utils.save_json`.
- Utility function `replace_illegal_filename_characters` from
  `.utils.replace_illegal_filename_characters`.
- The `emoji-data-python` library for emoji code conversion.
- The `pathvalidate` library (likely used within the filename cleaning utility).
"""
import os
import typing
from typing import Any, Dict, List, Tuple

import emoji_data_python
from pathvalidate import sanitize_filename

from .api import HabiticaAPI
from .data_processor import TaskProcessor
from .utils.display import console, print
from .utils.save_json import save_json


class ChallengeBackupper:
    """
    Handles fetching Habitica challenges, processing tasks, and saving backups.

    Orchestrates the process of connecting to the Habitica API, retrieving
    challenge and task data, cleaning and transforming the data into a suitable
    backup format, and writing individual JSON files for each challenge.
    """

    # Keys to remove from task data when embedding in the challenge backup.
    # These keys often contain user-specific state, history, or redundant info.
    TASK_KEYS_TO_REMOVE: List[str] = [
        "history",  # Task scoring history
        "byHabitica",  # Flag for official Habitica tasks
        "completed",  # User-specific completion status
        "createdAt",  # Task creation timestamp (within challenge context)
        "group",  # Group associated with the task (redundant)
        "isDue",  # User-specific daily due status
        "nextDue",  # User-specific daily next due date
        "updatedAt",  # Last updated timestamp (user-specific)
        "userId",  # User ID associated with the task instance
        "yesterDaily",  # User-specific daily yesterday status
        # "challenge",    # Keep challenge link within task? Removed by default.
    ]

    # & -     def __init__(self, api_client: HabiticaAPI):
    def __init__(self, api_client: HabiticaAPI):
        """
        Initializes the ChallengeBackupper.

        Args:
            api_client (HabiticaAPI): An authenticated instance of the HabiticaAPI
                                      client used to fetch data.
        """
        if not isinstance(api_client, HabiticaAPI):
            raise TypeError("api_client must be an instance of HabiticaAPI")
        self.api_client: HabiticaAPI = api_client
        print("[bold blue]ChallengeBackupper initialized.[/]")

    # --- Public Methods ---

    # & -     def create_backups(self, output_folder: str = "_challenge_backups") -> None:
    def create_backups(self, output_folder: str = "_challenge_backups") -> None:
        """
        Executes the full challenge backup process.

        Fetches challenges and tasks, processes them, and saves each challenge
        as a separate JSON file in the specified output folder. Challenges are
        sorted alphabetically by name before saving.

        Args:
            output_folder (str): The path to the directory where challenge JSON
                                 backup files will be saved. It will be created
                                 if it doesn't exist. Defaults to "_challenge_backups".

        Returns:
            None

        Raises:
            requests.exceptions.RequestException: If fetching data via the API fails.
            IOError: If creating the output directory or writing a file fails.
            Exception: Catches and prints other potential errors during processing.
        """
        print(f"Starting challenge backup process...")
        saved_count = 0
        try:
            # 1. Fetch Data
            tasks, challenges = self._fetch_data()
            if not challenges:
                print("[yellow]No challenges found to back up.[/]")
                return

            # 2. Group Tasks (Optimization)
            tasks_by_challenge = self._group_tasks_by_challenge(tasks)

            # 3. Prepare Output Directory
            os.makedirs(output_folder, exist_ok=True)
            print(f"Saving backups to folder: [file]'{output_folder}'[/]")

            # 4. Process and Save Each Challenge
            # Sort challenges by original name (case-insensitive) for consistent order
            sorted_challenges = sorted(
                challenges, key=lambda x: x.get("name", "").lower()
            )

            total_challenges = len(sorted_challenges)
            for index, challenge_data in enumerate(sorted_challenges):
                challenge_id = challenge_data.get("id")
                original_name = challenge_data.get("name", "Unnamed Challenge")
                short_name = challenge_data.get(
                    "shortName", original_name
                )  # Use shortName for filename if available

                print(
                    f"\nProcessing challenge {index + 1}/{total_challenges}: [bold magenta]'{original_name}'[/] (ID: {challenge_id or 'N/A'})"
                )

                if not challenge_id:
                    print(
                        f"[yellow]Skipping challenge with missing ID: '{original_name}'[/]"
                    )
                    continue

                # Get pre-grouped tasks for this challenge
                associated_tasks_raw = tasks_by_challenge.get(challenge_id, [])
                print(f"  Found {len(associated_tasks_raw)} associated task(s).")

                # Process the challenge and its tasks for backup format
                processed_backup = self._process_single_challenge(
                    challenge_data, associated_tasks_raw
                )

                # Generate filename using shortName preferably, cleaned for filesystem
                safe_title = short_name
                if not safe_title:  # Handle cases where name is only illegal chars
                    safe_title = f"challenge_{challenge_id}"
                filename = f"{safe_title}.json"
                filepath = os.path.join(output_folder, filename)

                # Save the file
                try:
                    # Use the imported save_json utility
                    save_json(
                        data=processed_backup,
                        filename=filepath,  # Pass the full path
                        suffix="",  # No suffix needed as extension is in filename
                    )
                    print(
                        f"  [green]:heavy_check_mark: Saved backup:[/green] [file]{filename}[/]"
                    )
                    saved_count += 1
                except IOError as save_err:
                    print(
                        f"  [error]:x: Error saving backup file '{filename}': {save_err}[/]"
                    )
                except Exception as save_err:  # Catch other potential save errors
                    print(
                        f"  [error]:x: Unexpected error saving backup '{filename}': {save_err}[/]"
                    )

            print(
                f"\n[bold green]Challenge backup process complete. Successfully saved {saved_count} / {total_challenges} challenges.[/]"
            )

        except requests.exceptions.RequestException as api_err:
            print(
                f"\n[error]:x: API Error during challenge backup process: {api_err}[/]"
            )
            # Optionally re-raise if needed elsewhere: raise
        except IOError as io_err:
            print(
                f"\n[error]:x: File System Error during challenge backup process (e.g., creating folder '{output_folder}'): {io_err}[/]"
            )
        except Exception as e:
            print(
                f"\n[error]:x: An unexpected error occurred during the challenge backup process: {e}[/]"
            )
            # Optional: Add more detailed logging for unexpected errors
            # import traceback
            # traceback.print_exc()

    # --- Internal Helper Methods ---

    # & -     def _fetch_data(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    def _fetch_data(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Fetches all user tasks and challenges the user is a member of via the API.

        Returns:
            Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]: A tuple containing:
                - list: All tasks belonging to the user.
                - list: All challenges the user is currently a member of.

        Raises:
            requests.exceptions.RequestException: If the API call to get tasks
                                                  or challenges fails.
        """
        print("Fetching all user tasks...")
        # Assuming get_tasks fetches all types (habits, dailies, todos, rewards)
        tasks = self.api_client.get_tasks()
        print(f"Fetched {len(tasks)} tasks.")

        print("Fetching member challenges (handles pagination)...")
        # get_challenges(member_only=True) retrieves only challenges user is in
        challenges = self.api_client.get_challenges(member_only=True)
        print(f"Fetched {len(challenges)} challenges.")

        return tasks, challenges

    # & -     def _group_tasks_by_challenge(
    def _group_tasks_by_challenge(
        self, tasks: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Groups tasks by their associated challenge ID for efficient lookup.

        This pre-processes the flat list of all user tasks into a dictionary
        where keys are challenge IDs and values are lists of tasks belonging
        to that challenge. This avoids repeatedly searching the task list later.

        Args:
            tasks (List[Dict[str, Any]]): The flat list of all user tasks fetched
                                          from the API.

        Returns:
            Dict[str, List[Dict[str, Any]]]: A dictionary mapping challenge IDs
                                             to lists of associated task objects.
                                             Challenges with no linked tasks found
                                             in the input list will not be keys.
        """
        print("Grouping tasks by challenge ID for faster lookup...")
        tasks_by_challenge: Dict[str, List[Dict[str, Any]]] = {}
        tasks_processed_count = 0
        for task in tasks:
            tasks_processed_count += 1
            # Task dictionary structure for challenge link: task['challenge']['id']
            challenge_info = task.get("challenge")  # Safely get the challenge dict
            if isinstance(challenge_info, dict):
                challenge_id = challenge_info.get("id")
                if challenge_id:  # Ensure challenge_id is not None or empty
                    if challenge_id not in tasks_by_challenge:
                        tasks_by_challenge[challenge_id] = []
                    tasks_by_challenge[challenge_id].append(task)

        print(
            f"Processed {tasks_processed_count} tasks. Found tasks linked to {len(tasks_by_challenge)} unique challenges."
        )
        return tasks_by_challenge

    # & -     def _clean_task_for_backup(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
    def _clean_task_for_backup(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Removes specified transient or user-specific keys from a task dictionary.

        Creates a cleaned copy of the task data suitable for embedding within a
        challenge backup, removing keys listed in `self.TASK_KEYS_TO_REMOVE`.

        Args:
            task_data (Dict[str, Any]): The original task dictionary object.

        Returns:
            Dict[str, Any]: A new dictionary containing the cleaned task data.
        """
        # Create a copy to avoid modifying the original task data if it's reused elsewhere
        cleaned_task = task_data.copy()
        keys_removed_count = 0
        for key in self.TASK_KEYS_TO_REMOVE:
            if key in cleaned_task:
                cleaned_task.pop(key)
                keys_removed_count += 1
        # Optional: Log how many keys were removed per task if needed for debugging
        # print(f"    Cleaned task '{task_data.get('text', 'N/A')}', removed {keys_removed_count} keys.")
        return cleaned_task

    # & -     def _process_single_challenge(
    def _process_single_challenge(
        self, challenge_data: Dict[str, Any], challenge_tasks_raw: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Processes a single challenge and its associated tasks into backup format.

        Takes the raw challenge data and the raw list of its associated tasks.
        It cleans the tasks using `_clean_task_for_backup`, adds the cleaned
        task list to the challenge data under the `_tasks` key, and processes
        key text fields (`name`, `description`, `summary`) to convert emoji
        shortcodes (like `:tada:`) to unicode emojis. Renames processed fields
        with a leading underscore (`_name`, `_description`, `_summary`).

        Args:
            challenge_data (Dict[str, Any]): The raw dictionary object for the
                                             challenge being processed.
            challenge_tasks_raw (List[Dict[str, Any]]): A list of raw task
                                                        dictionary objects
                                                        associated with this challenge.

        Returns:
            Dict[str, Any]: A dictionary representing the processed challenge
                            backup data, ready to be saved as JSON.
        """
        # Start with a copy of the original challenge data to avoid modifying it
        backup_data = challenge_data.copy()

        # Clean associated tasks and add them under a specific key (e.g., "_tasks")
        cleaned_tasks = [
            self._clean_task_for_backup(task) for task in challenge_tasks_raw
        ]
        backup_data["_tasks"] = cleaned_tasks  # Embed cleaned tasks

        # --- Process text fields for emojis and rename ---
        # Use .pop() to remove original key and .get() as fallback if needed

        # Process Name
        original_name = backup_data.pop("name", "Unnamed Challenge")
        backup_data["_name"] = emoji_data_python.replace_colons(original_name)

        # Process Description
        original_desc = backup_data.pop(
            "description", ""
        )  # Default to empty string if missing
        # Ensure description is a string before processing
        backup_data["_description"] = emoji_data_python.replace_colons(
            str(original_desc)
        )

        # Process Summary (only if it exists and is not empty)
        original_summary = backup_data.pop("summary", "")  # Default to empty string
        if original_summary:  # Avoid adding empty "_summary" field
            # Ensure summary is a string before processing
            backup_data["_summary"] = emoji_data_python.replace_colons(
                str(original_summary)
            )

        # Note: Other string fields could be processed similarly if needed,
        # but be careful not to process IDs or other non-textual string data.

        return backup_data


# --- Example Usage (Command-line execution) ---
# This block allows running the backup directly, e.g., python -m pixabit.challenge_backup
if __name__ == "__main__":
    print("[bold blue]Running Challenge Backup Script Directly...[/]")

    # Basic error handling for standalone execution
    try:
        # Assumes .env file is in the current working directory or parent for config loading
        # Adjust path to HabiticaAPI if needed relative to this script's execution context
        api = HabiticaAPI()  # Reads credentials from config/.env by default
    except (ImportError, ValueError, FileNotFoundError) as config_err:
        print(
            f"[error]:x: Failed to initialize Habitica API. Is .env file configured? Error: {config_err}[/]"
        )
        exit(1)  # Exit if API can't be initialized
    except Exception as api_init_err:
        print(
            f"[error]:x: An unexpected error occurred initializing Habitica API: {api_init_err}[/]"
        )
        exit(1)

    try:
        backupper = ChallengeBackupper(api_client=api)

        # Define output folder (e.g., relative to the script location)
        # Default is "_challenge_backups" in the current working directory
        # For relative path:
        # script_dir = os.path.dirname(__file__)
        # backup_folder = os.path.join(script_dir, "_challenge_backups")
        backup_folder = "_challenge_backups"  # Or use a specific absolute path

        backupper.create_backups(output_folder=backup_folder)

    except Exception as main_err:
        print(f"[error]:x: Failed to run challenge backup process: {main_err}[/]")
        # Optional: Detailed traceback for debugging standalone runs
        # import traceback
        # traceback.print_exc()
        exit(1)

    print("\n[bold blue]Challenge Backup Script Finished.[/]")
