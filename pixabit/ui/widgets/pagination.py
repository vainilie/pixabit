from rich.text import Text
from textual import events
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Static


class Pagination(Horizontal):
    """A custom pagination widget for Textual applications."""

    class PageChanged(Message):
        """Message sent when the page is changed."""

        def __init__(self, page: int) -> None:
            """Initialize with the new page number.

            Args:
                page: The new page number (1-indexed)
            """
            self.page = page
            super().__init__()

    def __init__(
        self,
        page_count: int = 1,
        current_page: int = 1,
        page_size: int = 10,
        id: str = None,
        classes: str = None,
    ) -> None:
        """Initialize the pagination widget.

        Args:
            page_count: Total number of pages
            current_page: Currently active page (1-indexed)
            page_size: Number of items per page
            id: The optional ID of the widget
            classes: The optional CSS classes of the widget
        """
        super().__init__(id=id, classes=classes)
        self.page_count = max(1, page_count)
        self._current_page = min(max(1, current_page), self.page_count)
        self.page_size = page_size

    @property
    def current_page(self) -> int:
        """Get the current page (1-indexed)."""
        return self._current_page

    @current_page.setter
    def current_page(self, value: int) -> None:
        """Set the current page, ensuring it's within valid range.

        Args:
            value: The new page number (1-indexed)
        """
        old_value = self._current_page
        self._current_page = min(max(1, value), self.page_count)

        if self._current_page != old_value:
            self.post_message(self.PageChanged(self._current_page))
            self.refresh()

    @property
    def page_count(self) -> int:
        """Get the total number of pages."""
        return self._page_count

    @page_count.setter
    def page_count(self, value: int) -> None:
        """Set the total number of pages.

        Args:
            value: The new page count
        """
        self._page_count = max(1, value)
        # Ensure current page is still valid
        if hasattr(self, "_current_page"):
            self._current_page = min(self._current_page, self._page_count)
        self.refresh()

    def compose(self):
        """Compose the pagination widget with navigation buttons."""
        yield Button("«", id="page-first", disabled=self.current_page == 1)
        yield Button("‹", id="page-prev", disabled=self.current_page == 1)

        yield Static(f"Page {self.current_page} of {self.page_count}", id="page-info")

        yield Button("›", id="page-next", disabled=self.current_page == self.page_count)
        yield Button("»", id="page-last", disabled=self.current_page == self.page_count)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events for pagination navigation.

        Args:
            event: The button pressed event
        """
        button_id = event.button.id

        if button_id == "page-first":
            self.current_page = 1
        elif button_id == "page-prev":
            self.current_page = self.current_page - 1
        elif button_id == "page-next":
            self.current_page = self.current_page + 1
        elif button_id == "page-last":
            self.current_page = self.page_count
