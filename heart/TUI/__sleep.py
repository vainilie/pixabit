from heart.basis.__get_data import get_user_stats  # Import API logic
from heart.basis.__get_data import toggle_sleep_status
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static, Switch


class SwitchApp(Horizontal):
    """
    A widget to display and toggle the sleeping status of the user.
    """

    DEFAULT_CSS = """Screen {
    align: center middle;
}

Horizontal {
    height: auto;
    width: auto;
    content-align: center middle;
}

Switch {
    height: 1;
    width: 3;
}

Static {
    height: 1;
    width: auto;
    content-align: center middle;
}
"""

    sleep = reactive(False)  # Tracks sleep status (initially False)

    def __init__(self):
        super().__init__()
        self.switch = None  # Placeholder for the Switch widget

    def compose(self) -> ComposeResult:
        """Compose the UI elements."""
        yield Static("[b]Sleeping Status", classes="label")
        self.switch = Switch(value=self.sleep, classes="container", id="sleep-switch")
        yield Horizontal(
            Static("Sleeping:", classes="label"),
            self.switch,
        )

    def on_mount(self):
        """Called when the widget is mounted."""
        self.call_later(self.fetch_stats)

    async def fetch_stats(self):
        """Fetch stats from the Habitica API asynchronously."""
        try:
            data = await get_user_stats()
            self.sleep = data["sleep"]  # Update reactive state
            if self.switch:
                self.switch.value = self.sleep  # Sync switch with state
        except Exception as e:
            self.notify(
                f"Error fetching sleeping status: {str(e)}",
                title="Error",
                severity="error",
            )

    async def send_sleep_toggle(self):
        """Send the updated sleep status to the API asynchronously."""
        try:
            await toggle_sleep_status()  # Send the new status
        except Exception as e:
            self.notify(
                f"Error toggling sleep status: {str(e)}",
                title="Error",
                severity="error",
            )

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle the switch toggle event."""
        if event.switch == self.switch:
            self.sleep = self.switch.value  # Update reactive state
            self.call_later(self.send_sleep_toggle)  # Schedule API update


if __name__ == "__main__":

    class TestApp(App):
        """Main application to test the SwitchApp widget."""

        async def on_mount(self):
            """Mount the widget on the screen."""
            widget = SwitchApp()
            await self.mount(widget)

    app = TestApp()
    app.run()
