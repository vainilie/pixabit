from textual import events
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class HelpModal(ModalScreen):
    """Modal screen to show keyboard help."""

    def compose(self):
        yield Vertical(
            Static("**Keyboard Shortcuts**", id="help-title"),
            *(Static(f"[b]{key}[/b]: {desc}", id="help-item") for key, _, desc in self.app.get_bindings_info()),
            id="help-list",
        )

    def on_key(self, event: events.Key) -> None:
        """Close help on Escape."""
        if event.key == "escape":
            self.dismiss()
