# pixabit/helpers/_textual.py

# SECTION: MODULE DOCSTRING
"""Provides convenient access to core Textual components and potentially enhanced base widgets.

Acts as a central point for importing commonly used Textual classes, reducing
redundant imports in other TUI modules. Includes examples of potentially
enhanced or styled base widgets.
"""

# SECTION: IMPORTS
from typing import (  # Keep TypeVar/cast for EnhancedContainer
    Any,
    Optional,
    Type,
    TypeVar,
    cast,
)

# --- Textual Core ---
from textual import events, log, on, work  # Import work decorator
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import (
    Container,
    Grid,
    Horizontal,
    HorizontalScroll,  # Added
    ScrollableContainer,
    Vertical,
    VerticalScroll,  # Added
)
from textual.css.query import NoMatches, QueryError  # Added QueryError
from textual.dom import DOMNode
from textual.geometry import (  # Added Region, Spacing
    Offset,
    Region,
    Size,
    Spacing,
)
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen  # Added ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    ContentSwitcher,
    DataTable,
    DirectoryTree,  # Added
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    Markdown,  # Added Markdown base widget
    MarkdownViewer,
    OptionList,
    Placeholder,  # Added Placeholder
    Pretty,  # Added Pretty
    RadioButton,
    RadioSet,
    RichLog,  # Added RichLog
    Rule,  # Added Rule
    Select,
    Sparkline,  # Added Sparkline
    Static,
    Switch,
    TabbedContent,
    TabPane,
    Tabs,  # Added Tabs
    TextArea,
    # Added TextLog
    Tree,
)
from textual.worker import Worker, get_current_worker  # Added Worker management

# SECTION: TYPE VARIABLES
T = TypeVar("T", bound=Widget)  # Generic type for widget querying


# SECTION: ENHANCED/CUSTOM WIDGETS (Examples)


# KLASS: EnhancedContainer
class EnhancedContainer(Container):
    """Example Container with additional convenience methods."""

    # FUNC: get_widget_by_id
    def get_widget_by_id(self, widget_id: str, *, expected_type: Type[T] = Widget) -> T:  # type: ignore
        """Safely gets a widget by ID, raising a specific error if not found or type mismatch.

        Args:
            widget_id: The ID of the widget to find (without the # prefix).
            expected_type: The expected type of the widget (e.g., Button, Input).

        Returns:
            The found widget instance, cast to the expected type.

        Raises:
            ValueError: If no widget with the ID is found.
            TypeError: If the found widget is not of the expected type.
        """
        try:
            widget = self.query_one(f"#{widget_id}", expected_type)
            return widget  # Already checked type with query_one
        except NoMatches:
            # Error if widget not found
            log.error(f"Widget with ID '#{widget_id}' not found within {self}.")
            raise ValueError(f"No widget with ID '{widget_id}' found.")
        except QueryError as e:
            # Error if widget found but type doesn't match expected_type
            log.error(f"Widget query error for '#{widget_id}': {e}")
            # Extract actual type if possible from error or query again without type check
            try:
                actual_widget = self.query_one(f"#{widget_id}")
                actual_type = type(actual_widget).__name__
            except Exception:
                actual_type = "unknown"
            raise TypeError(f"Widget '#{widget_id}' found, but its type ('{actual_type}') does not match expected type ('{expected_type.__name__}').") from e


# KLASS: PixabitButton (Example styled button)
class PixabitButton(Button):
    """Example Button using CSS variables defined in the application's theme."""

    DEFAULT_CSS = """
    PixabitButton {
        /* Assuming these CSS variables are defined in pixabit.tcss */
        background: $accent; /* Use accent color for background */
        color: $text;
        border: tall $accent-darken-2; /* Slightly darker border */
        min-width: 8; /* Ensure minimum width */
        padding: 0 2; /* Horizontal padding */
        height: 3; /* Explicit height */
        content-align: center middle; /* Center text */
    }

    PixabitButton:hover {
        background: $accent-lighten-1; /* Lighter on hover */
        border-color: $accent;
    }

    /* Focus state might need specific styling if default isn't sufficient */
    PixabitButton.-focused {
         border: thick $accent-lighten-2;
         outline: none; /* May need outline depending on terminal */
    }

    PixabitButton.-active {
         background: $accent-darken-2; /* Darker when pressed */
    }
    """
    # You can add custom methods or properties here if needed
    pass


# SECTION: EXPORTS
# Export common Textual components for use throughout the application
__all__ = [
    # --- Textual Core ---
    "App",
    "ComposeResult",
    "Binding",
    "Widget",
    "Screen",
    "ModalScreen",
    "reactive",
    "events",
    "on",
    "work",  # Export work decorator
    "log",
    "Message",
    "DOMNode",
    # Geometry
    "Size",
    "Offset",
    "Region",
    "Spacing",
    # Selectors / Querying
    "NoMatches",
    "QueryError",
    # Workers
    "Worker",
    "get_current_worker",
    # --- Containers ---
    "Container",
    "Grid",
    "Horizontal",
    "Vertical",
    "ScrollableContainer",
    "HorizontalScroll",
    "VerticalScroll",
    # --- Basic Widgets ---
    "Button",
    "Checkbox",
    "Input",
    "Label",
    "ListItem",
    "ListView",
    "OptionList",
    "RadioButton",
    "RadioSet",
    "Select",
    "Static",
    "Switch",
    # --- More Advanced Widgets ---
    "ContentSwitcher",
    "DataTable",
    "DirectoryTree",
    "Footer",
    "Header",
    "LoadingIndicator",
    "Markdown",
    "MarkdownViewer",
    "Placeholder",
    "Pretty",
    "RichLog",
    "Rule",
    "Sparkline",
    "TabbedContent",
    "TabPane",
    "Tabs",
    "TextArea",
    "Tree",
    # --- Custom Base Widgets ---
    "EnhancedContainer",  # Example enhanced container
    "PixabitButton",  # Example styled button
]
