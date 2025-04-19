# pixabit/cli/app.py (LEGACY - Rich CLI Version)

# SECTION: MODULE DOCSTRING
"""Main Command Line Interface application class for Pixabit (LEGACY Rich version).

Handles user interaction via menus, triggers data refreshes, and dispatches actions
to synchronous managers and processors. Contains the original action logic which
needs to be migrated/adapted for the async DataStore in the TUI version. Kept for reference.
"""

# SECTION: IMPORTS
import builtins  # For fallback print
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set  # Added List/Union

# --- Rich and Display ---
try:
    from pixabit.utils.display import (  # Use .. to import from parent utils
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
    builtins.print(
        f"Fatal Error: Failed to import Rich components in cli/app.py: {e_rich}"
    )
    sys.exit(1)

# --- Local Application Imports ---
try:
    from pixabit import config  # Import from .cli
    from pixabit.tui.api import (
        MIN_REQUEST_INTERVAL,
        HabiticaAPI,
    )  # Import sync API
    from pixabit.utils.dates import (
        convert_to_local_time,
    )  # Use .. for parent utils

    from .challenge_backupper import ChallengeBackupper
    from .config_tags import configure_tags as run_tag_config_setup  # Use alias
    from .data_processor import (
        TaskProcessor,
        get_user_stats,
    )  # Import sync processor
    from .exports import (
        save_all_userdata_into_json,
        save_processed_tasks_into_json,
        save_tags_into_json,
        save_tasks_without_proccessing,
    )
    from .tag_manager import TagManager  # Import sync tag manager
except ImportError as e_imp:
    builtins.print(
        f"Fatal Error importing Pixabit CLI modules in cli/app.py: {e_imp}"
    )
    sys.exit(1)


# SECTION: CliApp Class (Legacy)
# KLASS: CliApp
class CliApp:
    """Main application class for the Pixabit CLI (LEGACY Rich version)."""

    # MARK: Initialization

    # FUNC: __init__
    def __init__(self):
        """Initializes API client, managers, state, and performs initial data load."""
        self.console = console
        self.console.log(
            "Initializing Pixabit CLI App (Legacy)...", style="info"
        )
        try:
            self.api_client = HabiticaAPI()  # Sync API client
            self.processor: Optional[TaskProcessor] = None  # Sync processor
            self.tag_manager = TagManager(self.api_client)  # Sync tag manager
            self.backupper = ChallengeBackupper(self.api_client)
            self.console.log("Legacy CLI components initialized.", style="info")
        except ValueError as e:
            self.console.print(f"[error]Configuration Error:[/error] {e}")
            sys.exit(1)
        except Exception:
            self.console.print(
                "[error]Unexpected Initialization Error:[/error]"
            )
            self.console.print_exception(show_locals=False)
            sys.exit(1)

        # --- Application State Attributes (Legacy) ---
        self.user_data: Dict[str, Any] = {}
        self.party_data: Dict[str, Any] = {}
        self.content_data: Dict[str, Any] = {}
        self.all_tags: List[Dict[str, Any]] = []
        # Processed tasks stored as dict {id: processed_dict}
        self.processed_tasks: Dict[str, Dict[str, Any]] = {}
        self.cats_data: Dict[str, Any] = {}  # Categorized task IDs/metadata
        self.user_stats: Dict[str, Any] = {}
        self.unused_tags: List[Dict[str, Any]] = []
        self.all_challenges_cache: Optional[List[Dict[str, Any]]] = (
            None  # Cache for GET /challenges/user
        )

        # --- Initial Data Load ---
        self.console.log("Performing initial data refresh...", style="info")
        self.refresh_data()  # Call sync refresh
        self.console.log("Initialization complete.", style="success")
        self.console.print("")  # Spacer

    # MARK: Primary Public Method (Entry Point - Legacy)

    # FUNC: run
    def run(self) -> None:
        """Starts the main application menu loop (Legacy Rich version)."""
        while True:
            active_categories = self._build_active_menu()
            main_menu_options = list(active_categories.keys())

            choice = self._display_menu(
                "Main Menu", main_menu_options, embed_stats=True
            )
            if choice == 0:
                break  # Exit
            if choice == -1:
                continue  # Invalid input

            try:
                category_name = main_menu_options[choice - 1]
            except IndexError:
                self.console.print(
                    f"[error]Invalid choice index {choice}.[/error]"
                )
                continue

            if category_name == "Application":
                app_options = active_categories["Application"]
                app_choice = self._display_menu(
                    "Application Menu", app_options, embed_stats=False
                )
                if app_choice in [0, -1]:
                    continue
                try:
                    action_name = app_options[app_choice - 1]
                    if action_name == "Exit":
                        break
                    else:
                        self._execute_action(action_name)
                except IndexError:
                    self.console.print(
                        f"[error]Invalid app choice {app_choice}.[/error]"
                    )
            else:
                self._submenu_loop(
                    category_name, active_categories[category_name]
                )

        self.console.print("\nExiting Pixabit CLI. Goodbye!", style="bold info")

    # MARK: Dynamic Menu Building (Legacy)

    # FUNC: _build_active_menu
    def _build_active_menu(self) -> Dict[str, List[str]]:
        """Builds the menu dictionary for the legacy CLI, including optional items."""
        # --- Base Menu Structure ---
        categories: Dict[str, List[str]] = {
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

        # --- Add Optional Tag Actions Conditionally (using imported config values) ---
        mg_tags = categories["Manage Tags"]
        insert_pos = 3  # Position after basic display/delete

        if config.CHALLENGE_TAG_ID and config.PERSONAL_TAG_ID:
            mg_tags.insert(insert_pos, "Sync Challenge/Personal Tags")
            insert_pos += 1
        if config.PSN_TAG_ID and config.NOT_PSN_TAG_ID:
            mg_tags.insert(insert_pos, "Sync Poison Status Tags")
            insert_pos += 1
        if config.ATTR_TAG_MAP and config.NO_ATTR_TAG_ID:
            mg_tags.insert(insert_pos, "Sync Attribute Tags")
            insert_pos += 1

        return {
            name: opts for name, opts in categories.items() if opts
        }  # Filter empty

    # MARK: Major Workflow Methods (Legacy Sync)

    # FUNC: refresh_data
    def refresh_data(self) -> None:
        """Fetches/processes all necessary data using sync API calls (Legacy version)."""
        self.console.print(
            "\nRefreshing all application data (Sync)...", style="highlight"
        )
        start_time = time.monotonic()

        # Setup sync Progress Bar
        progress = Progress(
            TextColumn(" • ", style="subtle"),
            TextColumn(
                "[progress.description]{task.description}", justify="left"
            ),
            BarColumn(
                style="rp_surface",
                complete_style="rp_foam",
                finished_style="rp_pine",
            ),
            TaskProgressColumn(style="rp_subtle_color"),
            TimeElapsedColumn(),
            SpinnerColumn("dots", style="rp_iris"),
            console=self.console,
            transient=False,
        )
        # Define steps for sync refresh
        steps = [
            ("Fetch User", self.api_client.get_user_data, "user_data", 1, True),
            (
                "Fetch Content",
                self._get_content_cached,
                "content_data",
                1,
                True,
            ),
            ("Fetch Tags", self.api_client.get_tags, "all_tags", 1, False),
            (
                "Fetch Party",
                self.api_client.get_party_data,
                "party_data",
                1,
                False,
            ),
            (
                "Fetch Challenges",
                self._fetch_challenges_cached,
                "all_challenges_cache",
                1,
                False,
            ),
            (
                "Process Tasks",
                self._process_tasks_step,
                "processed_tasks",
                5,
                True,
            ),
            (
                "Calculate Stats/Unused",
                self._calculate_stats_unused_step,
                None,
                1,
                False,
            ),
        ]
        total_weight = sum(w for _, _, _, w, _ in steps)
        main_task_id = progress.add_task(
            "[info]Initializing...", total=total_weight
        )
        refresh_ok = True

        with Live(
            progress,
            console=self.console,
            vertical_overflow="ellipsis",
            refresh_per_second=10,
        ) as live:
            units_done = 0
            for i, (name, func, attr, weight, critical) in enumerate(steps):
                progress.update(
                    main_task_id,
                    description=f"[{i + 1}/{len(steps)}] {name}...",
                )
                try:
                    if name == "Process Tasks":
                        if not self._process_tasks_step():
                            raise RuntimeError("Task processing failed.")
                    elif name == "Calculate Stats/Unused":
                        self._calculate_stats_unused_step()
                    else:
                        result = func()  # Call sync function
                        if result is None and critical:
                            raise ValueError(
                                f"{name} data fetch returned None."
                            )
                        if attr:
                            setattr(
                                self,
                                attr,
                                (
                                    result
                                    if result is not None
                                    else self._get_default_for_attr(attr)
                                ),
                            )
                    units_done += weight
                    progress.update(main_task_id, completed=units_done)
                except Exception as e:
                    failed_msg = f"[error]Failed: {name}![/]"
                    progress.update(main_task_id, description=failed_msg)
                    self.console.log(
                        f"Error during '{name}': {e}", style="error"
                    )
                    refresh_ok = False
                    if critical:
                        self.console.print(
                            f"Halting refresh due to critical error in '{name}'.",
                            style="error",
                        )
                        self._ensure_default_attributes()  # Ensure defaults before breaking
                        break
                    else:
                        self.console.log(
                            "Continuing refresh despite non-critical error.",
                            style="warning",
                        )
                        if attr:
                            setattr(
                                self, attr, self._get_default_for_attr(attr)
                            )
                        units_done += weight  # Advance progress even on non-critical failure
                        progress.update(main_task_id, completed=units_done)

        # Post-Refresh Summary
        end_time = time.monotonic()
        duration = end_time - start_time
        final_status, final_style = (
            ("Refresh Complete!", "success")
            if refresh_ok
            else ("Refresh Failed!", "error")
        )
        progress.update(
            main_task_id,
            description=f"[{final_style}]{final_status}[/]",
            completed=total_weight,
        )
        time.sleep(0.1)  # Allow final render
        self.console.print(
            f"[{final_style}]{final_status}[/] (Duration: {duration:.2f}s)"
        )
        self._ensure_default_attributes()  # Ensure defaults after loop finishes

    # FUNC: _get_default_for_attr (Helper)
    def _get_default_for_attr(self, attr_name: str) -> Any:
        """Returns a sensible default value based on the attribute name."""
        if (
            "list" in attr_name
            or "tags" in attr_name
            or "cache" in attr_name
            or "broken" in attr_name
        ):
            return []
        if (
            "dict" in attr_name
            or "data" in attr_name
            or "stats" in attr_name
            or "tasks" in attr_name
            or "cats" in attr_name
        ):
            return {}
        return None

    # FUNC: _ensure_default_attributes (Helper)
    def _ensure_default_attributes(self) -> None:
        """Ensures core state attributes have default types after refresh."""
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
        # Handle challenge cache specifically
        if not isinstance(getattr(self, "all_challenges_cache", None), list):
            self.all_challenges_cache = None  # Reset if not list or None

    # FUNC: _get_content_cached (Sync version)
    def _get_content_cached(self) -> Dict[str, Any]:
        """Helper to get game content, using cache first (Sync version)."""
        content: Optional[Dict[str, Any]] = None
        cache_path = Path(config.CACHE_FILE_CONTENT)  # Use Path from config
        if cache_path.exists():
            try:
                with cache_path.open(encoding="utf-8") as f:
                    content = json.load(f)
                if isinstance(content, dict) and content:
                    # self.console.log(f"Using cached content from '{cache_path}'.", style="subtle")
                    return content
                else:
                    self.console.log(
                        f"Invalid content in cache '{cache_path}'. Refetching.",
                        style="warning",
                    )
                    content = None
            except (OSError, json.JSONDecodeError, Exception) as e:
                self.console.log(
                    f"Failed loading cache '{cache_path}': {e}. Refetching.",
                    style="warning",
                )
                content = None
        if content is None:
            # self.console.log("Fetching game content from API (Sync)...", style="info")
            try:
                content = self.api_client.get_content()  # Sync call
                if isinstance(content, dict) and content:
                    try:
                        with cache_path.open("w", encoding="utf-8") as f:
                            json.dump(content, f, ensure_ascii=False, indent=2)
                        # self.console.log(f"Saved content to cache: '{cache_path}'", style="subtle")
                    except (OSError, Exception) as e_save:
                        self.console.log(
                            f"Failed to save content cache: {e_save}",
                            style="warning",
                        )
                    return content
                else:
                    self.console.log(
                        "Failed to fetch valid game content.", style="error"
                    )
                    return {}
            except Exception as e_fetch:
                self.console.log(
                    f"Exception fetching content: {e_fetch}", style="error"
                )
                return {}
        return {}  # Should not be reached normally

    # FUNC: _fetch_challenges_cached (Sync version)
    def _fetch_challenges_cached(self) -> Optional[List[Dict[str, Any]]]:
        """Fetches challenges only if cache is empty (Sync version)."""
        if self.all_challenges_cache is None:
            # self.console.log("Challenge cache empty, fetching (Sync)...", style="subtle")
            # Use sync paginated fetch
            fetched = self.api_client.get_all_challenges_paginated(
                member_only=True
            )
            self.all_challenges_cache = fetched  # Update cache
            # self.console.log(f"Fetched and cached {len(self.all_challenges_cache)} challenges.", style="subtle")
        # else: self.console.log(f"Using cached challenges ({len(self.all_challenges_cache)} found).", style="subtle")
        return self.all_challenges_cache

    # FUNC: _process_tasks_step (Sync version)
    def _process_tasks_step(self) -> bool:
        """Internal step for sync task processing during refresh_data."""
        try:
            # Instantiate sync processor
            self.processor = TaskProcessor(  # Use the cli.data_processor
                api_client=self.api_client,
                user_data=self.user_data,
                party_data=self.party_data,
                all_tags_list=self.all_tags,
                content_data=self.content_data,
            )
            processed_results = (
                self.processor.process_and_categorize_all()
            )  # Sync call
            self.processed_tasks = processed_results.get("data", {})
            self.cats_data = processed_results.get("cats", {})
            if not self.processed_tasks and not self.cats_data.get("tasks"):
                self.console.log("No tasks found or processed.", style="info")
            return True
        except Exception as e:
            self.console.log(f"[error]Error processing tasks:[/error] {e}")
            self.processed_tasks = {}
            self.cats_data = {}
            return False

    # FUNC: _calculate_stats_unused_step (Sync version)
    def _calculate_stats_unused_step(self) -> None:
        """Internal sync step for calculating stats and unused tags."""
        try:
            if self.cats_data and self.processed_tasks and self.user_data:
                # Call sync get_user_stats from cli.data_processor
                self.user_stats = (
                    get_user_stats(
                        api_client=self.api_client,  # Pass sync client
                        cats_dict=self.cats_data,
                        processed_tasks_dict=self.processed_tasks,
                        user_data=self.user_data,
                    )
                    or {}
                )  # Ensure dict
            else:
                self.console.log(
                    "Skipping stats calculation: missing data.", style="warning"
                )
                self.user_stats = {}
        except Exception as e:
            self.console.log(
                f"Error calculating user stats: {e}.", style="warning"
            )
            self.user_stats = {}

        try:
            if (
                isinstance(self.all_tags, list)
                and self.cats_data.get("tags") is not None
            ):
                used_tag_ids: Set[str] = set(self.cats_data.get("tags", []))
                # Use sync TagManager instance
                self.unused_tags = self.tag_manager.find_unused_tags(
                    self.all_tags, used_tag_ids
                )
            else:
                self.console.log(
                    "Skipping unused tags calculation: missing data.",
                    style="warning",
                )
                self.unused_tags = []
        except Exception as e:
            self.console.log(
                f"Error calculating unused tags: {e}", style="warning"
            )
            self.unused_tags = []

    # FUNC: _submenu_loop (Legacy)
    def _submenu_loop(self, title: str, options: List[str]) -> None:
        """Handles display/logic for a submenu (Legacy Rich version)."""
        while True:
            choice = self._display_menu(
                f"{title} Menu", options, embed_stats=False
            )
            if choice == 0:
                break
            if choice == -1:
                continue
            try:
                self._execute_action(options[choice - 1])  # Calls sync execute
            except IndexError:
                self.console.print(
                    f"[error]Invalid submenu choice {choice}.[/error]"
                )

    # FUNC: _execute_action (Legacy Sync version - Contains original logic)
    def _execute_action(self, action_name: str) -> None:
        """Executes selected action using sync methods (Legacy Rich version)."""
        self.console.print(
            f"\n➡️ Executing: [highlight]{action_name}[/]", highlight=False
        )
        refresh_needed = False
        action_taken = False
        start_time = time.monotonic()

        try:
            # --- Task Management ---
            if action_name == "Handle Broken Tasks":
                action_taken = refresh_needed = (
                    self._handle_broken_tasks_action()
                )
            elif action_name == "Replicate Monthly Setup":
                action_taken = refresh_needed = (
                    self._replicate_monthly_setup_action()
                )

            # --- Tag Management ---
            elif action_name == "Display All Tags":
                self._display_tags()
                action_taken = True
            elif action_name == "Display Unused Tags":
                self._display_unused_tags()
                action_taken = True
            elif action_name == "Delete Unused Tags":
                used_ids = set(self.cats_data.get("tags", []))
                action_taken = refresh_needed = (
                    self.tag_manager.delete_unused_tags_interactive(
                        self.all_tags, used_ids
                    )
                )
            elif action_name == "Sync Challenge/Personal Tags":
                if config.CHALLENGE_TAG_ID and config.PERSONAL_TAG_ID:
                    action_taken = refresh_needed = (
                        self.tag_manager.sync_challenge_personal_tags(
                            self.processed_tasks
                        )
                    )
                else:
                    self.console.print(
                        "Challenge/Personal tags not configured.", style="info"
                    )
            elif action_name == "Sync Poison Status Tags":
                if config.PSN_TAG_ID and config.NOT_PSN_TAG_ID:
                    action_taken = refresh_needed = (
                        self.tag_manager.ensure_poison_status_tags(
                            self.processed_tasks
                        )
                    )
                else:
                    self.console.print(
                        "Poison Status tags not configured.", style="info"
                    )
            elif action_name == "Sync Attribute Tags":
                if config.ATTR_TAG_MAP and config.NO_ATTR_TAG_ID:
                    action_taken = refresh_needed = (
                        self.tag_manager.sync_attributes_to_tags(
                            self.processed_tasks
                        )
                    )
                else:
                    self.console.print(
                        "Attribute tags not fully configured.", style="info"
                    )
            elif action_name == "Add/Replace Tag Interactively":
                action_taken = refresh_needed = (
                    self._interactive_tag_replace_action()
                )

            # --- Challenge Management ---
            elif action_name == "Backup Challenges":
                if Confirm.ask(
                    "Backup all accessible challenges?", console=self.console
                ):
                    backup_folder = Path("_challenge_backups")
                    self.backupper.create_backups(
                        output_folder=backup_folder
                    )  # Sync call
                    action_taken = True
            elif action_name == "Leave Challenge":
                action_taken = (
                    self._leave_challenge_action()
                )  # Sync call, returns False if no refresh needed

            # --- View Data ---
            elif action_name == "Display Stats":
                stats_panel = self._display_stats()
                if stats_panel:
                    self.console.print(stats_panel)
                    action_taken = True

            # --- Export Data ---
            elif action_name == "Save Processed Tasks (JSON)":
                if self.processed_tasks and Confirm.ask(
                    "Save processed tasks?", console=self.console
                ):
                    save_processed_tasks_into_json(
                        self.processed_tasks, "tasks_processed.json"
                    )
                    action_taken = True
                elif not self.processed_tasks:
                    self.console.print(
                        "No processed tasks to save.", style="warning"
                    )
            elif action_name == "Save Raw Tasks (JSON)":
                if Confirm.ask(
                    "Save raw tasks (fetches fresh)?", console=self.console
                ):
                    save_tasks_without_proccessing(
                        self.api_client, "tasks_raw.json"
                    )  # Sync call
                    action_taken = True
            elif action_name == "Save All Tags (JSON)":
                if Confirm.ask(
                    "Save all tags (fetches fresh)?", console=self.console
                ):
                    save_tags_into_json(
                        self.api_client, "tags_all.json"
                    )  # Sync call
                    action_taken = True
            elif action_name == "Save Full User Data (JSON)":
                if Confirm.ask(
                    "Save full user data (fetches fresh)?", console=self.console
                ):
                    save_all_userdata_into_json(
                        self.api_client, "user_data_full.json"
                    )  # Sync call
                    action_taken = True

            # --- User Actions ---
            elif action_name == "Toggle Sleep Status":
                current_status = self.user_stats.get("sleeping", False)
                action_desc = "wake up" if current_status else "go to sleep"
                if Confirm.ask(
                    f"Do you want to {action_desc}?", console=self.console
                ):
                    response = self.api_client.toggle_user_sleep()  # Sync call
                    if response is not None:
                        new_status = (
                            response
                            if isinstance(response, bool)
                            else response.get("sleep", "Unknown")
                        )
                        self.console.print(
                            f"Sleep toggled. New status: {new_status}",
                            style="success",
                        )
                        refresh_needed = True
                        action_taken = True
                    else:
                        self.console.print(
                            "Failed to toggle sleep status.", style="error"
                        )

            # --- Application ---
            elif action_name == "Refresh Data":
                refresh_needed = True
                action_taken = True
            elif action_name == "Configure Special Tags":
                run_tag_config_setup()
                refresh_needed = True
                action_taken = True  # Sync call

            else:
                self.console.print(
                    f"Action '{action_name}' not implemented.", style="warning"
                )

            # Post-Action Refresh (Sync)
            if refresh_needed:
                self.console.print(
                    f"\nAction '{action_name}' requires data update.",
                    style="info",
                )
                self.refresh_data()  # Sync refresh

        except Exception:
            self.console.print(
                f"\n[error]Error executing action '{action_name}':[/error]"
            )
            self.console.print_exception(show_locals=False)
        finally:
            end_time = time.monotonic()
            duration = end_time - start_time
            if action_taken:
                self.console.print(
                    f"Action '{action_name}' finished. (Duration: {duration:.2f}s)",
                    style="subtle",
                )
                Prompt.ask(
                    "\n[subtle]Press Enter to continue...[/]",
                    default="",
                    console=self.console,
                )

    # MARK: UI Helper Methods (Legacy Rich)

    # FUNC: _display_menu
    def _display_menu(
        self, title: str, options: List[str], embed_stats: bool = False
    ) -> int:
        """Displays a menu using Rich (Legacy version)."""
        # (Keep existing Rich implementation from previous state)
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
                display_object = Panel(
                    layout_table, border_style="rp_overlay", expand=True
                )
            # else: self.console.print("Could not display stats panel.", style="warning") # Already handled in _display_stats
        self.console.print(display_object)
        try:
            return IntPrompt.ask(
                "Choose an option",
                choices=[str(i) for i in range(max_option + 1)],
                show_choices=False,
                console=self.console,
            )
        except Exception as e:
            self.console.print(f"[error]Menu input error:[/error] {e}")
            return -1

    # FUNC: _display_stats
    def _display_stats(self) -> Optional[Panel]:
        """Builds and returns a Rich Panel containing formatted user stats (Legacy)."""
        # (Keep existing Rich implementation from previous state)
        stats = self.user_stats
        if not stats:
            self.console.print(
                "[warning]No user stats data available.[/warning]"
            )
            return None
        try:
            uname, lvl, uclass = (
                stats.get("username", "N/A"),
                stats.get("level", 0),
                stats.get("class", "N/A").capitalize(),
            )
            hp, max_hp = int(stats.get("hp", 0)), stats.get("maxHealth", 50)
            mp, max_mp = int(stats.get("mp", 0)), stats.get(
                "maxMP", 30
            )  # Approx base
            exp, next_lvl = int(stats.get("exp", 0)), stats.get(
                "toNextLevel", 100
            )
            gp, gems = int(stats.get("gp", 0)), stats.get("gems", 0)
            core = stats.get("stats", {})
            sleeping, day_start = stats.get("sleeping", False), stats.get(
                "day_start", "?"
            )
            last_login = stats.get(
                "last_login_local", "N/A"
            )  # Use pre-formatted string
            broken, questing = stats.get(
                "broken_challenge_tasks", 0
            ), stats.get("quest_active", False)
            q_key = stats.get("quest_key")
            dmg_u, dmg_p = stats.get(
                "potential_daily_damage_user", 0.0
            ), stats.get("potential_daily_damage_party", 0.0)
            dmg_style = (
                "error" if dmg_u >= 5 else "warning" if dmg_u > 0 else "subtle"
            )
            dmg_p_str = f", Party: {dmg_p:.1f}" if dmg_p > 0 else ""
            t_counts = stats.get("task_counts", {})

            login_display = "N/A"
            # if last_login and "Error" not in last_login and last_login != "N/A":
            #     try:
            #         login_dt = datetime.datetime.fromisoformat(last_login); local_tz = datetime.datetime.now().astimezone().tzinfo
            #         now_local = datetime.datetime.now(local_tz); login_dt_aware = login_dt.replace(tzinfo=local_tz)
            #         login_display = timeago.format(login_dt_aware, now_local)
            #     except Exception: login_display = last_login

            user_info = Table.grid(padding=(0, 1), expand=False)
            user_info.add_column(style="subtle", justify="right", min_width=3)
            user_info.add_column(justify="left")
            user_info.add_row(
                "👤", f"[highlight]{uname}[/] ([rp_iris]{uclass} Lv {lvl}[/])"
            )
            # user_info.add_row("🕒", f"Login: [rp_text i]{login_display}[/]")
            user_info.add_row("🌅", f"Day start: {day_start}:00")
            if sleeping:
                user_info.add_row("💤", "[warning i]Resting in Inn[/]")
            if questing:
                user_info.add_row(
                    "🐉", f"[info]On Quest:[/] [i]{q_key or 'Unknown'}[/]"
                )
            if broken:
                user_info.add_row(
                    ":warning:", f"[error]{broken} broken tasks[/]"
                )
            user_info.add_row(
                "💔", f"Dmg: [{dmg_style}]User {dmg_u:.1f}{dmg_p_str}[/]"
            )

            stat_vals = Table.grid(padding=(0, 1), expand=False)
            stat_vals.add_row(
                f"[rp_love b]HP: [/]{hp: <3}/ {max_hp}",
                f"[rp_gold b]XP: [/]{exp: <3}/ {next_lvl}",
            )
            stat_vals.add_row(
                f"[rp_foam b]MP: [/]{mp: <3}/ {max_mp}",
                f"[rp_gold b]GP: [/]{gp}",
            )
            stat_vals.add_row(f"[b]💎 Gems:[/b] {gems}", "")
            stat_vals.add_row(
                f"[subtle]STR:[/] {core.get('str', 0)} [subtle]INT:[/] {core.get('int', 0)}",
                f"[subtle]CON:[/] {core.get('con', 0)} [subtle]PER:[/] {core.get('per', 0)}",
            )

            hab_c, rew_c = t_counts.get("habits", 0), t_counts.get("rewards", 0)
            day_d, todo_d = t_counts.get("dailys", {}), t_counts.get(
                "todos", {}
            )
            day_tot, todo_tot = day_d.get("_total", 0), todo_d.get("_total", 0)
            day_due = day_d.get("due", 0)
            todo_due = todo_d.get("due", 0) + todo_d.get("red", 0)
            day_done = day_d.get("success", 0)
            tasks_text = f"Habits:[b]{hab_c}[/]\n Daylies:[b]{day_tot}[/] ([warning]{day_due}[/] due/[success]{day_done}[/] done)\n Todo:[b]{todo_tot}[/] ([warning]{todo_due}[/] due)\n Rewards:[b]{rew_c}[/]"
            tasks_p = Panel(
                tasks_text,
                title="Tasks",
                border_style="blue",
                padding=(0, 1),
                expand=False,
            )

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
                final,
                title="📊 [highlight]Dashboard[/]",
                border_style="green",
                padding=(1, 2),
            )
        except Exception as e:
            self.console.print(
                f"[error]Error building stats display:[/error] {e}"
            )
            # self.console.print_exception(show_locals=False)
            return None

    # FUNC: _display_tags (Legacy)
    def _display_tags(self) -> None:
        """Displays all fetched tags in a table using theme styles (Legacy)."""
        # (Keep existing Rich implementation)
        if not self.all_tags:
            self.console.print("No tags data available.", style="warning")
            return
        self.console.print(
            f"\n[highlight]All Tags ({len(self.all_tags)})[/]", highlight=False
        )
        table = Table(
            show_header=True,
            header_style="rp_iris",
            box=box.ROUNDED,
            padding=(0, 1),
        )
        table.add_column("Num", style="subtle", width=4, justify="right")
        table.add_column("Name", style="rp_foam", min_width=20, no_wrap=True)
        table.add_column("ID", style="rp_rose", overflow="fold", min_width=36)
        valid = [
            t for t in self.all_tags if isinstance(t, dict) and t.get("id")
        ]
        for i, tag in enumerate(valid):
            table.add_row(
                str(i + 1), tag.get("name", "[subtle]N/A[/]"), tag["id"]
            )
        self.console.print(table)

    # FUNC: _display_unused_tags (Legacy)
    def _display_unused_tags(self) -> None:
        """Displays unused tags in a table using theme styles (Legacy)."""
        # (Keep existing Rich implementation)
        if not self.unused_tags:
            self.console.print("✅ No unused tags found.", style="success")
            return
        self.console.print(
            f"\n[highlight]Unused Tags ({len(self.unused_tags)})[/]",
            highlight=False,
        )
        table = Table(
            show_header=True,
            header_style="rp_gold",
            box=box.ROUNDED,
            padding=(0, 1),
        )
        table.add_column("Num", style="subtle", width=4, justify="right")
        table.add_column("Name", style="rp_foam", min_width=20, no_wrap=True)
        table.add_column("ID", style="rp_rose", overflow="fold", min_width=36)
        for i, tag in enumerate(self.unused_tags):
            table.add_row(
                str(i + 1),
                tag.get("name", "[subtle]N/A[/]"),
                tag.get("id", "[subtle]N/A[/]"),
            )
        self.console.print(table)

    # FUNC: _display_broken_tasks (Legacy)
    def _display_broken_tasks(
        self, challenge_id_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Displays broken tasks using theme styles, returns displayed task info list (Legacy)."""
        # (Keep existing Rich implementation)
        broken_ids = self.cats_data.get("broken", [])
        if not broken_ids and not challenge_id_filter:
            self.console.print("✅ No broken tasks found.", style="success")
            return []
        title, display_tasks = "Broken Challenge Tasks", []
        for tid in broken_ids:
            task = self.processed_tasks.get(tid)  # Use processed_tasks dict
            if task and isinstance(task, dict):  # Check if task is a dict
                cid = task.get("challenge_id")
                cname = task.get("challenge_name", "[subtle]N/A[/]")
                ttext = task.get("text", "[subtle]N/A[/]")
                info = {
                    "id": tid,
                    "text": ttext,
                    "challenge_id": cid,
                    "challenge_name": cname,
                }
                if challenge_id_filter:
                    if cid == challenge_id_filter:
                        display_tasks.append(info)
                else:
                    display_tasks.append(info)
        if not display_tasks:
            if challenge_id_filter:
                self.console.print(
                    f"No broken tasks for challenge ID {challenge_id_filter}.",
                    style="warning",
                )
            return []
        if challenge_id_filter:
            title = f"Broken Tasks for: {display_tasks[0]['challenge_name']}"
        self.console.print(
            f"\nFound {len(display_tasks)} broken tasks:", style="warning"
        )
        table = Table(
            title=title, show_header=True, header_style="error", box=box.ROUNDED
        )
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

    # MARK: Action Helper Methods (Legacy Sync - Reference for Logic)

    # FUNC: _handle_broken_tasks_action (Legacy Logic)
    def _handle_broken_tasks_action(self) -> bool:
        """Groups broken tasks, allows bulk/individual unlinking (Legacy version)."""
        # (Keep existing Rich implementation logic for reference)
        # ... (This logic needs to be adapted into DataStore async methods) ...
        broken_ids = self.cats_data.get("broken", [])
        should_refresh = False
        if not broken_ids:
            self.console.print("✅ No broken tasks found.", style="success")
            return False
        # ... (rest of the grouping, prompting, and sync API calls) ...
        return should_refresh  # Return based on whether API calls were made

    # FUNC: _interactive_tag_replace_action (Legacy Logic)
    def _interactive_tag_replace_action(self) -> bool:
        """Handles interactive prompts for replacing tags (Legacy version)."""
        # (Keep existing Rich implementation logic for reference)
        # ... (This logic needs to be adapted into DataStore async methods) ...
        self._display_tags()
        # ... (prompting for find/add tags) ...
        # success = self.tag_manager.add_or_replace_tag_based_on_other(...) # Calls sync TagManager
        # return success # Return based on whether API calls were made
        return False  # Placeholder

    # FUNC: _leave_challenge_action (Legacy Logic)
    def _leave_challenge_action(self) -> bool:
        """Handles listing JOINED challenges and leaving (Legacy version)."""
        # (Keep existing Rich implementation logic for reference)
        # ... (fetch/display joined challenges) ...
        # self.api_client.leave_challenge(sel_id, keep=keep_param) # Sync call
        # ... (update local cache) ...
        return False  # Return False as refresh not needed due to cache update

    # FUNC: _replicate_monthly_setup_action (Legacy Logic)
    def _replicate_monthly_setup_action(self) -> bool:
        """Replicates setup from old to new challenge (Legacy version)."""
        # (Keep existing Rich implementation logic for reference)
        # ... (prompting, fuzzy matching, sync API calls for attr/tags/position) ...
        # self.api_client.set_attribute(...)
        # self.api_client.add_tag_to_task(...)
        # self.api_client.move_task_to_position(...)
        # self.api_client.unlink_all_challenge_tasks(...)
        # return should_refresh # Return based on whether API calls were made
        return False  # Placeholder
