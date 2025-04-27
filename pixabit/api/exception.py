# pixabit/habitica/exception.py

# SECTION: MODULE DOCSTRING
"""Defines a custom exception class for Habitica API errors."""

# SECTION: IMPORTS
from typing import Any

# SECTION: EXCEPTION CLASS


# KLASS: HabiticaAPIError
class HabiticaAPIError(Exception):
    """Custom exception for Habitica API errors with detailed information."""

    # FUNC: __init__
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_type: str | None = None,
        response_data: Any | None = None,
    ):
        """Initialize the API error with detailed context.

        Args:
            message: The main error message.
            status_code: The HTTP status code, if available.
            error_type: The Habitica-specific error type (e.g., 'NotFound'), if available.
            response_data: The raw response data (dict/list) from the API, if available.
        """
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.response_data = response_data

    # FUNC: __str__
    def __str__(self) -> str:
        """Format the error message with available details."""
        details: list[str] = []
        if self.status_code is not None:
            details.append(f"Status={self.status_code}")
        if self.error_type:
            details.append(f"Type='{self.error_type}'")
        # Optionally add response data preview, be careful with large responses
        # if self.response_data:
        #     details.append(f"Data={str(self.response_data)[:50]}...")

        base_msg = super().__str__()
        details_str = f" ({', '.join(details)})" if details else ""
        return f"HabiticaAPIError: {base_msg}{details_str}"
