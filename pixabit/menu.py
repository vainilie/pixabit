# pixabit/cli/app.py

import datetime  # For stats display
import json  # Keep for temp display if needed
import os
import sys
import time  # Keep for potential pauses if needed
from typing import Any, Dict, List, Optional, Set

import timeago  # For stats display
from rich import rule  # Added Rule
from rich import box
from rich.columns import Columns
# --- Rich Imports ---
# Import necessary Rich components directly
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (BarColumn, Progress, SpinnerColumn,
                           TaskProgressColumn, TextColumn, TimeElapsedColumn,
                           track)
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

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
    from .challenge_backup import ChallengeBackupper
    from .config_utils import interactive_tag_setup
    from .export import (save_all_userdata_into_json,
                         save_processed_tasks_into_json, save_tags_into_json,
                         save_tasks_without_proccessing)
    from .processing import TaskProcessor, get_user_stats
    from .tag_manager import TagManager
    from .utils.clean_name import replace_illegal_filename_characters

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
    def __init__(self):
        """Initializes the application, API clients, and loads initial data."""
        self.console = Console()
        self.console.log("[bold blue]Initializing Pixabit App...[/bold blue]")

        try:
            self.api_client = HabiticaAPI(console=self.console)
            self.console.log("API Client Initialized.")
            self.processor = TaskProcessor(self.api_client)
            self.console.log("Task Processor Initialized.")
            self.tag_manager = TagManager(self.api_client)
            self.console.log("Tag Manager Initialized.")
            self.backupper = ChallengeBackupper(self.api_client)
            self.console.log("Challenge Backupper Initialized.")
        except ValueError as e:  # Config error likely from API init
            self.console.print(f"[bold red]Configuration Error:[/bold red] {e}")
            self.console.print("Please ensure your .env file is set up correctly.")
            self.console.print(
                "You might need to run 'pixabit configure tags' if needed."
            )
            sys.exit(1)
        except Exception as e:
            self.console.print(f"[bold red]Initialization Error:[/bold red] {e}")
            self.console.print_exception(show_locals=True)
            sys.exit(1)

        # Initialize application state
        self.processed_tasks: Dict[str, Dict] = {}
        self.cats_data: Dict[str, Any] = {}
        self.user_stats: Dict[str, Any] = {}
        self.all_tags: List[Dict] = []
        self.unused_tags: List[Dict] = []

        self.console.log("Performing initial data refresh...")
        self.refresh_data()  # Load data on startup
        self.console.log("[bold blue]Initialization complete.[/bold blue]\n")

    # --------------------------------------------------------------------------
    # 2. PRIMARY PUBLIC METHOD (Entry Point)
    # --------------------------------------------------------------------------
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
                "Manage Challenges": ["Backup Challenges"],
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

        total_steps = 4
        # Add ONE task for the overall refresh process
        refresh_task_id = progress.add_task("[cyan]Initializing...", total=total_steps)
        refresh_ok = True  # Flag to track overall success

        # Use Live context manager around the multi-step process
        with Live(progress, console=self.console, vertical_overflow="ellipsis") as live:
            try:
                # --- Step 1: Fetch Tags ---
                progress.update(
                    refresh_task_id, description="[cyan]Step 1/4: Fetching Tags..."
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
                        description="[cyan]Step 2/4: Processing Tasks...",
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
                        refresh_task_id, description="[cyan]Step 3/4: Fetching Stats..."
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
                        description="[cyan]Step 4/4: Calculating Unused...",
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

            except Exception as e:  # Catch unexpected errors during the Live block
                self.console.print_exception(show_locals=True)
                progress.update(refresh_task_id, description=f"[bold red]FATAL ERROR!")
                progress.stop()
                refresh_ok = False
                # Ensure defaults outside the 'with' block might be safer

        # Live context finished - Progress bar disappears if Progress(transient=True)
        # Update one last time to ensure final state is shown if transient=False
        final_description = (
            "[bold green]Refresh Complete!"
            if refresh_ok
            else "[bold red]Refresh Failed!"
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
            self.console.print(f"\n[bold red]Error during data refresh:[/bold red] {e}")
            self.console.print_exception(show_locals=False)
            # Ensure attributes remain valid default types
            self.processed_tasks = getattr(self, "processed_tasks", {}) or {}
            self.cats_data = getattr(self, "cats_data", {}) or {}
            self.user_stats = getattr(self, "user_stats", {}) or {}
            self.all_tags = getattr(self, "all_tags", []) or []
            self.unused_tags = getattr(self, "unused_tags", []) or []

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

    def _execute_action(self, action_name: str):
        """Executes the selected action by calling the appropriate method."""
        self.console.print(f"\n-> Executing: [cyan]{action_name}[/cyan]")
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
                f"[bold red]Error executing action '{action_name}': {e}[/bold red]"
            )
            self.console.print_exception(show_locals=False)

        # Use console instance for prompt
        Prompt.ask("\n[dim]Press Enter to continue...[/dim]", console=self.console)

    # --------------------------------------------------------------------------
    # 4. UI HELPER METHODS
    # --------------------------------------------------------------------------
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
                    f"[bold red]Invalid selection. Please choose 0-{max_option}.[/bold red]"
                )
                return -1
            return choice
        except ValueError:
            self.console.print("[red]Invalid input. Please enter a number.[/red]")
            return -1

        except Exception as e_menu:
            self.console.print(
                f"[bold red]>>> Error displaying menu '{title}':[/bold red]"
            )
            self.console.print_exception(show_locals=True)
            return -1  # Return invalid choice on error

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
            core_stats_table.add_row("[b #50B5E9]:gem: MP", f"{mp}")
            core_stats_table.add_row("[b #FFBE5D]:dizzy: EXP", f"{exp}")
            core_stats_table.add_row("[b #FFA624]:moneybag: GP", f"{gp}")

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
            self.console.print(
                f"[bold red]Error building stats display: {e}[/bold red]"
            )
            self.console.print_exception(show_locals=False)
            return Panel(
                f"[bold red]Error building stats[/]:\n{e}", border_style="red"
            )  # Return simple error panel

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
        table.add_column("Name", style="cyan", min_width=20)
        table.add_column("ID", style="magenta", overflow="fold", min_width=36)
        valid_tags = [tag for tag in self.all_tags if tag.get("id")]
        for i, tag in enumerate(valid_tags):
            table.add_row(str(i + 1), tag.get("name", "N/A"), tag.get("id"))
        self.console.print(table)

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
        table.add_column("Name", style="cyan", min_width=20)
        table.add_column("ID", style="magenta", overflow="fold", min_width=36)
        for i, tag in enumerate(self.unused_tags):
            table.add_row(str(i + 1), tag.get("name", "N/A"), tag.get("id", "N/A"))
        self.console.print(table)

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
            header_style="bold red",
            box=box.ROUNDED,
        )
        table.add_column("ID", style="magenta", width=36)
        table.add_column("Text", style="cyan")
        for task_id in broken_ids:
            task_detail = self.processed_tasks.get(task_id)
            task_text = (
                task_detail.get("text", "[i]N/A[/i]")
                if task_detail
                else "[dim](Details not found)[/dim]"
            )
            table.add_row(task_id, task_text)
        self.console.print(table)

    # --------------------------------------------------------------------------
    # 5. ACTION HELPER METHODS
    # --------------------------------------------------------------------------
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

    # --------------------------------------------------------------------------
    # 6. STATIC METHODS
    # --------------------------------------------------------------------------
    @staticmethod
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
#               console.print(f"\n[bold red]An unexpected critical error occurred in main:[/bold red]")
#               console.print_exception(show_locals=True)
#          except ImportError: # Fallback to standard print
#               print(f"\nAn unexpected critical error occurred in main: {e}")
#               traceback.print_exc()
#          sys.exit(1)
#
