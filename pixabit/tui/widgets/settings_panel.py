# settings_panel.py
from textual import log
from textual.app import ComposeResult
from textual.widgets import Static


class SettingsPanel(Static):
    """A panel showing settings content"""

    def compose(self) -> ComposeResult:
        yield Static("⚙️ Settings content here!")
