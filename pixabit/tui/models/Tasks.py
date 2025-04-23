from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Literal, Optional, Union

import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from rich.logging import RichHandler
from rich.markdown import Markdown

try:
    from pixabit.utils.converter import MarkdownConverter
except ImportError:

    logging.warning("Warning: Pixabit utility imports failed. Using placeholders.")

    class MarkdownConverter:
        @staticmethod
        def convert_to_rich(text: str) -> str:
            return text


FORMAT = "%(message)s"
logging.basicConfig(
    level="INFO",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
)
logger = logging.getLogger(__name__)


ALL_GEAR_CONTENT: dict[str, dict[str, Any]] = {
    "weapon_warrior_1": {"str": 3, "klass": "warrior"},
    "armor_warrior_1": {"con": 2, "klass": "warrior"},
    "head_warrior_1": {"int": 1, "klass": "warrior"},
    "shield_warrior_1": {"per": 2, "klass": "warrior"},
    "weapon_base_0": {"str": 0},
}


class ChecklistItem(BaseModel):

    model_config = ConfigDict(extra="ignore")
    id: Optional[str] = None
    text: str = ""
    completed: bool = False

    @field_validator("text", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any) -> str:
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value)
        return ""

    def __repr__(self) -> str:
        status = "[X]" if self.completed else "[ ]"
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"ChecklistItem(status='{status}', text='{text_preview}')"


class ChallengeData(BaseModel):

    model_config = ConfigDict(extra="ignore")
    task_id: Optional[str] = Field(None, alias="taskId")
    id: Optional[str] = Field(None)
    name: Optional[str] = Field(None, alias="shortName")
    broken_status: Optional[Literal["task", "challenge", "unknown"]] = Field(None)
    is_broken: bool = Field(False)

    @field_validator("name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> Optional[str]:
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value)
        return None

    @model_validator(mode="before")
    @classmethod
    def process_broken_status(cls, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        values = data.copy()
        broken_raw: Optional[str] = data.get("broken")
        is_broken = bool(broken_raw)
        broken_status = None
        if broken_raw:
            if broken_raw in ("TASK_DELETED", "CHALLENGE_TASK_NOT_FOUND"):
                broken_status = "task"
            elif broken_raw in ("CHALLENGE_DELETED", "UNSUBSCRIBED", "CHALLENGE_CLOSED"):
                broken_status = "challenge"
            else:
                broken_status = "unknown"
        values["is_broken"] = is_broken
        values["broken_status"] = broken_status
        return values

    def __repr__(self) -> str:
        status = f", broken='{self.broken_status}'" if self.is_broken else ""
        return f"ChallengeData(id={self.id}, name='{self.name}'{status})"


class Task(BaseModel):

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = Field(..., alias="_id")
    alias: Optional[str] = Field(None)
    user_id: Optional[str] = Field(None, alias="userId")
    text: str = Field("")
    notes: str = Field("")
    type: Optional[Literal["habit", "daily", "todo", "reward"]] = Field(None)
    tags: List[str] = Field(default_factory=list)
    value: float = Field(default=0.0)
    priority: float = Field(default=1.0)
    attribute: Literal["str", "int", "con", "per"] = Field(default="str")
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    by_habitica: bool = Field(False, alias="byHabitica")
    reminders: List[Dict[str, Any]] = Field(default_factory=list)
    challenge: Optional[ChallengeData] = Field(None)

    position: Optional[int] = Field(
        None, description="Calculated display position relative to type."
    )
    tag_names: List[str] = Field(
        default_factory=list, description="Resolved tag names (populated externally)."
    )

    damage_user: Optional[float] = Field(
        None, description="Calculated HP damage to user (populated externally)."
    )
    damage_party: Optional[float] = Field(
        None, description="Calculated damage to party/boss (populated externally)."
    )

    @field_validator("id", mode="before")
    @classmethod
    def check_id_exists(cls, v: Any) -> str:
        if not v:
            raise ValueError("Task data is missing required field '_id'.")
        return str(v)

    @field_validator("text", "notes", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any) -> str:
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value)
        return ""

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_utc(cls, value: Any) -> Optional[datetime]:
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))

                return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse timestamp: {value}")
                return None
        elif isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return None

    @field_validator("value", "priority", mode="before")
    @classmethod
    def ensure_float(cls, value: Any) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):

            return 1.0 if value is None else 0.0

    @property
    @lru_cache(maxsize=1)
    def styled(self) -> Markdown:
        return Markdown(self.text or "")

    def __repr__(self) -> str:
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return (
            f"{self.__class__.__name__}(id='{self.id}', text='{text_preview}', type='{self.type}')"
        )


class Habit(Task):

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    type: Literal["habit"] = "habit"
    up: bool = Field(True)
    down: bool = Field(True)
    counter_up: int = Field(0, alias="counterUp")
    counter_down: int = Field(0, alias="counterDown")
    frequency: str = Field("daily")
    history: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator("counter_up", "counter_down", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def __repr__(self) -> str:
        up_str = f"⬆️{self.counter_up}" if self.up else ""
        down_str = f"⬇️{self.counter_down}" if self.down else ""
        sep = " / " if self.up and self.down else ""
        counters = f"{up_str}{sep}{down_str}" if up_str or down_str else "No Counters"
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"Habit(id='{self.id}', text='{text_preview}', counters='{counters}')"


class Todo(Task):

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    type: Literal["todo"] = "todo"
    completed: bool = Field(False)
    completed_date: Optional[datetime] = Field(None, alias="dateCompleted")
    due_date: Optional[datetime] = Field(None, alias="date")
    collapse_checklist: bool = Field(False, alias="collapseChecklist")
    checklist: List[ChecklistItem] = Field(default_factory=list)

    @field_validator("completed_date", "due_date", mode="before")
    @classmethod
    def parse_todo_datetime_utc(cls, value: Any) -> Optional[datetime]:

        return Task.parse_datetime_utc(value)

    @property
    def is_past_due(self) -> bool:
        if self.completed or not self.due_date:
            return False
        return self.due_date < datetime.now(timezone.utc)

    @property
    def display_status(self) -> Literal["Complete", "Past Due", "Due", "No Due Date"]:
        if self.completed:
            return "Complete"
        elif not self.due_date:
            return "No Due Date"
        elif self.is_past_due:
            return "Past Due"
        else:
            return "Due"

    def __repr__(self) -> str:
        status_char = "[X]" if self.completed else "[ ]"
        due_str = f", due={self.due_date.strftime('%Y-%m-%d')}" if self.due_date else ""
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")

        return (
            f"Todo(id='{self.id}', status='{self.display_status}', text='{text_preview}'{due_str})"
        )


class Daily(Task):

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    type: Literal["daily"] = "daily"
    completed: bool = Field(False)
    is_due: bool = Field(False, alias="isDue")
    streak: int = Field(0)
    collapse_checklist: bool = Field(False, alias="collapseChecklist")
    checklist: List[ChecklistItem] = Field(default_factory=list)

    frequency: Literal["daily", "weekly", "monthly", "yearly"] = Field("weekly")
    every_x: int = Field(1, alias="everyX")
    start_date: Optional[datetime] = Field(None, alias="startDate")
    days_of_month: List[int] = Field(default_factory=list, alias="daysOfMonth")
    weeks_of_month: List[int] = Field(default_factory=list, alias="weeksOfMonth")
    repeat: Dict[str, bool] = Field(default_factory=dict)
    yesterday_completed: bool = Field(False, alias="yesterDaily")
    next_due: List[datetime] = Field(default_factory=list)
    history: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator("streak", "every_x", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 1

    @field_validator("start_date", mode="before")
    @classmethod
    def parse_start_date_utc(cls, value: Any) -> Optional[datetime]:

        return Task.parse_datetime_utc(value)

    @field_validator("next_due", mode="before")
    @classmethod
    def parse_next_due_list(cls, value: Any) -> List[datetime]:
        if not isinstance(value, list):
            return []
        parsed_dates = []
        for ts in value:
            dt = Task.parse_datetime_utc(ts)
            if dt:
                parsed_dates.append(dt)
        return parsed_dates

    @property
    def display_status(self) -> Literal["Complete", "Due", "Not Due"]:
        if self.completed:
            return "Complete"
        elif self.is_due:
            return "Due"
        else:
            return "Not Due"

    def __repr__(self) -> str:

        status_repr = f"status='{self.display_status}'"
        streak_str = f" (Streak: {self.streak})" if self.streak > 0 else ""
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"Daily(id='{self.id}', {status_repr}, text='{text_preview}'{streak_str})"


class Reward(Task):

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    type: Literal["reward"] = "reward"

    def __repr__(self) -> str:
        cost_str = f" (Cost: {self.value:.0f} GP)" if self.value > 0 else " (Free)"
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"Reward(id='{self.id}', text='{text_preview}'{cost_str})"


class TaskList:

    def __init__(self, processed_task_list: List[Task]):
        if not isinstance(processed_task_list, list):
            raise TypeError("processed_task_list must be a list of Task objects.")
        self.tasks: List[Task] = processed_task_list
        self._assign_relative_positions()

    def _assign_relative_positions(self) -> None:
        type_position_counters: Dict[str, int] = defaultdict(int)
        default_type_key = "unknown"
        for task in self.tasks:
            type_key = task.type if task.type else default_type_key
            task.position = type_position_counters[type_key]
            type_position_counters[type_key] += 1

    def __len__(self) -> int:
        return len(self.tasks)

    def __iter__(self) -> iter[Task]:
        return iter(self.tasks)

    def __getitem__(self, index: int) -> Task:
        if not isinstance(index, int):
            raise TypeError("Index must be an integer")
        if not 0 <= index < len(self.tasks):
            raise IndexError("Task index out of range")
        return self.tasks[index]

    def __repr__(self) -> str:
        counts = defaultdict(int)
        for task in self.tasks:
            counts[task.type or "unknown"] += 1
        count_str = ", ".join(f"{t}:{c}" for t, c in counts.items())
        return f"TaskList(count={len(self.tasks)}, types=[{count_str}])"

    def get_by_id(self, task_id: str) -> Optional[Task]:
        return next((task for task in self.tasks if task.id == task_id), None)

    def filter_by_type(self, task_type: str) -> TaskList:
        filtered_tasks = [task for task in self.tasks if task.type == task_type]
        return TaskList(filtered_tasks)

    def filter_by_tag_id(self, tag_id: str) -> TaskList:
        filtered_tasks = [task for task in self.tasks if tag_id in task.tags]
        return TaskList(filtered_tasks)

    def filter_by_tag_name(self, tag_name: str) -> TaskList:

        if not self.tasks or not hasattr(self.tasks[0], "tag_names") or not self.tasks[0].tag_names:
            logger.warning("Filtering by tag name, but 'tag_names' may not be populated.")
        filtered_tasks = [
            task for task in self.tasks if hasattr(task, "tag_names") and tag_name in task.tag_names
        ]
        return TaskList(filtered_tasks)

    def filter_by_priority(
        self,
        exact_priority: Optional[float] = None,
        min_priority: Optional[float] = None,
        max_priority: Optional[float] = None,
    ) -> TaskList:
        filtered = self.tasks
        if exact_priority is not None:
            tolerance = 0.01
            filtered = [
                task for task in filtered if abs(task.priority - exact_priority) < tolerance
            ]
        else:
            if min_priority is not None:
                filtered = [task for task in filtered if task.priority >= min_priority]
            if max_priority is not None:
                filtered = [task for task in filtered if task.priority <= max_priority]
        return TaskList(filtered)

    def filter_by_attribute(self, attribute: str) -> TaskList:
        filtered_tasks = [task for task in self.tasks if task.attribute == attribute]
        return TaskList(filtered_tasks)

    def filter_completed(self, completed: bool = True) -> TaskList:
        filtered_tasks = [
            task
            for task in self.tasks
            if isinstance(task, (Daily, Todo)) and task.completed is completed
        ]
        return TaskList(filtered_tasks)

    def filter_due_dailies(self, due: bool = True) -> TaskList:
        filtered_tasks = [
            task for task in self.tasks if isinstance(task, Daily) and task.is_due is due
        ]
        return TaskList(filtered_tasks)

    def filter_past_due_todos(self) -> TaskList:
        filtered_tasks = [
            task for task in self.tasks if isinstance(task, Todo) and task.is_past_due
        ]
        return TaskList(filtered_tasks)

    def filter_by_challenge(
        self,
        challenge_id: Optional[str] = None,
        is_broken: Optional[bool] = None,
        broken_status: Optional[str] = None,
    ) -> TaskList:
        filtered = [task for task in self.tasks if task.challenge is not None]
        if challenge_id is not None:
            filtered = [
                task for task in filtered if task.challenge and task.challenge.id == challenge_id
            ]
        if broken_status is not None:
            filtered = [
                task
                for task in filtered
                if task.challenge and task.challenge.broken_status == broken_status
            ]
        elif is_broken is not None:
            filtered = [
                task
                for task in filtered
                if task.challenge and task.challenge.is_broken is is_broken
            ]
        return TaskList(filtered)

    def filter_by_habitica(self, by_habitica: bool = True) -> TaskList:
        filtered_tasks = [task for task in self.tasks if task.by_habitica is by_habitica]
        return TaskList(filtered_tasks)

    def filter_needs_action(self) -> TaskList:
        actionable: List[Task] = []
        for task in self.tasks:
            if isinstance(task, Daily) and task.is_due and not task.completed:
                actionable.append(task)
            elif isinstance(task, Todo) and not task.completed:
                actionable.append(task)
        return TaskList(actionable)


if __name__ == "__main__":

    try:
        with open("tasks_data.json", encoding="utf-8") as f:
            raw_task_list_data = json.load(f)
        if not isinstance(raw_task_list_data, list):
            raise TypeError("Expected a list of tasks from JSON.")
    except (FileNotFoundError, json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to load or parse task data: {e}")
        raw_task_list_data = []

    processed_tasks: List[Task] = []
    task_type_map: Dict[str, type[Task]] = {
        "habit": Habit,
        "daily": Daily,
        "todo": Todo,
        "reward": Reward,
    }
    for task_data in raw_task_list_data:
        task_type_str = task_data.get("type")
        TaskModel = task_type_map.get(task_type_str, Task)
        try:
            task_obj = TaskModel.model_validate(task_data)
            processed_tasks.append(task_obj)
        except ValidationError as e:
            task_text = task_data.get("text", task_data.get("_id", "Unknown Task"))
            logger.error(f"Validation failed for task '{task_text}':\n{e}")
        except ValueError as e:
            logger.error(f"Skipping task due to processing error: {e}")

    logger.info(f"Processed {len(processed_tasks)} tasks.")

    task_list = TaskList(processed_tasks)
    logger.info(f"Created TaskList: {task_list}")

    print("\n--- Filtering Examples ---")

    todos = task_list.filter_by_type("todo")
    if todos:
        print("\n--- Todo Statuses ---")
        for todo in todos:
            print(f"'{todo.text[:20]}...': {todo.display_status}")
