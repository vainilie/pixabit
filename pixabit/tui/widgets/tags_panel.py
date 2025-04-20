# stats_panel.py
from textual.app import ComposeResult
from textual.widgets import Static


class TagsPanel(Static):
    """A panel showing stats content"""

    def compose(self) -> ComposeResult:
        yield Static("📊 Stats content here!")
