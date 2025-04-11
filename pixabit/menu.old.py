# pixabit/cli/app.py

import datetime  # For stats display
import os
import sys
from typing import Any, Dict, List, Set

import timeago  # For stats display
# --- Third-party Libs ---
from art import text2art  # If using ASCII art title
from rich import box, rule
from rich.columns import Columns
# --- Rich Imports ---
# Consolidate Rich imports needed for the App/Display
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel  # Optional for layout
from rich.progress import (BarColumn, Progress, SpinnerColumn,
                           TaskProgressColumn, TextColumn, TimeElapsedColumn)
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.spinner import Spinner  # Can specify spinner type
from rich.table import Table
from rich.text import Text

from . import config  # To access configured tag IDs if needed directly
# --- Local Application Imports ---
# Adjust paths based on your final structure
from .api import HabiticaAPI
from .challenge_backup import ChallengeBackupper
# Assume interactive tag setup is in config_utils
from .config_utils import interactive_tag_setup
# Import specific export functions if needed, or handle saving within methods
from .export import (  # Add others if called directly
    save_all_userdata_into_json, save_tasks_without_proccessing)
from .processing import (TaskProcessor,  # get_user_stats kept separate
                         get_user_stats)
from .tag_manager import TagManager

# Use the console instance for printing within the class
# from rich import print # Avoid using global rich print directly if using instance


class CliApp:
    """
    Main application class for the Pixabit CLI.
    Handles menu display, user interaction, data fetching/refreshing,
    and dispatching actions to appropriate handlers.
    """

    # & __init__
    def __init__(self):
        """Initializes the application, API clients, and loads initial data."""
        self.console = Console()
        self.console.log("[bold blue]Initializing Pixabit App...[/bold blue]")

        try:
            # Pass console instance if needed by API/other components
            self.api_client = HabiticaAPI(console=self.console)
            self.console.log("API Client Initialized.")
            self.processor = TaskProcessor(
                self.api_client
            )  # Assumes Processor handles its own tag fetch message
            self.tag_manager = TagManager(
                self.api_client
            )  # Pass api_client (which has console)
            self.console.log("Tag Manager Initialized.")
            self.backupper = ChallengeBackupper(self.api_client)  # Pass api_client
            self.console.log("Challenge Backupper Initialized.")
        except ValueError as e:
            self.console.log(f"[bold red]Configuration Error:[/bold red] {e}")
            self.console.log("Please ensure your .env file is set up correctly.")
            self.console.log("You might need to run the tag configuration command.")
            sys.exit(1)
        except Exception as e:
            self.console.log(f"[bold red]Initialization Error:[/bold red] {e}")
            self.console.log_exception(
                show_locals=True
            )  # Show traceback for init errors
            sys.exit(1)

        # Initialize application state (data attributes)
        self.processed_tasks: Dict[str, Dict] = {}
        self.cats_data: Dict[str, Any] = {}
        self.user_stats: Dict[str, Any] = {}
        self.all_tags: List[Dict] = []
        self.unused_tags: List[Dict] = []

        self.console.log("Performing initial data refresh...")
        self.refresh_data()  # Load data on startup
        self.console.log("[bold blue]Initialization complete.[/bold blue]\n\n")

    # & refresh_data
    def refresh_data(self):
        """
        Fetches fresh data from Habitica and processes it, showing unified progress
        with a single updating progress bar using Live + Progress.
        """
        self.console.log("\n[bold green]Refreshing data...[/bold green]")

        # Define progress bar columns - customize as desired
        progress = Progress(
            TextColumn("•", style="dim"),
            TextColumn("[bold blue]{task.description}", justify="left"),
            BarColumn(bar_width=50),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            SpinnerColumn("dots"),
            console=self.console,
            transient=True,
        )
        total_steps = 4
        refresh_task_id = progress.add_task("[cyan]Initializing...", total=total_steps)
        refresh_ok = True

        with Live(
            progress,
            refresh_per_second=10,
            console=self.console,
            transient=False,
            vertical_overflow="ellipsis",
        ) as live:
            try:
                # --- Step 1: Fetch Tags ---
                progress.update(
                    refresh_task_id, description="[cyan]Step 1/4: Fetching Tags..."
                )
                self.console.log("Starting: Fetch Tags")
                fetched_tags = None
                try:
                    fetched_tags = self.api_client.get_tags()
                    self.all_tags = (
                        fetched_tags if isinstance(fetched_tags, list) else []
                    )
                    self.console.log(f"Fetched {len(self.all_tags)} tags.")
                    progress.update(refresh_task_id, advance=1)  # Complete step 1
                except Exception as e:
                    progress.update(
                        refresh_task_id, description="[bold red]Failed: Fetching Tags!"
                    )
                    # FIX: Use self.console.log
                    self.console.log(f"[bold red]Error fetching tags: {e}[/bold red]")
                    self.all_tags = []
                    refresh_ok = False
                    progress.stop()  # Stop progress on critical fail? Or just advance? Let's advance.
                    progress.update(
                        refresh_task_id, advance=1
                    )  # Advance even on failure

                # --- Step 2: Process Tasks ---
                progress.update(
                    refresh_task_id, description="[cyan]Step 2/4: Processing Tasks..."
                )
                self.console.log("Starting: Process Tasks")
                try:
                    # TaskProcessor needs tags. Ensure it uses self.all_tags (fetched above) if passed via init,
                    # or refetch internally if needed (less ideal). Assuming it uses the API client passed in init.
                    processed_results = self.processor.process_and_categorize_all()
                    self.processed_tasks = processed_results.get("data", {})
                    self.cats_data = processed_results.get("cats", {})
                    self.console.log(f"Processed {len(self.processed_tasks)} tasks.")
                    progress.update(refresh_task_id, advance=1)  # Complete step 2
                except Exception as e:
                    progress.update(
                        refresh_task_id,
                        description="[bold red]Failed: Processing Tasks!",
                    )
                    self.console.log(
                        f"[bold red]Error processing tasks: {e}[/bold red]"
                    )
                    self.processed_tasks = {}
                    self.cats_data = {}
                    refresh_ok = False
                    progress.update(refresh_task_id, advance=1)  # Advance anyway

                # --- Step 3: Fetch User Stats ---
                progress.update(
                    refresh_task_id, description="[cyan]Step 3/4: Fetching Stats..."
                )
                self.console.log("Starting: Fetch Stats")
                if self.cats_data:  # Need valid cats_data
                    try:
                        self.user_stats = get_user_stats(
                            self.api_client, self.cats_data
                        )
                        self.console.log("User stats fetched.")
                        progress.update(refresh_task_id, advance=1)  # Complete step 3
                    except Exception as e:
                        progress.update(
                            refresh_task_id,
                            description="[bold red]Failed: Fetching Stats!",
                        )
                        self.console.log(
                            f"[bold red]Error fetching stats: {e}[/bold red]"
                        )
                        self.user_stats = {}
                        refresh_ok = False
                        progress.update(refresh_task_id, advance=1)
                else:
                    progress.update(
                        refresh_task_id,
                        advance=1,
                        description="[yellow]Skipped: Fetching Stats (No Task Data)",
                    )
                    self.console.log(
                        "[yellow]Skipped stats fetch (no category data).[/yellow]"
                    )
                    self.user_stats = {}

                # --- Step 4: Calculate Unused Tags ---
                progress.update(
                    refresh_task_id,
                    description="[cyan]Step 4/4: Calculating Unused Tags...",
                )
                self.console.log("Starting: Calculate Unused Tags")
                if (
                    isinstance(self.all_tags, list) and self.all_tags
                ):  # Need tags fetched
                    try:
                        used_tag_ids: Set[str] = set(self.cats_data.get("tags", []))
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
                                description="[yellow]Skipped: Calculate Unused (Method missing)",
                            )
                            self.console.log(
                                "[yellow]Skipped unused tags (TagManager missing method).[/yellow]"
                            )
                            self.unused_tags = []
                    except Exception as e:
                        progress.update(
                            refresh_task_id,
                            advance=1,
                            description="[bold red]Failed: Calculate Unused!",
                        )
                        self.console.log(
                            f"[bold red]Error calculating unused tags: {e}[/bold red]"
                        )
                        self.unused_tags = []
                        refresh_ok = False
                else:
                    progress.update(
                        refresh_task_id,
                        advance=1,
                        description="[yellow]Skipped: Calculate Unused (No Tags)",
                    )
                    self.console.log(
                        "[yellow]Skipped unused tags calculation (no tags fetched).[/yellow]"
                    )
                    self.unused_tags = []

            except Exception as e:
                self.console.log_exception(show_locals=True)
                progress.update(
                    refresh_task_id,
                    description=f"[bold red]FATAL ERROR during refresh!",
                )
                progress.stop()
                refresh_ok = False
                # Ensure defaults
                self.processed_tasks = self.processed_tasks or {}
                self.cats_data = self.cats_data or {}
                self.user_stats = self.user_stats or {}
                self.all_tags = self.all_tags or []
                self.unused_tags = self.unused_tags or []

        # Live context finished
        if refresh_ok:
            progress.update(
                refresh_task_id,
                description="[bold green]Refresh Complete!",
                completed=total_steps,
            )
            self.console.log(
                "[bold green]Data refresh process completed successfully![/bold green]"
            )
        else:
            self.console.log(
                "[bold red]Data refresh process completed with errors.[/bold red]"
            )

    # & refresh_data_old
    def refresh_data_old(self):
        """Fetches fresh data from Habitica and processes it."""
        self.console.log("\n[bold green]Refreshing data...[/bold green]")
        try:
            # Process tasks and categories

            processed_results = self.processor.process_and_categorize_all()
            self.processed_tasks = processed_results.get("data", {})
            self.cats_data = processed_results.get("cats", {})
            if not self.processed_tasks:
                self.console.log("[yellow]Warning: No tasks processed.[/yellow]")

            # Get user stats (requires cats_data)
            if self.cats_data:
                self.user_stats = get_user_stats(self.api_client, self.cats_data)
            else:
                self.user_stats = {}  # Reset if no categories
                self.console.log(
                    "[yellow]Warning: Cannot generate user stats without category data.[/yellow]"
                )

            # Get all tags
            self.all_tags = self.api_client.get_tags()

            # Get unused tags
            used_tag_ids: Set[str] = set(self.cats_data.get("tags", []))
            self.unused_tags = self.tag_manager.find_unused_tags(
                self.all_tags, used_tag_ids
            )

            self.console.log("[bold green]Data refreshed successfully![/bold green]")

        except Exception as e:
            self.console.log(f"[bold red]Error during data refresh:[/bold red] {e}")

    # --- Menu Display ---
    # Make get_total a static method as it doesn't need self
    @staticmethod
    # & _get_total
    def _get_total(task_counts: Dict) -> int:
        """
        Calculates total task count from the categorized numbers dict.

        Args:
            task_counts (dict): The nested dictionary containing task counts
                               (e.g., from self.user_stats['task_counts']).

        Returns:
            int: The total sum of all tasks.
        """
        total = 0
        if not isinstance(task_counts, dict):
            return 0
        for category, category_data in task_counts.items():
            if isinstance(category_data, dict):
                total += sum(category_data.values())
            elif isinstance(category_data, int):
                total += category_data
        return total

    # --- CORRECT Method Definition ---
    # & _display_stats
    def _display_stats(self):
        """Displays formatted user stats using Rich."""
        stats_data = self.user_stats  # Access data stored in the instance

        if not stats_data:
            self.console.print(
                "[yellow]No user stats data available. Refresh data first.[/yellow]"
            )
            return

        # --- Safely extract data using .get with defaults ---
        # Using keys from the refactored get_user_stats output
        username = stats_data.get("username", "N/A")
        last_login_str = stats_data.get("last_login_local")
        day_start = stats_data.get("day_start", "?")
        is_sleeping = stats_data.get("sleeping", False)
        broken_count = stats_data.get("broken_challenge_tasks", 0)
        is_questing = stats_data.get("quest_active", False)
        quest_key = stats_data.get("quest_key")  # Get quest key if available
        # Note: get_user_stats doesn't provide quest progress, only active/key
        # quest_up = 0
        # quest_down = 0
        core_stats_values = stats_data.get("stats", {})
        gp = int(stats_data.get("gp", 0))  # Use top-level gp if available
        hp = int(stats_data.get("hp", 0))
        exp = int(stats_data.get("exp", 0))
        mp = int(stats_data.get("mp", 0))
        level = stats_data.get("level", 0)
        user_class = stats_data.get("class", "N/A")
        task_counts = stats_data.get("task_counts", {})

        # --- Process Time ---
        now = datetime.datetime.now(datetime.timezone.utc)  # Get current UTC time
        last_login_display = "N/A"
        if last_login_str and last_login_str != "N/A":
            try:
                last_login_dt = datetime.datetime.fromisoformat(last_login_str)
                # timeago should handle timezone comparison correctly if one is aware
                last_login_display = timeago.format(last_login_dt, now)
            except (ValueError, TypeError) as e:
                last_login_display = f"(Time Error: {e})"

        # --- Build Rich Display ---

        # User Info Table
        user_info_table = Table.grid(padding=(0, 2), expand=True)
        user_info_table.add_column(no_wrap=True, justify="right", style="dim")
        user_info_table.add_column(no_wrap=False, justify="left")
        user_info_table.add_row(":mage:", f"Hello, [b i]{username}")
        user_info_table.add_row(":hourglass:", f"Last login: [i]{last_login_display}")
        user_info_table.add_row(":alarm_clock:", f"Day starts at: {day_start} am")
        if is_sleeping:
            user_info_table.add_row(":zzz:", "[i]Resting in the Inn[/i]")
        if broken_count > 0:
            user_info_table.add_row(
                ":wilted_flower:", f"[red]{broken_count} broken challenge tasks[/red]"
            )
        if is_questing:
            user_info_table.add_row(
                ":dragon:",
                f"[pink]Currently on quest: [i]{quest_key or 'Unknown'}[/i][/pink]",
            )

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
            Panel(dailys_table, title="Dailies", padding=(0, 1), border_style="dim"),
            Panel(todos_table, title="Todos", padding=(0, 1), border_style="dim"),
        )

        # Combine sections into Panels
        display_stats_panel = Panel(
            core_stats_table,
            box=box.ROUNDED,
            title=f"Lv {level} {user_class}",
            border_style="magenta",
            expand=True,
        )

        total_tasks_num = CliApp._get_total(task_counts)  # Call static method
        display_numbers_panel = Panel(
            counts_display,
            box=box.ROUNDED,
            title=f"Tasks ({total_tasks_num} total)",
            border_style="blue",
            expand=True,
        )

        # Main layout table
        about_section = Table.grid(padding=0, expand=True)  # Changed padding
        about_section.add_column(no_wrap=False)  # Allow wrap if needed
        try:
            # Wrap art generation in try-except
            about_section.add_row("[b #6133b4]" + text2art("HABITICA", font="eftifont"))
        except Exception as art_err:
            self.console.print(
                f"[dim]Skipping ASCII art header due to error: {art_err}[/dim]"
            )
            about_section.add_row("[b #6133b4]HABITICA[/b]")  # Fallback text
        about_section.add_row(user_info_table)
        top_layout = Table.grid(padding=(0, 1), expand=True)
        top_layout.add_column(min_width=35)  # Give user info space
        top_layout.add_column(min_width=20)
        top_layout.add_row(user_info_table, display_stats_panel)

        # Final layout combining top section and numbers panel
        final_layout_simple = Table.grid(expand=False)
        final_layout_simple.add_row(top_layout)
        final_layout_simple.add_row(display_numbers_panel)

        # --- Create the final renderable panel ---
        stats_renderable = Panel(
            final_layout_simple,
            box=box.HEAVY,
            title=":mage: [b i]User Stats[/] :mage:",
            border_style="green",
            expand=False,
            padding=(1, 2),
        )

        # --- Ensure it PRINTS ---
        return stats_renderable

    # & _display_menu
    def _display_menu(
        self, title: str, options: List[str], show_art: bool = False
    ) -> int:
        """Displays a menu and returns the user's choice (0 for back/exit)."""
        self.console.rule("[bold]Welcome to PIXABIT")
        menu_renderable = [f"[b]{i+1}.[/] {opt}" for i, opt in enumerate(options)]
        # Use context-aware back/exit label
        back_exit_label = "Exit" if title == "Main Menu" else "Back"
        menu_renderable.insert(0, f"[b]0.[/] {back_exit_label}")

        # Optional Art Panel
        left_panel_content: Any = Text("")  # Default to empty Text if no stats shown
        if show_stats_area:
            stats_panel_object = self._display_stats()  # Calls the modified method
            if stats_panel_object:  # Check if it returned a Panel
                left_panel_content = stats_panel_object
            # If stats failed or no data, left_panel_content remains empty Text

        right_panel = Panel(
            Columns(
                menu_renderable, equal=True, expand=False
            ),  # Adjust columns if needed
            title=f"[#ebcb8b][b]{title}[/b]",
            border_style="#ebcb8b",
            box=box.HEAVY,
            padding=(1, 2),
        )

        if left_panel:
            layout = Layout()
            # Adjust ratio as needed
            layout.split_row(
                Layout(left_panel_content, ratio=2), Layout(right_panel, ratio=3)
            )
            self.console.print(Panel(layout, border_style="#ebcb8b", box=box.HEAVY))
        else:
            self.console.print(right_panel)

        # Get user input
        max_option = len(options)
        choice = IntPrompt.ask(
            "Choose an option",
            choices=[str(i) for i in range(max_option + 1)],  # 0 to max_option
            show_choices=False,  # Don't repeat choices in prompt line
        )
        return choice

    # --- Main Application Loop ---

    # & run
    def run(self):
        """Starts the main application menu loop."""
        while True:
            # Define menu structure within the loop if it needs dynamic updates
            # Or define as a class constant if static
            categories = {
                "Manage Tasks": [
                    "List Broken Tasks",
                    "Unlink Broken Tasks",
                    # "Sort Tasks", # TODO
                ],
                "Manage Tags": [
                    "Display All Tags",
                    "Display Unused Tags",
                    "Delete Unused Tags",
                    "Sync Challenge/Personal Tags",
                    "Sync Poison Tags",
                    "Sync Attribute Tags",
                    "Add/Replace Tag Interactively",
                ],
                "Manage Challenges": [
                    "Backup Challenges",
                    # "List Challenges", # TODO
                    # "Import Challenges", # TODO
                ],
                "View Data": [
                    "Display Stats",
                    # Add options to display raw/processed tasks?
                ],
                "Export Data": [
                    "Save Processed Tasks (JSON)",
                    "Save Raw Tasks (JSON)",
                    "Save All Tags (JSON)",
                    "Save Full User Data (JSON)",
                    # Backup Challenges is under Manage Challenges
                ],
                "User Actions": [
                    "Toggle Sleep Status",
                    # "Set Custom Day Start", # TODO
                ],
                "Application": ["Refresh Data", "Configure Special Tags", "Exit"],
            }
            main_menu_options = list(categories.keys())
            choice = self._display_menu(
                "Main Menu", main_menu_options, show_stats_area=True
            )

            if choice == 0:  # Exit from main menu (Choice 0 is "Exit")
                break
            if not 1 <= choice <= len(main_menu_options):
                self.console.print(
                    "[bold red]Invalid choice, please try again.[/bold red]"
                )
                continue

            category_name = main_menu_options[choice - 1]

            # Handle Exit directly if chosen from category list (should map to last index)
            if category_name == "Application" and "Exit" in categories["Application"]:
                # Find index of Exit within Application submenu
                exit_index_in_submenu = categories["Application"].index("Exit") + 1
                # Show submenu, but only handle exit or back
                sub_choice = self._display_menu(
                    f"{category_name} Menu", categories[category_name]
                )
                if sub_choice == 0:
                    continue  # Back to main
                if sub_choice == exit_index_in_submenu:
                    break  # Exit application
                else:  # Handle other App actions like Refresh, Configure
                    action_name = categories[category_name][sub_choice - 1]
                    self._execute_action(action_name)  # Execute other app actions

            else:
                # Enter submenu loop for other categories
                self._submenu_loop(category_name, categories[category_name])

        self.console.print("\n[bold magenta]Exiting Pixabit. Goodbye![/bold magenta]")

    # & _submenu_loop
    def _submenu_loop(self, title: str, options: List[str]):
        """Handles the display and logic for a submenu."""
        while True:
            choice = self._display_menu(f"{title} Menu", options)
            if choice == 0:  # Back to main menu
                break
            if not 1 <= choice <= len(options):
                self.console.print(
                    "[bold red]Invalid choice, please try again.[/bold red]"
                )
                continue

            action_name = options[choice - 1]
            self._execute_action(action_name)
            # Add a pause or prompt to continue after action?
            # Prompt.ask("\nPress Enter to return to the menu...")

    # --- Action Dispatcher ---

    # & _execute_action
    def _execute_action(self, action_name: str):
        """Executes the selected action by calling the appropriate method."""
        self.console.print(f"\n-> Executing: [cyan]{action_name}[/cyan]")
        refresh_needed = False  # Flag to see if data should be refreshed

        # Use try-except around action execution
        try:
            # --- Manage Tasks ---
            if action_name == "List Broken Tasks":
                self._display_broken_tasks()
            elif action_name == "Unlink Broken Tasks":
                refresh_needed = self._unlink_broken_tasks_action()
            # elif action_name == "Sort Tasks": self._sort_tasks_action()

            # --- Manage Tags ---
            elif action_name == "Display All Tags":
                self._display_tags()  # Use internal display method
            elif action_name == "Display Unused Tags":
                self._display_unused_tags()  # Use internal display method
            elif action_name == "Delete Unused Tags":
                # Pass the set of used IDs from categories
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

            # --- Manage Challenges ---
            elif action_name == "Backup Challenges":
                if Confirm.ask("Proceed with challenge backup?"):
                    backup_folder = os.path.join(os.getcwd(), "_challenge_backups")
                    self.backupper.create_backups(output_folder=backup_folder)
            # elif action_name == "List Challenges": self._display_challenges()

            # --- View Data ---
            elif action_name == "Display Stats":
                self._display_stats()  # Use internal display method

            # --- Export Data ---
            elif action_name == "Save Processed Tasks (JSON)":
                if Confirm.ask("Save processed tasks?"):
                    save_processed_tasks_into_json(
                        self.processed_tasks
                    )  # Use export function
            elif action_name == "Save Raw Tasks (JSON)":
                if Confirm.ask("Save raw tasks?"):
                    save_tasks_without_proccessing(self.api_client)
            elif action_name == "Save All Tags (JSON)":
                if Confirm.ask("Save all tags?"):
                    save_tags_into_json(self.api_client)
            elif action_name == "Save Full User Data (JSON)":
                if Confirm.ask("Save full user data?"):
                    save_all_userdata_into_json(self.api_client)

            # --- User Actions ---
            elif action_name == "Toggle Sleep Status":
                current_status = self.user_stats.get("sleeping", False)
                action_desc = "wake up" if current_status else "go to sleep"
                if Confirm.ask(f"Do you want to {action_desc}?"):
                    self.api_client.toggle_user_sleep()
                    self.console.print("Toggled sleep status.")
                    refresh_needed = True  # Refresh data to show updated status
            # elif action_name == "Set Custom Day Start": self._set_cds_action()

            # --- Application ---
            elif action_name == "Refresh Data":
                refresh_needed = True  # Signal refresh after action completes
            elif action_name == "Configure Special Tags":
                interactive_tag_setup(self.api_client)  # Call the setup function
                refresh_needed = True  # Config changed, likely need refresh

            else:
                self.console.print(
                    f"[yellow]Action '{action_name}' logic not fully implemented yet.[/yellow]"
                )

            # --- Refresh data if needed after action ---
            if refresh_needed:
                self.refresh_data()

        except Exception as e:
            self.console.print(
                f"[bold red]Error executing action '{action_name}': {e}[/bold red]"
            )
            # import traceback # Uncomment for detailed debugging
            # traceback.print_exc()

        # Pause briefly or wait for user input before showing menu again
        # time.sleep(1)
        Prompt.ask("\n[dim]Press Enter to continue...[/dim]")

    # --- Internal Display Methods (Integrate your Rich logic here) ---

    # & _display_tags
    def _display_tags(self):
        """Displays all fetched tags using Rich."""
        # (Keep implementation from previous step - uses self.console, self.all_tags)
        if not self.all_tags:
            self.console.print("[yellow]No tags data available.[/yellow]")
            return
        self.console.print(f"[bold]All Tags ({len(self.all_tags)}):[/bold]")
        table = Table(show_header=True, header_style="bold magenta", title="All Tags")
        table.add_column("Num", style="dim", width=4, justify="right")
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="magenta", overflow="fold")
        valid_tags = [tag for tag in self.all_tags if tag.get("id")]
        for i, tag in enumerate(valid_tags):
            table.add_row(str(i + 1), tag.get("name", "N/A"), tag.get("id"))
        self.console.print(table)

    # & _display_unused_tags
    def _display_unused_tags(self):
        """Displays unused tags using Rich."""
        # (Keep implementation from previous step - uses self.console, self.unused_tags)
        if not self.unused_tags:
            self.console.print("[green]No unused tags found.[/green]")
            return
        self.console.print(f"[bold]Unused Tags ({len(self.unused_tags)}):[/bold]")
        table = Table(show_header=True, header_style="bold yellow", title="Unused Tags")
        table.add_column("Num", style="dim", width=4, justify="right")
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="magenta", overflow="fold")
        for i, tag in enumerate(self.unused_tags):
            table.add_row(str(i + 1), tag.get("name", "N/A"), tag.get("id", "N/A"))
        self.console.print(table)

        # --- Integrate your print_unused logic here ---
        # Use self.console and self.unused_tags (which is List[Dict])
        console = self.console
        tags = self.unused_tags

        tag_renderables = [
            f"[b]{i+1}.[/] [i]{tag.get('name', 'N/A')}[/]\n[dim]ID: {tag.get('id', 'N/A')}[/dim]"
            for i, tag in enumerate(tags)
        ]
        tag_render = Panel(
            Columns(tag_renderables, equal=True, expand=True, padding=(1, 2)),
            title=f"[gold][i]Unused Tags ({len(tags)})[/i]",
            border_style="yellow",
        )
        console.print(tag_render)

    # & _display_broken_tasks
    def _display_broken_tasks(self):
        """Displays tasks marked as belonging to a broken challenge."""
        broken_ids = self.cats_data.get("broken", [])
        if not broken_ids:
            self.console.print("[green]No broken tasks found.[/green]")
            return

        self.console.print(f"[yellow]Found {len(broken_ids)} broken tasks:[/yellow]")
        table = Table(title="Broken Challenge Tasks")
        table.add_column("ID", style="magenta")
        table.add_column("Text", style="cyan")
        for task_id in broken_ids:
            task_detail = self.processed_tasks.get(task_id)
            if task_detail:
                table.add_row(task_id, task_detail.get("text", "N/A"))
            else:
                table.add_row(
                    task_id, "[dim](Task details not found in processed data)[/dim]"
                )
        self.console.print(table)

    # & _unlink_broken_tasks_action
    def _unlink_broken_tasks_action(self) -> bool:
        """Handles confirming and unlinking broken tasks."""
        broken_ids = self.cats_data.get("broken", [])
        if not broken_ids:
            self.console.print("[green]No broken tasks to unlink.[/green]")
            return False

        self._display_broken_tasks()  # Show them first
        if Confirm.ask(
            f"\nUnlink these {len(broken_ids)} broken tasks? (Will be kept as personal tasks)",
            default=False,
        ):
            actions = [("unlink", task_id, "keep") for task_id in broken_ids]
            # Use a generic action executor or loop here
            error_count = 0
            for _, task_id, keep_status in track(
                actions, description="Unlinking broken tasks..."
            ):
                try:
                    self.api_client.unlink_task_from_challenge(
                        task_id, keep=keep_status
                    )
                except Exception as e:
                    self.console.print(f"\n[red]Error unlinking {task_id}: {e}[/red]")
                    error_count += 1
            if error_count == 0:
                self.console.print("[green]Broken tasks unlinked successfully.[/green]")
            else:
                self.console.print(
                    f"[yellow]Completed unlinking with {error_count} errors.[/yellow]"
                )
            return True  # Indicate refresh is needed
        else:
            self.console.print("No tasks unlinked.")
            return False

    # & _interactive_tag_replace_action
    def _interactive_tag_replace_action(self) -> bool:
        """Handles the interactive prompts for replacing tags."""
        self._display_tags()  # Show tags with numbers first
        if not self.all_tags:
            self.console.print(
                "[yellow]No tags available to perform replacement.[/yellow]"
            )
            return False

        valid_tags = [
            tag for tag in self.all_tags if tag.get("id")
        ]  # Use only tags with IDs
        num_tags = len(valid_tags)
        if num_tags == 0:
            self.console.print("[yellow]No valid tags with IDs found.[/yellow]")
            return False

        try:
            self.console.print("\nSelect tags by number from the list above.")
            del_num = IntPrompt.ask(
                f"Enter number of tag to find/replace (1-{num_tags})",
                console=self.console,
            )
            add_num = IntPrompt.ask(
                f"Enter number of tag to add (1-{num_tags})", console=self.console
            )

            # Validate choices against the valid tags list
            if not (1 <= del_num <= num_tags and 1 <= add_num <= num_tags):
                self.console.print("[red]Invalid tag number selection.[/red]")
                return False

            tag_find = valid_tags[del_num - 1]
            tag_add = valid_tags[add_num - 1]
            tag_find_id = tag_find.get("id")
            tag_add_id = tag_add.get("id")
            tag_find_name = tag_find.get("name", "N/A")
            tag_add_name = tag_add.get("name", "N/A")

            # ID check should be redundant now, but keep just in case
            if not tag_find_id or not tag_add_id:
                self.console.print(
                    "[red]Internal Error: Selected tags missing IDs.[/red]"
                )
                return False

            if tag_find_id == tag_add_id:
                self.console.print(
                    "[yellow]Source and target tags cannot be the same.[/yellow]"
                )
                return False

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
                # Pass console if TagManager needs it for its progress/confirmation
                self.tag_manager.add_or_replace_tag_based_on_other(
                    self.processed_tasks, tag_find_id, tag_add_id, replace
                )
                return True  # Refresh needed
            else:
                self.console.print("Operation cancelled.")
                return False

        except ValueError:
            self.console.print("[red]Invalid number entered.[/red]")
            return False
        except IndexError:
            self.console.print("[red]Selection number out of range.[/red]")
            return False


# --- Entry Point (main.py) ---
# import os
# import sys
# # Add project root to path if needed, depending on how you run it
# # project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# # sys.path.insert(0, project_root)
#
# from pixabit.cli.app import CliApp # Adjust import path
#
# if __name__ == "__main__":
#     app = CliApp()
#     app.run()
#
