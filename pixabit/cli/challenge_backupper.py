# pixabit/cli/challenge_backupper.py (Utility)

# SECTION: MODULE DOCSTRING
"""Provides the ChallengeBackupper class for backing up Habitica challenges (Synchronous).

Fetches challenges and tasks using the sync API client, processes them (cleans tasks,
handles emojis), and saves each challenge with its tasks as an individual JSON file
using sanitized filenames. This is likely still usable as a standalone utility
or could be adapted into an async action in DataStore.
"""

# SECTION: IMPORTS
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union  # Added List/Any

import emoji_data_python
import requests  # For specific API error handling
from pathvalidate import sanitize_filename  # For creating safe filenames

# Local Imports (Adjust based on structure)
try:
    from ..utils.display import console, print  # Use themed display
    from ..utils.save_json import save_json  # Use shared save utility
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
        print(f"Dummy save_json({filepath})")
        return False

    def sanitize_filename(fn: str) -> str:
        return fn.replace("/", "_")  # Basic fallback

    print("Warning: Using fallback imports in cli/challenge_backupper.py")


# SECTION: CLASS DEFINITION
# KLASS: ChallengeBackupper
class ChallengeBackupper:
    """Handles fetching Habitica challenges, processing tasks, and saving backups (Sync)."""

    # Keys to remove from task data for a cleaner, more reusable backup
    TASK_KEYS_TO_REMOVE: List[str] = [
        "history",
        "completed",
        "isDue",
        "nextDue",
        "yesterDaily",
        "streak",
        "userId",
        "updatedAt",
        "createdAt",
        # Decide if 'challenge' object itself should be removed from task backup
        # "challenge",
    ]

    # FUNC: __init__
    def __init__(self, api_client: HabiticaAPI):
        """Initializes the ChallengeBackupper with a synchronous API client.

        Args:
            api_client: An initialized instance of the synchronous HabiticaAPI client.

        Raises:
            TypeError: If api_client is not an instance of HabiticaAPI.
        """
        if not isinstance(api_client, HabiticaAPI):
            raise TypeError(
                "`api_client` must be an instance of the synchronous HabiticaAPI"
            )
        self.api_client: HabiticaAPI = api_client
        self.console = console
        self.console.log("ChallengeBackupper (Sync) initialized.", style="info")

    # --- Public Method ---

    # FUNC: create_backups
    def create_backups(
        self, output_folder: Union[str, Path] = "_challenge_backups"
    ) -> None:
        """Executes the full challenge backup process (Synchronous).

        Args:
            output_folder: The directory path (string or Path) to save backup files.
        """
        self.console.print("\n🚀 Starting challenge backup process (Sync)...")
        saved_count, failed_count = 0, 0
        output_path = Path(output_folder)

        try:
            # --- Fetch Data (Sync) ---
            self.console.print(
                "⏳ Fetching challenges and tasks from Habitica API (Sync)..."
            )
            tasks, challenges = self._fetch_data()  # Calls sync fetch
            if challenges is None or tasks is None:
                self.console.print(
                    "❌ Halting backup due to errors fetching data.",
                    style="error",
                )
                return
            if not challenges:
                self.console.print(
                    "ℹ️ No challenges found for this user to back up.",
                    style="info",
                )
                return
            self.console.print(
                f"✅ Fetched {len(challenges)} challenges and {len(tasks)} tasks.",
                style="success",
            )

            tasks_by_challenge = self._group_tasks_by_challenge(tasks)

            try:
                output_path.mkdir(parents=True, exist_ok=True)
                self.console.print(
                    f"💾 Saving backups to folder: [file]'{output_path.resolve()}'[/]"
                )
            except OSError as io_err:
                self.console.print(
                    f"❌ File System Error creating '{output_path}': {io_err}",
                    style="error",
                )
                return

            # --- Process & Save (Sync loop) ---
            sorted_challenges = sorted(
                challenges, key=lambda x: str(x.get("name", "")).lower()
            )
            total_challenges = len(sorted_challenges)
            self.console.print(f"⚙️ Processing {total_challenges} challenges...")

            # Consider using Rich track here if the list is long
            for index, challenge_data in enumerate(sorted_challenges):
                challenge_id = challenge_data.get("id")
                original_name = challenge_data.get("name", "Unnamed_Challenge")
                short_name = challenge_data.get("shortName") or original_name
                progress_prefix = f"({index + 1}/{total_challenges})"
                self.console.print(
                    f"\n{progress_prefix} Processing: [keyword]'{original_name}'[/] ([info]{challenge_id or 'N/A'}[/])"
                )

                if not challenge_id or not isinstance(challenge_data, dict):
                    self.console.print(
                        f"  ⚠️ Skipping invalid challenge data: {challenge_data}",
                        style="warning",
                    )
                    failed_count += 1
                    continue

                associated_tasks = tasks_by_challenge.get(challenge_id, [])
                self.console.print(
                    f"  Found {len(associated_tasks)} associated task(s)."
                )
                processed_backup = self._process_single_challenge(
                    challenge_data, associated_tasks
                )

                safe_base = sanitize_filename(str(short_name))
                if not safe_base:
                    safe_base = f"challenge_{challenge_id}"
                filename = f"{safe_base}.json"
                filepath = output_path / filename

                if save_json(
                    data=processed_backup, filepath=filepath
                ):  # Sync save
                    saved_count += 1
                else:
                    failed_count += 1  # save_json logs its own errors

            # --- Final Summary ---
            self.console.rule(style="rp_overlay")
            if failed_count == 0:
                self.console.print(
                    f"[success]✅ Backup complete. Saved {saved_count}/{total_challenges} challenges.[/success]"
                )
            else:
                self.console.print(
                    f"[warning]⚠️ Backup complete. Saved: {saved_count}, Failed/Skipped: {failed_count} (Total: {total_challenges}).[/warning]"
                )
            self.console.rule(style="rp_overlay")

        except Exception as e:
            self.console.print(
                f"\n[error]❌ Unexpected error during challenge backup:[/error] {e}"
            )
            # self.console.print_exception(show_locals=False) # Optional traceback

    # --- Internal Helper Methods ---

    # FUNC: _fetch_data (Sync version)
    def _fetch_data(
        self,
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]]]:
        """Fetches all user tasks and member challenges using sync API client.

        Returns:
            Tuple (tasks, challenges), where each can be a list or None on error.
        """
        tasks: Optional[List[Dict[str, Any]]] = None
        challenges: Optional[List[Dict[str, Any]]] = None
        try:
            # self.console.print("  Fetching all user tasks (Sync)...")
            tasks = self.api_client.get_tasks()  # Sync call
            if not isinstance(tasks, list):
                self.console.print(
                    f"API Error: Expected list of tasks, got {type(tasks)}.",
                    style="error",
                )
                tasks = None
            # else: self.console.print(f"  Fetched {len(tasks)} tasks.")

            # self.console.print("  Fetching member challenges (Sync)...")
            # Use sync paginated fetch
            challenges = self.api_client.get_all_challenges_paginated(
                member_only=True
            )
            if not isinstance(challenges, list):  # Should be list even if empty
                self.console.print(
                    f"API Error: Expected list of challenges, got {type(challenges)}.",
                    style="error",
                )
                challenges = None
            # else: self.console.print(f"  Fetched {len(challenges)} challenges.")
            return tasks, challenges

        except requests.exceptions.RequestException as api_err:
            self.console.print(
                f"API Connection Error fetching data: {api_err}", style="error"
            )
            return None, None
        except Exception as e:
            self.console.print(
                f"Unexpected Error fetching data: {e}", style="error"
            )
            return None, None

    # FUNC: _group_tasks_by_challenge
    def _group_tasks_by_challenge(
        self, tasks: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Groups tasks by challenge ID. Returns {challenge_id: [tasks]}. (Sync version)."""
        # self.console.print("  Grouping tasks by challenge ID...")
        tasks_by_challenge: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        if not isinstance(tasks, list):
            self.console.print(
                "Task list invalid for grouping. Returning empty map.",
                style="warning",
            )
            return {}

        processed_count, linked_count = 0, 0
        for task in tasks:
            if not isinstance(task, dict):
                continue
            processed_count += 1
            challenge = task.get("challenge")
            if isinstance(challenge, dict):
                c_id = challenge.get("id")
                if c_id and isinstance(c_id, str):
                    tasks_by_challenge[c_id].append(task)
                    linked_count += 1
        # self.console.print(f"  Processed {processed_count} tasks. Found {linked_count} linked to {len(tasks_by_challenge)} challenges.")
        return dict(tasks_by_challenge)  # Return standard dict

    # FUNC: _clean_task_for_backup
    def _clean_task_for_backup(
        self, task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Removes transient keys and processes emojis for task backup."""
        if not isinstance(task_data, dict):
            return {"error": "Invalid task data"}
        cleaned = task_data.copy()
        for key in self.TASK_KEYS_TO_REMOVE:
            cleaned.pop(key, None)

        # Process text/notes/checklist for emojis
        if "text" in cleaned and cleaned["text"]:
            cleaned["text"] = emoji_data_python.replace_colons(
                str(cleaned["text"])
            )
        if "notes" in cleaned and cleaned["notes"]:
            cleaned["notes"] = emoji_data_python.replace_colons(
                str(cleaned["notes"])
            )
        if "checklist" in cleaned and isinstance(cleaned["checklist"], list):
            for item in cleaned["checklist"]:
                if isinstance(item, dict) and "text" in item and item["text"]:
                    item["text"] = emoji_data_python.replace_colons(
                        str(item["text"])
                    )
        return cleaned

    # FUNC: _process_single_challenge
    def _process_single_challenge(
        self, challenge_data: Dict[str, Any], tasks_raw: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Processes a single challenge and its tasks into backup format."""
        backup = challenge_data.copy()
        # Embed cleaned tasks under a specific key (e.g., "_tasks")
        backup["_tasks"] = [
            self._clean_task_for_backup(task) for task in tasks_raw
        ]

        # Process text fields in the challenge data itself
        name = backup.pop("name", "Unnamed")
        desc = backup.pop("description", "")
        summary = backup.pop("summary", "")
        backup["_name"] = emoji_data_python.replace_colons(
            str(name)
        )  # Use a different key for processed name
        backup["_description"] = emoji_data_python.replace_colons(str(desc))
        if summary:
            backup["_summary"] = emoji_data_python.replace_colons(str(summary))
        return backup
