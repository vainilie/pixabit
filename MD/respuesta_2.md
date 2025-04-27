Okay, let's continue refactoring the remaining files.

---

## `pixabit/test/DataTableSample.py`

**Refactored Code:**

```python
# pixabit/test/DataTableSample.py

# SECTION: MODULE DOCSTRING
"""
Textual App Example: Displaying Formatted Data in a DataTable.

Demonstrates using markdown-it-py to parse Markdown strings and render
them as Rich Text within DataTable cells and a separate details panel.

NOTE: This appears to be an example or test script, not part of the core library.
      Consider moving to an 'examples/' directory.
"""

# SECTION: IMPORTS
from typing import Any # Use standard Any

# Markdown Parsing
try:
    import markdown_it
    from markdown_it.token import Token
    MARKDOWN_IT_AVAILABLE = True
except ImportError:
    MARKDOWN_IT_AVAILABLE = False
    Token = object # Dummy type

# Rich Integration
from rich.markdown import Markdown as RichMarkdown # Alias to avoid confusion
from rich.style import Style
from rich.text import Text

# Textual UI
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Static
from textual.widgets._data_table import RowKey # Import RowKey for event handling

# SECTION: APPLICATION CLASS

# KLASS: MarkdownTableApp
class MarkdownTableApp(App[None]):
    """Textual app showcasing Markdown rendering in DataTable and Static widgets."""

    # --- Configuration ---
    CSS_PATH = "datatable_sample.tcss" # Example CSS path if needed
    # Minimal CSS for layout
    DEFAULT_CSS = """
    Screen {
        layout: horizontal;
    }
    #table-container {
        width: 40%;
        height: 100%;
        border-right: thick $accent;
        overflow: hidden; /* Contain table */
    }
    #details-container {
        width: 1fr; /* Fill remaining space */
        height: 100%;
        overflow-y: auto; /* Allow scrolling for details */
    }
    #details-title {
        padding: 1;
        background: $accent-darken-2;
        text-align: center;
        dock: top; /* Keep title at top */
        border-bottom: thin $accent;
    }
    #markdown-content {
        padding: 1 2;
    }
    DataTable {
        height: 1fr; /* Fill space below title in table container */
    }
    """

    BINDINGS = [
        Binding(key="q", action="quit", description="Quit"),
        Binding(key="escape", action="quit", description="Quit"),
    ]

    # --- Initialization ---
    def __init__(self):
        super().__init__()
        if not MARKDOWN_IT_AVAILABLE:
            raise RuntimeError("This example requires 'markdown-it-py' to be installed.")
        # Initialize the markdown parser instance
        self.md_parser = markdown_it.MarkdownIt("commonmark", {"breaks": True, "html": False})
        self.md_parser.enable("strikethrough") # Enable strikethrough

        # Sample data
        self.items_data = [
            {
                "id": "1",
                "title": "**Introducción** a Python",
                "description": "Lenguaje de *programación* `versátil`",
                "markdown_content": "# Introducción a Python\n\nPython es un lenguaje...", # Keep content short for brevity
            },
            {
                "id": "2",
                "title": "Aprendiendo `Textual` para **TUI**",
                "description": "*Framework* **TUI** para Python",
                "markdown_content": "# Framework Textual\n\nTextual es un framework...",
            },
            {
                "id": "3",
                "title": "Markdown en *Rich* con `código`",
                "description": "~~Básico~~ -> **Avanzado** y *completo*",
                "markdown_content": "# Markdown en Rich\n\nRich permite renderizar...",
            },
        ]

    # --- Widget Composition ---
    def compose(self) -> ComposeResult:
        yield Header()
        # Main layout uses default Screen layout (horizontal)
        with Vertical(id="table-container"):
            yield Static("Select Item", id="table-title", classes="details-title") # Reused style
            yield DataTable(id="items-table")
        with Vertical(id="details-container"):
            yield Static("Details", id="details-title", classes="details-title")
            # Use Static for markdown, update content on selection
            yield Static(id="markdown-content", markup=False) # Start without markup
        yield Footer()

    # --- Event Handling & Logic ---
    def on_mount(self) -> None:
        """Called after the DOM is ready. Populate the DataTable."""
        try:
            table = self.query_one("#items-table", DataTable)
            table.cursor_type = "row" # Highlight the entire row

            # Add columns using Rich Text for headers
            table.add_column("ID", key="id") # Give key for potential later use
            table.add_column(self.markdown_to_rich_text("**Título**"), key="title")
            table.add_column(self.markdown_to_rich_text("*Descripción*"), key="description")

            # Add rows using Rich Text for cells
            for item in self.items_data:
                 table.add_row(
                      item["id"],
                      self.markdown_to_rich_text(item["title"]),
                      self.markdown_to_rich_text(item["description"]),
                      key=item["id"] # Use item ID as the row key
                 )
            # Initial details view
            self.update_details(self.items_data[0])

        except Exception as e:
            self.log.error(f"Error during table mount: {e}")


    @on(DataTable.RowSelected)
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the DataTable."""
        selected_row_key: RowKey | None = event.row_key
        self.log(f"Row Selected: key={selected_row_key}")

        if selected_row_key is not None:
            # Find the item data corresponding to the selected row key
            selected_item = next(
                (item for item in self.items_data if item["id"] == selected_row_key.value),
                None,
            )
            if selected_item:
                self.update_details(selected_item)
            else:
                 self.log.warning(f"No item data found for selected row key: {selected_row_key.value}")

    # FUNC: update_details
    def update_details(self, item_data: dict[str, Any]) -> None:
        """Updates the details panel with the selected item's information."""
        try:
             details_title = self.query_one("#details-title", Static)
             # Update title using Rich Text for consistency
             details_title.update(self.markdown_to_rich_text(f"Detalles: {item_data['title']}"))

             # Update the markdown content area
             markdown_content_widget = self.query_one("#markdown-content", Static)
             # Use Rich's Markdown class for rendering the main content area
             # This leverages Rich's more complete Markdown features
             rendered_markdown = RichMarkdown(item_data["markdown_content"])
             markdown_content_widget.update(rendered_markdown)
             self.log(f"Updated details panel for item ID: {item_data['id']}")
        except Exception as e:
             self.log.error(f"Error updating details panel: {e}")


    # --- Markdown to Rich Text Conversion (using markdown-it-py) ---
    # FUNC: markdown_to_rich_text
    def markdown_to_rich_text(self, markdown_str: str) -> Text:
        """Converts a simple Markdown string to a Rich Text object using markdown-it-py.

        Handles basic inline formatting like bold, italic, code, strikethrough.

        Args:
            markdown_str: The Markdown string to convert.

        Returns:
            A Rich Text object.
        """
        if not markdown_str:
            return Text()

        try:
            tokens = self.md_parser.parse(markdown_str.strip())
            result = Text()
            self._process_inline_tokens(tokens, result, Style())
            return result
        except Exception as e:
            self.log.error(f"Error converting Markdown to Rich Text: {e}")
            return Text(markdown_str) # Fallback to plain text

    # FUNC: _process_inline_tokens
    def _process_inline_tokens(self, tokens: list[Token], text_obj: Text, current_style: Style):
        """Recursively processes markdown-it tokens to build Rich Text (Inline focus)."""
        for token in tokens:
            if token.type == "inline" and token.children:
                # Process children with the current style
                self._process_inline_tokens(token.children, text_obj, current_style)
                continue

            new_style = current_style
            content = token.content if hasattr(token, 'content') else ''

            if token.type == "text":
                text_obj.append(content, style=current_style)
            elif token.type == "strong_open":
                # Create a new style by combining with bold
                style_stack = current_style + Style(bold=True)
                self._process_inline_tokens(token.children or [], text_obj, style_stack) # Process children with new style
            elif token.type == "em_open":
                 style_stack = current_style + Style(italic=True)
                 self._process_inline_tokens(token.children or [], text_obj, style_stack)
            elif token.type == "code_inline":
                # Apply code style directly, doesn't usually nest well
                text_obj.append(content, style=Style(bgcolor="#303030", color="#a6da95")) # Example style
            elif token.type == "s_open": # Strikethrough
                 style_stack = current_style + Style(strike=True)
                 self._process_inline_tokens(token.children or [], text_obj, style_stack)
            # Ignore closing tags here as styles are managed via recursion/stack


# SECTION: MAIN EXECUTION
if __name__ == "__main__":
    app = MarkdownTableApp()
    app.run()

```

**Suggestions & Comments:**

1.  **Purpose:** Added note clarifying this is an example script.
2.  **Typing:** Updated typing (`Any`, `|`).
3.  **Imports:** Standardized imports. Imported `RowKey`. Alias `RichMarkdown`.
4.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:` anchors.
5.  **CSS:** Defined `DEFAULT_CSS` directly in the app for self-containment of the example. Used Textual CSS variables (`$accent` etc.). Improved layout using `1fr` and explicit `overflow`. Docked title widgets.
6.  **`markdown-it` Check:** Added check during `__init__` to ensure `markdown-it-py` is installed.
7.  **DataTable Population:** Populates the table in `on_mount`. Uses the item's `id` as the `RowKey` for reliable selection handling.
8.  **Details Panel Update:**
    - Created `update_details` method for clarity.
    - Updates the title using `markdown_to_rich_text`.
    - Uses Rich's `Markdown` class (`RichMarkdown`) to render the main `markdown_content`. This is generally better for larger content as it handles more block elements correctly than the simple inline parser.
9.  **`markdown_to_rich_text`:**
    - Refined this helper to focus primarily on _inline_ formatting suitable for table cells/titles. It iterates through tokens, applying styles additively for bold/italic/strikethrough.
    - Simplified the recursive logic slightly. It now passes the combined style down.
    - Added basic error handling.
10. **Event Handling:** Uses `@on(DataTable.RowSelected)` decorator. Correctly extracts the row key value.
11. **Redundancy:** This script is very similar in purpose and partial implementation to `test/prev_mdrichconverter.py`. You should likely choose one or merge them and remove the duplicate.

---

## `pixabit/test/de_chatgppti.py`

**Refactored Code:**

````python
# pixabit/test/de_chatgppti.py

# SECTION: MODULE DOCSTRING
"""
Alternative Markdown to Rich Text Conversion Example.

This script provides another approach to converting Markdown to Rich Text objects,
using markdown-it-py tokens and managing styles via a dictionary.

NOTE: This appears to be an example or test script, potentially generated or experimental.
      Compare with `_md_to_rich.py` and choose one consistent approach for the main application.
      Consider moving to an 'examples/' directory.
"""

# SECTION: IMPORTS
from typing import Any, Dict, List, Optional, Sequence # Use standard types

# Markdown parsing
try:
    import markdown_it
    from markdown_it.token import Token
    MARKDOWN_IT_AVAILABLE = True
except ImportError:
    MARKDOWN_IT_AVAILABLE = False
    Token = object # Dummy type

# Rich rendering
from rich.console import Console
from rich.markdown import Markdown as RichMarkdown # Alias
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

# Textual integration (optional)
try:
    from textual.widgets import Static
    TEXTUAL_AVAILABLE = True
except ImportError:
    Static = object # Dummy type
    TEXTUAL_AVAILABLE = False

# Use themed console if available from helpers (adjust path if necessary)
try:
    # Assumes helpers are potentially one or two levels up depending on execution context
    try: from ..helpers._rich import console
    except ImportError: from pixabit.helpers._rich import console # Fallback path
except ImportError:
    # Basic console fallback if helpers aren't found
    class PrintConsole:
        def print(self, *args, **kwargs): print(*args)
    console = PrintConsole() # type: ignore


# SECTION: UTILITY FUNCTIONS

# FUNC: escape_rich
def escape_rich(text: str) -> str:
    """Escape Rich markup control characters (square brackets)."""
    return text.replace("[", r"\[").replace("]", r"\]") if text else ""


# SECTION: MARKDOWN RENDERER CLASS

# KLASS: MarkdownRenderer (Alternative Implementation)
class MarkdownRenderer:
    """Converts Markdown to Rich Text using a style dictionary approach."""

    # Define default styles (similar to the other renderer)
    DEFAULT_STYLES = {
        "h1": Style(bold=True, color="cyan", underline=True),
        "h2": Style(bold=True, color="bright_cyan"),
        "h3": Style(bold=True, color="blue"),
        "h4": Style(underline=True, color="bright_blue"),
        "h5": Style(italic=True, color="blue"),
        "h6": Style(italic=True, dim=True),
        "strong": Style(bold=True),
        "em": Style(italic=True),
        "code_inline": Style(bgcolor="#303030", color="#a6da95"), # Example style
        "code_block": Style(dim=True),
        "strike": Style(strike=True),
        "link": Style(underline=True, color="bright_blue"),
        "blockquote": Style(italic=True, color="green"),
        "hr": Style(color="bright_black", dim=True),
    }

    # FUNC: __init__
    def __init__(self, custom_styles: dict[str, Style] | None = None):
        """Initialize the renderer."""
        if not MARKDOWN_IT_AVAILABLE:
            raise ImportError("MarkdownRenderer requires 'markdown-it-py'.")

        self.md_parser = markdown_it.MarkdownIt("commonmark", {"breaks": True, "html": False})
        self.md_parser.enable("strikethrough")

        self.styles = self.DEFAULT_STYLES.copy()
        if custom_styles:
            self.styles.update(custom_styles)

    # --- Style Dictionary Helpers ---
    def _update_style_dict(self, style_dict: dict[str, Any], style_to_add: Style):
        """Merges attributes from a Style object into a dictionary."""
        # Iterate through common style attributes
        # This approach might not perfectly handle complex style interactions
        for attr in ["color", "bgcolor", "bold", "dim", "italic", "underline", "blink", "reverse", "conceal", "strike", "link"]:
            value = getattr(style_to_add, attr, None)
            if value is not None: # Only add if the attribute is explicitly set
                style_dict[attr] = value

    def _remove_style_dict(self, style_dict: dict[str, Any], style_to_remove: Style):
        """Removes attributes defined in style_to_remove from the dictionary."""
        for attr in ["color", "bgcolor", "bold", "dim", "italic", "underline", "blink", "reverse", "conceal", "strike", "link"]:
            if getattr(style_to_remove, attr, None) is not None:
                style_dict.pop(attr, None) # Remove the key if it exists

    # --- Conversion Core ---
    # FUNC: markdown_to_rich_text
    def markdown_to_rich_text(self, markdown_str: str) -> Text:
        """Convert Markdown string to a Rich Text object."""
        if not markdown_str:
            return Text()

        tokens = self.md_parser.parse(markdown_str)
        result = Text()
        self._process_tokens(tokens, result) # Start with empty style dict
        return result

    # FUNC: _process_tokens
    def _process_tokens(
        self,
        tokens: Sequence[Token],
        text_obj: Text,
        current_styles_dict: dict[str, Any] | None = None, # Use a dict to track styles
    ) -> None:
        """Process markdown-it tokens and apply styles using a dictionary."""
        if current_styles_dict is None:
            current_styles_dict = {}

        i = 0
        while i < len(tokens):
            token = tokens[i]

            # Handle inline tokens with children recursively
            if token.type == "inline" and token.children:
                # Pass a copy of the styles dict to the children
                self._process_tokens(token.children, text_obj, current_styles_dict.copy())
                i += 1
                continue

            # Handle specific token types
            elif token.type.startswith("heading_open"):
                level = int(token.tag[1])
                heading_style = self.styles.get(f"h{level}", Style())
                # Create a style dict specifically for this heading's content
                heading_styles = current_styles_dict.copy()
                self._update_style_dict(heading_styles, heading_style)

                # Process the inline content of the heading
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    heading_text = Text()
                    # Pass the specific heading style dict
                    self._process_tokens([tokens[i + 1]], heading_text, heading_styles)
                    if text_obj and not text_obj.plain.endswith('\n'): text_obj.append("\n")
                    text_obj.append(heading_text)
                    text_obj.append("\n") # Newline after heading
                    i += 3 # Skip heading_open, inline, heading_close
                    continue
                else: # Should not happen with valid markdown
                    i += 1
                    continue

            elif token.type == "text":
                # Create a Style object from the current dictionary
                # Handle the 'url' attribute specifically if present for links
                active_style = Style(**current_styles_dict)
                text_obj.append(token.content, active_style)

            # --- Style Modifiers ---
            elif token.type == "strong_open":
                self._update_style_dict(current_styles_dict, self.styles.get("strong", Style()))
            elif token.type == "strong_close":
                self._remove_style_dict(current_styles_dict, self.styles.get("strong", Style()))

            elif token.type == "em_open":
                 self._update_style_dict(current_styles_dict, self.styles.get("em", Style()))
            elif token.type == "em_close":
                 self._remove_style_dict(current_styles_dict, self.styles.get("em", Style()))

            elif token.type == "s_open": # Strikethrough
                 self._update_style_dict(current_styles_dict, self.styles.get("strike", Style()))
            elif token.type == "s_close":
                 self._remove_style_dict(current_styles_dict, self.styles.get("strike", Style()))

            elif token.type == "link_open":
                 link_style = self.styles.get("link", Style())
                 self._update_style_dict(current_styles_dict, link_style)
                 # Add link URL directly to the style dict (handled by Style(**dict))
                 if "href" in token.attrs:
                      current_styles_dict["link"] = token.attrs["href"]
            elif token.type == "link_close":
                 self._remove_style_dict(current_styles_dict, self.styles.get("link", Style()))
                 current_styles_dict.pop("link", None) # Remove link attribute

            # --- Other Elements ---
            elif token.type == "code_inline":
                # Apply style directly for inline code
                text_obj.append(token.content, self.styles.get("code_inline", Style()))

            elif token.type == "code_block" or token.type == "fence":
                # Append block content with dedicated style
                if text_obj and not text_obj.plain.endswith('\n'): text_obj.append("\n")
                text_obj.append(token.content.rstrip(), self.styles.get("code_block", Style()))
                text_obj.append("\n")

            elif token.type == "blockquote_open":
                # Add prefix and process children with blockquote style applied
                # (This requires adjusting the recursive call slightly)
                blockquote_style = self.styles.get("blockquote", Style())
                text_obj.append("> ", blockquote_style)
                # TODO: Refactor needed here to properly pass the blockquote style down
                # For now, only the prefix gets the style.
                pass # Let children be processed with potentially incorrect style

            elif token.type == "hr":
                 if text_obj and not text_obj.plain.endswith('\n'): text_obj.append("\n")
                 text_obj.append("─" * console.width, self.styles.get("hr", Style()))
                 text_obj.append("\n\n")

            elif token.type in ("paragraph_close", "blockquote_close", "heading_close"):
                 # Add spacing after block elements
                 if text_obj and not text_obj.plain.endswith("\n\n"):
                     if text_obj.plain.endswith("\n"): text_obj.append("\n")
                     else: text_obj.append("\n\n")

            elif token.type == "hardbreak":
                 text_obj.append("\n")
            elif token.type == "softbreak":
                 text_obj.append(" ") # Render soft breaks as spaces

            # Increment index for next token
            i += 1

    # --- Convenience Rendering Methods ---
    # FUNC: render_to_console
    def render_to_console(
        self, markdown_str: str, target_console: Console | None = None
    ) -> None:
        """Render markdown directly to a Rich console."""
        con = target_console or console
        rich_text = self.markdown_to_rich_text(markdown_str)
        con.print(rich_text)

    # FUNC: render_to_panel
    def render_to_panel(
        self, markdown_str: str, title: str | None = None, **panel_kwargs: Any
    ) -> Panel:
        """Render markdown inside a Rich panel."""
        rich_text = self.markdown_to_rich_text(markdown_str)
        return Panel(rich_text, title=title, **panel_kwargs)


# SECTION: TEXTUAL WIDGET (Optional)

if TEXTUAL_AVAILABLE and MARKDOWN_IT_AVAILABLE:

    # KLASS: MarkdownStatic (Alternative Implementation)
    class MarkdownStatic(Static):
        """Textual Static widget rendering Markdown via this renderer implementation."""
        markdown = reactive("", layout=True)

        # FUNC: __init__
        def __init__(
            self,
            markdown: str = "",
            renderer: MarkdownRenderer | None = None,
            *args: Any, **kwargs: Any,
        ):
            super().__init__("", *args, **kwargs)
            self._renderer = renderer or MarkdownRenderer()
            self.markdown = markdown # Set reactive property

        # FUNC: watch_markdown
        def watch_markdown(self, new_markdown: str) -> None:
            """Update widget when markdown content changes."""
            rich_text = self._renderer.markdown_to_rich_text(new_markdown)
            self.update(rich_text)


# SECTION: EXPORTS
__all__ = ["MarkdownRenderer", "escape_rich"]
if TEXTUAL_AVAILABLE and MARKDOWN_IT_AVAILABLE:
    __all__.append("MarkdownStatic")

# SECTION: EXAMPLE USAGE
if __name__ == "__main__":
     print("--- Markdown Renderer Example (de_chatgppti.py approach) ---")
     renderer = MarkdownRenderer()
     test_md = """
# Main Title

This is **bold** and *italic*. Here is `inline code`.
This is ~~strikethrough~~.

## Subtitle

> A blockquote example.
> With multiple lines.

A paragraph with a [link](https://example.com).

```python
# A code block
def main():
     print("Hello")
````

---

Another paragraph.
"""
print("\n--- Rendering to Console ---")
renderer.render_to_console(test_md)

     print("\n--- Rendering to Panel ---")
     panel = renderer.render_to_panel(test_md, title="Test Panel")
     console.print(panel)

     print("\n--- Generating Rich Text Object ---")
     rich_text_obj = renderer.markdown_to_rich_text(test_md)
     print(rich_text_obj)
     # print(repr(rich_text_obj)) # For detailed inspection

````

**Suggestions & Comments:**

1.  **Purpose:** Clarified in the docstring that this is an alternative implementation and likely an example/test script.
2.  **Typing:** Updated typing (`|`, `list`, `dict`, `Sequence`).
3.  **Imports:** Standardized imports. Adjusted path for helper imports.
4.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:` anchors.
5.  **Style Handling:** This version uses a dictionary (`current_styles_dict`) passed down recursively to manage styles, along with helper functions (`_update_style_dict`, `_remove_style_dict`). This approach can become complex to manage correctly for deeply nested styles compared to the stack-based approach in `_md_to_rich.py`.
6.  **Logic (`_process_tokens`):**
    *   The logic for handling different token types is present but relies heavily on modifying the `current_styles_dict`.
    *   Nested elements might not inherit or shed styles perfectly with this dictionary manipulation approach, especially compared to a style stack.
    *   Blockquote styling is noted as incomplete (only styles the ">").
7.  **Comparison:** This implementation is functionally similar to `_md_to_rich.py` but uses a different internal mechanism for style tracking. The stack-based approach in `_md_to_rich.py` is generally considered more robust for handling nested formatting. You should choose **one** consistent renderer for your main application (`_md_to_rich.py` seems preferable based on its refinement).
8.  **Example Usage:** Added an `if __name__ == "__main__":` block to demonstrate this specific renderer.

***

## `pixabit/test/message.py` (Custom Textual Messages)

**Refactored Code:**

```python
# pixabit/tui/messages.py (Renamed and moved to tui?)

# SECTION: MODULE DOCSTRING
"""
Defines custom Textual Message classes for application-specific events.

These messages facilitate communication between different components (e.g.,
DataStore -> App, Widgets -> App).
"""

# SECTION: IMPORTS
from typing import Any # Keep Any if needed for future message data

from textual.message import Message # Import base class

# SECTION: MESSAGE CLASSES

# KLASS: DataRefreshed
class DataRefreshed(Message):
    """Event published by DataStore when data refresh process completes.

    Attributes:
        success: Indicates if the overall refresh (especially critical data) succeeded.
        message: Optional status message providing more context.
    """
    # Add attributes to convey status
    def __init__(self, success: bool, message: str | None = None) -> None:
        self.success: bool = success
        self.message: str | None = message
        super().__init__()

    def __repr__(self) -> str:
        msg = f", message='{self.message}'" if self.message else ""
        return f"DataRefreshed(success={self.success}{msg})"


# KLASS: UIMessageRequest (Renamed from UIMessage for clarity)
class UIMessageRequest(Message):
    """Request to display a notification message in the UI (e.g., using App.notify).

    Attributes:
        text: The main message content.
        title: Optional title for the notification.
        severity: Severity level ('information', 'warning', 'error').
        timeout: Optional duration (seconds) for the notification.
    """
    DEFAULT_SEVERITY = "information"
    DEFAULT_TIMEOUT = 4.0

    def __init__(
        self,
        text: str,
        title: str = "Info",
        severity: str = DEFAULT_SEVERITY,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.text: str = text
        self.title: str = title
        self.severity: str = severity
        self.timeout: float = timeout
        super().__init__()

    def __repr__(self) -> str:
        return f"UIMessageRequest(title='{self.title}', severity='{self.severity}', text='{self.text[:50]}...')"

# KLASS: ShowStatusRequest
class ShowStatusRequest(Message):
    """Request to update a dedicated status bar or area."""
    def __init__(self, status_text: str, temporary: bool = False, duration: float = 5.0):
        self.status_text = status_text
        self.temporary = temporary
        self.duration = duration
        super().__init__()

# KLASS: ErrorOccurred
class ErrorOccurred(Message):
     """Generic message to signal an error happened, potentially with details."""
     def __init__(self, source: str, error: Exception, details: Any | None = None):
          self.source = source # Where the error originated (e.g., "API", "DataStore")
          self.error = error # The exception object
          self.details = details # Optional additional context
          super().__init__()

# Add other application-specific messages as needed:
# e.g., TaskScored, UserLoggedIn, ChallengeLeft, etc.

````

**Suggestions & Comments:**

1.  **Location & Naming:** Renamed the file to `messages.py` and suggested moving it to `pixabit/tui/messages.py` as these are specific to the TUI's event system. Renamed `UIMessage` to `UIMessageRequest` to clarify its intent (a request _to_ the UI).
2.  **Typing:** Standard typing.
3.  **Comments:** Added `# SECTION:`, `# KLASS:` anchors and improved docstrings.
4.  **`DataRefreshed`:** Added a `success: bool` attribute and an optional `message: str` attribute to provide more context about the refresh outcome when the App receives this event. Added `__repr__`.
5.  **`UIMessageRequest`:** Added a `timeout` attribute. Set defaults as constants. Added `__repr__`.
6.  **New Messages:** Added examples `ShowStatusRequest` and `ErrorOccurred` to illustrate other potential custom messages useful in a TUI app.
7.  **Clarity:** Made message purposes clearer in docstrings.

---

## `pixabit/test/Modelo.py`

**Refactored Code:**

```python
# pixabit/test/Modelo.py

# SECTION: MODULE DOCSTRING
"""
Textual UI Layout Prototype.

This script appears to be an early prototype or test for a potential
Habitica TUI layout using Textual widgets like Tree, DataTable, TabbedContent,
and custom containers.

NOTE: This is likely a standalone test/prototype and should not be considered
      part of the final application structure unless explicitly integrated.
      Move to an 'examples/' or 'prototypes/' directory.
"""

# SECTION: IMPORTS
# Textual UI Components
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    # ListView, # Not used in compose
    Rule,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)

# SECTION: WIDGETS

# KLASS: NavigationTree (Prototype)
class NavigationTree(Widget):
    """Simple navigation tree widget prototype."""

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Create the navigation tree structure."""
        # Use descriptive IDs for nodes if interaction is planned
        tree: Tree[str] = Tree("Habitica") # Specify data type for nodes if known
        tree.root.expand()

        # Tasks Section
        tasks_node = tree.root.add("Tasks", expand=True, id="nav-tasks")
        tasks_node.add_leaf("Todos", id="nav-tasks-todos")
        tasks_node.add_leaf("Habits", id="nav-tasks-habits")
        tasks_node.add_leaf("Dailies", id="nav-tasks-dailies")
        tasks_node.add_leaf("Rewards", id="nav-tasks-rewards")

        # Social Section
        social_node = tree.root.add("Social", id="nav-social")
        social_node.add_leaf("Party", id="nav-social-party")
        social_node.add_leaf("Challenges", id="nav-social-challenges")
        social_node.add_leaf("Messages", id="nav-social-messages")
        social_node.add_leaf("Guilds", id="nav-social-guilds") # Added Guilds

        # Data & Settings Section
        data_node = tree.root.add("Data & Settings", id="nav-data")
        data_node.add_leaf("User Profile", id="nav-data-profile")
        data_node.add_leaf("Tags", id="nav-data-tags")
        data_node.add_leaf("Inventory", id="nav-data-inventory") # Added Inventory
        data_node.add_leaf("Stats", id="nav-data-stats") # Added Stats
        data_node.add_leaf("Settings", id="nav-data-settings") # App Settings

        yield tree

# SECTION: MAIN APPLICATION PROTOTYPE

# KLASS: HabiticaTUIPrototype (Renamed from HabiticaTUI)
class HabiticaTUIPrototype(App[None]):
    """Textual UI prototype for a Habitica interface."""

    # --- Configuration ---
    # Use more semantic variable names based on a theme (e.g., Catppuccin)
    DEFAULT_CSS = """
    /* Basic Layout */
    Screen {
        overflow: hidden; /* Prevent screen overflow */
    }
    #main-layout {
         grid-size: 2;
         grid-gutter: 1 2;
         grid-columns: auto 1fr; /* Nav panel auto, content takes rest */
         grid-rows: auto 1fr auto; /* Header, Main Content, Footer */
         height: 100vh;
         width: 100vw;
    }
    Header { grid-column: 1 / 3; grid-row: 1; }
    Footer { grid-column: 1 / 3; grid-row: 3; }
    #nav-panel {
         grid-column: 1; grid-row: 2;
         width: 25; /* Fixed width for nav */
         border-right: thick $accent;
         display: block; /* Ensure visible by default */
         overflow-y: auto; /* Scroll if needed */
         background: $surface0; /* Slightly different bg */
    }
    #nav-panel.hidden { display: none; width: 0; border: none;} /* Hide nav */

    #content-panel {
         grid-column: 2; grid-row: 2;
         overflow: hidden; /* Let content manage its scroll */
         background: $base;
    }

    /* Visibility Toggle */
    #search-container { display: none; }
    #search-container.visible { display: block; }

    /* Components */
    Header, Footer { background: $mantle; }
    NavigationTree { padding: 1; border-bottom: thin $surface1; }
    #action-buttons { padding: 1; }
    #action-buttons Label { margin-bottom: 1; text-style: bold; }
    Button { width: 100%; margin-bottom: 1; }
    #status-bar { height: 1; dock: bottom; background: $surface1; } /* Use dock */
    #stats-container { layout: horizontal; height: 1; }
    .stat { width: 1fr; text-align: center; content-align: center middle; height: 1; }
    .hp { color: $red; } .mp { color: $blue; } .exp { color: $yellow; }
    .level { color: $mauve; } .gold { color: $peach; }
    #party-grid { grid-size: 2; padding: 1; grid-gutter: 1; }
    #party-grid > Container { border: round $surface2; padding: 1; }
    .span-2 { grid-column: 1 / 3; } /* Class for spanning grid columns */
    Label.heading { text-style: bold; margin-bottom: 1; }
    """

    BINDINGS = [
        Binding(key="q", action="quit", description="Quit"),
        Binding(key="ctrl+n", action="toggle_navigation", description="Toggle Nav"),
        Binding(key="/", action="toggle_search", description="Search"),
        Binding(key="f1", action="view_help", description="Help"), # Placeholder
        # Add Tab navigation bindings
        Binding(key="ctrl+t", action="next_tab", description="Next Tab"),
        Binding(key="ctrl+shift+t", action="prev_tab", description="Prev Tab"),
    ]

    # --- Reactive State ---
    show_search = reactive(False)
    show_navigation = reactive(True)

    # --- UI Composition ---
    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Create the main application layout."""
        yield Header(show_clock=True)
        # Main content area using CSS Grid defined in #main-layout
        with Container(id="main-layout"):
             # Navigation Panel (column 1, row 2)
             with Vertical(id="nav-panel"):
                  yield NavigationTree()
                  yield Rule()
                  with Container(id="action-buttons"):
                       yield Label("Quick Add:")
                       yield Button("Todo", id="add-todo")
                       yield Button("Habit", id="add-habit")
                       yield Button("Daily", id="add-daily")
                       yield Button("Reward", id="add-reward")

             # Content Panel (column 2, row 2)
             with Container(id="content-panel"):
                  # Search Bar (docked top, hidden initially)
                  with Container(id="search-container"):
                       yield Input(placeholder="Search...", id="global-search")
                  # Main content tabs
                  with TabbedContent(id="main-tabs", initial="tab-todos"): # Start on todos
                        # --- TASK TABS ---
                        with TabPane("Todos", id="tab-todos"):
                             yield DataTable(id="todos-table") # Simplified for prototype
                        with TabPane("Habits", id="tab-habits"):
                             yield DataTable(id="habits-table")
                        with TabPane("Dailies", id="tab-dailies"):
                             yield DataTable(id="dailies-table")
                        with TabPane("Rewards", id="tab-rewards"):
                             yield DataTable(id="rewards-table")
                        # --- SOCIAL TABS ---
                        with TabPane("Party", id="tab-party"):
                             with Grid(id="party-grid"): # Use Grid layout for party info
                                  yield Static("Party Info\n...", id="party-details")
                                  yield Static("Quest Info\n...", id="quest-details")
                                  with Vertical(classes="span-2"): # Chat spans columns
                                       yield Static("Party Chat\n...") # Placeholder
                                       with Horizontal():
                                           yield Input(placeholder="Message...", id="party-message")
                                           yield Button("Send", id="send-party-message")
                        with TabPane("Challenges", id="tab-challenges"):
                             yield DataTable(id="challenges-table")
                        with TabPane("Messages", id="tab-messages"):
                             yield DataTable(id="messages-table")
                        # --- DATA/SETTINGS TABS ---
                        with TabPane("Profile", id="tab-profile"):
                             yield Static("User Profile\n...")
                        with TabPane("Tags", id="tab-tags"):
                             yield DataTable(id="tags-table")
                        with TabPane("Settings", id="tab-settings"):
                             yield Static("Application Settings\n...")
                  # Status Bar (docked bottom within content panel)
                  with Container(id="status-bar"):
                       with Horizontal(id="stats-container"):
                            yield Label("HP --/--", classes="stat hp", id="hp-stat")
                            yield Label("MP --/--", classes="stat mp", id="mp-stat")
                            yield Label("XP --/--", classes="stat exp", id="exp-stat")
                            yield Label("L --", classes="stat level", id="level-stat")
                            yield Label("GP --", classes="stat gold", id="gold-stat")

        yield Footer()

    # --- Watchers for Reactive State ---
    # FUNC: watch_show_navigation
    def watch_show_navigation(self, show: bool) -> None:
        """Toggle visibility of the navigation panel."""
        try:
            nav_panel = self.query_one("#nav-panel")
            nav_panel.set_class(not show, "hidden") # Add/remove hidden class
            # Optional: Focus content when nav hidden
            # if not show: self.query_one("#content-panel").focus()
        except NoMatches:
            self.log.warning("Navigation panel '#nav-panel' not found.")

    # FUNC: watch_show_search
    def watch_show_search(self, show: bool) -> None:
        """Toggle visibility of the search bar."""
        try:
            search_container = self.query_one("#search-container")
            search_container.set_class(show, "visible")
            if show:
                self.set_focus(self.query_one("#global-search", Input))
            # else: # Optionally focus main content when hiding search
                # self.set_focus(self.query_one("#main-tabs", TabbedContent))
        except NoMatches:
             self.log.warning("Search container '#search-container' not found.")
        except Exception as e:
             self.log.error(f"Error toggling search visibility: {e}")


    # --- Actions ---
    # FUNC: action_toggle_navigation
    def action_toggle_navigation(self) -> None:
        """Action bound to Ctrl+N."""
        self.show_navigation = not self.show_navigation

    # FUNC: action_toggle_search
    def action_toggle_search(self) -> None:
        """Action bound to / key."""
        self.show_search = not self.show_search

    # FUNC: action_next_tab
    def action_next_tab(self) -> None:
         """Switch to the next tab."""
         try:
              tabs = self.query_one("#main-tabs", TabbedContent)
              tabs.action_next_tab()
         except NoMatches:
              self.log.warning("Main tabs '#main-tabs' not found.")

    # FUNC: action_prev_tab
    def action_prev_tab(self) -> None:
         """Switch to the previous tab."""
         try:
              tabs = self.query_one("#main-tabs", TabbedContent)
              tabs.action_previous_tab()
         except NoMatches:
              self.log.warning("Main tabs '#main-tabs' not found.")

    # Placeholder actions (implement actual logic later)
    def action_view_help(self) -> None: self.log.info("Action: View Help (Not Implemented)")
    def on_button_pressed(self, event: Button.Pressed) -> None: self.log.info(f"Button Pressed: {event.button.id}")
    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle navigation tree selection."""
        node_id = event.node.data # Assuming data holds the ID string
        self.log.info(f"Tree Node Selected: {node_id}")
        # Map tree node IDs to tab IDs (example)
        id_to_tab_map = {
             "nav-tasks-todos": "tab-todos", "nav-tasks-habits": "tab-habits",
             "nav-tasks-dailies": "tab-dailies", "nav-tasks-rewards": "tab-rewards",
             "nav-social-party": "tab-party", "nav-social-challenges": "tab-challenges",
             "nav-social-messages": "tab-messages", "nav-data-profile": "tab-profile",
             "nav-data-tags": "tab-tags", "nav-data-settings": "tab-settings",
             # Add mappings for other nodes...
        }
        target_tab = id_to_tab_map.get(str(node_id))
        if target_tab:
             try:
                  tabs = self.query_one("#main-tabs", TabbedContent)
                  tabs.active = target_tab
             except NoMatches:
                  self.log.warning(f"Target tab '{target_tab}' not found.")
        else:
             self.log.warning(f"No tab mapping found for tree node ID: {node_id}")


# SECTION: MAIN EXECUTION
if __name__ == "__main__":
    app = HabiticaTUIPrototype()
    app.run()
```

**Suggestions & Comments:**

1.  **Purpose:** Clarified in the docstring that this is a prototype/test script. Renamed class to `HabiticaTUIPrototype`.
2.  **Typing:** Standard typing.
3.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:` anchors.
4.  **CSS:**
    - Embedded CSS using `DEFAULT_CSS` for self-containment.
    - Switched main layout to CSS Grid (`#main-layout`) for potentially better control over panel sizing and arrangement compared to nested `Horizontal`/`Vertical`.
    - Used more semantic CSS variable names (assuming a theme like Catppuccin, e.g., `$base`, `$surface0`, `$accent`).
    - Simplified visibility toggling using a `.hidden` class for the nav panel and `.visible` for the search bar, controlled by watchers.
    - Docked the status bar to the bottom.
5.  **Layout (`compose`):**
    - Simplified the structure based on the CSS Grid layout.
    - Removed some unnecessary intermediate containers.
    - Used `TabbedContent`/`TabPane` directly within the content panel.
    - Added more placeholder tabs for social/data sections.
    - Simplified the status bar using docked container and horizontal layout.
6.  **Reactive State & Watchers:** Used reactive variables (`show_search`, `show_navigation`) and corresponding `watch_*` methods to handle UI changes (adding/removing CSS classes).
7.  **Actions:** Renamed actions (`toggle_search`, `toggle_navigation`). Added actions for tab switching (`next_tab`, `prev_tab`). Added basic `on_tree_node_selected` handler to demonstrate switching tabs based on tree selection (requires mapping node IDs to tab IDs). Removed unimplemented task actions.
8.  **Focus Management:** Added hints in watchers/actions where focus management might be needed (e.g., focusing search input when shown).
9.  **Simplification:** Removed some detailed button layouts within tabs for prototype clarity, focusing on the main structure. DataTables are used as placeholders within tabs.

---

## `pixabit/test/prev_mdrichconverter.py`

**Analysis:**

- The content of this file is **identical** to the original `pixabit/test/DataTableSample.py`.
- It seems to be a duplicate or an earlier version.

**Recommendation:**

- **Delete this file (`pixabit/test/prev_mdrichconverter.py`)**. Keep the refactored `pixabit/test/DataTableSample.py` (or move it to `examples/`).

---

## `pixabit/test/self.py`

**Refactored Code:**

```python
# pixabit/test/self.py (or examples/usage_example.py)

# SECTION: MODULE DOCSTRING
"""
Example Script Demonstrating Usage of Various Pixabit Helpers.

NOTE: This script assumes it's run from a context where the 'pixabit'
      package (especially the 'helpers' and potentially 'models' modules)
      is correctly installed or accessible in the PYTHONPATH.
      Consider moving to an 'examples/' directory.
"""

# SECTION: IMPORTS
import sys
from pathlib import Path

# --- Attempt to import helpers ---
# This adjusts the path to potentially find the 'pixabit' package if run directly
try:
    # Assumes the script is in pixabit/test/ or pixabit/examples/
    _project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_project_root.parent)) # Add the directory *containing* pixabit
    from pixabit.helpers import (
        MarkdownRenderer,
        PixabitBaseModel,
        console,
        print, # Themed print
        # Add other helpers you want to test
    )
    # Import Textual widget if needed and available
    try:
        from pixabit.helpers import MarkdownStatic
        TEXTUAL_AVAILABLE = True
    except ImportError:
        TEXTUAL_AVAILABLE = False
        MarkdownStatic = None # Placeholder

    print("[green]Successfully imported Pixabit helpers.[/green]")

except ImportError as e:
    print(f"[bold red]ERROR:[/bold red] Failed to import Pixabit helpers: {e}", file=sys.stderr)
    print("Ensure the pixabit package is installed or PYTHONPATH is set correctly.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
     print(f"[bold red]ERROR:[/bold red] An unexpected error occurred during import: {e}", file=sys.stderr)
     sys.exit(1)


# SECTION: EXAMPLE 1 - Basic Markdown Rendering

print("\n--- Example 1: Basic Markdown Rendering ---")

# Create a renderer instance (uses default styles)
try:
    md_renderer = MarkdownRenderer()

    markdown_text_1 = """
# My Title
This is **bold** and *italic* text with `inline code`.

## Section Header
- List item 1 using default bullet.
- List item 2.
    - Nested item.

[ ] Unchecked task
[x] Checked task

> Blockquote example.
---
Horizontal Rule
"""
    # Get Rich Text object
    rich_text_1 = md_renderer.markdown_to_rich_text(markdown_text_1)

    # Print to the themed console
    print("\n[bold yellow]Rendered Output:[/bold yellow]")
    print(rich_text_1)

except Exception as e:
    print(f"[red]Error during basic rendering: {e}[/red]")


# SECTION: EXAMPLE 2 - Custom Styling

print("\n--- Example 2: Custom Styling ---")
try:
    from rich.style import Style # Import Style for defining custom styles

    custom_styles = {
        "h1": Style(bold=True, color="bright_magenta", underline=False), # Override default
        "code_inline": Style(bgcolor="yellow", color="black"),
        "link": Style(underline=False, bold=True, color="green"),
        "blockquote": Style(color="blue", italic=False),
        "checkbox_checked": Style(color="green", dim=False, strike=True)
    }

    # Create renderer with custom styles
    custom_renderer = MarkdownRenderer(custom_styles=custom_styles)
    markdown_text_2 = """
# Custom Styled Title

This uses `custom inline code` styling.
Check out this [custom link](https://example.com).

> Custom blockquote style.

[ ] Unchecked item
[x] Checked item styling overridden.
"""
    rich_text_2 = custom_renderer.markdown_to_rich_text(markdown_text_2)

    print("\n[bold yellow]Custom Styled Output:[/bold yellow]")
    print(rich_text_2)

except NameError: # Handle if rich.style failed import
     print("[yellow]Skipping custom style example (rich.style not available).[/yellow]")
except Exception as e:
    print(f"[red]Error during custom styling example: {e}[/red]")


# SECTION: EXAMPLE 3 - Using in a (Mock) Textual App

print("\n--- Example 3: Textual Integration (Conceptual) ---")

if TEXTUAL_AVAILABLE and MarkdownStatic is not None:
    from textual.app import App, ComposeResult
    from textual.containers import ScrollableContainer
    from textual.widgets import Footer, Header

    # Define a simple Textual app
    # KLASS: MarkdownViewerApp
    class MarkdownViewerApp(App[None]):
        """Simple app to display the MarkdownStatic widget."""
        CSS = """
        Screen { layout: vertical; }
        Header, Footer { height: auto; }
        ScrollableContainer { width: 100%; height: 1fr; border: thick $accent; }
        MarkdownStatic { padding: 1 2; height: auto; }
        """
        # FUNC: compose
        def compose(self) -> ComposeResult:
            yield Header()
            # Use a ScrollableContainer in case markdown is long
            with ScrollableContainer():
                 # Use the imported MarkdownStatic widget
                yield MarkdownStatic(
                    markdown="""# Welcome to Pixabit Helper Test

This is rendered inside a **Textual** `MarkdownStatic` widget.

## Features
- Uses the *custom renderer* by default.
- Integrates with the Textual framework.

> Built with `markdown-it-py` and `Rich`.

[ ] Example task list item.
[x] Another completed item.

                    """,
                    id="md-viewer"
                )
            yield Footer()

    print("Textual MarkdownStatic widget is available.")
    print("Run 'textual run pixabit.test.self:MarkdownViewerApp' to see it (if runnable).")
    # Note: Actually running this requires Textual setup and might not work directly
    #       depending on the environment and how the script is invoked.
    # Example conceptual run (won't work directly here):
    # app = MarkdownViewerApp()
    # app.run()

else:
    print("[yellow]Skipping Textual example (Textual or MarkdownStatic not available/imported).[/yellow]")


# SECTION: EXAMPLE 4 - Using with Pydantic Base Model

print("\n--- Example 4: Pydantic Integration ---")

try:
    # Define a simple model using the imported base
    # KLASS: DocumentModel
    class DocumentModel(PixabitBaseModel):
        """An example Pydantic model incorporating markdown."""
        title: str
        content_md: str # Store raw markdown
        description: str | None = None

        # FUNC: render_to_console
        def render_to_console(self, renderer: MarkdownRenderer | None = None):
            """Renders the document content to the console."""
            # Use provided renderer or create a default one
            _renderer = renderer or MarkdownRenderer()

            print(f"\n[bold cyan underline]Title: {self.title}[/]\n")
            if self.description:
                print(f"[dim italic]Description: {self.description}[/]\n")

            print("[bold yellow]Content:[/]")
            content_text = _renderer.markdown_to_rich_text(self.content_md)
            print(content_text)

    # Create an instance
    doc_data = {
        "title": "Pydantic Document Example",
        "content_md": """
This content is stored as raw Markdown in the `content_md` field
of the Pydantic model.

The `render_to_console` method uses the **MarkdownRenderer**
to display it with formatting.

- Point 1
- Point 2 `code`
        """,
        "description": "A simple demonstration."
    }
    doc = DocumentModel.model_validate(doc_data) # Pydantic V2+

    # Render it
    doc.render_to_console()

except Exception as e:
    print(f"[red]Error during Pydantic example: {e}[/red]")

print("\n--- Example Script Finished ---")
```

**Suggestions & Comments:**

1.  **Purpose:** Clarified this is an example usage script and suggested moving it.
2.  **Typing:** Standard typing.
3.  **Imports:** Added dynamic path adjustment (`sys.path.insert`) to help find the `pixabit` package when running the script directly from the `test` or `examples` directory. Made Textual import conditional. Added robust error handling for imports.
4.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:` anchors.
5.  **Examples:**
    - Cleaned up the examples.
    - Used the imported themed `print` and `console`.
    - Added try/except blocks around each example section for better error isolation.
    - Updated the Textual example to use a `ScrollableContainer` and noted that running it directly might require specific setup. Used the imported `MarkdownStatic`.
    - Updated the Pydantic example to use `model_validate` (Pydantic V2+) and pass the renderer to the method. Stored markdown in a field named `content_md`.
6.  **Readability:** Added more print statements to delineate the different examples.

---

## `pixabit/tui/Api_Sample.py`

**Refactored Code:**

```python
# pixabit/tui/Api_Sample.py (or examples/api_usage.py)

# SECTION: MODULE DOCSTRING
"""
Example Script: Basic Usage of the HabiticaAPI Client.

Demonstrates initializing the API client, making a few common GET requests,
and handling potential errors.

NOTE: This script requires environment variables HABITICA_USER_ID and
      HABITICA_API_TOKEN to be set for authentication.
      Consider moving to an 'examples/' directory.
"""

# SECTION: IMPORTS
import asyncio
import logging
import os
import sys
from pathlib import Path

# --- Attempt to import API client ---
try:
    # Adjust path to find the pixabit package
    _project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_project_root.parent))
    from pixabit.habitica.api import HabiticaAPI, HabiticaConfig
    from pixabit.habitica.exception import HabiticaAPIError
    from pixabit.helpers._logger import log # Use the configured logger
    print("[green]Successfully imported Pixabit API components.[/green]")
except ImportError as e:
    # Fallback basic logging if helpers failed
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    log = logging.getLogger(__name__)
    print(f"[bold red]ERROR:[/bold red] Failed to import Pixabit API components: {e}", file=sys.stderr)
    print("Ensure the pixabit package is installed or PYTHONPATH is set correctly.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
     logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
     log = logging.getLogger(__name__)
     print(f"[bold red]ERROR:[/bold red] An unexpected error occurred during import: {e}", file=sys.stderr)
     sys.exit(1)


# SECTION: MAIN ASYNC FUNCTION

# FUNC: main
async def main():
    """Main execution function for the API example."""
    log.info("Starting Habitica API example...")
    api_client: HabiticaAPI | None = None # Initialize to None

    try:
        # --- Initialize Client using HabiticaConfig (recommended) ---
        # HabiticaConfig will load from .env by default
        log.info("Initializing HabiticaAPI client using configuration...")
        config = HabiticaConfig() # Raises error if vars missing
        api_client = HabiticaAPI(config=config)
        log.info("HabiticaAPI client initialized successfully.")

        # --- Make API Calls ---
        log.info("Fetching user data...")
        # Assuming get_user_data is now part of the main client or a mixin
        # We use the base 'get' method here for demonstration if mixins aren't used directly
        # user_data = await api_client.get_user_data() # If using HabiticaClient
        user_data = await api_client.get("user") # Using base get method

        if user_data and isinstance(user_data, dict):
            profile_name = user_data.get("profile", {}).get("name", "User")
            user_level = user_data.get("stats", {}).get("lvl", "N/A")
            log.success(f"  Welcome, {profile_name}! Level: {user_level}")
        else:
            log.warning("  Could not fetch or parse user data.")

        log.info("Fetching tasks...")
        # tasks = await api_client.get_tasks() # If using HabiticaClient
        tasks = await api_client.get("tasks/user") # Using base get method

        if tasks and isinstance(tasks, list):
            log.success(f"  Fetched {len(tasks)} tasks.")
            if tasks:
                first_task_text = tasks[0].get('text', 'N/A') if isinstance(tasks[0], dict) else 'N/A'
                log.info(f"  First task text: {first_task_text}")
        elif isinstance(tasks, list):
             log.info("  Fetched 0 tasks.")
        else:
            log.warning("  Could not fetch or parse tasks.")

        # Example: Fetch content (demonstrates handling non-standard success response)
        log.info("Fetching game content...")
        content_data = await api_client.get_content()
        if content_data:
             log.success(f"  Fetched game content. Top level keys: {list(content_data.keys())}")
        else:
             log.warning("  Could not fetch game content.")

        # Example: Score a task (replace 'dummy-task-id' with a REAL task ID)
        # task_to_score = "YOUR_REAL_TASK_ID_HERE"
        # if task_to_score != "YOUR_REAL_TASK_ID_HERE":
        #     try:
        #         log.info(f"Scoring task '{task_to_score}' up...")
        #         # score_result = await api_client.score_task(task_to_score, "up") # If using HabiticaClient
        #         score_result = await api_client.post(f"tasks/{task_to_score}/score/up") # Using base post
        #         log.success(f"  Score result: {score_result}")
        #     except HabiticaAPIError as e:
        #         log.error(f"  Failed to score task {task_to_score}: {e}")
        #     except Exception as e:
        #          log.exception(f"  Unexpected error scoring task {task_to_score}: {e}")
        # else:
        #     log.info("Skipping task scoring example (replace dummy ID).")

    except ValueError as e:
        # Catch config errors from HabiticaConfig() or API init
        log.error(f"Configuration Error: {e}")
        log.error("Please ensure HABITICA_USER_ID and HABITICA_API_TOKEN are set in your .env file or environment.")
    except HabiticaAPIError as e:
        log.error(f"Habitica API Error: {e}")
        # Log more details if available
        if e.status_code: log.error(f"  Status Code: {e.status_code}")
        if e.error_type: log.error(f"  Error Type: {e.error_type}")
        if e.response_data: log.error(f"  Response Data: {e.response_data}")
    except Exception as e:
        log.exception(f"An unexpected error occurred: {e}") # Log full traceback

    finally:
        # --- Close Client ---
        if api_client:
            log.info("Closing HabiticaAPI client...")
            await api_client.close()
            log.info("Client closed.")
        log.info("API example finished.")


# SECTION: SCRIPT EXECUTION
if __name__ == "__main__":
    # Logger is already configured by the import from pixabit.helpers._logger
    asyncio.run(main())

```

**Suggestions & Comments:**

1.  **Purpose:** Clarified this is an example script and needs environment variables. Suggested moving to `examples/`.
2.  **Typing:** Standard typing.
3.  **Imports:** Adjusted path finding logic. Uses the configured logger from `pixabit.helpers._logger`. Imports `HabiticaConfig`. Added error handling for imports.
4.  **Comments:** Added `# SECTION:`, `# FUNC:` anchors.
5.  **Initialization:** Changed to initialize `HabiticaAPI` using `HabiticaConfig` for better practice (loading from `.env`).
6.  **API Calls:** Modified the example calls to use the base `get`/`post` methods directly from `api_client`, as this script doesn't necessarily know about the full `HabiticaClient` with mixins. If you intend this example to use the full client, import `HabiticaClient` instead. Added an example for `get_content`. Commented out the `score_task` example with instructions to replace the dummy ID.
7.  **Logging:** Uses the imported `log` instance for all messages. Uses different log levels (`info`, `success`, `warning`, `error`, `exception`).
8.  **Error Handling:** Improved error handling to catch `ValueError` (likely from config), `HabiticaAPIError` (logging details), and general `Exception`.
9.  **Client Closing:** Ensures `api_client.close()` is called in the `finally` block if the client was successfully initialized.

---

## `pixabit/tui/app.py`

**Refactored Code:**

```python
# pixabit/tui/app.py

# SECTION: MODULE DOCSTRING
"""
The main Textual TUI Application for Pixabit Habitica Assistant.

Coordinates UI components, manages application state via DataStore,
handles user interactions, and orchestrates data fetching and updates.
"""

# SECTION: IMPORTS
import asyncio
import logging # Keep standard logging if needed for early init
from typing import Any, Dict, Optional, Type, cast # Use standard types

# Rich and Textual imports (use helpers where appropriate)
from rich.text import Text # Keep for specific formatting if needed
from textual import events, log, on, work # Import log, on decorator, work decorator
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical # Keep necessary containers
from textual.message import Message # Base class
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane, Tabs # Keep core widgets

# --- Pixabit Imports ---
# Assume helpers are one level up
try:
    from ..helpers import console, print # Themed console/print
    # Import custom messages
    from .messages import DataRefreshed, UIMessageRequest, ShowStatusRequest, ErrorOccurred
    # Import core data store
    from .data_store import PixabitDataStore
    # Import widgets (adjust paths if structure changed)
    from .widgets.stats_panel import StatsPanel
    from .widgets.tabs_panel import TabPanel # Assuming this handles the TabbedContent
    from .widgets.tasks_panel import TaskListWidget, ScoreTaskRequest, ViewTaskDetailsRequest
    # Import placeholder/other panels if used in compose
    # from .widgets.placeholder import PlaceholderWidget
    # from .widgets.settings_panel import SettingsPanel
    # from .widgets.tags_panel import TagsPanel
    # from .widgets.challenge_panel import ChallengeListWidget # etc.

except ImportError as e:
    # Basic fallback logging if imports fail early
    logging.basicConfig(level=logging.CRITICAL)
    logging.critical(f"FATAL ERROR: Could not import Pixabit TUI modules in app.py: {e}", exc_info=True)
    import sys
    sys.exit(1)


# SECTION: PixabitTUIApp CLASS

# KLASS: PixabitTUIApp
class PixabitTUIApp(App[None]):
    """The main Textual TUI Application for Pixabit."""

    # --- Configuration ---
    CSS_PATH = "pixabit.tcss" # Link to the main CSS file
    # Define key bindings for application-level actions
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+r", "refresh_data", "Refresh Data"),
        Binding("ctrl+s", "toggle_sleep", "Toggle Sleep"),
        Binding("f1", "show_help_screen", "Help"), # Example help binding
        # Add bindings for tab navigation if TabsPanel doesn't handle it internally
        # Binding("right", "next_tab", "Next Tab"),
        # Binding("left", "prev_tab", "Prev Tab"),
    ]

    # --- Reactive State ---
    # Controls visibility/state of a loading indicator overlay (implement in CSS)
    show_loading: reactive[bool] = reactive(False, layout=True)
    # Stores the current status message shown in the footer or a status bar
    status_message = reactive("")

    # --- Initialization ---
    # FUNC: __init__
    def __init__(self, **kwargs: Any):
        log.info("App: Initializing...")
        super().__init__(**kwargs)
        try:
            # Initialize the central data store, passing the app instance
            self.datastore = PixabitDataStore(self)
            log.info("App: PixabitDataStore initialized successfully.")
        except Exception as e:
            # Use standard logging as Textual log might not be ready
            logging.critical(f"FATAL: Failed to initialize PixabitDataStore: {e}", exc_info=True)
            # Optionally, try to display an error visually before exiting
            # self.show_fatal_error_screen(e) # Implement this method if desired
            import sys
            sys.exit(1)
        # Lock to prevent race conditions when multiple updates trigger UI refresh
        self._refresh_notify_lock = asyncio.Lock()

    # --- UI Composition ---
    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Compose the application's main widget hierarchy."""
        log.debug("App: Composing UI...")
        yield Header()
        # Main content area: Stats panel + Tabbed content panel
        # Using Vertical container to stack them
        with Container(id="app-grid"): # Use an outer container for potential overlays
             yield StatsPanel(id="stats-panel")
             yield TabPanel(id="main-tabs") # TabsPanel handles the TabbedContent internally
             # Example Loading Indicator (controlled by CSS based on show_loading)
             # yield Static("🔄 Loading...", id="loading-indicator", classes="loading")
        yield Footer() # Footer displays bindings and status message

    # --- Lifecycle Methods ---
    # FUNC: on_mount
    async def on_mount(self) -> None:
        """Called once when the app is mounted. Start initial data load."""
        log.info("App: Mounted. Starting initial data load...")
        self.title = "Pixabit TUI"
        self.sub_title = "Habitica Assistant"
        # Trigger initial data load in the background
        self.set_loading(True) # Show loading indicator immediately
        self.run_worker(self.initial_data_load, exclusive=True, group="data_load")

    # --- Workers ---

    # FUNC: initial_data_load (Worker)
    async def initial_data_load(self) -> None:
        """Worker task for the initial data load."""
        log.info("App: Initial data load worker started.")
        # DataStore handles internal errors and posts DataRefreshed/ErrorOccurred
        await self.datastore.refresh_all_data()
        # UI update is handled by the on_data_refreshed event handler
        log.info("App: Initial data load worker finished (awaiting events).")

    # --- Event Handlers ---

    # FUNC: on_data_refreshed
    @on(DataRefreshed)
    async def on_data_refreshed(self, event: DataRefreshed) -> None:
        """Handles the DataRefreshed message from the DataStore."""
        log.info(f"App: Received DataRefreshed event (success={event.success}).")
        await self.update_ui_after_refresh(event.success, event.message)

    # FUNC: on_ui_message_request
    @on(UIMessageRequest)
    def on_ui_message_request(self, event: UIMessageRequest) -> None:
        """Handles requests to show notifications."""
        log.info(f"App: Received UIMessageRequest: '{event.text}' (Severity: {event.severity})")
        self.notify(
            event.text,
            title=event.title,
            severity=event.severity, # type: ignore # Allow severity strings
            timeout=event.timeout
        )

    # FUNC: on_show_status_request
    @on(ShowStatusRequest)
    def on_show_status_request(self, event: ShowStatusRequest) -> None:
         """Handles requests to update the status message."""
         log.debug(f"App: Received ShowStatusRequest: '{event.status_text}'")
         self.status_message = event.status_text
         # If temporary, clear it after a delay (needs timer management)
         # TODO: Implement temporary status message clearing

    # FUNC: on_error_occurred
    @on(ErrorOccurred)
    def on_error_occurred(self, event: ErrorOccurred) -> None:
         """Handles generic error notifications."""
         log.error(f"App: Received ErrorOccurred from '{event.source}': {event.error}")
         self.notify(f"Error in {event.source}: {event.error}", title="Error", severity="error", timeout=10)
         # Optionally show more details or log event.details

    # FUNC: on_score_task_request (Handles request from TaskListWidget)
    @on(ScoreTaskRequest)
    async def on_score_task_request(self, message: ScoreTaskRequest) -> None:
        """Handles request from TaskListWidget to score a task via DataStore."""
        log.info(f"App: Received score request: Task={message.task_id}, Dir={message.direction}")
        self.set_loading(True) # Show loading while action is processed
        self.status_message = f"Scoring task {message.task_id[:8]}... {message.direction}"
        # Run the datastore action as a worker
        self.run_worker(
            self.datastore.score_task(message.task_id, message.direction),
            exclusive=True, # Prevent concurrent scoring of same task?
            group=f"score_task_{message.task_id}",
        )
        # DataStore.score_task should trigger a refresh, which then posts DataRefreshed
        # UI updates happen in on_data_refreshed

    # FUNC: on_view_task_details_request (Handles request from TaskListWidget)
    @on(ViewTaskDetailsRequest)
    async def on_view_task_details_request(self, message: ViewTaskDetailsRequest) -> None:
        """Handles request to view task details (placeholder)."""
        log.info(f"App: Received view details request for task: {message.task_id}")
        # TODO: Implement task detail view (e.g., push a new screen or show a modal)
        task_obj = self.datastore.tasks_list_obj.get_by_id(message.task_id) if self.datastore.tasks_list_obj else None
        title = task_obj.text if task_obj else f"Task {message.task_id[:8]}"
        details = f"Task ID: {message.task_id}\n\nDetails view not yet implemented."
        if task_obj:
             details += f"\nType: {task_obj.type}\nValue: {task_obj.value}\nNotes: {task_obj.notes}"
        self.notify(details, title=f"Details: {title[:30]}...", timeout=8)


    # --- UI Update Logic ---

    # FUNC: update_ui_after_refresh
    async def update_ui_after_refresh(self, success: bool, message: str | None) -> None:
        """Safely updates UI components after data refresh event is received."""
        log.info("App: Acquiring UI update lock...")
        async with self._refresh_notify_lock: # Prevent concurrent UI updates
            log.info("App: Lock acquired. Starting UI update.")
            self.set_loading(False) # Hide loading indicator FIRST

            if success:
                self.status_message = message or "Data refresh complete."
            else:
                 # Keep loading indicator if refresh failed critically? Maybe not.
                 # Show persistent error status?
                 self.status_message = message or "Data refresh failed or had errors."
                 # Optionally notify the user again about the failure state
                 self.notify(self.status_message, title="Refresh Status", severity="warning")


            # --- Update Stats Panel ---
            stats_data = self.datastore.get_user_stats() # Get latest data
            log.debug(f"App: Fetched stats data for UI update: {stats_data.get('level', 'N/A')}")
            try:
                stats_panel = self.query_one(StatsPanel)
                stats_panel.update_display(stats_data)
                log.info("App: StatsPanel updated.")
            except Exception as e:
                log.error(f"App: Error updating StatsPanel: {e}", exc_info=True)


            # --- Refresh Active Content Widget ---
            # Ask the TabPanel which widget is active and tell it to refresh
            try:
                tabs_panel = self.query_one(TabPanel)
                active_content_widget = tabs_panel.get_active_content_widget()

                if active_content_widget and hasattr(active_content_widget, 'load_or_refresh_data'):
                    log.info(f"App: Refreshing active content widget: {active_content_widget.id}")
                    # Run the widget's own refresh method as a worker
                    # Use exclusive=False if multiple widgets might need refresh concurrently?
                    # Or maybe widget refresh should be synchronous if data is already in datastore?
                    # Let's assume widget refresh might involve its own logic/API calls (though less ideal)
                    self.run_worker(active_content_widget.load_or_refresh_data, exclusive=True)
                elif active_content_widget:
                     log.debug(f"App: Active content widget {active_content_widget.id} has no refresh method.")
                else:
                     log.debug("App: No active content widget found in TabPanel.")

            except Exception as e:
                log.error(f"App: Error triggering refresh for active tab content: {e}", exc_info=True)

        log.info("App: UI update finished, lock released.")


    # --- Utility Methods ---

    # FUNC: set_loading
    def set_loading(self, loading: bool) -> None:
        """Controls the visibility state of the loading indicator."""
        self.show_loading = loading
        # Example: Update CSS class on a dedicated loading widget
        try:
             loading_widget = self.query_one("#loading-indicator")
             loading_widget.set_class(loading, "visible") # Add/remove 'visible' class
        except Exception:
             pass # Ignore if loading indicator doesn't exist


    # --- Actions (Bound to Keys) ---

    # FUNC: action_refresh_data
    async def action_refresh_data(self) -> None:
        """Action bound to 'Ctrl+R' - Triggers a manual data refresh via DataStore."""
        log.info("App: Manual Refresh Data Action Triggered")
        if self.datastore.is_refreshing.locked():
             log.warning("App: Refresh action ignored, already refreshing.")
             self.notify("Refresh already in progress...", severity="warning", timeout=2)
             return

        self.set_loading(True) # Show loading indicator
        self.status_message = "Refreshing data..."
        # Run the datastore refresh as a worker
        self.run_worker(
            self.datastore.refresh_all_data,
            name="manual_refresh",
            exclusive=True, # Prevent multiple manual refreshes
            group="data_load" # Ensure mutual exclusion with initial load
        )
        # UI update happens via on_data_refreshed

    # FUNC: action_toggle_sleep
    async def action_toggle_sleep(self) -> None:
        """Action bound to 'Ctrl+S' - Toggles user sleep status via DataStore."""
        log.info("App: Toggle Sleep Action Triggered")
        if self.datastore.is_refreshing.locked():
            log.warning("App: Toggle sleep blocked by active data refresh.")
            self.notify("Action unavailable: Data refresh in progress.", severity="warning")
            return

        # Optional: Check if another user action is running via worker group
        # if self.is_worker_running("user_action"): ...

        current_status = self.datastore.user_stats_dict.get("sleeping") # Get from cached dict
        if current_status is None:
             # Should not happen if datastore is loaded, but handle defensively
             self.notify("Cannot determine current sleep status.", severity="error")
             log.error("App: Could not get sleep status from datastore dictionary.")
             return

        action_desc = "wake up" if current_status else "go to sleep"
        self.status_message = f"Attempting to {action_desc}..."
        self.set_loading(True) # Indicate action in progress

        # Run the datastore action as a worker
        self.run_worker(
            self.datastore.toggle_sleep, # Pass the coroutine method
            exclusive=True, # Prevent multiple toggles
            group="user_action", # Group for user actions
        )
        # UI update will happen after DataStore triggers a refresh and DataRefreshed is handled

    # FUNC: action_show_help_screen (Placeholder)
    def action_show_help_screen(self) -> None:
        """Action bound to F1 - Shows a help screen (Not Implemented)."""
        log.info("Action: Show Help Screen (Not Implemented)")
        # TODO: Implement help screen (e.g., push a new Screen)
        self.notify("Help screen not yet implemented.", title="Help")

    # --- Footer Status Update ---
    # FUNC: watch_status_message
    def watch_status_message(self, new_message: str) -> None:
         """Update the footer's status message when the reactive variable changes."""
         try:
              footer = self.query_one(Footer)
              footer.status = new_message
         except Exception:
              pass # Ignore if footer not ready yet


# SECTION: MAIN ENTRY POINT
if __name__ == "__main__":
    # Logging is configured by helper import now
    app = PixabitTUIApp()
    app.run()
```

**Suggestions & Comments:**

1.  **Typing & Imports:** Updated typing. Standardized imports. Corrected paths assuming `helpers` is one level up. Imports custom messages and widgets. Added robust import error handling.
2.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:` anchors. Improved docstrings for methods and the main class.
3.  **Configuration:** Defined `BINDINGS` with more relevant TUI actions (refresh, sleep, quit). Removed mobile-specific or potentially widget-specific bindings.
4.  **State:** Added `status_message` reactive variable to potentially display status updates in the `Footer`.
5.  **Initialization (`__init__`):** Passes `self` (the app instance) to `PixabitDataStore`. Handles critical errors during `DataStore` initialization.
6.  **Composition (`compose`):** Simplified layout. Uses `StatsPanel` and `TabPanel`. Removed the manual `TabbedContent` setup as `TabPanel` should encapsulate that. Added a placeholder comment for a loading indicator.
7.  **Lifecycle (`on_mount`):** Triggers initial data load using `run_worker`. Sets loading state immediately.
8.  **Workers:** Kept `initial_data_load` worker. Removed `refresh_data_worker` as the logic is now directly in `action_refresh_data`.
9.  **Event Handling:**
    - Implemented handlers for custom messages (`DataRefreshed`, `UIMessageRequest`, `ShowStatusRequest`, `ErrorOccurred`).
    - `on_data_refreshed` now calls `update_ui_after_refresh`, passing success status.
    - Added handlers `on_score_task_request` and `on_view_task_details_request` to receive messages from `TaskListWidget` and delegate actions to the `DataStore` via workers.
10. **UI Update (`update_ui_after_refresh`):**
    - Protected by the `_refresh_notify_lock`.
    - Updates `StatsPanel` first.
    - Refreshes the content widget _within the currently active tab_ by asking `TabPanel` for the active widget and calling its `load_or_refresh_data` method (if it exists).
    - Sets status message based on refresh success.
11. **Actions:**
    - `action_refresh_data`: Checks if already refreshing, sets loading/status, runs `datastore.refresh_all_data` as an exclusive worker.
    - `action_toggle_sleep`: Checks if refresh is running, sets loading/status, runs `datastore.toggle_sleep` as an exclusive worker. Added better status feedback.
    - Added placeholder `action_show_help_screen`.
12. **Status Message:** Added `watch_status_message` to update the `Footer` when the `status_message` reactive variable changes (requires Footer to be queryable and have a `status` attribute or similar update mechanism).

---

## `pixabit/tui/data_processor.py`

**Refactored Code:**

```python
# pixabit/tui/data_processor.py

# SECTION: MODULE DOCSTRING
"""
Processes raw Habitica task data into specific data model objects.

Populates calculated fields (status, damage, tag names), and categorizes tasks
based on type and status. Also includes the function to calculate aggregate user
statistics using the processed task data and user context.

NOTE: This module assumes it receives raw dictionary data from the DataStore,
      which in turn got it from the API client. It operates synchronously.
"""

# SECTION: IMPORTS
import logging
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Type, cast # Use standard List/Dict

# Use textual's logger if running within Textual context, otherwise standard
try:
    from textual import log
except ImportError:
    # Fallback logger
    log = logging.getLogger(__name__) # type: ignore

# Local Imports (Adjust paths based on actual project structure)
try:
    from ..models.task import (
        ChallengeLinkData, # Renamed model
        ChecklistItem,
        Daily,
        Habit,
        Reward,
        Task, # Base task model
        TaskList, # TaskList container
        Todo,
    )
    # Import GameContentCache models if needed for context, but processor mainly uses lookups
    from ..models.game_content import Gear, Quest # Example content models
    # Import date helpers if used (e.g., for local time display in stats)
    # from ..helpers import convert_to_local_time, format_datetime_with_diff

    # Assuming GameContentCache provides lookup dictionaries now
    # from .game_content import GameContentCache # Not needed directly if lookups passed in

except ImportError as e:
    log.error(f"DataProcessor: Failed to import models/helpers: {e}. Using fallbacks.")
    # Define dummy models/classes if imports fail
    class Task: id: str = ""; type: str | None = None; value: float = 0.0; priority: float = 1.0; tags: list = []; challenge: Any = None; _status: str = "unknown"; value_color: str = "text"; tag_names: list = []; damage_user: float | None = None; damage_party: float | None = None; text: str = "" # type: ignore
    class Habit(Task): pass # type: ignore
    class Daily(Task): is_due: bool = False; completed: bool = False; checklist: list = [] # type: ignore
    class Todo(Task): completed: bool = False; due_date: Any = None; is_past_due: bool = False; checklist: list = [] # type: ignore
    class Reward(Task): pass # type: ignore
    class ChecklistItem: completed: bool = False # type: ignore
    class ChallengeLinkData: id: str | None = None; is_broken: bool = False; broken_status: str | None = None # type: ignore
    class Gear: pass # type: ignore
    class Quest: pass # type: ignore
    class TaskList: # type: ignore
         def __init__(self, tasks: list | None = None): self.tasks = tasks or []
         def __iter__(self): return iter(self.tasks)
         def __len__(self): return len(self.tasks)


# SECTION: TaskProcessor Class

# KLASS: TaskProcessor
class TaskProcessor:
    """Processes raw task dictionaries into structured Task data model objects.

    Calculates derived fields like status, value color, potential damage, and
    resolves tag names using provided context lookups.
    """

    # Mapping from API task type string to the corresponding Task subclass
    _TASK_TYPE_MAP: dict[str, Type[Task]] = {
        "habit": Habit,
        "daily": Daily,
        "todo": Todo,
        "reward": Reward,
    }
    # Default for unknown types
    _DEFAULT_TASK_CLASS: Type[Task] = Task

    # FUNC: __init__
    def __init__(
        self,
        user_data: dict[str, Any],
        party_data: dict[str, Any] | None,
        tags_lookup: dict[str, str], # Expecting {tag_id: tag_name}
        gear_lookup: dict[str, Gear], # Expecting {gear_key: GearObject}
        quests_lookup: dict[str, Quest], # Expecting {quest_key: QuestObject}
    ):
        """Initializes TaskProcessor with necessary context data lookups.

        Args:
            user_data: Raw user data dictionary (needed for context calculations).
            party_data: Raw party data dictionary, or None (for quest context).
            tags_lookup: Dictionary mapping Tag IDs to Tag names.
            gear_lookup: Dictionary mapping Gear keys to processed Gear objects.
            quests_lookup: Dictionary mapping Quest keys to processed Quest objects.
        """
        log.info("Initializing TaskProcessor...")

        # Validate critical context data
        if not isinstance(user_data, dict) or not user_data:
            log.critical("TaskProcessor requires valid user_data.")
            raise ValueError("TaskProcessor requires valid user_data.")
        if not isinstance(tags_lookup, dict):
            log.warning("TaskProcessor tags_lookup is not a dict.")
            tags_lookup = {} # Use empty dict if invalid
        if not isinstance(gear_lookup, dict):
            log.warning("TaskProcessor gear_lookup is not a dict.")
            gear_lookup = {}
        if not isinstance(quests_lookup, dict):
            log.warning("TaskProcessor quests_lookup is not a dict.")
            quests_lookup = {}

        # Store context lookups and raw data needed
        self.user_data = user_data
        self.party_data = party_data if isinstance(party_data, dict) else {}
        self.tags_lookup = tags_lookup
        self.gear_lookup = gear_lookup # Now stores Gear objects
        self.quests_lookup = quests_lookup # Now stores Quest objects

        # Calculate and store internal context values needed for processing tasks
        self.user_con: float = 0.0
        self.user_stealth: int = 0
        self.is_sleeping: bool = False
        self.is_on_boss_quest: bool = False
        self.boss_str: float = 0.0
        self.user_class: str | None = None # Store user class
        self._calculate_internal_context() # Calculate based on stored raw data

        log.info("TaskProcessor Context Initialized.")


    # FUNC: _calculate_internal_context
    def _calculate_internal_context(self) -> None:
        """Calculates and stores internal context like effective CON, stealth, etc."""
        log.debug("Calculating internal TaskProcessor context...")
        try:
            # --- User Stats Context ---
            # Use Pydantic User model for safer access if possible, otherwise dict.get
            # Assuming user_data is raw dict for now
            stats = self.user_data.get("stats", {})
            prefs = self.user_data.get("preferences", {})
            items = self.user_data.get("items", {})
            gear_data = items.get("gear", {})
            equipped_gear_keys = gear_data.get("equipped", {}) if isinstance(gear_data, dict) else {}

            level = int(stats.get("lvl", 0))
            self.user_class = stats.get("class") # Store class ('wizard', 'warrior', etc.)
            buffs = stats.get("buffs", {}) if isinstance(stats.get("buffs"), dict) else {}
            training = stats.get("training", {}) if isinstance(stats.get("training"), dict) else {}

            # Calculate CON (using formula similar to User model, but needs gear_lookup)
            level_bonus = min(50.0, math.floor(level / 2.0))
            alloc_con = float(stats.get("con", 0.0)) # Base CON points allocated
            buff_con = float(buffs.get("con", 0.0))
            train_con = float(training.get("con", 0.0))
            gear_con_total: float = 0.0

            if isinstance(equipped_gear_keys, dict) and self.gear_lookup:
                # Create temporary EquippedGear model for calculation? Or inline logic?
                # Inline logic using the gear_lookup (which contains Gear objects):
                 for gear_key in equipped_gear_keys.values():
                     if not gear_key or not isinstance(gear_key, str): continue
                     gear_obj = self.gear_lookup.get(gear_key)
                     if gear_obj and isinstance(gear_obj, Gear):
                         # Check item class vs user class for bonus
                         item_class = gear_obj.klass
                         class_bonus_mult = 1.5 if (item_class and (item_class == self.user_class or item_class == "base")) else 1.0
                         # Access stats via nested GearStats model
                         gear_con_total += float(gear_obj.stats.con) * class_bonus_mult

            # Effective CON = Base Points + Training + Level Bonus + Gear (with class bonus) + Buffs
            self.user_con = alloc_con + train_con + level_bonus + gear_con_total + buff_con

            # Other context values
            self.user_stealth = int(buffs.get("stealth", 0))
            self.is_sleeping = bool(prefs.get("sleep", False))

            # --- Party/Quest Context ---
            quest_info = self.party_data.get("quest", {})
            self.is_on_boss_quest = False
            self.boss_str = 0.0
            if isinstance(quest_info, dict) and quest_info.get("active") and not quest_info.get("completed"):
                quest_key = quest_info.get("key")
                if quest_key and self.quests_lookup:
                    # Look up Quest object
                    quest_obj = self.quests_lookup.get(quest_key)
                    if quest_obj and isinstance(quest_obj, Quest) and quest_obj.boss:
                         boss_info = quest_obj.boss
                         # Use Strength from the QuestBoss model
                         if boss_info.strength is not None:
                             self.is_on_boss_quest = True
                             self.boss_str = float(boss_info.strength) # Already float if parsed

            log.debug(f"Internal Context: CON={self.user_con:.1f}, Stealth={self.user_stealth}, Sleep={self.is_sleeping}, Class={self.user_class}, BossQuest={self.is_on_boss_quest}, BossStr={self.boss_str:.1f}")

        except Exception as e:
            log.error(f"Error calculating internal processor context: {e}", exc_info=True)
            # Reset defaults on error
            self.user_con, self.user_stealth, self.is_sleeping = 0.0, 0, False
            self.is_on_boss_quest, self.boss_str = False, 0.0
            self.user_class = None


    # FUNC: _value_color (Helper)
    def _value_color(self, value: float | None) -> str:
        """Determines a semantic style name based on task value."""
        if value is None: return "text-muted" # Style for unknown/neutral
        # Simplified mapping (adjust thresholds/colors as needed)
        if value > 10: return "success-dark" # Very positive
        elif value > 1: return "success"     # Positive
        elif value >= -1: return "text"        # Neutral / Slightly negative
        elif value > -10: return "warning"   # Negative
        else: return "error"                 # Very negative

    # FUNC: _calculate_checklist_done (Helper)
    def _calculate_checklist_done(self, checklist: list[ChecklistItem]) -> float:
        """Calculates proportion (0.0-1.0) of checklist items done."""
        if not checklist: return 1.0 # Treat no checklist as fully "done" for mitigation
        try:
            # Checklist items are already ChecklistItem objects if validation worked
            completed = sum(1 for item in checklist if item.completed)
            total = len(checklist)
            return completed / total if total > 0 else 1.0
        except Exception as e:
            log.warning(f"Error calculating checklist progress: {e}")
            return 1.0 # Default to max mitigation on error

    # FUNC: _calculate_task_damage (Helper)
    def _calculate_task_damage(self, task: Task) -> tuple[float | None, float | None]:
        """Calculates potential HP damage for a specific task if missed.

        Applies only to DUE, UNCOMPLETED Dailies when user is AWAKE and NOT STEALTHED.

        Args:
            task: The processed Task object (must be a Daily).

        Returns:
            A tuple (damage_to_user, damage_to_party). Values are None if no damage applies.
        """
        dmg_user: float | None = None
        dmg_party: float | None = None

        # Damage only applies to Dailies under specific conditions
        if not isinstance(task, Daily) or not task.is_due or task.completed or self.is_sleeping or self.user_stealth > 0:
            return None, None

        try:
            task_value = task.value
            # Use the checklist attribute directly from the Daily object
            checklist_proportion_done = self._calculate_checklist_done(task.checklist)
            priority_val = task.priority

            # Habitica Damage Formula components (constants can be fine-tuned)
            V_MIN, V_MAX = -47.27, 21.27 # Clamping thresholds for value
            BASE_DECAY_RATE = 0.9747 # Base decay rate for value effect

            clamped_value = max(V_MIN, min(task_value, V_MAX))
            # Damage potential increases as value gets more negative
            base_damage_potential = abs(math.pow(BASE_DECAY_RATE, clamped_value))
            # Checklist completion mitigates damage (more done = less damage)
            checklist_mitigation_factor = 1.0 - checklist_proportion_done
            effective_damage_potential = base_damage_potential * checklist_mitigation_factor

            # Constitution mitigates user damage
            con_mitigation_factor = max(0.1, 1.0 - (self.user_con / 250.0))

            # Priority multiplier (adjusts damage based on task importance)
            # Values from Habitica source (approx)
            prio_map = {0.1: 0.39, 1.0: 1.0, 1.5: 1.27, 2.0: 1.54} # Adjusted factors
            priority_multiplier = prio_map.get(priority_val, 1.0)

            # --- Calculate User HP Damage ---
            # Raw damage before CON mitigation
            raw_hp_damage = effective_damage_potential * priority_multiplier * 1.95 # Magic constant from source?
            # Apply CON mitigation
            hp_damage_calc = raw_hp_damage * con_mitigation_factor
            # Store if positive, otherwise None
            dmg_user = round(hp_damage_calc, 3) if hp_damage_calc > 0.01 else None

            # --- Calculate Party Damage (Boss Quest Only) ---
            if self.is_on_boss_quest and self.boss_str > 0:
                 # Boss damage uses slightly different scaling? Simpler approach:
                 # Use effective potential, maybe adjusted by priority differently?
                 # Habitica source suggests priority factor applies directly here too.
                 party_damage_calc = effective_damage_potential * priority_multiplier * self.boss_str
                 dmg_party = round(party_damage_calc, 3) if party_damage_calc > 0.01 else None

        except Exception as e_dmg:
            log.error(f"Error calculating damage for Daily {task.id}: {e_dmg}", exc_info=True)
            # Return None, None on error

        return dmg_user, dmg_party


    # FUNC: _determine_task_status (Helper)
    def _determine_task_status(self, task: Task) -> str:
         """Determines the display status string for a task."""
         if isinstance(task, Daily):
             if task.completed: return "success" # Completed Daily
             if task.is_due: return "due"       # Due Daily
             return "grey"                    # Not Due Daily
         elif isinstance(task, Todo):
             if task.completed: return "done"  # Completed Todo
             if task.is_past_due: return "red" # Past Due Todo
             if task.due_date: return "due"    # Due Todo (not past)
             return "grey"                    # Todo with no due date
         elif isinstance(task, Habit):
             return "habit" # Simple status for habits
         elif isinstance(task, Reward):
             return "reward" # Simple status for rewards
         else:
             return "unknown" # Fallback for base Task or unknown types


    # FUNC: process_task
    def process_task(self, raw_task_data: dict[str, Any]) -> Task | None:
        """Processes a single raw task dictionary into a fully populated Task object.

        Args:
            raw_task_data: The raw dictionary for a single task from the API.

        Returns:
            A processed Task object (Habit, Daily, Todo, or Reward) with calculated
            fields populated, or None if processing fails.
        """
        if not isinstance(raw_task_data, dict):
            log.warning(f"Skipping non-dict task data: {raw_task_data}")
            return None

        # 1. Create Base Task object instance (handles subclassing via Pydantic)
        task_type_str = raw_task_data.get("type")
        TaskModel = self._TASK_TYPE_MAP.get(task_type_str) if task_type_str else self._DEFAULT_TASK_CLASS

        try:
            task_instance = TaskModel.model_validate(raw_task_data)
        except ValidationError as e:
            task_id = raw_task_data.get("_id", raw_task_data.get("id", "N/A"))
            log.error(f"Validation failed for task ID {task_id}:\n{e}")
            return None
        except Exception as e:
            task_id = raw_task_data.get("_id", raw_task_data.get("id", "N/A"))
            log.error(f"Unexpected error creating task object ID {task_id}: {e}", exc_info=True)
            return None

        # 2. Perform post-instantiation processing and calculations
        try:
            # Assign Tag Names using lookup
            task_instance.tag_names = [
                self.tags_lookup.get(tag_id, f"ID:{tag_id}") # Use ID if name not found
                for tag_id in task_instance.tags
            ]

            # Determine Value Color
            task_instance.value_color = self._value_color(task_instance.value)

            # Determine Status String
            task_instance._status = self._determine_task_status(task_instance)

            # Calculate Potential Damage (for Dailies)
            dmg_user, dmg_party = self._calculate_task_damage(task_instance)
            task_instance.damage_user = dmg_user
            task_instance.damage_party = dmg_party

        except Exception as e_calc:
             log.error(f"Error during post-processing calculations for task {task_instance.id}: {e_calc}", exc_info=True)
             # Task instance is still created, but calculated fields might be default/missing

        return task_instance


    # FUNC: process_and_categorize_all
    def process_and_categorize_all(
        self, raw_task_list: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Processes a list of raw task data and categorizes the results.

        Args:
            raw_task_list: The list of raw task dictionaries from the API.

        Returns:
            A dictionary containing:
            - 'data': dict[str, Task] - Processed Task objects keyed by ID.
            - 'cats': dict[str, Any] - Categorized task IDs and metadata.
        """
        tasks_dict: dict[str, Task] = {}
        # Initialize categories structure
        cats_dict: dict[str, Any] = {
            "tasks": { # Task IDs categorized by type and status
                "habits": [],
                "todos": defaultdict(list), # Use defaultdict for todos statuses
                "dailys": defaultdict(list), # Use defaultdict for dailys statuses
                "rewards": [],
            },
            "tags": set(),           # Set of unique tag IDs used by tasks
            "broken": [],          # List of task IDs with broken challenge links
            "challenge_ids": set(), # Set of unique challenge IDs tasks belong to
        }

        if not isinstance(raw_task_list, list):
            log.error("Invalid raw_task_list provided to processor.")
            return {"data": {}, "cats": cats_dict} # Return empty structure

        log.info(f"Processing {len(raw_task_list)} raw tasks...")
        processed_count = 0
        skipped_count = 0

        for raw_task_data in raw_task_list:
            processed_task = self.process_task(raw_task_data)

            if processed_task and processed_task.id:
                tasks_dict[processed_task.id] = processed_task
                processed_count += 1

                # --- Categorization using the processed task object ---
                cats_dict["tags"].update(processed_task.tags) # Add all raw tag IDs

                if processed_task.challenge:
                    if processed_task.challenge.id:
                         cats_dict["challenge_ids"].add(processed_task.challenge.id)
                    if processed_task.challenge.is_broken:
                         cats_dict["broken"].append(processed_task.id)

                task_type = processed_task.type
                status = processed_task.status # Use the status property

                # Append ID to the correct category/status list
                if task_type == "habit":
                    cats_dict["tasks"]["habits"].append(processed_task.id)
                elif task_type == "reward":
                    cats_dict["tasks"]["rewards"].append(processed_task.id)
                elif task_type == "todo":
                    cats_dict["tasks"]["todos"][status].append(processed_task.id)
                elif task_type == "daily":
                    cats_dict["tasks"]["dailys"][status].append(processed_task.id)
                # else: task has unknown type, not categorized by type

            else:
                skipped_count += 1 # Task failed processing or had no ID

        # Finalize categories: convert sets/defaultdicts to sorted lists/dicts
        cats_dict["tags"] = sorted(list(cats_dict["tags"]))
        cats_dict["challenge_ids"] = sorted(list(cats_dict["challenge_ids"]))
        # Convert defaultdicts back to regular dicts
        cats_dict["tasks"]["todos"] = dict(cats_dict["tasks"]["todos"])
        cats_dict["tasks"]["dailys"] = dict(cats_dict["tasks"]["dailys"])

        log.info(f"Task processing complete. Processed: {processed_count}, Skipped: {skipped_count}")
        return {"data": tasks_dict, "cats": cats_dict}


# SECTION: User Stats Function (Remains largely the same logic)

# FUNC: get_user_stats
def get_user_stats(
    cats_dict: dict[str, Any],            # Expects 'cats' dictionary from processor
    processed_tasks_dict: dict[str, Task],# Expects 'data' dictionary (Task objects)
    user_data: dict[str, Any],           # Expects raw user data dict
    party_data: dict[str, Any] | None,   # Expects raw party data dict
) -> dict[str, Any] | None:
    """Generates combined user/task statistics dict using processed data.

    Args:
        cats_dict: The 'cats' dictionary from TaskProcessor results.
        processed_tasks_dict: The 'data' dictionary (Task objects) from processor.
        user_data: The raw user data dictionary from the API.
        party_data: The raw party data dictionary from the API.

    Returns:
        A dictionary containing combined user/task statistics, or None on critical failure.
    """
    log.debug("Calculating combined user stats...")
    # --- Input Validation ---
    if not isinstance(user_data, dict) or not user_data:
        log.error("Cannot calculate stats: Valid user_data required.")
        return None
    if not isinstance(cats_dict, dict):
        log.error("Cannot calculate stats: Valid cats_dict required.")
        return None
    if not isinstance(processed_tasks_dict, dict):
        log.error("Cannot calculate stats: Valid processed_tasks_dict required.")
        return None
    # Party data is optional, but check type if present
    if party_data is not None and not isinstance(party_data, dict):
         log.warning("Invalid party_data provided to get_user_stats, ignoring.")
         party_data = None

    try:
        # --- Extract from User/Party Data (using .get for safety) ---
        stats = user_data.get("stats", {})
        prefs = user_data.get("preferences", {})
        auth = user_data.get("auth", {})
        ts = auth.get("timestamps", {}) if isinstance(auth, dict) else {}
        local_auth = auth.get("local", {}) if isinstance(auth, dict) else {}
        balance = user_data.get("balance", 0.0)
        gems = int(balance * 4) if balance > 0 else 0
        u_class = stats.get("class", "warrior") # Default needed?
        last_login_ts = ts.get("loggedin")
        is_sleeping = bool(prefs.get("sleep", False))

        # Quest Info from party_data
        party_quest = party_data.get("quest", {}) if party_data else {}
        quest_active = isinstance(party_quest, dict) and party_quest.get("active", False) and not party_quest.get("completed")
        quest_key = party_quest.get("key") if isinstance(party_quest, dict) else None

        # --- Calculate Task Counts from cats_dict ---
        task_counts: dict[str, Any] = {}
        task_cats_data = cats_dict.get("tasks", {})
        if isinstance(task_cats_data, dict):
            for category, cat_data in task_cats_data.items():
                 if isinstance(cat_data, dict): # dailys/todos (nested statuses)
                     status_counts = {k: len(v) for k, v in cat_data.items() if isinstance(v, list)}
                     status_counts["_total"] = sum(status_counts.values())
                     task_counts[category] = status_counts
                 elif isinstance(cat_data, list): # habits/rewards (flat list)
                     task_counts[category] = len(cat_data)
        # Include totals for convenience
        task_counts["_total_all"] = sum(
             count if isinstance(count, int) else count.get("_total", 0)
             for count in task_counts.values()
        )


        # --- Calculate Total Damage (Sums pre-calculated values) ---
        dmg_user_total, dmg_party_total = 0.0, 0.0
        # Sum damage only from currently DUE dailies
        due_daily_ids = cats_dict.get("tasks", {}).get("dailys", {}).get("due", [])
        if isinstance(due_daily_ids, list):
            for task_id in due_daily_ids:
                task_obj = processed_tasks_dict.get(task_id)
                if task_obj: # Check if task exists in the processed dict
                    dmg_user_total += task_obj.damage_user or 0.0
                    dmg_party_total += task_obj.damage_party or 0.0


        # --- Assemble Output Dict ---
        output_stats = {
            "username": local_auth.get("username", "N/A"),
            "class": u_class,
            "level": int(stats.get("lvl", 0)),
            "hp": float(stats.get("hp", 0.0)),
            "maxHealth": int(stats.get("maxHealth", 50)),
            "mp": float(stats.get("mp", 0.0)),
            "maxMP": int(stats.get("maxMP", 0)),
            "exp": float(stats.get("exp", 0.0)),
            "toNextLevel": int(stats.get("toNextLevel", 0)),
            "gp": float(stats.get("gp", 0.0)),
            "gems": gems,
            "base_stats": { # Base allocated points only
                "str": int(stats.get("str", 0)),
                "int": int(stats.get("int", 0)),
                "con": int(stats.get("con", 0)),
                "per": int(stats.get("per", 0)),
            },
            "sleeping": is_sleeping,
            "day_start": int(prefs.get("dayStart", 0)),
            "last_login_utc": last_login_ts, # Keep raw timestamp string/None
            "quest_active": quest_active,
            "quest_key": quest_key,
            "task_counts": task_counts, # Nested dict of counts by type/status
            "broken_tasks_count": len(cats_dict.get("broken", [])),
            "challenge_ids": cats_dict.get("challenge_ids", []), # List of joined challenge IDs
            "active_tag_ids": cats_dict.get("tags", []), # List of tag IDs in use
            "potential_user_dmg": round(dmg_user_total, 3),
            "potential_party_dmg": round(dmg_party_total, 3),
        }
        log.debug("Combined user stats calculation complete.")
        return output_stats

    except Exception as e_stat:
        log.error(f"Error calculating combined user stats: {e_stat}", exc_info=True)
        return None # Return None on critical failure

```

**Suggestions & Comments:**

1.  **Typing & Imports:** Updated typing. Standardized imports. Imports specific Task subclasses. Imports `Gear`/`Quest` models for context lookups. Uses `textual.log` or fallback.
2.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:` anchors. Improved docstrings. Clarified purpose and synchronous nature.
3.  **TaskProcessor (`__init__`)**:
    - Now accepts pre-processed lookup dictionaries (`tags_lookup`, `gear_lookup`, `quests_lookup`) instead of raw lists or the `GameContentCache` instance. This makes the processor more focused and easier to test, decoupling it from cache management. `DataStore` becomes responsible for providing these lookups.
    - Added validation for the lookup dictionaries.
4.  **TaskProcessor (`_calculate_internal_context`)**:
    - Refined the context calculation, especially for `user_con`. It now correctly uses the `gear_lookup` (which contains processed `Gear` objects with nested `stats`) and applies the class bonus logic properly.
    - Stores `user_class` internally.
    - Uses the `quests_lookup` to get `Quest` objects for determining `boss_str`.
5.  **TaskProcessor (`_value_color`)**: Simplified the color mapping logic and used more descriptive style names (these should ideally match keys in your Rich theme).
6.  **TaskProcessor (`_calculate_task_damage`)**:
    - Moved damage calculation logic here from the main processing loop for clarity.
    - Takes a `Task` object as input.
    - Refined the conditions under which damage applies.
    - Uses internal context (`user_con`, `boss_str`, etc.).
    - Returns a tuple `(dmg_user, dmg_party)`, both potentially `None`.
7.  **TaskProcessor (`_determine_task_status`)**: Added a helper to centralize the logic for determining the `_status` string based on task type and properties.
8.  **TaskProcessor (`process_task`)**: Created a new method to process a _single_ task dictionary. This encapsulates:
    - Instantiating the correct Pydantic Task subclass.
    - Populating calculated fields (`tag_names`, `value_color`, `_status`, `damage_user`, `damage_party`) by calling helper methods.
    - Returns the processed `Task` object or `None` on failure.
9.  **TaskProcessor (`process_and_categorize_all`)**:
    - Now calls `self.process_task()` for each item in the raw list.
    - Categorization logic uses the fully processed `Task` object (including the `status` property and populated `challenge` object).
    - Uses `defaultdict(list)` for simpler categorization of todo/daily statuses.
    - Renamed `cats['challenge']` to `cats['challenge_ids']` for clarity (it stores IDs).
    - Converts sets/defaultdicts to lists/dicts at the end.
10. **`get_user_stats` Function**:
    - Now accepts `party_data` as an argument.
    - Extracts quest info from `party_data`.
    - Simplifies task count calculation using the structured `cats_dict`.
    - Sums damage by iterating through the relevant task IDs in `cats_dict` and looking up the pre-calculated damage on the `Task` objects in `processed_tasks_dict`.
    - Renamed some output keys for clarity (e.g., `base_stats`, `potential_user_dmg`). Removed local time conversion for simplicity (can be done in UI).

---

## `pixabit/tui/data_store.py`

**Refactored Code:**

```python
# pixabit/tui/data_store.py

# SECTION: MODULE DOCSTRING
"""
Provides the PixabitDataStore class, the central facade for TUI application state and logic.

Manages application data (User, Tasks, Tags, etc.) using processed Pydantic models,
orchestrates asynchronous API calls via HabiticaAPI, coordinates data processing
via TaskProcessor, handles content caching via GameContentCache, and notifies the
TUI of data changes using custom Messages.
"""

# SECTION: IMPORTS
import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union, cast # Use standard types

# Textual imports (use helpers where available)
try:
    from textual import log
    from textual.app import App # Needed for app reference type hint
except ImportError:
    # Fallback logger
    log = logging.getLogger(__name__) # type: ignore

# --- Pixabit Imports ---
try:
    # Core API & Config
    from ..habitica.api import HabiticaAPI, HabiticaAPIError
    from ..config import CACHE_DIR # Central cache directory config

    # Data Models
    from ..models.challenge import Challenge, ChallengeList
    from ..models.party import Party
    from ..models.tag import Tag, TagList, UserTag, ChallengeTag # Import specific tag types
    from ..models.task import Task, TaskList, Habit, Daily, Todo, Reward # Import Task subclasses
    from ..models.user import User
    # Models related to game content (used for lookups)
    from ..models.game_content import Gear, Quest, Spell, Pet, Mount

    # TUI Specific Components
    from .messages import DataRefreshed, UIMessageRequest, ErrorOccurred # Use specific message types
    from .game_content import GameContentCache # Use the dedicated content cache manager
    from .data_processor import TaskProcessor, get_user_stats # Import processor and stats func
    # Import TagManager if it exists and is used
    # from .tag_manager import TagManager

    # Helpers (optional, depending on usage)
    from ..helpers import load_json, save_json

except ImportError as e:
    log.critical(f"FATAL: Failed to import Pixabit components in DataStore: {e}", exc_info=True)
    import sys
    sys.exit(1)


# SECTION: PixabitDataStore Class

# KLASS: PixabitDataStore
class PixabitDataStore:
    """Central facade for managing Habitica data, API interactions, and processing.

    Holds the application state (processed objects) and provides methods for access
    and modification, notifying the UI layer upon data refresh completion.
    """
    # Define cache paths relative to the main cache dir
    CHALLENGES_CACHE_PATH: Path = CACHE_DIR / "challenges_cache.json" # Example cache file

    # FUNC: __init__
    def __init__(self, app: App):
        """Initializes the DataStore.

        Args:
            app: The Textual App instance, used for posting messages.
        """
        self.app = app
        log.info("DataStore: Initializing...")

        try:
            # Initialize API Client (handles its own config loading)
            self.api_client = HabiticaAPI()
            # Initialize Game Content Cache (passing API client is optional, it can create one)
            self.content_cache = GameContentCache(api_client=self.api_client)
            # Initialize Tag Manager (if used) - requires API client
            # self.tag_manager = TagManager(api_client=self.api_client)
            # Processor is initialized dynamically during refresh when context is available
            self.processor: TaskProcessor | None = None
        except ValueError as e: # Catch missing credentials from API init
            log.critical(f"DataStore Init Error: {e}. Check credentials/config.", exc_info=True)
            self.app.post_message(ErrorOccurred("Initialization", e, "Credentials missing?"))
            raise # Propagate critical init errors
        except Exception as e:
            log.critical(f"DataStore Init Error: {e}", exc_info=True)
            self.app.post_message(ErrorOccurred("Initialization", e, "Unexpected error"))
            raise

        # --- Application State ---
        # Store processed Pydantic model instances
        self.user_obj: User | None = None
        self.party_obj: Party | None = None
        self.tags_list_obj: TagList | None = None
        self.tasks_list_obj: TaskList | None = None
        self.challenges_list_obj: ChallengeList | None = None
        # self.spells_list_obj: SpellList | None = None # Add if SpellList model exists

        # Store aggregated/derived data
        self.user_stats_dict: dict[str, Any] = {} # Combined stats for quick UI access
        self.cats_data: dict[str, Any] = {} # Task categorization results

        # Store raw cache for items not yet fully modeled or needing direct access
        self._raw_challenges_cache: list[dict[str, Any]] = [] # Store raw challenge list

        # Concurrency control and state flags
        self.is_refreshing = asyncio.Lock()
        self.data_loaded_at_least_once: bool = False

        log.info("DataStore initialized successfully.")

    # --- Internal Helper Methods ---

    # FUNC: _load_or_fetch_challenges (Raw Cache Handling)
    async def _load_or_fetch_challenges(self) -> None:
        """Loads raw challenges from cache or fetches from API if needed."""
        log.info("DataStore: Loading/Fetching Raw Challenges...")
        # Try loading from cache first
        # Use helper function with error handling
        cached_data = load_json(self.CHALLENGES_CACHE_PATH)

        if isinstance(cached_data, list):
            log.info(f"DataStore: Loaded {len(cached_data)} raw challenges from cache.")
            self._raw_challenges_cache = cached_data
            return # Loaded successfully

        log.info("DataStore: Raw challenge cache missing or invalid. Fetching from API.")
        # Fetch if not loaded from cache
        try:
            # Use the paginated fetch method from the API client's mixin
            # Ensure the API client instance has the ChallengesMixin methods
            if hasattr(self.api_client, 'get_all_challenges_paginated'):
                # Specify cast for type checker clarity
                fetched_challenges = cast(List[Dict[str, Any]], await self.api_client.get_all_challenges_paginated(member_only=True)) # type: ignore [attr-defined]

                if isinstance(fetched_challenges, list):
                    log.info(f"DataStore: Fetched {len(fetched_challenges)} raw challenges.")
                    self._raw_challenges_cache = fetched_challenges
                    # Save the fetched data back to cache
                    save_ok = save_json(self._raw_challenges_cache, self.CHALLENGES_CACHE_PATH)
                    if not save_ok: log.warning("DataStore: Failed to save raw challenges cache.")
                else:
                    log.error("DataStore: Fetched challenges API call returned invalid type.")
                    self._raw_challenges_cache = [] # Use empty list on fetch error
            else:
                 log.error("API client does not have 'get_all_challenges_paginated' method.")
                 self._raw_challenges_cache = []

        except HabiticaAPIError as e:
            log.error(f"DataStore: API Error fetching challenges: {e}")
            self._raw_challenges_cache = [] # Use empty list on error
        except Exception as e:
            log.error(f"DataStore: Unexpected error fetching challenges: {e}", exc_info=True)
            self._raw_challenges_cache = []

    # FUNC: _post_status_update
    def _post_status_update(self, message: str, temporary: bool = True):
         """Helper to post status updates to the UI."""
         try:
              self.app.post_message(ShowStatusRequest(message, temporary=temporary))
         except Exception as e:
              log.warning(f"Failed to post status update '{message}': {e}")


    # --- Main Data Refresh Orchestration ---

    # FUNC: refresh_all_data
    async def refresh_all_data(self) -> None:
        """Fetches all required data concurrently, processes it, updates state, and notifies UI.

        Handles errors internally and posts DataRefreshed or ErrorOccurred messages.
        """
        if await self.is_refreshing.acquire(blocking=False): # Try to acquire lock non-blockingly
            log.info("DataStore: Starting full data refresh...")
            start_time = time.monotonic()
            self._post_status_update("Refreshing data...", temporary=False)
            success = False
            error_message: str | None = None
            raw_data: dict[str, Any] = {} # Store fetched results

            try:
                # --- 1. Prepare Context Data (Content Lookups, Raw Challenges) ---
                # Ensure game content lookups are ready (loads/fetches if needed)
                # Use asyncio.gather for concurrent preparation
                content_prep_tasks = {
                    "gear": self.content_cache.get_gear(),
                    "quests": self.content_cache.get_quests(),
                    "spells": self.content_cache.get_spells(), # Assuming get_spells() exists
                    "tags_lookup": self._prepare_tags_lookup(), # Make tags prep async?
                    "raw_challenges": self._load_or_fetch_challenges(), # Handles its own caching
                }
                prep_results = await asyncio.gather(
                    *content_prep_tasks.values(), return_exceptions=True
                )
                context_data = dict(zip(content_prep_tasks.keys(), prep_results))

                # Check for errors during context prep
                for key, result in context_data.items():
                    if isinstance(result, Exception):
                         raise RuntimeError(f"Failed to prepare context data '{key}': {result}") from result

                # Extract context lookups (adjust keys if needed)
                gear_lookup = cast(Dict[str, Gear], context_data["gear"])
                quests_lookup = cast(Dict[str, Quest], context_data["quests"])
                tags_lookup = cast(Dict[str, str], context_data["tags_lookup"])
                # raw_challenges are now in self._raw_challenges_cache

                # --- 2. Fetch Core Dynamic Data ---
                log.info("DataStore: Fetching dynamic API data (user, party, tasks)...")
                core_fetch_tasks = {
                    "user": self.api_client.get_user_data(),
                    "party": self.api_client.get_party_data(),
                    "tasks": self.api_client.get_tasks(),
                    # Add other dynamic fetches if needed (e.g., messages)
                }
                core_results = await asyncio.gather(
                    *core_fetch_tasks.values(), return_exceptions=True
                )
                raw_data = dict(zip(core_fetch_tasks.keys(), core_results))

                # Check for critical fetch errors (user, tasks)
                if isinstance(raw_data.get("user"), Exception) or not raw_data.get("user"):
                    raise ValueError("User data fetch failed.")
                if isinstance(raw_data.get("tasks"), Exception):
                    raise ValueError("Task data fetch failed.")
                # Handle party fetch error gracefully (user might not be in a party)
                if isinstance(raw_data.get("party"), Exception):
                     log.warning(f"Party data fetch failed: {raw_data['party']}. Continuing without party data.")
                     raw_data['party'] = None # Set to None if fetch failed

                # --- 3. Initialize Processor with all context ---
                log.info("DataStore: Initializing TaskProcessor...")
                self.processor = TaskProcessor(
                    user_data=raw_data["user"],
                    party_data=raw_data["party"],
                    tags_lookup=tags_lookup,
                    gear_lookup=gear_lookup,
                    quests_lookup=quests_lookup,
                )

                # --- 4. Process Tasks ---
                log.info("DataStore: Processing tasks...")
                processed_results = self.processor.process_and_categorize_all(raw_data["tasks"])
                processed_task_objects_dict = processed_results.get("data", {})
                self.cats_data = processed_results.get("cats", {}) # Store categories

                # --- 5. Instantiate/Update Model Objects & Containers ---
                log.info("DataStore: Updating state models...")
                # User object needs gear lookup for stat calculations
                self.user_obj = User.model_validate(raw_data["user"])
                self.party_obj = Party.model_validate(raw_data["party"]) if raw_data.get("party") else None
                # Assume TagManager/lookup provided `tags_lookup` used by processor; create TagList if needed
                # This assumes self._prepare_tags_lookup returns the raw list needed by TagList model
                _raw_tags_list = await self._prepare_tags_lookup(return_list=True)
                self.tags_list_obj = TagList.from_raw_data(_raw_tags_list) # Create TagList model instance
                self.tasks_list_obj = TaskList(list(processed_task_objects_dict.values()))
                # Create ChallengeList and link tasks
                self.challenges_list_obj = ChallengeList(self._raw_challenges_cache)
                if self.tasks_list_obj:
                     self.challenges_list_obj.link_tasks(self.tasks_list_obj)
                # self.spells_list_obj = ... # Create SpellList if applicable

                # --- 6. Calculate Final Aggregate Stats ---
                log.info("DataStore: Calculating aggregate user stats...")
                stats_result = get_user_stats(
                    cats_dict=self.cats_data,
                    processed_tasks_dict=processed_task_objects_dict,
                    user_data=raw_data["user"],
                    party_data=raw_data["party"], # Pass party data
                )
                self.user_stats_dict = stats_result if stats_result else {} # Store result or empty dict

                success = True # Mark overall success
                self.data_loaded_at_least_once = True
                error_message = None # Clear previous error if successful
                log.info("DataStore: Refresh sequence completed successfully.")

            except Exception as e:
                success = False
                error_message = f"Refresh failed: {type(e).__name__} - {e}"
                log.error(f"DataStore: Error during refresh sequence: {error_message}", exc_info=True)
                # Post specific error message
                self.app.post_message(ErrorOccurred("Data Refresh", e, raw_data))

            finally:
                # Release lock and notify UI
                self.is_refreshing.release()
                log.info("DataStore: Released refresh lock.")
                # Post DataRefreshed message with success status
                try:
                    self.app.post_message(DataRefreshed(success=success, message=error_message))
                    log.info(f"DataStore: Posted DataRefreshed(success={success}).")
                except Exception as e_post:
                     log.error(f"DataStore: Failed to post DataRefreshed message: {e_post}")

                end_time = time.monotonic()
                duration = end_time - start_time
                status = "successful" if success else "failed"
                log.info(f"DataStore: Refresh finished in {duration:.2f}s ({status}).")
                self._post_status_update(f"Refresh {status}. ({duration:.1f}s)", temporary=True)

        else:
             log.warning("DataStore: Refresh already in progress, skipping request.")
             # Optionally notify user request was skipped
             # self.app.post_message(UIMessageRequest("Refresh already running.", severity="warning", timeout=2))

    # FUNC: _prepare_tags_lookup (Helper for tag data)
    async def _prepare_tags_lookup(self, return_list: bool = False) -> dict[str, str] | list[dict[str, Any]]:
         """Fetches tags and prepares a lookup dict or returns the raw list."""
         try:
              # TODO: Implement caching for tags if desired
              raw_tags = await self.api_client.get_tags() # Assuming get_tags fetches List[Dict]
              if return_list:
                   return raw_tags if isinstance(raw_tags, list) else []

              if isinstance(raw_tags, list):
                   lookup = {
                       tag["id"]: tag.get("name", f"ID:{tag['id'][:6]}")
                       for tag in raw_tags if isinstance(tag, dict) and "id" in tag
                   }
                   return lookup
              else:
                   log.warning("Failed to fetch a valid list of tags from API.")
                   return [] if return_list else {}
         except Exception as e:
              log.error(f"Error preparing tags lookup: {e}")
              return [] if return_list else {}


    # SECTION: Data Accessor Methods (Synchronous reads)

    # FUNC: get_user
    def get_user(self) -> User | None: return self.user_obj
    # FUNC: get_user_stats
    def get_user_stats(self) -> dict[str, Any]: return self.user_stats_dict
    # FUNC: get_party
    def get_party(self) -> Party | None: return self.party_obj
    # FUNC: get_tags
    def get_tags(self) -> list[Tag]: return self.tags_list_obj.tags if self.tags_list_obj else []
    # FUNC: get_tasks
    def get_tasks(self, **filters: Any) -> TaskList: # Return TaskList object
         """Returns the TaskList object, allowing further filtering by the caller."""
         # TODO: Apply basic filters here if needed, or let caller use TaskList methods
         if not self.tasks_list_obj:
              return TaskList([]) # Return empty TaskList if not loaded
         # Apply simple type filter if provided
         if task_type := filters.get("task_type"):
              return self.tasks_list_obj.filter_by_type(task_type)
         # Apply text filter if provided
         if text_filter := filters.get("text_filter"):
              return self.tasks_list_obj.filter_by_text(text_filter)

         return self.tasks_list_obj # Return the full list object


    # FUNC: get_challenges
    def get_challenges(self) -> list[Challenge]: return self.challenges_list_obj.challenges if self.challenges_list_obj else []
    # FUNC: get_spells
    # def get_spells(self) -> list[Spell]: return self.spells_list_obj.spells if self.spells_list_obj else []


    # SECTION: Action Methods (Asynchronous - Trigger API calls & Refresh)

    # FUNC: toggle_sleep
    async def toggle_sleep(self) -> bool:
        """Toggles the user's sleep status via API and triggers data refresh."""
        log.info("DataStore: Action - Toggle sleep...")
        self._post_status_update("Toggling sleep status...")
        try:
            # Use the specific API method
            new_state = await self.api_client.toggle_user_sleep()

            if new_state is not None: # API call succeeded and returned state
                log.info(f"DataStore: Sleep toggle API successful. New state: {new_state}")
                # Trigger full refresh in background to update all related data
                asyncio.create_task(self.refresh_all_data())
                # Post immediate success message
                self.app.post_message(UIMessageRequest(f"Sleep status set to: {'Sleeping' if new_state else 'Awake'}", severity="information"))
                return True
            else:
                log.warning("DataStore: Sleep toggle API call failed or returned unexpected data.")
                self.app.post_message(UIMessageRequest("Failed to toggle sleep (API error).", severity="warning"))
                return False
        except HabiticaAPIError as e:
            log.error(f"DataStore: API Error toggling sleep: {e}")
            self.app.post_message(UIMessageRequest(f"API Error toggling sleep: {e}", severity="error"))
            return False
        except Exception as e:
            log.error(f"DataStore: Unexpected error toggling sleep: {e}", exc_info=True)
            self.app.post_message(UIMessageRequest("Unexpected error toggling sleep.", severity="error"))
            return False
        finally:
             self._post_status_update("Toggle sleep attempt finished.", temporary=True)


    # FUNC: score_task
    async def score_task(self, task_id: str, direction: str) -> bool:
        """Scores a task via API and triggers data refresh."""
        log.info(f"DataStore: Action - Scoring task {task_id} {direction}...")
        self._post_status_update(f"Scoring task {task_id[:8]}... {direction}")
        try:
            # Use the specific API method
            result = await self.api_client.score_task(task_id, direction) # type: ignore [arg-type] # Allow string direction
            if result is not None: # API call succeeded (result has score deltas)
                log.info(f"DataStore: Task {task_id} scored {direction}. Deltas: {result}")
                # Trigger refresh in background
                asyncio.create_task(self.refresh_all_data())
                # Optionally post immediate feedback based on result (e.g., drops)
                # self.app.post_message(UIMessageRequest(f"Task scored! Drops: {result.get('drop')}", severity="information"))
                return True
            else:
                log.warning(f"DataStore: Score task API call failed or returned no data for {task_id}.")
                self.app.post_message(UIMessageRequest(f"Failed to score task {task_id[:8]}.", severity="warning"))
                return False
        except HabiticaAPIError as e:
            log.error(f"DataStore: API Error scoring task {task_id}: {e}")
            self.app.post_message(UIMessageRequest(f"API Error scoring task: {e}", severity="error"))
            return False
        except Exception as e:
            log.error(f"DataStore: Unexpected error scoring task {task_id}: {e}", exc_info=True)
            self.app.post_message(UIMessageRequest("Unexpected error scoring task.", severity="error"))
            return False
        finally:
             self._post_status_update(f"Score task {task_id[:8]} attempt finished.", temporary=True)


    # --- Add other action methods (leave_challenge, unlink_task, delete_tag, etc.) ---
    # --- following the pattern: log, call API, handle result/error, post message, trigger refresh ---

    # Example: Delete Tag
    async def delete_tag(self, tag_id: str) -> bool:
        """Deletes a tag globally via API and triggers data refresh."""
        log.info(f"DataStore: Action - Deleting tag {tag_id}...")
        self._post_status_update(f"Deleting tag {tag_id[:8]}...")
        try:
            success = await self.api_client.delete_tag(tag_id)
            if success:
                log.info(f"DataStore: Deleted tag {tag_id} successfully.")
                asyncio.create_task(self.refresh_all_data())
                self.app.post_message(UIMessageRequest(f"Tag {tag_id[:8]} deleted.", severity="information"))
                return True
            else:
                log.warning(f"DataStore: Delete tag API call failed for {tag_id}.")
                self.app.post_message(UIMessageRequest(f"Failed to delete tag {tag_id[:8]}.", severity="warning"))
                return False
        except HabiticaAPIError as e:
            log.error(f"DataStore: API Error deleting tag {tag_id}: {e}")
            self.app.post_message(UIMessageRequest(f"API Error deleting tag: {e}", severity="error"))
            return False
        except Exception as e:
            log.error(f"DataStore: Unexpected error deleting tag {tag_id}: {e}", exc_info=True)
            self.app.post_message(UIMessageRequest("Unexpected error deleting tag.", severity="error"))
            return False
        finally:
             self._post_status_update(f"Delete tag {tag_id[:8]} attempt finished.", temporary=True)
```

**Suggestions & Comments:**

1.  **Typing & Imports:** Updated typing. Standardized imports. Imports specific model classes and message types. Uses `cast` where necessary.
2.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:` anchors. Improved docstrings.
3.  **Initialization (`__init__`)**:
    - Correctly initializes `api_client` and `content_cache`.
    - Removes `TagManager` initialization (assuming tag logic is simpler or integrated elsewhere for now).
    - Initializes state attributes (`user_obj`, `tasks_list_obj`, etc.) to `None` or empty collections.
    - Adds more robust error handling during initialization.
4.  **Refresh Logic (`refresh_all_data`)**:
    - Refactored significantly for clarity and better error handling.
    - Now uses `asyncio.Lock` correctly with `acquire(blocking=False)` and `release()` in `finally`.
    - **Concurrency:** Uses `asyncio.gather` to fetch _context_ data (content lookups, tags, raw challenges) concurrently first. Then uses another `gather` to fetch the _dynamic_ core data (user, party, tasks).
    - **Context Preparation:** Explicitly awaits necessary data from `GameContentCache` _before_ initializing `TaskProcessor`. Includes preparing the `tags_lookup`.
    - **Error Handling:** Checks for exceptions after each `gather` call. Raises specific `RuntimeError` or `ValueError` if critical context/data fetching fails. Posts `ErrorOccurred` message on failure.
    - **State Update:** Updates internal model instances (`user_obj`, `tasks_list_obj`, etc.) after successful fetching and processing. Links challenges and tasks. Calculates aggregate stats.
    - **Notification:** Posts `DataRefreshed` message in the `finally` block, indicating success or failure.
5.  **Challenge Caching (`_load_or_fetch_challenges`)**: Handles loading/fetching the _raw_ challenge list and caching it to a JSON file. `ChallengeList` model processing happens during the main refresh.
6.  **Tag Lookup (`_prepare_tags_lookup`)**: Added helper to fetch tags and create the ID->Name lookup dictionary needed by `TaskProcessor`. Added `return_list` option for when the raw list is needed (e.g., for `TagList` model init). _Consider adding caching here._
7.  **Accessor Methods (`get_user`, `get_tasks`, etc.)**: These are synchronous reads of the current state. `get_tasks` now returns the `TaskList` object, allowing the caller (e.g., `TaskListWidget`) to apply further filtering. Added basic type/text filtering within `get_tasks` as an example.
8.  **Action Methods (`toggle_sleep`, `score_task`, `delete_tag`, etc.)**:
    - Follow a standard pattern: Log action -> Post status update -> Call specific `api_client` method -> Handle success/failure -> Post result message -> Trigger background refresh (`asyncio.create_task(self.refresh_all_data())`) -> Return boolean status.
    - Use specific custom messages (`UIMessageRequest`, `ShowStatusRequest`).
    - Improved error handling using `try...except HabiticaAPIError...except Exception`.
9.  **Status Updates:** Added `_post_status_update` helper and calls it to provide feedback during actions.

---

## `pixabit/tui/game_content.py`

**Analysis:**

- This file was already refactored when `pixabit/models/data.py` was processed and renamed. The code generated in the previous response for `pixabit/models/game_content.py` is the correct refactored version.

**Action:**

- No changes needed here. Ensure the content matches the refactored version provided earlier.

---

## `pixabit/tui/widgets/placeholder.py`

**Refactored Code:**

```python
# pixabit/tui/widgets/placeholder.py

# SECTION: MODULE DOCSTRING
"""A simple placeholder widget for layout purposes during TUI development."""

# SECTION: IMPORTS
from textual.app import ComposeResult # Not strictly needed but good practice
from textual.widgets import Static

# SECTION: WIDGET CLASS

# KLASS: PlaceholderWidget
class PlaceholderWidget(Static):
    """A basic placeholder Static widget with default styling."""

    DEFAULT_CSS = """
    PlaceholderWidget {
        border: round $accent-lighten-2; /* Use theme variable */
        background: $panel-darken-2;   /* Use theme variable */
        color: $text-muted;            /* Use theme variable */
        content-align: center middle;
        height: 100%; /* Often useful for placeholders */
        width: 100%;
        text-style: italic;
    }
    """

    # FUNC: __init__
    def __init__(self, label: str = "Placeholder", **kwargs):
        """Initialize the placeholder with a label.

        Args:
            label: The text to display inside the placeholder.
            **kwargs: Additional keyword arguments for Static.
        """
        super().__init__(f"[dim italic]({label})[/]", **kwargs) # Add markup for clarity

    # Compose is inherited from Static, no need to override for basic text
    # def compose(self) -> ComposeResult:
    #     yield from super().compose() # Or just remove compose
```

**Suggestions & Comments:**

1.  **Typing:** Standard typing.
2.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:` anchors.
3.  **CSS:** Uses Textual CSS variables (`$accent-lighten-2`, etc.) assuming they are defined in the main CSS file. Added `text-style: italic`.
4.  **Initialization:** Added dim italic markup to the label passed to the `Static` parent for better visual distinction as a placeholder.
5.  **`compose`:** Removed the redundant `compose` method override.

---

## `pixabit/tui/widgets/settings_panel.py`

**Refactored Code:**

```python
# pixabit/tui/widgets/settings_panel.py

# SECTION: MODULE DOCSTRING
"""Defines the SettingsPanel widget for displaying application settings."""

# SECTION: IMPORTS
from textual.app import ComposeResult
from textual.containers import VerticalScroll # Allow scrolling for settings
from textual.widgets import Checkbox, Input, Label, Static, Rule # Example widgets

# SECTION: WIDGET CLASS

# KLASS: SettingsPanel
class SettingsPanel(Static): # Inherit from Static or Container
    """A panel widget to display and potentially modify application settings."""

    DEFAULT_CSS = """
    SettingsPanel {
        padding: 1 2; /* Add padding */
    }
    SettingsPanel > VerticalScroll { /* Style the scrollable container */
         border: round $accent;
         padding: 1;
    }
    SettingsPanel .setting-label {
        margin-top: 1;
        text-style: bold;
    }
    SettingsPanel Input {
        margin-bottom: 1;
    }
    SettingsPanel Checkbox {
         margin-bottom: 1;
    }
    """

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Create the content of the settings panel."""
        # Use VerticalScroll to handle potentially many settings
        with VerticalScroll():
            yield Label("Application Settings", classes="title") # Example title class
            yield Rule()

            yield Label("API Configuration", classes="setting-label")
            # Display API info (read-only for security)
            # TODO: Load actual config values securely if needed, mask token
            yield Static("User ID: user_id_here", classes="setting-value")
            yield Static("API Token: ********", classes="setting-value")
            yield Static("Base URL: base_url_here", classes="setting-value")

            yield Rule()

            yield Label("Cache Settings", classes="setting-label")
            # Example setting using Input (read-only example)
            yield Label("Cache Duration (Days):")
            yield Input(value="7", disabled=True, id="cache-duration-input")

            yield Rule()

            yield Label("UI Preferences", classes="setting-label")
            # Example setting using Checkbox
            yield Checkbox("Enable Notifications", True, id="enable-notifications-cb")
            yield Checkbox("Confirm Actions", False, id="confirm-actions-cb")

            # Add more setting sections and widgets as needed
```

**Suggestions & Comments:**

1.  **Typing:** Standard typing.
2.  **Imports:** Added relevant widgets (`VerticalScroll`, `Checkbox`, `Input`, `Label`, `Rule`).
3.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:` anchors.
4.  **Structure:** Changed base class to `Static` (or could be `Container`). Used `VerticalScroll` inside `compose` to allow scrolling if settings content becomes long.
5.  **Content:** Added example structure with labels, rules, and placeholder setting widgets (`Static` for read-only API info, disabled `Input`, `Checkbox`). **Security Note:** Avoid displaying the full API token directly in the UI.
6.  **CSS:** Added `DEFAULT_CSS` with basic padding and styling for the scrollable container and example setting elements. Uses theme variables.
7.  **Functionality:** This is currently just a display panel. Adding interaction (e.g., saving settings) would require adding event handlers (`on_mount` to load settings, `on_checkbox_changed`, `on_input_submitted`, etc.) and methods to interact with a configuration manager or the `DataStore`.

---

## `pixabit/tui/widgets/stats_panel.py`

**Refactored Code:**

```python
# pixabit/tui/widgets/stats_panel.py

# SECTION: MODULE DOCSTRING
"""Defines the StatsPanel widget for displaying key Habitica user statistics."""

# SECTION: IMPORTS
from typing import Any, Dict, Optional

# Use textual's logger
try:
    from textual import log
except ImportError:
    import logging
    log = logging.getLogger(__name__) # type: ignore

# Textual Imports
from textual.app import ComposeResult
from textual.containers import Container # Use Container for layout flexibility
from textual.widget import Widget
from textual.widgets import Static # Use Static for individual stat lines

# SECTION: WIDGET CLASS

# KLASS: StatsPanel
class StatsPanel(Container): # Inherit from Container for layout control
    """A widget to display summarized Habitica user statistics."""

    DEFAULT_CSS = """
    StatsPanel {
        height: auto; /* Adjust height automatically */
        padding: 0 1; /* Add horizontal padding */
        border-bottom: thick $accent-darken-1; /* Separator line */
        background: $surface0; /* Slightly different background */
        /* Use horizontal layout for stats */
        layout: horizontal;
        grid-size: 6; /* Define columns for stats */
        grid-gutter: 1 2;
    }
    StatsPanel > Static { /* Style direct Static children */
        width: 1fr; /* Distribute width equally */
        height: 1; /* Keep height tight */
        text-align: center;
        content-align: center middle;
    }
    /* Specific stat styling using IDs */
    #stat-level { color: $mauve; }
    #stat-class { color: $text; }
    #stat-hp { color: $red; }
    #stat-mp { color: $blue; }
    #stat-exp { color: $yellow; }
    #stat-gp { color: $peach; }
    /* #stat-gems { color: $green; } */ /* Optional */
    /* #stat-status { color: $subtext1; } */ /* Optional */
    """

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Create Static widgets for each statistic."""
        # Yield Static widgets directly inside the Container (uses horizontal layout from CSS)
        yield Static("Lvl --", id="stat-level")
        yield Static("Class --", id="stat-class")
        yield Static("HP --/--", id="stat-hp")
        yield Static("MP --/--", id="stat-mp")
        yield Static("XP --/--", id="stat-exp")
        yield Static("GP --", id="stat-gp")
        # yield Static("Gems --", id="stat-gems") # Optional: Add Gems
        # yield Static("Status: --", id="stat-status") # Optional: Add Status (Sleeping/Awake)

    # FUNC: update_display
    def update_display(self, stats_data: dict[str, Any] | None) -> None:
        """Updates the displayed statistics based on data from DataStore.

        Args:
            stats_data: The dictionary returned by DataStore.get_user_stats(), or None.
        """
        log.debug(f"StatsPanel: Attempting to update display. Data provided: {bool(stats_data)}")

        # --- Define Placeholder Texts ---
        placeholders = {
            "stat-level": "Lvl --",
            "stat-class": "Class --",
            "stat-hp": "HP --/--",
            "stat-mp": "MP --/--",
            "stat-exp": "XP --/--",
            "stat-gp": "GP --",
            # "stat-gems": "Gems --",
            # "stat-status": "Status: --",
        }

        # --- Update Logic ---
        if not stats_data:
            log.warning("StatsPanel received no data. Displaying placeholders.")
            update_values = placeholders # Use placeholders if no data
        else:
            # Safely extract values from stats_data, providing defaults
            level = stats_data.get("level", "--")
            u_class = str(stats_data.get("class", "--")).capitalize()
            hp = stats_data.get("hp", 0.0)
            max_hp = stats_data.get("maxHealth", 0)
            mp = stats_data.get("mp", 0.0)
            max_mp = stats_data.get("maxMP", 0)
            exp = stats_data.get("exp", 0.0)
            next_lvl_exp = stats_data.get("toNextLevel", 0)
            gp = stats_data.get("gp", 0.0)
            # gems = stats_data.get("gems", "--")
            # sleeping = stats_data.get("sleeping", False)
            # status = "[yellow]Sleep[/]" if sleeping else "[green]Awake[/]" # Example status formatting

            # --- Create Formatted Strings ---
            update_values = {
                "stat-level": f"Lvl [b]{level}[/]",
                "stat-class": f"{u_class}", # No label, just class name
                "stat-hp": f"HP [b]{hp:.0f}[/]/[dim]{max_hp}[/]", # No decimals for HP
                "stat-mp": f"MP [b]{mp:.0f}[/]/[dim]{max_mp}[/]", # No decimals for MP
                "stat-exp": f"XP [b]{exp:.0f}[/]/[dim]{next_lvl_exp}[/]",
                "stat-gp": f"GP [b]{gp:.1f}[/]", # One decimal for GP
                # "stat-gems": f"Gems [b]{gems}[/]",
                # "stat-status": f"Status: {status}",
            }

        # --- Update Widgets ---
        for widget_id, text in update_values.items():
            try:
                widget = self.query_one(f"#{widget_id}", Static)
                widget.update(text)
            except Exception as e:
                # Log specific widget update errors but continue
                log.error(f"StatsPanel: Error updating widget '{widget_id}': {e}")

        log.info("StatsPanel display updated.")

```

**Suggestions & Comments:**

1.  **Typing:** Standard typing.
2.  **Imports:** Uses `textual.log`. Imports `Container` and `Static`.
3.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:` anchors.
4.  **Base Class:** Changed base class to `Container` to allow direct layout control using CSS (`layout: horizontal`).
5.  **CSS:**
    - Updated CSS to use `layout: horizontal` and `grid-size` for distributing the `Static` widgets.
    - Uses theme variables (`$accent-darken-1`, `$surface0`, `$red`, etc.).
    - Simplified individual stat styling using IDs and theme colors.
    - Set `height: auto`.
6.  **Composition (`compose`):** Simplified `compose` to directly yield the `Static` widgets within the `StatsPanel` container. Removed the extra `Vertical`.
7.  **`update_display`:**
    - Improved logic for handling `None` input data by using placeholder text.
    - Refined the formatting of stat strings (e.g., removing decimals for HP/MP, adding `[b]` markup).
    - Added safer extraction using `.get()` with defaults.
    - Improved logging.

---

## `pixabit/tui/widgets/tabs_panel.py`

**Refactored Code:**

```python
# pixabit/tui/widgets/tabs_panel.py

# SECTION: MODULE DOCSTRING
"""
Defines the TabPanel widget which manages the main application content sections
using Textual's TabbedContent.
"""

# SECTION: IMPORTS
from typing import Optional, Type # Use standard Optional/Type

# Use textual's logger
try:
    from textual import log, on
    from textual.app import ComposeResult
    from textual.containers import Container # Base container
    from textual.message import Message # Base Message class
    from textual.widget import Widget
    from textual.widgets import TabbedContent, TabPane, Tabs # Core tab widgets
    # Import the specific content panel widgets this panel will contain
    from .settings_panel import SettingsPanel
    from .tags_panel import TagsPanel
    from .tasks_panel import TaskListWidget
    # from .challenges_panel import ChallengeListWidget # Example for future
    # from .party_panel import PartyPanel # Example for future
    # from .profile_panel import ProfilePanel # Example for future

except ImportError as e:
    # Fallback logger
    import logging
    log = logging.getLogger(__name__) # type: ignore
    log.critical(f"FATAL: Failed to import Textual or widget components in TabPanel: {e}", exc_info=True)
    # Define dummy types if imports fail
    Widget = object; ComposeResult = object; TabbedContent = object; TabPane = object; on = lambda *args: (lambda f: f); Message = object; SettingsPanel=object; TagsPanel=object; TaskListWidget=object # type: ignore


# SECTION: WIDGET CLASS

# KLASS: TabPanel
class TabPanel(Container): # Inherit from Container or Widget
    """A widget containing the main TabbedContent area of the application."""

    DEFAULT_CSS = """
    TabPanel {
        width: 1fr; /* Fill available horizontal space */
        height: 1fr; /* Fill available vertical space */
        overflow: hidden; /* Prevent TabPanel itself from scrolling */
    }
    /* Style the TabbedContent widget itself */
    TabbedContent {
        height: 100%; /* Make TabbedContent fill the TabPanel */
    }
    /* Style the actual content panes */
    TabPane {
        /* Add padding to content panes */
        padding: 1 2;
        height: 100%; /* Ensure panes try to fill height */
        overflow-y: auto; /* Allow individual panes to scroll if needed */
    }
    """

    BINDINGS = [
        # Consider moving tab switching bindings here if App doesn't handle them
        Binding("right", "next_tab", "Next Tab", show=False), # Show=False hides from footer
        Binding("left", "prev_tab", "Prev Tab", show=False),
    ]

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Creates the TabbedContent widget and its initial TabPanes."""
        log.debug("TabPanel: Composing...")
        # Use TabbedContent to manage tabs and content switching
        # Provide an initial tab ID to display first
        with TabbedContent(initial="tab-tasks", id="main-tabbed-content"):
            # Define each tab pane with its content widget
            # Use descriptive IDs for tabs/panes
            with TabPane("Tasks", id="tab-tasks"):
                 # Yield the specific widget instance for this pane
                 # Pass specific filters if needed, e.g., TaskListWidget(task_type='todo')
                yield TaskListWidget(id="tasklist-all") # One list, filters internally
            with TabPane("Tags", id="tab-tags"):
                yield TagsPanel(id="tags-content") # Your Tags display widget
            with TabPane("Settings", id="tab-settings"):
                yield SettingsPanel(id="settings-content") # Your Settings display widget

            # Add placeholders for future tabs
            # with TabPane("Party", id="tab-party"):
            #     yield PlaceholderWidget("Party Panel")
            # with TabPane("Challenges", id="tab-challenges"):
            #     yield PlaceholderWidget("Challenges Panel")

    # FUNC: get_active_content_widget
    def get_active_content_widget(self) -> Widget | None:
        """Returns the main content widget within the currently active TabPane.

        This allows the App to know which widget might need refreshing.
        """
        try:
            # Query the TabbedContent within this TabPanel
            tabbed_content = self.query_one(TabbedContent)
            active_pane = tabbed_content.active_pane
            # The content widget is usually the first child of the TabPane
            if active_pane and active_pane.children:
                return active_pane.children[0]
        except Exception as e:
            log.error(f"TabPanel: Error getting active content widget: {e}")
        return None

    # FUNC: on_tabbed_content_tab_activated (Event Handler)
    @on(TabbedContent.TabActivated)
    async def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Handle tab activation. Potentially trigger data load for the activated pane's content."""
        # event.pane is the TabPane that became active
        # event.tab is the Tab widget that was clicked
        pane = event.pane
        log.info(f"TabPanel: Tab activated: {pane.id if pane else 'None'}")

        if pane and pane.children:
            content_widget = pane.children[0] # Get the main widget in the pane
            # Check if the content widget has a specific method to load its data
            if hasattr(content_widget, "load_or_refresh_data"):
                log.debug(f"TabPanel: Requesting data load for widget: {content_widget.id}")
                # Use run_worker to load data asynchronously
                # Ensure the widget's load method is async or wrapped
                # Use exclusive=True if only one tab should load at a time
                # Pass the widget's method directly to the worker
                self.app.run_worker(
                     content_widget.load_or_refresh_data,
                     name=f"load_{content_widget.id}",
                     group="tab_load",
                     exclusive=True
                )
            else:
                 log.debug(f"TabPanel: Widget {content_widget.id} has no load_or_refresh_data method.")

    # --- Actions for Tab Switching (if bindings are here) ---
    # FUNC: action_next_tab
    def action_next_tab(self) -> None:
         """Switch to the next tab."""
         try:
              tabs = self.query_one(TabbedContent)
              tabs.action_next_tab()
              log.debug("Switched to next tab.")
         except Exception as e:
              log.error(f"Failed to switch to next tab: {e}")

    # FUNC: action_prev_tab
    def action_prev_tab(self) -> None:
         """Switch to the previous tab."""
         try:
              tabs = self.query_one(TabbedContent)
              tabs.action_previous_tab()
              log.debug("Switched to previous tab.")
         except Exception as e:
              log.error(f"Failed to switch to previous tab: {e}")

```

**Suggestions & Comments:**

1.  **Typing:** Standard typing.
2.  **Imports:** Standardized imports. Imports specific content panel widgets (`SettingsPanel`, `TagsPanel`, `TaskListWidget`). Added placeholders for future panels. Added `on` decorator.
3.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:` anchors. Improved docstrings.
4.  **Base Class:** Changed base class to `Container` which is more appropriate for a widget that primarily holds and manages other widgets.
5.  **CSS:** Added `DEFAULT_CSS` for self-containment or reference. Styles the `TabPanel` itself and the `TabbedContent`/`TabPane` widgets within it. Ensures `TabbedContent` fills the panel and panes handle their own scrolling.
6.  **Composition (`compose`):** Creates a `TabbedContent` widget. Each section of the application is placed within its own `TabPane`, yielding the specific content widget instance (e.g., `TaskListWidget()`). Uses descriptive IDs for tabs/panes. Sets an `initial` active tab.
7.  **`get_active_content_widget`:** Helper method for the main `App` to query which content widget is currently visible, allowing the app to trigger refreshes on the correct widget.
8.  **`on_tab_activated`:** Added an event handler that fires when a tab is switched _to_. It finds the main content widget within the activated pane and calls its `load_or_refresh_data` method (if it exists) using `run_worker`. This enables lazy-loading or refreshing data only when a tab becomes visible.
9.  **Tab Switching Actions:** Added `action_next_tab` and `action_prev_tab` with corresponding bindings (set `show=False` to hide them from the footer if desired). These actions allow keyboard navigation between tabs.

---

## `pixabit/tui/widgets/tags_panel.py`

**Refactored Code:**

```python
# pixabit/tui/widgets/tags_panel.py

# SECTION: MODULE DOCSTRING
"""Defines the TagsPanel widget for displaying and managing Habitica tags."""

# SECTION: IMPORTS
from typing import List, Optional, Tuple

# Use textual's logger
try:
    from textual import log, on
    from textual.app import ComposeResult
    from textual.containers import Vertical # For layout
    from textual.message import Message
    from textual.widget import Widget
    from textual.widgets import Button, DataTable, Input, Static # Core widgets
    from textual.widgets._data_table import RowKey # For interaction

    # Import the Tag model (adjust path if needed)
    from ...models.tag import Tag, UserTag, ChallengeTag # Import specific types

except ImportError as e:
    import logging
    log = logging.getLogger(__name__) # type: ignore
    log.critical(f"FATAL: Failed to import Textual/Model components in TagsPanel: {e}", exc_info=True)
    # Define dummy types if imports fail
    Widget=object; ComposeResult=object; Vertical=object; Button=object; DataTable=object; Input=object; Static=object; RowKey=object; on=lambda *args: (lambda f:f); Message=object; Tag=object; UserTag=object; ChallengeTag=object # type: ignore

# SECTION: MESSAGE CLASSES (Specific to this widget's actions)

# KLASS: DeleteTagRequest
class DeleteTagRequest(Message):
     """Request to delete a specific tag."""
     def __init__(self, tag_id: str):
          self.tag_id = tag_id
          super().__init__()

# KLASS: EditTagRequest
class EditTagRequest(Message):
     """Request to edit a specific tag (e.g., open an edit dialog)."""
     def __init__(self, tag_id: str, current_name: str):
          self.tag_id = tag_id
          self.current_name = current_name
          super().__init__()

# KLASS: CreateTagRequest
class CreateTagRequest(Message):
     """Request to create a new tag (e.g., open a create dialog)."""
     pass # No data needed initially, dialog will collect it


# SECTION: WIDGET CLASS

# KLASS: TagsPanel
class TagsPanel(Container): # Inherit from Container for layout
    """A widget panel for displaying and managing Habitica tags."""

    DEFAULT_CSS = """
    TagsPanel {
        padding: 1 2;
        height: 100%;
        width: 100%;
        /* Use vertical layout for controls + table */
        layout: vertical;
        overflow: hidden; /* Prevent panel scroll, table handles it */
    }
    #tags-controls {
        height: auto; /* Size controls automatically */
        margin-bottom: 1;
        border-bottom: thin $accent;
    }
    #tags-controls Button {
        margin-right: 1;
        min-width: 10; /* Ensure buttons have some width */
    }
    #tags-table {
        width: 100%;
        height: 1fr; /* Table fills remaining space */
        border: round $accent-lighten-1;
    }
    /* Style for challenge tags */
    .challenge-tag-row {
        color: $text-muted;
        text-style: italic;
    }
    """

    # Store table internally
    _datatable: DataTable | None = None

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Create the layout for the tags panel."""
        log.debug("TagsPanel: Composing...")
        # Container for action buttons
        with Vertical(id="tags-layout"): # Use Vertical layout
            with Static(id="tags-controls"): # Use Static as simple container for buttons
                 yield Button("New Tag", id="btn-new-tag", variant="success")
                 # Add Edit/Delete later, triggered by selection/keybind
                 # yield Button("Edit Tag", id="btn-edit-tag", variant="primary", disabled=True)
                 # yield Button("Delete Tag", id="btn-delete-tag", variant="error", disabled=True)
            # DataTable to display tags
            self._datatable = DataTable(id="tags-table", cursor_type="row")
            # Define columns
            self._datatable.add_column("Name", key="name", width=30)
            self._datatable.add_column("ID", key="id", width=40)
            self._datatable.add_column("Type", key="type", width=10) # User/Challenge
            self._datatable.add_column("Challenge ID", key="challenge_id", width=40)
            yield self._datatable

    # FUNC: on_mount
    async def on_mount(self) -> None:
         """Load initial tag data when the widget is mounted."""
         log.info("TagsPanel: Mounted.")
         # Trigger initial load
         await self.load_or_refresh_data()

    # FUNC: load_or_refresh_data
    async def load_or_refresh_data(self) -> None:
        """Fetches tags from the DataStore and populates the table."""
        table = self._datatable
        if not table:
            log.error("TagsPanel: DataTable not found during refresh!")
            return

        log.info("TagsPanel: Refreshing tag data...")
        table.loading = True
        table.clear()

        try:
            # Get processed Tag objects from DataStore
            tags_list: list[Tag] = self.app.datastore.get_tags()
            log.info(f"TagsPanel: Received {len(tags_list)} tags from DataStore.")

            # Add rows to table
            for tag in sorted(tags_list, key=lambda t: t.name.lower()): # Sort by name
                row_data: list[Any] = []
                tag_type_str = ""
                challenge_id_str = ""
                row_class = ""

                if isinstance(tag, UserTag):
                     tag_type_str = "User"
                     challenge_id_str = "N/A"
                elif isinstance(tag, ChallengeTag):
                     tag_type_str = "Challenge"
                     challenge_id_str = tag.challenge_id
                     row_class = "challenge-tag-row" # Apply CSS class
                else: # BaseTag or unknown
                    tag_type_str = "Unknown"
                    challenge_id_str = getattr(tag, 'challenge_id', 'N/A') or "N/A"

                # Ensure order matches add_column calls
                row_data = [
                    tag.name,
                    tag.id,
                    tag_type_str,
                    challenge_id_str,
                ]
                table.add_row(*row_data, key=tag.id) # Use tag ID as row key

                # Apply CSS class if needed (Textual doesn't directly support row classes yet easily)
                # For now, styling is based on cell content or manual styling per cell if needed.
                # if row_class:
                #    pass # Row class application is tricky, maybe style the first cell?

            log.info(f"TagsPanel: Table updated with {table.row_count} tags.")

        except Exception as e:
            log.error(f"TagsPanel: Error loading/displaying tags: {e}", exc_info=True)
            # Optionally display an error message in the table or panel
            # table.add_row("Error loading tags.")

        finally:
            table.loading = False

    # --- Event Handlers ---

    # FUNC: on_button_pressed (Handle New Tag button)
    @on(Button.Pressed, "#btn-new-tag")
    def handle_new_tag_button(self, event: Button.Pressed) -> None:
        """Handle the 'New Tag' button press."""
        log.info("TagsPanel: 'New Tag' button pressed.")
        # Post a message to the App to handle tag creation (e.g., open a dialog)
        self.post_message(CreateTagRequest())

    # FUNC: on_data_table_row_selected (Handle row selection for potential edit/delete)
    @on(DataTable.RowSelected)
    def handle_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle selection of a tag row."""
        table = self._datatable
        if not table or event.row_key is None: return

        tag_id = str(event.row_key.value)
        log.info(f"TagsPanel: Row selected for tag ID: {tag_id}")

        # TODO: Enable Edit/Delete buttons or show context menu
        # Example: Enable buttons (assuming they exist and have IDs)
        # try:
        #    self.query_one("#btn-edit-tag", Button).disabled = False
        #    self.query_one("#btn-delete-tag", Button).disabled = False
        # except Exception: pass

        # For now, maybe post an Edit request on selection? Or require another action.
        # Example: Post Edit request immediately on selection
        try:
            # Get the tag name from the selected row data for the edit request
            row_data = table.get_row(event.row_key)
            tag_name = str(row_data[0]) # Assuming name is the first column
            self.post_message(EditTagRequest(tag_id=tag_id, current_name=tag_name))
        except Exception as e:
            log.error(f"TagsPanel: Error getting tag name for edit request: {e}")


    # FUNC: on_key (Handle keys like Delete for selected row)
    def on_key(self, event: events.Key) -> None:
        """Handle key presses, e.g., Delete key for selected tag."""
        table = self._datatable
        if not table or not table.row_count or table.cursor_coordinate.row < 0:
            return # No table or no row selected

        if event.key == "delete":
            try:
                # --- Get Key for Selected Row ---
                row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
                if row_key is not None:
                    tag_id = str(row_key.value)
                    log.info(f"TagsPanel: Delete key pressed for tag ID: {tag_id}")
                    # Post a message to the App to confirm and handle deletion
                    self.post_message(DeleteTagRequest(tag_id=tag_id))
                    event.stop() # Prevent further key handling
            except Exception as e:
                 log.error(f"TagsPanel: Error handling delete key: {e}")

```

**Suggestions & Comments:**

1.  **Typing:** Standard typing (`|`, `list`, `dict`).
2.  **Imports:** Standardized imports. Uses `textual.log`. Imports `Tag`, `UserTag`, `ChallengeTag` models. Added necessary Textual widgets (`Button`, `DataTable`, etc.) and `RowKey`.
3.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:` anchors and improved docstrings.
4.  **Base Class:** Changed base class to `Container` to better manage layout of controls and the table.
5.  **Custom Messages:** Defined specific message classes (`DeleteTagRequest`, `EditTagRequest`, `CreateTagRequest`) for actions originating from this panel. This follows the Textual pattern of widgets posting messages for the App (or parent) to handle.
6.  **CSS:** Added `DEFAULT_CSS` with basic layout (Vertical), controls section, and table styling. Added a sample class `.challenge-tag-row` for styling challenge tags differently (though applying row classes isn't straightforward in current Textual DataTable, styling might need to be per-cell).
7.  **Composition (`compose`):** Creates a `Vertical` layout holding a controls area (`Static` container) and the `DataTable`. Added a "New Tag" button. Placeholder comments for Edit/Delete buttons (these would likely be enabled upon row selection). Defines columns for the `DataTable`.
8.  **Data Loading (`load_or_refresh_data`):** Fetches the list of `Tag` objects from `app.datastore.get_tags()`. Iterates through the tags, determines the type (`UserTag`/`ChallengeTag`), formats the row data, and adds it to the table using the tag's `id` as the `RowKey`. Includes basic sorting by name.
9.  **Event Handling:**
    - `on_button_pressed`: Handles the "New Tag" button, posting a `CreateTagRequest`.
    - `on_data_table_row_selected`: Handles row selection. Logs the selected ID. TODO added for enabling edit/delete actions. Currently posts an `EditTagRequest` immediately on selection as an example (might want a dedicated Edit button or keybind).
    - `on_key`: Added handler for the "delete" key. If a row is selected, it gets the `tag_id` from the `RowKey` and posts a `DeleteTagRequest`.

---

## `pixabit/tui/widgets/tasks_panel copy.py`

**Analysis:**

- This file appears to be an almost identical copy or a slightly earlier version of `pixabit/tui/widgets/tasks_panel.py`.
- Maintaining duplicate widget files leads to confusion and maintenance issues.

**Recommendation:**

- **Delete this file (`pixabit/tui/widgets/tasks_panel copy.py`)**. Focus on maintaining and improving the main `pixabit/tui/widgets/tasks_panel.py`.

---

## `pixabit/tui/widgets/tasks_panel.py`

**Refactored Code:**

```python
# pixabit/tui/widgets/tasks_panel.py

# SECTION: MODULE DOCSTRING
"""Defines the TaskListWidget for displaying and interacting with Habitica tasks."""

# SECTION: IMPORTS
import asyncio
import datetime # Keep for date formatting
from datetime import timezone
from operator import attrgetter, itemgetter # For sorting
from typing import Any, Callable, Dict, List, Optional, Tuple, cast # Use standard types

# Use textual's logger
try:
    from textual import events, log, on, work
    from textual.app import ComposeResult
    from textual.containers import Vertical
    from textual.coordinate import Coordinate
    from textual.message import Message
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import DataTable, Input, Select
    from textual.widgets._data_table import CellKey, ColumnKey, RowKey
    # Import Rich Text for styling cells
    from rich.text import Text
    from rich.emoji import Emoji

    # Local Imports (Adjust path if necessary)
    from ...models.task import Daily, Task, TaskList, Todo, Habit, Reward # Import models
    from ..messages import UIMessageRequest # For posting errors/info

except ImportError as e:
    # Fallback logger and dummy types
    import logging
    log = logging.getLogger(__name__) # type: ignore
    log.critical(f"FATAL: Failed to import Textual/Model components in TaskListWidget: {e}", exc_info=True)
    # Define dummy types if imports fail
    Widget=object; ComposeResult=object; Vertical=object; Input=object; Select=object; DataTable=object; Message=object; on=lambda *args: (lambda f:f); work=lambda *args, **kwargs: (lambda f:f); events=object; Text=str; Emoji=lambda s:s; reactive=lambda x, **kwargs: x; Coordinate=object; CellKey=object; RowKey=object; ColumnKey=object; Task=object; Daily=object; Todo=object; Habit=object; Reward=object; TaskList=list; UIMessageRequest=object # type: ignore

# SECTION: MESSAGE CLASSES (Outgoing requests from this widget)

# KLASS: ScoreTaskRequest
class ScoreTaskRequest(Message):
    """Message requesting the App/DataStore to score a task."""
    def __init__(self, task_id: str, direction: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.direction = direction

# KLASS: ViewTaskDetailsRequest
class ViewTaskDetailsRequest(Message):
    """Message requesting the App to show details for a task."""
    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


# SECTION: WIDGET CLASS

# KLASS: TaskListWidget
class TaskListWidget(Widget):
    """A widget to display Habitica tasks in a DataTable with filtering and sorting."""

    DEFAULT_CSS = """
    TaskListWidget {
        height: 100%; width: 100%;
        display: block; /* Ensure it takes block space */
    }
    TaskListWidget > Vertical { /* Target the direct Vertical child */
        height: 100%; width: 100%;
    }
    /* Controls styling */
    .task-list-controls {
        height: auto;
        margin-bottom: 1;
        /* Use horizontal layout for controls */
        layout: horizontal;
        grid-size: 2; /* Example: 2 columns */
        grid-gutter: 1 2;
    }
    .task-list-controls > Select { width: 1fr; }
    .task-list-controls > Input { width: 1fr; }

    /* Table styling */
    DataTable {
        height: 1fr; /* Fill remaining space */
        width: 100%;
        border: round $accent;
    }
    /* Status Cell Styling */
    .status-due { color: $warning; }
    .status-red { color: $error; }
    .status-done { color: $success; }
    .status-success { color: $success; }
    .status-grey { color: $text-muted; }
    .status-habit { color: $secondary; }
    .status-reward{ color: $warning-darken-1; } /* Slightly different warning */
    .status-unknown { color: $text-disabled; }
    /* Damage Indicator */
    .damage-indicator {
        color: $error;
        text-style: bold;
        margin-left: 1;
    }
    """

    # --- Reactive State ---
    _text_filter = reactive("", layout=True)
    _active_task_type = reactive("all") # Default to 'all'
    _sort_column_key: ColumnKey | None = reactive(None) # Use reactive for sorting key
    _sort_reverse: reactive[bool] = reactive(False)

    # --- Internal ---
    _datatable: DataTable | None = None
    # Store raw Task objects fetched from DataStore
    _tasks: list[Task] = []
    # Map status strings to simple icons
    _STATUS_ICONS = {
        "due": "⏳", "red": Emoji("warning"), "done": Emoji("white_check_mark"),
        "success": Emoji("white_check_mark"), "grey": "➖", "habit": "🔄",
        "reward": Emoji("star"), "unknown": "?"
    }

    # FUNC: __init__
    def __init__(self, id: str | None = None, **kwargs: Any):
        """Initialize the TaskListWidget."""
        # Determine ID based on initial filter or default
        widget_id = id or f"task-list-all" # Default ID if none provided
        super().__init__(id=widget_id, **kwargs)
        # _active_task_type defaults to "all" via reactive definition

    # FUNC: compose
    def compose(self) -> ComposeResult:
        """Create child widgets: Controls (Select, Input) and DataTable."""
        with Vertical():
            with Container(classes="task-list-controls"): # Container for controls
                yield Select(
                    options=[
                        ("All", "all"), ("Todos", "todo"), ("Dailies", "daily"),
                        ("Habits", "habit"), ("Rewards", "reward"),
                    ],
                    value=self._active_task_type,
                    id="task-type-select",
                    allow_blank=False,
                )
                yield Input(
                    placeholder="Filter by text...", id="task-filter-input"
                )
            # Create and store DataTable instance
            self._datatable = DataTable(id=f"tasks-data-table-{self.id}", cursor_type="row")
            self._setup_columns() # Define columns before mount
            yield self._datatable

    # FUNC: _setup_columns
    def _setup_columns(self) -> None:
        """Defines the columns for the DataTable."""
        table = self._datatable
        if not table: return

        # Define columns with keys for sorting/identification
        # Key 'status' for visual indicator, maybe not sortable by default
        table.add_column(Text("S", justify="center"), key="status", width=3)
        table.add_column("Task Text", key="text", width=40) # Sortable
        table.add_column(Text("Dmg", justify="center"), key="damage", width=5) # Damage indicator
        table.add_column(Text("Val", justify="right"), key="value", width=7) # Sortable
        table.add_column(Text("Pri", justify="center"), key="priority", width=5) # Sortable
        table.add_column("Due", key="due", width=12) # Sortable by date
        table.add_column("Tags", key="tags") # Not typically sorted

    # FUNC: on_mount
    @work(exclusive=True, group="load_tasks", thread=True) # Run initial load in worker thread
    async def on_mount(self) -> None:
        """Called after the widget is mounted. Perform initial data load."""
        log.info(f"TaskListWidget ({self.id}): Mounted.")
        # DataTable columns are set up in compose
        await self.load_or_refresh_data()

    # --- Watchers for Reactive State Changes ---

    # FUNC: watch__active_task_type
    def watch__active_task_type(self, old_type: str, new_type: str) -> None:
        """Trigger data refresh when the selected task type changes."""
        if old_type != new_type:
             log.info(f"TaskListWidget ({self.id}): Task type changed to '{new_type}'. Refreshing.")
             # Update the Select widget's value visually
             try:
                  select = self.query_one("#task-type-select", Select)
                  if select.value != new_type: select.value = new_type
             except Exception: pass # Ignore if widget not ready
             # Run refresh in worker thread
             self.run_worker(self.load_or_refresh_data, exclusive=True, thread=True)

    # FUNC: watch__text_filter
    @work(exclusive=True, group="load_tasks", thread=True) # Debounce using worker name/group?
    async def watch__text_filter(self, new_filter: str) -> None:
        """Trigger data refresh when the text filter changes (debounced via worker)."""
        log.info(f"TaskListWidget ({self.id}): Text filter changed to '{new_filter}'. Refreshing.")
        # Worker automatically calls the refresh method
        await self.load_or_refresh_data()

    # FUNC: watch__sort_column_key
    # FUNC: watch__sort_reverse
    def watch__sort_column_key(self, old_key: ColumnKey | None, new_key: ColumnKey | None) -> None:
        """Resort and redisplay tasks when sort key changes."""
        if old_key != new_key: self.sort_and_display_tasks()
    def watch__sort_reverse(self, old_val: bool, new_val: bool) -> None:
        """Resort and redisplay tasks when sort direction changes."""
        if old_val != new_val: self.sort_and_display_tasks()


    # --- Data Loading and Display Logic ---

    # FUNC: load_or_refresh_data
    async def load_or_refresh_data(self) -> None:
        """Worker task: Fetches tasks from DataStore, filters locally, updates table."""
        table = self._datatable
        if not table:
            log.error(f"TaskListWidget ({self.id}): DataTable is None in load/refresh!")
            return

        log.info(f"TaskListWidget ({self.id}): Refreshing data...")

        # Preserve cursor position if possible
        current_row_key: RowKey | None = None
        try:
            if table.row_count > 0 and table.cursor_row >= 0:
                 current_row_key = table.get_row_key(table.cursor_row)
                 log.debug(f"TaskListWidget ({self.id}): Preserving cursor key: {current_row_key}")
        except Exception as e:
            log.warning(f"TaskListWidget ({self.id}): Could not get current row key: {e}")

        table.loading = True
        table.clear() # Clear previous rows
        self._tasks = [] # Clear internal list

        # Fetch ALL tasks from DataStore (filtering done locally now)
        try:
             # Assuming DataStore.get_tasks() returns the full TaskList object
             full_task_list_obj: TaskList = self.app.datastore.get_tasks() # Get base TaskList
             self._tasks = list(full_task_list_obj) # Convert to list for sorting/filtering
             log.info(f"TaskListWidget ({self.id}): Received {len(self._tasks)} total tasks.")
        except Exception as e:
            log.error(f"TaskListWidget ({self.id}): Error getting tasks from datastore: {e}", exc_info=True)
            self._tasks = []
            # Post an error message to the UI?
            self.app.post_message(UIMessageRequest("Error loading tasks.", severity="error"))

        # Filter and display the fetched tasks
        self.filter_sort_and_display_tasks()

        table.loading = False

        # Restore cursor position
        if current_row_key:
            try:
                new_row_index = table.get_row_index(current_row_key)
                table.move_cursor(row=new_row_index, animate=False)
                log.debug(f"TaskListWidget ({self.id}): Restored cursor to key {current_row_key}")
            except KeyError:
                log.warning(f"TaskListWidget ({self.id}): Row key {current_row_key} not found after refresh.")
                if table.row_count > 0: table.move_cursor(row=0, animate=False)
            except Exception as e:
                log.error(f"TaskListWidget ({self.id}): Error restoring cursor: {e}")
                if table.row_count > 0: table.move_cursor(row=0, animate=False)
        elif table.row_count > 0:
            table.move_cursor(row=0, animate=False) # Move to top if no previous cursor

    # FUNC: filter_sort_and_display_tasks
    def filter_sort_and_display_tasks(self):
         """Applies current filters and sorting, then updates the DataTable rows."""
         table = self._datatable
         if not table: return

         table.clear()

         # 1. Apply Type Filter
         filtered_tasks = self._tasks
         active_type = self._active_task_type
         if active_type != "all":
              filtered_tasks = [t for t in filtered_tasks if t.type == active_type]

         # 2. Apply Text Filter (case-insensitive)
         text_filter = self._text_filter.lower()
         if text_filter:
              filtered_tasks = [t for t in filtered_tasks if text_filter in t.text.lower()]

         # 3. Apply Sorting
         sort_key = self._sort_column_key.value if self._sort_column_key else "text" # Default sort key
         reverse_sort = self._sort_reverse

         try:
              # Define sorting key function dynamically
              def get_sort_value(task: Task) -> Any:
                   if sort_key == "status": return getattr(task, "_status", "")
                   if sort_key == "text": return getattr(task, "text", "").lower()
                   # Handle numeric keys safely, providing defaults
                   if sort_key == "value": return getattr(task, "value", 0.0)
                   if sort_key == "priority": return getattr(task, "priority", 1.0)
                   if sort_key == "damage": return getattr(task, "damage_user", 0.0) or 0.0 # Sort by user damage
                   if sort_key == "due":
                       if isinstance(task, Todo): return task.due_date or datetime.max.replace(tzinfo=timezone.utc)
                       if isinstance(task, Daily): return task.next_due[0] if task.next_due else datetime.max.replace(tzinfo=timezone.utc)
                       return datetime.max.replace(tzinfo=timezone.utc) # Non-due tasks last
                   return None # Fallback for unknown keys

              filtered_tasks.sort(key=get_sort_value, reverse=reverse_sort)
              log.debug(f"Sorted {len(filtered_tasks)} tasks by '{sort_key}', reverse={reverse_sort}")

         except Exception as e:
              log.error(f"Error during task sorting by '{sort_key}': {e}", exc_info=True)
              # Proceed with unsorted filtered list if sorting fails


         # 4. Add Rows to Table
         for task in filtered_tasks:
              try:
                   # --- Extract and Format Row Data ---
                   status = getattr(task, "_status", "unknown")
                   task_text = Text.from_markup(task.text) # Use plain text for now

                   # Damage Indicator Cell
                   dmg_val = getattr(task, "damage_user", None)
                   dmg_cell = Text(f"{dmg_val:.1f}", style="error bold") if dmg_val and dmg_val > 0 else Text("-", style="dim")

                   value = getattr(task, "value", 0.0)
                   priority = getattr(task, "priority", 1.0)
                   tag_names = getattr(task, "tag_names", [])
                   tag_str = ", ".join(tag_names) if tag_names else "-" # Use "-" if no tags

                   due_str = ""
                   if isinstance(task, Todo) and task.due_date:
                       due_str = task.due_date.strftime("%Y-%m-%d")
                   elif isinstance(task, Daily) and task.next_due:
                       due_str = task.next_due[0].strftime("%Y-%m-%d") # Show first due date

                   status_icon = self._STATUS_ICONS.get(status, "?")
                   status_color = self.get_status_style(status)
                   status_cell = Text(status_icon, style=f"bold {status_color}")

                   # --- Add Row ---
                   # Ensure order matches column setup
                   table.add_row(
                       status_cell,
                       task_text,
                       dmg_cell,
                       Text(f"{value:.1f}", style=self.get_value_style(value), justify="right"),
                       Text(f"{priority:.1f}", justify="center"),
                       due_str,
                       Text(tag_str, overflow="ellipsis"), # Ellipsis for long tag lists
                       key=task.id, # Use task ID as the key
                   )
              except Exception as e:
                   log.error(f"Error processing task {getattr(task, 'id', 'N/A')} for display: {e}")

         log.info(f"TaskListWidget ({self.id}): Display updated with {table.row_count} rows.")


    # --- Style Helpers ---
    def get_status_style(self, status: str) -> str:
        """Maps status string to CSS color variable name."""
        return {
            "due": "warning", "red": "error", "done": "success", "success": "success",
            "grey": "text-muted", "habit": "secondary", "reward": "warning-darken-1",
            "unknown": "text-disabled",
        }.get(status, "text-muted")

    def get_value_style(self, value: float) -> str:
         """Maps task value to a Rich style name (matches _value_color logic)."""
         if value > 10: return "success-dark"
         elif value > 1: return "success"
         elif value >= -1: return "text"
         elif value > -10: return "warning"
         else: return "error"

    # --- Event Handlers ---

    @on(Select.Changed, "#task-type-select")
    def handle_type_change(self, event: Select.Changed) -> None:
        """Handle task type selection change by updating reactive var."""
        self._active_task_type = str(event.value) # Watcher will trigger refresh

    @on(Input.Changed, "#task-filter-input")
    def handle_filter_change(self, event: Input.Changed) -> None:
        """Handle text filter input change by updating reactive var."""
        self._text_filter = event.value # Watcher will trigger refresh

    @on(DataTable.HeaderSelected)
    def on_header_selected(self, event: DataTable.HeaderSelected):
        """Handle clicking on a table header to sort."""
        table = self._datatable
        if not table: return

        column_key = event.column_key
        log.info(f"Header selected: {column_key.value}")

        # Check if the column is actually sortable based on our logic
        # (e.g., don't sort by status icon or tags column)
        sortable_keys = {"text", "value", "priority", "due", "damage"}
        if column_key.value not in sortable_keys:
             log.debug(f"Column '{column_key.value}' is not configured for sorting.")
             return

        if column_key == self._sort_column_key:
             # Toggle direction if same column clicked again
             self._sort_reverse = not self._sort_reverse
        else:
             # Set new sort column and default to ascending
             self._sort_column_key = column_key
             self._sort_reverse = False

        # Watchers for _sort_column_key and _sort_reverse handle the actual resort/redisplay

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle selection of a task row to view details."""
        if event.row_key is not None:
            task_id = str(event.row_key.value)
            log.info(f"TaskListWidget ({self.id}): Row selected for task ID: {task_id}")
            self.post_message(ViewTaskDetailsRequest(task_id))

    def on_key(self, event: events.Key) -> None:
        """Handle key presses for scoring tasks (+/-)."""
        table = self._datatable
        if not table or table.cursor_row < 0: return # No selection

        # Allow scoring only for certain types?
        can_score = self._active_task_type in ("all", "habit", "daily", "todo")

        if can_score and event.key in ("+", "-"):
            try:
                row_key = table.get_row_key(table.cursor_row)
                task_id = str(row_key.value)
                direction = "up" if event.key == "+" else "down"
                log.info(f"TaskListWidget ({self.id}): Posting score request for {task_id} ({direction})")
                self.post_message(ScoreTaskRequest(task_id, direction))
                event.stop()
            except KeyError:
                 log.warning(f"Could not find row key for cursor row {table.cursor_row}")
            except Exception as e:
                log.error(f"TaskListWidget ({self.id}): Error handling score key: {e}")

```

**Suggestions & Comments:**

1.  **Typing & Imports:** Standardized. Imported necessary models and Textual components. Uses Rich `Text` for potentially styled cells. Imports `UIMessageRequest`.
2.  **Comments:** Added `# SECTION:`, `# KLASS:`, `# FUNC:`, etc. anchors. Improved docstrings.
3.  **CSS:** Updated `DEFAULT_CSS`. Added a container class `.task-list-controls` for layout flexibility. Defined styles for status indicators. Added a style for damage indicator.
4.  **Reactive State:** Uses reactive variables for `_text_filter`, `_active_task_type`, `_sort_column_key`, and `_sort_reverse`. Watchers now handle triggering refreshes or resorting.
5.  **Composition (`compose`):** Creates a `Vertical` layout containing a controls `Container` (with `Select` and `Input`) and the `DataTable`. Calls `_setup_columns` to define table columns.
6.  **Column Setup (`_setup_columns`):** Centralized column definition. Added a 'Dmg' column. Uses Rich `Text` for headers allowing justification. Specifies `key` for each column.
7.  **Data Handling:**
    - `load_or_refresh_data`: Now fetches the _full_ `TaskList` from `DataStore`. Local filtering and sorting happen _after_ fetching in `filter_sort_and_display_tasks`. Added error handling for DataStore access. Implemented cursor preservation using `RowKey`. Runs initial load in a worker thread (`@work`).
    - `filter_sort_and_display_tasks`: New method responsible for applying local filters (type, text), sorting based on reactive state, and populating the `DataTable`. This separates fetching from display logic.
    - Sorting logic now uses a dynamic `get_sort_value` function based on `_sort_column_key`. Handles sorting by status, text, numeric values, and dates. Includes fallback for `None` dates.
    - Row creation formats data appropriately for display, including status icons, damage indicator, numeric formatting, and tag string. Uses Rich `Text` for potentially styled cells (status, value, damage, tags). Uses task `id` as the `RowKey`.
8.  **Watchers:** Watchers for reactive state variables now trigger `load_or_refresh_data` (via worker) or `sort_and_display_tasks` directly, simplifying the logic within the watchers themselves.
9.  **Event Handlers:**
    - `handle_type_change`, `handle_filter_change`: Update reactive variables.
    - `on_header_selected`: Updates reactive sort state (`_sort_column_key`, `_sort_reverse`). Watchers handle the table update. Added check for sortable columns.
    - `on_row_selected`: Posts `ViewTaskDetailsRequest`.
    - `on_key`: Handles `+`/`-` keys for scoring, posting `ScoreTaskRequest`. Added check if scoring is applicable to the current task type view.
10. **Style Helpers:** Added `get_status_style` and `get_value_style` for consistent cell styling.

---

## `pixabit/tui/widgets/task_panel.py`

**Analysis:**

- The content of this file is **identical** to the refactored `pixabit/tui/widgets/tasks_panel.py`.
- It appears to be a duplicate.

**Recommendation:**

- **Delete this file (`pixabit/tui/widgets/task_panel.py`)**. Use `tasks_panel.py`.

---

## `pixabit/tui/widgets/task_panelw_.py`

**Analysis:**

- The content of this file is also **identical** to the refactored `pixabit/tui/widgets/tasks_panel.py`.
- It appears to be another duplicate or backup.

**Recommendation:**

- **Delete this file (`pixabit/tui/widgets/task_panelw_.py`)**. Use `tasks_panel.py`.

---

## `pixabit/tui/__init__.py`

**Refactored Code:**

```python
# pixabit/tui/__init__.py

"""Pixabit Textual User Interface Package.

This package contains the main TUI application (app.py), data handling logic
(data_store.py, data_processor.py, game_content.py), custom messages
(messages.py), and UI widgets (widgets/).
"""

# Optionally expose the main App class for easier execution/import
try:
    from .app import PixabitTUIApp
    __all__ = ["PixabitTUIApp"]
except ImportError:
     # Handle cases where app might not be importable directly (e.g., during setup)
     __all__ = []

```

**Suggestions & Comments:**

1.  **Exports:** Added an optional export of the main `PixabitTUIApp` class via `__all__`. This allows running the app potentially via `python -m pixabit.tui` if a corresponding `__main__.py` is added or simply makes importing `PixabitTUIApp` slightly cleaner. Added basic error handling for the import.

---

## `pixabit/ui/app.py` & `pixabit/ui/__init__.py`

**Analysis:**

- These files are currently empty. They suggest a potential alternative UI layer (perhaps graphical like Qt/Kivy, or web-based) that hasn't been developed.

**Recommendation:**

- If you don't plan on building a non-TUI interface soon, you can **delete the `pixabit/ui/` directory** to keep the project focused.
- If you might add another UI later, keep them as empty placeholders.

---

## `pixabit/__init__.py`

**Analysis:**

- This file is empty.

**Recommendation:**

- Keep this file **empty**. It marks the `pixabit` directory as the main package root. You could optionally add top-level imports here if desired (e.g., `from .tui import PixabitTUIApp`), but it's often kept minimal.

---

## `pixabit/__main__.py`

**Refactored Code:**

```python
# pixabit/__main__.py

# SECTION: MODULE DOCSTRING
"""
Main entry point for running the Pixabit TUI application.

Allows execution using `python -m pixabit`.
"""

# SECTION: IMPORTS
import logging
import sys

# Import the main App class
try:
    # Assume helpers setup logging, but set a basic config here just in case.
    # The App's init or helper import should configure Rich logging properly.
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    log = logging.getLogger(__name__) # Standard logger for this file

    from pixabit.tui.app import PixabitTUIApp

except ImportError as e:
    # Use print as logging might not be fully set up
    print(f"FATAL ERROR: Could not import PixabitTUIApp in __main__.py: {e}", file=sys.stderr)
    print("Ensure pixabit is installed correctly or PYTHONPATH is set.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"FATAL ERROR: An unexpected error occurred during import in __main__.py: {e}", file=sys.stderr)
    sys.exit(1)


# SECTION: MAIN EXECUTION

# FUNC: run_app
def run_app():
    """Initializes and runs the Pixabit TUI application."""
    log.info("Launching Pixabit TUI Application...")
    try:
        app = PixabitTUIApp()
        app.run()
        log.info("Pixabit TUI Application finished.")
    except Exception as e:
         # Catch potential errors during app run
         log.critical(f"Critical error during application execution: {e}", exc_info=True)
         print(f"\n[bold red]Application Error:[/]\n{e}", file=sys.stderr) # Also print basic error
         sys.exit(1)


if __name__ == "__main__":
    run_app()
```

**Suggestions & Comments:**

1.  **Purpose:** Added docstring clarifying the purpose for `python -m pixabit` execution.
2.  **Imports:** Imports the main `PixabitTUIApp`. Added robust error handling around the import. Uses standard logging initially, assuming the main app/helpers will configure Rich logging upon import.
3.  **Execution:** Wrapped the app instantiation and `run()` call in a `run_app` function with a `try...except` block to catch potential runtime errors during app execution and log/print them before exiting.
4.  **Logging:** Uses a standard logger for messages within `__main__.py` itself. The main application logging is handled by the imported helpers/app.

---

This completes the refactoring based on the provided files and requirements. Remember to address the TODOs, integrate the `TagManager` logic, potentially remove duplicate files, and test thoroughly!
