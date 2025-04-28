# previous_tui_files/layout.py (GENERIC EXAMPLE)

# SECTION: MODULE DOCSTRING
"""GENERIC EXAMPLE: Simple Textual App showing only the Header widget.
Minimal reuse value.
"""

# SECTION: IMPORTS
from textual.app import App, ComposeResult
from textual.widgets import Header


# SECTION: EXAMPLE APP
# KLASS: HeaderApp
class HeaderApp(App[None]):  # Add type hint for run()
    """A simple app demonstrating the Header."""

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Create the Header widget."""
        yield Header(
            show_clock=True
        )  # time_format deprecated, show_clock is bool

    # FUNC: on_mount
    def on_mount(self) -> None:
        """Set the title and subtitle."""
        self.title = "PIXABIT Header Example"
        self.sub_title = "Habitica TUI Client"


# Example Runner (Not needed for Pixabit)
# if __name__ == "__main__":
#     app = HeaderApp()
#     app.run()
