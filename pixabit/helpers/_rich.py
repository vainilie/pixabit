# pixabit/helpers/_rich.py

# SECTION: MODULE DOCSTRING
"""Initializes and configures the Rich Console instance with a custom theme.

Loads theme definitions from a specified file ('styles' by default), handles
potential loading errors by falling back to a default theme. Exports the
configured 'console' instance and commonly used Rich components for consistent
UI elements across the application. Also installs Rich tracebacks.
"""

# SECTION: IMPORTS
import builtins
import logging  # Use standard logging for internal messages here
import sys
from pathlib import Path
from typing import Any, Optional, TextIO  # Added TextIO

# Rich Imports
from rich import box
from rich.columns import Columns
from rich.console import Console, ConsoleRenderable
from rich.highlighter import ReprHighlighter  # Useful for debugging
from rich.layout import Layout
from rich.live import Live
from rich.logging import RichHandler
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
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme, ThemeStack  # Import ThemeStack for fallback
from rich.traceback import install as install_traceback

# Optional art import
try:
    from art import text2art

    ART_AVAILABLE = True
except ImportError:
    ART_AVAILABLE = False

    # Define dummy function if art not installed
    def text2art(*args: Any, **kwargs: Any) -> str:
        """Dummy text2art function when 'art' library is not available."""
        logging.warning("'art' library not found, ASCII art disabled.")
        # Return the first arg if it's the text, otherwise a default
        return str(args[0]) if args else "Pixabit"


# SECTION: PATHS AND DEFAULTS

# Define theme filename
THEME_FILENAME = "styles.theme"  # Use a descriptive extension

# Determine base directory more robustly
# Assumes this file is in pixabit/helpers/
try:
    _current_file_path = Path(__file__).resolve()
    # Go up two levels from pixabit/helpers/_rich.py to project root
    _project_root = _current_file_path.parent.parent.parent
    # Look for theme file in project_root/themes/ or project_root/
    _theme_search_paths = [
        _project_root / "themes" / THEME_FILENAME,
        _project_root / THEME_FILENAME,
        _current_file_path.parent / THEME_FILENAME,  # Fallback next to this file
    ]
except NameError:  # Fallback if __file__ is not defined (e.g., interactive)
    _project_root = Path.cwd()
    _theme_search_paths = [
        Path("themes") / THEME_FILENAME,
        Path(THEME_FILENAME),
    ]

# Find the first existing theme file
theme_file_path: Path | None = next((p for p in _theme_search_paths if p.is_file()), None)


# Default theme dictionary (simplified fallback based on names in styles file)
DEFAULT_THEME_DICT = {
    "bar.complete": "#a6e3a1",
    "bar.finished": "#74c7ec",
    "bar.pulse": "#f5c2e7",
    "danger": "bold #eb6f92 on #e0def4",
    "debug": "dim #908caa",
    "dim": "dim",
    "error": "bold #f38ba8",
    "field": "dim",
    "file": "underline #b4bdf8",
    "highlight": "bold #eb6f92",
    "info": "bold #cba6f7",
    "keyword": "bold #c4a7e7",
    "link_style": "underline #89b4fa",
    "log.level.debug": "dim #908caa",
    "log.level.error": "bold #f38ba8",
    "log.level.info": "#cba6f7",
    "log.level.warning": "bold #f6c177",
    "progress.description": "#e0def4",
    "progress.percentage": "#9ccfd8",
    "progress.remaining": "#f6c177",
    "prompt.choices": "#94e2d5",
    "prompt.default": "#7f849c",
    "prompt.invalid": "#f38ba8",
    "regular": "default",
    "repr.bool_false": "bold #f38ba8",
    "repr.bool_true": "bold #a6e3a1",
    "repr.none": "dim #908caa",
    "repr.number": "#fab387",
    "repr.str": "#a6e3a1",
    "repr.url": "underline #89b4fa",
    "rp_foam": "#9ccfd8",
    "rp_gold": "#f6c177",
    "rp_iris": "#c4a7e7",
    "rp_love": "#eb6f92",
    "rp_muted": "#6e6a86",
    "rp_overlay": "#26233a",
    "rp_pine": "#31748f",
    "rp_rose": "#ebbcba",
    "rp_subtle_color": "#908caa",
    "rp_surface": "#1f1d2e",
    "rp_text": "#e0def4",
    "rule.line": "#45475A",
    "subtle": "dim #908caa",
    "success": "bold #a6e3a1",
    "table.header": "bold #cba6f7",
    "warning": "bold #f6c177",
}

# SECTION: THEME LOADING AND CONSOLE INITIALIZATION

# Initialize console with fallback theme stack first
_fallback_theme = Theme(DEFAULT_THEME_DICT)
console: Console = Console(
    theme=_fallback_theme,
    color_system="auto",  # Prueba con "standard", "256" o "truecolor" si "auto" no funciona
    highlight=False,
    width=None,  # Ajusta al ancho de la terminal
    emoji=False,
)
_custom_theme_loaded = False

if theme_file_path:
    try:
        # Attempt to load theme from file
        custom_theme = Theme.read(str(theme_file_path))  # Use Theme.read for direct loading
        _fallback_theme.push(custom_theme)  # Push loaded theme on top
        _custom_theme_loaded = True
        # Use standard logging here as the logger helper might depend on this console
        logging.info(f"Successfully loaded theme from '{theme_file_path}'")
    except Exception as e:
        # Use builtins.print for critical fallback messages before console is fully trusted
        builtins.print(
            f"WARNING: Error loading theme from '{theme_file_path}': {e}",
            file=sys.stderr,
        )
        builtins.print("WARNING: Falling back to default theme.", file=sys.stderr)
        # Fallback theme is already in the stack
else:
    logging.warning(f"Theme file '{THEME_FILENAME}' not found in search paths. Using default theme.")

# Use the configured console for subsequent operations
_themed_print = console.print  # Capture the themed print method

# SECTION: PRETTY TRACEBACKS
# Installs a handler to format tracebacks using the configured Rich console
try:
    install_traceback(
        console=console,
        show_locals=False,  # Set True for detailed debugging if needed
        word_wrap=True,  # Enable word wrap for tracebacks
        width=None,  # Let Rich determine width based on console
        suppress=[],  # Add libraries to suppress frames from (e.g., ['click'])
    )
    logging.debug("Rich traceback handler installed.")
except Exception as e:
    logging.error(f"Failed to install Rich tracebacks: {e}")

# SECTION: CONVENIENCE PRINT FUNCTION


# Define a wrapper function 'print' that uses the themed console's print method.
# This allows other modules to just use `from pixabit.helpers._rich import print`.
# Use different name internally to avoid recursion errors.
def print(*args: Any, **kwargs: Any) -> None:
    """Prints to the configured Rich console using the loaded theme.

    Provides a convenient way to access `console.print` throughout the application.

    Args:
        *args: Positional arguments passed to `rich.console.Console.print`.
        **kwargs: Keyword arguments passed to `rich.console.Console.print`.
    """
    # Call the internal themed print function captured earlier
    _themed_print(*args, **kwargs)


# SECTION: EXPORTS
# Export the configured console instance and commonly used Rich components
# Other modules can import these directly from pixabit.helpers._rich
__all__ = [
    "console",  # The configured Console instance
    "print",  # The themed print function wrapper
    # Rich UI Components
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
    "Markdown",
    "Text",
    "Syntax",
    "ReprHighlighter",
    # Progress Bar Columns
    "SpinnerColumn",
    "BarColumn",
    "TextColumn",
    "TimeElapsedColumn",
    "TimeRemainingColumn",
    "TaskProgressColumn",
    # Base Types / Theming
    "Theme",
    "ConsoleRenderable",
    "RichHandler",  # Export RichHandler type for use in logger setup
    # Optional ASCII Art
    "ART_AVAILABLE",
    "text2art",
]
