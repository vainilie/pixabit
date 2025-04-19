# pixabit/tui/widgets/stats_panel.py

# SECTION: MODULE DOCSTRING
"""Defines the StatsPanel widget for displaying user statistics."""

# SECTION: IMPORTS
import logging
from typing import Any, Dict, Optional

from rich.logging import RichHandler
from rich.text import Text  # For potential advanced formatting
from textual import log
from textual.app import ComposeResult
from textual.containers import Vertical  # Arrange stats vertically
from textual.widget import Widget  # Base class for custom widgets
from textual.widgets import Static  # Use Static for displaying text/values

FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)])


# SECTION: WIDGET CLASS
# KLASS: StatsPanel
class StatsPanel(Static):  # Inherit from Static or Widget/Container
    """A widget to display Habitica user statistics."""

    DEFAULT_CSS = """
    StatsPanel {
        border: round $accent;
        padding: 1;
        height: auto; /* Adjust height as needed */
        /* Add more specific styling */
    }
    StatsPanel > Vertical > Static { /* Target Static widgets inside */
        margin-bottom: 1;
    }
    .stat-label {
        color: $text-muted; /* Dim color for labels */
        margin-right: 1;
    }
    .stat-value {
        /* Add styling for values if needed */
        color: $text;
    }
    /* Colors based on stats_widget.py attempt */
    #stat-level .stat-value { color: $warning; }
    #stat-hp .stat-value { color: $error; }
    #stat-mp .stat-value { color: $primary; }
    #stat-exp .stat-value { color: $success; }
    #stat-gp .stat-value { color: $warning-darken-2; }
    #stat-gems .stat-value { color: $secondary; } /* Example color */
    #stat-class .stat-value { color: $text; }
    #stat-status .stat-value { color: $text; }
    """

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Create child widgets for the stats display."""
        # Use Vertical layout to stack stats
        with Vertical():
            # Create Static widgets for each stat, giving them IDs for updating
            yield Static("Level: [b]--[/b]", id="stat-level")
            yield Static("Class: [b]--[/b]", id="stat-class")
            yield Static("HP:    [b]-- / --[/b]", id="stat-hp")
            yield Static("MP:    [b]-- / --[/b]", id="stat-mp")
            yield Static("EXP:   [b]-- / --[/b]", id="stat-exp")
            yield Static("GP:    [b]--[/b]", id="stat-gp")
            yield Static("Gems:  [b]--[/b]", id="stat-gems")
            yield Static("Status:[b]--[/b]", id="stat-status")
            # Add more stats as needed (e.g., STR, INT, CON, PER from base stats)

    # FUNC: update_display
    def update_display(self, stats_data: Optional[Dict[str, Any]]) -> None:
        """Updates the displayed statistics.

        Called by the main App after data is refreshed in the DataStore.

        Args:
            stats_data: The dictionary returned by DataStore.get_user_stats(), or None.
        """
        if not stats_data:
            log.warning("StatsPanel received no data to display.")
            # Clear display or show placeholders
            placeholders = {
                "stat-level": "Level: [b]--[/b]",
                "stat-class": "Class: [b]--[/b]",
                "stat-hp": "HP:    [b]-- / --[/b]",
                "stat-mp": "MP:    [b]-- / --[/b]",
                "stat-exp": "EXP:   [b]-- / --[/b]",
                "stat-gp": "GP:    [b]--[/b]",
                "stat-gems": "Gems:  [b]--[/b]",
                "stat-status": "Status:[b]--[/b]",
            }
            for widget_id, text in placeholders.items():
                try:
                    self.query_one(f"#{widget_id}", Static).update(text)
                except Exception as e:
                    log.error(f"Error clearing stat {widget_id}: {e}")
            return

        # Safely get values from the dictionary
        level = stats_data.get("level", "--")
        u_class = str(stats_data.get("class", "--")).capitalize()
        hp = stats_data.get("hp", 0.0)
        max_hp = stats_data.get("maxHealth", 0)
        mp = stats_data.get("mp", 0.0)
        max_mp = stats_data.get("maxMP", 0)
        exp = stats_data.get("exp", 0.0)
        next_lvl = stats_data.get("toNextLevel", 0)
        gp = stats_data.get("gp", 0.0)
        gems = stats_data.get("gems", "--")
        sleeping = stats_data.get("sleeping", False)
        status = "[yellow]Sleeping[/]" if sleeping else "[green]Awake[/]"

        # Update the Static widgets using their IDs
        try:
            self.query_one("#stat-level", Static).update(f"Level: [b]{level}[/]")
            self.query_one("#stat-class", Static).update(f"Class: [b]{u_class}[/]")
            self.query_one("#stat-hp", Static).update(f"HP:    [b]{hp:.1f} / {max_hp}[/]")
            self.query_one("#stat-mp", Static).update(f"MP:    [b]{mp:.1f} / {max_mp}[/]")
            self.query_one("#stat-exp", Static).update(f"EXP:   [b]{exp:.0f} / {next_lvl}[/]")
            self.query_one("#stat-gp", Static).update(f"GP:    [b]{gp:.2f}[/]")
            self.query_one("#stat-gems", Static).update(f"Gems:  [b]{gems}[/]")
            self.query_one("#stat-status", Static).update(f"Status:{status}")
            log.info("StatsPanel display updated.")
        except Exception as e:
            log.error(f"Error updating stat widgets: {e}")
