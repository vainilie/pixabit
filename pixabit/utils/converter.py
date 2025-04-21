import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

# --- Imports for Rich Conversion ---
try:
    import markdown_it
    from markdown_it.renderer import RendererProtocol
    from markdown_it.token import Token
    from markdown_it.utils import OptionsDict

    MARKDOWN_IT_AVAILABLE = True
except ImportError:
    MARKDOWN_IT_AVAILABLE = False
    # Define dummy types if library is not available
    OptionsDict = Dict[str, Any]
    Token = Any
    Sequence = List

    class RendererProtocol:
        pass

    RichRenderer = None  # Will be defined below if library exists


# --- Helper Function ---
def escape_rich(text: str) -> str:
    """Escapes '[' characters for Rich markup."""
    if not text:
        return ""
    # Basic escaping sufficient for many Rich use cases
    return text.replace("[", r"\[")


# --- Custom Rich Renderer (using the version from previous steps) ---
if MARKDOWN_IT_AVAILABLE:

    class RichRenderer(RendererProtocol):
        """markdown-it-py renderer targeting Rich Console Markup."""

        __output__ = "rich"

        def __init__(self, md: Optional[markdown_it.MarkdownIt] = None):
            self._list_level = 0
            self._list_indent = "  "  # Indent two spaces per level
            self._ordered_info: List[Dict[str, Any]] = []  # Stack for ordered list counters

        def render(self, tokens: Sequence[Token], options: OptionsDict, env: Dict[str, Any]) -> str:
            """Takes token stream and generates Rich text."""
            # This loop structure correctly uses specific methods or renderToken fallback
            result = ""
            for i, token in enumerate(tokens):
                renderer_method = getattr(self, token.type, self.renderToken)
                result += renderer_method(tokens, i, options, env)
            return result

        def renderInline(self, tokens: Sequence[Token], options: OptionsDict, env: Dict) -> str:
            """Render inline tokens by calling the appropriate render methods."""
            result = ""
            for i, token in enumerate(tokens):
                renderer_method = getattr(self, token.type, self.renderToken)
                result += renderer_method(tokens, i, options, env)
            return result

        def renderToken(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            """Fallback for rendering tokens not explicitly handled."""
            token = tokens[idx]
            # Fallback: render children for block tokens, or escape text content
            if token.children:
                return self.renderInline(token.children, options, env)
            elif token.content:
                # Ensure empty strings are handled correctly if content exists but is empty
                return escape_rich(token.content) if token.content else ""
            # print(f"Warning: Unhandled token type '{token.type}' was ignored.")
            return ""  # Ignore other unhandled tokens

        # --- Block Token Renderers (Using Simplified Spacing) ---
        def heading_open(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            level = int(tokens[idx].tag[1])
            color = {1: "#FF5733", 2: "#33FF57", 3: "#339CFF"}.get(level, "bold")
            prefix = "\n" if idx > 0 else ""  # Add newline before heading unless first element
            return f"{prefix}[bold {color}]"

        def heading_close(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            return "[/]\n"  # Newline AFTER heading

        def paragraph_open(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            return ""  # Paragraphs don't add leading space

        def paragraph_close(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            # Add a newline after paragraph content, creates spacing
            # Avoid adding if it's the very last token potentially
            if idx < len(tokens) - 2:
                return "\n"
            return ""

        def fence(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict) -> str:
            token = tokens[idx]
            content = escape_rich(token.content.rstrip("\n"))
            prefix = "\n"  # Always add newline before code block for separation
            return f"{prefix}[reverse #363642 on #FFD700]{content}[/]\n"  # And after

        def bullet_list_open(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            self._list_level += 1
            return "\n"  # Start list on a new line

        def bullet_list_close(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            self._list_level -= 1
            return ""  # Rely on next block's opening newline or paragraph close

        def ordered_list_open(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            self._list_level += 1
            start = tokens[idx].attrGet("start") or 1
            self._ordered_info.append({"counter": start, "level": self._list_level})
            return "\n"  # Start list on a new line

        def ordered_list_close(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            if self._ordered_info and self._ordered_info[-1]["level"] == self._list_level:
                self._ordered_info.pop()
            self._list_level -= 1
            return ""

        def list_item_open(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            indent = self._list_indent * (self._list_level - 1)
            list_marker = "•"
            if self._ordered_info and self._ordered_info[-1]["level"] == self._list_level:
                current_counter = self._ordered_info[-1]["counter"]
                list_marker = f"{current_counter}."
                self._ordered_info[-1]["counter"] += 1
            # Add newline before item marker only if it follows another list item directly
            prefix = "\n" if idx > 0 and tokens[idx - 1].type == "list_item_close" else ""
            return f"{prefix}{indent}{list_marker} "

        def list_item_close(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            # Let content (paragraph) inside handle closing newline
            return ""

        # --- Inline Token Renderers ---
        def inline(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict) -> str:
            """Render an 'inline' token by rendering its children."""
            return self.renderInline(tokens[idx].children or [], options, env)

        def text(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict) -> str:
            return escape_rich(tokens[idx].content)

        def code_inline(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            content = escape_rich(tokens[idx].content)
            return f"[reverse #363642 on #FFD700]{content}[/]"

        def strong_open(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            return "[bold]"

        def strong_close(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            return "[/bold]"

        def em_open(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            return "[italic]"

        def em_close(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            return "[/italic]"

        def link_open(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            href = escape_rich(tokens[idx].attrGet("href") or "")
            return f"[link={href}][bold][#00FFFF]"  # Using the bold+color style

        def link_close(
            self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict
        ) -> str:
            return "[/][/bold][/link]"  # Close color, bold, then link

        def image(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: Dict) -> str:
            token = tokens[idx]
            src = escape_rich(token.attrGet("src") or "")
            alt_text = self._renderInlineAsText(token.children or [], options, env)
            alt = escape_rich(alt_text)
            return f"[Image: {alt} @ {src}]"  # Text representation

        # Helper to render inline content as plain text for alt attributes etc.
        def _renderInlineAsText(
            self, tokens: Sequence[Token], options: OptionsDict, env: Dict
        ) -> str:
            result = ""
            for token in tokens:
                if token.type == "text":
                    result += token.content
                elif token.type == "image":
                    result += self._renderInlineAsText(token.children or [], options, env)
            return result

        pass  # End of RichRenderer definition


# --- Simplified Converter Class ---
class MarkdownConverter:
    """Converts Markdown to Rich text using markdown-it-py"""

    # --- Rich Parser Initialization ---
    md_parser = None
    if MARKDOWN_IT_AVAILABLE and RichRenderer:
        md_parser = markdown_it.MarkdownIt(renderer_cls=RichRenderer)
    elif not MARKDOWN_IT_AVAILABLE:
        print("Warning: markdown-it-py library not found. Rich text conversion unavailable.")

    @classmethod
    def convert_to_rich(cls, markdown: str) -> str:
        """Converts markdown string to Rich text markup."""
        if not markdown:
            return ""

        if cls.md_parser:
            try:
                # Each render call uses a new renderer instance, resetting state (like list counters)
                rich_text = cls.md_parser.render(markdown)
                return rich_text.strip()  # Strip final whitespace
            except Exception as e:
                print(f"Error during Rich conversion: {e}")
                # Fallback to escaped original text on error
                return f"[red]Error during conversion:[/red]\n{escape_rich(markdown)}"
        else:
            # If library wasn't imported, return informative message
            return "[red]Error: markdown-it-py not installed.[/red]"


# --- Example Usage ---
if __name__ == "__main__":
    if not MARKDOWN_IT_AVAILABLE:
        print("Please install markdown-it-py to run this example: pip install markdown-it-py")
    else:
        sample_md = """
# Heading 1
Some introduction text. *Italic* and **Bold**.

A paragraph with a
soft line break.

Another paragraph.

## Lists

- Item A

- Item B
  1. Nested 1 (Starts 1)

  2. Nested 2
    - Deeper Bullet
- Item C

### Code and Links
```python
print("Hello") # Comment
"""
