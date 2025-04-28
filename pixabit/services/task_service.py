# pixabit/services/task_service.py

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pixabit.helpers._logger import log
from pixabit.models.task import AnyTask, TaskData  # Import specific model if needed

if TYPE_CHECKING:
    from pixabit.api.client import HabiticaClient
    from pixabit.api.mixin.task_mixin import ScoreDirection  # Import Enum
    from pixabit.models.task import TaskList  # The container/manager model

    from .data_manager import DataManager


class TaskService:
    """Service layer for interacting with Habitica Tasks.
    Coordinates API calls and updates the local data managed by DataManager.
    """

    def __init__(self, api_client: HabiticaClient, data_manager: DataManager):
        """Initializes the TaskService.

        Args:
            api_client: The Habitica API client instance.
            data_manager: The data manager instance holding live data models.
        """
        self.api = api_client
        self.dm = data_manager
        log.debug("TaskService initialized.")

    # --- Read Operations (Synchronous - access cached data) ---

    def get_tasks(self) -> TaskList | None:
        """Returns the cached TaskList instance from the DataManager."""
        if not self.dm.tasks:
            log.warning("Attempted to get tasks, but TaskList is not loaded in DataManager.")
        return self.dm.tasks

    def get_task_by_id(self, task_id: str) -> AnyTask | None:
        """Gets a specific task by its ID from the cached TaskList."""
        task_list = self.get_tasks()
        if task_list:
            return task_list.get_by_id(task_id)
        return None

    def get_tasks_by_type(self, task_type: Literal[habit, daily, todo, reward]) -> list[AnyTask]:
        """Gets tasks of a specific type from the cached TaskList."""
        task_list = self.get_tasks()
        if task_list:
            # TaskList should provide direct access by type
            return task_list.get_tasks_by_type(task_type)
        return []

    # --- Write Operations (Asynchronous) ---

    async def create_task(self, task_input: TaskData | dict[str, Any]) -> AnyTask | None:
        """Creates a new task via the API and adds it to the local TaskList.

        Args:
            task_input: Task data (Pydantic model TaskData or dictionary).

        Returns:
            The created Task object (Habit, Daily, Todo, Reward), or None if failed.

        Raises:
            ValueError: If task_input is invalid.
            HabiticaAPIError: If the API call fails.
        """
        log.info("Attempting to create task...")
        try:
            # 1. Call API
            # create_task expects dict or TaskData model, handles validation
            task_data: dict[str, Any] | None = await self.api.create_task(task=task_input)

            if not task_data:
                log.error("API call to create task did not return data.")
                return None

            # 2. Add to local cache using TaskList's method
            task_list = self.get_tasks()
            if task_list:
                # add_task should validate the raw dict and create the correct subclass
                new_task_instance = task_list.add_task(task_data)
                if new_task_instance:
                    log.info(f"Successfully created and cached task: {new_task_instance}")
                    # self.dm.save_tasks() # Optional: Save updated cache
                    return new_task_instance
                else:
                    log.error("Failed to add created task to local TaskList.")
                    # Task created in API but not locally? Inconsistent state.
                    # Maybe return the raw dict? Or None? Let's return None for now.
                    return None
            else:
                log.error("Cannot add created task: TaskList not loaded in DataManager.")
                return None  # Local cache not available

        except ValueError as ve:
            log.error(f"Input validation error creating task: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to create task: {e}")
            raise

    async def update_task(self, task_id: str, update_data: dict[str, Any]) -> AnyTask | None:
        """Updates an existing task via the API and updates the local cache.

        Args:
            task_id: The ID of the task to update.
            update_data: Dictionary containing fields to update.

        Returns:
            The updated Task object, or None if update failed.

        Raises:
            ValueError: If update_data is empty or task not found.
            HabiticaAPIError: If the API call fails.
        """
        if not update_data:
            log.error("Task update failed: update_data cannot be empty.")
            raise ValueError("Update data cannot be empty.")

        task_list = self.get_tasks()
        if not task_list or task_id not in task_list:
            log.error(f"Cannot update task '{task_id}': Task not found or TaskList not loaded.")
            raise ValueError(f"Task with ID '{task_id}' not found locally.")

        log.info(f"Attempting to update task '{task_id}'...")
        try:
            # 1. Call API
            updated_data_from_api = await self.api.update_task(task_id=task_id, data=update_data)

            if not updated_data_from_api:
                log.error(f"API call to update task '{task_id}' did not return data.")
                return None

            # 2. Update local cache using TaskList's method
            # edit_task should handle validation and updating the existing instance
            updated_task_instance = task_list.edit_task(task_id, updated_data_from_api)

            if updated_task_instance:
                log.info(f"Successfully updated and cached task: {updated_task_instance}")
                # self.dm.save_tasks() # Optional
                return updated_task_instance
            else:
                log.error(f"Failed to update task '{task_id}' in local TaskList.")
                return None

        except ValueError as ve:
            log.error(f"Input validation error updating task: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to update task '{task_id}': {e}")
            raise

    async def delete_task(self, task_id: str) -> bool:
        """Deletes a task via the API and removes it from the local cache.

        Args:
            task_id: The ID of the task to delete.

        Returns:
            True if deletion was successful (both API and local), False otherwise.

        Raises:
            ValueError: If task not found.
            HabiticaAPIError: If the API call fails.
        """
        task_list = self.get_tasks()
        if not task_list or task_id not in task_list:
            log.error(f"Cannot delete task '{task_id}': Task not found or TaskList not loaded.")
            raise ValueError(f"Task with ID '{task_id}' not found locally.")

        log.info(f"Attempting to delete task '{task_id}'...")
        try:
            # 1. Call API
            api_success = await self.api.delete_task(task_id=task_id)

            if not api_success:
                log.error(f"API call to delete task '{task_id}' failed.")
                return False

            # 2. Remove from local cache using TaskList's method
            deleted_task = task_list.delete_task(task_id)

            if deleted_task:
                log.info(f"Successfully deleted task '{task_id}' from API and cache.")
                # self.dm.save_tasks() # Optional
                return True
            else:
                log.warning(f"API deletion successful, but failed to remove task '{task_id}' from local cache.")
                return False

        except ValueError as ve:
            log.error(f"Input validation error deleting task: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to delete task '{task_id}': {e}")
            raise

    async def score_task(self, task_id: str, direction: ScoreDirection | Literal[up, down]) -> dict[str, Any] | None:
        """Scores a task (up or down) via the API, updates local user stats,
        and updates the local task state.

        Args:
            task_id: The ID of the task to score.
            direction: "up" or "down" (or ScoreDirection enum).

        Returns:
            The score result dictionary from the API (containing deltas), or None on failure.

        Raises:
            ValueError: If task or user not found.
            HabiticaAPIError: If the API call fails.
        """
        task_list = self.get_tasks()
        user = self.dm.user
        if not task_list or task_id not in task_list:
            log.error(f"Cannot score task '{task_id}': Task not found or TaskList not loaded.")
            raise ValueError(f"Task with ID '{task_id}' not found locally.")
        if not user:
            log.error(f"Cannot score task '{task_id}': User data not loaded.")
            raise ValueError("User data not loaded.")

        task = task_list.get_by_id(task_id)  # Get the specific task instance

        log.info(f"Attempting to score task '{task_id}' direction '{direction}'...")
        try:
            # 1. Call API
            score_result = await self.api.score_task(task_id=task_id, direction=direction)

            if not score_result:
                log.error(f"API call to score task '{task_id}' failed or returned no data.")
                return None

            # 2. Update local User stats based on score_result deltas
            # This is complex: need to parse score_result keys (+hp, -mp, etc.)
            # and apply them carefully to user.stats and user.party.quest.progress if applicable
            delta = score_result.get("delta", 0)  # Habitica's main score delta

            # --- Apply Deltas to User (Simplified Example) ---
            # A more robust implementation would parse all possible delta keys
            user.stats.hp = max(0, user.stats.hp + score_result.get("hp", 0))  # Ensure HP doesn't go below 0
            user.stats.mp += score_result.get("mp", 0)
            user.stats.exp += score_result.get("exp", 0)
            user.stats.gp += score_result.get("gp", 0)
            new_lvl = score_result.get("lvl")
            if new_lvl and new_lvl > user.stats.lvl:
                user.stats.lvl = new_lvl
                # Need to update maxHP/MP, expToNextLevel etc. based on level up
                # Maybe trigger a full user re-processing?
                log.info(f"User leveled up to {new_lvl}!")
                # Re-fetch user data might be simplest after level up
                # await self.dm.load_user(force_refresh=True) ? Or recalculate locally?

            log.debug(f"Applied score deltas to user: {score_result}")

            # 3. Update local Task state
            update_payload = {}
            if task.type == "habit":
                if direction == "up":
                    update_payload["counterUp"] = task.counter_up + 1
                else:  # direction == "down"
                    update_payload["counterDown"] = task.counter_down + 1
            elif task.type in ["daily", "todo"]:
                # Scoring 'up' completes it, scoring 'down' uncompletes it? Check API behavior.
                # Assume 'up' means complete, 'down' means uncomplete for score_task endpoint
                update_payload["completed"] = direction == "up"
                if direction == "up":
                    # TODO: Add completedDate? API might set this implicitly.
                    update_payload["dateCompleted"] = datetime.now(timezone.utc).isoformat()
                else:
                    update_payload["dateCompleted"] = None

            # Edit the task locally with the derived state changes
            if update_payload:
                updated_task = task_list.edit_task(task_id, update_payload)
                if updated_task:
                    log.debug(f"Updated local task state after scoring: {updated_task}")
                else:
                    log.warning(f"Failed to update local task state for {task_id} after scoring.")
            else:
                # For rewards, scoring consumes GP, no task state change usually needed
                log.debug(f"Scored reward '{task_id}'. No local task state change applied.")

            # 4. Return API score result
            return score_result

        except ValueError as ve:
            log.error(f"Input validation error scoring task: {ve}")
            raise
        except Exception as e:
            log.exception(f"Failed to score task '{task_id}': {e}")
            raise

    async def clear_completed_todos(self) -> bool:
        """Clears completed Todos via API and removes them locally.

        Returns:
            True if successful, False otherwise.
        """
        log.info("Attempting to clear completed Todos...")
        task_list = self.get_tasks()
        if not task_list:
            log.error("Cannot clear Todos: TaskList not loaded.")
            return False

        try:
            # 1. Call API
            api_success = await self.api.clear_completed_todos()
            if not api_success:
                log.error("API call to clear completed Todos failed.")
                return False

            # 2. Remove completed Todos locally
            ids_to_remove = [task.id for task in task_list.get_tasks_by_type("todo") if task.completed]
            log.debug(f"Found {len(ids_to_remove)} completed Todos locally to remove.")
            removed_count = 0
            for task_id in ids_to_remove:
                if task_list.delete_task(task_id):
                    removed_count += 1

            log.info(f"Cleared completed Todos. API success: True. Local removed: {removed_count}/{len(ids_to_remove)}.")
            # self.dm.save_tasks() # Optional
            return True

        except Exception as e:
            log.exception("Failed to clear completed Todos: {e}")
            raise

    # --- Tagging/Checklist Methods (Example: Add Tag) ---

    async def add_tag_to_task(self, task_id: str, tag_id: str) -> AnyTask | None:
        """Adds a tag to a task via API and updates local cache."""
        task_list = self.get_tasks()
        tag_list = self.dm.tags
        if not task_list or task_id not in task_list:
            raise ValueError(f"Task '{task_id}' not found locally.")
        if not tag_list or tag_id not in tag_list:
            raise ValueError(f"Tag '{tag_id}' not found locally.")

        log.info(f"Attempting to add tag '{tag_id}' to task '{task_id}'...")
        try:
            # 1. Call API
            updated_task_data = await self.api.add_tag_to_task(task_id=task_id, tag_id=tag_id)
            if not updated_task_data:
                log.error("API call to add tag to task returned no data.")
                return None

            # 2. Update local task
            # The API response should contain the updated task data including the new tag list
            updated_task = task_list.edit_task(task_id, updated_task_data)
            if updated_task:
                log.info(f"Successfully added tag '{tag_id}' to task '{task_id}'.")
                # self.dm.save_tasks() # Optional
                return updated_task
            else:
                log.error(f"Failed to update local task '{task_id}' after adding tag.")
                return None

        except Exception as e:
            log.exception(f"Failed to add tag '{tag_id}' to task '{task_id}': {e}")
            raise

    async def delete_tag_from_task(self, task_id: str, tag_id: str) -> AnyTask | None:
        """Removes a tag from a task via API and updates local cache."""
        task_list = self.get_tasks()
        tag_list = self.dm.tags  # Assuming TagList holds tag info
        if not task_list or task_id not in task_list:
            raise ValueError(f"Task '{task_id}' not found locally.")
        # No need to check if tag exists, API handles non-existent tag removal gracefully?
        # existing_task = task_list.get_by_id(task_id)
        # if tag_id not in existing_task.tags_id:
        #     log.warning(f"Tag '{tag_id}' not found on task '{task_id}' locally, attempting API removal anyway.")
        #     # return existing_task # Or proceed? Proceed for now.

        log.info(f"Attempting to remove tag '{tag_id}' from task '{task_id}'...")
        try:
            # 1. Call API
            updated_task_data = await self.api.delete_tag_from_task(task_id=task_id, tag_id=tag_id)
            if not updated_task_data:
                log.error("API call to remove tag from task returned no data.")
                return None

            # 2. Update local task
            updated_task = task_list.edit_task(task_id, updated_task_data)
            if updated_task:
                log.info(f"Successfully removed tag '{tag_id}' from task '{task_id}'.")
                # self.dm.save_tasks() # Optional
                return updated_task
            else:
                log.error(f"Failed to update local task '{task_id}' after removing tag.")
                return None

        except Exception as e:
            log.exception(f"Failed to remove tag '{tag_id}' from task '{task_id}': {e}")
            raise

    # --- Checklist Methods (Example: Add Item) ---
    async def add_checklist_item(self, task_id: str, text: str) -> AnyTask | None:
        """Adds a checklist item via API and updates local cache."""
        if not text.strip():
            raise ValueError("Checklist item text cannot be empty.")

        task_list = self.get_tasks()
        if not task_list or task_id not in task_list:
            raise ValueError(f"Task '{task_id}' not found locally.")

        existing_task = task_list.get_by_id(task_id)
        if existing_task.type not in ["daily", "todo"]:
            raise ValueError("Checklists are only supported for Dailies and Todos.")

        log.info(f"Attempting to add checklist item to task '{task_id}'...")
        try:
            # 1. Call API
            updated_task_data = await self.api.add_checklist_item(task_id=task_id, text=text)
            if not updated_task_data:
                log.error("API call to add checklist item returned no data.")
                return None

            # 2. Update local task
            updated_task = task_list.edit_task(task_id, updated_task_data)
            if updated_task:
                log.info(f"Successfully added checklist item to task '{task_id}'.")
                # self.dm.save_tasks() # Optional
                return updated_task
            else:
                log.error(f"Failed to update local task '{task_id}' after adding checklist item.")
                return None

        except Exception as e:
            log.exception(f"Failed to add checklist item to task '{task_id}': {e}")
            raise

    # Add other checklist/tagging methods following the same pattern...
    # score_checklist_item, delete_checklist_item, update_checklist_item
