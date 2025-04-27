# previous_tui_files/stats.py (LEGACY TUI WIDGET ATTEMPT)

# SECTION: MODULE DOCSTRING
"""LEGACY: Previous attempt at a stats display widget for Textual.

Contained logic for fetching stats directly via httpx within the widget worker.
This logic should now reside in PixabitDataStore, and the widget should only
display data passed to it. CSS and layout might be reusable.
"""

# SECTION: IMPORTS
# Standard Imports (Keep asyncio if worker logic remains temporarily)
import asyncio
from importlib.metadata import version

# Textual Imports
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Digits, Label

# Third-party Imports
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore

# Local Imports (These are from the OLD structure - likely invalid now)
# from heart.basis.auth_keys import get_user_id, get_api_token # Old auth method

# SECTION: CONSTANTS (Old hardcoded values - use config/DataStore now)
# BASEURL = "https://habitica.com/api/v3/"
# USER_ID = get_user_id() # Should come from config/DataStore
# API_TOKEN = get_api_token() # Should come from config/DataStore
# HEADERS = { ... } # Headers should be handled by HabiticaAPI client


# SECTION: LEGACY WIDGET CLASS
# KLASS: StarCount (Legacy Widget)
class StarCount(Vertical):
    """LEGACY WIDGET: Displays Habitica stats.

    NOTE: Contains direct API fetching logic (@work) which is DEPRECATED in the
    new architecture. Widgets should receive data from the App/DataStore.
    The CSS and compose() method might offer reusable layout ideas.
    """

    DEFAULT_CSS = """
    StarCount {
        /* Layout */
        height: 6; /* Consider auto height? */
        layout: horizontal;
        padding: 0 1;
        align: center middle; /* Align items vertically centered */
        border-bottom: hkey $background; /* Example border */
        border-top: hkey $background;
        background: $boost; /* Example background */

        /* Child Alignment */
        &> Horizontal { /* Target the inner Horizontal container */
            width: auto; /* Allow horizontal container to fit content */
            align: center middle; /* Align vertical stat groups */
            /* max-width: 100; /* Optional max width */
        }
        Vertical { /* Target individual stat groups */
             width: auto; /* Allow vertical group to fit content */
             margin: 0 1; /* Add spacing between stat groups */
             align: center top; /* Align label above digits */
        }
        Label { width: auto; text-style: bold; color: $text; margin-bottom: 1; }
        Digits { width: auto; }

        /* Stat-specific Colors */
        #lvl Label, #lvl Digits { color: #FFD700; } /* Gold */
        #mp Label, #mp Digits { color: #00BFFF; }  /* Deep Sky Blue */
        #hp Label, #hp Digits { color: #FF4500; }  /* Orange Red */
        #exp Label, #exp Digits { color: #32CD32; } /* Lime Green */
        #gp Label, #gp Digits { color: #DAA520; }  /* Goldenrod */
    }
    """

    # Reactive variables to hold stats (still potentially useful)
    lvl: reactive[int] = reactive(0)
    mp: reactive[float] = reactive(0.0)  # Use float for potential decimals
    hp: reactive[float] = reactive(0.0)  # Use float
    gp: reactive[float] = reactive(0.0)  # Use float
    exp: reactive[float] = reactive(0.0)  # Use float
    # Add max values if displaying hp/max_hp etc.
    max_hp: reactive[int] = reactive(50)
    max_mp: reactive[int] = reactive(30)  # Example base
    to_next_level: reactive[int] = reactive(0)

    # DEPRECATED worker - Fetching logic belongs in DataStore
    # @work
    # async def get_stars(self):
    #     """Worker to get stats from Habitica API."""
    #     # ... (Old httpx fetching logic) ...

    # FUNC: update_display (NEW - Required for new architecture)
    def update_display(self, stats_data: dict[str, Any] | None) -> None:
        """Updates the widget's display based on data from the DataStore.

        Args:
            stats_data: The stats dictionary (e.g., from DataStore.get_user_stats()).
        """
        if not stats_data:  # Handle case where stats are not available
            self.log.warning("Stats widget received no data to display.")
            # Optionally clear display or show placeholder text
            self.lvl = 0
            self.mp = 0.0
            self.hp = 0.0
            self.gp = 0.0
            self.exp = 0.0
            self.max_hp = 50
            self.max_mp = 30
            self.to_next_level = 0
            return

        # Update reactive variables from the provided dictionary
        self.lvl = stats_data.get("level", 0)
        self.mp = stats_data.get("mp", 0.0)
        self.hp = stats_data.get("hp", 0.0)
        self.gp = stats_data.get("gp", 0.0)
        self.exp = stats_data.get("exp", 0.0)
        self.max_hp = stats_data.get("maxHealth", 50)
        self.max_mp = stats_data.get(
            "maxMP", 30
        )  # Get actual max if calculated
        self.to_next_level = stats_data.get("toNextLevel", 0)
        # Update will trigger recompose/rewatch

        # Update Tooltips (since recompose=False for Digits by default)
        try:
            self.query_one("#lvl Digits", Digits).tooltip = f"Level: {self.lvl}"
            self.query_one("#mp Digits", Digits).tooltip = (
                f"Mana: {self.mp:.1f} / {self.max_mp}"
            )
            self.query_one("#hp Digits", Digits).tooltip = (
                f"Health: {self.hp:.1f} / {self.max_hp}"
            )
            self.query_one("#exp Digits", Digits).tooltip = (
                f"Experience: {self.exp:.0f} / {self.to_next_level}"
            )
            self.query_one("#gp Digits", Digits).tooltip = (
                f"Gold: {self.gp:.2f}"
            )
        except Exception as e:
            self.log.error(f"Error updating tooltips: {e}")

    # Watch methods to update Digits when reactive vars change
    def watch_lvl(self, value: int) -> None:
        try:
            self.query_one("#lvl Digits", Digits).update(f"{value}")
        except Exception:
            pass  # Ignore if widget not ready

    def watch_mp(self, value: float) -> None:
        try:
            self.query_one("#mp Digits", Digits).update(f"{value:.1f}")
        except Exception:
            pass

    def watch_hp(self, value: float) -> None:
        try:
            self.query_one("#hp Digits", Digits).update(f"{value:.1f}")
        except Exception:
            pass

    def watch_exp(self, value: float) -> None:
        try:
            self.query_one("#exp Digits", Digits).update(f"{value:.0f}")
        except Exception:
            pass

    def watch_gp(self, value: float) -> None:
        try:
            self.query_one("#gp Digits", Digits).update(f"{value:.2f}")
        except Exception:
            pass

    # FUNC: compose (Layout structure looks reusable)
    def compose(self) -> ComposeResult:
        """Create UI components."""
        # This layout seems reasonable, using Horizontal for overall layout
        # and Vertical for each stat Label + Digits pair.
        with Horizontal():  # Contains the vertical stat groups
            with Vertical(id="lvl"):
                yield Label("Level ★")
                yield Digits(f"{self.lvl}")  # Tooltip set in update_display

            with Vertical(id="mp"):
                yield Label("Mana")
                yield Digits(f"{self.mp:.1f}")

            with Vertical(id="hp"):
                yield Label("Health")
                yield Digits(f"{self.hp:.1f}")

            with Vertical(id="exp"):
                yield Label("Experience")
                yield Digits(f"{self.exp:.0f}")

            with Vertical(id="gp"):
                yield Label("Gold")
                yield Digits(f"{self.gp:.2f}")

    # FUNC: on_mount (Should not fetch data directly)
    # def on_mount(self) -> None:
    #     """DEPRECATED: Fetch stats on mount."""
    #     # self.get_stars() # Remove direct fetch

    # FUNC: on_click (Should likely trigger App refresh, not local fetch)
    # def on_click(self) -> None:
    #     """DEPRECATED: Refresh stats on click."""
    #     # self.get_stars() # Remove direct fetch
    #     # Instead, could post a message: self.post_message(self.RefreshRequest())
