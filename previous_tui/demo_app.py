# previous_tui_files/demo_app.py (GENERIC EXAMPLE - Not App Specific)

# SECTION: MODULE DOCSTRING
"""GENERIC EXAMPLE: Textual Demo App showing modes and bindings.
Not directly relevant to Pixabit's core functionality. Can be discarded.
"""

# SECTION: IMPORTS
from typing import Tuple, Union  # Added Union

from textual.app import App
from textual.binding import Binding

# Assume these screens exist elsewhere or are placeholders
from textual.screen import Screen


class GameScreen(Screen):
    pass


class HomeScreen(Screen):
    pass


class ProjectsScreen(Screen):
    pass


class WidgetsScreen(Screen):
    pass


# SECTION: EXAMPLE APP
# KLASS: DemoApp
class DemoApp(App[None]):  # Add return type hint
    """Generic demo app showing modes and bindings."""

    CSS = """
    /* Example CSS */
    Screen { align: center middle; }
    """

    # Define modes mapping mode names to Screen classes
    MODES = {
        "game": GameScreen,
        "home": HomeScreen,
        "projects": ProjectsScreen,
        "widgets": WidgetsScreen,
    }
    DEFAULT_MODE = "home"

    # Define key bindings
    BINDINGS = [
        Binding(
            "h", "app.switch_mode('home')", "Home", tooltip="Show home screen"
        ),
        Binding("g", "app.switch_mode('game')", "Game", tooltip="Play a game"),
        Binding(
            "p",
            "app.switch_mode('projects')",
            "Projects",
            tooltip="View projects",
        ),
        Binding(
            "w", "app.switch_mode('widgets')", "Widgets", tooltip="Test widgets"
        ),
        Binding(
            "ctrl+s",
            "app.screenshot",
            "Screenshot",
            tooltip="Save SVG screenshot",
        ),
        Binding(
            "escape", "app.quit", "Quit", tooltip="Exit the app"
        ),  # Added quit
    ]

    # Example custom action
    # def action_maximize(self) -> None: ...

    # Example action check
    def check_action(
        self, action: str, parameters: Tuple[object, ...]
    ) -> Union[bool, None]:
        """Disable switching to the current mode."""
        if (
            action == "switch_mode"
            and parameters
            and self.current_mode == parameters[0]
        ):
            return None  # Disable action
        return True  # Allow action
