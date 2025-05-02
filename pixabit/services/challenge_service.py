from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from pixabit.helpers._logger import log
from pixabit.models.challenge import Challenge, ChallengeList
from pixabit.models.task import Task, TaskList

if TYPE_CHECKING:
    from pixabit.api.client import HabiticaClient
    from pixabit.api.mixin.challenge_mixin import ChallengeKeepOption, TaskKeepOption
    from pixabit.models.challenge import Challenge, ChallengeList
    from pixabit.models.task import Task, TaskList

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

    def get_cached_challenges(self) -> ChallengeList | None:
        """Returns the cached ChallengeList instance from the DataManager.

        Returns:
            The cached ChallengeList or None if not loaded.
        """
        if not self.dm.challenges:
            log.warning("Attempted to get challenges, but ChallengeList is not loaded in DataManager.")
        return self.dm.challenges

    def get_challenge_by_id(self, challenge_id: str) -> Challenge | None:
        """Gets a specific challenge by its ID from the cached ChallengeList.

        Args:
            challenge_id: The ID of the challenge to retrieve.

        Returns:
            The Challenge object if found, otherwise None.
        """
        challenge_list = self.get_cached_challenges()
        if challenge_list:
            return challenge_list.get_by_id(challenge_id)
        return None

    # --- Direct API Operations (Asynchronous) ---

    async def fetch_challenges(self, member_only: bool = False, page: int = 0) -> ChallengeList | None:
        """Fetches challenges directly from the API without relying on cache.

        Args:
            member_only: If True, only return challenges the user is a member of.
            page: Page number for paginated results.

        Returns:
            A ChallengeList containing the challenges or None if the API call failed.
        """
        log.info(f"Fetching challenges from API (member_only={member_only}, page={page})...")
        try:
            challenges_data = await self.api.get_challenges(member_only=member_only, page=page)
            if not challenges_data:
                log.warning("API returned no challenge data.")
                return None

            # Create validation context for the challenge list
            user_id_context = self.dm.user.id if self.dm.user else None
            validation_context = {"current_user_id": user_id_context}

            # Create challenge list from API data
            challenge_list = ChallengeList.from_raw_data(challenges_data, context=validation_context)
            for challenge in challenge_list:
                if challenge.id in self.dm.user.challenges:
                    challenge.joined = True
                else:
                    challenge.joined = False
            log.info(f"Successfully fetched {len(challenge_list.challenges) if challenge_list else 0} challenges from API.")
            return challenge_list
        except Exception as e:
            log.exception(f"Failed to fetch challenges from API: {e}")
            return None

    async def fetch_challenge_details(self, challenge_id: str) -> Challenge | None:
        """Fetches detailed information about a specific challenge from the API.

        Args:
            challenge_id: The ID of the challenge to fetch.

        Returns:
            The Challenge object with full details if successful, None otherwise.
        """
        log.info(f"Fetching challenge details for '{challenge_id}' from API...")
        try:
            challenge_data = await self.api.get_challenge(challenge_id=challenge_id)
            if not challenge_data:
                log.warning(f"API returned no data for challenge '{challenge_id}'.")
                return None

            # Create validation context
            user_id_context = self.dm.user.id if self.dm.user else None
            validation_context = {"current_user_id": user_id_context}

            # Create a temporary list to parse the challenge
            temp_list = ChallengeList.from_raw_data([challenge_data], context=validation_context)
            challenge = temp_list.challenges[0] if temp_list and temp_list.challenges else None

            if challenge:
                log.info(f"Successfully fetched challenge details for '{challenge_id}'.")
                return challenge
            else:
                log.error(f"Failed to parse challenge data for '{challenge_id}'.")
                return None
        except Exception as e:
            log.exception(f"Failed to fetch challenge details for '{challenge_id}': {e}")
            return None

    async def fetch_challenge_tasks(self, challenge_id: str) -> List[Task] | None:
        """Fetches tasks belonging to a specific challenge from the API.

        Args:
            challenge_id: The ID of the challenge to fetch tasks for.

        Returns:
            A list of Task objects if successful, None otherwise.
        """
        log.info(f"Fetching tasks for challenge '{challenge_id}' from API...")
        try:
            tasks_data = await self.api.get_challenge_tasks(challenge_id=challenge_id)
            if not tasks_data:
                log.warning(f"API returned no tasks for challenge '{challenge_id}'.")
                return None

            # We need to parse raw task data into Task objects
            task_list = TaskList.from_raw_api_list(tasks_data)
            if not task_list:
                log.error("Task list not available in DataManager.")
                return None

            # Create Task objects from raw data
            # tasks = []
            # for task_data in tasks_data:
            #     task = task_list.add_task(task_data, update_existing=True)
            #     if task:
            #         tasks.append(task)

            # log.info(f"Successfully fetched {len(tasks)} tasks for challenge '{challenge_id}'.")
            return task_list
        except Exception as e:
            log.exception(f"Failed to fetch tasks for challenge '{challenge_id}': {e}")
            return None

    # --- Write Operations (Asynchronous) ---

    async def join_challenge(self, challenge_id: str) -> bool:
        """Joins a challenge via API and updates the local cache.

        Args:
            challenge_id: The ID of the challenge to join.

        Returns:
            True if successful, False otherwise.

        Raises:
            ValueError: If challenge_id is invalid.
            HabiticaAPIError: If the API call fails.
        """
        log.info(f"Attempting to join challenge '{challenge_id}'...")
        try:
            # 1. Call API
            api_success = await self.api.join_challenge(challenge_id=challenge_id)
            if not api_success:
                log.error(f"API call to join challenge '{challenge_id}' failed.")
                return False

            # 2. Update local cache if challenge exists
            challenge_list = self.get_cached_challenges()
            if challenge_list:
                challenge = challenge_list.get_by_id(challenge_id)
                if challenge:
                    challenge.joined = True
                    log.info(f"Updated local cache: challenge '{challenge_id}' is now joined.")
                else:
                    log.info(f"Challenge '{challenge_id}' not found in local cache. Will be updated on next fetch.")

            # 3. Fetch and merge challenge tasks into user tasks
            tasks = await self.fetch_challenge_tasks(challenge_id)
            if tasks:
                log.info(f"Added {len(tasks)} tasks from challenge '{challenge_id}' to local task list.")

            return True
        except ValueError as ve:
            log.error(f"Input validation error joining challenge: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to join challenge '{challenge_id}': {e}")
            raise

    async def leave_challenge(self, challenge_id: str, keep: str) -> bool:
        """Leaves a challenge via API and updates the local cache.

        Args:
            challenge_id: The ID of the challenge to leave.
            keep: Option whether to keep tasks ("keep-all" or "remove-all").

        Returns:
            True if successful, False otherwise.

        Raises:
            ValueError: If challenge not found.
            HabiticaAPIError: If the API call fails.
        """
        challenge_list = self.get_cached_challenges()
        if not challenge_list:
            log.warning("Challenge list not available, proceeding with API call only.")
        else:
            existing_challenge = challenge_list.get_by_id(challenge_id)
            if not existing_challenge:
                log.warning(f"Challenge with ID '{challenge_id}' not found in cache.")

        log.info(f"Attempting to leave challenge '{challenge_id}' (keep={keep})...")
        try:
            # 1. Call API
            api_success = await self.api.leave_challenge(challenge_id=challenge_id, keep=keep)
            if not api_success:
                log.error(f"API call to leave challenge '{challenge_id}' failed.")
                return False

            # 2. Update local cache if challenge exists
            if challenge_list:
                existing_challenge = challenge_list.get_by_id(challenge_id)
                if existing_challenge:
                    existing_challenge.joined = False
                    log.info(f"Updated local cache: challenge '{challenge_id}' is now left.")

            # 3. Remove challenge tasks from task list if keep is "remove-all"
            if keep == "remove-all" and self.dm.tasks:
                # This would require a method to identify and remove challenge tasks
                # Consider adding this functionality to the TaskList class
                log.info(f"Tasks from challenge '{challenge_id}' should be removed from local task list.")

            return True
        except ValueError as ve:
            log.error(f"Input validation error leaving challenge: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to leave challenge '{challenge_id}': {e}")
            raise

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
            challenge_list = self.get_cached_challenges()
            if challenge_list:
                # Create Challenge instance with context
                user_id_context = self.dm.user.id if self.dm.user else None
                context = {"current_user_id": user_id_context}
                temp_list = ChallengeList.from_raw_data([challenge_data], context=context)
                new_challenge = temp_list.challenges[0] if temp_list.challenges else None

                if new_challenge:
                    challenge_list.add_challenge(new_challenge)  # Assumes implementation of add_challenge
                    log.info(f"Successfully created and cached challenge: {new_challenge}")
                    return new_challenge
                else:
                    log.error("Failed to validate/create Challenge object from API response.")
                    return None
            else:
                log.warning("Cannot add created challenge to cache: ChallengeList not loaded.")
                # Still return the created challenge even if we couldn't cache it
                return Challenge.model_validate(challenge_data)

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

        challenge_list = self.get_cached_challenges()
        existing_challenge = None
        if challenge_list:
            existing_challenge = challenge_list.get_by_id(challenge_id)
            if not existing_challenge:
                log.warning(f"Challenge with ID '{challenge_id}' not found in local cache.")

        log.info(f"Attempting to update challenge '{challenge_id}'...")
        try:
            # 1. Call API
            updated_data = await self.api.update_challenge(challenge_id=challenge_id, data=data)
            if not updated_data:
                log.error(f"API call to update challenge '{challenge_id}' did not return data.")
                return None

            # 2. Update local cache if challenge exists
            if existing_challenge:
                existing_challenge.model_validate(updated_data, update=True)
                log.info(f"Successfully updated cached challenge: {existing_challenge}")
                return existing_challenge
            else:
                # Create a new Challenge object with the updated data
                user_id_context = self.dm.user.id if self.dm.user else None
                context = {"current_user_id": user_id_context}
                temp_list = ChallengeList.from_raw_data([updated_data], context=context)
                new_challenge = temp_list.challenges[0] if temp_list.challenges else None

                if new_challenge and challenge_list:
                    challenge_list.add_challenge(new_challenge)  # Assumes implementation of add_challenge
                    log.info(f"Added updated challenge to cache: {new_challenge}")

                return new_challenge

        except ValueError as ve:
            log.error(f"Input validation error updating challenge: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to update challenge '{challenge_id}': {e}")
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

        challenge_list = self.get_cached_challenges()
        task_list = self.dm.tasks

        if not task_list:
            raise ValueError("Task list not available.")

        challenge = None
        if challenge_list:
            challenge = challenge_list.get_by_id(challenge_id)
            if not challenge:
                log.warning(f"Challenge with ID '{challenge_id}' not found in local cache.")

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

            # 3. Add task reference to Challenge's task list if challenge exists in cache
            if challenge:
                # Ensure challenge tasks are initialized
                if not hasattr(challenge, "tasks") or not challenge.tasks:
                    challenge.tasks = []
                # Avoid duplicates if already added via some other means
                if new_task_instance.id not in [task.id for task in challenge.tasks]:
                    challenge.tasks.append(new_task_instance)

            log.info(f"Successfully created task '{new_task_instance.id}' in challenge '{challenge_id}' and cached.")
            return new_task_instance

        except ValueError as ve:
            log.error(f"Input validation error creating challenge task: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to create challenge task for challenge '{challenge_id}': {e}")
            raise

    # --- Helper Methods ---

    async def refresh_challenges(self, member_only: bool = False) -> ChallengeList | None:
        """Refreshes the locally cached ChallengeList from the API.

        Args:
            member_only: If True, only fetch challenges the user is a member of.

        Returns:
            The updated ChallengeList or None if the API call failed.
        """
        log.info(f"Refreshing challenges (member_only={member_only})...")
        try:
            # Fetch challenges from API
            challenges_data = await self.api.get_challenges(member_only=member_only)
            if not challenges_data:
                log.warning("API returned no challenge data.")
                return None

            # Create validation context
            user_id_context = self.dm.user.id if self.dm.user else None
            validation_context = {"current_user_id": user_id_context}

            # Create challenge list from API data
            challenge_list = ChallengeList.from_raw_data(challenges_data, context=validation_context)

            # Update data manager's challenge list
            self.dm.challenges = challenge_list
            log.info(f"Successfully refreshed {len(challenge_list.challenges) if challenge_list else 0} challenges in cache.")

            return challenge_list
        except Exception as e:
            log.exception(f"Failed to refresh challenges: {e}")
            return None
