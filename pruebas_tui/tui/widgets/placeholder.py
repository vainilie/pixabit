# pixabit/tui/widgets/placeholder.py

# SECTION: MODULE DOCSTRING
"""A simple placeholder widget for layout purposes during development."""

# SECTION: IMPORTS
from textual.app import ComposeResult
from textual.widgets import Static


# SECTION: WIDGET CLASS
# KLASS: PlaceholderWidget
class PlaceholderWidget(Static):
    """A basic placeholder widget inheriting from Static."""

    DEFAULT_CSS = """
    PlaceholderWidget {
        border: round $accent-lighten-2;
        background: $panel-darken-2;
        content-align: center middle;
        color: $text-muted;
        height: 100%; /* Make it fill space */
        width: 100%;
    }
    """

    # FUNC: __init__
    def __init__(self, label: str = "Placeholder", **kwargs):
        """Initialize with a label."""
        super().__init__(label, **kwargs)

    # FUNC: compose (Not strictly needed for Static)
    # def compose(self) -> ComposeResult:
    #     yield from super().compose()
