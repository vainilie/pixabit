# pixabit/cli/app.py
# MARK: - MODULE DOCSTRING
"""Main Command Line Interface application class for Pixabit.
Handles user interaction, menu navigation, data fetching/refreshing,
and dispatching actions to underlying managers and processors, respecting
optional feature configurations.
"""

# MARK: - IMPORTS
import builtins
import datetime
import difflib
import json  # Keep for debug dumping if needed
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import timeago

# --- Rich and Display ---
try:
    from pixabit.utils.display import (
        BarColumn,
        Confirm,
        IntPrompt,
        Live,
        Panel,
        Progress,
        Prompt,
        Rule,
        SpinnerColumn,
        Table,
        TaskProgressColumn,
        Text,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
        box,
        console,
        print,
        track,
    )
except ImportError as e_rich:
    # Use standard print for this critical failure
    builtins.print(f"Fatal Error: Failed to import Rich components: {e_rich}")
    builtins.print("Please install Rich: pip install rich")
    sys.exit(1)

# --- Local Application Imports ---
try:
    from pixabit import config  # Import config to check optional tags
    from pixabit.api import MIN_REQUEST_INTERVAL, HabiticaAPI  # Import constant
    from pixabit.challenge_backupper import ChallengeBackupper  # Correct class name/file
    from pixabit.config_tags import configure_tags as run_tag_config_setup  # Alias for clarity
    from pixabit.data_processor import TaskProcessor, get_user_stats
    from pixabit.exports import (  # Import export functions
        save_all_userdata_into_json,
        save_processed_tasks_into_json,
        save_tags_into_json,
        save_tasks_without_proccessing,
    )
    from pixabit.tag_manager import TagManager
    from pixabit.utils.dates import convert_to_local_time
except ImportError as e_imp:
    # Use standard print as console might not be ready
    builtins.print(f"Fatal Error importing Pixabit modules: {e_imp}")
    sys.exit(1)


# MARK: - CliApp Class
# ==============================================================================
class CliApp:
    """Main application class for the Pixabit CLI."""

    # MARK: - Initialization
    # & - def __init__(self):
    def __init__(self):
        """Initializes API client, managers, state, and performs initial data load."""
        self.console = console
        self.console.log("Initializing Pixabit App...", style="info")
        try:
            self.api_client = HabiticaAPI()  # Handles mandatory credential check
            self.processor: Optional[TaskProcessor] = None  # Initialized in refresh_data
            self.tag_manager = TagManager(self.api_client)  # Logs its own config status
            self.backupper = ChallengeBackupper(self.api_client)
            self.console.log("Core components initialized.", style="info")
        except ValueError as e:  # Catch missing mandatory creds from API init
            self.console.print(f"Configuration Error: {e}", style="error")
            sys.exit(1)
        except Exception:
            self.console.print("Unexpected Initialization Error:", style="error")
            self.console.print_exception(show_locals=False)
            sys.exit(1)

        # --- Application State Attributes ---
        self.user_data: Dict[str, Any] = {}
        self.party_data: Dict[str, Any] = {}
        self.content_data: Dict[str, Any] = {}
        self.all_tags: List[Dict] = []
        self.processed_tasks: Dict[str, Dict] = {}
        self.cats_data: Dict[str, Any] = {}  # Categorized task IDs/metadata
        self.user_stats: Dict[str, Any] = {}
        self.unused_tags: List[Dict] = []
        self.all_challenges_cache: Optional[List[Dict]] = None  # Cache for GET /challenges/user

        # --- Initial Data Load ---
        self.console.log("Performing initial data refresh...", style="info")
        self.refresh_data()
        self.console.log("Initialization complete.", style="success")
        self.console.print("")  # Spacer

    # MARK: - Primary Public Method (Entry Point)
    # & - def run(self):
    def run(self):
        """Starts the main application menu loop."""
        while True:
            # --- Dynamically Build Menu Based on Config ---
            active_categories = self._build_active_menu()
            main_menu_options = list(active_categories.keys())

            # --- Display Menu & Get Choice ---
            choice = self._display_menu("Main Menu", main_menu_options, embed_stats=True)
            if choice == 0:
                break  # Exit
            if choice == -1:
                continue  # Invalid input

            # --- Handle Choice ---
            try:
                category_name = main_menu_options[choice - 1]
            except IndexError:
                self.console.print(f"Invalid choice index {choice}.", style="error")
                continue

            if category_name == "Application":
                app_options = active_categories["Application"]
                app_choice = self._display_menu("Application Menu", app_options, embed_stats=False)
                if app_choice in [0, -1]:
                    continue
                try:
                    action_name = app_options[app_choice - 1]
                    if action_name == "Exit":
                        break
                    else:
                        self._execute_action(action_name)
                except IndexError:
                    self.console.print(f"Invalid app choice {app_choice}.", style="error")
            else:
                self._submenu_loop(category_name, active_categories[category_name])

        self.console.print("\nExiting Pixabit. Goodbye!", style="bold info")

    # MARK: - Dynamic Menu Building
    # & - def _build_active_menu(self) -> Dict[str, List[str]]:
    def _build_active_menu(self) -> Dict[str, List[str]]:
        """Builds the menu dictionary, including optional items based on config."""
        # --- Base Menu Structure ---
        categories = {
            "Manage Tasks": ["Handle Broken Tasks", "Replicate Monthly Setup"],
            "Manage Tags": [
                "Display All Tags",
                "Display Unused Tags",
                "Delete Unused Tags",
                "Add/Replace Tag Interactively",
            ],
            "Manage Challenges": ["Backup Challenges", "Leave Challenge"],
            "View Data": ["Display Stats"],
            "Export Data": [
                "Save Processed Tasks (JSON)",
                "Save Raw Tasks (JSON)",
                "Save All Tags (JSON)",
                "Save Full User Data (JSON)",
            ],
            "User Actions": ["Toggle Sleep Status"],
            "Application": ["Refresh Data", "Configure Special Tags", "Exit"],
        }

        # --- Add Optional Tag Actions Conditionally ---
        mg_tags = categories["Manage Tags"]  # Shortcut
        # Insert items at specific indices to maintain logical order
        insert_pos = 3  # Position after basic display/delete options

        # Check config directly (config module holds the loaded values)
        if config.CHALLENGE_TAG_ID and config.PERSONAL_TAG_ID:
            mg_tags.insert(insert_pos, "Sync Challenge/Personal Tags")
            insert_pos += 1
        if config.PSN_TAG_ID and config.NOT_PSN_TAG_ID:
            mg_tags.insert(insert_pos, "Sync Poison Status Tags")
            insert_pos += 1
        if config.ATTR_TAG_MAP and config.NO_ATTR_TAG_ID:
            mg_tags.insert(insert_pos, "Sync Attribute Tags")
            insert_pos += 1

        # Filter out any categories that might have become empty (unlikely here)
        active_categories = {name: opts for name, opts in categories.items() if opts}
        return active_categories

    # MARK: - Major Workflow Methods
    # & - def refresh_data(self):
    def refresh_data(self):
        """Fetches/processes all necessary data using optimized API calls."""
        self.console.print("\nRefreshing all application data...", style="highlight")
        start_time = time.monotonic()
        # --- Setup Progress Bar ---
        progress = Progress(
            TextColumn(" • ", style="subtle"),
            TextColumn("[progress.description]{task.description}", justify="left"),
            BarColumn(style="rp_surface", complete_style="rp_foam", finished_style="rp_pine"),
            TaskProgressColumn(style="rp_subtle_color"),
            TimeElapsedColumn(),
            SpinnerColumn("dots", style="rp_iris"),
            console=self.console,
            transient=False,
        )
        # Define steps and weights for progress calculation
        steps = [
            (
                "Fetch User",
                self.api_client.get_user_data,
                "user_data",
                1,
                True,
            ),  # Name, function, attr_name, weight, critical
            ("Fetch Content", self._get_content_cached, "content_data", 1, True),
            ("Fetch Tags", self.api_client.get_tags, "all_tags", 1, False),  # Non-critical
            (
                "Fetch Party",
                self.api_client.get_party_data,
                "party_data",
                1,
                False,
            ),  # Non-critical
            (
                "Fetch Challenges",
                self._fetch_challenges_cached,
                "all_challenges_cache",
                1,
                False,
            ),  # Non-critical
            (
                "Process Tasks",
                self._process_tasks_step,
                "processed_tasks",
                5,
                True,
            ),  # Special step
            (
                "Calculate Stats/Unused",
                self._calculate_stats_unused_step,
                None,
                1,
                False,
            ),  # Special step
        ]
        total_weight = sum(w for _, _, _, w, _ in steps)
        main_task_id = progress.add_task("[info]Initializing...", total=total_weight)
        refresh_ok = True

        with Live(
            progress, console=self.console, vertical_overflow="ellipsis", refresh_per_second=10
        ) as live:
            units_done = 0
            # --- Execute Steps ---
            for i, (name, func, attr, weight, critical) in enumerate(steps):
                progress.update(main_task_id, description=f"[{i + 1}/{len(steps)}] {name}...")
                try:
                    # Special steps call internal methods directly
                    if name == "Process Tasks":
                        if not self._process_tasks_step():  # Returns success bool
                            raise RuntimeError("Task processing failed.")
                    elif name == "Calculate Stats/Unused":
                        self._calculate_stats_unused_step()  # Updates attributes directly
                    else:  # Standard data fetching steps
                        result = func()  # Call the fetch function
                        if (
                            result is None and critical
                        ):  # Critical fetch failed (e.g., user, content)
                            raise ValueError(f"{name} data fetch returned None.")
                        if attr:  # If an attribute name is provided, store the result
                            setattr(
                                self,
                                attr,
                                result if result is not None else self._get_default_for_attr(attr),
                            )

                    units_done += weight
                    progress.update(main_task_id, completed=units_done)

                except Exception as e:
                    failed_msg = f"[error]Failed: {name}!"
                    progress.update(main_task_id, description=failed_msg)
                    self.console.log(f"Error during '{name}': {e}", style="error")
                    refresh_ok = False
                    if critical:  # Stop refresh if critical step fails
                        self.console.print(
                            f"Halting refresh due to critical error in '{name}'.", style="error"
                        )
                        # Ensure default types are set for subsequent steps even if we break
                        self._ensure_default_attributes()
                        break  # Exit the loop
                    else:  # Non-critical error, log and continue
                        self.console.log(
                            "Continuing refresh despite non-critical error.", style="warning"
                        )
                        # Ensure attribute has a default value if fetch failed
                        if attr:
                            setattr(self, attr, self._get_default_for_attr(attr))
                        units_done += weight  # Still advance progress for non-critical failures
                        progress.update(main_task_id, completed=units_done)

        # --- Post-Refresh Summary ---
        end_time = time.monotonic()
        duration = end_time - start_time
        final_status, final_style = (
            ("Refresh Complete!", "success") if refresh_ok else ("Refresh Failed!", "error")
        )
        progress.update(
            main_task_id, description=f"[{final_style}]{final_status}[/]", completed=total_weight
        )
        time.sleep(0.1)  # Allow final render
        self.console.print(f"[{final_style}]{final_status}[/] (Duration: {duration:.2f}s)")
        # Ensure default types after loop finishes, especially if errors occurred
        self._ensure_default_attributes()

    # & - def _get_default_for_attr(self, attr_name: str) -> Any:
    def _get_default_for_attr(self, attr_name: str) -> Any:
        """Returns a sensible default value based on the attribute name."""
        if "list" in attr_name or "tags" in attr_name or "cache" in attr_name:
            return []
        if "dict" in attr_name or "data" in attr_name or "stats" in attr_name:
            return {}
        return None  # Default fallback

    # & - def _ensure_default_attributes(self):
    def _ensure_default_attributes(self):
        """Ensures core state attributes have default types after refresh, especially if errors occurred."""
        self.user_data = getattr(self, "user_data", None) or {}
        self.party_data = getattr(self, "party_data", None) or {}
        self.content_data = getattr(self, "content_data", None) or {}
        self.all_tags = getattr(self, "all_tags", None) or []
        self.processed_tasks = getattr(self, "processed_tasks", None) or {}
        self.cats_data = getattr(self, "cats_data", None) or {
            "tasks": {},
            "tags": [],
            "broken": [],
            "challenge": [],
        }
        self.user_stats = getattr(self, "user_stats", None) or {}
        self.unused_tags = getattr(self, "unused_tags", None) or []
        self.all_challenges_cache = getattr(
            self, "all_challenges_cache", None
        )  # Keep None if not fetched
        if (
            not isinstance(self.all_challenges_cache, list)
            and self.all_challenges_cache is not None
        ):
            self.all_challenges_cache = []  # Reset to list if it became something else

    # & - def _get_content_cached(self) -> Dict[str, Any]: ... (keep previous implementation)
    def _get_content_cached(self) -> Dict[str, Any]:
        """Helper to get game content, using cache first."""
        # Re-use implementation from app_v5.txt
        content = None
        cache_path = Path("content_cache.json")  # Use Path object
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    content = json.load(f)
                if isinstance(content, dict) and content:
                    self.console.log(f"Using cached content from '{cache_path}'.", style="subtle")
                    return content
                else:
                    self.console.log(
                        f"Invalid content in cache '{cache_path}'. Refetching.", style="warning"
                    )
                    content = None
            except (OSError, json.JSONDecodeError, Exception) as e:
                self.console.log(
                    f"Failed loading cache '{cache_path}': {e}. Refetching.", style="warning"
                )
                content = None
        if content is None:
            self.console.log("Fetching game content from API...", style="info")
            try:
                content = self.api_client.get_content()  # Returns dict or None
                if isinstance(content, dict) and content:
                    try:
                        with open(cache_path, "w", encoding="utf-8") as f:
                            json.dump(content, f, ensure_ascii=False, indent=2)
                        self.console.log(f"Saved content to cache: '{cache_path}'", style="subtle")
                    except (OSError, Exception) as e_save:
                        self.console.log(
                            f"Failed to save content cache: {e_save}", style="warning"
                        )
                    return content
                else:
                    self.console.log("Failed to fetch valid game content.", style="error")
                    return {}
            except Exception as e_fetch:
                self.console.log(f"Exception fetching content: {e_fetch}", style="error")
                return {}
        return {}  # Should not be reached

    # & - def _fetch_challenges_cached(self) -> Optional[List[Dict]]:
    def _fetch_challenges_cached(self) -> Optional[List[Dict]]:
        """Fetches challenges only if cache is empty."""
        if self.all_challenges_cache is None:
            self.console.log("Challenge cache empty, fetching...", style="subtle")
            # Fetch only challenges the user is currently a member of
            fetched = self.api_client.get_challenges(member_only=True)  # Returns list or []
            self.all_challenges_cache = fetched  # Update cache
            self.console.log(
                f"Fetched and cached {len(self.all_challenges_cache)} challenges.", style="subtle"
            )
        else:
            self.console.log(
                f"Using cached challenges ({len(self.all_challenges_cache)} found).",
                style="subtle",
            )
        return self.all_challenges_cache  # Return the list (potentially empty or from cache)

    # & - def _process_tasks_step(self) -> bool:
    def _process_tasks_step(self) -> bool:
        """Internal step for task processing during refresh_data."""
        try:
            # Instantiate processor, passing pre-fetched data
            self.processor = TaskProcessor(
                api_client=self.api_client,
                user_data=self.user_data,
                party_data=self.party_data,
                all_tags_list=self.all_tags,
                content_data=self.content_data,
            )
            # Perform processing and categorization
            processed_results = self.processor.process_and_categorize_all()
            # Store results
            self.processed_tasks = processed_results.get("data", {})
            self.cats_data = processed_results.get("cats", {})
            if not self.processed_tasks and not self.cats_data.get("tasks"):
                self.console.log("No tasks found or processed.", style="info")
            return True  # Indicate success
        except Exception as e:
            self.console.log(f"Error processing tasks: {e}", style="error")
            self.processed_tasks = {}  # Reset on error
            self.cats_data = {}
            return False  # Indicate failure

    # & - def _calculate_stats_unused_step(self):
    def _calculate_stats_unused_step(self):
        """Internal step for calculating stats and unused tags during refresh_data."""
        # Calculate User Stats (uses pre-fetched/processed data)
        try:
            if self.cats_data and self.processed_tasks and self.user_data:
                self.user_stats = get_user_stats(
                    api_client=self.api_client,  # Pass client just in case
                    cats_dict=self.cats_data,
                    processed_tasks_dict=self.processed_tasks,
                    user_data=self.user_data,  # Pass pre-fetched data
                )
            else:
                self.console.log("Skipping stats calculation: missing data.", style="warning")
                self.user_stats = {}
        except Exception as e:
            self.console.log(f"Error calculating user stats: {e}.", style="warning")
            self.user_stats = {}

        # Calculate Unused Tags (uses pre-fetched/processed data)
        try:
            if isinstance(self.all_tags, list) and self.cats_data.get("tags") is not None:
                # Ensure used_tag_ids is a set
                used_tag_ids: Set[str] = set(self.cats_data.get("tags", []))
                self.unused_tags = self.tag_manager.find_unused_tags(self.all_tags, used_tag_ids)
                # self.console.log(f"Calculated {len(self.unused_tags)} unused tags.", style="subtle")
            else:
                self.console.log(
                    "Skipping unused tags calculation: missing data.", style="warning"
                )
                self.unused_tags = []
        except Exception as e:
            self.console.log(f"Error calculating unused tags: {e}", style="warning")
            self.unused_tags = []

    # & - def _submenu_loop(...)
    def _submenu_loop(self, title: str, options: List[str]):
        """Handles display/logic for a submenu."""
        while True:
            choice = self._display_menu(f"{title} Menu", options, embed_stats=False)
            if choice == 0:
                break
            if choice == -1:
                continue
            try:
                self._execute_action(options[choice - 1])
            except IndexError:
                self.console.print(f"Invalid submenu choice {choice}.", style="error")

    # & - def _execute_action(...)
    def _execute_action(self, action_name: str):
        """Executes selected action, passing data, checks config for optional actions."""
        self.console.print(f"\n➡️ Executing: [highlight]{action_name}[/]", highlight=False)
        refresh_needed = False
        action_taken = False  # Track if an action was actually performed
        start_time = time.monotonic()

        try:
            # --- Task Management ---
            if action_name == "Handle Broken Tasks":
                # This action uses self.cats_data and self.processed_tasks internally
                action_taken = refresh_needed = self._handle_broken_tasks_action()
            elif action_name == "Replicate Monthly Setup":
                # This action uses self.cats_data, self.processed_tasks, self.all_challenges_cache
                action_taken = refresh_needed = self._replicate_monthly_setup_action()

            # --- Tag Management (Check Config for Optional Actions) ---
            elif action_name == "Display All Tags":
                self._display_tags()
                action_taken = True  # Display actions always run
            elif action_name == "Display Unused Tags":
                self._display_unused_tags()
                action_taken = True
            elif action_name == "Delete Unused Tags":
                # Pass necessary data to TagManager method
                used_ids = set(self.cats_data.get("tags", []))
                action_taken = refresh_needed = self.tag_manager.delete_unused_tags_interactive(
                    self.all_tags, used_ids
                )
            elif action_name == "Sync Challenge/Personal Tags":
                # Check config before calling
                if config.CHALLENGE_TAG_ID and config.PERSONAL_TAG_ID:
                    action_taken = refresh_needed = self.tag_manager.sync_challenge_personal_tags(
                        self.processed_tasks
                    )
                else:
                    self.console.print("Challenge/Personal tags not configured.", style="info")
            elif action_name == "Sync Poison Status Tags":
                if config.PSN_TAG_ID and config.NOT_PSN_TAG_ID:
                    action_taken = refresh_needed = self.tag_manager.ensure_poison_status_tags(
                        self.processed_tasks
                    )
                else:
                    self.console.print("Poison Status tags not configured.", style="info")
            elif action_name == "Sync Attribute Tags":
                if config.ATTR_TAG_MAP and config.NO_ATTR_TAG_ID:
                    action_taken = refresh_needed = self.tag_manager.sync_attributes_to_tags(
                        self.processed_tasks
                    )
                else:
                    self.console.print("Attribute tags not fully configured.", style="info")
            elif action_name == "Add/Replace Tag Interactively":
                # This action uses self.all_tags and self.processed_tasks
                action_taken = refresh_needed = self._interactive_tag_replace_action()

            # --- Challenge Management ---
            elif action_name == "Backup Challenges":
                if Confirm.ask("Backup all accessible challenges?", console=self.console):
                    backup_folder = Path("_challenge_backups")  # Use Path
                    self.backupper.create_backups(output_folder=backup_folder)
                    action_taken = True
            elif action_name == "Leave Challenge":
                # This action uses self.all_challenges_cache, self.user_data, updates cache
                action_taken = self._leave_challenge_action()  # Returns False for refresh

            # --- View Data ---
            elif action_name == "Display Stats":
                stats_panel = self._display_stats()  # Uses self.user_stats
                if stats_panel:
                    self.console.print(stats_panel)
                    action_taken = True

            # --- Export Data ---
            elif action_name == "Save Processed Tasks (JSON)":
                if self.processed_tasks and Confirm.ask(
                    "Save processed tasks?", console=self.console
                ):
                    save_processed_tasks_into_json(self.processed_tasks, "tasks_processed.json")
                    action_taken = True
                elif not self.processed_tasks:
                    self.console.print("No processed tasks to save.", style="warning")
            elif action_name == "Save Raw Tasks (JSON)":
                if Confirm.ask("Save raw tasks (fetches fresh)?", console=self.console):
                    save_tasks_without_proccessing(self.api_client, "tasks_raw.json")
                    action_taken = True
            elif action_name == "Save All Tags (JSON)":
                if Confirm.ask("Save all tags (fetches fresh)?", console=self.console):
                    save_tags_into_json(self.api_client, "tags_all.json")
                    action_taken = True
            elif action_name == "Save Full User Data (JSON)":
                if Confirm.ask("Save full user data (fetches fresh)?", console=self.console):
                    save_all_userdata_into_json(self.api_client, "user_data_full.json")
                    action_taken = True

            # --- User Actions ---
            elif action_name == "Toggle Sleep Status":
                current_status = self.user_stats.get("sleeping", False)
                action_desc = "wake up" if current_status else "go to sleep"
                if Confirm.ask(f"Do you want to {action_desc}?", console=self.console):
                    response = self.api_client.toggle_user_sleep()
                    if response is not None:
                        new_status = (
                            response.get("sleep") if isinstance(response, dict) else "Unknown"
                        )
                        self.console.print(
                            f"Sleep toggled. New status: {new_status}", style="success"
                        )
                        refresh_needed = True
                        action_taken = True
                    else:
                        self.console.print("Failed to toggle sleep status.", style="error")

            # --- Application ---
            elif action_name == "Refresh Data":
                refresh_needed = True
                action_taken = True  # Refresh happens after action block
            elif action_name == "Configure Special Tags":
                run_tag_config_setup()  # Call the setup function
                refresh_needed = True
                action_taken = True  # Assume config changed

            # --- Fallback ---
            else:
                self.console.print(f"Action '{action_name}' not implemented.", style="warning")

            # --- Post-Action Refresh ---
            if refresh_needed:
                self.console.print(f"\nAction '{action_name}' requires data update.", style="info")
                self.refresh_data()

        except Exception:
            self.console.print(f"\nError executing action '{action_name}':", style="error")
            self.console.print_exception(show_locals=False)
        finally:
            end_time = time.monotonic()
            duration = end_time - start_time
            if action_taken:  # Only prompt if something actually happened
                self.console.print(
                    f"Action '{action_name}' finished. (Duration: {duration:.2f}s)", style="subtle"
                )
                Prompt.ask(
                    "\n[subtle]Press Enter to continue...[/]", default="", console=self.console
                )

    # MARK: - UI Helper Methods
    # & - def _display_menu(...) (Keep previous themed implementation)
    def _display_menu(self, title: str, options: List[str], embed_stats: bool = False) -> int:
        """Displays a menu using Rich, optionally embedding stats."""
        # Re-use implementation from app_v5.txt
        max_option = len(options)
        menu_renderables = []
        back_label = "Exit Application" if title == "Main Menu" else "Back"
        menu_renderables.append(f"[subtle] 0.[/] {back_label}")
        for i, opt in enumerate(options):
            menu_renderables.append(f"[bold] {i + 1}.[/] {opt}")
        menu_panel = Panel(
            "\n".join(menu_renderables),
            title=f"[highlight]{title}[/]",
            border_style="rp_subtle_color",
            box=box.ROUNDED,
            padding=(1, 2),
            expand=False,
        )
        display_object: Any = menu_panel
        if embed_stats:
            stats_panel = self._display_stats()
            if stats_panel:
                layout_table = Table.grid(expand=True)
                layout_table.add_column(ratio=3)
                layout_table.add_column(ratio=2)
                layout_table.add_row(stats_panel, menu_panel)
                display_object = Panel(layout_table, border_style="rp_overlay", expand=True)
            else:
                self.console.print("Could not display stats panel.", style="warning")
        self.console.print(display_object)
        try:
            return IntPrompt.ask(
                "Choose an option",
                choices=[str(i) for i in range(max_option + 1)],
                show_choices=False,
                console=self.console,
            )
        except Exception as e:
            self.console.print(f"Menu input error: {e}", style="error")
            return -1

    # & - def _display_stats(...) (Keep previous themed implementation)
    def _display_stats(self) -> Optional[Panel]:
        """Builds and returns a Rich Panel containing formatted user stats."""
        # Re-use implementation from app_v5.txt
        stats = self.user_stats
        if not stats:
            self.console.print("No user stats data available.", style="warning")
            return None
        try:
            # Extract data safely
            uname, lvl, uclass = (
                stats.get("username", "N/A"),
                stats.get("level", 0),
                stats.get("class", "N/A").capitalize(),
            )
            hp, max_hp, mp, max_mp = (
                int(stats.get("hp", 0)),
                stats.get("maxHealth", 50),
                int(stats.get("mp", 0)),
                stats.get("maxMP", 30),
            )
            exp, next_lvl, gp, gems = (
                int(stats.get("exp", 0)),
                stats.get("toNextLevel", 100),
                int(stats.get("gp", 0)),
                stats.get("gems", 0),
            )
            core = stats.get("stats", {})
            sleeping, day_start, last_login = (
                stats.get("sleeping", False),
                stats.get("day_start", "?"),
                stats.get("last_login_local", "N/A"),
            )
            broken, questing, q_key = (
                stats.get("broken_challenge_tasks", 0),
                stats.get("quest_active", False),
                stats.get("quest_key"),
            )
            dmg_u, dmg_p = (
                stats.get("potential_daily_damage_user", 0.0),
                stats.get("potential_daily_damage_party", 0.0),
            )
            dmg_style = "error" if dmg_u >= 5 else "warning" if dmg_u > 0 else "subtle"
            dmg_p_str = f", Party: {dmg_p:.1f}" if dmg_p > 0 else ""
            t_counts = stats.get("task_counts", {})

            # Format login time
            login_display = "N/A"
            if last_login and "Error" not in last_login and last_login != "N/A":
                try:
                    login_dt = datetime.datetime.fromisoformat(last_login)
                    local_tz = datetime.datetime.now().astimezone().tzinfo
                    now_local = datetime.datetime.now(local_tz)
                    login_dt_aware = login_dt.replace(tzinfo=local_tz)
                    login_display = timeago.format(login_dt_aware, now_local)
                except Exception:
                    login_display = last_login  # Fallback

            # Build UI Tables
            user_info = Table.grid(padding=(0, 1), expand=False)
            user_info.add_column(style="subtle", justify="right", min_width=3)
            user_info.add_column(justify="left")
            user_info.add_row("👤", f"[highlight]{uname}[/] ([rp_iris]{uclass} Lv {lvl}[/])")
            user_info.add_row("🕒", f"Login: [rp_text i]{login_display}[/]")
            user_info.add_row("🌅", f"Day start: {day_start}:00")
            if sleeping:
                user_info.add_row("💤", "[warning i]Resting in Inn[/]")
            if questing:
                user_info.add_row("🐉", f"[info]On Quest:[/] [i]{q_key or 'Unknown'}[/]")
            if broken:
                user_info.add_row(":warning:", f"[error]{broken} broken tasks[/]")
            user_info.add_row("💔", f"Dmg: [{dmg_style}]User {dmg_u:.1f}{dmg_p_str}[/]")

            stat_vals = Table.grid(padding=(0, 1), expand=False)
            stat_vals.add_row(
                f"[rp_love b]HP: [/]{hp: <3}/ {max_hp}", f"[rp_gold b]XP: [/]{exp: <3}/ {next_lvl}"
            )
            stat_vals.add_row(f"[rp_foam b]MP: [/]{mp: <3}/ {max_mp}", f"[rp_gold b]GP: [/]{gp}")
            stat_vals.add_row(f"[b]💎 Gems:[/b] {gems}", "")
            stat_vals.add_row(
                f"[subtle]STR:[/] {core.get('str', 0)} [subtle]INT:[/] {core.get('int', 0)}",
                f"[subtle]CON:[/] {core.get('con', 0)} [subtle]PER:[/] {core.get('per', 0)}",
            )

            # Task Counts Panel
            hab_c, rew_c = t_counts.get("habits", 0), t_counts.get("rewards", 0)
            day_d, todo_d = t_counts.get("dailys", {}), t_counts.get("todos", {})
            day_tot, todo_tot = day_d.get("_total", 0), todo_d.get("_total", 0)
            day_due, todo_due = day_d.get("due", 0), todo_d.get("due", 0) + todo_d.get("red", 0)
            day_done = day_d.get("success", 0)  # Use 'success' key from processor
            tasks_text = f"Habits:[b]{hab_c}[/]\n Daylies:[b]{day_tot}[/] ([warning]{day_due}[/] due/[success]{day_done}[/] done)\n Todo:[b]{todo_tot}[/] ([warning]{todo_due}[/] due)\n Rewards:[b]{rew_c}[/]"
            tasks_p = Panel(
                tasks_text, title="Tasks", border_style="blue", padding=(0, 1), expand=False
            )

            # Assemble Layout
            top = Table.grid(expand=True)
            top.add_column(ratio=1)
            top.add_column(ratio=1)
            top.add_row(
                Panel(user_info, border_style="rp_overlay", padding=(1, 1)),
                Panel(stat_vals, border_style="rp_overlay", padding=(1, 1)),
            )
            final = Table.grid(expand=True)
            final.add_row(top)
            final.add_row(tasks_p)
            return Panel(
                final, title="📊 [highlight]Dashboard[/]", border_style="green", padding=(1, 2)
            )
        except Exception:
            self.console.print("Error building stats display:", style="error")
            self.console.print_exception(show_locals=False)
            return None

    # & - def _display_tags(...) (Keep previous themed implementation)
    def _display_tags(self):
        """Displays all fetched tags in a table using theme styles."""
        if not self.all_tags:
            self.console.print("No tags data available.", style="warning")
            return
        self.console.print(f"\n[highlight]All Tags ({len(self.all_tags)})[/]", highlight=False)
        table = Table(show_header=True, header_style="rp_iris", box=box.ROUNDED, padding=(0, 1))
        table.add_column("Num", style="subtle", width=4, justify="right")
        table.add_column("Name", style="rp_foam", min_width=20, no_wrap=True)
        table.add_column("ID", style="rp_rose", overflow="fold", min_width=36)
        valid = [tag for tag in self.all_tags if isinstance(tag, dict) and tag.get("id")]
        for i, tag in enumerate(valid):
            table.add_row(str(i + 1), tag.get("name", "[subtle]N/A[/]"), tag["id"])
        self.console.print(table)

    # & - def _display_unused_tags(...) (Keep previous themed implementation)
    def _display_unused_tags(self):
        """Displays unused tags in a table using theme styles."""
        if not self.unused_tags:
            self.console.print("✅ No unused tags found.", style="success")
            return
        self.console.print(
            f"\n[highlight]Unused Tags ({len(self.unused_tags)})[/]", highlight=False
        )
        table = Table(show_header=True, header_style="rp_gold", box=box.ROUNDED, padding=(0, 1))
        table.add_column("Num", style="subtle", width=4, justify="right")
        table.add_column("Name", style="rp_foam", min_width=20, no_wrap=True)
        table.add_column("ID", style="rp_rose", overflow="fold", min_width=36)
        for i, tag in enumerate(self.unused_tags):
            table.add_row(
                str(i + 1), tag.get("name", "[subtle]N/A[/]"), tag.get("id", "[subtle]N/A[/]")
            )
        self.console.print(table)

    # & - def _display_broken_tasks(...) (Keep previous themed implementation)
    def _display_broken_tasks(self, challenge_id_filter: Optional[str] = None) -> List[Dict]:
        """Displays broken tasks using theme styles, returns displayed task info list."""
        broken_ids = self.cats_data.get("broken", [])
        if not broken_ids:
            if not challenge_id_filter:
                self.console.print("✅ No broken tasks found.", style="success")
            return []
        title, display_tasks = "Broken Challenge Tasks", []
        for tid in broken_ids:
            task = self.processed_tasks.get(tid)
            if task:
                cid = task.get("challenge_id")
                cname = task.get("challenge_name", "[subtle]N/A[/]")
                ttext = task.get("text", "[subtle]N/A[/]")
                info = {"id": tid, "text": ttext, "challenge_id": cid, "challenge_name": cname}
                if challenge_id_filter:
                    if cid == challenge_id_filter:
                        display_tasks.append(info)
                else:
                    display_tasks.append(info)
        if not display_tasks:
            if challenge_id_filter:
                self.console.print(
                    f"No broken tasks for challenge ID {challenge_id_filter}.", style="warning"
                )
            return []
        if challenge_id_filter:
            title = f"Broken Tasks for: {display_tasks[0]['challenge_name']}"
        self.console.print(f"\nFound {len(display_tasks)} broken tasks:", style="warning")
        table = Table(title=title, show_header=True, header_style="error", box=box.ROUNDED)
        table.add_column("Num", style="subtle", width=4, justify="right")
        table.add_column("Task Text", style="rp_text", min_width=30)
        if not challenge_id_filter:
            table.add_column("Challenge", style="rp_iris", min_width=20)
        table.add_column("Task ID", style="subtle", width=36)
        for i, task in enumerate(display_tasks):
            row = [str(i + 1), task["text"]]
            if not challenge_id_filter:
                row.append(task["challenge_name"])
            row.append(task["id"])
            table.add_row(*row)
        self.console.print(table)
        return display_tasks

    # MARK: - Action Helper Methods
    # & - def _handle_broken_tasks_action(...) (Keep previous themed implementation)
    def _handle_broken_tasks_action(self) -> bool:
        """Groups broken tasks, allows bulk/individual unlinking using theme styles."""
        # Re-use implementation from app_v5.txt
        broken_ids = self.cats_data.get("broken", [])
        should_refresh = False
        if not broken_ids:
            self.console.print("✅ No broken tasks found.", style="success")
            return False
        broken_by_challenge = defaultdict(list)
        challenge_names = {}
        all_valid = []
        for tid in broken_ids:
            task = self.processed_tasks.get(tid)
            if task:
                cid = task.get("challenge_id")
                if cid:
                    cname = task.get("challenge_name", cid)
                    info = {"id": tid, "text": task.get("text", "N/A")}
                    broken_by_challenge[cid].append(info)
                    if cid not in challenge_names:
                        challenge_names[cid] = cname
                    all_valid.append({**info, "challenge_id": cid, "challenge_name": cname})
        if not broken_by_challenge:
            self.console.print("No broken tasks with challenge links found.", style="warning")
            return False
        self.console.print(
            f"\nFound {len(all_valid)} broken tasks across {len(broken_by_challenge)} challenges:",
            style="warning",
        )
        ch_table = Table(
            title="Challenges with Broken Tasks", box=box.ROUNDED, border_style="warning"
        )
        ch_table.add_column("Num", style="subtle", width=4)
        ch_table.add_column("Challenge Name / ID", style="rp_iris")
        ch_table.add_column("Task Count", style="rp_text", justify="right")
        ch_list = list(broken_by_challenge.keys())
        for i, cid in enumerate(ch_list):
            ch_table.add_row(
                str(i + 1), challenge_names.get(cid, cid), str(len(broken_by_challenge[cid]))
            )
        self.console.print(ch_table)
        self.console.print(
            "\nManage broken tasks:\n  [1] By Challenge (Bulk)\n  [2] Individually\n  [0] Cancel"
        )
        try:
            mode = IntPrompt.ask(
                "Enter choice", choices=["0", "1", "2"], show_choices=False, console=self.console
            )
            if mode == 0:
                return False
            elif mode == 1:  # Bulk
                if not ch_list:
                    return False
                ch_num = IntPrompt.ask(
                    f"Challenge number (1-{len(ch_list)})",
                    choices=[str(i) for i in range(1, len(ch_list) + 1)],
                    show_choices=False,
                    console=self.console,
                )
                sel_cid = ch_list[ch_num - 1]
                sel_cname = challenge_names.get(sel_cid, sel_cid)
                tasks_in_ch = broken_by_challenge[sel_cid]
                self.console.print(f"\nTasks in [rp_iris]'{sel_cname}'[/]:")
                [
                    self.console.print(f"  - {t['text']} ([subtle]{t['id']}[/])")
                    for t in tasks_in_ch
                ]
                keep = Confirm.ask(
                    f"\nKeep personal copies of these {len(tasks_in_ch)} tasks?",
                    default=True,
                    console=self.console,
                )
                keep_param = "keep-all" if keep else "remove-all"
                action_desc = (
                    "keeping copies"
                    if keep_param == "keep-all"
                    else "[error]removing permanently[/]"
                )
                if Confirm.ask(
                    f"Confirm bulk-unlink for '{sel_cname}' ({action_desc})?",
                    default=True,
                    console=self.console,
                ):
                    self.console.print(
                        f"Attempting bulk unlink for {sel_cid} ({action_desc})...", style="info"
                    )
                    try:
                        self.api_client.unlink_all_challenge_tasks(sel_cid, keep=keep_param)
                        self.console.print(
                            f"Bulk unlink successful for '{sel_cname}'.", style="success"
                        )
                        should_refresh = True
                    except Exception as e:
                        self.console.print(f"Error bulk unlinking {sel_cid}: {e}", style="error")
                        self.console.print("Hint: Try individual unlinking.", style="warning")
                        should_refresh = False
                else:
                    self.console.print("Bulk unlink cancelled.", style="info")
            elif mode == 2:  # Individual
                if not all_valid:
                    return False
                disp_tasks = self._display_broken_tasks()  # Use helper to display numbered list
                if not disp_tasks:
                    return False
                task_num = IntPrompt.ask(
                    f"Task number to unlink (1-{len(disp_tasks)})",
                    choices=[str(i) for i in range(1, len(disp_tasks) + 1)],
                    show_choices=False,
                    console=self.console,
                )
                sel_task = disp_tasks[task_num - 1]
                sel_tid = sel_task["id"]
                sel_ttext = sel_task["text"]
                keep = Confirm.ask(
                    f"Keep personal copy of '{sel_ttext}'?", default=True, console=self.console
                )
                keep_param = "keep" if keep else "remove"
                action_desc = (
                    "keeping copy" if keep_param == "keep" else "[error]removing permanently[/]"
                )
                if Confirm.ask(
                    f"Unlink task '{sel_ttext}' ({action_desc})?",
                    default=True,
                    console=self.console,
                ):
                    self.console.print(
                        f"Attempting unlink for task {sel_tid} ({action_desc})...", style="info"
                    )
                    try:
                        self.api_client.unlink_task_from_challenge(sel_tid, keep=keep_param)
                        self.console.print(
                            f"Successfully unlinked '{sel_ttext}'.", style="success"
                        )
                        should_refresh = True
                    except Exception as e:
                        self.console.print(f"Error unlinking task {sel_tid}: {e}", style="error")
                        should_refresh = False
                else:
                    self.console.print("Unlink cancelled.", style="info")
        except (ValueError, IndexError) as e:
            self.console.print(f"Invalid selection: {e}", style="error")
        except KeyboardInterrupt:
            self.console.print("\nOperation cancelled.")
        return should_refresh

    # & - def _interactive_tag_replace_action(...) (Keep previous themed implementation)
    def _interactive_tag_replace_action(self) -> bool:
        """Handles interactive prompts for replacing tags using theme styles."""
        # Re-use implementation from app_v5.txt
        self._display_tags()
        valid = [t for t in self.all_tags if isinstance(t, dict) and t.get("id")]
        num_tags = len(valid)
        if not valid:
            self.console.print("No valid tags found.", style="warning")
            return False
        should_refresh = False
        try:
            self.console.print("\nSelect tags by number:")
            del_num = IntPrompt.ask(f"Tag to FIND/REPLACE (1-{num_tags})", console=self.console)
            if not 1 <= del_num <= num_tags:
                raise ValueError("Find selection out of range")
            find_tag = valid[del_num - 1]
            find_id, find_name = find_tag["id"], find_tag.get("name", find_tag["id"])
            add_num = IntPrompt.ask(f"Tag to ADD (1-{num_tags})", console=self.console)
            if not 1 <= add_num <= num_tags:
                raise ValueError("Add selection out of range")
            if del_num == add_num:
                self.console.print("Source and target tags cannot be same.", style="warning")
                return False
            add_tag = valid[add_num - 1]
            add_id, add_name = add_tag["id"], add_tag.get("name", add_tag["id"])
            replace = Confirm.ask(
                f"Also REMOVE '[rp_rose]{find_name}[/]' after adding '[rp_foam]{add_name}[/]'?",
                default=False,
                console=self.console,
            )
            mode = "replace" if replace else "add"
            if Confirm.ask(
                f"Proceed to {mode} tag '[rp_foam]{add_name}[/]' on tasks having '[rp_rose]{find_name}[/]'?",
                default=True,
                console=self.console,
            ):
                if not self.processed_tasks:
                    self.console.print("No processed task data.", style="warning")
                    return False
                self.console.print(f"Performing tag {mode} operation...", style="info")
                # Pass data to TagManager method
                success = self.tag_manager.add_or_replace_tag_based_on_other(
                    tasks_dict=self.processed_tasks,
                    find_tag_id=find_id,
                    add_tag_id=add_id,
                    remove_original=replace,
                )
                if success:
                    self.console.print("Tag operation completed.", style="success")
                    should_refresh = True
                else:
                    self.console.print("Tag operation may have errors.", style="warning")
                    should_refresh = True  # Refresh anyway
            else:
                self.console.print("Operation cancelled.", style="info")
        except (ValueError, IndexError) as e:
            self.console.print(f"Invalid input: {e}.", style="error")
        except KeyboardInterrupt:
            self.console.print("\nOperation cancelled.")
        return should_refresh

    # & - def _leave_challenge_action(...) (Keep previous themed implementation, ensure cache update)
    def _leave_challenge_action(self) -> bool:
        """Handles listing JOINED challenges and leaving, updates local cache."""
        # Re-use implementation from app_v5.txt, ensure cache update logic is solid
        if self.all_challenges_cache is None:
            self.console.print("Challenge list not loaded. Refresh data.", style="warning")
            return False
        uid = self.user_data.get("id", "") if self.user_data else None
        joined = (
            [
                ch
                for ch in self.all_challenges_cache
                if isinstance(ch, dict) and ch.get("leader", {}).get("_id") != uid
            ]
            if uid
            else self.all_challenges_cache
        )
        if not joined:
            self.console.print("No challenges joined (or cannot determine owner).", style="info")
            return False
        table = Table(
            title="Challenges You Have Joined",
            show_header=True,
            header_style="bold blue",
            box=box.ROUNDED,
        )
        table.add_column("Num", style="subtle", width=4)
        table.add_column("Name", style="rp_iris", min_width=25)
        table.add_column("Leader", style="subtle", min_width=15)
        table.add_column("Memb", style="rp_text", width=7, justify="right")
        valid_sel = []  # List of dicts
        for ch in joined:
            if isinstance(ch, dict) and ch.get("id"):
                valid_sel.append(ch)
                ldr = ch.get("leader", {}).get("profile", {}).get("name", "[subtle]?[/]")
                mem = ch.get("memberCount", "?")
                table.add_row(str(len(valid_sel)), ch.get("shortName", "N/A"), ldr, str(mem))
        if not valid_sel:
            self.console.print("No valid joined challenges.", style="warning")
            return False
        self.console.print(table)
        try:
            choice = IntPrompt.ask(
                f"Challenge number to leave (1-{len(valid_sel)}), or 0",
                choices=["0"] + [str(i) for i in range(1, len(valid_sel) + 1)],
                show_choices=False,
                console=self.console,
            )
            if choice == 0:
                return False
            sel_ch = valid_sel[choice - 1]
            sel_id, sel_name = sel_ch["id"], sel_ch.get("shortName", sel_ch["id"])
            self.console.print(f"\nSelected: [rp_iris]'{sel_name}'[/]")
            keep = Confirm.ask(
                "Keep personal copies of tasks?", default=True, console=self.console
            )
            keep_param = "keep-all" if keep else "remove-all"
            action_desc = (
                "keeping copies" if keep_param == "keep-all" else "[error]removing tasks[/]"
            )
            if Confirm.ask(
                f"Confirm leaving '{sel_name}' ({action_desc})?",
                default=True,
                console=self.console,
            ):
                self.console.print(
                    f"Attempting to leave '{sel_name}' ({action_desc})...", style="info"
                )
                try:
                    self.api_client.leave_challenge(sel_id, keep=keep_param)
                    self.console.print(
                        f"Successfully left challenge '{sel_name}'.", style="success"
                    )
                    # --- IMPORTANT: Update Cache ---
                    if self.all_challenges_cache is not None:
                        self.all_challenges_cache = [
                            c
                            for c in self.all_challenges_cache
                            if isinstance(c, dict) and c.get("id") != sel_id
                        ]
                        self.console.print("In-memory challenge cache updated.", style="subtle")
                    return False  # IMPORTANT: Return False as refresh is not needed due to cache update
                except Exception as e:
                    self.console.print(f"Error leaving challenge {sel_id}: {e}", style="error")
                    return False
            else:
                self.console.print("Leave cancelled.", style="info")
                return False
        except (ValueError, IndexError) as e:
            self.console.print(f"Invalid selection: {e}", style="error")
        except KeyboardInterrupt:
            self.console.print("\nOperation cancelled.")
        return False

    # & - def _replicate_monthly_setup_action(...) (Keep previous themed implementation)
    def _replicate_monthly_setup_action(self) -> bool:
        """Replicates setup from old to new challenge using theme styles."""
        # Re-use implementation from app_v5.txt
        self.console.print("\n--- Replicate Monthly Challenge Setup ---", style="highlight")
        should_refresh = False
        old_cid, new_cid = None, None
        try:
            # Step 1: Select Old
            self.console.print("Identifying source challenges...", style="info")
            broken_ids = self.cats_data.get("broken", [])
            old_chs = {}
            if not broken_ids:
                self.console.print("No broken tasks found.", style="warning")
                return False
            for tid in broken_ids:
                task = self.processed_tasks.get(tid)
                if task:
                    cid = task.get("challenge_id")
                if cid and cid not in old_chs:
                    old_chs[cid] = task.get("challenge_name", cid)
            if not old_chs:
                self.console.print(
                    "Could not extract challenge info from broken tasks.", style="warning"
                )
                return False
            old_list = list(old_chs.items())
            old_list.sort(key=lambda x: x[1])  # Sort by name
            old_table = Table(
                title="Select Source (Old/Broken)", box=box.ROUNDED, border_style="rp_pine"
            )
            old_table.add_column("Num", style="subtle", width=4)
            old_table.add_column("Name / ID", style="rp_iris")
            old_table.add_column("ID", style="subtle")
            for i, (cid, cname) in enumerate(old_list):
                old_table.add_row(str(i + 1), cname, cid)
            self.console.print(old_table)
            old_choice = IntPrompt.ask(
                f"Select OLD (1-{len(old_list)})",
                choices=[str(i) for i in range(1, len(old_list) + 1)],
                show_choices=False,
                console=self.console,
            )
            old_cid, old_cname = old_list[old_choice - 1]
            uid = self.user_data.get("id", "") if self.user_data else None
            # Step 2: Select New
            self.console.print("\nLoading current challenges for destination...", style="info")
            if self.all_challenges_cache is None:
                self.console.print("Challenge cache not loaded.", style="warning")
                return False
            valid_new = [
                ch
                for ch in self.all_challenges_cache
                if isinstance(ch, dict)
                and ch.get("id")
                and ch.get("id") != old_cid
                and ch.get("leader", "").get("_id") != uid
            ]
            valid_new.sort(key=lambda x: x.get("shortName", ""))
            if not valid_new:
                self.console.print("No other suitable challenges found.", style="warning")
                return False
            new_table = Table(
                title="Select Destination (New)", box=box.ROUNDED, border_style="rp_foam"
            )
            new_table.add_column("Num", style="subtle", width=4)
            new_table.add_column("Name", style="rp_iris")
            new_table.add_column("Leader", style="subtle")
            new_table.add_column("ID", style="subtle")
            for i, ch in enumerate(valid_new):
                ldr = ch.get("leader", {}).get("profile", {}).get("name", "?")
                new_table.add_row(str(i + 1), ch.get("shortName", "N/A"), ldr, ch["id"])
            self.console.print(new_table)
            new_choice = IntPrompt.ask(
                f"Select NEW (1-{len(valid_new)})",
                choices=[str(i) for i in range(1, len(valid_new) + 1)],
                show_choices=False,
                console=self.console,
            )
            new_ch = valid_new[new_choice - 1]
            new_cid, new_cname = new_ch["id"], new_ch.get("shortName", new_ch["id"])

            # Step 3: Confirm
            self.console.print(f"\nSource: [rp_iris]'{old_cname}'[/] ([subtle]{old_cid}[/])")
            self.console.print(f"Destination: [rp_iris]'{new_cname}'[/] ([subtle]{new_cid}[/])")
            if not Confirm.ask("Confirm selection?", default=True, console=self.console):
                return False

            # Step 4: Get Tasks
            self.console.print(f"Gathering OLD tasks for '{old_cname}'...", style="info")
            old_tasks = [
                t for t in self.processed_tasks.values() if t.get("challenge_id") == old_cid
            ]
            if not old_tasks:
                self.console.print(
                    "Warning: No tasks found for OLD challenge.", style="warning"
                )  # Allow continue?

            self.console.print(f"Gathering NEW tasks for '{new_cname}'...", style="info")
            new_tasks = [
                t for t in self.processed_tasks.values() if t.get("challenge_id") == new_cid
            ]
            self.console.print(
                f"Found {len(old_tasks)} old, {len(new_tasks)} new tasks.", style="info"
            )
            if not new_tasks:
                self.console.print(
                    "No tasks found for NEW challenge. Cannot proceed.", style="error"
                )
                return False

            # Step 5: Filter Type (Optional)

            # Step 6: Match Tasks
            sim_thresh = 0.80
            matched: List[Tuple[Dict, Dict]] = []  # List of (old_task, new_task) tuples
            matched_new_ids: Set[str] = set()  # Track matched new tasks to avoid duplicates
            self.console.print(
                f"Matching tasks (> {sim_thresh * 100:.0f}% similarity)...", style="info"
            )
            # --- START: INSERTED FUZZY MATCHING LOOP ---
            # Use track for progress indication if task lists are large
            for old_task in track(
                old_tasks,
                description="Comparing tasks...",  # Progress bar description
                console=self.console,
                total=len(old_tasks),
                transient=True,  # Make bar disappear after loop
            ):
                best_match_new_task = None
                highest_ratio = 0.0
                old_text = old_task.get("text", "")
                old_id = old_task.get("id")  # Needed for debugging maybe

                if not old_text or not old_id:
                    # self.console.log(f"Skipping old task due to missing text/ID: {old_task}", style="subtle")
                    continue  # Skip old tasks without text or ID
                # Compare against all potentially available new tasks
                for new_task in new_tasks:
                    new_id = new_task.get("id")
                    new_text = new_task.get("text", "")

                    # Skip new tasks already matched or without text/ID
                    if not new_id or new_id in matched_new_ids or not new_text:
                        continue
                    # --- Calculate Similarity ---
                    # SequenceMatcher is good for finding similar sequences
                    # You could also explore other libraries like fuzzywuzzy or rapidfuzz if needed
                    # but difflib is built-in.
                    matcher = difflib.SequenceMatcher(None, old_text, new_text, autojunk=False)
                    ratio = matcher.ratio()  # Get similarity ratio (0.0 to 1.0)

                    # --- Check if this is the best match found *so far* for this *old_task* ---
                    if ratio > highest_ratio and ratio >= sim_thresh:
                        highest_ratio = ratio
                        best_match_new_task = new_task  # Store the potential best match

                # After checking all new tasks for the current old_task:
                if best_match_new_task:
                    # We found a suitable match above the threshold
                    matched.append((old_task, best_match_new_task))
                    # Mark the new task as used so it can't be matched again
                    matched_new_ids.add(best_match_new_task["id"])
            # --- END: INSERTED FUZZY MATCHING LOOP ---

            if not matched:
                self.console.print("No matching tasks found.", style="warning")
                return False
            self.console.print(f"Found {len(matched)} potential pairs:")
            for old, new in matched:
                ratio = difflib.SequenceMatcher(
                    None, old.get("text", ""), new.get("text", "")
                ).ratio()
                self.console.print(
                    f"  - '[subtle]{old.get('text', 'N/A')}[/]' -> '[rp_iris]{new.get('text', 'N/A')}[/]' ({ratio:.1%})"
                )
            if not Confirm.ask(
                "Proceed replicating attributes/tags?", default=True, console=self.console
            ):
                return False

            # === Step 7: Apply Attributes & Tags ===
            self.console.print("Applying attributes and tags...", style="info")
            errors = 0

            # Use track for progress feedback during API calls
            for old, new in track(
                matched,
                description="Syncing attributes/tags...",
                console=self.console,
                total=len(matched),
                transient=True,
            ):
                # Extract IDs and attributes
                # Corrected variable names
                new_id = new["id"]
                old_attr = old.get("attribute", "str")
                cur_attr = new.get("attribute", "str")
                if old_attr != cur_attr:
                    try:
                        self.api_client.set_attribute(new_id, old_attr)
                    except Exception as e:
                        self.console.print(f"Error setting attr: {e}", style="error")
                        errors += 1
                old_tags = old.get("tags", [])
                tags_to_add = [t for t in old_tags if t != old_cid]  # Filter out old challenge tag
                cur_new_tags = set(new.get("tags", []))
                for tag_id in tags_to_add:
                    if tag_id not in cur_new_tags:
                        try:
                            self.api_client.add_tag_to_task(new_id, tag_id)
                            time.sleep(0.05)
                        except Exception as e:
                            if "already has the tag" not in str(e).lower():
                                self.console.print(
                                    f"Error adding tag {tag_id}: {e}", style="error"
                                )
                                errors += 1
            self.console.print("Attribute/tag replication finished.", style="info")
            if errors > 0:
                self.console.print(f"Completed with {errors} errors.", style="warning")
            should_refresh = True

            # === Step 8: Apply Position (Optional & Slow) ===
            if Confirm.ask(
                "\nAttempt to replicate task order? ([warning]SLOW[/])",
                default=False,
                console=self.console,
            ):
                task_type_filter = None
                if Confirm.ask(
                    "Replicate for [highlight]Dailies only[/]?", default=True, console=self.console
                ):
                    task_type_filter = "daily"
                    old_tasks = [t for t in old_tasks if t.get("_type") == "daily"]
                    new_tasks = [t for t in new_tasks if t.get("_type") == "daily"]
                    self.console.print(
                        f"Filtered to {len(old_tasks)} old, {len(new_tasks)} new dailies.",
                        style="info",
                    )
                if not old_tasks or not new_tasks:
                    self.console.print("No matching types after filtering.", style="warning")
                    return False
                self.console.print("Determining original task order...", style="info")
                # Create map of {old_task_id: original_index} from the filtered old_tasks list
                old_task_order_map = {
                    task["id"]: i
                    for i, task in enumerate(old_tasks)
                    if isinstance(task, dict) and task.get("id")
                }

                # Sort the *matched* new task IDs based on the original order of their old counterparts
                def sort_key(match_tuple: Tuple[Dict, Dict]):
                    old_task_id = match_tuple[0].get("id")
                    return old_task_order_map.get(
                        old_task_id, float("inf")
                    )  # Place unmatched last

                sorted_matched_tasks = sorted(matched, key=sort_key)
                # Extract the new task IDs in the desired final order
                desired_new_task_order_ids = [
                    new_task["id"]
                    for old_task, new_task in sorted_matched_tasks
                    if isinstance(new_task, dict) and new_task.get("id")
                ]

                if not desired_new_task_order_ids:
                    self.console.print("Could not determine desired task order.", style="warning")
                else:
                    num_to_move = len(desired_new_task_order_ids)
                    # Estimate time using the actual request interval from the API client
                    est_time_secs = num_to_move * (
                        self.api_client.request_interval + 0.1
                    )  # Add small buffer
                    self.console.print(f"Will move {num_to_move} tasks to replicate order.")
                    self.console.print(
                        f"[warning]Estimated time: ~{est_time_secs:.1f} seconds due to API rate limits.[/warning]"
                    )

                    if Confirm.ask(
                        "Proceed with moving tasks?", default=True, console=self.console
                    ):
                        move_errors = 0
                        # Move tasks to the top (position 0) one by one, IN REVERSE of the desired final order
                        # This ensures they end up in the correct order at the top.
                        for task_id_to_move in track(
                            reversed(desired_new_task_order_ids),
                            description="Moving tasks to position 0...",
                            console=self.console,
                            total=num_to_move,
                            transient=True,
                        ):
                            try:
                                self.api_client.move_task_to_position(task_id_to_move, 0)
                                # Rate limiting is handled automatically by api_client._wait_for_rate_limit
                            except Exception as e:
                                # Use print within track context
                                self.console.print(
                                    f"\n[error]Error moving task {task_id_to_move}: {e}[/]"
                                )
                                move_errors += 1

                        self.console.print("Task moving finished.", style="info")
                        if move_errors > 0:
                            self.console.print(
                                f"Completed moving with {move_errors} errors.", style="warning"
                            )
                        should_refresh = True  # Order definitely changed (or errors occurred)
                    else:
                        self.console.print("Task moving cancelled.", style="info")
            else:
                self.console.print("Skipping position replication.", style="info")

            # === Step 9: Cleanup (Optional Unlink Old) ===
            self.console.print("\nReplication process complete.", style="success")
            if old_cid and Confirm.ask(
                f"\nRemove all tasks from OLD challenge '[rp_iris]{old_cname}[/]'?",
                default=False,
                console=self.console,
            ):
                remove_permanently = Confirm.ask(
                    "Remove OLD tasks permanently? (No = Keep personal copies)",
                    default=False,
                    console=self.console,
                )
                keep_param = "remove-all" if remove_permanently else "keep-all"
                action_desc = (
                    "[error]removing permanently[/]"
                    if keep_param == "remove-all"
                    else "keeping personal copies"
                )
                if Confirm.ask(
                    f"Confirm unlinking ALL tasks from OLD challenge ({action_desc})?",
                    default=True,
                    console=self.console,
                ):
                    self.console.print(
                        f"Attempting bulk unlink for OLD challenge ({old_cid})...", style="info"
                    )
                    try:
                        # Call the correct API method
                        response = self.api_client.unlink_all_challenge_tasks(
                            old_cid, keep="remove-all"
                        )
                        self.console.print(
                            f"Successfully unlinked tasks from old challenge '{old_cname}'.",
                            style="success",
                        )
                        should_refresh = False
                    except Exception as e:
                        self.console.print(
                            f"Error unlinking tasks from old challenge: {e}", style="error"
                        )
                else:
                    self.console.print("Unlinking from old challenge cancelled.", style="info")
            else:
                self.console.print("Skipping cleanup of old challenge tasks.", style="info")
                # ... (Confirm keep/remove, confirm unlink, call unlink_all_challenge_tasks) ...

        except (ValueError, IndexError) as e:
            self.console.print(f"Invalid selection: {e}", style="error")
        except KeyboardInterrupt:
            self.console.print("\nReplication cancelled.")
        except Exception as e:
            self.console.print(f"Unexpected error during replication: {e}", style="error")
            self.console.print_exception(show_locals=False)
            should_refresh = False
        return should_refresh

    # MARK: - Static Helper Methods
    # & - def _get_total(...) (Keep previous implementation)
    @staticmethod
    def _get_total(task_counts: Dict) -> int:
        """Calculates total task count from the categorized counts dictionary."""
        # Re-use implementation from app_v5.txt
        total = 0
        if not isinstance(task_counts, dict):
            return 0
        try:
            for cat, data in task_counts.items():
                if isinstance(data, dict):
                    total += sum(
                        v for k, v in data.items() if isinstance(v, int) and not k.startswith("_")
                    )
                elif isinstance(data, int):
                    total += data
        except Exception as e:
            console.log(f"Error calculating total task count: {e}", style="warning")
            return -1
        return total


# MARK: - Entry Point (Example for running the CLI)
# Typically lives in project root, e.g., main.py or run_pixabit.py
# if __name__ == "__main__":
#     try:
#         app = CliApp()
#         app.run()
#     except KeyboardInterrupt:
#         console.print("\n[bold yellow]Ctrl+C detected. Exiting Pixabit.[/bold yellow]")
#         sys.exit(0)
#     except Exception as e:
#         # Use console for final error display if available
#         try: from pixabit.utils.display import console
#         except ImportError: console = None
#         if console:
#              console.print(f"\n[error]An unexpected critical error occurred:[/error]")
#              console.print_exception(show_locals=True, word_wrap=False)
#         else:
#              import traceback
#              print(f"\nAn unexpected critical error occurred: {e}")
#              traceback.print_exc()
#         sys.exit(1)
