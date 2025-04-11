# pixabit/cli/app.py

import json
import os
import sys
from typing import Any, Dict, List, Optional

from .api import HabiticaAPI
from .challenge_backup import ChallengeBackupper
from .get_user_stats import get_user_stats
from .processing import TaskProcessor
from .tag_manager import TagManager
from .utils.display import (Confirm, IntPrompt, Layout, Panel, Prompt, Table,
                            console, print)

console = console


# ==============================================================================
# CLI Application Class
# ==============================================================================
class CliApp:
    """
    Main application class for the Pixabit CLI.

    Handles initializing core components (API, Processor, Managers),
    managing application state (fetched data), displaying menus using Rich,
    handling user input, refreshing data, and dispatching actions to the
    appropriate handlers (e.g., TagManager, ChallengeBackupper).
    """

    # --- Initialization ---
    def __init__(self):
        """
        Initializes the Pixabit CLI application.

        - Sets up a Rich Console.
        - Creates instances of core components (HabiticaAPI, TaskProcessor, etc.).
          Crucially handles potential configuration errors during API init.
        - Initializes internal state variables to hold processed data.
        - Performs an initial data refresh to populate the state.

        Raises:
            ValueError: If Habitica API credentials (user ID, API token) are
                        missing or invalid, preventing API client initialization.
            SystemExit: If initialization fails due to configuration or other
                        critical errors.
        """
        print("Initializing Pixabit App...")
        # Use an instance console for consistent output formatting
        console = console
        try:
            # Instantiate core components
            self.api_client = HabiticaAPI()  # Reads config from .env or env vars
            self.processor = TaskProcessor(self.api_client)
            self.tag_manager = TagManager(
                self.api_client
            )  # Pass console if needed for interaction
            self.backupper = ChallengeBackupper(self.api_client)  # Pass console
            # Add other manager/handler instances if created (e.g., TaskSorter)
            # self.sorter = TaskSorter(self.api_client)

        except (
            ValueError
        ) as e:  # Specific error from HabiticaAPI likely due to missing creds
            console.print(f"[bold red]Configuration Error:[/bold red] {e}")
            console.print(
                "Please ensure your HABITICA_USER_ID and HABITICA_API_TOKEN are set"
            )
            console.print("correctly in your .env file or environment variables.")
            sys.exit(1)  # Exit if core API component can't load
        except Exception as e:
            console.print(
                f"[bold red]Initialization Error:[/bold red] Failed to initialize components."
            )
            console.print(f"Error details: {type(e).__name__}: {e}")
            # import traceback # Uncomment for debug
            # traceback.print_exc() # Uncomment for debug
            sys.exit(1)

        # Initialize application state (data caches)
        self.processed_tasks: Dict[str, Dict] = (
            {}
        )  # Maps task_id -> processed task dict
        self.cats_data: Dict[str, Any] = {}  # Holds categorized task IDs etc.
        self.user_stats: Dict[str, Any] = {}  # Holds user profile stats
        self.all_tags: List[Dict] = []  # Stores the full list of tag dicts from API
        # self.unused_tags: List[Dict] = [] # Calculated in refresh_data if needed

        print("Performing initial data refresh...")
        # Perform initial data fetch and processing
        self.refresh_data()  # This populates the state variables above
        print("Initialization complete.")

    # --- Data Handling ---
    def refresh_data(self):
        """
        Fetches fresh data from Habitica and processes it, showing unified progress.
        Uses the Live + Progress pattern.
        """
        console.print("\n[bold green]Refreshing data...[/bold green]")

        # Define progress bar columns
        progress = Progress(
            TextColumn("•"),  # Small prefix
            TextColumn("[bold blue]{task.description}", justify="left"),
            BarColumn(bar_width=None),  # Bar fills remaining space
            TaskProgressColumn(),  # Percentage or completed count
            TimeElapsedColumn(),
            Spinner("dots", style="status.spinner"),  # Spinner shown while task active
            console=console,
            # transient=True, # Set True to remove progress bar on exit
        )

        # Define overall layout (optional, can just use 'progress')
        layout = Panel(progress, title="Data Refresh Progress", border_style="green")

        # Add tasks for each major step (total=1 indicates completion state)
        tags_task = progress.add_task("Fetch Tags", total=1, start=False)
        process_task = progress.add_task("Process Tasks", total=1, start=False)
        stats_task = progress.add_task("Fetch Stats", total=1, start=False)
        unused_task = progress.add_task("Calculate Unused Tags", total=1, start=False)

        tasks_processed_ok = False  # Flag for dependent steps

        # Use Live context manager
        with Live(progress, refresh_per_second=10, console=console) as live:
            try:
                # --- Step 1: Fetch Tags ---
                live.log(
                    "Starting: Fetch Tags"
                )  # Use live.log for messages within Live
                progress.start_task(tags_task)
                try:
                    self.all_tags = self.api_client.get_tags()
                    progress.update(
                        tags_task, completed=1, description="[green]Fetched Tags"
                    )
                    live.log(f"Fetched {len(self.all_tags)} tags.")
                except Exception as e:
                    progress.update(
                        tags_task, description="[bold red]Failed: Fetch Tags"
                    )
                    live.log(f"[bold red]Error fetching tags: {e}[/bold red]")
                    # Decide if we should stop here? Let's continue for now.

                # --- Step 2: Process Tasks ---
                # This might take a while, Progress bar will just show 'running'
                # unless TaskProcessor itself can update a sub-task (more complex)
                live.log("Starting: Process Tasks")
                progress.start_task(process_task)
                try:
                    processed_results = self.processor.process_and_categorize_all()
                    self.processed_tasks = processed_results.get("data", {})
                    self.cats_data = processed_results.get("cats", {})
                    progress.update(
                        process_task, completed=1, description="[green]Processed Tasks"
                    )
                    live.log(f"Processed {len(self.processed_tasks)} tasks.")
                    tasks_processed_ok = True  # Set flag for dependent steps
                except Exception as e:
                    progress.update(
                        process_task, description="[bold red]Failed: Process Tasks"
                    )
                    live.log(f"[bold red]Error processing tasks: {e}[/bold red]")
                    tasks_processed_ok = False

                # --- Step 3: Fetch User Stats (Depends on successful processing) ---
                live.log("Starting: Fetch Stats")
                progress.start_task(stats_task)
                if tasks_processed_ok and self.cats_data:
                    try:
                        self.user_stats = get_user_stats(
                            self.api_client, self.cats_data
                        )
                        progress.update(
                            stats_task, completed=1, description="[green]Fetched Stats"
                        )
                        live.log("User stats fetched.")
                    except Exception as e:
                        progress.update(
                            stats_task, description="[bold red]Failed: Fetch Stats"
                        )
                        live.log(f"[bold red]Error fetching stats: {e}[/bold red]")
                else:
                    progress.update(
                        stats_task, description="[yellow]Skipped: Fetch Stats"
                    )
                    live.log(
                        "[yellow]Skipped stats fetch (task processing failed or no category data).[/yellow]"
                    )
                    self.user_stats = {}  # Ensure it's reset

                # --- Step 4: Calculate Unused Tags (Depends on tags and processed tasks) ---
                live.log("Starting: Calculate Unused Tags")
                progress.start_task(unused_task)
                if (
                    tasks_processed_ok and self.all_tags
                ):  # Need all_tags and used tags from cats_data
                    try:
                        used_tag_ids: Set[str] = set(self.cats_data.get("tags", []))
                        # Assuming find_unused_tags is now part of TagManager
                        self.unused_tags = self.tag_manager.find_unused_tags(
                            self.all_tags, used_tag_ids
                        )
                        progress.update(
                            unused_task,
                            completed=1,
                            description="[green]Calculated Unused Tags",
                        )
                        live.log(f"Found {len(self.unused_tags)} unused tags.")
                    except Exception as e:
                        progress.update(
                            unused_task,
                            description="[bold red]Failed: Calculate Unused",
                        )
                        live.log(
                            f"[bold red]Error calculating unused tags: {e}[/bold red]"
                        )
                else:
                    progress.update(
                        unused_task, description="[yellow]Skipped: Calculate Unused"
                    )
                    live.log(
                        "[yellow]Skipped unused tags calculation (task processing or tag fetch failed).[/yellow]"
                    )
                    self.unused_tags = []  # Ensure it's reset

            except Exception as e:
                # Catch unexpected errors during the overall Live process
                # This might hide where the error happened, specific try/excepts above are better
                console.print_exception()  # Print traceback for unexpected errors
                live.update(
                    Panel(
                        f"[bold red]An unexpected error interrupted the refresh: {e}[/bold red]"
                    )
                )

        # Live context finished
        # Check final status? Or rely on logs printed above the final bar.
        # Print final summary message
        if tasks_processed_ok:  # Check if the critical step succeeded
            console.print("[bold green]Data refresh process completed![/bold green]")
        else:
            console.print(
                "[bold red]Data refresh process completed with errors.[/bold red]"
            )

    # --- Menu & UI ---
    def _display_menu(
        self, title: str, options: List[str], exit_option: str = "Back / Exit"
    ) -> int:
        """
        Displays a formatted menu using Rich and prompts the user for a choice.

        Args:
            title (str): The title of the menu.
            options (List[str]): A list of strings representing the menu options.
            exit_option (str): The text for the '0' option (usually back or exit).

        Returns:
            int: The user's numerical choice (0 for exit/back, 1+ for options).
                 Returns -1 or raises an error on input failure if not handled by IntPrompt.
        """
        console.print(
            f"\n╭─ [bold cyan]{title}[/bold cyan] {'─' * (30 - len(title))}─╮"
        )  # Basic frame

        renderables = [
            f"│ [bold yellow] {i+1}.[/] {opt:<28} │" for i, opt in enumerate(options)
        ]
        renderables.insert(
            0, f"│ [bold yellow] 0.[/] {exit_option:<28} │"
        )  # Add exit/back option

        for item in renderables:
            console.print(item)

        console.print(f"╰─{'─' * 35}─╯")

        # Get user input using Rich IntPrompt for validation
        max_option = len(options)
        choice = IntPrompt.ask(
            "Choose an option",
            choices=[
                str(i) for i in range(max_option + 1)
            ],  # Valid choices are 0 to max_option
            show_choices=False,  # Don't repeat choices in the prompt itself
            console=console,  # Use the instance console
        )
        return choice

    # --- Application Flow ---
    def run(self):
        """
        Starts the main application loop.

        Displays the main menu, handles user selection, and either enters a
        submenu loop, executes an app-level action (like refresh or exit),
        or exits the application.
        """
        while True:
            # Define menu structure dynamically
            categories = {
                "Challenges": [
                    "Backup Challenges",
                    "List Challenges (TODO)",
                ],  # Add more? Import?
                "Tasks": [
                    "List Broken Tasks",
                    "Unlink Broken Tasks",
                    "Sort Tasks (TODO)",
                ],
                "Tags": [
                    "Display All Tags",
                    "Sync Challenge/Personal Tags",
                    "Sync Poison Status Tags",
                    "Sync Attribute Tags",
                    "Manage Unused Tags",
                    "Replace Tag (TODO)",
                ],
                "User": ["Display Stats", "Toggle Sleep", "Save All User Data (TODO)"],
                "App": ["Refresh Data", "Exit"],
            }
            main_menu_options = list(categories.keys())
            choice = self._display_menu(
                "Main Menu", main_menu_options, exit_option="Exit Pixabit"
            )

            if choice == 0:  # Exit from main menu
                break
            # Choice validation already handled by _display_menu's IntPrompt

            category_name = main_menu_options[choice - 1]  # Adjust index

            if category_name == "App":
                # Handle App actions directly in this loop
                # For simplicity, assume 'Refresh Data' is 1, 'Exit' is 2 in the 'App' list
                app_choice = self._display_menu(
                    "App Actions", categories["App"], exit_option="Back"
                )
                if app_choice == 1:  # Refresh Data
                    self.refresh_data()
                elif app_choice == 2:  # Exit chosen from App submenu
                    if Confirm.ask(
                        "Are you sure you want to exit Pixabit?", console=console
                    ):
                        break  # Break main loop
                # If app_choice is 0 (Back), the loop continues to main menu
            else:
                # Enter submenu loop for the chosen category
                self._submenu_loop(category_name, categories[category_name])

        console.print("\n[bold magenta]✨ Exiting Pixabit. Goodbye! ✨[/bold magenta]")

    def _submenu_loop(self, title: str, options: List[str]):
        """
        Handles the display and logic for a specific category's submenu.

        Continuously displays the submenu options until the user chooses '0' (Back).
        For other choices, it calls `_execute_action` to perform the task.

        Args:
            title (str): The title for the submenu (e.g., "Tags").
            options (List[str]): The list of actions available in this submenu.
        """
        while True:
            choice = self._display_menu(
                f"{title} Menu", options, exit_option="Back to Main Menu"
            )
            if choice == 0:  # Back to main menu
                break
            # Choice validation handled by _display_menu

            action_name = options[choice - 1]  # Adjust index
            self._execute_action(action_name, title)  # Pass title for context if needed

    # --- Action Execution ---
    def _execute_action(self, action_name: str, category: str):
        """
        Executes the selected action by calling the appropriate method/handler.

        Acts as a dispatcher based on the `action_name`. Passes necessary data
        (like `self.processed_tasks`, `self.api_client`, etc.) to the handlers.
        Includes basic confirmation prompts for potentially destructive actions.
        Refreshes data automatically after actions that modify Habitica state.

        Args:
            action_name (str): The name of the action selected from a submenu.
            category (str): The category the action belongs to (e.g., "Tags", "Tasks").
                             Used for context in messages or logic if needed.
        """
        console.print(f"\n▶️ Executing: [bold cyan]{action_name}[/bold cyan]...")

        # Flag to indicate if data should be refreshed after the action
        should_refresh = False

        try:
            # --- Challenges ---
            if action_name == "Backup Challenges":
                if Confirm.ask(
                    "Proceed with backing up all owned/contributed challenges?",
                    console=console,
                ):
                    # Define backup folder path more robustly
                    backup_folder = os.path.join(os.getcwd(), "_challenge_backups")
                    os.makedirs(backup_folder, exist_ok=True)  # Ensure folder exists
                    self.backupper.create_backups(output_folder=backup_folder)
                    # No refresh needed for backup
            elif action_name == "List Challenges (TODO)":
                console.print(
                    "[yellow]🚧 Action 'List Challenges' not implemented yet.[/yellow]"
                )
                # Implementation: Fetch challenges (e.g., self.api_client.get_challenges()), format, display.

            # --- Tasks ---
            elif action_name == "List Broken Tasks":
                broken_ids = self.cats_data.get("broken", [])
                if not broken_ids:
                    console.print("[green]✅ No broken tasks found.[/green]")
                else:
                    console.print(
                        f"[yellow]⚠️ Found {len(broken_ids)} tasks linked to broken challenges:[/yellow]"
                    )
                    # Display basic info - consider a more detailed table display
                    table = Table(
                        title="Broken Tasks",
                        show_header=True,
                        header_style="bold magenta",
                    )
                    table.add_column("ID", style="dim", width=36)
                    table.add_column("Text")
                    for task_id in broken_ids:
                        task_detail = self.processed_tasks.get(task_id)
                        task_text = (
                            task_detail.get("text", "[i]N/A[/i]")
                            if task_detail
                            else "[i]Details not found[/i]"
                        )
                        table.add_row(task_id, task_text)
                    console.print(table)
                    console.print("[i]Use 'Unlink Broken Tasks' to detach them.[/i]")
            elif action_name == "Unlink Broken Tasks":
                broken_ids = self.cats_data.get("broken", [])
                if not broken_ids:
                    console.print("[green]✅ No broken tasks to unlink.[/green]")
                else:
                    if Confirm.ask(
                        f"Unlink {len(broken_ids)} broken tasks? (They will be kept as personal tasks)",
                        console=console,
                    ):
                        console.print("   Unlinking tasks...")
                        success_count = 0
                        fail_count = 0
                        for task_id in broken_ids:
                            try:
                                # 'keep' is the default, but being explicit is good
                                self.api_client.unlink_task_from_challenge(
                                    task_id, keep="keep"
                                )
                                console.print(
                                    f"     [green]✓ Unlinked {task_id}[/green]"
                                )
                                success_count += 1
                            except Exception as e:
                                console.print(
                                    f"     [red]✗ Error unlinking {task_id}: {e}[/red]"
                                )
                                fail_count += 1
                        console.print(
                            f"   Unlink complete. Success: {success_count}, Failed: {fail_count}"
                        )
                        if success_count > 0:
                            should_refresh = True  # Refresh if changes were made
            elif action_name == "Sort Tasks (TODO)":
                console.print(
                    "[yellow]🚧 Action 'Sort Tasks' not implemented yet.[/yellow]"
                )
                # Implementation: Needs TaskSorter class/methods, user interaction for criteria.

            # --- Tags ---
            elif action_name == "Display All Tags":
                if not self.all_tags:
                    console.print(
                        "[yellow]No tags found or data not refreshed.[/yellow]"
                    )
                else:
                    # Use TagManager or a local display function
                    self.tag_manager.display_tags_table(
                        self.all_tags
                    )  # Assumes method exists in TagManager
            elif action_name == "Sync Challenge/Personal Tags":
                if Confirm.ask(
                    "Sync 'challenge'/'personal' tags based on task challenge status?",
                    console=console,
                ):
                    count = self.tag_manager.sync_challenge_personal_tags(
                        self.processed_tasks
                    )
                    console.print(f"   Checked/Updated tags for {count} tasks.")
                    if count > 0:
                        should_refresh = True
            elif action_name == "Sync Poison Status Tags":
                if Confirm.ask(
                    "Sync 'poison' tags based on daily/todo status (red/overdue)?",
                    console=console,
                ):
                    count = self.tag_manager.ensure_poison_status_tags(
                        self.processed_tasks
                    )
                    console.print(f"   Checked/Updated poison tags for {count} tasks.")
                    if count > 0:
                        should_refresh = True
            elif action_name == "Sync Attribute Tags":
                if Confirm.ask(
                    "Sync attribute tags (str, int, per, con) based on task attribute?",
                    console=console,
                ):
                    count = self.tag_manager.sync_attributes_to_tags(
                        self.processed_tasks
                    )
                    console.print(
                        f"   Checked/Updated attribute tags for {count} tasks."
                    )
                    if count > 0:
                        should_refresh = True
            elif action_name == "Manage Unused Tags":
                used_ids = set(self.cats_data.get("tags", []))
                # This method should handle the interaction internally
                deleted_count = self.tag_manager.delete_unused_tags_interactive(
                    self.all_tags, used_ids
                )
                console.print(f"   Deleted {deleted_count} unused tags.")
                if deleted_count > 0:
                    should_refresh = True
            elif action_name == "Replace Tag (TODO)":
                console.print(
                    "[yellow]🚧 Action 'Replace Tag' not implemented yet.[/yellow]"
                )
                # Implementation: Prompt for tag_find ID, tag_add ID, replace bool, call tag_manager method.

            # --- User ---
            elif action_name == "Display Stats":
                if not self.user_stats:
                    console.print(
                        "[yellow]User stats not available. Refresh data?[/yellow]"
                    )
                else:
                    # Use a dedicated display function (could be in utils.display or here)
                    self._display_user_stats(self.user_stats)
            elif action_name == "Toggle Sleep":
                current_status = self.user_stats.get("preferences", {}).get(
                    "sleep", False
                )
                action = "wake up" if current_status else "go to sleep"
                if Confirm.ask(
                    f"Currently {'sleeping' if current_status else 'awake'}. Do you want to {action}?",
                    console=console,
                ):
                    self.api_client.toggle_user_sleep()  # API call handles the toggle
                    console.print(
                        f"   Toggled sleep status. User should now be {'awake' if current_status else 'sleeping'}."
                    )
                    should_refresh = True  # Refresh to show updated status
            elif action_name == "Save All User Data (TODO)":
                console.print(
                    "[yellow]🚧 Action 'Save All User Data' not implemented yet.[/yellow]"
                )
                # Implementation: Fetch full user profile (api_client.get_user()), save to file.

            # --- Default ---
            else:
                console.print(
                    f"[yellow]🚧 Action '{action_name}' is recognized but not implemented yet.[/yellow]"
                )

            # --- Post-Action Refresh ---
            if should_refresh:
                self.refresh_data()
            else:
                console.print("[dim]   (No data refresh needed for this action)[/dim]")

        except Exception as e:
            console.print(
                f"[bold red]❌ Error executing action '{action_name}':[/bold red]"
            )
            console.print(f"   {type(e).__name__}: {e}")
            # import traceback # Uncomment for detailed debugging during development
            # traceback.print_exc(file=sys.stderr) # Print traceback to stderr

        # Add a small pause or prompt before returning to the menu
        # Prompt.ask("\n[Press Enter to continue...]", console=console)

    # --- Internal Display Helpers ---
    def _display_user_stats(self, stats: Dict):
        """Displays user statistics in a formatted way."""
        if not stats:
            console.print("[yellow]No stats data to display.[/yellow]")
            return

        panel_content = f"""
[b]Username:[/b] {stats.get('username', 'N/A')}
[b]Level:[/b] {stats.get('level', 'N/A')}
[b]Class:[/b] {stats.get('class', 'N/A')}
[b]HP:[/b] {stats.get('hp', 0.0):.1f} / {stats.get('maxHealth', 'N/A')}
[b]MP:[/b] {stats.get('mp', 0.0):.1f} / {stats.get('maxMP', 'N/A')}
[b]XP:[/b] {stats.get('exp', 0.0):.1f} / {stats.get('toNextLevel', 'N/A')}
[b]Gold:[/b] {stats.get('gp', 0.0):.2f}
[b]Gems:[/b] {stats.get('gems', 0)} {'💎'}
[b]Sleeping:[/b] {'Yes' if stats.get('sleeping', False) else 'No'} 😴

[b]Tasks:[/b]
  Habits: {stats.get('habit_count', 'N/A')}
  Dailies: {stats.get('daily_count', 'N/A')} (Due: {stats.get('dailies_due', 'N/A')}, Done: {stats.get('dailies_done', 'N/A')})
  To-Dos: {stats.get('todo_count', 'N/A')} (Due: {stats.get('todos_due', 'N/A')}, Overdue: {stats.get('todos_overdue', 'N/A')})
  Rewards: {stats.get('reward_count', 'N/A')}
"""
        console.print(Panel(panel_content, title="User Stats", border_style="blue"))


# ==============================================================================
# Entry Point (Example - usually in a main.py)
# ==============================================================================
# This block should typically reside in your top-level script (e.g., main.py or pixabit_cli.py)
#
# if __name__ == "__main__":
#     # Ensure terminal supports colors if possible (Rich handles this well)
#     # os.system('') # Optional: Might help on Windows for ANSI codes
#
#     try:
#         app = CliApp() # Initialization happens here (incl. initial refresh)
#         app.run()      # Start the main menu loop
#     except KeyboardInterrupt:
#         print("\n[yellow]Operation cancelled by user. Exiting.[/yellow]")
#         sys.exit(0)
#     except Exception as e:
#         # Catch any unexpected errors during run that weren't handled internally
#         console = Console() # Create a console just for this final error message
#         console.print(f"[bold red]\n--- An Unexpected Error Occurred ---[/bold red]")
#         console.print(f"{type(e).__name__}: {e}")
#         console.print("[italic]Please report this issue if it persists.[/italic]")
#         # import traceback # Uncomment for debugging
#         # traceback.print_exc() # Uncomment for debugging
#         sys.exit(1)
