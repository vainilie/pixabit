# previous_tui_files/sleep.py (LEGACY TUI WIDGET ATTEMPT)

# SECTION: MODULE DOCSTRING
"""LEGACY: Previous attempt at a sleep toggle widget for Textual.

Contained logic for fetching state and toggling sleep directly via imported API functions.
This logic should now reside in PixabitDataStore. The Switch widget and basic layout
might be reusable, but event handling needs modification.
"""

# SECTION: IMPORTS
from typing import Any, Dict, Optional  # Added Optional, Dict, Any

# Textual Imports
from textual.app import (
    App,
    ComposeResult,
)  # Keep App/ComposeResult for example runner
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static, Switch

# Local Imports (These are from the OLD structure - likely invalid now)
# from heart.basis.__get_data import get_user_stats # Old API call
# from heart.basis.__get_data import toggle_sleep_status # Old API call


# SECTION: LEGACY WIDGET CLASS
# KLASS: SwitchApp (Legacy Widget - Needs Rename)
class SleepToggleWidget(Horizontal):  # Renamed class for clarity
    """LEGACY WIDGET: Displays and toggles the user's sleep status.

    NOTE: Contains direct API fetching/updating logic which is DEPRECATED.
    Should receive status from DataStore and trigger actions via App messages.
    """

    DEFAULT_CSS = """
    SleepToggleWidget { /* Renamed selector */
        height: auto;
        width: auto;
        border: round $accent; /* Example border */
        padding: 0 1;
        /* align: center middle; */ /* Center content */
    }
    SleepToggleWidget > Static { /* Target direct children */
        height: 1;
        width: auto;
        margin-right: 1;
        /* content-align: center middle; */ /* Align text vertically */
    }
    SleepToggleWidget > Switch { /* Target direct children */
        height: 1;
        width: 3;
    }
    """

    # Reactive state for sleep status (potentially reusable)
    _sleep_status: reactive[bool] = reactive(
        False, init=False
    )  # Don't init until data received

    # Store reference to the switch
    _switch_widget: Optional[Switch] = None

    # FUNC: update_display (NEW - Required for new architecture)
    def update_display(self, sleep_status: Optional[bool]) -> None:
        """Updates the widget's display based on data from the DataStore.

        Args:
            sleep_status: The current sleep status (True/False) or None if unknown.
        """
        if sleep_status is None:
            # Handle unknown state (e.g., disable switch, show placeholder)
            self._sleep_status = False  # Default internal state
            if self._switch_widget:
                self._switch_widget.disabled = True
                self._switch_widget.value = False
            self.query_one("#sleep-label", Static).update(
                "Sleep: [dim]Unknown[/]"
            )
            self.log.warning("Sleep widget received None status.")
        else:
            # Update internal state and sync the switch widget
            self._sleep_status = sleep_status
            if self._switch_widget:
                self._switch_widget.disabled = False
                # Check if update is needed to avoid recursion if watch triggers change
                if self._switch_widget.value != self._sleep_status:
                    self._switch_widget.value = self._sleep_status
            self.query_one("#sleep-label", Static).update("Sleep:")
            self.log.info(f"Sleep widget updated to: {self._sleep_status}")

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Compose the UI elements."""
        yield Static("Sleep:", id="sleep-label")
        # Store the switch instance when created
        self._switch_widget = Switch(
            value=self._sleep_status, disabled=True, id="sleep-switch"
        )
        yield self._switch_widget

    # FUNC: on_mount (Should not fetch data)
    # def on_mount(self) -> None:
    # """DEPRECATED: Called when the widget is mounted."""
    # Initial update should happen via App's notify_data_refreshed

    # Watcher for internal state change (optional, could update label here)
    # def watch__sleep_status(self, value: bool) -> None:
    #     if self._switch_widget and self._switch_widget.value != value:
    #          self._switch_widget.value = value # Sync switch if state changes externally

    # Event handler for the switch changing *by user interaction*
    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle the switch toggle event initiated by the user."""
        # Ensure this event is from *our* switch
        if event.switch.id == "sleep-switch":
            new_value = event.value
            # Prevent triggering action if the change came from update_display
            if new_value != self._sleep_status:
                self.log(f"Sleep switch toggled by user to: {new_value}")
                # Update internal state immediately for visual feedback
                self._sleep_status = new_value
                # Post a message to the App to trigger the actual API call
                # Define a message class (e.g., in this file or a messages.py)
                # class ToggleSleep(Message): pass
                # self.post_message(self.ToggleSleep())
                self.app.action_toggle_sleep()  # Or call app action directly if simpler

    # DEPRECATED methods that called API directly
    # async def fetch_stats(self): ...
    # async def send_sleep_toggle(self): ...
