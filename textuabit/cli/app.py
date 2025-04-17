
# pixabit/cli/app.py

# MARK: - MODULE DOCSTRING
"""Main Command Line Interface application class for Pixabit - TEXTUAL TUI VERSION.

(Phase 1: Basic Textual App Structure)
"""


# --- Standard Imports ---
import asyncio
# Import asyncio
import sys
# Import sys for system exit
from typing import Any, Dict


# --- Third-party Imports (Textual & Rich) ---
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
# Layout containers
from textual.widgets import Footer, Header, Label
# Basic widgets


# --- Local Application Imports ---
try:
    from pixabit.api import HabiticaAPI
# Still need API Client
except ImportError:
    print("[Fatal Error] Could not import Pixabit modules in app.py.")
    sys.exit(1)



# MARK: - PixabitTUIApp Class (Textual App)

# ==============================================================================
class PixabitTUIApp(App):
    """Basic Textual TUI Application for Pixabit - PLACEHOLDER UI."""

    CSS_PATH = "pixabit.tcss"
# Link CSS file for styling
    BINDINGS = [
        ("q", "quit_app", "Quit"),
# Keybinding to quit
        ("r", "refresh_data_ui", "Refresh Data (Placeholder)"),
# Keybinding for refresh
    ]


# & - def __init__(self, **kwargs):
    def __init__(self, **kwargs):
        """Initialize Pixabit TUI App (basic init)."""
        super().__init__(**kwargs)
        self.api_client = HabiticaAPI()
# API Client (still sync for now)


# & - async def on_mount(self) -> None:
    async def on_mount(self) -> None:
        """Async on_mount hook - initial async setup."""
        self.title = "Pixabit - Placeholder UI"
        self.subtitle = "Alpha - Placeholder UI"
        self.console.log("Textual App Mounted (on_mount)")
        await self.action_refresh_data_ui()
# Call placeholder refresh


# & - def compose(self) -> ComposeResult:
    def compose(self) -> ComposeResult:
        """Compose the basic visual structure using placeholder widgets."""

# Yield the Header and Footer widget
        yield Header()
        yield Footer()


# Basic grid layout with placeholder panels
        yield Container(
            Vertical(Label("User Stats Placeholder", id="stats-label"), id="stats-panel"),
            Vertical(Label("Main Menu Placeholder", id="menu-label"), id="menu-panel"),
            Vertical(Label("Content Area Placeholder", id="content-label"), id="content-panel"),
            id="main-content-area",
# ID for the main container, used in CSS
        )


# MARK: - Actions (Key Bindings)

# & - async def action_quit_app(self) -> None:
    async def action_quit_app(self) -> None:
        """Action bound to 'q' - quits the app."""
        self.console.log("Action: Quit App")
        await self.shutdown()
# Textual shutdown


# & - async def action_refresh_data_ui(self) -> None:
    async def action_refresh_data_ui(self) -> None:
        """Action bound to 'r' - placeholder refresh."""
        self.console.log("Action: Refresh Data (UI)")

# --- Placeholder Refresh Logic ---
        self.console.log("Simulating data refresh...")
        await asyncio.sleep(1)
# Simulate async data loading
        self.console.log("Data refresh complete (simulated).")

# Update placeholder labels to show refresh happened
        self.query_one("
#stats-label", Label).update("User Stats Refreshed!")
        self.query_one("
#menu-label", Label).update("Main Menu Refreshed!")
        self.query_one(" #content-label", Label).update("Content Area Refreshed!")


# & - def _get_content_cached(self) -> Dict[str, Any]:
    def _get_content_cached(self) -> Dict[str, Any]:
        """Placeholder for cached content loading."""

# Keep this placeholder function for now, implementation not critical for Phase 1
        return {}



# MARK: - Run App Function

# & - def run_app():
def run_app():
    """Run the Pixabit Textual TUI application."""
    try:
        app = PixabitTUIApp()
        app.run()
# Run Textual app
    except Exception:
        console.print_exception(show_locals=False)



# MARK: - Entry Point

# & - if __name__ == "__main__":
if __name__ == "__main__":
    run_app()
