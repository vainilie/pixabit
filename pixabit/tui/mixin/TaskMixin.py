class TaskType(str, Enum):
    HABIT = "habit"
    DAILY = "daily"
    TODO = "todo"
    REWARD = "reward"


class ScoreDirection(str, Enum):
    UP = "up"
    DOWN = "down"


class Attribute(str, Enum):
    STRENGTH = "str"
    INTELLIGENCE = "int"
    CONSTITUTION = "con"
    PERCEPTION = "per"


class TaskData(BaseModel):
    text: str
    type: TaskType
    notes: str | None = None
    priority: float | None = 1.0
    attribute: Attribute | None = None
    tags: list[str] | None = None


class TaskMixin:

    # Métodos para tareas
    async def get_tasks(
        self, task_type: TaskType | None = None
    ) -> List[dict[str, Any]]:
        """Get user tasks, optionally filtered by type.

        Args:
            task_type: Optional task type filter

        Returns:
            List of tasks
        """
        params = {"type": task_type.value} if task_type else None
        result = await self.get("tasks/user", params=params)
        return result if isinstance(result, list) else []

    async def create_task(
        self, task: TaskData | dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new task.

        Args:
            task: Task data (either as Pydantic model or dict)

        Returns:
            Created task data

        Raises:
            ValueError: If required fields are missing
        """
        # Convert to dict if it's a Pydantic model
        data = task.model_dump() if hasattr(task, "model_dump") else task

        # Validate essential fields
        if not data.get("text") or not data.get("type"):
            raise ValueError("Task data requires 'text' and 'type'.")

        result = await self.post("tasks/user", data=data)
        return self._ensure_type(result, dict) or {}

    async def update_task(
        self, task_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing task.

        Args:
            task_id: ID of the task to update
            data: Fields to update

        Returns:
            Updated task data

        Raises:
            ValueError: If task_id is empty
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")

        result = await self.put(f"tasks/{task_id}", data=data)
        return self._ensure_type(result, dict) or {}

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task.

        Args:
            task_id: ID of the task to delete

        Returns:
            True if deletion was successful

        Raises:
            ValueError: If task_id is empty
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")

        result = await self.delete(f"tasks/{task_id}")
        return result is None

    async def score_task(
        self,
        task_id: str,
        direction: ScoreDirection | str = ScoreDirection.UP,
    ) -> dict[str, Any]:
        """Score (complete or undo) a task.

        Args:
            task_id: ID of the task to score
            direction: "up" to complete, "down" to undo/fail

        Returns:
            Score response data including drops, damage, etc.

        Raises:
            ValueError: If task_id is empty or direction is invalid
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")

        # Handle string or enum
        if isinstance(direction, str):
            if direction not in ["up", "down"]:
                raise ValueError("Direction must be 'up' or 'down'.")
            dir_value = direction
        else:
            dir_value = direction.value

        result = await self.post(f"tasks/{task_id}/score/{dir_value}")
        return self._ensure_type(result, dict) or {}

    async def set_attribute(
        self, task_id: str, attribute: Attribute | str
    ) -> dict[str, Any]:
        """Set the attribute for a task.

        Args:
            task_id: ID of the task
            attribute: Attribute to set

        Returns:
            Updated task data

        Raises:
            ValueError: If attribute is invalid
        """
        # Handle string or enum
        if isinstance(attribute, str):
            if attribute not in ["str", "int", "con", "per"]:
                raise ValueError(
                    "Invalid attribute. Must be 'str', 'int', 'con', or 'per'."
                )
            attr_value = attribute
        else:
            attr_value = attribute.value

        return await self.update_task(task_id, {"attribute": attr_value})

    async def move_task_to_position(
        self, task_id: str, position: int
    ) -> List[str]:
        """Move a task to a specific position.

        Args:
            task_id: ID of the task to move
            position: New position index

        Returns:
            Updated task order

        Raises:
            ValueError: If task_id is empty or position is not an integer
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")

        if not isinstance(position, int):
            raise ValueError("Position must be an integer.")

        result = await self.post(f"tasks/{task_id}/move/to/{position}")
        return result if isinstance(result, list) else []

    async def clear_completed_todos(self) -> bool:
        """Clear (delete) all completed todo tasks.

        Returns:
            True if successful
        """
        result = await self.post("tasks/clearCompletedTodos")
        return result is None

    async def add_tag_to_task(
        self, task_id: str, tag_id: str
    ) -> Optional[Dict[str, Any]]:
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    async def delete_tag_from_task(
        self, task_id: str, tag_id: str
    ) -> Optional[Dict[str, Any]]:
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = await self.delete(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    async def add_checklist_item(
        self, task_id: str, text: str
    ) -> Optional[Dict[str, Any]]:
        if not task_id or not text:
            raise ValueError("task_id and text cannot be empty.")
        result = await self.post(
            f"/tasks/{task_id}/checklist", data={"text": text}
        )
        return result if isinstance(result, dict) else None

    async def update_checklist_item(
        self, task_id: str, item_id: str, text: str
    ) -> Optional[Dict[str, Any]]:
        if not task_id or not item_id or text is None:
            raise ValueError("task_id, item_id, and text required.")
        result = await self.put(
            f"/tasks/{task_id}/checklist/{item_id}", data={"text": text}
        )
        return result if isinstance(result, dict) else None

    async def delete_checklist_item(
        self, task_id: str, item_id: str
    ) -> Optional[Dict[str, Any]]:
        if not task_id or not item_id:
            raise ValueError("task_id and item_id required.")
        result = await self.delete(f"/tasks/{task_id}/checklist/{item_id}")
        return result if isinstance(result, dict) else None

    async def score_checklist_item(
        self, task_id: str, item_id: str
    ) -> Optional[Dict[str, Any]]:
        if not task_id or not item_id:
            raise ValueError("task_id and item_id required.")
        result = await self.post(f"/tasks/{task_id}/checklist/{item_id}/score")
        return result if isinstance(result, dict) else None
