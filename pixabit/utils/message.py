# messages.py (or define within app.py)
from typing import Any, Dict, Optional

from textual.message import Message


class DataRefreshed(Message):
    """Event posted when DataStore finishes refreshing."""

    # You could add data payload here if needed, e.g.
    # def __init__(self, success: bool):
    #     self.success = success
    #     super().__init__()
    pass  # Simple notification is often enough


class UIMessage(Message):
    """Event to show a message/notification in the UI."""

    def __init__(self, text: str, title: str = "Info", severity: str = "information") -> None:
        self.text = text
        self.title = title
        self.severity = severity
        super().__init__()


# Add other messages as needed (e.g., for errors, specific updates)
