# pixabit/challenge_backupper.py
# MARK: - MODULE DOCSTRING
"""Provides the ChallengeBackupper class for backing up Habitica challenges.

Fetches challenges and tasks, processes them (cleans tasks, handles emojis),
and saves each challenge with its tasks as an individual JSON file using
sanitized filenames.
"""

# MARK: - IMPORTS
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import emoji_data_python
import requests  # For specific API error handling
from pathvalidate import sanitize_filename  # For creating safe filenames

# Local Imports
from .api import HabiticaAPI
from .utils.display import console  # Use themed display
from .utils.save_json import save_json  # Use shared save utility


# MARK: - CLASS DEFINITION
class ChallengeBackupper:
    """Handles fetching Habitica challenges, processing tasks, and saving backups."""

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
        # Keep 'group', 'byHabitica', 'challenge' for context? Decide based on backup goal.
        # Let's keep them for now unless they cause issues.
    ]

    # & - def __init__(self, api_client: HabiticaAPI):
    def __init__(self, api_client: HabiticaAPI):
        """Initializes the ChallengeBackupper."""
        if not isinstance(api_client, HabiticaAPI):
            raise TypeError("`api_client` must be an instance of HabiticaAPI")
        self.api_client: HabiticaAPI = api_client
        self.console = console  # Use themed console
        self.console.log("ChallengeBackupper initialized.", style="info")

    # --- Public Method ---
    # & - def create_backups(...)
    def create_backups(self, output_folder: Union[str, Path] = "_challenge_backups") -> None:
        """Executes the full challenge backup process."""
        self.console.print("\n🚀 Starting challenge backup process...")
        saved_count, failed_count = 0, 0
        output_path = Path(output_folder)

        try:
            # --- Fetch Data ---
            self.console.print("⏳ Fetching challenges and tasks from Habitica API...")
            tasks, challenges = self._fetch_data()
            if challenges is None or tasks is None:  # Check for fetch failure
                self.console.print("❌ Halting backup due to errors fetching data.", style="error")
                return
            if not challenges:
                self.console.print("ℹ️ No challenges found for this user to back up.", style="info")
                return
            self.console.print(
                f"✅ Fetched {len(challenges)} challenges and {len(tasks)} tasks.", style="success"
            )

            # --- Group Tasks ---
            tasks_by_challenge = self._group_tasks_by_challenge(tasks)

            # --- Prepare Output Dir ---
            try:
                output_path.mkdir(parents=True, exist_ok=True)
                self.console.print(
                    f"💾 Saving backups to folder: [file]'{output_path.resolve()}'[/]"
                )
            except OSError as io_err:
                self.console.print(
                    f"❌ File System Error creating '{output_path}': {io_err}", style="error"
                )
                return

            # --- Process & Save ---
            sorted_challenges = sorted(challenges, key=lambda x: str(x.get("name", "")).lower())
            total_challenges = len(sorted_challenges)
            self.console.print(f"⚙️ Processing {total_challenges} challenges...")

            for index, challenge_data in enumerate(sorted_challenges):
                challenge_id = challenge_data.get("id")
                original_name = challenge_data.get("name", "Unnamed_Challenge")
                short_name = challenge_data.get("shortName") or original_name  # Fallback

                progress_prefix = f"({index + 1}/{total_challenges})"
                self.console.print(
                    f"\n{progress_prefix} Processing: [keyword]'{original_name}'[/] ([info]{challenge_id or 'N/A'}[/])"
                )

                if not challenge_id or not isinstance(challenge_data, dict):
                    self.console.print(
                        f"  ⚠️ Skipping invalid challenge data: {challenge_data}", style="warning"
                    )
                    failed_count += 1
                    continue

                associated_tasks = tasks_by_challenge.get(challenge_id, [])
                self.console.print(f"  Found {len(associated_tasks)} associated task(s).")

                processed_backup = self._process_single_challenge(challenge_data, associated_tasks)

                # Generate safe filename
                safe_base = sanitize_filename(str(short_name))
                if not safe_base:
                    safe_base = (
                        f"challenge_{challenge_id}"  # Fallback if name was all invalid chars
                    )
                filename = f"{safe_base}.json"
                filepath = output_path / filename

                # Save using utility
                if save_json(data=processed_backup, filepath=filepath):
                    saved_count += 1
                else:
                    failed_count += 1  # save_json already prints errors

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
                f"\n[error]❌ Unexpected error during challenge backup: {e}[/error]"
            )
            # self.console.print_exception(show_locals=False) # Optional traceback

    # --- Internal Helper Methods ---
    # & - def _fetch_data(...)
    def _fetch_data(self) -> Tuple[Optional[List[Dict]], Optional[List[Dict]]]:
        """Fetches all user tasks and member challenges. Returns (tasks, challenges) or (None, None) on error."""
        tasks, challenges = None, None
        try:
            self.console.print("  Fetching all user tasks...")
            tasks = self.api_client.get_tasks()
            if not isinstance(tasks, list):
                self.console.print(
                    f"API Error: Expected list of tasks, got {type(tasks)}.", style="error"
                )
                tasks = None  # Signal error
            else:
                self.console.print(f"  Fetched {len(tasks)} tasks.")

            self.console.print("  Fetching member challenges...")
            challenges = self.api_client.get_challenges(member_only=True)
            if not isinstance(challenges, list):
                self.console.print(
                    f"API Error: Expected list of challenges, got {type(challenges)}.",
                    style="error",
                )
                challenges = None  # Signal error
            else:
                self.console.print(f"  Fetched {len(challenges)} challenges.")

            return tasks, challenges

        except requests.exceptions.RequestException as api_err:
            self.console.print(f"API Connection Error fetching data: {api_err}", style="error")
            return None, None
        except Exception as e:
            self.console.print(f"Unexpected Error fetching data: {e}", style="error")
            return None, None

    # & - def _group_tasks_by_challenge(...)
    def _group_tasks_by_challenge(self, tasks: Optional[List[Dict]]) -> Dict[str, List[Dict]]:
        """Groups tasks by challenge ID. Returns {challenge_id: [tasks]}."""
        self.console.print("  Grouping tasks by challenge ID...")
        tasks_by_challenge: Dict[str, List[Dict]] = {}
        if not isinstance(tasks, list):
            self.console.print(
                "Task list invalid for grouping. Returning empty map.", style="warning"
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
                    tasks_by_challenge.setdefault(c_id, []).append(task)
                    linked_count += 1
        self.console.print(
            f"  Processed {processed_count} tasks. Found {linked_count} linked to {len(tasks_by_challenge)} challenges."
        )
        return tasks_by_challenge

    # & - def _clean_task_for_backup(...)
    def _clean_task_for_backup(self, task_data: Dict) -> Dict:
        """Removes transient keys and processes emojis for task backup."""
        if not isinstance(task_data, dict):
            return {"error": "Invalid task data"}
        cleaned = task_data.copy()
        for key in self.TASK_KEYS_TO_REMOVE:
            cleaned.pop(key, None)
        if "text" in cleaned:
            cleaned["text"] = emoji_data_python.replace_colons(str(cleaned.get("text", "")))
        if "notes" in cleaned:
            cleaned["notes"] = emoji_data_python.replace_colons(str(cleaned.get("notes", "")))
        # Clean checklist items too
        if "checklist" in cleaned and isinstance(cleaned["checklist"], list):
            for item in cleaned["checklist"]:
                if isinstance(item, dict) and "text" in item:
                    item["text"] = emoji_data_python.replace_colons(str(item.get("text", "")))
        return cleaned

    # & - def _process_single_challenge(...)
    def _process_single_challenge(self, challenge_data: Dict, tasks_raw: List[Dict]) -> Dict:
        """Processes a single challenge and its tasks into backup format."""
        backup = challenge_data.copy()
        backup["_tasks"] = [
            self._clean_task_for_backup(task) for task in tasks_raw
        ]  # Embed cleaned tasks
        # Process text fields
        name = backup.pop("name", "Unnamed")
        desc = backup.pop("description", "")
        summary = backup.pop("summary", "")
        backup["_name"] = emoji_data_python.replace_colons(str(name))
        backup["_description"] = emoji_data_python.replace_colons(str(desc))
        if summary:
            backup["_summary"] = emoji_data_python.replace_colons(str(summary))
        return backup
