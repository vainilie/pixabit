# pixabit/habitica/mixin/message_mixin.py

# SECTION: MODULE DOCSTRING
"""Mixin class providing Habitica Messaging (Inbox/PM) related API methods."""

# SECTION: IMPORTS
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

# Use TYPE_CHECKING to avoid circular import issues if API uses models
if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine  # For hinting self methods

    from pixabit.api.habitica_api import HabiticaAPI, HabiticaApiSuccessData

# SECTION: MIXIN CLASS


# KLASS: MessageMixin
class MessageMixin:
    """Mixin containing methods for interacting with Habitica Messages."""

    # Assert self is HabiticaAPI for type hinting internal methods
    if TYPE_CHECKING:
        _request: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        get: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        post: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        put: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        delete: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]

    # FUNC: get_inbox_messages
    async def get_inbox_messages(self, page: int = 0, conversation_id: str | None = None) -> list[dict[str, Any]]:
        """Fetches inbox messages, optionally filtered by conversation.

        Args:
            page: The page number to retrieve (0-indexed).
            conversation_id: Optional UUID of the other user in the conversation.

        Returns:
            A list of message dictionaries, or an empty list.
        """
        params: dict[str, Any] = {"page": page}
        if conversation_id:
            # API parameter is 'conversation' according to docs
            params["conversation"] = conversation_id
        result = await self.get("/inbox/messages", params=params)
        return cast(list[dict[str, Any]], result) if isinstance(result, list) else []

    # FUNC: send_private_message
    async def send_private_message(self, recipient_id: str, message_text: str) -> dict[str, Any] | None:
        """Sends a private message to another user.

        Args:
            recipient_id: The UUID of the recipient user.
            message_text: The content of the message.

        Returns:
            A dictionary representing the sent message confirmation, or None on failure.

        Raises:
            ValueError: If recipient_id or message_text is empty.
        """
        if not recipient_id:
            raise ValueError("recipient_id is required.")
        message_text_stripped = message_text.strip()
        if not message_text_stripped:
            raise ValueError("message_text cannot be empty.")

        payload = {"toUserId": recipient_id, "message": message_text_stripped}
        # Endpoint is documented as /members/send-private-message
        result = await self.post("/members/send-private-message", data=payload)
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: mark_pms_read
    async def mark_pms_read(self) -> bool:
        """Marks all private messages as read for the current user.

        Returns:
            True if the operation was successful (API returned no data), False otherwise.
        """
        # Endpoint is /user/mark-pms-read
        result = await self.post("/user/mark-pms-read")
        return result is None

    # FUNC: delete_private_message
    async def delete_private_message(self, message_id: str) -> bool:
        """Deletes a specific private message.

        Args:
            message_id: The ID (_id) of the message to delete.

        Returns:
            True if the operation was successful (API returned no data), False otherwise.

        Raises:
            ValueError: If message_id is empty.
        """
        if not message_id:
            raise ValueError("message_id is required.")
        # Endpoint includes user prefix based on some API patterns, double-check docs if issues arise
        result = await self.delete(f"/user/messages/{message_id}")
        return result is None
