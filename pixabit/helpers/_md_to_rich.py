# pixabit/helpers/_md_to_rich.py

# SECTION: MODULE DOCSTRING
"""Provides utilities for converting Markdown to Rich Text objects.

Uses markdown-it-py for parsing and Rich for constructing styled text.
Includes default styling and allows for custom style overrides.
Optionally integrates with Textual via a MarkdownStatic widget.

NOTE: This renderer provides fine-grained control but might be complex.
      Consider using Rich's built-in `Markdown` class if simpler rendering suffices.
"""

# SECTION: IMPORTS
import re
from typing import Any, Dict, List, Optional, Sequence, TypeVar, Union, cast

# Markdown parsing
try:
    import markdown_it
    from markdown_it.token import Token

    MARKDOWN_IT_AVAILABLE = True
except ImportError:
    MARKDOWN_IT_AVAILABLE = False
    Token = TypeVar("Token")  # Dummy type if not available

# Rich rendering
from rich.console import Console, ConsoleOptions, RenderResult
from rich.panel import Panel
from rich.style import Style, StyleType
from rich.text import Text, TextType

# Textual integration (optional import)
try:
    from textual.reactive import reactive  # Import reactive specifically
    from textual.widget import Widget
    from textual.widgets import Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    Widget = object  # Dummy base class
    Static = object  # Dummy base class

# Use themed console if available from ._rich
try:
    from ._rich import console
except ImportError:
    # Basic console fallback
    class PrintConsole:
        def print(self, *args, **kwargs):
            print(*args)

    console = PrintConsole()  # type: ignore


# SECTION: UTILITY FUNCTIONS


# FUNC: escape_rich
def escape_rich(text: str) -> str:
    """Escape Rich markup control characters (square brackets) in text.

    Args:
        text: The text to escape.

    Returns:
        String with Rich control characters escaped. Returns empty string if input is None or empty.
    """
    if not text:
        return ""
    # Escape square brackets which Rich uses for markup
    return text.replace("[", r"\[").replace("]", r"\]")


# SECTION: MARKDOWN RENDERER CLASS


# KLASS: MarkdownRenderer
class MarkdownRenderer:
    """Converts Markdown to Rich Text with custom styling using markdown-it-py.

    Attributes:
        DEFAULT_STYLES: Class variable holding default styles for elements.
        md_parser: The markdown-it parser instance.
        styles: The effective styles (defaults merged with custom).
    """

    # Default styles for different Markdown elements
    DEFAULT_STYLES: dict[str, Style] = {
        "h1": Style(bold=True, color="cyan", underline=True),
        "h2": Style(bold=True, color="bright_cyan"),
        "h3": Style(bold=True, color="blue"),
        "h4": Style(underline=True, color="bright_blue"),
        "h5": Style(italic=True, color="blue"),
        "h6": Style(italic=True, dim=True),
        "strong": Style(bold=True),
        "em": Style(italic=True),
        "code_inline": Style(
            bgcolor="#303030", color="#00ff00"
        ),  # Dark bg, green text
        "code_block": Style(dim=True),  # Dim background for blocks
        "strike": Style(strike=True),
        "link": Style(underline=True, color="bright_blue"),
        "list_item": Style(),  # Base style for list items (prefix added separately)
        "blockquote": Style(italic=True, color="green"),
        "hr": Style(color="bright_black", dim=True),
        "table": Style(),  # Placeholder for potential table styling
        "checkbox_unchecked": Style(),
        "checkbox_checked": Style(dim=True),  # Dim completed checklist items
    }

    # FUNC: __init__
    def __init__(self, custom_styles: dict[str, Style] | None = None):
        """Initialize the Markdown renderer.

        Args:
            custom_styles: Dictionary mapping element names (e.g., 'h1', 'link')
                           to Rich Style objects. These override defaults.
        """
        if not MARKDOWN_IT_AVAILABLE:
            raise ImportError(
                "MarkdownRenderer requires 'markdown-it-py' to be installed."
            )

        # Create markdown-it parser with extensions
        # Enable strikethrough ('strikethrough') and tables ('table')
        self.md_parser = (
            markdown_it.MarkdownIt(
                "commonmark", {"breaks": True, "html": False}
            ).enable(  # Disable raw HTML
                "strikethrough"
            )
            # .enable("table") # Uncomment if table rendering is needed
        )

        # Merge default styles with any custom styles
        self.styles = self.DEFAULT_STYLES.copy()
        if custom_styles:
            self.styles.update(custom_styles)

    # --- Style Application Helpers ---

    # FUNC: _apply_style
    def _apply_style(self, current_style: Style, style_key: str) -> Style:
        """Applies a named style on top of the current style."""
        style_to_add = self.styles.get(style_key)
        if style_to_add:
            # Combine styles: attributes from style_to_add override current_style
            return current_style + style_to_add
        return current_style

    # FUNC: _remove_style
    def _remove_style(self, current_style: Style, style_key: str) -> Style:
        """Removes attributes defined in a named style from the current style.

        This is tricky. We approximate by creating a style with only the
        attributes from the target style set to None or default.
        A more robust way might involve tracking active style keys.
        For now, we'll just reset to parent style conceptually.
        """
        # This simple approach doesn't truly "remove" overlapping styles.
        # It relies on the parent context having the correct base style.
        # For common cases like bold/italic, it works if nesting is handled.
        return current_style  # Placeholder - relies on context stack in _process_tokens

    # --- Core Conversion Method ---

    # FUNC: markdown_to_rich_text
    def markdown_to_rich_text(self, markdown_str: str) -> Text:
        """Convert Markdown string to a Rich Text object using markdown-it tokens.

        Args:
            markdown_str: Markdown-formatted string.

        Returns:
            Rich Text object with appropriate styling.
        """
        if not markdown_str:
            return Text()

        # Parse the markdown
        tokens = self.md_parser.parse(markdown_str)

        # Create a Text object for the result
        result = Text()
        # Process the tokens recursively, starting with an empty style stack
        self._process_tokens(tokens, result, style_stack=[Style()])

        return result

    # --- Token Processing Logic ---

    # FUNC: _process_tokens
    def _process_tokens(
        self,
        tokens: Sequence[Token],
        text_obj: Text,
        style_stack: list[Style],  # Stack to manage nested styles
    ) -> None:
        """Process markdown-it tokens recursively and apply styles.

        Args:
            tokens: List of markdown-it tokens to process.
            text_obj: Rich Text object to append styled content to.
            style_stack: A list representing the stack of active styles.
                         The effective style is the top of the stack.
        """
        i = 0
        while i < len(tokens):
            token = tokens[i]
            current_style = style_stack[-1]  # Get the currently active style

            # Handle inline tokens with children recursively
            if token.type == "inline" and token.children:
                self._process_tokens(token.children, text_obj, style_stack)
                i += 1
                continue

            # --- Block Element Open/Close ---
            elif token.type.endswith("_open"):
                new_style = current_style  # Default to inheriting style
                style_key = ""
                prefix = ""
                needs_newline = False

                if token.type == "heading_open":
                    level = int(token.tag[1])
                    style_key = f"h{level}"
                    needs_newline = True  # Add newline before heading starts
                elif token.type == "strong_open":
                    style_key = "strong"
                elif token.type == "em_open":
                    style_key = "em"
                elif token.type == "s_open":
                    style_key = "strike"  # Strikethrough
                elif token.type == "link_open":
                    style_key = "link"
                    href = token.attrs.get("href", "") if token.attrs else ""
                    # Apply link attribute directly to the style
                    new_style = self._apply_style(
                        current_style, style_key
                    ).update_link(href or None)
                    style_stack.append(
                        new_style
                    )  # Push specialized style with link
                    i += 1
                    continue  # Skip default style push
                elif token.type == "blockquote_open":
                    style_key = "blockquote"
                    prefix = "> "
                    needs_newline = True
                elif token.type == "bullet_list_open":
                    style_key = "list_item"  # Apply base list style
                elif token.type == "list_item_open":
                    # Handle prefix and checkbox within list_item processing
                    style_key = "list_item"  # Inherit list item style
                elif (
                    token.type == "code_block" or token.type == "fence"
                ):  # Treat as single token
                    style_key = "code_block"
                    # Append code directly, don't push style for children
                    if text_obj and not text_obj.plain.endswith("\n"):
                        text_obj.append("\n")
                    text_obj.append(
                        token.content.rstrip(),
                        self.styles.get(style_key, Style()),
                    )
                    text_obj.append("\n")
                    i += 1
                    continue

                # Apply the style for the opening tag
                if style_key:
                    new_style = self._apply_style(current_style, style_key)

                if (
                    needs_newline
                    and text_obj
                    and not text_obj.plain.endswith("\n")
                ):
                    text_obj.append("\n")
                if prefix:
                    text_obj.append(
                        prefix, new_style
                    )  # Apply style to prefix too

                style_stack.append(new_style)  # Push the new style context

            # --- Block Element Close ---
            elif token.type.endswith("_close"):
                if len(style_stack) > 1:  # Don't pop the base style
                    style_stack.pop()

                # Add spacing after certain block elements
                if token.type in (
                    "paragraph_close",
                    "blockquote_close",
                    "heading_close",
                    "list_item_close",
                ):
                    # Avoid double newlines if already present
                    if text_obj and not text_obj.plain.endswith("\n\n"):
                        if text_obj.plain.endswith("\n"):
                            text_obj.append("\n")
                        else:
                            text_obj.append("\n\n")

            # --- Specific Inline Elements ---
            elif token.type == "text":
                # Handle checkboxes within list items here
                parent_token_type = tokens[i - 1].type if i > 0 else ""
                content = token.content
                item_prefix = ""
                text_style = current_style

                if parent_token_type == "list_item_open":
                    # Default bullet
                    item_prefix = "• "
                    stripped_content = content.lstrip()
                    # Check for GFM checkboxes [ ] or [x]
                    if stripped_content.startswith("[ ] "):
                        item_prefix = "☐ "
                        content = content.lstrip()[3:]  # Remove checkbox markup
                        text_style = self._apply_style(
                            current_style, "checkbox_unchecked"
                        )
                    elif stripped_content.lower().startswith("[x] "):
                        item_prefix = "☑ "
                        content = content.lstrip()[3:]  # Remove checkbox markup
                        text_style = self._apply_style(
                            current_style, "checkbox_checked"
                        )

                    # Add prefix with list item style, then text with potentially updated style
                    text_obj.append(
                        item_prefix, self.styles.get("list_item", Style())
                    )
                    text_obj.append(content, text_style)

                else:
                    # Regular text, apply current style from stack top
                    text_obj.append(content, current_style)

            elif token.type == "code_inline":
                text_obj.append(
                    token.content, self.styles.get("code_inline", Style())
                )

            elif token.type == "softbreak":
                # CommonMark soft breaks are rendered as spaces or newlines depending on context
                # For simple Rich text, often a space is sufficient unless 'breaks' option forces newline
                text_obj.append(
                    " "
                )  # Or "\n" if md_parser.options['breaks'] is True
            elif token.type == "hardbreak":
                text_obj.append("\n")

            elif token.type == "hr":
                # Add newline if needed before hr
                if text_obj and not text_obj.plain.endswith("\n"):
                    text_obj.append("\n")
                # Use Theme style or default
                text_obj.append(
                    "─" * console.width, self.styles.get("hr", Style())
                )
                text_obj.append("\n\n")

            # --- Tables (Basic - requires 'table' extension enabled) ---
            # elif token.type == "table_open": ... handle table start ...
            # elif token.type == "thead_open": ... handle header start ...
            # elif token.type == "tr_open": ... handle row start ...
            # elif token.type == "th_open": ... handle header cell start ...
            # elif token.type == "td_open": ... handle data cell start ...
            # Table rendering to Rich Text is complex, often better handled by Rich's Table object.

            # Increment token index
            i += 1

    # --- Convenience Rendering Methods ---

    # FUNC: render_to_console
    def render_to_console(
        self, markdown_str: str, target_console: Console | None = None
    ) -> None:
        """Render markdown directly to a Rich console.

        Args:
            markdown_str: Markdown-formatted string.
            target_console: Optional console instance (uses imported `console` if None).
        """
        con = target_console or console
        rich_text = self.markdown_to_rich_text(markdown_str)
        con.print(rich_text)

    # FUNC: render_to_panel
    def render_to_panel(
        self, markdown_str: str, title: str | None = None, **panel_kwargs: Any
    ) -> Panel:
        """Render markdown inside a Rich panel.

        Args:
            markdown_str: Markdown-formatted string.
            title: Optional title for the panel.
            **panel_kwargs: Additional keyword arguments for rich.panel.Panel.

        Returns:
            Rich Panel containing the rendered markdown.
        """
        rich_text = self.markdown_to_rich_text(markdown_str)
        return Panel(rich_text, title=title, **panel_kwargs)


# SECTION: TEXTUAL INTEGRATION (Optional)

if TEXTUAL_AVAILABLE and MARKDOWN_IT_AVAILABLE:

    # KLASS: MarkdownStatic
    class MarkdownStatic(Static):
        """A Textual Static widget that renders Markdown content using MarkdownRenderer."""

        # Define a reactive property for markdown content
        markdown = reactive("", layout=True)

        # FUNC: __init__
        def __init__(
            self,
            markdown: str = "",
            renderer: MarkdownRenderer | None = None,
            *args: Any,
            **kwargs: Any,
        ):
            """Initialize the markdown static widget.

            Args:
                markdown: Initial Markdown content to render.
                renderer: Optional custom MarkdownRenderer instance. Defaults to a new instance.
                *args, **kwargs: Additional arguments for the Static widget.
            """
            super().__init__(
                "", *args, **kwargs
            )  # Initialize Static with empty string
            self._renderer = renderer or MarkdownRenderer()
            # Set reactive property AFTER super init, which triggers the render
            self.markdown = markdown

        # FUNC: render (Override Static's render or watch the reactive property)
        # Watching the reactive property is generally preferred in Textual >0.10
        def watch_markdown(self, new_markdown: str) -> None:
            """Called when the 'markdown' reactive property changes."""
            rich_text = self._renderer.markdown_to_rich_text(new_markdown)
            self.update(rich_text)

        # Optional: Method to update content programmatically
        # FUNC: set_markdown (Alternative way to update)
        def set_markdown(self, markdown: str) -> None:
            """Update the widget with new markdown content."""
            self.markdown = markdown  # Setting the reactive property triggers watch_markdown


# SECTION: EXPORTS
__all__ = [
    "MarkdownRenderer",
    "escape_rich",
]

# Add Textual integration to exports if available
if TEXTUAL_AVAILABLE and MARKDOWN_IT_AVAILABLE:
    __all__.append("MarkdownStatic")
