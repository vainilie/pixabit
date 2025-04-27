# pixabit/habitica/mixin/task_mixin.py

# SECTION: MODULE DOCSTRING
"""Mixin class providing Habitica Task related API methods."""

# SECTION: IMPORTS
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, cast

# Pydantic is used for the TaskData input model
from pydantic import BaseModel

# Use TYPE_CHECKING to avoid circular import issues if API uses models
if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine  # For hinting self methods

    from pixabit.api.habitica_api import HabiticaAPI, HabiticaApiSuccessData

# SECTION: ENUMS


# ENUM: TaskType
class TaskType(str, Enum):
    """Enumeration for Habitica task types."""

    HABIT = "habit"
    DAILY = "daily"
    TODO = "todo"
    REWARD = "reward"


# ENUM: ScoreDirection
class ScoreDirection(str, Enum):
    """Enumeration for task scoring direction."""

    UP = "up"
    DOWN = "down"


# ENUM: Attribute
class Attribute(str, Enum):
    """Enumeration for Habitica character attributes."""

    STRENGTH = "str"
    INTELLIGENCE = "int"
    CONSTITUTION = "con"
    PERCEPTION = "per"


# SECTION: INPUT DATA MODEL


# KLASS: TaskData (Input Model)
class TaskData(BaseModel):
    """Pydantic model representing data for creating a new task."""

    text: str
    type: TaskType
    notes: str | None = None
    priority: float = 1.0  # Default priority
    attribute: Attribute | None = None  # Maps to str, int, con, per
    tags: list[str] | None = None  # List of tag UUIDs

    model_config = {"use_enum_values": True}  # Ensure enum values are used in serialization


# SECTION: MIXIN CLASS


# KLASS: TasksMixin
class TasksMixin:
    """Mixin containing methods for interacting with Habitica Tasks."""

    # Assert self is HabiticaAPI for type hinting internal methods
    if TYPE_CHECKING:
        _request: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        get: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        post: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        put: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]
        delete: Callable[..., Coroutine[Any, Any, HabiticaApiSuccessData]]

    # --- Core Task Methods ---

    # FUNC: get_tasks
    async def get_tasks(
        self,
        task_type: TaskType | Literal["habits", "dailys", "todos", "rewards"] | None = None,
    ) -> list[dict[str, Any]]:
        """Get user tasks, optionally filtered by type.

        Args:
            task_type: Optional task type filter (enum or string). Note Habitica API
                       uses plural for filtering (e.g., 'dailys').

        Returns:
            A list of task dictionaries, or an empty list.
        """
        params: dict[str, Any] | None = None
        if task_type:
            # API uses plural form for type filtering
            type_value = task_type.value if isinstance(task_type, Enum) else task_type
            # Adjust to plural if needed, handle potential inconsistencies
            api_type_filter = type_value + "s" if type_value in ["daily", "todo", "reward"] else type_value
            params = {"type": api_type_filter}

        # Endpoint is /tasks/user
        result = await self.get("tasks/user", params=params)
        return cast(list[dict[str, Any]], result) if isinstance(result, list) else []

    # FUNC: create_task
    async def create_task(self, task: TaskData | dict[str, Any]) -> dict[str, Any] | None:
        """Create a new task.

        Args:
            task: Task data (either as TaskData Pydantic model or dict).

        Returns:
            A dictionary representing the created task, or None on failure.

        Raises:
            ValueError: If required fields ('text', 'type') are missing in the input data.
        """
        # Convert Pydantic model to dict if necessary
        if isinstance(task, TaskData):
            # Use model_dump for Pydantic v2+, ensure enums become values
            data = task.model_dump(mode="json")
        elif isinstance(task, dict):
            data = task
        else:
            raise TypeError("task argument must be a TaskData model or a dictionary.")

        # Validate essential fields before sending
        if not data.get("text") or not data.get("type"):
            raise ValueError("Task data requires 'text' and 'type'.")
        # Ensure type is a valid string if passed as dict
        if data["type"] not in TaskType._value2member_map_:
            raise ValueError(f"Invalid task type: {data['type']}")

        # Endpoint is /tasks/user
        result = await self.post("tasks/user", data=data)
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: update_task
    async def update_task(self, task_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Update an existing task.

        Args:
            task_id: The ID (_id) of the task to update.
            data: Dictionary containing fields to update.

        Returns:
            A dictionary representing the updated task, or None on failure.

        Raises:
            ValueError: If task_id is empty or data is empty.
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if not data:
            raise ValueError("Update data cannot be empty.")

        # Endpoint is /tasks/:taskId
        result = await self.put(f"tasks/{task_id}", data=data)
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: delete_task
    async def delete_task(self, task_id: str) -> bool:
        """Delete a task.

        Args:
            task_id: The ID (_id) of the task to delete.

        Returns:
            True if deletion was successful (API returned no data), False otherwise.

        Raises:
            ValueError: If task_id is empty.
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")

        # Endpoint is /tasks/:taskId
        result = await self.delete(f"tasks/{task_id}")
        # Successful DELETE often returns 204 No Content (result is None)
        return result is None

    # FUNC: score_task
    async def score_task(
        self,
        task_id: str,
        direction: ScoreDirection | Literal["up", "down"] = ScoreDirection.UP,
    ) -> dict[str, Any] | None:
        """Score (complete or undo/fail) a task.

        Args:
            task_id: The ID (_id) of the task to score.
            direction: "up" to complete/check positive, "down" to undo/fail/check negative (enum or string).

        Returns:
            Score response data including drops, damage, stat changes etc., or None on failure.

        Raises:
            ValueError: If task_id is empty or direction is invalid.
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")

        # Get the string value from enum or validate the string
        if isinstance(direction, ScoreDirection):
            dir_value = direction.value
        elif isinstance(direction, str) and direction in ["up", "down"]:
            dir_value = direction
        else:
            raise ValueError("Direction must be 'up' or 'down'.")

        # Endpoint is /tasks/:taskId/score/:direction
        result = await self.post(f"tasks/{task_id}/score/{dir_value}")
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # --- Helper Task Methods ---

    # FUNC: set_task_attribute (Helper using update_task)
    async def set_task_attribute(
        self,
        task_id: str,
        attribute: Attribute | Literal["str", "int", "con", "per"],
    ) -> dict[str, Any] | None:
        """Set the primary attribute for a task (influences stat gain on completion).

        Args:
            task_id: The ID (_id) of the task.
            attribute: The attribute to set (enum or string 'str', 'int', 'con', 'per').

        Returns:
            The updated task data dictionary, or None on failure.

        Raises:
            ValueError: If attribute is invalid.
        """
        # Get the string value from enum or validate the string
        if isinstance(attribute, Attribute):
            attr_value = attribute.value
        elif isinstance(attribute, str) and attribute in [
            "str",
            "int",
            "con",
            "per",
        ]:
            attr_value = attribute
        else:
            raise ValueError("Invalid attribute. Must be 'str', 'int', 'con', or 'per'.")

        return await self.update_task(task_id, {"attribute": attr_value})

    # FUNC: move_task_to_position
    async def move_task_to_position(self, task_id: str, position: int) -> list[str] | None:
        """Move a task to a specific position within its list (e.g., Todos).

        Args:
            task_id: The ID (_id) of the task to move.
            position: The desired 0-based index.

        Returns:
            A list of task IDs in the new order, or None on failure.

        Raises:
            ValueError: If task_id is empty or position is not an integer.
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if not isinstance(position, int):
            raise ValueError("Position must be an integer.")

        # Endpoint: /tasks/:taskId/move/to/:position
        result = await self.post(f"tasks/{task_id}/move/to/{position}")
        # API returns the new task order [taskId1, taskId2, ...]
        return cast(list[str], result) if isinstance(result, list) else None

    # FUNC: clear_completed_todos
    async def clear_completed_todos(self) -> bool:
        """Clear (delete) all completed todo tasks for the user.

        Returns:
            True if successful (API returned no data), False otherwise.
        """
        # Endpoint: /tasks/clearCompletedTodos
        result = await self.post("tasks/clearCompletedTodos")
        return result is None

    # --- Tagging Methods ---

    # FUNC: add_tag_to_task
    async def add_tag_to_task(self, task_id: str, tag_id: str) -> dict[str, Any] | None:
        """Adds a tag to a specific task.

        Args:
            task_id: The ID (_id) of the task.
            tag_id: The UUID of the tag to add.

        Returns:
            The updated task data dictionary, or None on failure.

        Raises:
            ValueError: If task_id or tag_id is empty.
        """
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        # Endpoint: /tasks/:taskId/tags/:tagId
        result = await self.post(f"/tasks/{task_id}/tags/{tag_id}")
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: delete_tag_from_task
    async def delete_tag_from_task(self, task_id: str, tag_id: str) -> dict[str, Any] | None:
        """Removes a tag from a specific task.

        Args:
            task_id: The ID (_id) of the task.
            tag_id: The UUID of the tag to remove.

        Returns:
            The updated task data dictionary (likely without the tag), or None on failure.

        Raises:
            ValueError: If task_id or tag_id is empty.
        """
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        # Endpoint: /tasks/:taskId/tags/:tagId
        result = await self.delete(f"/tasks/{task_id}/tags/{tag_id}")
        # API returns the updated task after tag removal
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # --- Checklist Methods ---

    # FUNC: add_checklist_item
    async def add_checklist_item(self, task_id: str, text: str) -> dict[str, Any] | None:
        """Adds a checklist item to a Daily or Todo task.

        Args:
            task_id: The ID (_id) of the task.
            text: The text content of the checklist item.

        Returns:
            The updated task data dictionary (with the new checklist item), or None on failure.

        Raises:
            ValueError: If task_id or text is empty.
        """
        if not task_id or not text.strip():
            raise ValueError("task_id and text cannot be empty.")
        # Endpoint: /tasks/:taskId/checklist
        result = await self.post(f"/tasks/{task_id}/checklist", data={"text": text.strip()})
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: update_checklist_item
    async def update_checklist_item(self, task_id: str, item_id: str, text: str) -> dict[str, Any] | None:
        """Updates the text of an existing checklist item.

        Args:
            task_id: The ID (_id) of the parent task.
            item_id: The ID of the checklist item to update.
            text: The new text content for the item.

        Returns:
            The updated task data dictionary, or None on failure.

        Raises:
            ValueError: If task_id, item_id, or text is empty/missing.
        """
        if not task_id or not item_id or not text.strip():  # Check text is not just whitespace
            raise ValueError("task_id, item_id, and text are required.")
        # Endpoint: /tasks/:taskId/checklist/:itemId
        result = await self.put(f"/tasks/{task_id}/checklist/{item_id}", data={"text": text.strip()})
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: delete_checklist_item
    async def delete_checklist_item(self, task_id: str, item_id: str) -> dict[str, Any] | None:
        """Deletes a checklist item from a task.

        Args:
            task_id: The ID (_id) of the parent task.
            item_id: The ID of the checklist item to delete.

        Returns:
            The updated task data dictionary (without the checklist item), or None on failure.

        Raises:
            ValueError: If task_id or item_id is empty.
        """
        if not task_id or not item_id:
            raise ValueError("task_id and item_id are required.")
        # Endpoint: /tasks/:taskId/checklist/:itemId
        result = await self.delete(f"/tasks/{task_id}/checklist/{item_id}")
        return cast(dict[str, Any], result) if isinstance(result, dict) else None

    # FUNC: score_checklist_item
    async def score_checklist_item(self, task_id: str, item_id: str) -> dict[str, Any] | None:
        """Scores (marks as complete/incomplete) a checklist item.

        Args:
            task_id: The ID (_id) of the parent task.
            item_id: The ID of the checklist item to score.

        Returns:
            The updated task data dictionary (with the checklist item's status changed), or None on failure.

        Raises:
            ValueError: If task_id or item_id is empty.
        """
        if not task_id or not item_id:
            raise ValueError("task_id and item_id are required.")
        # Endpoint: /tasks/:taskId/checklist/:itemId/score
        result = await self.post(f"/tasks/{task_id}/checklist/{item_id}/score")
        return cast(dict[str, Any], result) if isinstance(result, dict) else None
