# pixabit/tui/app.py

# --- REMOVE logging.basicConfig near the top ---
# import logging
# from rich.logging import RichHandler
# FORMAT = "%(message)s"
# logging.basicConfig(...)
# --- End Removal ---

# --- Keep other imports ---
import asyncio
from typing import Any, Type

from rich.text import Text  # Keep if using Text.from_markup
from textual import log  # Use textual's log
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static  # Removed RichLog for brevity

from pixabit.utils.display import console  # Keep if used elsewhere, otherwise remove

# --- Local Application Imports ---
try:
    from pixabit.tui.data_store import PixabitDataStore
    from pixabit.tui.widgets.placeholder import PlaceholderWidget as ContentArea
    from pixabit.tui.widgets.placeholder import PlaceholderWidget as MainMenu
    from pixabit.tui.widgets.stats_panel import StatsPanel

    # Import message definitions
    from .messages import DataRefreshed, UIMessage  # Adjust import path if needed
except ImportError as e:
    # Keep error handling
    import builtins

    builtins.print(f"FATAL ERROR: Could not import Pixabit TUI modules in app.py: {e}")
    import sys

    sys.exit(1)


# --- PixabitTUIApp Class ---
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

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        try:
            # Pass self (app instance) to DataStore
            self.datastore = PixabitDataStore(self)
        except Exception as e:
            print(f"FATAL: Failed to initialize PixabitDataStore: {e}")
            import sys

            sys.exit(1)
        self._refresh_notify_lock = asyncio.Lock()  # Keep for UI updates

    # --- compose ---
    def compose(self) -> ComposeResult:
        """Compose the application's widget hierarchy."""
        # Keep as is
        yield Header()
        yield Container(
            Vertical(
                StatsPanel(id="stats-panel"),
                MainMenu("Main Menu", id="menu-panel"),
                id="left-column",
            ),
            Vertical(
                ContentArea("Content Area", id="content-panel"),
                id="right-column",
            ),
            id="main-grid",
        )
        yield Footer()

    # --- on_mount ---
    async def on_mount(self) -> None:
        """Called once when the app is mounted. Used for initial setup."""
        # Keep as is
        log.info("App Mounted.")
        log.info("Starting initial data load worker...")
        self.title = "Pixabit TUI"
        self.sub_title = "Habitica Assistant"
        self.run_worker(self.initial_data_load, exclusive=True, group="data_load")

    # --- Workers ---
    async def initial_data_load(self) -> None:
        """Worker task for the initial data load."""
        # Keep as is
        log.info("Starting initial data load worker...")
        self.set_loading(True)
        await self.datastore.refresh_all_data()
        log.info("Initial data load worker finished.")

    async def refresh_data_worker(self) -> None:
        """Worker task for manual data refresh."""
        # Keep as is (including debug logs if helpful)
        log.info(">>> refresh_data_worker STARTED")
        log.info("Starting manual data refresh worker...")
        self.set_loading(True)  # Show loading for manual refresh too
        try:
            await self.datastore.refresh_all_data()
        except Exception as e:
            log.exception(">>> EXCEPTION in refresh_data_worker")
        finally:
            log.info(">>> refresh_data_worker FINISHED")
        log.info("Manual data refresh worker finished.")

    # --- Event Handlers ---
    async def on_data_refreshed(self, event: DataRefreshed) -> None:
        """Handles the DataRefreshed message from the DataStore."""
        # Keep as is
        log.info("UI Update: Received DataRefreshed event.")
        await self.update_ui_after_refresh()
        self.notify("Data refresh complete!", title="Refreshed", severity="information", timeout=4)
        log.info(">>> 'Data refresh complete!' notification called.")

    def on_ui_message(self, event: UIMessage) -> None:
        """Handles UIMessage events for notifications."""
        # Keep as is
        log.info(f">>> Received UIMessage: Title='{event.title}', Severity='{event.severity}', Text='{event.text}'")
        self.notify(event.text, title=event.title, severity=event.severity)
        log.info(">>> Called self.notify inside on_ui_message.")

    # --- UI Update Method ---
    async def update_ui_after_refresh(self) -> None:
        """Safely updates UI components after data refresh."""
        # Keep as is, ensure Text.from_markup is used for Static.update if needed
        # Consider removing the lock here unless you see specific race conditions
        # async with self._refresh_notify_lock:
        log.info("UI Update: Updating widgets...")  # Changed log message slightly
        self.set_loading(False)

        stats_data = self.datastore.get_user_stats()
        log.info(f"UI Update: Stats data received: {stats_data}")

        try:
            stats_panel = self.query_one(StatsPanel)
            stats_panel.update_display(stats_data)
            log.info("UI Update: Stats panel update called.")
        except Exception as e:
            log.error(f"Error updating stats panel: {e}")

        # ... update other widgets (e.g., TaskListWidget) ...

        log.info("UI Update: Finished updating widgets.")

    # --- Utility Methods ---
    def set_loading(self, loading: bool) -> None:
        """Controls the visibility of a loading indicator (optional)."""
        # Keep as is
        self.show_loading = loading

    # --- Actions ---
    async def action_refresh_data(self) -> None:
        """Action bound to 'r' - Triggers a manual data refresh."""
        log.info("Action: Manual Refresh Data Triggered")
        # The exclusive=True and group="data_load" on run_worker
        # will prevent multiple *workers* from starting if one is already
        # running in that group. DataStore's internal lock prevents
        # concurrent *execution* within refresh_all_data.
        # No need to check the lock here explicitly.
        log.info("Action Refresh: Attempting to start refresh worker...")
        # --- FIX: Add the missing run_worker call ---
        self.run_worker(self.refresh_data_worker, name="manual_refresh", exclusive=True, group="data_load")  # Pass the METHOD to run  # Optional: Name the worker  # Prevent multiple manual refreshes via worker  # Use same group as initial load
        # --- End Fix ---

    async def action_toggle_sleep(self) -> None:
        """Action bound to 's' - Toggles user sleep status."""
        log.info("Action: Toggle Sleep Triggered")
        # Check DataStore's internal lock to prevent action during refresh
        if self.datastore.is_refreshing.locked():
            self.notify("Cannot toggle sleep: Refresh in progress.", severity="warning")
            log.info(">>> Toggle sleep blocked by active refresh lock.")
            return  # Stop the action

        # Lock is free, proceed
        current_status = self.datastore.user_stats_dict.get("sleeping", None)
        action_desc = "Wake up" if current_status else "Go to sleep"
        self.notify(f"Attempting to {action_desc}...", title="Action")
        log.info(">>> 'Attempting to...' notification call finished.")

        # Run the worker for the toggle action
        self.run_worker(
            self.datastore.toggle_sleep(),  # Pass the coroutine object directly
            name="toggle_sleep_action",
            exclusive=True,  # Prevent multiple simultaneous toggles
            group="user_action",  # Use a different group for user actions
        )

    # ... other event handlers ...


# --- Main Entry Point ---
if __name__ == "__main__":
    app = PixabitTUIApp()
    app.run()
