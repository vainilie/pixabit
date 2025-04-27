# pixabit/habitica/mixin/user_mixin.py

# SECTION: MODULE DOCSTRING
"""Mixin class providing Habitica User related API methods."""

# SECTION: IMPORTS
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

# Use TYPE_CHECKING to avoid circular import issues if API uses models
if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine  # For hinting self methods

    from pixabit.api.habitica_api import HabiticaAPI, HabiticaApiSuccessData

# SECTION: MIXIN CLASS


# KLASS: UserMixin
class UserMixin:
    """Mixin containing methods for interacting with the Habitica User endpoint."""

    # Assert self is HabiticaAPI for type hinting internal methods
    if TYPE_CHECKING:
        _request: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        get: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        post: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        put: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        delete: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]

    # FUNC: get_user_data
    async def get_user_data(self) -> dict[str, Any] | None:
        """Fetches the authenticated user's data object.

        Returns:
            A dictionary containing the user's data, or None on failure.
        """
        # Endpoint: /user
        result = await self.get("user")
        # User data is expected to be a dictionary
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: update_user
    async def update_user(self, update_data: dict[str, Any]) -> dict[str, Any] | None:
        """Updates user preferences or settings.

        Args:
            update_data: A dictionary containing the fields to update (e.g., {"preferences.sleep": True}).
                         Uses dot notation for nested fields.

        Returns:
            A dictionary representing the updated user data, or None on failure.

        Raises:
            ValueError: If update_data is empty.
        """
        if not update_data:
            raise ValueError("update_data cannot be empty.")
        # Endpoint: /user
        result = await self.put("user", data=update_data)
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: toggle_user_sleep
    async def toggle_user_sleep(self) -> bool | None:
        """Toggles the user's sleep status (resting in the Inn).

        Returns:
            The new sleep status (True if sleeping, False if awake) if successful, None otherwise.
        """
        # Endpoint: /user/sleep
        result = await self.post("user/sleep")
        # The API documentation suggests the 'data' field in the response contains the new sleep status.
        if isinstance(result, bool):
            return result  # API directly returns boolean in 'data'
        elif isinstance(result, dict) and "data" in result and isinstance(result["data"], bool):
            return result["data"]  # Handle if wrapped in standard {success:true, data: bool}
        # Fallback based on observed behavior or if docs are unclear: Check if result is a dict and non-empty?
        # elif isinstance(result, dict):
        #     return result.get('sleep_status_key') # Check if a specific key indicates status
        return None  # Return None if status cannot be determined

    # FUNC: run_cron
    async def run_cron(self) -> dict[str, Any] | None:
        """Manually triggers the user's cron process (resets dailies, etc.).

        Note: Use with caution, intended primarily for development/testing.

        Returns:
            A dictionary confirming the cron run (often empty), or None on failure.
        """
        # Endpoint: /cron
        result = await self.post("cron")
        # Cron response is typically empty or just {success: true, data: {}}
        return cast(dict[str, Any], result) if isinstance(result, dict) else {}  # Return empty dict on success if None

    # FUNC: set_custom_day_start
    async def set_custom_day_start(self, hour: int) -> dict[str, Any] | None:
        """Sets the user's custom day start hour (when dailies reset).

        Args:
            hour: The hour in 24-hour format (0-23) when the day should start.

        Returns:
            The updated user data dictionary, or None on failure.

        Raises:
            ValueError: If the hour is outside the valid range (0-23).
        """
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23 (inclusive).")

        # Endpoint: /user/custom-day-start
        result = await self.post("user/custom-day-start", data={"dayStart": hour})
        return cast(dict[str, Any], result) if isinstance(result, dict) else None
