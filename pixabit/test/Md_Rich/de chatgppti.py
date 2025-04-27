"""Provides utilities for converting Markdown to Rich Text and Textual widgets."""

# SECTION: IMPORTS
from typing import Any, Dict, List, Optional

import markdown_it
from markdown_it.token import Token
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

# Textual integration (optional)
try:
    from textual.widgets import Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    Static = object
    TEXTUAL_AVAILABLE = False

# Use themed console if available
try:
    from .display import console
except ImportError:
    console = Console()

# SECTION: UTILITY FUNCTIONS


def escape_rich(text: str) -> str:
    """Escape Rich markup control characters."""
    return text.replace("[", r"\[").replace("]", r"\]") if text else ""


# SECTION: MARKDOWN RENDERER


class MarkdownRenderer:
    """Converts Markdown to Rich Text and optionally to Textual widgets."""

    DEFAULT_STYLES = {
        "h1": Style(bold=True, color="cyan"),
        "h2": Style(bold=True, color="bright_cyan"),
        "h3": Style(bold=True, color="blue"),
        "h4": Style(underline=True, color="bright_blue"),
        "h5": Style(italic=True, color="blue"),
        "h6": Style(italic=True, dim=True),
        "strong": Style(bold=True),
        "em": Style(italic=True),
        "code_inline": Style(reverse=True),
        "code_block": Style(bgcolor="black", color="green"),
        "strike": Style(strike=True),
        "link": Style(underline=True, color="bright_blue"),
        "blockquote": Style(italic=True, color="green"),
        "hr": Style(dim=True),
    }

    def __init__(self, custom_styles: dict[str, Style] | None = None):
        self.md_parser = markdown_it.MarkdownIt(
            "commonmark", {"breaks": True, "html": True}
        )
        self.styles = self.DEFAULT_STYLES.copy()
        if custom_styles:
            self.styles.update(custom_styles)

    def markdown_to_rich_text(self, markdown_str: str) -> Text:
        if not markdown_str:
            return Text()
        tokens = self.md_parser.parse(markdown_str)
        result = Text()
        self._process_tokens(tokens, result)
        return result

    def _process_tokens(
        self,
        tokens: list[Token],
        text_obj: Text,
        current_styles: dict[str, Any] | None = None,
    ) -> None:
        if current_styles is None:
            current_styles = {}

        i = 0
        while i < len(tokens):
            token = tokens[i]

            if token.type == "inline" and token.children:
                self._process_tokens(
                    token.children, text_obj, current_styles.copy()
                )
                i += 1
                continue

            elif token.type.startswith("heading_open"):
                level = int(token.tag[1])
                heading_style = self.styles.get(f"h{level}", Style())
                temp_styles = current_styles.copy()
                temp_styles.update(heading_style.serialize())

                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    heading_text = Text()
                    self._process_tokens(
                        [tokens[i + 1]], heading_text, temp_styles
                    )
                    text_obj.append(heading_text)
                    text_obj.append("\n")
                    i += 3
                    continue

            elif token.type == "text":
                text_obj.append(token.content, Style(**current_styles))

            elif token.type == "strong_open":
                current_styles.update(self.styles["strong"].serialize())
            elif token.type == "strong_close":
                for k in self.styles["strong"].serialize():
                    current_styles.pop(k, None)

            elif token.type == "em_open":
                current_styles.update(self.styles["em"].serialize())
            elif token.type == "em_close":
                for k in self.styles["em"].serialize():
                    current_styles.pop(k, None)

            elif token.type == "code_inline":
                text_obj.append(token.content, self.styles["code_inline"])

            elif token.type == "code_block":
                text_obj.append("\n")
                text_obj.append(token.content, self.styles["code_block"])
                text_obj.append("\n")

            elif token.type == "fence":
                text_obj.append("\n")
                text_obj.append(token.content, self.styles["code_block"])
                text_obj.append("\n")

            elif token.type == "s_open":
                current_styles.update(self.styles["strike"].serialize())
            elif token.type == "s_close":
                for k in self.styles["strike"].serialize():
                    current_styles.pop(k, None)

            elif token.type == "link_open":
                current_styles.update(self.styles["link"].serialize())
                if "href" in token.attrs:
                    current_styles["url"] = token.attrs["href"]
            elif token.type == "link_close":
                for k in self.styles["link"].serialize():
                    current_styles.pop(k, None)
                current_styles.pop("url", None)

            elif (
                token.type == "paragraph_close"
                or token.type == "blockquote_close"
            ):
                text_obj.append("\n\n")

            elif token.type == "hardbreak":
                text_obj.append("\n")

            elif token.type == "hr":
                text_obj.append("-" * 40 + "\n", self.styles["hr"])

            elif token.type == "blockquote_open":
                text_obj.append("> ", self.styles["blockquote"])

            i += 1

    def markdown_to_rich_markdown(self, markdown_str: str) -> Markdown:
        return Markdown(markdown_str)

    def render_to_console(
        self, markdown_str: str, console: Console | None = None
    ) -> None:
        (console or globals().get("console", Console())).print(
            self.markdown_to_rich_text(markdown_str)
        )

    def render_to_panel(
        self, markdown_str: str, title: str | None = None, **panel_kwargs
    ) -> Panel:
        return Panel(
            self.markdown_to_rich_text(markdown_str),
            title=title,
            **panel_kwargs,
        )


# SECTION: TEXTUAL WIDGET

if TEXTUAL_AVAILABLE:

    class MarkdownStatic(Static):
        def __init__(
            self,
            markdown: str = "",
            renderer: MarkdownRenderer | None = None,
            *args,
            **kwargs,
        ):
            super().__init__("", *args, **kwargs)
            self.markdown_content = markdown
            self._renderer = renderer or MarkdownRenderer()

        def set_markdown(self, markdown: str) -> None:
            self.markdown_content = markdown
            self.update(self._renderer.markdown_to_rich_text(markdown))

        def on_mount(self) -> None:
            if self.markdown_content:
                self.update(
                    self._renderer.markdown_to_rich_text(self.markdown_content)
                )


# SECTION: EXPORTS

__all__ = ["MarkdownRenderer", "escape_rich"]
if TEXTUAL_AVAILABLE:
    __all__.append("MarkdownStatic")
