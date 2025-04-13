# pixabit/cli/app.py
import datetime  # For stats display
import difflib  # For fuzzy matching
import json  # Keep for temp display if needed
import os
import sys
import time  # Keep for potential pauses if needed
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

import timeago  # For stats display

from .utils.dates import (convert_and_check_timestamp, convert_timestamp,
                          convert_to_local_time, is_date_passed)
from .utils.display import (BarColumn, Columns, Confirm, IntPrompt, Live,
                            Markdown, Panel, Progress, Prompt, SpinnerColumn,
                            Table, TaskProgressColumn, TextColumn,
                            TimeElapsedColumn, box, console, print, track)

# --- Third-party Libs ---
try:
    from art import text2art

    ART_AVAILABLE = True
except ImportError:
    ART_AVAILABLE = False

# --- Local Application Imports ---
# Adjust paths based on your final structure (assuming app.py is in pixabit/cli/)
try:
    from . import config
    from .api import HabiticaAPI
    from .config_tags import interactive_tag_setup
    from .data_processor import TaskProcessor, get_user_stats
    from .export_challenges import ChallengeBackupper
    from .export_to_json import (save_all_userdata_into_json,
                                 save_processed_tasks_into_json,
                                 save_tags_into_json,
                                 save_tasks_without_proccessing)
    from .tag_manager import TagManager

    # Import save_file only if export functions DON'T handle saving
    # from ..utils.save_file import save_file
except ImportError as e:
    print(f"[Fatal Error] Could not import application modules in app.py.")
    print(f"Check import paths relative to {__file__}.")
    print(f"Error details: {e}")
    sys.exit(1)
except FileNotFoundError as e:
    print(f"[Fatal Error] A required file was not found during import in app.py.")
    print(f"Error details: {e}")
    sys.exit(1)


class CliApp:
    """
    Main application class for the Pixabit CLI.
    Handles menu display, user interaction, data fetching/refreshing,
    and dispatching actions to appropriate handlers.
    """

    # --------------------------------------------------------------------------
    # 1. INIT METHOD
    # --------------------------------------------------------------------------
    # >> INIT
    def __init__(self):
        """Initializes the application, API clients, and loads initial data."""
        self.console = console
        self.console.log("[bold blue]Initializing Pixabit App...[/bold blue]")

        try:
            self.api_client = HabiticaAPI()
            self.console.log("API Client Initialized.")
            self.processor = TaskProcessor(self.api_client)
            self.console.log("Task Processor Initialized.")
            self.tag_manager = TagManager(self.api_client)
            self.console.log("Tag Manager Initialized.")
            self.backupper = ChallengeBackupper(self.api_client)
            self.console.log("Challenge Backupper Initialized.")
        except ValueError as e:  # Config error likely from API init
            self.console.print(f"[error]Configuration Error:[/error] {e}")
            self.console.print("Please ensure your .env file is set up correctly.")
            self.console.print(
                "You might need to run 'pixabit configure tags' if needed."
            )
            sys.exit(1)
        except Exception as e:
            self.console.print(f"[error]Initialization Error:[/error] {e}")
            self.console.print_exception(show_locals=True)
            sys.exit(1)

        # Initialize application state
        self.processed_tasks: Dict[str, Dict] = {}
        self.cats_data: Dict[str, Any] = {}
        self.user_stats: Dict[str, Any] = {}
        self.all_tags: List[Dict] = []
        self.unused_tags: List[Dict] = []
        self.all_challenges_cache: Optional[List[Dict]] = None  # Add this attribute

        self.console.log("Performing initial data refresh...")
        self.refresh_data()  # Load data on startup
        self.console.log("[bold blue]Initialization complete.[/bold blue]\n")

    # --------------------------------------------------------------------------
    # 2. PRIMARY PUBLIC METHOD (Entry Point)
    # --------------------------------------------------------------------------

    # >> RUN MAIN APP
    def run(self):
        """Starts the main application menu loop."""
        self.console.print(
            "--- DEBUG: Entered run() method ---"
        )  # Keep for debug if needed
        while True:
            categories = {
                "Manage Tasks": ["List Broken Tasks", "Unlink Broken Tasks"],
                "Manage Tags": [
                    "Display All Tags",
                    "Display Unused Tags",
                    "Delete Unused Tags",
                    "Sync Challenge/Personal Tags",
                    "Sync Poison Tags",
                    "Sync Attribute Tags",
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
            main_menu_options = list(categories.keys())
            choice = self._display_menu(
                "Main Menu", main_menu_options, embed_stats=True
            )
            print(f"--- DEBUG run(): Main menu choice = {choice} ---")  # <<< ADD

            if choice == 0:
                print("--- DEBUG run(): Choice 0, breaking loop. ---")
                break
            if choice == -1:
                print("--- DEBUG run(): Choice -1, continuing loop. ---")
                continue
            # Ensure choice is valid before indexing
            if not 1 <= choice <= len(main_menu_options):
                print(
                    f"--- DEBUG run(): Invalid choice {choice} not in range, continuing loop. ---"
                )
                continue

            category_name = main_menu_options[choice - 1]
            print(
                f"--- DEBUG run(): Category selected = {category_name} ---"
            )  # <<< ADD

            if category_name == "Application":
                app_options = categories["Application"]
                app_choice = self._display_menu("Application Menu", app_options)
                if app_choice == 0:
                    continue
                if app_choice == -1:
                    continue

                action_name = app_options[app_choice - 1]
                if action_name == "Exit":
                    break
                else:
                    self._execute_action(action_name)
            else:
                self._submenu_loop(category_name, categories[category_name])

        self.console.print("\n[bold magenta]Exiting Pixabit. Goodbye![/bold magenta]")

    # --------------------------------------------------------------------------
    # 3. MAJOR WORKFLOW METHODS
    # --------------------------------------------------------------------------
    # >> REFRESH DATA
    def refresh_data(self):
        """
        Fetches fresh data from Habitica and processes it, showing unified progress
        with a single updating progress bar using Live + Progress.
        """
        self.console.print(
            "\n[bold green]Refreshing data...[/bold green]"
        )  # Print message before starting Live

        progress = Progress(
            TextColumn("•", style="dim"),
            TextColumn("[bold blue]{task.description}", justify="left"),
            BarColumn(bar_width=None),  # Flexible width bar
            TaskProgressColumn(),  # Shows X/Total
            TimeElapsedColumn(),
            SpinnerColumn("dots"),  # Shows activity
            console=self.console,
            transient=False,  # Keep final state visible briefly
            # refresh_per_second=10 # Default is usually fine
        )

        total_steps = 5
        # Add ONE task for the overall refresh process
        refresh_task_id = progress.add_task("[file]Initializing...", total=total_steps)
        refresh_ok = True  # Flag to track overall success

        # Use Live context manager around the multi-step process
        with Live(progress, console=self.console, vertical_overflow="ellipsis") as live:
            try:
                # --- Step 1: Fetch Tags ---
                progress.update(
                    refresh_task_id, description="[file]Step 1/4: Fetching Tags..."
                )
                self.console.log(
                    "Starting: Fetch Tags"
                )  # Log appears above live display
                try:
                    fetched_tags = self.api_client.get_tags()
                    self.all_tags = (
                        fetched_tags if isinstance(fetched_tags, list) else []
                    )
                    self.console.log(f"Fetched {len(self.all_tags)} tags.")
                    progress.update(refresh_task_id, advance=1)  # Complete step 1
                except Exception as e:
                    progress.update(
                        refresh_task_id, description="[red]Failed: Tags!", advance=1
                    )  # Advance even on fail
                    self.console.log(f"[red]Error fetching tags: {e}[/red]")
                    self.all_tags = []
                    refresh_ok = False

                # --- Step 2: Process Tasks ---
                if refresh_ok:  # Optional: only proceed if previous steps worked
                    progress.update(
                        refresh_task_id,
                        description="[file]Step 2/4: Processing Tasks...",
                    )
                    self.console.log("Starting: Process Tasks")
                    try:
                        processed_results = self.processor.process_and_categorize_all()
                        self.processed_tasks = processed_results.get("data", {})
                        self.cats_data = processed_results.get("cats", {})
                        self.console.log(
                            f"Processed {len(self.processed_tasks)} tasks."
                        )
                        progress.update(refresh_task_id, advance=1)  # Complete step 2
                    except Exception as e:
                        progress.update(
                            refresh_task_id,
                            description="[red]Failed: Tasks!",
                            advance=1,
                        )
                        self.console.log(f"[red]Error processing tasks: {e}[/red]")
                        self.processed_tasks = {}
                        self.cats_data = {}
                        refresh_ok = False

                # --- Step 3: Fetch User Stats ---
                if refresh_ok:
                    progress.update(
                        refresh_task_id, description="[file]Step 3/4: Fetching Stats..."
                    )
                    self.console.log("Starting: Fetch Stats")
                    if self.cats_data:  # Need valid cats_data
                        try:
                            self.user_stats = get_user_stats(
                                self.api_client, self.cats_data, self.processed_tasks
                            )
                            self.console.log("User stats fetched.")
                            progress.update(
                                refresh_task_id, advance=1
                            )  # Complete step 3
                        except Exception as e:
                            progress.update(
                                refresh_task_id,
                                description="[red]Failed: Stats!",
                                advance=1,
                            )
                            self.console.log(f"[red]Error fetching stats: {e}[/red]")
                            self.user_stats = {}
                            refresh_ok = False
                    else:
                        progress.update(
                            refresh_task_id,
                            advance=1,
                            description="[yellow]Skipped: Stats",
                        )
                        self.console.log(
                            "[yellow]Skipped stats fetch (no task data)[/yellow]"
                        )
                        self.user_stats = {}

                # --- Step 4: Calculate Unused Tags ---
                if refresh_ok:
                    progress.update(
                        refresh_task_id,
                        description="[file]Step 4/4: Calculating Unused...",
                    )
                    self.console.log("Starting: Calculate Unused Tags")
                    # Check self.all_tags is valid before use
                    if isinstance(
                        self.all_tags, list
                    ):  # Check it's a list (even if empty)
                        used_tag_ids: Set[str] = set(self.cats_data.get("tags", []))
                        try:
                            if hasattr(self.tag_manager, "find_unused_tags"):
                                self.unused_tags = self.tag_manager.find_unused_tags(
                                    self.all_tags, used_tag_ids
                                )
                                self.console.log(
                                    f"Found {len(self.unused_tags)} unused tags."
                                )
                                progress.update(
                                    refresh_task_id, advance=1
                                )  # Complete step 4
                            else:
                                progress.update(
                                    refresh_task_id,
                                    advance=1,
                                    description="[yellow]Skipped: Unused (Code Error)",
                                )
                                self.console.log(
                                    "[yellow]Skipped unused (Method missing)[/yellow]"
                                )
                                self.unused_tags = []
                        except Exception as e:  # Error during calculation
                            progress.update(
                                refresh_task_id,
                                advance=1,
                                description="[red]Failed: Unused!",
                            )
                            self.console.log(
                                f"[red]Error calculating unused: {e}[/red]"
                            )
                            self.unused_tags = []
                            refresh_ok = False
                    else:  # No valid tags fetched earlier
                        progress.update(
                            refresh_task_id,
                            advance=1,
                            description="[yellow]Skipped: Unused (No Tags)",
                        )
                        self.console.log("[yellow]Skipped unused (no tags)[/yellow]")
                        self.unused_tags = []

                # Step 5: Fetch All Challenges
                progress.update(
                    refresh_task_id,
                    description="[cyan]Step X/5: Fetching Challenges...",
                )
                self.console.log("Starting: Fetch Challenges")
                try:
                    # Fetch ALL accessible challenges once
                    # Use member_only=False if replicate feature needs owned ones
                    fetched_challenges = self.api_client.get_challenges(
                        member_only=False
                    )
                    self.all_challenges_cache = (
                        fetched_challenges
                        if isinstance(fetched_challenges, list)
                        else []
                    )
                    self.console.log(
                        f"Fetched and cached {len(self.all_challenges_cache)} challenges."
                    )
                    progress.update(refresh_task_id, advance=1)
                except Exception as e:
                    progress.update(
                        refresh_task_id,
                        description="[red]Failed: Challenges!",
                        advance=1,
                    )
                    self.console.log(f"[red]Error fetching challenges: {e}[/red]")
                    self.all_challenges_cache = []  # Ensure it's an empty list on error
                    # refresh_ok = False # Decide if this is critical enough to stop

            except Exception as e:  # Catch unexpected errors during the Live block
                self.console.print_exception(show_locals=True)
                progress.update(refresh_task_id, description=f"[error]FATAL ERROR!")
                progress.stop()
                refresh_ok = False
                # Ensure defaults outside the 'with' block might be safer

        # Live context finished - Progress bar disappears if Progress(transient=True)
        # Update one last time to ensure final state is shown if transient=False
        final_description = (
            "[bold green]Refresh Complete!" if refresh_ok else "[error]Refresh Failed!"
        )
        progress.update(
            refresh_task_id,
            description=final_description,
            completed=total_steps,
            visible=True,
        )  # Make sure it's visible
        time.sleep(0.1)  # Tiny pause to allow final update to render if transient=False

        self.console.print(
            f"[bold {'green' if refresh_ok else 'red'}]Data refresh process completed{' successfully' if refresh_ok else ' with errors'}![/bold {'green' if refresh_ok else 'red'}]"
        )
        # Ensure attributes are default types after potential errors
        self.processed_tasks = getattr(self, "processed_tasks", {}) or {}
        self.cats_data = getattr(self, "cats_data", {}) or {}
        self.user_stats = getattr(self, "user_stats", {}) or {}
        self.all_tags = getattr(self, "all_tags", []) or []
        self.unused_tags = getattr(self, "unused_tags", []) or []

    # >> REFRESH DATA WORKING
    def refresh_data_working(self):
        """
        Fetches fresh data from Habitica and processes it sequentially,
        printing status updates for each step. Uses stable version.
        """
        self.console.print("\n[bold green]Refreshing data...[/bold green]")
        try:
            self.console.print("  - Fetching tags...")
            fetched_tags = self.api_client.get_tags()
            self.all_tags = fetched_tags if isinstance(fetched_tags, list) else []
            self.console.print(f"  - Fetched {len(self.all_tags)} tags.")

            self.console.print("  - Processing tasks...")
            processed_results = self.processor.process_and_categorize_all()
            self.processed_tasks = processed_results.get("data", {})
            self.cats_data = processed_results.get("cats", {})
            self.console.print(f"  - Processed {len(self.processed_tasks)} tasks.")

            self.console.print("  - Fetching user stats...")
            if self.cats_data:
                self.user_stats = get_user_stats(self.api_client, self.cats_data)
                self.console.print("  - User stats fetched.")
            else:
                self.user_stats = {}
                self.console.print("  - Skipped user stats (no category data).")

            self.console.print("  - Calculating unused tags...")
            if isinstance(self.all_tags, list):
                used_tag_ids: Set[str] = set(self.cats_data.get("tags", []))
                if hasattr(self.tag_manager, "find_unused_tags"):
                    self.unused_tags = self.tag_manager.find_unused_tags(
                        self.all_tags, used_tag_ids
                    )
                    self.console.print(
                        f"  - Found {len(self.unused_tags)} unused tags."
                    )
                else:
                    self.console.print(
                        "[yellow]  - TagManager missing find_unused_tags method.[/yellow]"
                    )
                    self.unused_tags = []
            else:
                self.console.print(
                    "[yellow]  - Cannot calculate unused tags (tag list invalid).[/yellow]"
                )
                self.unused_tags = []

            self.console.print("[bold green]Data refreshed successfully![/bold green]")

        except Exception as e:
            self.console.print(f"\n[error]Error during data refresh:[/error] {e}")
            self.console.print_exception(show_locals=False)
            # Ensure attributes remain valid default types
            self.processed_tasks = getattr(self, "processed_tasks", {}) or {}
            self.cats_data = getattr(self, "cats_data", {}) or {}
            self.user_stats = getattr(self, "user_stats", {}) or {}
            self.all_tags = getattr(self, "all_tags", []) or []
            self.unused_tags = getattr(self, "unused_tags", []) or []

    # >> SUBMENU LOOP
    def _submenu_loop(self, title: str, options: List[str]):
        """Handles the display and logic for a submenu."""
        while True:
            choice = self._display_menu(f"{title} Menu", options, embed_stats=False)
            if choice == 0:
                break  # Back to main menu
            if choice == -1:
                continue  # Invalid input

            action_name = options[choice - 1]
            self._execute_action(action_name)

    # >> ACTION HANDLERS
    def _execute_action(self, action_name: str):
        """Executes the selected action by calling the appropriate method."""
        self.console.print(f"\n-> Executing: [file]{action_name}[/file]")
        refresh_needed = False
        try:
            # --- Action mapping ---
            if action_name == "List Broken Tasks":
                self._display_broken_tasks()
            elif action_name == "Unlink Broken Tasks":
                refresh_needed = self._unlink_broken_tasks_action()
            # --- Tags ---
            elif action_name == "Display All Tags":
                self._display_tags()
            elif action_name == "Display Unused Tags":
                self._display_unused_tags()
            elif action_name == "Delete Unused Tags":
                used_ids = set(self.cats_data.get("tags", []))
                self.tag_manager.delete_unused_tags_interactive(self.all_tags, used_ids)
                refresh_needed = True
            elif action_name == "Sync Challenge/Personal Tags":
                self.tag_manager.sync_challenge_personal_tags(self.processed_tasks)
                refresh_needed = True
            elif action_name == "Sync Poison Tags":
                self.tag_manager.ensure_poison_status_tags(self.processed_tasks)
                refresh_needed = True
            elif action_name == "Sync Attribute Tags":
                self.tag_manager.sync_attributes_to_tags(self.processed_tasks)
                refresh_needed = True
            elif action_name == "Add/Replace Tag Interactively":
                refresh_needed = self._interactive_tag_replace_action()
            # --- Challenges ---
            elif action_name == "Backup Challenges":
                # Pass console instance to Confirm
                if Confirm.ask("Proceed with challenge backup?", console=self.console):
                    backup_folder = os.path.join(os.getcwd(), "_challenge_backups")
                    self.backupper.create_backups(output_folder=backup_folder)
            elif action_name == "Leave Challenge":
                refresh_needed = self._leave_challenge_action()
            # --- View Data ---
            elif action_name == "Display Stats":
                self._display_stats()  # Correct call
            # --- Export ---
            elif action_name == "Save Processed Tasks (JSON)":
                if Confirm.ask("Save processed tasks?", console=self.console):
                    save_processed_tasks_into_json(
                        self.processed_tasks, "tasks_processed.json"
                    )
            elif action_name == "Save Raw Tasks (JSON)":
                if Confirm.ask("Save raw tasks?", console=self.console):
                    save_tasks_without_proccessing(self.api_client, "tasks_raw.json")
            elif action_name == "Save All Tags (JSON)":
                if Confirm.ask("Save all tags?", console=self.console):
                    save_tags_into_json(self.api_client, "tags_all.json")
            elif action_name == "Save Full User Data (JSON)":
                if Confirm.ask("Save full user data?", console=self.console):
                    save_all_userdata_into_json(self.api_client, "user_data_full.json")
            # --- User Actions ---
            elif action_name == "Toggle Sleep Status":
                current_status = self.user_stats.get("sleeping", False)
                action_desc = "wake up" if current_status else "go to sleep"
                if Confirm.ask(f"Do you want to {action_desc}?", console=self.console):
                    self.api_client.toggle_user_sleep()
                    self.console.print("Toggled sleep status.")
                    refresh_needed = True
            # --- Application ---
            elif action_name == "Refresh Data":
                refresh_needed = True
            elif action_name == "Configure Special Tags":
                interactive_tag_setup(self.api_client)
                refresh_needed = True  # Config changed
            # --- Fallback ---
            else:
                self.console.print(
                    f"[yellow]Action '{action_name}' not implemented yet.[/yellow]"
                )

            if refresh_needed:
                self.refresh_data()

        except Exception as e:
            self.console.print(
                f"[error]Error executing action '{action_name}': {e}[/error]"
            )
            self.console.print_exception(show_locals=False)

        # Use console instance for prompt
        Prompt.ask("\n[dim]Press Enter to continue...[/dim]", console=self.console)

    # --------------------------------------------------------------------------
    # 4. UI HELPER METHODS
    # --------------------------------------------------------------------------
    # >> DISPLAY MENU
    def _display_menu(
        self, title: str, options: List[str], embed_stats: bool = True
    ) -> int:
        """Displays menu, returns user choice (0 for back/exit, -1 for invalid)."""

        try:  # Added try/except for robustness
            menu_renderable = [f"[b]{i+1}.[/] {opt}" for i, opt in enumerate(options)]
            back_exit_label = "Exit" if title == "Main Menu" else "Back"
            menu_renderable.insert(0, f"[b]0.[/] {back_exit_label}")

            menu_panel = Panel(
                Columns(menu_renderable, equal=True, expand=True, padding=(0, 1)),
                title=f"[#ebcb8b][b]{title}[/b]",
                border_style="#ebcb8b",
                box=box.ROUNDED,
                padding=(1, 1),
            )

            display_object: Any = menu_panel  # Default to just the menu

            # if show_art and ART_AVAILABLE:
            #     art_content = Text("Pixabit", style="#cba6f7")
            #     try:
            #         art_content = Text(
            #             text2art("Pixabit", font="rnd-small"), style="#cba6f7"
            #         )
            #     except Exception:
            #         pass  # Ignore art error, use default text
            #     layout = Layout()
            #     layout.split_row(
            #         Layout(
            #             Panel(art_content, border_style="dim"), name="left", ratio=2
            #         ),
            #         Layout(menu_panel, name="right", ratio=3),
            #     )
            #     display_object = Panel(layout, border_style="#ebcb8b", box=box.HEAVY)

            # If embedding stats, create a layout

            if embed_stats:
                stats_panel_object = (
                    self._display_stats()
                )  # Calls the modified method returning Panel or None
                left_panel_content = (
                    stats_panel_object
                    if stats_panel_object
                    else Panel("[dim]Stats not available[/dim]", border_style="dim")
                )

                layout = Table.grid(expand=True)
                # Give slightly more space to art than menu perhaps
                layout.add_column(ratio=2)
                layout.add_column(ratio=1)
                layout.add_row(left_panel_content, menu_panel)
                display_object = Panel(layout, border_style="#ebcb8b", box=box.ROUNDED)
            # If not show_art, display_object remains just menu_panel

            self.console.print(display_object)  # Print the constructed object
            max_option = len(options)
            # Use console instance for prompts
            choice = IntPrompt.ask("Choose an option", console=self.console)
            if not 0 <= choice <= max_option:
                self.console.print(
                    f"[error]Invalid selection. Please choose 0-{max_option}.[/error]"
                )
                return -1
            return choice
        except ValueError:
            self.console.print("[red]Invalid input. Please enter a number.[/red]")
            return -1

        except Exception as e_menu:
            self.console.print(f"[error]>>> Error displaying menu '{title}':[/error]")
            self.console.print_exception(show_locals=True)
            return -1  # Return invalid choice on error

    # >> DISPLAY STATS
    def _display_stats(self):
        """Displays formatted user stats using Rich."""
        stats_data = self.user_stats

        user_dmg = stats_data.get("potential_daily_damage_user", 0.0)
        party_dmg = stats_data.get("potential_daily_damage_party", 0.0)
        if not stats_data:
            self.console.print(
                "[yellow]No user stats data available. Refresh data first.[/yellow]"
            )
            return

        try:
            # --- Build Rich Display Components ---
            username = stats_data.get("username", "N/A")
            last_login_str = stats_data.get("last_login_local")
            day_start = stats_data.get("day_start", "?")
            is_sleeping = stats_data.get("sleeping", False)
            broken_count = stats_data.get("broken_challenge_tasks", 0)
            is_questing = stats_data.get("quest_active", False)
            quest_key = stats_data.get("quest_key")
            dmg_color = "red" if user_dmg >= 10 else "yellow" if user_dmg > 0 else "dim"
            party_dmg_str = f", Party: {party_dmg:.1f}" if party_dmg > 0 else ""
            core_stats_values = stats_data.get("stats", {})
            gp = int(stats_data.get("gp", 0))
            hp = int(stats_data.get("hp", 0))
            exp = int(stats_data.get("exp", 0))
            mp = int(stats_data.get("mp", 0))
            gems = stats_data.get("gems", 0)  # Get the gems value

            level = stats_data.get("level", 0)
            user_class = stats_data.get("class", "N/A")
            task_counts = stats_data.get("task_counts", {})

            now = datetime.datetime.now(datetime.timezone.utc)
            last_login_display = "N/A"
            if last_login_str and last_login_str != "N/A":
                try:
                    last_login_display = timeago.format(
                        datetime.datetime.fromisoformat(last_login_str), now
                    )
                except Exception:
                    last_login_display = "(Time Error)"

            # User Info Table
            user_info_table = Table.grid(padding=(0, 2), expand=True)
            user_info_table.add_column(no_wrap=True, justify="right", style="dim")
            user_info_table.add_column(no_wrap=False, justify="left")

            user_info_table.add_row(":mage:", f"Hello, [b i]{username}")
            user_info_table.add_row(
                ":hourglass:", f"Last login: [i]{last_login_display}"
            )
            user_info_table.add_row(":alarm_clock:", f"Day starts at: {day_start} am")
            if is_sleeping:
                user_info_table.add_row(":zzz:", "[i]Resting in the Inn[/i]")
            if broken_count > 0:
                user_info_table.add_row(
                    ":wilted_flower:",
                    f"[red]{broken_count} broken challenge tasks[/red]",
                )
            if is_questing:
                user_info_table.add_row(
                    ":dragon:",
                    f"[pink]On quest: [i]{quest_key or 'Unknown'}[/i][/pink]",
                )
            # --- ADD Damage Row HERE ---
            user_info_table.add_row(
                ":biohazard:",
                f"Potential Daily Damage: [{dmg_color}]User: {user_dmg:.1f}{party_dmg_str}[/]",
            )

            # ---------------------------

            # Core Stats Table
            core_stats_table = Table.grid(padding=(0, 1), expand=True)
            core_stats_table.add_row("[b #F74E52]:heartpulse: HP", f"{hp}")
            core_stats_table.add_row("[b #50B5E9]:cyclone: MP", f"{mp}")
            core_stats_table.add_row("[b #FFBE5D]:dizzy: EXP", f"{exp}")
            core_stats_table.add_row("[b #FFA624]:moneybag: GP", f"{gp}")
            core_stats_table.add_row("[b #50B5E9]:gem: Gems", f"{gems}")

            # Task Counts Display
            habits_count = task_counts.get("habits", 0)
            rewards_count = task_counts.get("rewards", 0)
            todos_data = task_counts.get("todos", {})
            dailys_data = task_counts.get("dailys", {})
            counts_display = Table.grid(padding=(0, 1), expand=True)
            counts_display.add_column(min_width=15)
            counts_display.add_column(min_width=15)
            counts_display.add_row(
                Panel(
                    f"[b]{habits_count}[/]",
                    title="Habits",
                    padding=(0, 1),
                    border_style="dim",
                ),
                Panel(
                    f"[b]{rewards_count}[/]",
                    title="Rewards",
                    padding=(0, 1),
                    border_style="dim",
                ),
            )
            todos_table = Table.grid(padding=(0, 1))
            todos_table.add_column(justify="left")
            todos_table.add_column(justify="right")
            todos_table.add_row("[b]Total", f"{sum(todos_data.values())}")
            todos_table.add_row("  Due", f"{todos_data.get('due', 0)}")
            todos_table.add_row("  Expired", f"{todos_data.get('red', 0)}")
            todos_table.add_row("  No Due", f"{todos_data.get('grey', 0)}")
            dailys_table = Table.grid(padding=(0, 1))
            dailys_table.add_column(justify="left")
            dailys_table.add_column(justify="right")
            dailys_table.add_row("[b]Total", f"{sum(dailys_data.values())}")
            dailys_table.add_row("  Due", f"{dailys_data.get('due', 0)}")
            dailys_table.add_row("  Done", f"{dailys_data.get('done', 0)}")
            dailys_table.add_row("  Not Due", f"{dailys_data.get('grey', 0)}")
            counts_display.add_row(
                Panel(
                    dailys_table, title="Dailies", padding=(0, 1), border_style="dim"
                ),
                Panel(todos_table, title="Todos", padding=(0, 1), border_style="dim"),
            )

            # Combine sections
            display_stats_panel = Panel(
                core_stats_table,
                box=box.ROUNDED,
                title=f"Lv {level} {user_class}",
                border_style="magenta",
                expand=True,
            )
            total_tasks_num = CliApp._get_total(task_counts)
            display_numbers_panel = Panel(
                counts_display,
                box=box.ROUNDED,
                title=f"Tasks ({total_tasks_num} total)",
                border_style="blue",
                expand=True,
            )

            top_layout = Table.grid(padding=(0, 1), expand=True)
            top_layout.add_column(min_width=35)
            top_layout.add_column(min_width=20)
            top_layout.add_row(user_info_table, display_stats_panel)
            final_layout_simple = Table.grid()
            final_layout_simple.add_row(top_layout)
            final_layout_simple.add_row(display_numbers_panel)

            stats_renderable = Panel(
                final_layout_simple,
                box=box.ROUNDED,
                title=":mage: [b i]User Stats[/] :mage:",
                border_style="green",
                expand=True,
                padding=(1, 2),
            )

            # Print the final panel
            return stats_renderable

        except Exception as e:
            self.console.print(f"[error]Error building stats display: {e}[/error]")
            self.console.print_exception(show_locals=False)
            return Panel(
                f"[error]Error building stats[/]:\n{e}", border_style="red"
            )  # Return simple error panel

    # >> DISPLAY ALL TAGS
    def _display_tags(self):
        """Displays all fetched tags using Rich."""
        if not self.all_tags:
            self.console.print("[yellow]No tags data available.[/yellow]")
            return
        self.console.print(f"\n[bold]All Tags ({len(self.all_tags)}):[/bold]")
        table = Table(
            show_header=True,
            header_style="bold magenta",
            title="All Tags",
            box=box.ROUNDED,
        )
        table.add_column("Num", style="dim", width=4, justify="right")
        table.add_column("Name", style="sapphire", min_width=20)
        table.add_column("ID", style="magenta", overflow="fold", min_width=36)
        valid_tags = [tag for tag in self.all_tags if tag.get("id")]
        for i, tag in enumerate(valid_tags):
            table.add_row(str(i + 1), tag.get("name", "N/A"), tag.get("id"))
        self.console.print(table)

    # >> DISPLAY UNUSED TAGS
    def _display_unused_tags(self):
        """Displays unused tags using Rich."""
        if not self.unused_tags:
            self.console.print("[green]No unused tags found.[/green]")
            return
        self.console.print(f"\n[bold]Unused Tags ({len(self.unused_tags)}):[/bold]")
        table = Table(
            show_header=True,
            header_style="bold yellow",
            title="Unused Tags",
            box=box.ROUNDED,
        )
        table.add_column("Num", style="dim", width=4, justify="right")
        table.add_column("Name", style="file", min_width=20)
        table.add_column("ID", style="magenta", overflow="fold", min_width=36)
        for i, tag in enumerate(self.unused_tags):
            table.add_row(str(i + 1), tag.get("name", "N/A"), tag.get("id", "N/A"))
        self.console.print(table)

    # >> DISPLAY BROKEN TASKS
    def _display_broken_tasks(self):
        """Displays tasks marked as belonging to a broken challenge."""
        broken_ids = self.cats_data.get("broken", [])
        if not broken_ids:
            self.console.print("[green]No broken tasks found.[/green]")
            return
        self.console.print(f"\n[yellow]Found {len(broken_ids)} broken tasks:[/yellow]")
        table = Table(
            title="Broken Challenge Tasks",
            show_header=True,
            header_style="error",
            box=box.ROUNDED,
        )
        table.add_column("ID", style="magenta", width=36)
        table.add_column("Text", style="sapphire")
        table.add_column("Challenge", style="dim", min_width=20)
        for task_id in broken_ids:
            task_detail = self.processed_tasks.get(task_id)
            task_challenge = (
                task_detail.get("challenge", "[i]N/A[i]") if task_detail else None
            )
            task_text = (
                task_detail.get("text", "[i]N/A[/i]")
                if task_detail
                else "[dim](Details not found)[/dim]"
            )
            table.add_row(task_id, task_text, task_challenge)
        self.console.print(table)

    # --------------------------------------------------------------------------
    # 5. ACTION HELPER METHODS
    # --------------------------------------------------------------------------
    # >> UNLINK BROKEN TASKS
    def _unlink_broken_tasks_action(self) -> bool:
        """Handles confirming and unlinking broken tasks."""
        broken_ids = self.cats_data.get("broken", [])
        if not broken_ids:
            self.console.print("[green]No broken tasks to unlink.[/green]")
            return False
        self._display_broken_tasks()  # Show before asking
        if Confirm.ask(
            f"\nUnlink these {len(broken_ids)} tasks? (Will keep as personal)",
            default=False,
            console=self.console,
        ):
            error_count = 0
            # Use track for simple progress here
            for task_id in track(
                broken_ids,
                description="Unlinking broken tasks...",
                console=self.console,
            ):
                try:
                    self.api_client.unlink_task_from_challenge(task_id, keep="keep")
                except Exception as e:
                    self.console.print(f"\n[red]Error unlinking {task_id}: {e}[/red]")
                    error_count += 1
            if error_count == 0:
                self.console.print("[green]Broken tasks unlinked.[/green]")
            else:
                self.console.print(
                    f"[yellow]Completed unlinking with {error_count} errors.[/yellow]"
                )
            return True  # Refresh needed
        else:
            self.console.print("No tasks unlinked.")
            return False

    # >> INTERACTIVE TAG REPLACE
    def _interactive_tag_replace_action(self) -> bool:
        """Handles the interactive prompts for replacing tags."""
        self._display_tags()  # Show tags first
        valid_tags = [tag for tag in self.all_tags if tag.get("id")]
        if not valid_tags:
            self.console.print("[yellow]No valid tags found.[/yellow]")
            return False
        num_tags = len(valid_tags)

        try:
            self.console.print("\nSelect tags by number from the list above.")
            del_num = IntPrompt.ask(
                f"Enter number of tag to find/replace (1-{num_tags})",
                console=self.console,
            )
            add_num = IntPrompt.ask(
                f"Enter number of tag to add (1-{num_tags})", console=self.console
            )

            # Basic validation
            if not (1 <= del_num <= num_tags and 1 <= add_num <= num_tags):
                raise ValueError("Selection out of range")
            if del_num == add_num:
                self.console.print(
                    "[yellow]Source and target tags are the same.[/yellow]"
                )
                return False

            tag_find = valid_tags[del_num - 1]
            tag_add = valid_tags[add_num - 1]
            tag_find_id = tag_find.get("id")
            tag_add_id = tag_add.get("id")
            tag_find_name = tag_find.get("name", "N/A")
            tag_add_name = tag_add.get("name", "N/A")

            if not tag_find_id or not tag_add_id:
                raise ValueError("Selected tag missing ID")

            replace = Confirm.ask(
                f"Also remove original tag '{tag_find_name}' after adding?",
                default=False,
                console=self.console,
            )
            mode = "replace" if replace else "add"

            if Confirm.ask(
                f"{mode.capitalize()} tag '{tag_add_name}' on all tasks that have '{tag_find_name}'?",
                default=True,
                console=self.console,
            ):
                # Assuming TagManager handles its own progress/confirmation for the batch API calls
                self.tag_manager.add_or_replace_tag_based_on_other(
                    self.processed_tasks, tag_find_id, tag_add_id, replace
                )
                return True  # Refresh needed
            else:
                self.console.print("Operation cancelled.")
                return False
        except (ValueError, IndexError) as e:
            self.console.print(f"[red]Invalid input or selection: {e}.[/red]")
            return False

    # >> LEAVE CHALLENGE ACTION
    def _leave_challenge_action(self) -> bool:
        """Handles listing challenges the user has JOINED (not owned)
        and leaving a selected one, optionally unlinking tasks first."""
        if self.all_challenges_cache is None:
            self.console.print(
                "[yellow]Challenge list not loaded. Please refresh data first (App -> Refresh Data).[/yellow]"
            )
            return False

        # Filter self.all_challenges_cache instead of fetching anew
        user_id = self.api_client.user_id
        joined_challenges = [
            ch
            for ch in self.all_challenges_cache
            if ch.get("leader", {}).get("_id") != user_id
        ]

        #   self.console.print("\nFetching challenges you are a member of...")
        try:
            # Fetch challenges user has access to (includes owned and joined)
            all_accessible_challenges = self.api_client.get_challenges(member_only=True)
        except Exception as e:
            self.console.print(f"[error]Error fetching challenges: {e}[/error]")
            return False

        # --- ADD FILTERING LOGIC HERE ---
        joined_challenges = []
        user_id = (
            self.api_client.user_id
        )  # Get the current user's ID from the api_client instance
        for challenge in all_accessible_challenges:
            # Keep the challenge only if the leader's ID does NOT match the user's ID
            leader_id = challenge.get("leader", {}).get("_id")
            if leader_id and leader_id != user_id:
                joined_challenges.append(challenge)
        # ---------------------------------

        # Now use the filtered list 'joined_challenges' instead of 'challenges'
        if not joined_challenges:
            self.console.print(
                "[yellow]You have not joined any challenges created by other users.[/yellow]"
            )
            return False

        # Display challenges in a table (using the filtered list)
        table = Table(
            title="Challenges You Have Joined (Not Owned)",
            show_header=True,
            header_style="bold blue",
            box=box.ROUNDED,
            expand=True,
        )
        # ... (Keep the same table columns as before: Num, Name, ID, Guild?, Memb, Created, Updated, Prize) ...
        table.add_column("Num", style="dim", width=4, justify="right")
        table.add_column("Name", style="file", min_width=25, ratio=3, no_wrap=False)
        #        table.add_column("ID", style="magenta", width=36)
        table.add_column("Guild?", style="yellow", width=6)
        table.add_column("Memb", style="blue", width=5, justify="right")
        table.add_column("Created", style="green", width=11)
        #        table.add_column("Updated", style="green", min_width=12, ratio=1)
        table.add_column("Prize", style="yellow", width=5, justify="right")

        valid_challenges_for_selection = []  # Reset this list
        now = datetime.datetime.now(datetime.timezone.utc)

        # Loop through the FILTERED list 'joined_challenges'
        for i, challenge in enumerate(joined_challenges):
            challenge_id = challenge.get("id")
            if challenge_id:
                valid_challenges_for_selection.append(challenge)
                # --- Extract details (same as before) ---
                name = challenge.get("name", "N/A")
                prize = challenge.get("prize", 0)
                member_count = challenge.get("memberCount", "?")
                group_type = challenge.get("group", {}).get("type")
                group_name = challenge.get("group", {}).get("name")

                is_guild = (
                    group_name
                    if group_type == "guild" and group_name != "Tavern"
                    else "N"
                )

                created_at_str = "N/A"
                created_at_raw = challenge.get("createdAt")
                if created_at_raw:
                    try:
                        created_dt_local = convert_to_local_time(created_at_raw)
                        created_at_str = created_dt_local.strftime("%Y-%m-%d")
                    except Exception:
                        created_at_str = "Date Err"

                updated_at_str = "N/A"
                updated_at_raw = challenge.get("updatedAt")
                if updated_at_raw:
                    try:
                        updated_dt_utc = datetime.datetime.fromisoformat(
                            updated_at_raw.replace("Z", "+00:00")
                        )
                        updated_at_str = timeago.format(updated_dt_utc, now)
                    except Exception:
                        updated_at_str = "Date Err"

                table.add_row(
                    str(
                        len(valid_challenges_for_selection)
                    ),  # Use length of this list for numbering
                    name,
                    #                    challenge_id,
                    is_guild,
                    str(member_count),
                    created_at_str,
                    #                    updated_at_str,
                    str(prize),
                )
        # --- Check valid_challenges_for_selection again after filtering ---
        if not valid_challenges_for_selection:
            # This case might occur if the user only owns challenges or API returned unexpected data
            self.console.print(
                "[yellow]No challenges found that you have joined (excluding owned).[/yellow]"
            )
            return False

        self.console.print(table)

        # --- Prompt user to select a challenge (using the filtered list count) ---
        try:
            choice = IntPrompt.ask(
                f"Enter the number of the challenge to manage (1-{len(valid_challenges_for_selection)}), or 0 to cancel",
                choices=["0"]
                + [str(i) for i in range(1, len(valid_challenges_for_selection) + 1)],
                show_choices=False,
                console=self.console,
            )
            # ... (Rest of the logic: get selected challenge, fetch tasks, prompt action, execute remains the same) ...
            # Make sure to use 'valid_challenges_for_selection' when getting the selected challenge by index.

            if choice == 0:
                self.console.print("Operation cancelled.")
                return False

            selected_index = choice - 1
            selected_challenge = valid_challenges_for_selection[
                selected_index
            ]  # Use the filtered list here
            selected_challenge_id = selected_challenge.get("id")
            selected_challenge_name = selected_challenge.get("name", "N/A")

            # --- Fetch and Display Tasks for Selected Challenge ---
            self.console.print(
                f"\nFetching tasks for challenge: [file]'{selected_challenge_name}'[/]..."
            )
            try:
                tasks = self.api_client.get_challenge_tasks(selected_challenge_id)
                if tasks:
                    counts = {"habits": 0, "dailys": 0, "todos": 0, "rewards": 0}
                    task_list_renderable = []
                    for task in tasks:
                        task_type = task.get("type", "unknown") + "s"  # Pluralize
                        if task_type in counts:
                            counts[task_type] += 1
                        task_list_renderable.append(f"- {task.get('text', 'N/A')}")

                    self.console.print(f"Found {len(tasks)} tasks:")
                    self.console.print(
                        f"  Habits: {counts['habits']}, Dailies: {counts['dailys']}, Todos: {counts['todos']}, Rewards: {counts['rewards']}"
                    )
                    # Optionally print the list (might be long)
                    # if Confirm.ask("Display task list?", default=False, console=self.console):
                    #     self.console.print("\n".join(task_list_renderable))
                else:
                    self.console.print(
                        "[yellow]No tasks found for this challenge.[/yellow]"
                    )
                    tasks = (
                        []
                    )  # Ensure tasks is an empty list if fetch fails or returns none

            except Exception as e:
                self.console.print(
                    f"[error]Error fetching tasks for challenge {selected_challenge_id}: {e}[/error]"
                )
                # Allow proceeding to leave without unlinking if task fetch fails? Or force cancel? Let's allow leaving.
                tasks = []  # Ensure tasks is empty on error

            # --- Prompt for Action ---
            self.console.print("\nChoose an action:")
            self.console.print(
                "  [1] Unlink All Tasks (Keep Personal Copies) & Leave Challenge"
            )
            self.console.print(
                "  [2] Unlink All Tasks (Remove Permanently) & Leave Challenge"
            )
            self.console.print("  [3] Leave Challenge (Keep Tasks Linked)")
            self.console.print("  [0] Cancel")

            action_choice = IntPrompt.ask(
                "Enter your choice",
                choices=["0", "1", "2", "3"],
                show_choices=False,
                console=self.console,
            )

            # --- Execute Action ---
            should_refresh = False
            if action_choice == 0:
                self.console.print("Operation cancelled.")
                return False

            # --- Perform Unlinking if chosen (Actions 1 or 2) ---
            if action_choice in [1, 2]:
                if not tasks:
                    self.console.print(
                        "[yellow]No tasks to unlink for this challenge.[/yellow]"
                    )
                    # Continue to leaving step
                else:
                    keep_option = "keep" if action_choice == 1 else "remove"
                    action_desc = (
                        "Keeping personal copies"
                        if keep_option == "keep"
                        else "Removing permanently"
                    )
                    if Confirm.ask(
                        f"Unlink all {len(tasks)} tasks ({action_desc})?",
                        default=True,
                        console=self.console,
                    ):
                        self.console.print(
                            f"Attempting to unlink all tasks ({action_desc})..."
                        )
                        try:
                            unlink_response = (
                                self.api_client.unlink_all_challenge_tasks(
                                    selected_challenge_id, keep=keep_option
                                )
                            )
                            self.console.print(
                                "[green]Tasks unlinked successfully.[/green]"
                            )
                            # Even if unlinking works, we still need to leave. Proceed.
                        except Exception as e:
                            self.console.print(
                                f"[error]Error unlinking tasks: {e}. Cannot proceed with leaving.[/error]"
                            )
                            return False  # Stop if unlinking failed when requested
                    else:
                        self.console.print(
                            "Unlinking cancelled. Aborting leave action."
                        )
                        return False  # User cancelled the unlink step

            # --- Perform Leave Challenge (Actions 1, 2 after unlink, or 3 directly) ---
            if action_choice in [1, 2, 3]:
                if Confirm.ask(
                    f"Confirm leaving challenge '{selected_challenge_name}'?",
                    default=True,
                    console=self.console,
                ):
                    self.console.print(
                        f"Attempting to leave challenge '{selected_challenge_name}'..."
                    )
                    try:
                        response = self.api_client.post(
                            f"/challenges/{selected_challenge_id}/leave"
                        )
                        self.console.print(
                            f"[bold green]Successfully left challenge '{selected_challenge_name}'.[/bold green]"
                        )
                        should_refresh = True  # Refresh needed after leaving
                    except Exception as e:
                        self.console.print(
                            f"[error]Error leaving challenge {selected_challenge_id}: {e}[/error]"
                        )
                        should_refresh = False  # No refresh on error
                else:
                    self.console.print("Leave challenge cancelled.")
                    should_refresh = False

            return should_refresh  # Return True only if leave was successful

        except (ValueError, IndexError):
            # ... (Handle errors as before) ...
            self.console.print("[error]Invalid selection.[/error]")
            return False
        except KeyboardInterrupt:
            self.console.print("\nOperation cancelled by user.")
            return False

    # >> REPLICATE MONTHLY SETUP
    def _replicate_monthly_setup_action(self) -> bool:
        """Replicates attributes, tags, and optionally position from an old challenge to a new one."""
        self.console.print("\n--- Replicate Monthly Challenge Setup ---")
        should_refresh = False
        old_challenge_id = None
        new_challenge_id = None

        try:
            # --- 1. Select Challenges ---
            self.console.print("Fetching challenges...")
            if self.all_challenges_cache is None:
                self.console.print(
                    "[yellow]Challenge list not loaded. Please refresh data first (App -> Refresh Data).[/yellow]"
                )
                challenges = self.api_client.get_challenges(
                    member_only=True
                )  # Get all accessible
            else:
                challenges = self.all_challenges_cache  # Use cached data

            if not challenges:
                self.console.print("[yellow]No challenges found.[/yellow]")
                return False

            challenge_table = Table(
                title="Select Source (Old) and Destination (New) Challenges",
                box=box.ROUNDED,
            )
            challenge_table.add_column("Num", style="dim", width=4)
            challenge_table.add_column("Name", style="cyan")
            challenge_table.add_column("ID", style="magenta")

            valid_challenges_for_selection = []
            for i, ch in enumerate(challenges):
                if ch.get("id"):
                    valid_challenges_for_selection.append(ch)
                    challenge_table.add_row(
                        str(len(valid_challenges_for_selection)),
                        ch.get("name", "N/A"),
                        ch.get("id"),
                    )

            if not valid_challenges_for_selection:
                self.console.print(
                    "[yellow]No valid challenges with IDs found.[/yellow]"
                )
                return False

            self.console.print(challenge_table)

            old_choice = IntPrompt.ask(
                f"Enter number for OLD challenge (Source) (1-{len(valid_challenges_for_selection)})",
                choices=[
                    str(i) for i in range(1, len(valid_challenges_for_selection) + 1)
                ],
                show_choices=False,
                console=self.console,
            )
            old_challenge = valid_challenges_for_selection[old_choice - 1]
            old_challenge_id = old_challenge["id"]
            old_challenge_name = old_challenge.get("name", old_challenge_id)

            new_choice = IntPrompt.ask(
                f"Enter number for NEW challenge (Destination) (1-{len(valid_challenges_for_selection)})",
                choices=[
                    str(i) for i in range(1, len(valid_challenges_for_selection) + 1)
                ],
                show_choices=False,
                console=self.console,
            )
            new_challenge = valid_challenges_for_selection[new_choice - 1]
            new_challenge_id = new_challenge["id"]
            new_challenge_name = new_challenge.get("name", new_challenge_id)

            if old_challenge_id == new_challenge_id:
                self.console.print(
                    "[red]Old and New challenges cannot be the same.[/red]"
                )
                return False

            self.console.print(
                f"Source (Old): [cyan]'{old_challenge_name}'[/] ({old_challenge_id})"
            )
            self.console.print(
                f"Destination (New): [cyan]'{new_challenge_name}'[/] ({new_challenge_id})"
            )

            # --- 2. Fetch Tasks ---
            self.console.print("Fetching tasks for both challenges...")
            old_tasks = self.api_client.get_challenge_tasks(old_challenge_id)
            new_tasks = self.api_client.get_challenge_tasks(new_challenge_id)
            self.console.print(
                f"Found {len(old_tasks)} tasks in old challenge, {len(new_tasks)} in new."
            )

            # --- 3. Filter Task Type (Optional) ---
            task_type_filter = None
            if Confirm.ask(
                "Replicate for [cyan]Dailies only[/]? (No = All task types)",
                default=True,
                console=self.console,
            ):
                task_type_filter = "daily"
                old_tasks = [t for t in old_tasks if t.get("type") == "daily"]
                new_tasks = [t for t in new_tasks if t.get("type") == "daily"]
                self.console.print(
                    f"Filtered to {len(old_tasks)} old dailies, {len(new_tasks)} new dailies."
                )

            # --- 4. Match Tasks (Fuzzy) ---
            similarity_threshold = 0.85  # Adjust as needed (0.0 to 1.0)
            matched_tasks = []  # List of tuples: (old_task_dict, new_task_dict)
            # Use a set to track new tasks already matched to prevent duplicates
            matched_new_task_ids = set()

            self.console.print(
                f"Matching tasks with similarity > {similarity_threshold*100}%..."
            )
            for old_task in old_tasks:
                best_match_new_task = None
                highest_ratio = 0.0
                old_text = old_task.get("text", "")
                if not old_text:
                    continue  # Skip old tasks without text

                for new_task in new_tasks:
                    new_id = new_task.get("id")
                    # Skip new tasks already matched
                    if not new_id or new_id in matched_new_task_ids:
                        continue

                    new_text = new_task.get("text", "")
                    if not new_text:
                        continue  # Skip new tasks without text

                    # Calculate similarity ratio
                    matcher = difflib.SequenceMatcher(None, old_text, new_text)
                    ratio = matcher.ratio()

                    # Check if this is the best match found so far for this old_task
                    if ratio > highest_ratio and ratio >= similarity_threshold:
                        highest_ratio = ratio
                        best_match_new_task = new_task

                # If a good enough match was found for this old_task, store it
                if best_match_new_task:
                    matched_tasks.append((old_task, best_match_new_task))
                    # Mark the new task as matched so it can't be matched again
                    matched_new_task_ids.add(best_match_new_task["id"])

            if not matched_tasks:
                self.console.print(
                    "[yellow]No matching tasks found based on the criteria.[/yellow]"
                )
                return False

            self.console.print(f"Found {len(matched_tasks)} potential task pairs:")
            for old, new in matched_tasks:
                self.console.print(
                    f"  - [dim]'{old.get('text', 'N/A')}'[/] -> [cyan]'{new.get('text', 'N/A')}'[/]"
                )

            if not Confirm.ask(
                "Proceed with replicating attributes and tags for these pairs?",
                default=True,
                console=self.console,
            ):
                self.console.print("Replication cancelled.")
                return False

            # --- 5. Apply Attributes & Tags ---
            self.console.print("Applying attributes and tags...")
            replication_errors = 0
            for i, (old_task, new_task) in enumerate(matched_tasks):
                old_task_id = old_task["id"]
                new_task_id = new_task["id"]
                new_task_text = new_task.get("text", new_task_id)
                self.console.print(
                    f"  ({i+1}/{len(matched_tasks)}) Processing: '{new_task_text}'"
                )

                # Attribute
                old_attribute = old_task.get("attribute", "str")  # Default to 'str'
                try:
                    self.api_client.set_attribute(new_task_id, old_attribute)
                    self.console.print(f"    - Set attribute to: {old_attribute}")
                except Exception as e:
                    self.console.print(
                        f"    [red]- Error setting attribute for {new_task_id}: {e}[/red]"
                    )
                    replication_errors += 1

                # Tags
                old_tags = old_task.get("tags", [])
                # TODO: Add logic here to filter out unwanted tags if necessary
                # e.g., filter out tags matching old_challenge_id or specific meta-tags
                tags_to_add = old_tags
                if tags_to_add:
                    self.console.print(f"    - Adding {len(tags_to_add)} tags...")
                    for tag_id in tags_to_add:
                        try:
                            self.api_client.add_tag(new_task_id, tag_id)
                            # time.sleep(0.2) # Optional small delay between tag adds
                        except Exception as e:
                            # Handle cases where tag already exists on task (API might error)
                            if "already has the tag" in str(e).lower():
                                self.console.print(
                                    f"      - Tag {tag_id} likely already exists."
                                )
                            else:
                                self.console.print(
                                    f"      [red]- Error adding tag {tag_id} for {new_task_id}: {e}[/red]"
                                )
                                replication_errors += 1

            self.console.print("Attribute and tag replication finished.")
            if replication_errors > 0:
                self.console.print(
                    f"[yellow]Completed with {replication_errors} errors.[/yellow]"
                )

            # --- 6. Apply Position (Optional) ---
            if Confirm.ask(
                "\nAttempt to replicate task order? (This can take a LONG time)",
                default=False,
                console=self.console,
            ):
                self.console.print("Determining task order...")
                # Get the order of the OLD tasks that were successfully matched
                old_task_order_map = {task["id"]: i for i, task in enumerate(old_tasks)}

                # Sort the NEW tasks based on the original order of their OLD counterparts
                # This gives the desired final order for the new tasks
                def sort_key(new_task_match_tuple):
                    old_task_id = new_task_match_tuple[0][
                        "id"
                    ]  # Get old task id from the tuple
                    return old_task_order_map.get(
                        old_task_id, float("inf")
                    )  # Place unmatched ones last

                # Sort the matched_tasks list itself based on the old task order
                sorted_matched_tasks = sorted(matched_tasks, key=sort_key)
                # Extract the new task IDs in the desired final order
                desired_new_task_order_ids = [
                    new_task["id"] for old_task, new_task in sorted_matched_tasks
                ]

                if not desired_new_task_order_ids:
                    self.console.print(
                        "[yellow]Could not determine desired order.[/yellow]"
                    )
                else:
                    num_to_move = len(desired_new_task_order_ids)
                    est_time_secs = num_to_move * 2.1  # Estimate time
                    self.console.print(
                        f"Will move {num_to_move} tasks. Estimated time: ~{est_time_secs:.1f} seconds."
                    )
                    if Confirm.ask(
                        "Proceed with moving tasks?", default=True, console=self.console
                    ):
                        self.console.print("Moving tasks (in reverse order)...")
                        move_errors = 0
                        # Iterate in REVERSE of the desired final order
                        for task_id_to_move in reversed(desired_new_task_order_ids):
                            try:
                                self.console.print(
                                    f"  - Moving task {task_id_to_move} to top (pos 0)..."
                                )
                                self.api_client.move_task_to_position(
                                    task_id_to_move, 0
                                )
                                time.sleep(2.1)  # IMPORTANT: Wait for rate limit
                            except Exception as e:
                                self.console.print(
                                    f"  [red]- Error moving task {task_id_to_move}: {e}[/red]"
                                )
                                move_errors += 1
                        self.console.print("Task moving finished.")
                        if move_errors > 0:
                            self.console.print(
                                f"[yellow]Completed moving with {move_errors} errors.[/yellow]"
                            )
                    else:
                        self.console.print("Task moving cancelled.")
            else:
                self.console.print("Skipping position replication.")

            # --- 7. Final Cleanup (Optional) ---
            self.console.print("\nReplication process complete.")
            if old_challenge_id:  # Ensure we have the old challenge ID
                if Confirm.ask(
                    f"\nDo you want to unlink all tasks from the OLD challenge '{old_challenge_name}' ({old_challenge_id}) now?",
                    default=False,
                    console=self.console,
                ):
                    # Ask whether to remove tasks permanently
                    remove_permanently = Confirm.ask(
                        "Remove tasks permanently? (No = Keep personal copies)",
                        default=False,
                        console=self.console,
                    )  # Default to safer option
                    keep_param = "remove-all" if remove_permanently else "keep-all"
                    action_desc = (
                        "Removing permanently"
                        if keep_param == "remove-all"
                        else "Keeping personal copies"
                    )

                    if Confirm.ask(
                        f"Confirm unlinking all tasks from OLD challenge ({action_desc})?",
                        default=True,
                        console=self.console,
                    ):
                        self.console.print(
                            f"Attempting to unlink all tasks from {old_challenge_id} ({action_desc})..."
                        )
                        try:
                            # Use the corrected API method
                            response = self.api_client.unlink_all_challenge_tasks(
                                old_challenge_id, keep=keep_param
                            )
                            self.console.print(
                                f"[bold green]Successfully unlinked tasks from old challenge '{old_challenge_name}'.[/bold green]"
                            )
                            should_refresh = (
                                True  # Refresh needed after modifying tasks
                            )
                        except Exception as e:
                            self.console.print(
                                f"[bold red]Error unlinking tasks from old challenge {old_challenge_id}: {e}[/bold red]"
                            )
                    else:
                        self.console.print("Unlinking from old challenge cancelled.")
                else:
                    self.console.print("Skipping cleanup of old challenge tasks.")

        except Exception as e:
            self.console.print(
                f"[bold red]An error occurred during the replication process: {e}[/bold red]"
            )
            self.console.print_exception(
                show_locals=False
            )  # Show traceback for debugging
            should_refresh = False  # Don't refresh if the process errored out

        return should_refresh  # Return True if major steps likely succeeded

        # Use self.all_challenges_cache to display options
        challenges_to_display = self.all_challenges_cache
        # ... build table from challenges_to_display ...
        # ... prompt user to select old/new numbers based on this list ...

    # >> HANDLE BROKEN TASKS

    # Add near other imports at the top of pixabit/menu.py if not present
    # Ensure Table, Confirm, IntPrompt, Prompt, box are imported from .utils.display

    # Replace or add this method inside the CliApp class in pixabit/menu.py

    def _handle_broken_tasks_action(self) -> bool:
        """Groups broken tasks by challenge, allows bulk or individual unlinking."""
        broken_ids = self.cats_data.get("broken", [])
        should_refresh = False

        if not broken_ids:
            self.console.print("[green]✅ No broken tasks found.[/green]")
            return False

        # --- Group broken tasks by challenge ID ---
        broken_by_challenge = defaultdict(list)
        challenge_names = {}  # Store challenge names for display
        valid_broken_tasks = (
            []
        )  # Store tasks with details for individual selection later

        for task_id in broken_ids:
            task_detail = self.processed_tasks.get(task_id)
            if task_detail:
                challenge_id = task_detail.get("challenge_id")
                if (
                    challenge_id
                ):  # Only include tasks that still have a challenge ID linkage
                    challenge_name = task_detail.get(
                        "challenge", challenge_id
                    )  # Use shortName or ID
                    task_info = {"id": task_id, "text": task_detail.get("text", "N/A")}
                    broken_by_challenge[challenge_id].append(task_info)
                    if challenge_id not in challenge_names:
                        challenge_names[challenge_id] = (
                            challenge_name  # Store first encountered name
                        )
                    valid_broken_tasks.append(
                        {
                            **task_info,
                            "challenge_id": challenge_id,
                            "challenge_name": challenge_name,
                        }
                    )

        if not broken_by_challenge:
            self.console.print(
                "[yellow]No broken tasks with valid challenge links found.[/yellow]"
            )
            return False

        # --- Display Summary by Challenge ---
        self.console.print(
            f"\n[yellow]Found {len(valid_broken_tasks)} broken tasks across {len(broken_by_challenge)} challenges:[/yellow]"
        )
        challenge_table = Table(title="Challenges with Broken Tasks", box=box.ROUNDED)
        challenge_table.add_column("Num", style="dim", width=4)
        challenge_table.add_column("Challenge Name / ID", style="cyan")
        challenge_table.add_column(
            "Broken Task Count", style="magenta", justify="right"
        )

        challenge_list_for_selection = list(broken_by_challenge.keys())
        for i, challenge_id in enumerate(challenge_list_for_selection):
            name = challenge_names.get(challenge_id, challenge_id)
            count = len(broken_by_challenge[challenge_id])
            challenge_table.add_row(str(i + 1), name, str(count))

        self.console.print(challenge_table)

        # --- Prompt for Action Mode ---
        self.console.print("\nHow do you want to manage these broken tasks?")
        self.console.print("  [1] Manage by Challenge (Bulk Unlink)")
        self.console.print("  [2] Manage Individually (Select One Task)")
        self.console.print("  [0] Cancel")

        try:
            mode_choice = IntPrompt.ask(
                "Enter choice",
                choices=["0", "1", "2"],
                show_choices=False,
                console=self.console,
            )

            if mode_choice == 0:
                self.console.print("Operation cancelled.")
                return False

            # --- Mode 1: Manage by Challenge (Bulk) ---
            elif mode_choice == 1:
                challenge_num_choice = IntPrompt.ask(
                    f"Enter challenge number to manage (1-{len(challenge_list_for_selection)})",
                    choices=[
                        str(i) for i in range(1, len(challenge_list_for_selection) + 1)
                    ],
                    show_choices=False,
                    console=self.console,
                )
                selected_challenge_id = challenge_list_for_selection[
                    challenge_num_choice - 1
                ]
                selected_challenge_name = challenge_names.get(
                    selected_challenge_id, selected_challenge_id
                )
                tasks_in_selected_challenge = broken_by_challenge[selected_challenge_id]

                self.console.print(
                    f"\nTasks for challenge [cyan]'{selected_challenge_name}'[/]:"
                )
                for task_info in tasks_in_selected_challenge:
                    self.console.print(
                        f"  - {task_info['text']} ([dim]{task_info['id']}[/dim])"
                    )

                keep_personal_copy = Confirm.ask(
                    f"\nChoose unlink action for all {len(tasks_in_selected_challenge)} tasks in this challenge:\nKeep personal copies?",
                    default=True,
                    console=self.console,
                )
                keep_param = "keep" if keep_personal_copy else "remove"
                action_desc = (
                    "keeping personal copies"
                    if keep_param == "keep"
                    else "removing permanently"
                )

                if Confirm.ask(
                    f"Bulk-unlink all listed tasks for '{selected_challenge_name}' ({action_desc})?",
                    default=True,
                    console=self.console,
                ):
                    self.console.print(
                        f"Attempting bulk unlink for challenge {selected_challenge_id} ({action_desc})..."
                    )
                    try:
                        response = self.api_client.unlink_all_challenge_tasks(
                            selected_challenge_id, keep=keep_param
                        )
                        self.console.print(
                            f"[bold green]Bulk unlink successful for challenge '{selected_challenge_name}'.[/bold green]"
                        )
                        should_refresh = True
                    except Exception as e:
                        self.console.print(
                            f"[bold red]Error during bulk unlink for challenge {selected_challenge_id}: {e}[/bold red]"
                        )
                        self.console.print(
                            "[yellow]Note: This might happen if the challenge was deleted. Try individual unlinking.[/yellow]"
                        )
                        should_refresh = False  # Don't refresh if bulk failed
                else:
                    self.console.print("Bulk unlink cancelled.")
                    should_refresh = False

            # --- Mode 2: Manage Individually ---
            elif mode_choice == 2:
                # Display all valid broken tasks numbered
                individual_table = Table(
                    title="Select Individual Broken Task", box=box.ROUNDED
                )
                individual_table.add_column("Num", style="dim", width=4)
                individual_table.add_column("Task Text", style="cyan")
                individual_table.add_column("Challenge", style="magenta")
                individual_table.add_column("Task ID", style="dim")

                for i, task_info in enumerate(valid_broken_tasks):
                    individual_table.add_row(
                        str(i + 1),
                        task_info["text"],
                        task_info["challenge_name"],
                        task_info["id"],
                    )

                self.console.print(individual_table)

                task_num_choice = IntPrompt.ask(
                    f"Enter number of the task to unlink (1-{len(valid_broken_tasks)})",
                    choices=[str(i) for i in range(1, len(valid_broken_tasks) + 1)],
                    show_choices=False,
                    console=self.console,
                )
                selected_task = valid_broken_tasks[task_num_choice - 1]
                selected_task_id = selected_task["id"]
                selected_task_text = selected_task["text"]

                keep_personal_copy = Confirm.ask(
                    f"Keep a personal copy of '{selected_task_text}' after unlinking?",
                    default=True,
                    console=self.console,
                )
                keep_param = "keep" if keep_personal_copy else "remove"
                action_desc = (
                    "keeping personal copy"
                    if keep_param == "keep"
                    else "removing permanently"
                )

                if Confirm.ask(
                    f"Unlink task '{selected_task_text}' ({action_desc})?",
                    default=True,
                    console=self.console,
                ):
                    self.console.print(
                        f"Attempting to unlink task {selected_task_id} ({action_desc})..."
                    )
                    try:
                        response = self.api_client.unlink_task_from_challenge(
                            selected_task_id, keep=keep_param
                        )
                        self.console.print(
                            f"[bold green]Successfully unlinked task '{selected_task_text}'.[/bold green]"
                        )
                        should_refresh = True
                    except Exception as e:
                        self.console.print(
                            f"[bold red]Error unlinking task {selected_task_id}: {e}[/bold red]"
                        )
                        should_refresh = False
                else:
                    self.console.print("Unlink cancelled.")
                    should_refresh = False

        except (ValueError, IndexError):
            self.console.print("[bold red]Invalid selection.[/bold red]")
            should_refresh = False
        except KeyboardInterrupt:
            self.console.print("\nOperation cancelled by user.")
            should_refresh = False

        return should_refresh

    # --------------------------------------------------------------------------
    # 6. STATIC METHODS
    # --------------------------------------------------------------------------
    @staticmethod
    # >> Static method to calculate total task count
    def _get_total(task_counts: Dict) -> int:
        """Calculates total task count from categorized numbers dict."""
        total = 0
        if not isinstance(task_counts, dict):
            return 0
        for category_data in task_counts.values():
            if isinstance(category_data, dict):
                total += sum(category_data.values())
            elif isinstance(category_data, int):
                total += category_data
        return total


# --- End of CliApp class ---

# --- Entry Point (Example main.py) ---
# import sys
# from pathlib import Path
# project_dir = Path(__file__).resolve().parent.parent # Assumes main.py is in project root
# sys.path.insert(0, str(project_dir))
#
# from pixabit.cli.app import CliApp # Assuming app.py is in pixabit/cli/
# import traceback
#
# if __name__ == "__main__":
#     print("--- DEBUG: main.py starting ---")
#     try:
#         app = CliApp()
#         print("--- DEBUG: CliApp initialized. Calling run()... ---")
#         app.run()
#         print("--- DEBUG: app.run() finished. ---")
#     except KeyboardInterrupt:
#          print("\n[bold yellow]Ctrl+C detected. Exiting Pixabit.[/bold yellow]")
#          sys.exit(0)
#     except Exception as e:
#          try: # Try using Rich console for final error
#               from rich.console import Console
#               console = Console()
#               console.print(f"\n[error]An unexpected critical error occurred in main:[/error]")
#               console.print_exception(show_locals=True)
#          except ImportError: # Fallback to standard print
#               print(f"\nAn unexpected critical error occurred in main: {e}")
#               traceback.print_exc()
#          sys.exit(1)
#
