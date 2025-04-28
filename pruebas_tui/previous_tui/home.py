# previous_tui_files/home.py (LEGACY TUI SCREEN EXAMPLE)

# SECTION: MODULE DOCSTRING
"""LEGACY: Example Home Screen using TabbedContent.

Demonstrates how to arrange different widgets (including legacy ones from this
attempt) into tabs. The concept of using tabs might be useful, but the specific
widgets and content are deprecated.
"""

# SECTION: IMPORTS
from typing import Any  # Added Any

# Textual Imports
from textual.app import ComposeResult
from textual.containers import Container  # Use base Container
from textual.screen import Screen  # Use base Screen
from textual.widgets import (
    Footer,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
)  # Added Static

# Local Imports (These point to OLD widget locations - DEPRECATED)
# from heart.TUI.__stats_widget import StatsCount # Old stats widget
# from heart.TUI.__backup import ButtonsApp # Generic button example
# from heart.TUI.__sleep import SwitchApp # Old sleep widget
# from heart.TUI.__tags import TagsSection, SelectApp, TagManagerWidget # Old tag widgets
# Import placeholder for now
from .widgets.placeholder import PlaceholderWidget

# SECTION: MARKDOWN CONTENT (Keep for reference if text is useful)
WHAT_IS_TEXTUAL_MD = """..."""  # Keep content
WELCOME_MD = """..."""  # Keep content
ABOUT_MD = """..."""  # Keep content (Shows original feature ideas)
API_MD = """..."""  # Keep content
DEPLOY_MD = """..."""  # Keep content


# SECTION: LEGACY SCREEN CLASS
# KLASS: HomeScreen (Legacy Example)
class HomeScreen(Screen):  # Inherit from Screen
    """LEGACY Example Home Screen using Tabs."""

    DEFAULT_CSS = """
    HomeScreen {
        /* Basic screen styling */
        background: $panel;
    }
    TabbedContent {
        height: 1fr; /* Make tabs fill available space */
    }
    TabPane {
        padding: 1 2; /* Add padding within tabs */
    }
    /* Add styling for Markdown or other content as needed */
    Markdown {
        background: transparent; /* Make markdown background transparent */
    }
    """

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Compose the tabbed layout."""
        # Yield Footer separately, not inside TabbedContent
        with TabbedContent(initial="welcome"):  # Set initial active tab
            # Use Placeholders instead of legacy widgets
            with TabPane("Welcome", id="welcome"):
                yield PlaceholderWidget(
                    "Welcome Content / Buttons / Sleep Toggle Area"
                )
                # yield ButtonsApp() # Legacy
                # yield SwitchApp() # Legacy
            with TabPane("About / Features", id="about"):
                # Use Static or Markdown to display text content
                yield Static(
                    "Feature List / About Section", classes="about-text"
                )
                # yield Markdown(ABOUT_MD) # Legacy
            with TabPane("Tags", id="tags"):
                yield PlaceholderWidget("Tag List / Management Area")
                # yield TagsSection() # Legacy
                # yield TagManagerWidget() # Legacy
            with TabPane("Stats", id="stats"):
                yield PlaceholderWidget("Stats Display Area")
                # yield StatsCount() # Legacy
            # Add more tabs as needed

        # yield Footer() # Footer should be part of the App.compose, not Screen
