# pixabit/utils/display.py

# SECTION: MODULE DOCSTRING
"""Initializes and configures the Rich Console instance with a custom theme.

Loads theme definitions from a specified file ('styles' by default), handles
potential loading errors by falling back to a default theme. Exports the
configured 'console' instance and commonly used Rich components for consistent
UI elements across the application. Also installs Rich tracebacks.
"""

# SECTION: IMPORTS
import builtins
from pathlib import Path
from typing import Any, Optional  # Added Any for **kwargs

# Rich Imports
from rich import box
from rich.columns import Columns
from rich.console import Console, ConsoleRenderable  # Import ConsoleRenderable
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    track,
)

# Removed Spinner import as SpinnerColumn is usually sufficient
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.traceback import install as install_traceback

# Optional art import
try:
    from art import text2art

    ART_AVAILABLE = True
except ImportError:
    ART_AVAILABLE = False

    def text2art(
        *args: Any, **kwargs: Any
    ) -> str:  # Dummy function if art not installed
        """Dummy text2art function when 'art' library is not available."""
        print("[Warning] 'art' library not found, ASCII art disabled.")
        return "Pixabit"  # Fallback text


# SECTION: PATHS AND DEFAULTS

# Assumes display.py is in utils/, styles file is one level up from utils/
try:  # Go up one level from utils/display.py to project root/pixabit/
    base_dir = Path(__file__).resolve().parent.parent
    theme_file_path = (
        base_dir / "utils" / "styles"
    )  # Corrected path assuming styles is in utils
    # If styles is at the *project root* (outside pixabit folder), adjust base_dir:
    # base_dir = Path(__file__).resolve().parent.parent.parent
    # theme_file_path = base_dir / "styles"
except NameError:  # Fallback if __file__ is not defined
    theme_file_path = (
        Path("pixabit") / "utils" / "styles"
    )  # Assume running from project root
    if not theme_file_path.exists():
        theme_file_path = Path("utils") / "styles"  # Try without pixabit prefix
        if not theme_file_path.exists():
            theme_file_path = Path("styles")  # Final fallback to project root

# Default theme dictionary (simplified fallback based on names in styles file)
default_theme_dict = {
    "regular": "default",
    "highlight": "bold #eb6f92",
    "subtle": "dim #908caa",
    "file": "underline #b4bdf8",
    "info": "#cba6f7",
    "warning": "bold #f6c177",
    "danger": "bold #eb6f92 on #e0def4",
    "error": "bold #f38ba8",
    "success": "bold #a6e3a1",
    "keyword": "bold #c4a7e7",
    "link_style": "underline #89b4fa",
    "dim": "dim",
    "rule.line": "#45475A",
    "prompt.choices": "#94e2d5",
    "prompt.default": "#7f849c",
    "prompt.invalid": "#f38ba8",
    "log.level.warning": "bold #f6c177",
    "log.level.error": "bold #f38ba8",
    "log.level.info": "#cba6f7",
    "log.level.debug": "dim #908caa",
    "repr.number": "#fab387",
    "repr.str": "#a6e3a1",
    "repr.bool_true": "bold #a6e3a1",
    "repr.bool_false": "bold #f38ba8",
    "repr.none": "dim #908caa",
    "repr.url": "underline #89b4fa",
    "progress.description": "#e0def4",
    "progress.percentage": "#9ccfd8",
    "progress.remaining": "#f6c177",
    "bar.complete": "#a6e3a1",
    "bar.finished": "#74c7ec",
    "bar.pulse": "#f5c2e7",
    "table.header": "bold #cba6f7",
    "rp_text": "#e0def4",
    "rp_iris": "#c4a7e7",
    "rp_foam": "#9ccfd8",
    "rp_rose": "#ebbcba",
    "rp_gold": "#f6c177",
    "rp_pine": "#31748f",
    "rp_love": "#eb6f92",
    "rp_muted": "#6e6a86",
    "rp_subtle_color": "#908caa",
    "rp_surface": "#1f1d2e",
    "rp_overlay": "#26233a",
    "field": "dim",
}

# SECTION: THEME LOADING AND CONSOLE INITIALIZATION

custom_theme: Optional[Theme] = None
console: Console  # Define console type hint

if theme_file_path.exists():
    try:
        # Load theme using Rich's Theme.from_file method
        with open(theme_file_path, encoding="utf-8") as tf:
            custom_theme = Theme.from_file(tf, source=str(theme_file_path))
        console = Console(theme=custom_theme)
        # Use console.print if theme loaded successfully
        _themed_print = console.print
        # Use log for theme loading status for better semantics
        console.log(
            f"Successfully loaded theme from [file]{theme_file_path}[/]",
            style="success",
        )
    except Exception as e:
        builtins.print(f"⛔ Error loading theme from {theme_file_path}: {e}")
        builtins.print("⛔ Falling back to basic default theme.")
        custom_theme = Theme(default_theme_dict)  # Use basic dict fallback
        console = Console(theme=custom_theme)
        _themed_print = (
            console.print
        )  # Still use the themed print even with fallback theme
else:
    builtins.print(
        f"⛔ Theme file not found at '{theme_file_path}'. Using basic default theme."
    )
    custom_theme = Theme(default_theme_dict)  # Use basic dict fallback
    console = Console(theme=custom_theme)
    _themed_print = console.print  # Use the themed print

# SECTION: PRETTY TRACEBACKS
# Installs a handler to format tracebacks using Rich
install_traceback(
    console=console,
    show_locals=False,  # Set show_locals=True for more detailed debugging if needed
    word_wrap=False,
    width=console.width,  # Use console width
    suppress=[],  # Add libraries to suppress here if needed (e.g., ['click'])
)

# SECTION: CONVENIENCE PRINT FUNCTION


# Define a wrapper function 'print' that uses the themed console's print method.
# This allows other modules to just use `from pixabit.utils.display import print`.
# Use different name internally to avoid recursion errors.
def print(*args: Any, **kwargs: Any) -> None:
    """Prints to the configured Rich console using the loaded theme.

    Provides a convenient way to access `console.print` throughout the application.

    Args:
        *args: Positional arguments passed to `rich.console.Console.print`.
        **kwargs: Keyword arguments passed to `rich.console.Console.print`.
    """
    # Call the internal themed print function captured earlier
    return _themed_print(*args, **kwargs)


# SECTION: EXPORTS
# Export the configured console instance and commonly used Rich components
# Other modules can import these directly from pixabit.utils.display
__all__ = [
    "console",
    "print",  # Export the wrapper function as 'print'
    "Confirm",
    "IntPrompt",
    "Prompt",
    "Table",
    "Panel",
    "Columns",
    "Layout",
    "Rule",
    "box",
    "Progress",
    "track",
    "Live",
    "SpinnerColumn",  # Use SpinnerColumn with Progress
    "BarColumn",
    "TextColumn",
    "TimeElapsedColumn",
    "TimeRemainingColumn",
    "TaskProgressColumn",
    "Markdown",
    "Text",
    "Syntax",
    "ART_AVAILABLE",  # Export flag
    "text2art",  # Export original or dummy function
    "ConsoleRenderable",  # Export base type for renderables
]
