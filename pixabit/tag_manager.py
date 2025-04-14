# pixabit/tag_manager.py
# MARK: - MODULE DOCSTRING
"""Provides TagManager class for managing Habitica tags and task attributes.

Enforces consistency rules (challenge vs. personal), ensures status tags
(poison), synchronizes attributes (STR, INT etc.) with tags, identifies/manages
unused tags. Relies on tag IDs from config and uses API client for modifications.
Checks config to enable/disable optional features gracefully.
"""

# MARK: - IMPORTS
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

# Local Imports
from .api import HabiticaAPI

# Import specific, configured tag IDs directly from config
from .config import (  # Use the generated map
    ATTR_TAG_MAP,
    CHALLENGE_TAG_ID,
    NO_ATTR_TAG_ID,
    NOT_PSN_TAG_ID,
    PERSONAL_TAG_ID,
    PSN_TAG_ID,
)

# Use themed display components
from .utils.display import (
    BarColumn,
    Confirm,
    Progress,
    SpinnerColumn,
    Table,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    box,  # No track needed if using Progress
    console,
)


# MARK: - CLASS DEFINITION
class TagManager:
    """Manages consistency of tags and related attributes on tasks.

    Provides methods for bulk operations based on tags/attributes. Requires
    specific Tag IDs configured via `config.py`/.env. Checks config availability.
    """

    # & - def __init__(self, api_client: HabiticaAPI):
    def __init__(self, api_client: HabiticaAPI):
        """Initializes TagManager, loads configured tag IDs, checks status."""
        if not isinstance(api_client, HabiticaAPI):
            raise TypeError("`api_client` must be an instance of HabiticaAPI")

        self.api_client: HabiticaAPI = api_client
        self.console = console  # Use themed console

        # --- Load Optional Tag IDs from Config ---
        self.challenge_tag: Optional[str] = CHALLENGE_TAG_ID
        self.personal_tag: Optional[str] = PERSONAL_TAG_ID
        self.psn_tag: Optional[str] = PSN_TAG_ID
        self.not_psn_tag: Optional[str] = NOT_PSN_TAG_ID
        self.no_attr_tag: Optional[str] = NO_ATTR_TAG_ID

        # Use the pre-built map from config.py
        self.attr_tag_map: Dict[str, str] = ATTR_TAG_MAP
        self.attr_to_tag_map: Dict[str, str] = {v: k for k, v in self.attr_tag_map.items()}

        self.console.log("TagManager initialized.", style="info")
        self._log_config_status()

    # & - def _log_config_status(self):
    def _log_config_status(self):
        """Logs the status of optional tag configurations."""
        status = []
        # Check if BOTH required tags for a feature are set
        status.append(
            f"Challenge/Personal: {'✅ Configured' if self.challenge_tag and self.personal_tag else '❌ Off'}"
        )
        status.append(
            f"Poison Status: {'✅ Configured' if self.psn_tag and self.not_psn_tag else '❌ Off'}"
        )
        # For attributes, check the map AND the no_attr tag
        status.append(
            f"Attributes: {'✅ Configured' if self.attr_tag_map and self.no_attr_tag else '❌ Off'}"
        )
        self.console.log(f"Tag Feature Status - {', '.join(status)}", style="subtle")

    # MARK: - Action Execution Helper
    # & - def _confirm_and_execute_actions(...)
    def _confirm_and_execute_actions(
        self, actions: List[Tuple[str, str, str]], description: str
    ) -> bool:
        """Confirms and executes a list of API actions with progress display.

        Handles 'add_tag', 'delete_tag', 'set_attribute', 'delete_tag_global'.

        Returns:
            bool: True if changes were attempted (regardless of errors), False if cancelled.
        """
        fix_count = len(actions)
        if fix_count == 0:
            self.console.print(
                f"[success]✅ {description}: All conform. No actions needed.[/success]"
            )
            return False

        est_seconds = fix_count * (
            self.api_client.request_interval + 0.1
        )  # Use API client interval
        est_time_str = (
            f"{est_seconds / 60:.1f} minutes"
            if est_seconds > 120
            else f"{est_seconds:.1f} seconds"
        )
        self.console.print(
            f"🔎 [warning]{description}:[/] Found [keyword]{fix_count}[/] action(s) needed. Est. time: {est_time_str}"
        )

        if not Confirm.ask(f"Apply these {fix_count} changes?", default=False):
            self.console.print("[warning]❌ Operation cancelled. No changes made.[/warning]")
            return False

        # --- Execute with Progress Bar ---
        error_count = 0
        progress_cols = [  # Use theme styles for progress
            TextColumn("[progress.description]{task.description}"),
            BarColumn(style="rp_surface", complete_style="rp_foam"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%", style="rp_foam"),
            SpinnerColumn("dots", style="rp_iris"),
            TextColumn("• Elapsed:"),
            TimeElapsedColumn(),
            TextColumn("• Remain:"),
            TimeRemainingColumn(),
        ]
        with Progress(*progress_cols, console=self.console, transient=False) as progress:
            batch_task_id = progress.add_task(description, total=fix_count)
            for i, (action, item_id, target) in enumerate(actions):
                progress.update(batch_task_id, description=f"{description} ({i+1}/{fix_count})")
                try:
                    if action == "add_tag":
                        self.api_client.add_tag_to_task(item_id, target)
                    elif action == "delete_tag":
                        self.api_client.delete_tag_from_task(item_id, target)
                    elif action == "set_attribute":
                        self.api_client.set_attribute(task_id=item_id, attribute=target)
                    elif action == "delete_tag_global":
                        # CRITICAL: Assumes global delete implemented in API client
                        self.api_client.delete_tag(item_id)  # Calls DELETE /tags/{tagId}
                    else:
                        progress.console.print(
                            f"\n[warning]⚠️ Unknown action '{action}' for item {item_id}. Skipping.[/]"
                        )
                        error_count += 1
                except requests.exceptions.RequestException as e:
                    progress.console.print(
                        f"\n[error]❌ API Error ({action} on {item_id}): {e}[/]"
                    )
                    error_count += 1
                except Exception as e:
                    progress.console.print(
                        f"\n[error]❌ Unexpected Error ({action} on {item_id}): {e}[/]"
                    )
                    error_count += 1
                finally:
                    progress.update(batch_task_id, advance=1)
                    # time.sleep(0.05) # Small delay optional

        # --- End Progress ---
        self.console.rule(style="rp_overlay")
        if error_count == 0:
            self.console.print(f"[success]✅ {description}: Completed successfully![/success]")
        else:
            self.console.print(
                f"[warning]⚠️ {description}: Completed with {error_count} error(s).[/warning]"
            )
        self.console.rule(style="rp_overlay")
        return True  # Changes were attempted

    # MARK: - Tag Consistency Methods
    # & - def sync_challenge_personal_tags(...)
    def sync_challenge_personal_tags(self, processed_tasks: Dict[str, Dict[str, Any]]) -> bool:
        """Ensures tasks have mutually exclusive challenge/personal tags."""
        description = "Challenge/Personal Tag Sync"
        if not self.challenge_tag or not self.personal_tag:
            self.console.print(f"[info]ℹ️ Skipping '{description}': Tags not configured.[/info]")
            return False
        if not isinstance(processed_tasks, dict):
            self.console.print(f"[error]❌ Skipping '{description}': Invalid input.[/error]")
            return False

        actions: List[Tuple[str, str, str]] = []
        for task_id, task_data in processed_tasks.items():
            if not isinstance(task_data, dict):
                continue
            tags = set(task_data.get("tags", []))  # Use raw tags list from processed data
            is_challenge = bool(task_data.get("challenge_id"))
            # Rule 1a: Challenge task MUST have challenge_tag
            if is_challenge and self.challenge_tag not in tags:
                actions.append(("add_tag", task_id, self.challenge_tag))
            # Rule 1b: Challenge task MUST NOT have personal_tag
            if is_challenge and self.personal_tag in tags:
                actions.append(("delete_tag", task_id, self.personal_tag))
            # Rule 2a: Personal task MUST have personal_tag
            if not is_challenge and self.personal_tag not in tags:
                actions.append(("add_tag", task_id, self.personal_tag))
            # Rule 2b: Personal task MUST NOT have challenge_tag
            if not is_challenge and self.challenge_tag in tags:
                actions.append(("delete_tag", task_id, self.challenge_tag))

        return self._confirm_and_execute_actions(actions, description)

    # & - def ensure_poison_status_tags(...)
    def ensure_poison_status_tags(self, processed_tasks: Dict[str, Dict[str, Any]]) -> bool:
        """Ensures tasks have either psn_tag or not_psn_tag, defaulting to not_psn_tag."""
        description = "Poison Status Tag Check"
        if not self.psn_tag or not self.not_psn_tag:
            self.console.print(f"[info]ℹ️ Skipping '{description}': Tags not configured.[/info]")
            return False
        if not isinstance(processed_tasks, dict):
            self.console.print(f"[error]❌ Skipping '{description}': Invalid input.[/error]")
            return False

        actions: List[Tuple[str, str, str]] = []
        for task_id, task_data in processed_tasks.items():
            if not isinstance(task_data, dict):
                continue
            tags = set(task_data.get("tags", []))
            has_psn, has_not_psn = self.psn_tag in tags, self.not_psn_tag in tags
            # Add default NOT_PSN if neither is present
            if not has_psn and not has_not_psn:
                actions.append(("add_tag", task_id, self.not_psn_tag))
            # Optional: If both present, remove NOT_PSN (assume PSN takes priority)
            # elif has_psn and has_not_psn: actions.append(("delete_tag", task_id, self.not_psn_tag))

        return self._confirm_and_execute_actions(actions, description)

    # & - def sync_attributes_to_tags(...)
    def sync_attributes_to_tags(self, processed_tasks: Dict[str, Dict[str, Any]]) -> bool:
        """Synchronizes task 'attribute' field with configured attribute tags."""
        description = "Attribute Sync (Field <-> Tags)"
        if not self.attr_tag_map or not self.no_attr_tag:
            self.console.print(
                f"[info]ℹ️ Skipping '{description}': Attribute/NoAttr tags not fully configured.[/info]"
            )
            return False
        if not isinstance(processed_tasks, dict):
            self.console.print(f"[error]❌ Skipping '{description}': Invalid input.[/error]")
            return False

        actions: List[Tuple[str, str, str]] = []
        all_attr_tags: Set[str] = set(self.attr_tag_map.keys())

        for task_id, task_data in processed_tasks.items():
            if not isinstance(task_data, dict):
                continue
            tags: Set[str] = set(task_data.get("tags", []))
            current_attribute: Optional[str] = task_data.get("attribute")
            present_attr_tags: Set[str] = tags.intersection(all_attr_tags)
            num_present = len(present_attr_tags)
            has_no_attr_tag = self.no_attr_tag in tags

            if num_present > 1:  # Conflict -> Apply NO_ATTR
                if not has_no_attr_tag:
                    actions.append(("add_tag", task_id, self.no_attr_tag))
                for tag in present_attr_tags:
                    actions.append(("delete_tag", task_id, tag))
                # Reset attribute field to default 'str' if it had a specific one
                if current_attribute and current_attribute != "str":
                    actions.append(("set_attribute", task_id, "str"))
            elif num_present == 1:  # Single ATTR tag -> Ensure field matches, remove NO_ATTR
                attr_tag = present_attr_tags.pop()
                correct_attribute = self.attr_tag_map[attr_tag]
                if has_no_attr_tag:
                    actions.append(("delete_tag", task_id, self.no_attr_tag))
                if current_attribute != correct_attribute:
                    actions.append(("set_attribute", task_id, correct_attribute))
            else:  # No ATTR tags -> Ensure NO_ATTR tag, ensure field is 'str' (default)
                if not has_no_attr_tag:
                    actions.append(("add_tag", task_id, self.no_attr_tag))
                # If attribute field currently has a non-default value without a tag, reset it
                if current_attribute and current_attribute != "str":
                    actions.append(("set_attribute", task_id, "str"))

        return self._confirm_and_execute_actions(actions, description)

    # MARK: - Utility / Other Tag Methods
    # & - def add_or_replace_tag_based_on_other(...)
    def add_or_replace_tag_based_on_other(
        self,
        tasks_dict: Dict[str, Dict[str, Any]],
        find_tag_id: str,
        add_tag_id: str,
        remove_original: bool = False,
    ) -> bool:
        """Adds `add_tag_id` if `find_tag_id` exists. Optionally removes `find_tag_id`."""
        if not find_tag_id or not add_tag_id:
            self.console.print(
                "[error]❌ Error: Both 'find_tag_id' and 'add_tag_id' must be provided.[/error]"
            )
            return False
        if not isinstance(tasks_dict, dict):
            self.console.print("[error]❌ Error: Invalid `tasks_dict` input.[/error]")
            return False

        actions: List[Tuple[str, str, str]] = []
        mode = "Replacing" if remove_original else "Adding"
        # Use styles for tag IDs in description
        action_desc = f"{mode} tag '[rp_foam]{add_tag_id}[/]' based on '[rp_rose]{find_tag_id}[/]'"

        for task_id, task_data in tasks_dict.items():
            if not isinstance(task_data, dict):
                continue
            tags = set(task_data.get("tags", []))
            if find_tag_id in tags:
                if add_tag_id not in tags:
                    actions.append(("add_tag", task_id, add_tag_id))
                if remove_original and find_tag_id != add_tag_id:
                    actions.append(("delete_tag", task_id, find_tag_id))

        return self._confirm_and_execute_actions(actions, action_desc)

    # & - def find_unused_tags(...)
    def find_unused_tags(
        self, all_tags: List[Dict[str, Any]], used_tag_ids: Set[str]
    ) -> List[Dict[str, Any]]:
        """Identifies tags not present in the `used_tag_ids` set."""
        unused_tags: List[Dict[str, Any]] = []
        self.console.print("🔎 Finding unused tags...", style="info")

        if not isinstance(used_tag_ids, set):
            self.console.print(
                "[warning]⚠️ `used_tag_ids` not a set, converting for efficiency.[/warning]"
            )
            try:
                used_tag_ids = set(used_tag_ids)
            except TypeError:
                self.console.print(
                    "[error]❌ Invalid `used_tag_ids`. Cannot find unused tags.[/error]"
                )
                return []
        if not isinstance(all_tags, list):
            self.console.print("[error]❌ Invalid `all_tags` list.[/error]")
            return []

        for tag in all_tags:
            if not isinstance(tag, dict):
                continue
            tag_id = tag.get("id")
            if tag_id and tag_id not in used_tag_ids:
                unused_tags.append({"id": tag_id, "name": tag.get("name", "[dim]N/A[/dim]")})

        self.console.print(
            f"[success]✅ Found {len(unused_tags)} potentially unused tags.[/success]"
        )
        return unused_tags

    # & - def delete_unused_tags_interactive(...) -> bool:
    def delete_unused_tags_interactive(
        self, all_tags: List[Dict[str, Any]], used_tag_ids: Set[str]
    ) -> bool:
        """Finds unused tags and interactively asks user to delete them globally."""
        description = "Deleting Unused Tags"
        unused = self.find_unused_tags(all_tags, used_tag_ids)
        if not unused:
            self.console.print(f"[success]✅ {description}: No unused tags found.[/success]")
            return False

        # --- Display ---
        self.console.print("\n[warning]--- Potentially Unused Tags ---[/warning]")
        table = Table(title="Unused Tags", box=box.ROUNDED, border_style="warning")
        table.add_column("Num", style="subtle", width=4)
        table.add_column("Name", style="rp_foam")
        table.add_column("ID", style="rp_rose")
        for i, tag in enumerate(unused):
            table.add_row(str(i + 1), tag["name"], tag["id"])
        self.console.print(table)

        # --- Confirmation & Action ---
        if Confirm.ask(
            "\n[error]Delete ALL[/] listed unused tags permanently from Habitica?\n"
            "[warning]⚠️ This action is IRREVERSIBLE and deletes the tag globally, not just from tasks![/]",
            default=False,
        ):
            # Prepare actions using 'delete_tag_global' type
            actions = [("delete_tag_global", tag["id"], tag["id"]) for tag in unused]
            if actions:
                self.console.print("[warning]Proceeding with global tag deletion...[/warning]")
                return self._confirm_and_execute_actions(actions, description)
            else:
                self.console.print(
                    f"[warning]⚠️ {description}: No delete actions prepared.[/warning]"
                )
                return False  # No action attempted
        else:
            self.console.print(f"[warning]❌ {description}: No tags were deleted.[/warning]")
            return False  # User cancelled


# --- End of TagManager class ---
