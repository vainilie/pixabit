# pixabit/tui/messages.py

# SECTION: MODULE DOCSTRING
"""Defines custom Textual Message classes for application-specific events.

These messages facilitate communication between different components (e.g.,
DataStore -> App, Widgets -> App).
"""

# SECTION: IMPORTS
from typing import Any  # Keep Any if needed for future message data

from textual.message import Message  # Import base class

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
        self.source = source  # Where the error originated (e.g., "API", "DataStore")
        self.error = error  # The exception object
        self.details = details  # Optional additional context
        super().__init__()


# Add other application-specific messages as needed:
# e.g., TaskScored, UserLoggedIn, ChallengeLeft, etc.
