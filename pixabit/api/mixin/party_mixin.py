# pixabit/habitica/mixin/party_mixin.py

# SECTION: MODULE DOCSTRING
"""Mixin class providing Habitica Party and Group related API methods."""

# SECTION: IMPORTS
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pixabit.api.exception import HabiticaAPIError

# Assuming logger helper is in helpers
from pixabit.helpers._logger import log

# Use TYPE_CHECKING to avoid circular import issues if API uses models
if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine  # For hinting self methods

    from pixabit.api.habitica_api import HabiticaAPI, HabiticaApiSuccessData

# SECTION: MIXIN CLASS


# KLASS: PartyMixin
class PartyMixin:
    """Mixin containing methods for interacting with Habitica Parties and Groups."""

    # Assert self is HabiticaAPI for type hinting internal methods
    if TYPE_CHECKING:
        _request: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        get: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        post: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        put: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        delete: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        # Removed _ensure_type

    # FUNC: get_party_data
    async def get_party_data(self) -> dict[str, Any] | None:
        """Fetches data for the user's current party.

        Returns:
            A dictionary containing party data, or None if not in a party or on error.
        """
        # Endpoint is /groups/party for the user's party
        result = await self.get("/groups/party")
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: get_group_chat_messages
    async def get_group_chat_messages(self, group_id: str) -> list[dict[str, Any]]:
        """Fetches chat messages for a specific group (party, guild, tavern).

        Args:
            group_id: The ID of the group ('party', guild ID, or 'tavern').

        Returns:
            A list of chat message dictionaries, or an empty list.

        Raises:
            ValueError: If group_id is empty.
        """
        if not group_id:
            raise ValueError("group_id cannot be empty.")

        params: dict[str, Any] = {}

        result = await self.get(f"/groups/{group_id}/chat", params=params)
        return cast(list[dict[str, Any]], result) if isinstance(result, list) else []

    # FUNC: like_group_chat_message
    async def like_group_chat_message(self, group_id: str, chat_id: str) -> dict[str, Any] | None:
        """Likes a specific chat message within a group.

        Args:
            group_id: The ID of the group containing the message.
            chat_id: The ID (_id) of the chat message to like.

        Returns:
            A dictionary confirming the like action, or None on failure.

        Raises:
            ValueError: If group_id or chat_id is empty.
        """
        if not group_id or not chat_id:
            raise ValueError("group_id and chat_id are required.")
        # Note: API endpoint requires POST, not GET
        result = await self.post(f"/groups/{group_id}/chat/{chat_id}/like")
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: mark_group_chat_seen
    async def mark_group_chat_seen(self, group_id: str = "party") -> bool:
        """Marks messages in a group chat as seen by the user.

        Args:
            group_id: The ID of the group ('party', guild ID, 'tavern').

        Returns:
            True if the operation was successful (API returned no data), False otherwise.

        Raises:
            ValueError: If group_id is empty.
        """
        if not group_id:
            raise ValueError("group_id cannot be empty.")
        result = await self.post(f"/groups/{group_id}/chat/seen")
        return result is None

    # FUNC: post_group_chat_message
    async def post_group_chat_message(self, group_id: str = "party", message_text: str = "") -> dict[str, Any] | None:
        """Posts a message to a group chat.

        Args:
            group_id: The ID of the group ('party', guild ID, 'tavern').
            message_text: The content of the message to post.

        Returns:
            A dictionary representing the posted message, or None on failure.

        Raises:
            ValueError: If group_id is empty or message_text is empty/whitespace.
        """
        if not group_id:
            raise ValueError("group_id is required.")
        message_text_stripped = message_text.strip()
        if not message_text_stripped:
            raise ValueError("message_text cannot be empty.")

        payload = {"message": message_text_stripped}
        result = await self.post(f"/groups/{group_id}/chat", data=payload)
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: get_quest_status (Checks if party quest is active)
    async def get_quest_status(self) -> bool | None:
        """Checks if the user's party is currently on an active quest.

        Returns:
            True if a quest is active, False if not active or no quest,
            None if not in a party or an error occurred.
        """
        try:
            party_data = await self.get_party_data()
            if party_data is None:
                log.info("User not in a party, cannot get quest status.")
                return None  # Not in a party

            quest_info = party_data.get("quest", {})
            # Check if 'active' is true and 'completed' is missing/false
            is_active = isinstance(quest_info, dict) and quest_info.get("active", False) and not quest_info.get("completed")
            log.debug(f"Party quest active status: {is_active}")
            return is_active

        except HabiticaAPIError as e:
            log.error(f"API Error getting quest status: {e}")
            return None
        except Exception as e:
            log.exception(f"Unexpected error getting quest status: {e}")
            return None

    # FUNC: cast_skill
    async def cast_skill(self, spell_id: str, target_id: str | None = None) -> dict[str, Any] | None:
        """Casts a class skill/spell, optionally targeting another user.

        Args:
            spell_id: The key/ID of the skill/spell to cast (e.g., 'smash', 'healAll').
            target_id: Optional UUID of the user to target (for single-target skills).

        Returns:
            A dictionary containing the result of the cast (e.g., updated stats), or None on failure.

        Raises:
            ValueError: If spell_id is empty.
        """
        if not spell_id:
            raise ValueError("spell_id cannot be empty.")

        params = {"targetId": target_id} if target_id else None
        # Endpoint: /user/class/cast/:spellId
        result = await self.post(f"/user/class/cast/{spell_id}", params=params)
        # API returns the updated user data or error
        return cast(dict[str, Any], result) if isinstance(result, dict) else None
