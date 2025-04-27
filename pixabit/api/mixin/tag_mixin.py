# pixabit/habitica/mixin/tag_mixin.py

# SECTION: MODULE DOCSTRING
"""Mixin class providing Habitica Tag related API methods."""

# SECTION: IMPORTS
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

# Use TYPE_CHECKING to avoid circular import issues if API uses models
if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine  # For hinting self methods

    from pixabit.api.habitica_api import HabiticaAPI, HabiticaApiSuccessData

# SECTION: MIXIN CLASS


# KLASS: TagMixin # Renamed from TagsMixin for consistency
class TagMixin:
    """Mixin containing methods for managing Habitica Tags."""

    # Assert self is HabiticaAPI for type hinting internal methods
    if TYPE_CHECKING:
        _request: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        get: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        post: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        put: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        delete: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]

    # FUNC: get_tags
    async def get_tags(self) -> list[dict[str, Any]]:
        """Fetches all tags associated with the user.

        Returns:
            A list of tag dictionaries, or an empty list.
        """
        result = await self.get("/tags")
        return cast(list[dict[str, Any]], result) if isinstance(result, list) else []

    # FUNC: create_tag
    async def create_tag(self, name: str) -> dict[str, Any] | None:
        """Creates a new tag.

        Args:
            name: The name for the new tag.

        Returns:
            A dictionary representing the newly created tag, or None on failure.

        Raises:
            ValueError: If the tag name is empty or whitespace.
        """
        name_stripped = name.strip()
        if not name_stripped:
            raise ValueError("Tag name cannot be empty.")
        result = await self.post("/tags", data={"name": name_stripped})
        # API returns the created tag object
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: update_tag
    async def update_tag(self, tag_id: str, name: str) -> dict[str, Any] | None:
        """Updates the name of an existing tag.

        Args:
            tag_id: The ID of the tag to update.
            name: The new name for the tag.

        Returns:
            A dictionary representing the updated tag, or None on failure.

        Raises:
            ValueError: If tag_id is empty or the new name is empty/whitespace.
        """
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        name_stripped = name.strip()
        if not name_stripped:
            raise ValueError("New tag name cannot be empty.")

        result = await self.put(f"/tags/{tag_id}", data={"name": name_stripped})
        # API returns the updated tag object
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: delete_tag
    async def delete_tag(self, tag_id: str) -> bool:
        """Deletes a specific tag.

        Args:
            tag_id: The ID of the tag to delete.

        Returns:
            True if the operation was successful (API returned no data), False otherwise.

        Raises:
            ValueError: If tag_id is empty.
        """
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        result = await self.delete(f"/tags/{tag_id}")
        # Successful DELETE often returns 204 No Content (result is None)
        return result is None

    # FUNC: reorder_tag
    async def reorder_tag(self, tag_id: str, position: int) -> bool:
        """Moves a tag to a specific position in the user's tag list.

        Args:
            tag_id: The ID of the tag to move.
            position: The desired 0-based index for the tag.

        Returns:
            True if the operation was successful (API returned no data), False otherwise.

        Raises:
            ValueError: If tag_id is empty or position is invalid.
        """
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        if not isinstance(position, int) or position < 0:
            raise ValueError("Position must be a non-negative integer index.")

        # API endpoint is /reorder-tags, payload requires 'tagId' and 'to'
        payload = {"tagId": tag_id, "to": position}
        result = await self.post("/reorder-tags", data=payload)
        # Successful reorder likely returns 204 No Content (result is None)
        return result is None
