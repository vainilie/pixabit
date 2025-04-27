# pixabit/habitica/mixin/challenge_mixin.py

# SECTION: MODULE DOCSTRING
"""Mixin class providing Habitica Challenge related API methods."""

# SECTION: IMPORTS
import asyncio
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, cast

# Use TYPE_CHECKING to avoid circular import issues if API uses models
if TYPE_CHECKING:
    from pixabit.api.habitica_api import HabiticaAPI

# SECTION: ENUMS


# ENUM: TaskKeepOption
class TaskKeepOption(str, Enum):
    """Options for keeping tasks when unlinking."""

    KEEP = "keep"
    REMOVE = "remove"


# ENUM: ChallengeKeepOption
class ChallengeKeepOption(str, Enum):
    """Options for keeping challenge tasks when leaving."""

    KEEP_ALL = "keep-all"
    REMOVE_ALL = "remove-all"


# SECTION: MIXIN CLASS


# KLASS: ChallengesMixin
class ChallengesMixin:
    """Mixin containing methods for interacting with Habitica Challenges."""

    # Assert self is HabiticaAPI for type hinting internal methods like self.get
    if TYPE_CHECKING:
        _request: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        get: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        post: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        put: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        delete: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]

    # FUNC: get_challenges
    async def get_challenges(self, member_only: bool = True, page: int = 0) -> list[dict[str, Any]]:
        """Fetches a single page of user challenges.

        Args:
            member_only: If True, only return challenges the user is a member of.
            page: The page number to retrieve (0-indexed).

        Returns:
            A list of challenge dictionaries for the requested page, or empty list.
        """
        params: dict[str, Any] = {"page": page}
        # API uses string "true"/"false" for boolean params
        params["member"] = "true" if member_only else "false"
        result = await self.get("/challenges/user", params=params)
        # Ensure result is a list, return empty list otherwise
        return cast(list[dict[str, Any]], result) if isinstance(result, list) else []

    # FUNC: get_all_challenges_paginated (Renamed for clarity)
    async def get_all_challenges_paginated(self, member_only: bool = True, page_delay: float = 0.5) -> list[dict[str, Any]]:
        """Fetches all challenges the user is associated with, handling pagination.

        Args:
            member_only: If True, only return challenges user is a member of.
            page_delay: Delay in seconds between fetching pages to respect rate limits.

        Returns:
            A list containing all challenge dictionaries across all pages.
        """
        all_challenges: list[dict[str, Any]] = []
        current_page = 0
        while True:
            page_data = await self.get_challenges(member_only=member_only, page=current_page)
            if not page_data:  # Empty list indicates end of pagination
                break
            all_challenges.extend(page_data)
            current_page += 1
            await asyncio.sleep(page_delay)  # Prevent hitting rate limits too quickly
        return all_challenges

    # FUNC: get_challenge_tasks
    async def get_challenge_tasks(self, challenge_id: str) -> list[dict[str, Any]]:
        """Fetches the tasks associated with a specific challenge.

        Args:
            challenge_id: The ID of the challenge.

        Returns:
            A list of task dictionaries within the challenge, or empty list.

        Raises:
            ValueError: If challenge_id is empty.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        result = await self.get(f"/tasks/challenge/{challenge_id}")
        return cast(list[dict[str, Any]], result) if isinstance(result, list) else []

    # FUNC: leave_challenge
    async def leave_challenge(
        self,
        challenge_id: str,
        keep: ChallengeKeepOption | Literal["keep-all", "remove-all"] = ChallengeKeepOption.KEEP_ALL,
    ) -> bool:
        """Leaves a specific challenge.

        Args:
            challenge_id: The ID of the challenge to leave.
            keep: Option whether to keep tasks ('keep-all', 'remove-all', or enum).

        Returns:
            True if the operation was successful (API returned no data), False otherwise.

        Raises:
            ValueError: If challenge_id is empty or keep option is invalid.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")

        keep_value = keep.value if isinstance(keep, Enum) else keep
        if keep_value not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")

        result = await self.post(f"/challenges/{challenge_id}/leave", params={"keep": keep_value})
        # Successful leave often returns 204 No Content (result is None)
        return result is None

    # FUNC: unlink_task_from_challenge
    async def unlink_task_from_challenge(
        self,
        task_id: str,
        keep: TaskKeepOption | Literal["keep", "remove"] = TaskKeepOption.KEEP,
    ) -> bool:
        """Unlinks a specific task from its challenge.

        Args:
            task_id: The ID of the task to unlink.
            keep: Option whether to keep the task as a personal task ('keep', 'remove', or enum).

        Returns:
            True if the operation was successful (API returned no data), False otherwise.

        Raises:
            ValueError: If task_id is empty or keep option is invalid.
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")

        keep_value = keep.value if isinstance(keep, Enum) else keep
        if keep_value not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")

        result = await self.post(f"/tasks/unlink-one/{task_id}", params={"keep": keep_value})
        return result is None

    # FUNC: unlink_all_challenge_tasks
    async def unlink_all_challenge_tasks(
        self,
        challenge_id: str,
        keep: ChallengeKeepOption | Literal["keep-all", "remove-all"] = ChallengeKeepOption.KEEP_ALL,
    ) -> bool:
        """Unlinks all tasks belonging to a specific challenge.

        Args:
            challenge_id: The ID of the challenge whose tasks should be unlinked.
            keep: Option whether to keep tasks ('keep-all', 'remove-all', or enum).

        Returns:
            True if the operation was successful (API returned no data), False otherwise.

        Raises:
            ValueError: If challenge_id is empty or keep option is invalid.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")

        keep_value = keep.value if isinstance(keep, Enum) else keep
        if keep_value not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")

        result = await self.post(f"/tasks/unlink-all/{challenge_id}", params={"keep": keep_value})
        return result is None

    # FUNC: create_challenge
    async def create_challenge(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """Creates a new challenge.

        Args:
            data: A dictionary containing challenge data (requires 'name', 'shortName', 'group').

        Returns:
            A dictionary representing the newly created challenge, or None on failure.

        Raises:
            ValueError: If required fields ('name', 'shortName', 'group') are missing.
        """
        if not data.get("name") or not data.get("shortName") or not data.get("group"):  # Group ID is required
            raise ValueError("Challenge creation requires at least 'name', 'shortName', and 'group' ID.")
        result = await self.post("/challenges", data=data)
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: clone_challenge
    async def clone_challenge(self, challenge_id: str) -> dict[str, Any] | None:
        """Clones an existing challenge.

        Args:
            challenge_id: The ID of the challenge to clone.

        Returns:
            A dictionary representing the cloned challenge, or None on failure.

        Raises:
            ValueError: If challenge_id is empty.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        result = await self.post(f"/challenges/{challenge_id}/clone")
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: update_challenge
    async def update_challenge(self, challenge_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Updates an existing challenge.

        Args:
            challenge_id: The ID of the challenge to update.
            data: A dictionary containing the fields to update.

        Returns:
            A dictionary representing the updated challenge, or None on failure.

        Raises:
            ValueError: If challenge_id or data is empty.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if not data:
            raise ValueError("Update data cannot be empty.")
        result = await self.put(f"/challenges/{challenge_id}", data=data)
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: create_challenge_task
    async def create_challenge_task(self, challenge_id: str, task_data: dict[str, Any]) -> dict[str, Any] | None:
        """Creates a new task within a specific challenge.

        Args:
            challenge_id: The ID of the challenge to add the task to.
            task_data: A dictionary containing task data (requires 'text', 'type').

        Returns:
            A dictionary representing the newly created task, or None on failure.

        Raises:
            ValueError: If challenge_id is empty, required task fields are missing, or type is invalid.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if not task_data.get("text") or not task_data.get("type"):
            raise ValueError("Task data requires 'text' and 'type'.")
        if task_data["type"] not in {"habit", "daily", "todo", "reward"}:
            raise ValueError("Invalid task type. Must be 'habit', 'daily', 'todo', or 'reward'.")

        result = await self.post(f"/tasks/challenge/{challenge_id}", data=task_data)
        return cast(dict[str, Any], result) if isinstance(result, dict) else None
