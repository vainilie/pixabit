# pixabit/tui/app.py (Modifications)
# SECTION: IMPORTS
import asyncio
import logging
from typing import Any, Dict, Optional, Type

from rich.console import Console
from rich.logging import RichHandler
from rich.text import Text
from textual import events, log
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical  # Keep Container
from textual.message import (
    Message,
)  # Import base Message class if defining custom ones
from textual.reactive import reactive
from textual.widgets import (  # Keep Core widgets
    Footer,
    Header,
    Static,
    # RichLog, # Consider removing if textual.log is sufficient
    # Static, # Unused in this snippet
    TabbedContent,
    TabPane,
)

from pixabit.utils.display import console
from pixabit.utils.message import DataRefreshed, UIMessage

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
)  # Keep for rich tracebacks

from pixabit.tui.widgets.tasks_panel import (
    ScoreTaskRequest,
    TaskListWidget,
    ViewTaskDetailsRequest,
)

# --- Local Application Imports ---
try:
    from pixabit.tui.data_store import PixabitDataStore
    from pixabit.tui.widgets.placeholder import PlaceholderWidget

    # Alias 'ContentArea' is not used below, consider removing or using it.
    # from pixabit.tui.widgets.placeholder import PlaceholderWidget as ContentArea
    # Import Placeholders for others until they are created
    # Alias 'MainMenu' is not used below, consider removing or using it.
    # from pixabit.tui.widgets.placeholder import PlaceholderWidget as MainMenu
    # Import the NEW StatsPanel widget
    from pixabit.tui.widgets.stats_panel import StatsPanel
    from pixabit.tui.widgets.tabs_panel import TabPanel
    from pixabit.tui.widgets.tasks_panel import (
        ScoreTaskRequest,
        TaskListWidget,
        ViewTaskDetailsRequest,
    )
except ImportError as e:
    import builtins

    builtins.print(f"FATAL ERROR: Could not import Pixabit TUI modules in app.py: {e}")
    import sys

    sys.exit(1)


# Add other messages as needed (e.g., for errors, specific updates)
# SECTION: PixabitTUIApp Class
# KLASS: PixabitTUIApp
class PixabitTUIApp(App[None]):
    """The main Textual TUI Application for Pixabit."""

    CSS_PATH = "pixabit.tcss"
    # Adjust bindings - remove menu-specific ones if any, maybe add tab switching?
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("r", "refresh_data", "Refresh Data"),
        ("s", "toggle_sleep", "Toggle Sleep"),
        # Example: ("ctrl+t", "app.action_next_tab", "Next Tab"),
        # Example: ("ctrl+shift+t", "app.action_previous_tab", "Prev Tab"),
    ]

    show_loading: reactive[bool] = reactive(True, layout=True)

    # FUNC: __init__ (Mantenido como estaba en tu versión original)
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        try:
            self.datastore = PixabitDataStore(self)
            # Se podrían añadir logs aquí si se quisiera verificar
            log.info(">>> PixabitDataStore initialized successfully in __init__.")
        except Exception as e:
            # Using standard logging before Textual's log might be fully ready
            logging.fatal(f"FATAL: Failed to initialize PixabitDataStore: {e}")
            import sys

            sys.exit(1)
        self._refresh_notify_lock = asyncio.Lock()
        # logging.info(f">>> __init__ finished. hasattr(self, 'datastore'): {hasattr(self, 'datastore')}")

    # FUNC: compose (Use the new StatsPanel)
    def compose(self) -> ComposeResult:
        """Compose the application's widget hierarchy using yield."""
        yield Header()
        yield StatsPanel(id="stats-panel")
        yield TabPanel(id="main-tabs")
        yield Footer()

    # FUNC: on_mount (Keep as refactored previously)
    async def on_mount(self) -> None:
        """Called once when the app is mounted. Used for initial setup."""
        log.info("App Mounted.")  # Use textual.log
        log.info("Starting initial data load...")

        self.title = "Pixabit TUI"
        self.sub_title = "Habitica Assistant"

        # Trigger initial data load AFTER mounting panes
        self.run_worker(self.initial_data_load, exclusive=True, group="data_load")

    # ... (rest of App methods) ...
    # --- Workers ---

    # FUNC: initial_data_load (Worker)
    async def initial_data_load(self) -> None:
        """Worker task for the initial data load using run_in_thread."""
        log.info("Starting initial data load worker...")
        self.set_loading(True)
        # DataStore should handle its own errors and potentially post a UIMessage
        await self.datastore.refresh_all_data()  # This will now post DataRefreshed
        log.info("Initial data load worker finished.")  # UI update happens via event handler

    # FUNC: refresh_data_worker (Worker - Using run_in_thread)
    async def refresh_data_worker(self) -> None:
        """Worker task for manual data refresh using run_in_thread."""
        log.info(">>> refresh_data_worker STARTED")
        log.info("Starting manual data refresh worker...")
        self.set_loading(True)
        try:
            await self.datastore.refresh_all_data()  # This will post DataRefreshed on success/partial success
        except Exception as e:
            # Log the exception details using textual's logger
            log.exception(">>> EXCEPTION in refresh_data_worker")
            # Optionally notify the user about the failure
            self.post_message(
                UIMessage("Refresh Failed", f"Error during data refresh: {e}", "error")
            )
        finally:
            # set_loading(False) is handled by update_ui_after_refresh via the event
            log.info(">>> refresh_data_worker FINISHED")

    # --- Data Refresh Notification ---

    # FUNC: Event Handler Method ---

    async def on_data_refreshed(self, event: DataRefreshed) -> None:
        """Handles the DataRefreshed message from the DataStore."""
        log.info("UI Update: Received DataRefreshed event.")

        # Call the UI update method directly - this handler runs on the main thread
        await self.update_ui_after_refresh()  # Make sure it's async if needed

        # Check if the refresh was successful (assuming DataRefreshed carries status)
        # Example: if event.success:
        self.notify("Data refresh complete!", title="Refreshed", severity="information", timeout=4)
        log.info(">>> 'Data refresh complete!' notification called.")
        # else:
        #    self.notify("Data refresh finished with errors.", title="Refreshed", severity="warning", timeout=4)
        #    log.warning(">>> Data refresh finished, but DataRefreshed indicated issues.")

    # FUNC: UI message
    # Optional: Handler for UI messages
    def on_ui_message(self, event: UIMessage) -> None:
        """Handles UIMessage events for notifications."""
        log.info(
            f">>> Received UIMessage: Title='{event.title}', Severity='{event.severity}', Text='{event.text}'"
        )
        self.notify(event.text, title=event.title, severity=event.severity)
        log.info(">>> Called self.notify inside on_ui_message.")

    # FUNC: update_ui_after_refresh (Modify to update StatsPanel)
    async def update_ui_after_refresh(self) -> None:
        """Safely updates UI components after data refresh notification."""
        # This lock might be less critical if workers are exclusive, but good practice
        async with self._refresh_notify_lock:
            log.info("UI Update: Acquiring lock and starting UI update.")
            self.set_loading(False)  # Hide loading indicator FIRST

            stats_data = self.datastore.get_user_stats()  # Get potentially updated data
            log.info(f"UI Update: Stats data received from store: {stats_data}")

            # Update specific widgets by querying them and calling their update methods
            # Example: Update Stats Panel
            try:
                stats_panel = self.query_one(StatsPanel)  # Query by class is fine if only one
                # latest_stats = self.datastore.get_user_stats() # Already fetched above
                stats_panel.update_display(stats_data)
                log.info("UI Update: Stats panel updated.")
            except Exception as e:
                log.error(f"Error updating stats panel: {e}")

        # --- Refresh Active Content Widget INSIDE TabPanel ---
        try:
            main_tabs = self.query_one("#main-tabs", TabbedContent)
            active_tab_pane = main_tabs.active_pane
            # Si la pestaña activa es la de tareas O si quieres que siempre se refresque
            if active_tab_pane and active_tab_pane.children:
                task_list_widget = active_tab_pane.query_one(TaskListWidget)
                self.run_worker(task_list_widget.load_or_refresh_data)

        except Exception as e:
            log.error(f"Error refreshing active tab content: {e}")  # Error gets logged here
        log.info("UI Update: Finished processing refresh notification.")
        # Lock released automatically by 'async with'

    # --- Utility Methods ---

    # FUNC: set_loading
    def set_loading(self, loading: bool) -> None:
        """Controls the visibility of a loading indicator (optional)."""
        # This reactive variable might trigger CSS changes or be watched elsewhere
        self.show_loading = loading
        log.debug(f"Loading state set to: {loading}")
        # Example if using Textual's LoadingIndicator widget:
        # try:
        #     self.query_one(LoadingIndicator).display = loading
        # except NoMatches:
        #     pass # Ignore if not found

    # --- Actions (Triggered by Key Bindings) ---

    # FUNC: action_refresh_data (Keep as before)
    async def action_refresh_data(self) -> None:
        """Action bound to 'r' - Triggers a manual data refresh."""
        log.info("Action: Manual Refresh Data Triggered")
        # Checking the DataStore's internal lock state might be complex; rely on exclusive worker group.
        # is_locked = self.datastore.is_refreshing.locked() # This depends on DataStore implementation details
        # log.info(f"Action Refresh: DataStore lock check omitted, relying on exclusive worker.")

        # Use exclusive=True to prevent multiple refreshes running concurrently
        self.run_worker(
            self.refresh_data_worker, name="manual_refresh", exclusive=True, group="data_load"
        )  # Pass the method itself  # Ensure worker groups match if exclusivity is desired across types

    async def on_task_list_widget_score_task_request(self, message: ScoreTaskRequest) -> None:
        """Handles request from TaskListWidget to score a task."""
        log(f"App received score request: Task={message.task_id}, Dir={message.direction}")
        self.set_loading(True)
        self.run_worker(
            self.datastore.score_task(message.task_id, message.direction),
            group=f"score_task_{message.task_id}",
        )
        # UI updates after refresh notification

    # FUNC: action_toggle_sleep (Example action implementation)
    async def action_toggle_sleep(self) -> None:
        """Action bound to 's' - Toggles user sleep status."""
        log.info("Action: Toggle Sleep Triggered")

        # It's better to check if *any* critical action (like refresh) is running
        # A simple way is to check if a worker in a specific group is running
        if self.is_worker_running(
            "data_load"
        ):  # Check if any worker in 'data_load' group is active
            self.notify("Action blocked: Data refresh in progress.", severity="warning")
            log.warning("Toggle sleep blocked by active 'data_load' worker.")
            return

        # Optional: Check if another 'user_action' is already running
        if self.is_worker_running("user_action"):
            self.notify("Action blocked: Another user action is in progress.", severity="warning")
            log.warning("Toggle sleep blocked by active 'user_action' worker.")
            return

        current_status = self.datastore.user_stats_dict.get("sleeping", None)
        if current_status is None:
            self.notify("Cannot determine sleep status.", severity="error")
            log.error("Could not get sleep status from datastore dictionary.")
            return

        action_desc = "Wake up" if current_status else "Go to sleep"
        self.notify(f"Attempting to {action_desc}...", title="Action")
        log.info(f">>> Attempting to {action_desc} notification sent.")

        # --- *** CORRECTION HERE *** ---
        # Pass the METHOD REFERENCE, not the result of calling the method.
        self.run_worker(
            self.datastore.toggle_sleep,  # Pass the method without calling it ()
            exclusive=True,  # Prevent multiple toggle attempts at once
            group="user_action",  # Assign a group for user-initiated actions
            # Add error handling/notification upon completion if needed (e.g., via another message)
        )
        # Note: The result/success of toggle_sleep should ideally trigger a DataRefreshed
        # or a specific UIMessage so the UI updates accordingly.

    # FUNC: TABS

    # etc.

    # --- Event Handlers (Placeholders for now) ---
    # async def on_main_menu_selected(self, event: MainMenu.Selected) -> None: ...
    # async def on_task_list_widget_score_task(self, message: TaskListWidget.ScoreTask) -> None: ...

    # --- ADD Message Handler for ViewTaskDetailsRequest (Placeholder) ---
    async def on_task_list_widget_view_task_details_request(
        self, message: ViewTaskDetailsRequest
    ) -> None:
        """Handles request to view task details (placeholder)."""
        log(f"App received view details request for task: {message.task_id}")
        self.notify(f"Details view for {message.task_id} not yet implemented.", severity="warning")
        # Later: Mount a TaskDetail screen/widget here

    # ... (rest of App methods) ...


# SECTION: Main Entry Point
if __name__ == "__main__":
    app = PixabitTUIApp()
    app.run()
