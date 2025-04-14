# pixabit/utils/display.py
# MARK: - MODULE DOCSTRING
"""Initializes and configures the Rich Console instance with a custom theme.

Loads theme definitions from a specified file ('styles' by default) and handles
potential loading errors by falling back to a default theme. Exports the
configured 'console' instance and commonly used Rich components for consistent
UI elements across the application.
"""

import builtins  # For fallback print

# MARK: - IMPORTS
from pathlib import Path
from typing import Optional

# Third-party Rich library components
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    Spinner,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    track,
)
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.traceback import install as install_traceback

# Optional: For ASCII art integration
try:
    from art import text2art

    ART_AVAILABLE = True
except ImportError:
    ART_AVAILABLE = False

# MARK: - THEME LOADING AND CONSOLE INITIALIZATION

# Define the path relative to this file's location
# Assumes display.py is in utils/, styles file is at project root
try:
    # Go up two levels from utils/display.py to project root
    base_dir = Path(__file__).resolve().parent
    theme_file_path = base_dir / "styles"
except NameError:
    # Fallback if __file__ is not defined (e.g. interactive testing)
    theme_file_path = Path("styles")  # Look in CWD relative to execution

# Default theme dictionary (simplified fallback based on names in styles.txt)
default_theme_dict = {
    "regular": "default",
    "highlight": "bold #eb6f92",  # love
    "subtle": "dim #908caa",  # rp_subtle_color
    "file": "underline #b4bdf8",  # lavender
    "info": "#cba6f7",  # info
    "warning": "bold #f6c177",  # gold
    "error": "bold #f38ba8",  # red
    "success": "bold #a6e3a1",  # green
    "keyword": "bold #c4a7e7",  # iris
    "link_style": "underline #89b4fa",  # blue
    "dim": "dim",
    "rule.line": "#45475A",  # surface1
    "prompt.choices": "#94e2d5",  # teal
    "prompt.default": "#7f849c",  # overlay1
    "prompt.invalid": "#f38ba8",  # red
    "progress.description": "#e0def4",  # rp_text
    "progress.percentage": "#9ccfd8",  # rp_foam
    "progress.remaining": "#f6c177",  # rp_gold
    "bar.complete": "#a6e3a1",  # green
    "bar.finished": "#74c7ec",  # sapphire
    "bar.pulse": "#f5c2e7",  # pink
    "table.header": "bold #cba6f7",  # info
    "repr.number": "#fab387",  # peach
    "repr.str": "#a6e3a1",  # green
    #    "repr.url": "link_style",
    # Add simplified Rose Pine styles referenced in code
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
    "field": "dim",  # Style for field names in reviews
}

custom_theme: Optional[Theme] = None
console: Console
print_func = builtins.print  # Default to standard print

# Check if the theme file exists and load it
if theme_file_path.exists():
    try:
        # Load theme using Rich's Theme.from_file method
        with open(theme_file_path, encoding="utf-8") as tf:
            custom_theme = Theme.from_file(tf, source=str(theme_file_path))
        console = Console(theme=custom_theme)
        print_func = console.print  # Use console.print if theme loaded
        console.log(f"Successfully loaded theme from [file]{theme_file_path}[/]", style="success")
    except Exception as e:
        builtins.print(f"⛔ Error loading theme from {theme_file_path}: {e}")
        builtins.print("⛔ Falling back to basic default theme.")
        custom_theme = Theme(default_theme_dict)  # Use basic dict fallback
        console = Console(theme=custom_theme)
else:
    builtins.print(f"⛔ Theme file not found at {theme_file_path}. Using basic default theme.")
    custom_theme = Theme(default_theme_dict)  # Use basic dict fallback
    console = Console(theme=custom_theme)

# --- Pretty Tracebacks ---
# Installs a handler to format tracebacks using Rich
install_traceback(
    console=console,
    show_locals=False,  # Set show_locals=True for more detailed debugging
)

# --- Convenience print ---
# Allows using `print` instead of `console.print` in other modules
_print = console.print


def print(*args, **kwargs):
    """Wrapper for console.print using the themed console."""
    return _print(*args, **kwargs)


# MARK: - EXPORTS
# Export the configured console instance and commonly used Rich components
# Other modules can import these directly from pixabit.utils.display
__all__ = [
    "console",
    "print_func",  # Keep original name for clarity if needed elsewhere
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
    "Spinner",
    "BarColumn",
    "TextColumn",
    "TimeElapsedColumn",
    "TimeRemainingColumn",
    "TaskProgressColumn",
    "SpinnerColumn",
    "Markdown",
    "Text",
    "ART_AVAILABLE",
    "text2art",
    "Syntax",
]
