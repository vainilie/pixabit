# pixabit/tui/app.py

# SECTION: MODULE DOCSTRING
"""Main Textual TUI application class for Pixabit.

Sets up the layout, widgets, data store, and handles user interactions,
key bindings, and asynchronous operations for interacting with the Habitica API.
"""

# SECTION: IMPORTS
import asyncio
from typing import Any  # Use Type for class reference in ComposeResult

# --- Textual Imports ---
from textual.app import App, ComposeResult
from textual.containers import Container  # Basic layout containers
from textual.reactive import reactive
from textual.widgets import Footer, Header  # Core widgets

# Optional: For loading indicators, modals etc.
# from textual.widgets import LoadingIndicator
# from textual.screen import ModalScreen

# --- Local Application Imports ---
try:
    from .data_store import PixabitDataStore
    from .widgets.placeholder import PlaceholderWidget as ContentArea
    from .widgets.placeholder import PlaceholderWidget as MainMenu

    # Import Widgets (Create these files in tui/widgets/)
    # Assuming placeholder widgets for now
    from .widgets.placeholder import PlaceholderWidget as StatsPanel

    # from .widgets.stats_panel import StatsPanel # Example real widget import
    # from .widgets.main_menu import MainMenu     # Example real widget import
    # from .widgets.content_area import ContentArea # Example real widget import

except ImportError as e:
    # Use standard print as console might not be ready
    import builtins

    builtins.print(
        f"FATAL ERROR: Could not import Pixabit TUI modules in app.py: {e}"
    )
    # Provide instructions if possible
    builtins.print(
        "Ensure DataStore, Widgets etc. are correctly defined and importable."
    )
    import sys

    sys.exit(1)


# SECTION: PixabitTUIApp Class
# KLASS: PixabitTUIApp
class PixabitTUIApp(App[None]):  # Specify return type for run() as None
    """The main Textual TUI Application for Pixabit."""

    # Link CSS file for styling
    CSS_PATH = "pixabit.tcss"

    # Define key bindings
    BINDINGS = [
        ("q", "quit", "Quit"),  # Use built-in quit action
        ("ctrl+c", "quit", "Quit"),  # Standard Ctrl+C exit
        ("r", "refresh_data", "Refresh Data"),
        # Add more bindings as needed (e.g., focus switching, specific actions)
        # ("tab", "focus_next", "Focus Next"),
        # ("shift+tab", "focus_previous", "Focus Prev"),
    ]

    # Reactive variable to control loading state display (optional)
    show_loading: reactive[bool] = reactive(False, layout=True)

    # FUNC: __init__
    def __init__(self, **kwargs: Any):
        """Initialize Pixabit TUI App."""
        super().__init__(**kwargs)
        # Instantiate DataStore, passing the notification method
        # Use try-except to handle potential credential errors during API init within DataStore
        try:
            self.datastore = PixabitDataStore(
                app_notify_update=self.notify_data_refreshed
            )
        except Exception as e:
            # If DataStore init fails (e.g., bad creds), log and exit gracefully
            # Note: Textual might handle this better, but basic exit is safer
            print(f"FATAL: Failed to initialize PixabitDataStore: {e}")
            # Maybe show an error screen before exiting?
            # For now, just exit.
            import sys

            sys.exit(1)
        # Lock to prevent potential race conditions if refresh notifications are rapid
        self._refresh_notify_lock = asyncio.Lock()

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Compose the application's widget hierarchy."""
        yield Header()  # Standard Textual header
        # Main content area using grid layout defined in CSS
        yield Container(
            # Replace PlaceholderWidgets with actual widget classes once created
            StatsPanel("User Stats", id="stats-panel"),
            MainMenu("Main Menu", id="menu-panel"),
            ContentArea("Content Area", id="content-panel"),
            id="main-grid",  # ID for the main grid container
        )
        # Optional: Add a loading indicator, controlled by show_loading reactive var
        # yield LoadingIndicator(id="loading-indicator")
        yield Footer()  # Standard Textual footer (displays key bindings)

    # --- Lifecycle Methods ---

    # FUNC: on_mount
    async def on_mount(self) -> None:
        """Called once when the app is mounted in the terminal. Used for initial setup."""
        self.title = "Pixabit TUI"
        self.sub_title = "Habitica Assistant"
        # Trigger the initial data load in the background
        self.run_worker(
            self.initial_data_load, exclusive=True, group="data_load"
        )

    # --- Workers ---

    # FUNC: initial_data_load (Worker)
    async def initial_data_load(self) -> None:
        """Worker task for the initial data load."""
        self.log("Starting initial data load...")
        self.set_loading(True)  # Show loading indicator
        await self.datastore.refresh_all_data()
        # Notification callback `notify_data_refreshed` handles UI update & hiding loading
        self.log("Initial data load worker finished.")

    # FUNC: refresh_data_worker (Worker)
    async def refresh_data_worker(self) -> None:
        """Worker task for manual data refresh."""
        self.log("Starting manual data refresh...")
        self.set_loading(True)
        await self.datastore.refresh_all_data()
        # Notification callback handles UI update & hiding loading
        self.log("Manual data refresh worker finished.")

    # --- Data Refresh Notification ---

    # FUNC: notify_data_refreshed
    def notify_data_refreshed(self) -> None:
        """Callback passed to DataStore. Called *after* data refresh completes.
        Schedules UI updates to run on the main event loop thread.
        """
        # This method might be called from the DataStore's worker context.
        # We need to schedule the UI updates to run safely on the main thread.
        self.call_from_thread(self.update_ui_after_refresh)

    # FUNC: update_ui_after_refresh (Runs via call_from_thread)
    async def update_ui_after_refresh(self) -> None:
        """Safely updates UI components after data refresh notification."""
        # Use a lock to prevent multiple rapid UI updates if notifications overlap
        async with self._refresh_notify_lock:
            self.log("UI Update: Received data refresh notification.")
            self.set_loading(False)  # Hide loading indicator

            # Update specific widgets by querying them and calling their update methods
            # Example: Update Stats Panel
            try:
                # Query for the specific widget instance using its ID or class
                stats_panel = self.query_one(
                    StatsPanel
                )  # Or self.query_one("#stats-panel", StatsPanel)
                # Call a method on the widget to pass it the new data
                stats_panel.update_display(self.datastore.get_user_stats())
                self.log("UI Update: Stats panel updated.")
            except Exception as e:
                self.log(f"Error updating stats panel: {e}")

            # Example: Update Task List (if it exists and is mounted)
            try:
                # Replace TaskListWidget with your actual class name
                task_list_widget = self.query_one(
                    "#task-list-widget", TaskListWidget
                )
                task_list_widget.refresh_data()  # Widget pulls data from store
                self.log("UI Update: Task list updated.")
            except Exception:
                # Widget might not be mounted, ignore error or log subtly
                # self.log("Task list widget not found for refresh.")
                pass

            # Add updates for other active widgets (Challenges, Tags, MainMenu counts?)

        self.log("UI Update: Finished processing refresh notification.")

    # --- Utility Methods ---

    # FUNC: set_loading
    def set_loading(self, loading: bool) -> None:
        """Controls the visibility of a loading indicator (optional)."""
        self.show_loading = loading
        # If using LoadingIndicator widget:
        # try:
        #     self.query_one(LoadingIndicator).display = loading
        # except NoMatches:
        #     pass # Ignore if not found

    # --- Actions (Triggered by Key Bindings) ---

    # FUNC: action_refresh_data
    async def action_refresh_data(self) -> None:
        """Action bound to 'r' - Triggers a manual data refresh."""
        self.log("Action: Manual Refresh Data Triggered")
        if not self.datastore.is_refreshing.locked():
            # Run the refresh worker, ensure only one refresh runs at a time
            self.run_worker(
                self.refresh_data_worker, exclusive=True, group="data_load"
            )
        else:
            self.log("Refresh already in progress, skipping manual trigger.")
            # Optional: Show a notification to the user
            # self.notify("Refresh already in progress.", title="Info", severity="information")

    # --- Event Handlers (Respond to Widget Messages, etc.) ---

    # Example: Handling main menu selection
    # async def on_main_menu_selected(self, event: MainMenu.Selected) -> None:
    #     """Handles selection from the MainMenu widget."""
    #     selected_item = event.item_id # Assuming widget sends message with item identifier
    #     self.log(f"Menu selection: {selected_item}")
    #     content_area = self.query_one(ContentArea)
    #     await content_area.show_content(selected_item) # Tell content area to switch view

    # Example: Handling task scoring request from a TaskList widget
    # async def on_task_list_widget_score_task(self, message: TaskListWidget.ScoreTask) -> None:
    #     """Handles request from TaskListWidget to score a task."""
    #     task_id = message.task_id
    #     direction = message.direction
    #     self.log(f"App: Handling score request for task {task_id} ({direction})")
    #     self.set_loading(True)
    #     # Run the DataStore action in the background
    #     self.run_worker(
    #          self.datastore.score_task(task_id, direction),
    #          exclusive=True, # Prevent overlapping scores on same task?
    #          group=f"score_{task_id}" # Group related actions
    #     )
    #     # Callback handles hiding loading indicator after refresh

    # Add more event handlers (`on_...`) as widgets are developed and emit messages.


# SECTION: Main Entry Point (for running the TUI app)
# This would typically be called from your project's main script or entry point.
if __name__ == "__main__":
    app = PixabitTUIApp()
    app.run()
