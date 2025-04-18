# pixabit/models/task.py

# SECTION: MODULE DOCSTRING
"""Defines data model classes for representing Habitica Tasks and related entities.

Includes:
- `ChecklistItem`: Represents an item within a task's checklist.
- `ChallengeData`: Holds information about a challenge linked to a task.
- `Task`: Base class for all task types.
- `Habit`, `Daily`, `Todo`, `Reward`: Subclasses for specific task types.
- `TaskList`: A container class to manage a collection of Task objects,
  providing processing initialization and filtering capabilities.
"""

# SECTION: IMPORTS
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union  # Keep Dict/List, add Union

import emoji_data_python

# Local Imports (assuming utils and models are siblings or configured in path)
try:
    from ..utils.dates import convert_timestamp_to_utc

    # Tag models might be needed if linking Tag objects instead of just names/IDs
    # from .tag import Tag, TagList
except ImportError:
    print("Warning: Using placeholder convert_timestamp_to_utc in task.py.")

    def convert_timestamp_to_utc(ts: Any) -> Optional[datetime]:  # noqa: D103
        return None  # type: ignore


# SECTION: HELPER DATA CLASSES


# KLASS: ChecklistItem
class ChecklistItem:
    """Represents a single item within a Task's checklist."""

    # FUNC: __init__
    def __init__(self, item_data: Dict[str, Any]):
        """Initializes a ChecklistItem object from API data.

        Args:
            item_data: A dictionary representing the checklist item from the API.

        Raises:
            TypeError: If item_data is not a dictionary.
        """
        if not isinstance(item_data, dict):
            raise TypeError("item_data must be a dictionary.")
        self.id: Optional[str] = item_data.get("id")
        _text = item_data.get("text", "")
        self.text: str = (
            emoji_data_python.replace_colons(_text) if _text else ""
        )
        self.completed: bool = item_data.get("completed", False)
        # Optional: Add position if available/needed: self.position = item_data.get('position')

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        status = "[X]" if self.completed else "[ ]"
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"ChecklistItem(id={self.id}, status='{status}', text='{text_preview}')"


# KLASS: ChallengeData
class ChallengeData:
    """Represents data about a challenge associated with a task."""

    # FUNC: __init__
    def __init__(self, challenge_data: Optional[Dict[str, Any]]):
        """Initializes ChallengeData from the 'challenge' sub-object of a task.

        Args:
            challenge_data: The dictionary containing challenge link details, or None.
        """
        data = challenge_data if isinstance(challenge_data, dict) else {}

        self.task_id: Optional[str] = data.get(
            "taskId"
        )  # ID of the task *within* the challenge
        self.id: Optional[str] = data.get("id")  # ID of the challenge itself
        _short_name = data.get("shortName")
        self.name: Optional[str] = (
            emoji_data_python.replace_colons(_short_name)
            if _short_name
            else None
        )  # Often challenge shortName

        # Process 'broken' status - can indicate task or challenge issues
        broken_raw: Optional[str] = data.get("broken")
        self.broken_status: Optional[str] = None  # e.g., 'task', 'challenge'
        self.is_broken: bool = bool(
            broken_raw
        )  # True if any broken status exists

        if broken_raw:
            if broken_raw in ("TASK_DELETED", "CHALLENGE_TASK_NOT_FOUND"):
                self.broken_status = "task"
            elif broken_raw in (
                "CHALLENGE_DELETED",
                "UNSUBSCRIBED",
                "CHALLENGE_CLOSED",
            ):
                self.broken_status = "challenge"
            else:
                self.broken_status = "unknown"  # Store unknown broken types

        # Optional: Add group info if the API ever includes it here (unlikely in task challenge object)
        # self.group_id: Optional[str] = data.get("groupId")

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        status = f", broken='{self.broken_status}'" if self.is_broken else ""
        return f"ChallengeData(id={self.id}, name='{self.name}'{status})"


# SECTION: BASE TASK CLASS


# KLASS: Task
class Task:
    """Base representation of a Habitica Task.

    Holds common attributes shared by all task types. Specific task types
    inherit from this and add their unique attributes.
    """

    # FUNC: __init__
    def __init__(self, task_data: Dict[str, Any]):
        """Initializes the base Task object from API data dictionary.

        Args:
            task_data: A dictionary containing the raw task data from the API.

        Raises:
            TypeError: If task_data is not a dictionary.
            ValueError: If task data is missing essential '_id'.
        """
        if not isinstance(task_data, dict):
            raise TypeError("task_data must be a dictionary.")
        if not task_data.get("_id"):
            # ID is essential for referencing the task
            raise ValueError(
                f"Task data is missing '_id': {task_data.get('text', 'N/A')}"
            )

        self.id: str = task_data["_id"]  # Should exist based on check above
        self.alias: Optional[str] = task_data.get("alias")
        self.user_id: Optional[str] = task_data.get(
            "userId"
        )  # ID of the user who owns this task

        _text = task_data.get("text", "")
        self.text: str = (
            emoji_data_python.replace_colons(_text) if _text else ""
        )
        _notes = task_data.get("notes", "")
        self.notes: str = (
            emoji_data_python.replace_colons(_notes) if _notes else ""
        )

        self.type: Optional[str] = task_data.get(
            "type"
        )  # 'habit', 'daily', 'todo', 'reward'
        self.tags: List[str] = task_data.get("tags", [])  # List of Tag UUIDs
        self.value: float = float(
            task_data.get("value", 0.0)
        )  # Task difficulty/value
        self.priority: float = float(
            task_data.get("priority", 1.0)
        )  # Task priority (difficulty multiplier)
        self.attribute: str = task_data.get(
            "attribute", "str"
        )  # Default 'str', others: 'int', 'con', 'per'

        # Position: This is tricky. API doesn't return absolute position.
        # It might be calculated relative to type during processing. Initialize as None.
        self.position: Optional[int] = None

        # Dates (converted to UTC datetime objects)
        self.created_at: Optional[datetime] = convert_timestamp_to_utc(
            task_data.get("createdAt")
        )
        self.updated_at: Optional[datetime] = convert_timestamp_to_utc(
            task_data.get("updatedAt")
        )

        # Other common fields
        self.by_habitica: bool = task_data.get(
            "byHabitica", False
        )  # System-created task?
        self.reminders: List[Dict[str, Any]] = task_data.get(
            "reminders", []
        )  # List of reminder objects

        # Challenge Integration (using ChallengeData class)
        challenge_info = task_data.get(
            "challenge"
        )  # Can be {} or dict with data
        self.challenge: Optional[ChallengeData] = (
            ChallengeData(challenge_info) if challenge_info else None
        )

        # Standardized Checklist placeholder (populated by specific types if applicable)
        self.checklist: List[ChecklistItem] = []

        # --- Processed/Calculated Fields (Populated by TaskProcessor) ---
        # These are initialized here but set externally after instantiation.
        self.tag_names: List[str] = []  # Resolved tag names
        self.value_color: str = "neutral"  # Semantic color based on value
        self._status: str = (
            "unknown"  # Calculated status (e.g., 'due', 'red', 'success')
        )
        self.damage_user: Optional[float] = None  # Potential HP damage to user
        self.damage_party: Optional[float] = (
            None  # Potential damage to party/boss
        )
        # Optional: Store linked Tag objects if needed later
        # self.origin_tag: Optional[Tag] = None
        # self.attribute_tag: Optional[Tag] = None
        # self.area_tag: Optional[Tag] = None

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"{self.__class__.__name__}(id='{self.id}', text='{text_preview}', type='{self.type}')"

    # FUNC: update_from_processed (DEPRECATED - Handled by TaskProcessor)
    # This function seems redundant if TaskProcessor directly modifies the instance attributes.
    # Keeping it commented out for reference, but recommend removing it.
    # def update_from_processed(self, processed_data: Dict[str, Any]):
    #     """Updates task instance with fields calculated during processing."""
    #     # self.tag_names = processed_data.get("tag_names", self.tags) # Prefer direct assignment in processor
    #     # self.value_color = processed_data.get("value_color", "neutral")
    #     # self._status = processed_data.get("_status", "unknown")
    #     # self.damage_user = processed_data.get("damage_to_user")
    #     # self.damage_party = processed_data.get("damage_to_party")
    #     # ... other processed fields ...
    #     pass


# SECTION: TASK SUBCLASSES


# KLASS: Habit
class Habit(Task):
    """Represents a Habit task, inheriting from Task."""

    # FUNC: __init__
    def __init__(self, task_data: Dict[str, Any]):
        """Initializes the Habit object, calling parent init and adding habit-specific fields."""
        super().__init__(task_data)
        self.type = "habit"  # Override type
        self.up: bool = task_data.get(
            "up", True
        )  # Can score positively? (Defaults true)
        self.down: bool = task_data.get(
            "down", True
        )  # Can score negatively? (Defaults true)
        self.counter_up: int = int(
            task_data.get("counterUp", 0)
        )  # Positive clicks count
        self.counter_down: int = int(
            task_data.get("counterDown", 0)
        )  # Negative clicks count
        self.frequency: str = task_data.get(
            "frequency", "daily"
        )  # Not typically used for Habits? API includes it.
        # History might contain recent scoring events, could be large
        self.history: List[Dict[str, Any]] = task_data.get("history", [])

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Developer-friendly representation including counters."""
        up_str = f"⬆️{self.counter_up}" if self.up else ""
        down_str = f"⬇️{self.counter_down}" if self.down else ""
        sep = " / " if self.up and self.down else ""
        counters = (
            f"{up_str}{sep}{down_str}" if up_str or down_str else "No Counters"
        )
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"Habit(id='{self.id}', text='{text_preview}', counters='{counters}')"


# KLASS: Todo
class Todo(Task):
    """Represents a To-Do task, inheriting from Task."""

    # FUNC: __init__
    def __init__(self, task_data: Dict[str, Any]):
        """Initializes the Todo object, calling parent init and adding to-do-specific fields."""
        super().__init__(task_data)
        self.type = "todo"  # Override type
        self.completed: bool = task_data.get(
            "completed", False
        )  # Is the To-Do marked complete?
        # Date the To-Do was completed
        self.completed_date: Optional[datetime] = convert_timestamp_to_utc(
            task_data.get("dateCompleted")
        )
        # Due date for the To-Do
        self.due_date: Optional[datetime] = convert_timestamp_to_utc(
            task_data.get("date")
        )
        # Preference for collapsing checklist display
        self.collapse_checklist: bool = task_data.get(
            "collapseChecklist", False
        )

        # Populate checklist from data using ChecklistItem class
        self.checklist: List[ChecklistItem] = [
            ChecklistItem(item)
            for item in task_data.get("checklist", [])
            if isinstance(item, dict)
        ]

    # Property to check if due date is passed (read-only check)
    @property
    def is_past_due(self) -> bool:
        """Checks if the To-Do is past its due date AND not completed."""
        # This property just performs the check based on current state.
        # The actual status ('red', 'due', 'done') should be set by TaskProcessor in self._status.
        if self.completed or not self.due_date:
            return False
        # Ensure comparison happens with timezone-aware datetime
        # Assume self.due_date is already UTC from conversion
        return self.due_date < datetime.now(timezone.utc)

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Developer-friendly representation including completion status and due date."""
        status_char = "[X]" if self.completed else "[ ]"
        due_str = (
            f", due={self.due_date.strftime('%Y-%m-%d')}"
            if self.due_date
            else ""
        )
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"Todo(id='{self.id}', status='{status_char}', text='{text_preview}'{due_str})"


# KLASS: Daily
class Daily(Task):
    """Represents a Daily task, inheriting from Task."""

    # FUNC: __init__
    def __init__(self, task_data: Dict[str, Any]):
        """Initializes the Daily object, calling parent init and adding daily-specific fields."""
        super().__init__(task_data)
        self.type = "daily"  # Override type
        self.completed: bool = task_data.get(
            "completed", False
        )  # Completed for the current period?
        self.is_due: bool = task_data.get(
            "isDue", False
        )  # Is it due today based on schedule and CDS?
        self.streak: int = int(
            task_data.get("streak", 0)
        )  # Current completion streak
        # Preference for collapsing checklist display
        self.collapse_checklist: bool = task_data.get(
            "collapseChecklist", False
        )

        # Populate checklist from data using ChecklistItem class
        self.checklist: List[ChecklistItem] = [
            ChecklistItem(item)
            for item in task_data.get("checklist", [])
            if isinstance(item, dict)
        ]

        # Scheduling properties
        self.frequency: str = task_data.get(
            "frequency", "weekly"
        )  # 'daily', 'weekly', 'monthly', 'yearly'
        self.every_x: int = int(
            task_data.get("everyX", 1)
        )  # e.g., every 3 days
        # Date the daily first became active
        self.start_date: Optional[datetime] = convert_timestamp_to_utc(
            task_data.get("startDate")
        )
        # For monthly frequency (days of month)
        self.days_of_month: List[int] = task_data.get("daysOfMonth", [])
        # For monthly frequency (weeks of month)
        self.weeks_of_month: List[int] = task_data.get("weeksOfMonth", [])
        # For weekly frequency {m:T, t:T, w:T, th:T, f:T, s:T, su:T}
        self.repeat: Dict[str, bool] = task_data.get("repeat", {})
        # Was it completed on its last due day?
        self.yesterday_completed: bool = task_data.get("yesterDaily", False)
        # List of upcoming due dates (timestamps)
        _next_due_ts = task_data.get("nextDue", [])
        self.next_due: List[datetime] = [
            dt
            for ts in _next_due_ts
            if (dt := convert_timestamp_to_utc(ts)) is not None
        ]
        # History might contain recent scoring/cron events
        self.history: List[Dict[str, Any]] = task_data.get("history", [])

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Developer-friendly representation including due status and streak."""
        status_char = (
            "[X]" if self.completed else ("[ ]" if self.is_due else "[-]")
        )
        streak_str = f" (Streak: {self.streak})" if self.streak > 0 else ""
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"Daily(id='{self.id}', status='{status_char}', text='{text_preview}'{streak_str})"


# KLASS: Reward
class Reward(Task):
    """Represents a Reward task, inheriting from Task."""

    # FUNC: __init__
    def __init__(self, task_data: Dict[str, Any]):
        """Initializes the Reward object, calling parent init."""
        # Rewards have fewer specific fields than other types.
        # The main difference is 'value' typically represents GP cost.
        super().__init__(task_data)
        self.type = "reward"  # Override type
        # Value is cost, already handled by base Task. Ensure it's parsed correctly.
        self.value = float(
            task_data.get("value", 0.0)
        )  # Explicitly handle value as cost

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Developer-friendly representation including cost."""
        cost_str = f" (Cost: {self.value:.0f} GP)"
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"Reward(id='{self.id}', text='{text_preview}'{cost_str})"


# SECTION: TASK LIST CONTAINER


# KLASS: TaskList
class TaskList:
    """Container for managing a list of Task objects.

    Handles instantiation of appropriate Task subclasses from raw data and
    provides filtering capabilities. Relies on TaskProcessor for calculating
    status, damage, tag names etc.
    """

    # Mapping from type string to the corresponding class constructor
    _TASK_TYPE_MAP: Dict[str, type[Task]] = {
        "habit": Habit,
        "daily": Daily,
        "todo": Todo,
        "reward": Reward,
    }

    # FUNC: __init__
    def __init__(
        self,
        # Expects a list of processed Task objects, not raw data
        # This assumes TaskProcessor has already created the objects
        processed_task_list: List[Task],
        # tag_collection: Optional[TagList] = None, # Pass if needed for name resolution, but TaskProcessor handles this
    ):
        """Initializes the TaskList with pre-processed Task objects.

        Args:
            processed_task_list: A list of Task subclass instances already processed
                                 (e.g., by TaskProcessor).
            # tag_collection: Deprecated - Tag name resolution should happen in TaskProcessor.
        """
        # Store the provided list of Task objects directly
        self.tasks: List[Task] = processed_task_list

        # Optional: Resolve tag names if needed, but processor should do this
        # if tag_collection:
        #     self._resolve_tag_names(tag_collection) # Deprecated here

        # Assign relative positions based on type (useful for display ordering)
        self._assign_relative_positions()

    # FUNC: _assign_relative_positions (Helper)
    def _assign_relative_positions(self) -> None:
        """Assigns a relative position index to each task within its type group."""
        type_position_counters: Dict[str, int] = defaultdict(int)
        default_type_key = "unknown"

        for task in self.tasks:
            # Use the task's type attribute, fallback if None/empty
            type_key = task.type if task.type else default_type_key
            task.position = type_position_counters[type_key]
            type_position_counters[type_key] += 1

    # FUNC: _resolve_tag_names (DEPRECATED - Handled by TaskProcessor)
    # def _resolve_tag_names(self, tag_collection: TagList) -> None:
    #     """Populates the tag_names list for each task using the tag_collection."""
    #     if not hasattr(tag_collection, "by_id"):
    #         print("Warning: tag_collection provided to TaskList lacks 'by_id'. Cannot resolve tag names.")
    #         return
    #     for task in self.tasks:
    #         task.tag_names = [] # Reset just in case
    #         for tag_id in task.tags:
    #             tag_obj = tag_collection.by_id(tag_id)
    #             if tag_obj and tag_obj.name:
    #                 task.tag_names.append(tag_obj.name)
    #             else:
    #                 task.tag_names.append(tag_id) # Fallback to ID

    # SECTION: Access and Filtering Methods

    # FUNC: __len__
    def __len__(self) -> int:
        """Returns the number of tasks in the list."""
        return len(self.tasks)

    # FUNC: __iter__
    def __iter__(self):
        """Allows iterating over the Task objects."""
        yield from self.tasks

    # FUNC: __getitem__
    def __getitem__(self, index: int) -> Task:
        """Allows accessing tasks by index."""
        if not isinstance(index, int):
            raise TypeError("Index must be an integer")
        if not 0 <= index < len(self.tasks):
            raise IndexError("Task index out of range")
        return self.tasks[index]

    # FUNC: get_by_id
    def get_by_id(self, task_id: str) -> Optional[Task]:
        """Finds a task by its ID.

        Args:
            task_id: The ID string of the task to find.

        Returns:
            The Task object if found, otherwise None.
        """
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    # FUNC: filter_by_type
    def filter_by_type(self, task_type: str) -> List[Task]:
        """Returns tasks matching the given type ('habit', 'daily', 'todo', 'reward').

        Args:
            task_type: The type string to filter by.

        Returns:
            A list of matching Task objects.
        """
        # Use type attribute for filtering
        return [task for task in self.tasks if task.type == task_type]

    # FUNC: filter_by_tag_id
    def filter_by_tag_id(self, tag_id: str) -> List[Task]:
        """Returns tasks that have the given tag ID in their `tags` list.

        Args:
            tag_id: The tag ID string to filter by.

        Returns:
            A list of matching Task objects.
        """
        return [task for task in self.tasks if tag_id in task.tags]

    # FUNC: filter_by_tag_name
    def filter_by_tag_name(self, tag_name: str) -> List[Task]:
        """Returns tasks that have the given tag name in their resolved `tag_names` list.

        Requires `tag_names` to be populated (usually by TaskProcessor).

        Args:
            tag_name: The tag name string to filter by (case-sensitive).

        Returns:
            A list of matching Task objects.
        """
        # Check if tag_names seem populated on the first task (heuristic)
        if not self.tasks or not hasattr(self.tasks[0], "tag_names"):
            print(
                "Warning: Filtering by tag name, but 'tag_names' may not be populated."
            )
        return [
            task
            for task in self.tasks
            if hasattr(task, "tag_names") and tag_name in task.tag_names
        ]

    # FUNC: filter_by_priority
    def filter_by_priority(
        self,
        exact_priority: Optional[float] = None,
        min_priority: Optional[float] = None,
        max_priority: Optional[float] = None,
    ) -> List[Task]:
        """Returns tasks matching priority criteria.

        Habitica priorities: 0.1 (Trivial), 1 (Easy), 1.5 (Medium), 2 (Hard).

        Args:
            exact_priority: Filter by exact priority value (uses tolerance for float comparison).
            min_priority: Filter by minimum priority value (inclusive).
            max_priority: Filter by maximum priority value (inclusive).

        Returns:
            A list of matching Task objects.
        """
        filtered = self.tasks
        if exact_priority is not None:
            tolerance = 0.01  # Tolerance for float comparison
            filtered = [
                task
                for task in filtered
                if abs(task.priority - exact_priority) < tolerance
            ]
        else:  # Apply range filters only if exact_priority is not given
            if min_priority is not None:
                filtered = [
                    task for task in filtered if task.priority >= min_priority
                ]
            if max_priority is not None:
                filtered = [
                    task for task in filtered if task.priority <= max_priority
                ]
        return filtered

    # FUNC: filter_by_attribute
    def filter_by_attribute(self, attribute: str) -> List[Task]:
        """Returns tasks matching the given attribute ('str', 'int', 'con', 'per').

        Args:
            attribute: The attribute string to filter by.

        Returns:
            A list of matching Task objects.
        """
        return [task for task in self.tasks if task.attribute == attribute]

    # FUNC: filter_by_status
    def filter_by_status(self, status: str) -> List[Task]:
        """Returns tasks matching a specific calculated status.

        Status values depend on TaskProcessor logic (e.g., 'due', 'red', 'success', 'grey', 'done').

        Args:
            status: The status string to filter by.

        Returns:
            A list of matching Task objects.
        """
        if not self.tasks or not hasattr(self.tasks[0], "_status"):
            print(
                "Warning: Filtering by status, but '_status' may not be populated."
            )
        return [
            task
            for task in self.tasks
            if hasattr(task, "_status") and task._status == status
        ]

    # FUNC: filter_completed (More specific than status filter)
    def filter_completed(
        self, completed: bool = True
    ) -> List[Union[Daily, Todo]]:
        """Returns completed or uncompleted Dailies and Todos.

        Args:
            completed: Set to True to find completed tasks, False for incomplete (default: True).

        Returns:
            A list of matching Daily or Todo objects.
        """
        return [
            task
            for task in self.tasks
            if isinstance(task, (Daily, Todo)) and task.completed is completed
        ]

    # FUNC: filter_due_dailies (More specific than status filter)
    def filter_due_dailies(self, due: bool = True) -> List[Daily]:
        """Returns Dailies that are marked as due (or not due) for today.

        Args:
            due: Set to True to find due dailies, False for not due (default: True).

        Returns:
            A list of matching Daily objects.
        """
        return [
            task
            for task in self.tasks
            if isinstance(task, Daily) and task.is_due is due
        ]

    # FUNC: filter_past_due_todos (More specific than status filter)
    def filter_past_due_todos(self) -> List[Todo]:
        """Returns Todos that are past their due date and not completed.

        Returns:
            A list of matching Todo objects.
        """
        # Relies on the is_past_due property
        return [
            task
            for task in self.tasks
            if isinstance(task, Todo) and task.is_past_due
        ]

    # FUNC: filter_by_challenge
    def filter_by_challenge(
        self,
        challenge_id: Optional[str] = None,
        is_broken: Optional[bool] = None,
        broken_status: Optional[
            str
        ] = None,  # Filter by specific broken type ('task', 'challenge')
    ) -> List[Task]:
        """Returns tasks associated with challenges based on criteria.

        Args:
            challenge_id: If provided, only return tasks from this specific challenge.
            is_broken: If True, return tasks with any broken status. If False, return
                       tasks that are part of a challenge but not broken. If None,
                       broken status is not filtered (but still requires task to be in a challenge).
            broken_status: If provided (e.g., 'task', 'challenge'), only return tasks
                           with that specific `broken_status` value (implies is_broken=True).

        Returns:
            A list of matching Task objects.
        """
        # Start with tasks that have challenge data
        filtered = [task for task in self.tasks if task.challenge is not None]

        if challenge_id is not None:
            filtered = [
                task
                for task in filtered
                if task.challenge and task.challenge.id == challenge_id
            ]

        if broken_status is not None:
            # Filter by specific broken type (most restrictive)
            filtered = [
                task
                for task in filtered
                if task.challenge
                and task.challenge.broken_status == broken_status
            ]
        elif is_broken is not None:
            # Filter by general broken state (True or False)
            filtered = [
                task
                for task in filtered
                if task.challenge and task.challenge.is_broken is is_broken
            ]
        # If is_broken is None and broken_status is None, we just return all tasks linked to any challenge

        return filtered

    # FUNC: filter_by_habitica
    def filter_by_habitica(self, by_habitica: bool = True) -> List[Task]:
        """Returns tasks created by Habitica (e.g., system tasks, tutorial tasks).

        Args:
            by_habitica: Set to True to filter for Habitica-created tasks, False otherwise (default: True).

        Returns:
            A list of matching Task objects.
        """
        return [task for task in self.tasks if task.by_habitica is by_habitica]

    # FUNC: filter_needs_action (Example complex filter)
    def filter_needs_action(self) -> List[Task]:
        """Returns Dailies due today and uncompleted, and Todos not completed.

        This is an example of combining other filter logic or criteria.

        Returns:
            A list of Task objects considered actionable.
        """
        actionable: List[Task] = []
        for task in self.tasks:
            # Daily: due today and not completed
            if isinstance(task, Daily) and task.is_due and not task.completed:
                actionable.append(task)
            # Todo: not completed (optionally add check for past due if desired)
            elif isinstance(task, Todo) and not task.completed:
                # if task.is_past_due: # Uncomment to only include overdue Todos
                actionable.append(task)
            # Could potentially include positive Habits here too if desired
            # elif isinstance(task, Habit) and task.up:
            #     actionable.append(task)
        return actionable
