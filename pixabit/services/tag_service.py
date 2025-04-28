# pixabit/services/tag_service.py

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pixabit.helpers._logger import log
from pixabit.models.tag import Tag  # Asumiendo el Tag simple por ahora

if TYPE_CHECKING:
    from pixabit.api.client import HabiticaClient
    from pixabit.models.tag import TagList  # O tag_factory.TagList si usas el avanzado

    from .data_manager import DataManager


class TagService:
    """Service layer for interacting with Habitica Tags.
    Coordinates API calls and updates the local data managed by DataManager.
    """

    def __init__(self, api_client: HabiticaClient, data_manager: DataManager):
        """Initializes the TagService.

        Args:
            api_client: The Habitica API client instance.
            data_manager: The data manager instance holding live data models.
        """
        self.api = api_client
        self.dm = data_manager
        log.debug("TagService initialized.")

    # --- Read Operations (Synchronous - access cached data) ---

    def get_tags(self) -> TagList | None:
        """Returns the cached TagList instance from the DataManager."""
        # Ensure data is loaded before accessing? The TUI layer should ensure this.
        if not self.dm.tags:
            log.warning("Attempted to get tags, but TagList is not loaded in DataManager.")
        return self.dm.tags

    def get_tag_by_id(self, tag_id: str) -> Tag | None:
        """Gets a specific tag by its ID from the cached TagList."""
        tag_list = self.get_tags()
        if tag_list:
            return tag_list.get_by_id(tag_id)
        return None

    # --- Write Operations (Asynchronous - interact with API and cache) ---

    async def create_tag(self, name: str) -> Tag | None:
        """Creates a new tag via the API and adds it to the local TagList.

        Args:
            name: The name for the new tag.

        Returns:
            The created Tag object, or None if creation failed.

        Raises:
            ValueError: If the name is empty.
            HabiticaAPIError: If the API call fails.
        """
        name_stripped = name.strip()
        if not name_stripped:
            log.error("Tag creation failed: Name cannot be empty.")
            raise ValueError("Tag name cannot be empty.")

        log.info(f"Attempting to create tag with name: '{name_stripped}'")
        try:
            # 1. Call API
            # create_tag in mixin returns dict or None
            tag_data: dict[str, any] | None = await self.api.create_tag(name=name_stripped)

            if not tag_data:
                # This case might happen if API returns success but no data, or if the method returns None on failure
                log.error("API call to create tag did not return data.")
                # Consider raising an error or returning None based on expected API behavior
                return None  # Or raise HabiticaAPIError("Failed to create tag, no data returned")

            # 2. Validate API response into Tag model
            # Use TagList's factory if available and configured, otherwise simple Tag
            tag_list = self.get_tags()
            if tag_list and hasattr(tag_list, "factory") and tag_list.factory:
                new_tag = tag_list.factory.create_tag(tag_data)
            else:
                new_tag = Tag.model_validate(tag_data)  # Use simple Tag validation

            # 3. Add to local cache (DataManager's TagList)
            if tag_list:
                tag_list.add_tag(new_tag)  # Assumes TagList has add_tag method
                log.info(f"Successfully created and cached tag: {new_tag}")
                # Optionally trigger saving the updated TagList cache file via DataManager
                # self.dm.save_tags() # If such a method exists
                return new_tag
            else:
                log.error("Cannot add created tag: TagList not loaded in DataManager.")
                # Return the tag instance even if caching fails? Or None? Return instance for now.
                return new_tag

        except ValueError as ve:  # Catch specific input errors
            log.error(f"Input validation error creating tag: {ve}")
            raise  # Re-raise input validation errors
        except Exception as e:  # Catch API errors or other issues
            log.exception(f"Failed to create tag '{name_stripped}': {e}")
            # Re-raise the exception so the caller (TUI) knows it failed
            raise

    async def update_tag(self, tag_id: str, new_name: str) -> Tag | None:
        """Updates an existing tag's name via the API and updates the local cache.

        Args:
            tag_id: The ID of the tag to update.
            new_name: The new name for the tag.

        Returns:
            The updated Tag object, or None if update failed.

        Raises:
            ValueError: If the name is empty or tag not found/is challenge tag.
            HabiticaAPIError: If the API call fails.
        """
        name_stripped = new_name.strip()
        if not name_stripped:
            log.error("Tag update failed: New name cannot be empty.")
            raise ValueError("New tag name cannot be empty.")

        tag_list = self.get_tags()
        if not tag_list:
            log.error(f"Cannot update tag '{tag_id}': TagList not loaded.")
            raise ValueError("Tag list not available.")  # Or return None

        existing_tag = tag_list.get_by_id(tag_id)
        if not existing_tag:
            log.error(f"Tag update failed: Tag ID '{tag_id}' not found.")
            raise ValueError(f"Tag with ID '{tag_id}' not found.")
        if existing_tag.challenge:
            log.error(f"Tag update failed: Cannot update challenge tag '{tag_id}'.")
            raise ValueError("Cannot update challenge tags.")

        log.info(f"Attempting to update tag '{tag_id}' name to: '{name_stripped}'")
        try:
            # 1. Call API
            updated_data = await self.api.update_tag(tag_id=tag_id, name=name_stripped)

            if not updated_data:
                log.error(f"API call to update tag '{tag_id}' did not return data.")
                return None  # Or raise

            # 2. Update local cache
            # Use model_validate with update=True or manually set attributes
            existing_tag.model_validate(updated_data, update=True)
            log.info(f"Successfully updated and cached tag: {existing_tag}")
            # self.dm.save_tags() # Optional: Save updated cache
            return existing_tag

        except ValueError as ve:
            log.error(f"Input validation error updating tag: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to update tag '{tag_id}': {e}")
            raise

    async def delete_tag(self, tag_id: str) -> bool:
        """Deletes a tag via the API and removes it from the local cache.

        Args:
            tag_id: The ID of the tag to delete.

        Returns:
            True if deletion was successful (both API and local), False otherwise.

        Raises:
            ValueError: If tag not found or is a challenge tag.
            HabiticaAPIError: If the API call fails.
        """
        tag_list = self.get_tags()
        if not tag_list:
            log.error(f"Cannot delete tag '{tag_id}': TagList not loaded.")
            raise ValueError("Tag list not available.")

        existing_tag = tag_list.get_by_id(tag_id)
        if not existing_tag:
            log.error(f"Tag deletion failed: Tag ID '{tag_id}' not found.")
            raise ValueError(f"Tag with ID '{tag_id}' not found.")
        if existing_tag.challenge:
            log.error(f"Tag deletion failed: Cannot delete challenge tag '{tag_id}'.")
            raise ValueError("Cannot delete challenge tags.")

        log.info(f"Attempting to delete tag '{tag_id}' ({existing_tag.name})...")
        try:
            # 1. Call API
            api_success = await self.api.delete_tag(tag_id=tag_id)

            if not api_success:
                # API call failed or returned False
                log.error(f"API call to delete tag '{tag_id}' failed.")
                return False  # Indicate failure

            # 2. Remove from local cache
            removed_local = tag_list.remove_tag(tag_id)  # Assumes TagList has remove_tag
            if removed_local:
                log.info(f"Successfully deleted tag '{tag_id}' from API and cache.")
                # self.dm.save_tags() # Optional: Save updated cache
                return True
            else:
                # This shouldn't happen if get_by_id worked, but log just in case
                log.warning(f"API deletion successful, but failed to remove tag '{tag_id}' from local cache.")
                return False  # Indicate partial success/failure

        except ValueError as ve:
            log.error(f"Input validation error deleting tag: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to delete tag '{tag_id}': {e}")
            raise

    async def reorder_tag(self, tag_id: str, position: int) -> bool:
        """Reorders a tag via the API and updates the local cache order.

        Args:
            tag_id: The ID of the tag to move.
            position: The desired 0-based index.

        Returns:
            True if reordering was successful, False otherwise.

        Raises:
            ValueError: If tag not found or position is invalid.
            HabiticaAPIError: If the API call fails.
        """
        tag_list = self.get_tags()
        if not tag_list:
            log.error(f"Cannot reorder tag '{tag_id}': TagList not loaded.")
            raise ValueError("Tag list not available.")

        if not isinstance(position, int) or position < 0:
            log.error("Tag reorder failed: Position must be a non-negative integer.")
            raise ValueError("Position must be a non-negative integer index.")

        # Check if tag exists locally before calling API
        if tag_id not in tag_list:
            log.error(f"Tag reorder failed: Tag ID '{tag_id}' not found locally.")
            raise ValueError(f"Tag with ID '{tag_id}' not found.")

        log.info(f"Attempting to reorder tag '{tag_id}' to position {position}...")
        try:
            # 1. Call API first
            api_success = await self.api.reorder_tag(tag_id=tag_id, position=position)

            if not api_success:
                log.error(f"API call to reorder tag '{tag_id}' failed.")
                return False

            # 2. Reorder locally
            # Assumes TagList has a reorder_tags method that handles updating internal positions
            local_reorder_success = tag_list.reorder_tags(tag_id, position)

            if local_reorder_success:
                log.info(f"Successfully reordered tag '{tag_id}' in API and cache.")
                # self.dm.save_tags() # Optional: Save updated cache
                return True
            else:
                log.warning(f"API reorder successful, but failed to reorder tag '{tag_id}' locally.")
                # Maybe force a full refresh of tags here?
                # await self.dm.load_tags(force_refresh=True)
                return False  # Indicate local state might be inconsistent

        except ValueError as ve:
            log.error(f"Input validation error reordering tag: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to reorder tag '{tag_id}': {e}")
            raise
