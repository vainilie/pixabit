"""Helpers to convert Markdown to Rich."""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Dict, Optional, Sequence

logger = logging.getLogger(__name__)

try:
    import markdown_it
    from markdown_it.renderer import RendererProtocol
    from markdown_it.token import Token
    from markdown_it.utils import OptionsDict

    MarkdownToken = Token
    MarkdownOptionsDict = OptionsDict
    MarkdownRendererProtocol = RendererProtocol

    MARKDOWN_IT_AVAILABLE = True
except ImportError:
    from typing import Any, Dict, List

    MarkdownToken = Any
    MarkdownOptionsDict = dict[str, Any]
    MarkdownRendererProtocol = Any  # Fallback, not used for actual rendering

    Sequence = List  # fallback
    MARKDOWN_IT_AVAILABLE = False


def escape_rich(text: str) -> str:
    """Escape Rich control characters in text, e.g., unescaped brackets."""
    return text.replace("[", r"\[") if text else ""


class RichRenderer:
    """Renderer that translates Markdown tokens into Rich-friendly strings."""

    name = "rich"
    options: ClassVar[MarkdownOptionsDict] = {}

    def __init__(self) -> None:
        self.output: list[str] = []

    def render(
        self,
        tokens: Sequence[MarkdownToken],
        options: MarkdownOptionsDict | None,
        env: dict | None = None,
    ) -> str:
        """Render Markdown tokens into a Rich-friendly string."""
        self.output.clear()
        for i, token in enumerate(tokens):
            method_name = f"{token.type}_render"
            method = getattr(self, method_name, self.fallback)
            self.output.append(method(tokens, i, options, env))
        return "".join(self.output)

    def fallback(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        """Fallback renderer when no specific method is found."""
        return tokens[idx].content or ""

    def inline(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        """Render inline tokens recursively."""
        return self.render(tokens[idx].children or [], options, env)

    def paragraph_open(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        return ""

    def paragraph_close(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        return "\n"

    def bullet_list_open(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        return ""

    def bullet_list_close(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        return ""

    def list_item_open(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        return "• "

    def list_item_close(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        return "\n"

    def strong_open(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        return "[bold]"

    def strong_close(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        return "[/bold]"

    def em_open(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        return "[italic]"

    def em_close(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        return "[/italic]"

    def link_open(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        href = tokens[idx].attrs.get("href") if tokens[idx].attrs else ""
        return f"[link={href}]"

    def link_close(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        return "[/link]"

    def heading_open(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        level = tokens[idx].tag[1]
        return "[bold magenta]"

    def heading_close(
        self,
        tokens: Sequence[MarkdownToken],
        idx: int,
        options: MarkdownOptionsDict | None,
        env: dict | None,
    ) -> str:
        return "[/bold magenta]\n"


class RichMarkdown:
    """Markdown processor that renders to Rich-friendly output using markdown-it-py."""

    md_parser: ClassVar[Any | None] = None

    @classmethod
    def to_rich(cls, text: str) -> str:
        """Convert Markdown text into a Rich-compatible string."""
        if not text:
            return ""

        if not MARKDOWN_IT_AVAILABLE:
            return escape_rich(text)

        if cls.md_parser is None:
            try:
                cls.md_parser = markdown_it.MarkdownIt(
                    renderer_cls=RichRenderer
                )
            except Exception as e:
                logger.exception(
                    "Failed to initialize MarkdownIt with RichRenderer"
                )
                return escape_rich(text)

        try:
            return cls.md_parser.render(text)
        except Exception as e:
            logger.exception("Failed to render Markdown with RichRenderer")
            return escape_rich(text)
