# pixabit/services/challenge_service.py

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pixabit.helpers._logger import log
from pixabit.models.challenge import Challenge  # Assuming ChallengeList has add/remove methods
from pixabit.models.task import Task  # For create_challenge_task

if TYPE_CHECKING:
    from pixabit.api.client import HabiticaClient
    from pixabit.api.mixin.challenge_mixin import ChallengeKeepOption, TaskKeepOption
    from pixabit.models.challenge import ChallengeList

    from .data_manager import DataManager


class ChallengeService:
    """Service layer for interacting with Habitica Challenges.
    Coordinates API calls and updates the local data managed by DataManager.
    """

    def __init__(self, api_client: HabiticaClient, data_manager: DataManager):
        """Initializes the ChallengeService.

        Args:
            api_client: The Habitica API client instance.
            data_manager: The data manager instance holding live data models.
        """
        self.api = api_client
        self.dm = data_manager
        log.debug("ChallengeService initialized.")

    # --- Read Operations (Synchronous - access cached data) ---

    def get_challenges(self) -> ChallengeList | None:
        """Returns the cached ChallengeList instance from the DataManager."""
        if not self.dm.challenges:
            log.warning("Attempted to get challenges, but ChallengeList is not loaded in DataManager.")
        return self.dm.challenges

    def get_challenge_by_id(self, challenge_id: str) -> Challenge | None:
        """Gets a specific challenge by its ID from the cached ChallengeList."""
        challenge_list = self.get_challenges()
        if challenge_list:
            # Assumes ChallengeList has get_by_id
            return challenge_list.get_by_id(challenge_id)
        return None

    # --- Write Operations (Asynchronous) ---

    async def create_challenge(self, data: dict[str, Any]) -> Challenge | None:
        """Creates a new challenge via the API and adds it to the local ChallengeList.

        Args:
            data: Dictionary containing challenge data (requires 'name', 'shortName', 'group').

        Returns:
            The created Challenge object, or None if creation failed.

        Raises:
            ValueError: If required fields are missing.
            HabiticaAPIError: If the API call fails.
        """
        # Basic validation - API mixin already does this, but good practice here too
        if not data.get("name") or not data.get("shortName") or not data.get("group"):
            log.error("Challenge creation failed: Missing required fields (name, shortName, group).")
            raise ValueError("Challenge creation requires 'name', 'shortName', and 'group' ID.")

        log.info(f"Attempting to create challenge '{data.get('name')}'...")
        try:
            # 1. Call API
            challenge_data = await self.api.create_challenge(data=data)
            if not challenge_data:
                log.error("API call to create challenge did not return data.")
                return None

            # 2. Add to local cache
            challenge_list = self.get_challenges()
            if challenge_list:
                # Create Challenge instance - Use from_raw_data with context?
                # Need to determine context (user ID) for ownership etc.
                user_id_context = self.dm.user.id if self.dm.user else None
                context = {"current_user_id": user_id_context}
                temp_list = ChallengeList.from_raw_data([challenge_data], context=context)
                new_challenge = temp_list.challenges[0] if temp_list.challenges else None

                if new_challenge:
                    # TODO: ChallengeList needs an add_challenge method similar to TaskList
                    # For now, append directly (less safe)
                    challenge_list.challenges.append(new_challenge)
                    log.info(f"Successfully created and cached challenge: {new_challenge}")
                    # self.dm.save_challenges() # If exists
                    return new_challenge
                else:
                    log.error("Failed to validate/create Challenge object from API response.")
                    return None
            else:
                log.error("Cannot add created challenge: ChallengeList not loaded.")
                return None

        except ValueError as ve:
            log.error(f"Input validation error creating challenge: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to create challenge: {e}")
            raise

    async def update_challenge(self, challenge_id: str, data: dict[str, Any]) -> Challenge | None:
        """Updates an existing challenge via the API and updates the local cache.

        Args:
            challenge_id: The ID of the challenge to update.
            data: Dictionary containing the fields to update.

        Returns:
            The updated Challenge object, or None if update failed.

        Raises:
            ValueError: If challenge not found or data is empty.
            HabiticaAPIError: If the API call fails.
        """
        if not data:
            raise ValueError("Update data cannot be empty.")

        challenge_list = self.get_challenges()
        if not challenge_list:
            raise ValueError("Challenge list not available.")

        existing_challenge = challenge_list.get_by_id(challenge_id)
        if not existing_challenge:
            raise ValueError(f"Challenge with ID '{challenge_id}' not found.")

        log.info(f"Attempting to update challenge '{challenge_id}'...")
        try:
            # 1. Call API
            updated_data = await self.api.update_challenge(challenge_id=challenge_id, data=data)
            if not updated_data:
                log.error(f"API call to update challenge '{challenge_id}' did not return data.")
                return None

            # 2. Update local cache
            # Use model_validate with update=True
            existing_challenge.model_validate(updated_data, update=True)
            log.info(f"Successfully updated and cached challenge: {existing_challenge}")
            # self.dm.save_challenges() # If exists
            return existing_challenge

        except ValueError as ve:
            log.error(f"Input validation error updating challenge: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to update challenge '{challenge_id}': {e}")
            raise

    async def leave_challenge(self, challenge_id: str, keep: ChallengeKeepOption | Literal[keep - all, remove - all]) -> bool:
        """Leaves a challenge via API and updates the local cache.

        Args:
            challenge_id: The ID of the challenge to leave.
            keep: Option whether to keep tasks.

        Returns:
            True if successful, False otherwise.

        Raises:
            ValueError: If challenge not found.
            HabiticaAPIError: If the API call fails.
        """
        challenge_list = self.get_challenges()
        if not challenge_list:
            raise ValueError("Challenge list not available.")

        existing_challenge = challenge_list.get_by_id(challenge_id)
        if not existing_challenge:
            raise ValueError(f"Challenge with ID '{challenge_id}' not found.")

        log.info(f"Attempting to leave challenge '{challenge_id}' (keep={keep})...")
        try:
            # 1. Call API
            api_success = await self.api.leave_challenge(challenge_id=challenge_id, keep=keep)
            if not api_success:
                log.error(f"API call to leave challenge '{challenge_id}' failed.")
                return False

            # 2. Update local cache
            # Set 'joined' status to False, maybe remove challenge if list is only 'joined'?
            existing_challenge.joined = False
            log.info(f"Successfully left challenge '{challenge_id}' via API. Updated local joined status.")
            # self.dm.save_challenges() # If exists
            return True

        except ValueError as ve:
            log.error(f"Input validation error leaving challenge: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to leave challenge '{challenge_id}': {e}")
            raise

    async def create_challenge_task(self, challenge_id: str, task_data: dict[str, Any]) -> Task | None:
        """Creates a task within a challenge via API and updates local caches.

        Args:
            challenge_id: ID of the challenge to add the task to.
            task_data: Dictionary containing task data (requires 'text', 'type').

        Returns:
            The created Task object, or None if failed.

        Raises:
            ValueError: If input data is invalid or challenge not found.
            HabiticaAPIError: If the API call fails.
        """
        # Validate inputs (API mixin also validates)
        if not task_data.get("text") or not task_data.get("type"):
            raise ValueError("Task data requires 'text' and 'type'.")
        if task_data["type"] not in {"habit", "daily", "todo", "reward"}:
            raise ValueError("Invalid task type.")

        challenge_list = self.get_challenges()
        task_list = self.dm.tasks
        if not challenge_list:
            raise ValueError("Challenge list not available.")
        if not task_list:
            raise ValueError("Task list not available.")

        challenge = challenge_list.get_by_id(challenge_id)
        if not challenge:
            raise ValueError(f"Challenge with ID '{challenge_id}' not found.")

        log.info(f"Attempting to create task in challenge '{challenge_id}'...")
        try:
            # 1. Call API
            new_task_data = await self.api.create_challenge_task(challenge_id=challenge_id, task_data=task_data)
            if not new_task_data:
                log.error("API call to create challenge task returned no data.")
                return None

            # 2. Add task to main TaskList cache
            new_task_instance = task_list.add_task(new_task_data)
            if not new_task_instance:
                log.error("Failed to add created challenge task to local TaskList.")
                # API created task, but local cache failed. Inconsistent.
                return None

            # 3. Add task reference to Challenge's task list
            # Ensure challenge tasks are initialized
            if not isinstance(challenge.tasks, list):
                challenge.tasks = []
            # Avoid duplicates if already added via some other means
            if new_task_instance not in challenge.tasks:
                challenge.tasks.append(new_task_instance)

            log.info(f"Successfully created task '{new_task_instance.id}' in challenge '{challenge_id}' and cached.")
            # self.dm.save_tasks() # Optional
            # self.dm.save_challenges() # Optional (to save the updated link)
            return new_task_instance

        except ValueError as ve:
            log.error(f"Input validation error creating challenge task: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to create challenge task for challenge '{challenge_id}': {e}")
            raise

    # Add other methods like clone_challenge, unlink_task_from_challenge etc.
    # following the pattern: Call API, update local ChallengeList/TaskList cache.
