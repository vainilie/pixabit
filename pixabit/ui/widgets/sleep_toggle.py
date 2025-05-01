# pixabit/ui/widgets/sleep_toggle.py
import asyncio
from typing import Any, Callable, Dict, Optional

from textual.containers import Horizontal
from textual.widgets import Label, Static, Switch

from pixabit.api.client import HabiticaClient
from pixabit.helpers._logger import log
from pixabit.models.user import User


class SleepToggle(Horizontal):
    """Widget for toggling the user's sleep mode in Habitica."""

    DEFAULT_CSS = """
    SleepToggle {
        height: auto;
        padding: 1;
        margin-top: 1;
        background: $panel;
        border: round $accent;
        align: center middle;
    }

    SleepToggle #sleep-label {
        margin-right: 0;
    }
    """

    def __init__(
        self,
        api_client: Optional[HabiticaClient] = None,
        status_update_callback: Optional[Callable[[str, str], None]] = None,
        on_data_changed: Optional[Callable[[Dict[str, Any]], Any]] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        """Initialize the SleepToggle widget.

        Args:
            api_client: HabiticaClient for API calls
            status_update_callback: Callback function to update status messages
            on_data_changed: Callback called when data changes to notify parent components
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.api_client = api_client
        self.status_update_callback = status_update_callback
        self.on_data_changed = on_data_changed

        # Flag to prevent toggle loop
        self._updating_ui = False
        # Flag to track the last known sleep state
        self._last_sleep_state = False

    def compose(self):
        """Create child widgets."""
        yield Label("Sleep Mode:", id="sleep-label")
        yield Switch(value=False, id="sleep-toggle")

    def update_sleep_state(self, user: Optional[User]) -> None:
        """Update the switch state based on the user's sleep state.

        Args:
            user: User object containing sleep state
        """
        self._updating_ui = True
        try:
            sleep_toggle = self.query_one("#sleep-toggle", Switch)

            if user is None:
                sleep_toggle.disabled = True
                return

            try:
                is_sleeping = getattr(user, "is_sleeping", False)
                sleep_toggle.value = is_sleeping
                sleep_toggle.disabled = False
                self._last_sleep_state = is_sleeping
            except Exception as e:
                log.error(f"Error updating sleep toggle: {e}")
                sleep_toggle.disabled = True
        finally:
            self._updating_ui = False

    async def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch toggle events."""
        if event.switch.id == "sleep-toggle" and not self._updating_ui:
            # Only proceed if it's a genuine user action and state has changed
            if event.value != self._last_sleep_state:
                await self._toggle_sleep(event.value)

    async def _toggle_sleep(self, sleep_value: bool) -> None:
        """Toggle user sleep state."""
        if not self.api_client:
            self._update_status("Error: API client not initialized", "error")
            return

        self._update_status("Toggling sleep state...", "loading")

        try:
            # Call API to toggle sleep
            # The API call returns the CURRENT sleep state after toggle, not a success flag
            new_sleep_state = await self.api_client.toggle_user_sleep()
            log.info(f"API returned sleep state: {new_sleep_state}")

            # Check if the toggle was successful by comparing with desired state
            if new_sleep_state == sleep_value:
                self._update_status("Sleep state changed successfully", "success")

                # Update our cached sleep state to match the API response
                self._last_sleep_state = new_sleep_state

                # Call the callback to notify the parent component using new data_changed pattern
                if self.on_data_changed:
                    await self.on_data_changed({"action": "sleep_toggled", "new_value": new_sleep_state})
            else:
                self._update_status("Failed to toggle sleep state", "error")
                # Reset switch to match the actual state returned by API
                self._reset_switch_value(new_sleep_state)

        except Exception as e:
            self._update_status(f"Error: {e}", "error")
            # Reset switch to previous state since we don't know the current state
            self._reset_switch_value(not sleep_value)

    def _reset_switch_value(self, value: bool) -> None:
        """Reset the switch value without triggering events."""
        self._updating_ui = True
        try:
            switch = self.query_one("#sleep-toggle", Switch)
            switch.value = value
        finally:
            self._updating_ui = False

    def _update_status(self, message: str, status_class: str = "") -> None:
        """Updates the status via callback."""
        if self.status_update_callback:
            self.status_update_callback(message, status_class)
