# pixabit/tag_manager.py
"""
Provides the TagManager class for managing Habitica tags and task attributes.

This module defines the `TagManager` class, which offers methods to enforce
consistency rules between different types of tags (e.g., challenge vs. personal),
ensure specific tags are present (e.g., 'poison status' tags), synchronize task
attributes (STR, INT, CON, PER) with corresponding tags, and identify/manage
unused tags. It relies on tag IDs loaded from the application's configuration.

Classes:
    TagManager: Manages tag consistency and attribute synchronization.
"""

from typing import Any, Dict, List, Set, Tuple

from rich.progress import (BarColumn, Progress, SpinnerColumn, TextColumn,
                           TimeElapsedColumn, TimeRemainingColumn)

from .api import HabiticaAPI
from .config import (  # Import required Tag IDs from config module
    ATTR_TAG_CON_ID, ATTR_TAG_INT_ID, ATTR_TAG_PER_ID, ATTR_TAG_STR_ID,
    CHALLENGE_TAG_ID, NO_ATTR_TAG_ID, NOT_PSN_TAG_ID, PERSONAL_TAG_ID,
    PSN_TAG_ID)
from .utils.display import Confirm, Table, console, print, track


class TagManager:
    """
    Manages and maintains consistency of tags and related attributes on tasks.

    Provides methods to perform bulk operations on tasks based on their tags
    and attributes, such as ensuring challenge tasks have the correct tags,
    synchronizing attribute tags with the task's 'attribute' field, managing
    'poison status' tags, and finding/deleting unused tags. It uses an API client
    to execute changes and requires specific Tag IDs to be configured.
    """

    def __init__(self, api_client: HabiticaAPI):
        """
        Initializes the TagManager.

        Args:
            api_client (HabiticaAPI): An authenticated instance of the HabiticaAPI
                                      client used to perform tag/task updates.
        """
        if not isinstance(api_client, HabiticaAPI):
            raise TypeError("api_client must be an instance of HabiticaAPI")
        self.api_client: HabiticaAPI = api_client
        self.console = getattr(
            api_client, "console", console
        )  # Example: reuse or create

        # Load necessary tag IDs from config module
        # These must be defined in config.py / loaded from .env
        self.challenge_tag: str | None = CHALLENGE_TAG_ID
        self.personal_tag: str | None = PERSONAL_TAG_ID
        self.psn_tag: str | None = PSN_TAG_ID
        self.not_psn_tag: str | None = NOT_PSN_TAG_ID
        self.no_attr_tag: str | None = NO_ATTR_TAG_ID

        # Map Attribute Tag IDs to their corresponding attribute strings
        self.attr_tag_map: Dict[str | None, str] = {
            ATTR_TAG_STR_ID: "str",
            ATTR_TAG_INT_ID: "int",
            ATTR_TAG_CON_ID: "con",
            ATTR_TAG_PER_ID: "per",
        }
        # Filter out None keys in case some attribute tags aren't configured
        self.attr_tag_map = {
            k: v for k, v in self.attr_tag_map.items() if k is not None
        }

        # Inverse map might be useful for finding the tag for a given attribute
        self.attr_to_tag_map: Dict[str, str | None] = {
            v: k for k, v in self.attr_tag_map.items()
        }

        print("[bold blue]TagManager initialized.[/]")
        self._validate_config()  # Check if essential tags are loaded

    def _validate_config(self):
        """Checks if essential tag IDs loaded correctly from config."""
        essential_tags = {
            "CHALLENGE_TAG_ID": self.challenge_tag,
            "PERSONAL_TAG_ID": self.personal_tag,
            # Add others that are absolutely required by functions you use
        }
        missing = [name for name, value in essential_tags.items() if not value]
        if missing:
            print(
                f"[bold yellow]Warning: Essential Tag Manager tag IDs not configured in .env: {', '.join(missing)}. Related functions may be skipped or fail.[/]"
            )

    # --- Action Execution Helper ---

    def _confirm_and_execute_actions(
        self, actions: List[Tuple[str, str, str]], description: str
    ) -> None:
        """
        Helper method to confirm and execute a list of API actions with progress.

        Takes a list of actions, where each action is a tuple:
        `(action_type: str, task_id: str, target_id_or_value: str)`.
        Supported `action_type`s: 'add_tag', 'delete_tag', 'set_attribute'.
        For 'set_attribute', `target_id_or_value` is the attribute string ('str', 'int', etc.).
        For tag actions, `target_id_or_value` is the Tag ID.

        Estimates execution time based on Habitica rate limits (approx. 2s/action).
        Prompts the user for confirmation before executing. Shows progress using Rich `track`.

        Args:
            actions (List[Tuple[str, str, str]]): A list of action tuples to perform.
            description (str): A description of the batch operation (e.g., "Challenge Tag Sync").

        Returns:
            None
        """
        fix_count = len(actions)
        if fix_count == 0:
            self.console.print(f"{description}: All OK :thumbs_up:")
            return

        # Estimate time (Habitica rate limit: 30/min => 2 sec/request)
        est_seconds = fix_count * 2.0
        if est_seconds > 120:  # More than 2 minutes
            est_time_str = f"[cyan]{est_seconds / 60:.1f} minutes[/cyan]"
        else:
            est_time_str = f"[cyan]{est_seconds:.1f} seconds[/cyan]"

        self.console.print(
            f"{description}: Found {fix_count} actions needed. Estimated time: {est_time_str}"
        )

        if Confirm.ask("Apply changes?", default=False, console=self.console):
            error_count = 0
            # --- Use rich.progress.Progress ---
            progress_cols = [
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                SpinnerColumn("dots"),  # Choose a spinner
                TextColumn("• Elapsed:"),
                TimeElapsedColumn(),
                TextColumn("• Remaining:"),
                TimeRemainingColumn(),
            ]
            # transient=True makes the bar disappear on completion
            with Progress(
                *progress_cols, console=self.console, transient=False
            ) as progress:
                # Add one task representing the whole batch
                batch_task_id = progress.add_task(description, total=fix_count)

                for i, (action, task_id, target_id) in enumerate(actions):
                    # Optionally update description to show current item
                    progress.update(
                        batch_task_id,
                        description=f"{description} ({i+1}/{fix_count}) - {task_id}",
                    )
                    try:
                        # --- Perform API Call via self.api_client ---
                        if action == "add_tag":
                            self.api_client.add_tag(task_id, target_id)
                        elif action == "delete_tag":
                            self.api_client.delete_tag(task_id, target_id)
                        elif action == "set_attribute":
                            self.api_client.set_attribute(task_id, target_id)
                        # Add other actions if needed ('unlink', etc.)
                        else:
                            # Use progress.console for printing errors within the bar context
                            progress.console.print(
                                f"\nWarning: Unknown action '{action}' for task {task_id}"
                            )
                            error_count += 1

                    except Exception as e:
                        progress.console.print(
                            f"\n[red]Error: {action} on {task_id} ({target_id}): {e}[/red]"
                        )
                        error_count += 1
                    finally:
                        # Advance progress even if there was an error
                        progress.update(batch_task_id, advance=1)
            # --- End of Progress ---

            if error_count == 0:
                self.console.print(
                    f"[bold green]{description}: Completed successfully! :cherry_blossom:"
                )
            else:
                self.console.print(
                    f"[bold yellow]{description}: Completed with {error_count} errors.[/bold yellow]"
                )
        else:
            self.console.print("[b]OK, no changes were made. :cherry_blossom:")

    # ... (Rest of TagManager methods that call _confirm_and_execute_actions) ...

    # --- Tag Consistency Methods ---

    def sync_challenge_personal_tags(
        self, processed_tasks: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Ensures challenge tasks have challenge_tag (not personal_tag) and vice versa.

        Iterates through processed tasks and applies these rules:
        1. If task is a challenge task (`challenge_id` is present), ensure
           `challenge_tag` exists and `personal_tag` does NOT exist.
        2. If task is NOT a challenge task, ensure `challenge_tag` does NOT
           exist and `personal_tag` DOES exist.

        Requires `challenge_tag` and `personal_tag` IDs to be configured.

        Args:
            processed_tasks (Dict[str, Dict[str, Any]]): A dictionary where keys are
                task IDs and values are processed task data dictionaries. Each task
                dict should contain 'tag_id' (list of tag IDs) and 'challenge_id'.
        """
        description = "Challenge/Personal Tag Sync"
        if not self.challenge_tag or not self.personal_tag:
            print(
                f"[yellow]Skipping '{description}': CHALLENGE_TAG_ID or PERSONAL_TAG_ID not configured.[/]"
            )
            return

        actions: List[Tuple[str, str, str]] = []
        for task_id, task_data in processed_tasks.items():
            tags = set(task_data.get("tag_id", []))  # Use set for efficient checking
            # Use processed 'challenge_id' field which should be reliable
            is_challenge_task = bool(task_data.get("challenge_id"))

            # --- Apply Rules ---
            # Rule 1: Challenge task MUST have challenge_tag
            if is_challenge_task and self.challenge_tag not in tags:
                actions.append(("add_tag", task_id, self.challenge_tag))
            # Rule 2: Challenge task MUST NOT have personal_tag
            if is_challenge_task and self.personal_tag in tags:
                actions.append(("delete_tag", task_id, self.personal_tag))
            # Rule 3: Personal task MUST NOT have challenge_tag
            if not is_challenge_task and self.challenge_tag in tags:
                actions.append(("delete_tag", task_id, self.challenge_tag))
            # Rule 4: Personal task MUST have personal_tag
            if not is_challenge_task and self.personal_tag not in tags:
                actions.append(("add_tag", task_id, self.personal_tag))

        self._confirm_and_execute_actions(actions, description)

    def ensure_poison_status_tags(
        self, processed_tasks: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Ensures tasks have either psn_tag or not_psn_tag, defaulting to not_psn_tag.

        If a task has neither the 'Poisoned' (`psn_tag`) nor the 'Not Poisoned'
        (`not_psn_tag`) tag, this function adds the `not_psn_tag` as a default.
        It assumes tasks should always have one of these two statuses explicitly tagged.

        Requires `psn_tag` and `not_psn_tag` IDs to be configured.

        Args:
            processed_tasks (Dict[str, Dict[str, Any]]): A dictionary of processed
                task data, where each task dict contains 'tag_id' (list).
        """
        description = "Poison Status Tag Check"
        # Check if tags are configured
        if not self.psn_tag or not self.not_psn_tag:
            print(
                f"[yellow]Skipping '{description}': PSN_TAG_ID or NOT_PSN_TAG_ID not configured.[/]"
            )
            return

        actions: List[Tuple[str, str, str]] = []
        for task_id, task_data in processed_tasks.items():
            tags = set(task_data.get("tag_id", []))
            has_psn = self.psn_tag in tags
            has_not_psn = self.not_psn_tag in tags

            if not has_psn and not has_not_psn:
                # If neither tag is present, add the default 'not poisoned' tag
                actions.append(("add_tag", task_id, self.not_psn_tag))
            # Optional: Rule for mutual exclusivity - If both are present, remove one?
            # elif has_psn and has_not_psn:
            #     print(f"[yellow]Warning: Task {task_id} has both PSN and NOT_PSN tags. Removing NOT_PSN.[/]")
            #     actions.append(("delete_tag", task_id, self.not_psn_tag))

        self._confirm_and_execute_actions(actions, description)

    def sync_attributes_to_tags(
        self, processed_tasks: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Ensures task 'attribute' field matches attribute tags, handling conflicts.

        Compares the task's 'attribute' field ('str', 'int', 'con', 'per', or None)
        with the presence of corresponding attribute tags (loaded from config).
        - If multiple attribute tags exist, removes them and adds `no_attr_tag`.
        - If exactly one attribute tag exists, ensures the task's 'attribute' field
          matches it and removes `no_attr_tag`.
        - If no attribute tags exist, ensures `no_attr_tag` is present.

        Requires attribute tags (`ATTR_TAG_*_ID`) and `no_attr_tag` ID to be configured.

        Args:
            processed_tasks (Dict[str, Dict[str, Any]]): A dictionary of processed
                task data, where each task dict contains 'tag_id' (list) and 'attribute'.
        """
        description = "Attribute Sync with Tags"
        # Check if tags are configured
        if not self.attr_tag_map or not self.no_attr_tag:
            print(
                f"[yellow]Skipping '{description}': Attribute tags (ATTR_TAG_*) or NO_ATTR_TAG_ID not fully configured.[/]"
            )
            return

        actions: List[Tuple[str, str, str]] = []
        all_attr_tags: Set[str] = set(
            self.attr_tag_map.keys()
        )  # Set of configured ATTR_* tags

        for task_id, task_data in processed_tasks.items():
            tags: Set[str] = set(task_data.get("tag_id", []))
            current_attribute: str | None = task_data.get(
                "attribute"
            )  # Can be 'str', 'int', ..., or None

            # Find which attribute tags are present on this task
            present_attr_tags: Set[str] = tags.intersection(all_attr_tags)
            num_present = len(present_attr_tags)
            has_no_attr_tag = self.no_attr_tag in tags

            if num_present > 1:
                # Conflict: Multiple attribute tags found. Enforce NO_ATTR.
                print(
                    f"[yellow]Warning: Task {task_id} ({task_data.get('text', 'N/A')}) has conflicting attribute tags: {present_attr_tags}. Applying '{self.no_attr_tag}'.[/]"
                )
                # Add NO_ATTR tag if not present
                if not has_no_attr_tag:
                    actions.append(("add_tag", task_id, self.no_attr_tag))
                # Remove all conflicting attribute tags
                for conflicting_tag in present_attr_tags:
                    actions.append(("delete_tag", task_id, conflicting_tag))
                # Optional: Set attribute field to default? Let's set to 'str' if it has conflicting tags.
                # if current_attribute: # Only change if it wasn't already None/default
                #     actions.append(("set_attribute", task_id, "str")) # Set to default 'str'

            elif num_present == 1:
                # Exactly one attribute tag found. Enforce match with attribute field.
                attr_tag = present_attr_tags.pop()  # Get the single tag
                correct_attribute = self.attr_tag_map[attr_tag]

                # Remove NO_ATTR tag if it's incorrectly present
                if has_no_attr_tag:
                    actions.append(("delete_tag", task_id, self.no_attr_tag))

                # Check if task's attribute field needs updating
                if current_attribute != correct_attribute:
                    actions.append(("set_attribute", task_id, correct_attribute))

            else:  # num_present == 0
                # No attribute tags found. Enforce NO_ATTR tag.
                if not has_no_attr_tag:
                    actions.append(("add_tag", task_id, self.no_attr_tag))
                # Optional: Ensure attribute field is default ('str') if no tag?
                # Let's enforce 'str' if attribute is currently set to something else.
                # if current_attribute not in [None, "str"]: # Check if it's set to int/con/per without a tag
                #      actions.append(("set_attribute", task_id, "str")) # Reset attribute to default 'str'

        self._confirm_and_execute_actions(actions, description)

    # --- Utility / Other Tag Methods ---

    def add_or_replace_tag_based_on_other(
        self,
        processed_tasks: Dict[str, Dict[str, Any]],
        tag_to_find: str,
        tag_to_add: str,
        replace: bool = False,
    ) -> None:
        """
        Adds `tag_to_add` if `tag_to_find` exists. Optionally removes `tag_to_find`.

        Iterates through tasks. If a task has `tag_to_find`:
        - Adds `tag_to_add` (if not already present).
        - If `replace` is True, also removes `tag_to_find`.

        Args:
            processed_tasks (Dict[str, Dict[str, Any]]): Dictionary of processed tasks.
            tag_to_find (str): The Tag ID to look for on tasks.
            tag_to_add (str): The Tag ID to add to tasks where `tag_to_find` exists.
            replace (bool): If True, remove `tag_to_find` after adding `tag_to_add`.
                            Defaults to False.

        Returns:
            None
        """
        if not tag_to_find or not tag_to_add:
            print(
                "[bold red]Error in add_or_replace_tag: Both 'tag_to_find' and 'tag_to_add' must be valid Tag IDs.[/]"
            )
            return

        actions: List[Tuple[str, str, str]] = []
        action_desc = (
            f"Replacing tag ID '{tag_to_find}' with '{tag_to_add}'"
            if replace
            else f"Adding tag ID '{tag_to_add}' where '{tag_to_find}' exists"
        )

        for task_id, task_data in processed_tasks.items():
            tags = set(task_data.get("tag_id", []))
            if tag_to_find in tags:
                # Add the new tag if it's not already there
                if tag_to_add not in tags:
                    actions.append(("add_tag", task_id, tag_to_add))
                # If replacing, also schedule deletion of the old tag
                if replace:
                    # Ensure we don't try to delete the tag we just added if they are the same
                    if tag_to_find != tag_to_add:
                        actions.append(("delete_tag", task_id, tag_to_find))

        self._confirm_and_execute_actions(actions, action_desc)

    def find_unused_tags(
        self,
        all_tags: List[Dict[str, Any]],  # Expects list of {'id': ..., 'name': ...}
        used_tag_ids: Set[str],
    ) -> List[Dict[str, Any]]:
        """
        Identifies tags from a list that are not present in a set of used tag IDs.

        Args:
            all_tags (List[Dict[str, Any]]): A list of all tag dictionaries fetched
                                             from the API (each dict should have 'id' and 'name').
            used_tag_ids (Set[str]): A set containing the IDs of all tags that are
                                     currently assigned to at least one task.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries for tags found in `all_tags`
                                  but not in `used_tag_ids`. Each dict contains 'id'
                                  and 'name'. Returns an empty list if none are found.
        """
        unused_tags: List[Dict[str, Any]] = []
        print("Finding unused tags...")
        if not isinstance(used_tag_ids, set):
            print("[yellow]Warning: used_tag_ids should be a set for efficiency.[/]")
            used_tag_ids = set(used_tag_ids)  # Convert if needed

        for tag in all_tags:
            tag_id = tag.get("id")
            if tag_id and tag_id not in used_tag_ids:
                # Return a simple dict with id and name for clarity
                unused_tags.append({"id": tag_id, "name": tag.get("name", "N/A")})

        print(f"Found {len(unused_tags)} potentially unused tags.")
        return unused_tags

    def delete_unused_tags_interactive(
        self, all_tags: List[Dict[str, Any]], used_tag_ids: Set[str]
    ) -> None:
        """
        Finds unused tags and interactively asks the user to delete them.

        Calls `find_unused_tags` to get the list. If any are found, it prints
        them and asks for confirmation before attempting to delete them globally
        via the API.

        Note: Global tag deletion might require a specific API endpoint not yet
        implemented in the base `HabiticaAPI` client (`delete_tag` usually removes
        a tag *from a task*). This method currently prepares actions assuming
        a hypothetical "delete_tag_global" action. **Adjust if API differs.**

        Args:
            all_tags (List[Dict[str, Any]]): List of all tag dictionaries from API.
            used_tag_ids (Set[str]): Set of IDs of tags currently in use.

        Returns:
            None
        """
        description = "Deleting Unused Tags"
        unused_tags_list = self.find_unused_tags(all_tags, used_tag_ids)

        if not unused_tags_list:
            print(f"[green]{description}: No unused tags found.[/]")
            return

        print("\n[bold yellow]--- Potentially Unused Tags ---[/]")
        # Display unused tags clearly before asking
        table = Table(title="Unused Tags Found", show_lines=True)
        table.add_column("Num", style="dim", width=4, justify="right")
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="magenta")
        for i, tag in enumerate(unused_tags_list):
            table.add_row(str(i + 1), tag["name"], tag["id"])
        print(table)

        # Ask for confirmation to delete ALL listed tags
        if Confirm.ask(
            "\n[bold red]Delete ALL[/] these unused tags permanently from Habitica?",
            default=False,
        ):
            # --- IMPORTANT ---
            # This assumes a global tag delete API call exists and is mapped to "delete_tag_global".
            # If Habitica API only allows deleting tags from tasks, this approach won't work
            # for global deletion. You might need to manually delete them on the website,
            # or the API might auto-delete tags when they become truly unused (check docs).
            # Using "delete_tag" action here would try to remove tag_id from task_id=tag_id which is wrong.
            print(
                "[bold yellow]Warning: Global tag deletion requires a specific API endpoint. Ensure 'delete_tag_global' action is correctly implemented in the API client.[/]"
            )
            # Prepare actions assuming a hypothetical global delete action
            actions: List[Tuple[str, str, str]] = []
            for tag in unused_tags_list:
                # Action type, Item ID (Tag ID), Target (can be None or tag ID)
                actions.append(("delete_tag_global", tag["id"], tag["id"]))

            # Check if any actions were actually prepared
            if actions:
                self._confirm_and_execute_actions(actions, description)
            else:
                print(
                    f"[yellow]{description}: No delete actions prepared (check implementation).[/]"
                )

        else:
            print(f"[yellow]{description}: No tags were deleted.[/]")


# End of TagManager class
