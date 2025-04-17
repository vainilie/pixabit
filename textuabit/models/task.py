# pixabit/models/task.py
# MARK: - MODULE DOCSTRING
"""Defines data classes for representing Habitica Tasks (Habits, Dailies, To-Dos, Rewards)."""

# MARK: - IMPORTS
from datetime import datetime
from typing import Any, Dict, List, Optional  # Use typing imports for 3.9

from ..utils.dates import convert_timestamp_to_utc

# Import Tag class if it's defined elsewhere (e.g., models/tag.py)
# from .tag import Tag


# KLASS: - ChecklistItem
class ChecklistItem:
    """Represents a single item within a Task's checklist."""

    # FUNC: - __init__
    def __init__(self, item_data: Dict[str, Any]):
        self.id: Optional[str] = item_data.get("id")
        self.text: str = item_data.get("text", "")
        self.completed: bool = item_data.get("completed", False)

    # FUNC: - __repr__
    def __repr__(self) -> str:
        status = "[X]" if self.completed else "[ ]"
        return f"ChecklistItem(id={self.id}, status='{status}', text='{self.text[:30]}...')"


# KLASS: - Task (Base Class)
class Task:
    """Base representation of a Habitica Task."""

    # FUNC: - __init__
    def __init__(self, task_data: Dict[str, Any]):
        """Initializes the base Task object."""
        self.id: Optional[str] = task_data.get("id")
        self.alias: Optional[str] = task_data.get("alias")

        self.user_id: Optional[str] = task_data.get(
            "userId"
        )  # ID of the user owning this instance
        self.text: str = task_data.get("text", "")
        self.notes: str = task_data.get("notes", "")
        self.type: Optional[str] = task_data.get("type")  # Set by subclasses
        self.tags: List[str] = task_data.get("tags", [])  # List of Tag IDs
        self.value: float = float(task_data.get("value", 0.0))  # Ensure float
        self.priority: float = float(
            task_data.get("priority", 1.0)
        )  # Ensure float (1.0=Easy default)
        self.attribute: str = task_data.get("attribute", "str")  # Default 'str'
        self.created_at: Optional[datetime] = convert_timestamp_to_utc(task_data.get("createdAt"))

        # Challenge Info (handle potential non-dict challenge field)
        challenge_data = task_data.get("challenge", {})
        self.challenge_id: Optional[str] = (
            challenge_data.get("id") if isinstance(challenge_data, dict) else None
        )
        self.challenge_name: Optional[str] = (
            challenge_data.get("shortName") if isinstance(challenge_data, dict) else None
        )
        # Check for broken status correctly based on API response inspection needed here
        self.challenge_broken: bool = (
            challenge_data.get("broken") == "BROKEN" if isinstance(challenge_data, dict) else False
        )
        self.task_broken: bool = (
            challenge_data.get("broken") == "DELETED_"
            if isinstance(challenge_data, dict)
            else False
        )

        # Processed/Calculated Fields (Populated by TaskProcessor or later)
        self.tag_names: List[str] = []  # Populated later
        self.value_color: str = "neutral"  # Populated later
        self._status: str = "unknown"  # Internal status (due, red, grey, done) populated later

        # What with this?

        self.origin_tag: Optional[Tag] = None
        self.attribute_tag: Optional[Tag] = None
        self.area_tag: Optional[Tag] = None

        self.checklist: Optional[bool] = task_data.get("checklist") is not None
        self.subtasks: Optional[dict[str, any]] = task_data.get("checklist")

    # FUNC: - __repr__
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"{self.__class__.__name__}(id='{self.id}', text='{self.text[:30]}...', type='{self.type}')"

    # FUNC: - update_from_processed
    def update_from_processed(self, processed_data: Dict[str, Any]):
        """Updates task instance with fields calculated during processing."""
        self.tag_names = processed_data.get(
            "tag_names", self.tags
        )  # Fallback to IDs if names missing
        self.value_color = processed_data.get("value_color", "neutral")
        self._status = processed_data.get("_status", "unknown")
        # Add any other processed fields you need (like damage)
        self.damage_user = processed_data.get("damage_to_user")
        self.damage_party = processed_data.get("damage_to_party")


# KLASS: - Habit
class Habit(Task):
    """Represents a Habit task."""

    # FUNC: - __init__
    def __init__(self, task_data: Dict[str, Any]):
        super().__init__(task_data)
        self.type = "habit"
        self.up: bool = task_data.get("up", False)
        self.down: bool = task_data.get("down", False)
        self.counter_up: int = task_data.get("counterUp", 0)
        self.counter_down: int = task_data.get("counterDown", 0)
        self.frequency: str = task_data.get("frequency", "daily")  # daily or weekly

    # Override representation for specific Habit info
    def __repr__(self) -> str:
        up_str = f"⬆️{self.counter_up}" if self.up else ""
        down_str = f"⬇️{self.counter_down}" if self.down else ""
        sep = " / " if self.up and self.down else ""
        return f"Habit(id='{self.id}', text='{self.text[:30]}...', counters='{up_str}{sep}{down_str}')"


# KLASS: - Todo
class Todo(Task):
    """Represents a To-Do task."""

    # FUNC: - __init__
    def __init__(self, task_data: Dict[str, Any]):
        super().__init__(task_data)
        self.type = "todo"
        self.completed: bool = task_data.get("completed", False)
        self.date: Optional[datetime] = convert_timestamp_to_utc(task_data.get("date"))  # Due date
        # API v3 doesn't have separate start date for todos
        self.checklist: List[ChecklistItem] = [
            ChecklistItem(item)
            for item in task_data.get("checklist", [])
            if isinstance(item, dict)
        ]

    # Property to check if due date is passed
    @property
    def is_past_due(self) -> bool:
        if not self.date:
            return False
        return self.date < datetime.now(timezone.utc)

    # Override representation
    def __repr__(self) -> str:
        status = "[X]" if self.completed else "[ ]"
        due = f", due={self.date.strftime('%Y-%m-%d')}" if self.date else ""
        return f"Todo(id='{self.id}', status='{status}', text='{self.text[:30]}...'{due})"


# KLASS: - Daily
class Daily(Task):
    """Represents a Daily task."""

    # FUNC: - __init__
    def __init__(self, task_data: Dict[str, Any]):
        super().__init__(task_data)
        self.type = "daily"
        self.completed: bool = task_data.get("completed", False)
        self.is_due: bool = task_data.get(
            "isDue", False
        )  # If due for the *current* day based on cron
        self.streak: int = task_data.get("streak", 0)
        self.checklist: List[ChecklistItem] = [
            ChecklistItem(item)
            for item in task_data.get("checklist", [])
            if isinstance(item, dict)
        ]
        # Scheduling properties
        self.frequency: str = task_data.get(
            "frequency", "daily"
        )  # 'daily', 'weekly', 'monthly', 'yearly'
        self.every_x: int = task_data.get("everyX", 1)
        self.start_date: Optional[datetime] = convert_timestamp_to_utc(task_data.get("startDate"))
        self.days_of_month: List[int] = task_data.get("daysOfMonth", [])  # For monthly frequency
        self.weeks_of_month: List[int] = task_data.get("weeksOfMonth", [])  # For monthly frequency
        self.repeat: Dict[str, bool] = task_data.get("repeat", {})  # For weekly {m:t, t:f, ...}
        self.yesterday: Optional[bool] = task_data.get("yesterDaily")
        self.next_due: Optional[list[str]] = task_data.get("nextDue")
        # Calculated properties (to be updated by processor)
        self.damage_user: Optional[float] = None
        self.damage_party: Optional[float] = None

    # Override representation
    def __repr__(self) -> str:
        status = "[X]" if self.completed else "[ ]"
        due_today = " (Due)" if self.is_due else " (Not Due)"
        return f"Daily(id='{self.id}', status='{status}', text='{self.text[:30]}...'{due_today})"


# KLASS: - Reward
class Reward(Task):
    """Represents a Reward task."""

    # FUNC: - __init__
    def __init__(self, task_data: Dict[str, Any]):
        super().__init__(task_data)
        self.type = "reward"
        # 'value' attribute (cost) is inherited from Task

    # Override representation
    def __repr__(self) -> str:
        cost = self.value
        return f"Reward(id='{self.id}', text='{self.text[:30]}...', cost={cost})"


# Example in TaskProcessor or CliApp after fetching raw task data
""" raw_task_list = await api_client.get_tasks()
processed_task_objects: Dict[str, Task] = {}
for raw_task in raw_task_list:
     task_type = raw_task.get("type")
     task_instance: Optional[Task] = None
     if task_type == "habit": task_instance = Habit(raw_task)
     elif task_type == "daily": task_instance = Daily(raw_task)
     # ... etc for todo, reward ...
     elif task_type: task_instance = Task(raw_task) # Base class for unknown

     if task_instance and task_instance.id:
         # You might still run parts of your original processor logic
         # to calculate things like _status, value_color, damage
         # and then call task_instance.update_from_processed(calculated_data)
         processed_task_objects[task_instance.id] = task_instance """
