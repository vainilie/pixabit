user data


from enum import Enum, auto
from typing import Any, List, Optional, TypeVar, Union, cast

T = TypeVar("T")  # Tipo genérico para ayudar con las conversiones

class UserMixin:
    # Métodos para usuario
    async def get_user_data(self) -> dict[str, Any]:
        """Get current user data."""
        result = await self.get("user")
        return self._ensure_type(result, dict) or {}

    async def update_user(self, update_data: dict[str, Any]) -> dict[str, Any]:
        """Update user preferences or settings."""
        result = await self.put("user", data=update_data)
        return self._ensure_type(result, dict) or {}


    async def toggle_user_sleep(self) -> bool | dict[str, Any]:
        """Toggle the user's sleep state.

        Returns:
            User data or success indicator
        """
        return await self.post("user/sleep")

    async def run_cron(self) -> dict[str, Any]:
        """Run cron manually to reset dailies.

        Returns:
            Cron response data
        """
        result = await self.post("cron")
        return self._ensure_type(result, dict) or {}


    async def set_custom_day_start(self, hour: int) -> dict[str, Any]:
        """Set the user's custom day start hour.

        Args:
            hour: Hour in 24-hour format (0-23)

        Returns:
            Updated user data

        Raises:
            ValueError: If hour is not between 0 and 23
        """
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")

        result = await self.post(
            "user/custom-day-start", data={"dayStart": hour}
        )
        return self._ensure_type(result, dict) or {}
