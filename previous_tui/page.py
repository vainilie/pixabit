# previous_tui_files/page.py (GENERIC EXAMPLE - Not App Specific)

# SECTION: MODULE DOCSTRING
"""GENERIC EXAMPLE: Utility screens for displaying code (CodeScreen) and a base
PageScreen with a 'Show Code' binding. Not directly required for Pixabit's
core functionality but could be adapted if needed later.
"""

# SECTION: IMPORTS
import inspect
from typing import Optional  # Added Optional

# Third-party Imports
try:
    from rich.syntax import Syntax
except ImportError:
    Syntax = None  # type: ignore

# Textual Imports
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import ModalScreen, Screen
from textual.widgets import Static


# SECTION: CODE SCREEN (Modal)
# KLASS: CodeScreen
class CodeScreen(ModalScreen[None]):  # Add return type hint
    """A modal screen for displaying code with syntax highlighting."""

    DEFAULT_CSS = """
    CodeScreen {
        align: center middle; /* Center the modal */
    }
    #code-container { /* Changed ID for clarity */
        width: 80%;
        height: 80%;
        border: thick $accent;
        background: $surface;
    }
    #code-content { /* Target the Static widget holding the code */
        width: auto; /* Allow code to determine width */
        height: auto;
        padding: 1 2;
    }
    ScrollableContainer { /* Style the scrollbar */
         scrollbar-gutter: stable;
    }
    """
    BINDINGS = [
        ("escape", "dismiss", "Dismiss code")
    ]  # Dismiss action closes modal

    # FUNC: __init__
    def __init__(self, title: str, code: str, lexer: str = "python") -> None:
        """Initialize the code screen.

        Args:
            title: The title to display for the code.
            code: The code string to display.
            lexer: The lexer to use for syntax highlighting (default: 'python').
        """
        super().__init__()
        self.code_title = (
            title  # Use different attribute name from Screen.title
        )
        self.code = code
        self.lexer = lexer

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Create the code display area."""
        syntax_widget = Static(
            "Loading code...", expand=True, id="code-content"
        )
        if Syntax is not None:  # Check if Rich Syntax is available
            syntax = Syntax(
                self.code,
                self.lexer,
                theme="github-dark",  # Example theme
                line_numbers=True,
                word_wrap=False,
                indent_guides=True,
            )
            syntax_widget = Static(syntax, expand=True, id="code-content")

        container = ScrollableContainer(syntax_widget, id="code-container")
        container.border_title = self.code_title
        container.border_subtitle = "Press Esc to close"
        yield container

    # action_dismiss is handled by ModalScreen automatically for 'escape'


# SECTION: PAGE SCREEN (Base Class Example)
# KLASS: PageScreen
class PageScreen(Screen):
    """Generic base screen with a 'Show Code' binding."""

    DEFAULT_CSS = """
    PageScreen {
        /* Base styling for pages */
        padding: 1 2;
    }
    """
    BINDINGS = [
        Binding(
            "c", "show_code", "Code", tooltip="Show source code for this screen"
        ),
    ]

    # Worker to get source code (can be kept if feature desired)
    @work(thread=True)
    def get_code(self, source_file: str) -> str | None:
        """Reads code from disk in a thread. Returns None on error."""
        try:
            with open(source_file, encoding="utf-8") as file_:
                return file_.read()
        except Exception as e:
            self.log.error(f"Failed to read source file {source_file}: {e}")
            return None

    # Action to show the code modal
    async def action_show_code(self) -> None:
        """Shows the source code for the current screen in a modal."""
        source_file = inspect.getsourcefile(self.__class__)
        if source_file is None:
            self.app.notify(
                "Could not determine source file.",
                title="Show Code",
                severity="error",
            )
            return

        code = await self.get_code(source_file).wait()  # Run worker and wait
        if code is None:
            self.app.notify(
                "Could not read source code.",
                title="Show Code",
                severity="error",
            )
        else:
            # Assume file path is suitable for title, maybe shorten it
            title = f"Code: {Path(source_file).name}"
            await self.app.push_screen(CodeScreen(title, code))
