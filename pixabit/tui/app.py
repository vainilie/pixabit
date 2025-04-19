# pixabit/tui/app.py (Modifications)
# SECTION: IMPORTS
import asyncio
import logging
from typing import Any, Dict, Optional, Type

from rich.console import Console
from rich.logging import RichHandler
from rich.text import Text
from textual import log
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical  # Keep Container
from textual.message import (
    Message,
)  # Import base Message class if defining custom ones
from textual.reactive import reactive
from textual.widgets import Footer, Header, RichLog, Static  # Keep Core widgets

from pixabit.utils.display import console
from pixabit.utils.message import DataRefreshed, UIMessage

FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)])

# --- Local Application Imports ---
try:
    from pixabit.tui.data_store import PixabitDataStore
    from pixabit.tui.widgets.placeholder import PlaceholderWidget as ContentArea

    # Import Placeholders for others until they are created
    from pixabit.tui.widgets.placeholder import PlaceholderWidget as MainMenu

    # Import the NEW StatsPanel widget
    from pixabit.tui.widgets.stats_panel import StatsPanel
except ImportError as e:
    import builtins

    builtins.print(f"FATAL ERROR: Could not import Pixabit TUI modules in app.py: {e}")
    import sys

    sys.exit(1)

# messages.py (or define within app.py)


# Add other messages as needed (e.g., for errors, specific updates)
# SECTION: PixabitTUIApp Class
# KLASS: PixabitTUIApp
class PixabitTUIApp(App[None]):
    """The main Textual TUI Application for Pixabit."""

    CSS_PATH = "pixabit.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("r", "refresh_data", "Refresh Data"),
        ("s", "toggle_sleep", "Toggle Sleep"),
    ]

    show_loading: reactive[bool] = reactive(True, layout=True)

    # FUNC: __init__ (Keep as refactored previously)
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        try:
            self.datastore = PixabitDataStore(self)
        except Exception as e:
            print(f"FATAL: Failed to initialize PixabitDataStore: {e}")
            import sys

            sys.exit(1)
        self._refresh_notify_lock = asyncio.Lock()

    # FUNC: compose (Use the new StatsPanel)
    def compose(self) -> ComposeResult:
        """Compose the application's widget hierarchy."""
        yield Header()
        yield Container(  # Outer container, ID #main-grid
            # --- Left Column ---
            Vertical(
                StatsPanel(id="stats-panel"),  # ID used only for internal styling now
                MainMenu("Main Menu", id="menu-panel"),  # Placeholder
                id="left-column",  # ID for the Vertical container
            ),
            # --- Right Column ---
            Vertical(
                ContentArea("Content Area", id="content-panel"),  # Placeholder
                id="right-column",  # ID for the Vertical container
            ),
            id="main-grid",  # ID for the outer container
        )
        yield Footer()

    # FUNC: on_mount (Keep as refactored previously)
    async def on_mount(self) -> None:
        """Called once when the app is mounted. Used for initial setup."""
        log.info("App Mounted.")  # Basic print check
        log.info("Starting initial data load...")  # Textual log

        self.title = "Pixabit TUI"
        self.sub_title = "Habitica Assistant"
        self.run_worker(self.initial_data_load, exclusive=True, group="data_load")

    # --- Workers ---

    # FUNC: initial_data_load (Worker)
    async def initial_data_load(self) -> None:
        """Worker task for the initial data load using run_in_thread."""
        log.info("Starting initial data load worker...")
        self.set_loading(True)
        await self.datastore.refresh_all_data()  # This will now post DataRefreshed
        log.info("Initial data load worker finished.")  # Note: UI update happens via event now

    # FUNC: refresh_data_worker (Worker - Using run_in_thread)
    async def refresh_data_worker(self) -> None:
        """Worker task for manual data refresh using run_in_thread."""
        log.info(">>> refresh_data_worker STARTED")  # ADD THIS
        log.info("Starting manual data refresh worker...")
        self.set_loading(True)
        try:
            await self.datastore.refresh_all_data()  # This will now post DataRefreshed
        # Notification callback handles UI update & hiding loading
        except Exception as e:
            log.exception(">>> EXCEPTION in refresh_data_worker")  # ADD THIS
        finally:
            # Ensure loading is set false even if refresh fails partially
            # Note: UI update should still happen via DataRefreshed event
            # self.set_loading(False) # Maybe handled by update_ui_after_refresh now? Check logic.
            log.info(">>> refresh_data_worker FINISHED")  # ADD THIS

        log.info("Manual data refresh worker finished.")

    # --- Data Refresh Notification ---

    # FUNC: notify_data_refreshed
    # def notify_data_refreshed(self) -> None:
    #     """Callback passed to DataStore. Called *after* data refresh completes. Schedules UI updates to run on the main event loop thread."""
    #     # This method might be called from the DataStore's worker context.
    #     # We need to schedule the UI updates to run safely on the main thread.
    #     self.call_from_thread(self.update_ui_after_refresh)

    # FUNC: Event Handler Method ---

    async def on_data_refreshed(self, event: DataRefreshed) -> None:
        """Handles the DataRefreshed message from the DataStore."""
        log.info("UI Update: Received DataRefreshed event.")

        # Call the UI update method directly - this handler runs on the main thread
        await self.update_ui_after_refresh()  # Make sure it's async if needed
        self.notify("Data refresh complete!", title="Refreshed", severity="information", timeout=4)  # timeout is optional
        log.info(">>> 'Data refresh complete!' notification called.")

    # FUNC: UI message
    # Optional: Handler for UI messages
    def on_ui_message(self, event: UIMessage) -> None:
        """Handles UIMessage events for notifications."""
        log.info(f">>> Received UIMessage: Title='{event.title}', Severity='{event.severity}', Text='{event.text}'")

        self.notify(event.text, title=event.title, severity=event.severity)
        log.info(">>> Called self.notify inside on_ui_message.")

    # FUNC: update_ui_after_refresh (Modify to update StatsPanel)
    async def update_ui_after_refresh(self) -> None:
        """Safely updates UI components after data refresh notification."""
        async with self._refresh_notify_lock:
            log.info("UI Update: Received data refresh notification.")
            self.set_loading(False)  # Hide loading indicator

            stats_data = self.datastore.get_user_stats()
            log.info(f"UI Update: Stats data received: {stats_data}")

            # Update specific widgets by querying them and calling their update methods
            # Example: Update Stats Panel
            try:
                # Query for the specific widget instance using its ID or class
                stats_panel = self.query_one(StatsPanel)  # Or self.query_one("#stats-panel", StatsPanel)
                # Call a method on the widget to pass it the new data
                stats_panel.update_display(stats_data)
                log.info("UI Update: Stats panel update called.")
            except Exception as e:
                log.error(f"Error updating stats panel: {e}")

            # Example: Update Task List (if it exists and is mounted)
            try:
                # Replace TaskListWidget with your actual class name
                task_list_widget = self.query_one("#task-list-widget", TaskListWidget)
                task_list_widget.refresh_data()  # Widget pulls data from store
                log.info("UI Update: Task list updated.")
            except Exception:
                # Widget might not be mounted, ignore error or log subtly
                # log("Task list widget not found for refresh.")
                pass

            # Add updates for other active widgets (Challenges, Tags, MainMenu counts?)

        log.info("UI Update: Finished updating widgets.")

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

    # FUNC: action_refresh_data (Keep as before)

    async def action_refresh_data(self) -> None:
        """Action bound to 'r' - Triggers a manual data refresh."""
        log.info("Action: Manual Refresh Data Triggered")
        is_locked = self.datastore.is_refreshing.locked()  # Check lock status
        log.warning(f"Action Refresh: DataStore lock is currently {'LOCKED' if is_locked else 'UNLOCKED'}.")  # Log status
        if not is_locked:
            log.info("Action Refresh: Lock is free, starting worker...")  # Log starting worker
        self.run_worker(self.refresh_data_worker, name="manual_refresh", exclusive=True, group="data_load")  # Pass the METHOD to run  # Optional: Name the worker  # Prevent multiple manual refreshes via worker  # Use same group as initial load

    # FUNC: action_toggle_sleep (Example action implementation)
    async def action_toggle_sleep(self) -> None:
        """Action bound to 's' - Toggles user sleep status."""
        log.info("Action: Toggle Sleep Triggered")
        if self.datastore.is_refreshing.locked():
            self.notify("Cannot toggle sleep: Refresh in progress.", severity="warning")
            log.info(">>> Toggle sleep blocked by active refresh lock.")
            return  # Stop the action
        current_status = self.datastore.user_stats_dict.get("sleeping", None)
        action_desc = "Wake up" if current_status else "Go to sleep"
        self.notify(f"Attempting to {action_desc}...", title="Action")
        log.info(">>> 'Attempting to...' notification call finished.")  # ADD THIS LOG

        # Run the worker for the toggle action
        self.run_worker(
            self.datastore.toggle_sleep(),  # Call the datastore action
            exclusive=True,
            group="user_action",
        )
        # else:

    # --- Event Handlers (Placeholders for now) ---
    # async def on_main_menu_selected(self, event: MainMenu.Selected) -> None: ...
    # async def on_task_list_widget_score_task(self, message: TaskListWidget.ScoreTask) -> None: ...


# SECTION: Main Entry Point
if __name__ == "__main__":
    app = PixabitTUIApp()
    app.run()
