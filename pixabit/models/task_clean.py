from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

import emoji_data_python
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown
from rich.text import Text
from textual import log

from pixabit.utils.converter import MarkdownConverter
from pixabit.utils.display import console

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
)
try:
    from pixabit.utils.dates import convert_timestamp_to_utc
except ImportError:
    log.warning("Warning: Using placeholder convert_timestamp_to_utc in task.py.")

    def convert_timestamp_to_utc(ts: Any) -> Optional[datetime]:
        return None


class ChecklistItem:
    def __init__(self, item_data: Dict[str, Any]):
        if not isinstance(item_data, dict):
            raise TypeError("item_data must be a dictionary.")
        self.id: Optional[str] = item_data.get("id")
        _text = item_data.get("text", "")
        self.text: str = emoji_data_python.replace_colons(_text) if _text else ""
        self.completed: bool = item_data.get("completed", False)

    def __repr__(self) -> str:
        status = "[X]" if self.completed else "[ ]"
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"ChecklistItem(id={self.id}, status='{status}', text='{text_preview}')"


class ChallengeData:
    def __init__(self, challenge_data: Optional[Dict[str, Any]]):
        data = challenge_data if isinstance(challenge_data, dict) else {}
        self.task_id: Optional[str] = data.get("taskId")
        self.id: Optional[str] = data.get("id")
        _short_name = data.get("shortName")
        self.name: Optional[str] = (
            emoji_data_python.replace_colons(_short_name) if _short_name else None
        )
        broken_raw: Optional[str] = data.get("broken")
        self.broken_status: Optional[str] = None
        self.is_broken: bool = bool(broken_raw)
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
                self.broken_status = "unknown"

    def __repr__(self) -> str:
        status = f", broken='{self.broken_status}'" if self.is_broken else ""
        return f"ChallengeData(id={self.id}, name='{self.name}'{status})"


class Task:
    def __init__(self, task_data: Dict[str, Any]):
        if not isinstance(task_data, dict):
            raise TypeError("task_data must be a dictionary.")
        if not task_data.get("_id"):
            raise ValueError(f"Task data is missing '_id': {task_data.get('text', 'N/A')}")
        self.id: str = task_data["_id"]
        self.alias: Optional[str] = task_data.get("alias")
        self.user_id: Optional[str] = task_data.get("userId")
        _text = task_data.get("text", "")
        if _text:
            text_with_emojis = emoji_data_python.replace_colons(_text)
            self.text: str = text_with_emojis
            _styled_dict = MarkdownConverter.convert_to_rich(text_with_emojis)
            self.styled: str = _styled_dict
        else:
            self.text = ""
            self.styled = ""
        _notes = task_data.get("notes", "")
        self.notes: str = emoji_data_python.replace_colons(_notes) if _notes else ""
        self.type: Optional[str] = task_data.get("type")
        self.tags: List[str] = task_data.get("tags", [])
        self.value: float = float(task_data.get("value", 0.0))
        self.priority: float = float(task_data.get("priority", 1.0))
        self.attribute: str = task_data.get("attribute", "str")
        self.position: Optional[int] = None
        self.created_at: Optional[datetime] = convert_timestamp_to_utc(task_data.get("createdAt"))
        self.updated_at: Optional[datetime] = convert_timestamp_to_utc(task_data.get("updatedAt"))
        self.by_habitica: bool = task_data.get("byHabitica", False)
        self.reminders: List[Dict[str, Any]] = task_data.get("reminders", [])
        challenge_info = task_data.get("challenge")
        self.challenge: Optional[ChallengeData] = (
            ChallengeData(challenge_info) if challenge_info else None
        )
        self.checklist: List[ChecklistItem] = []
        self.tag_names: List[str] = []
        self.value_color: str = "neutral"
        self._status: str = "unknown"
        self.damage_user: Optional[float] = None
        self.damage_party: Optional[float] = None

    def __repr__(self) -> str:
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return (
            f"{self.__class__.__name__}(id='{self.id}', text='{text_preview}', type='{self.type}')"
        )


class Habit(Task):
    def __init__(self, task_data: Dict[str, Any]):
        super().__init__(task_data)
        self.type = "habit"
        self.up: bool = task_data.get("up", True)
        self.down: bool = task_data.get("down", True)
        self.counter_up: int = int(task_data.get("counterUp", 0))
        self.counter_down: int = int(task_data.get("counterDown", 0))
        self.frequency: str = task_data.get("frequency", "daily")
        self.history: List[Dict[str, Any]] = task_data.get("history", [])

    def __repr__(self) -> str:
        up_str = f"⬆️{self.counter_up}" if self.up else ""
        down_str = f"⬇️{self.counter_down}" if self.down else ""
        sep = " / " if self.up and self.down else ""
        counters = f"{up_str}{sep}{down_str}" if up_str or down_str else "No Counters"
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"Habit(id='{self.id}', text='{text_preview}', counters='{counters}')"


class Todo(Task):
    def __init__(self, task_data: Dict[str, Any]):
        super().__init__(task_data)
        self.type = "todo"
        self.completed: bool = task_data.get("completed", False)
        self.completed_date: Optional[datetime] = convert_timestamp_to_utc(
            task_data.get("dateCompleted")
        )
        self.due_date: Optional[datetime] = convert_timestamp_to_utc(task_data.get("date"))
        self.collapse_checklist: bool = task_data.get("collapseChecklist", False)
        self.checklist: List[ChecklistItem] = [
            ChecklistItem(item) for item in task_data.get("checklist", []) if isinstance(item, dict)
        ]

    @property
    def is_past_due(self) -> bool:
        if self.completed or not self.due_date:
            return False
        return self.due_date < datetime.now(timezone.utc)

    def __repr__(self) -> str:
        status_char = "[X]" if self.completed else "[ ]"
        due_str = f", due={self.due_date.strftime('%Y-%m-%d')}" if self.due_date else ""
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"Todo(id='{self.id}', status='{status_char}', text='{text_preview}'{due_str})"


class Daily(Task):
    def __init__(self, task_data: Dict[str, Any]):
        super().__init__(task_data)
        self.type = "daily"
        self.completed: bool = task_data.get("completed", False)
        self.is_due: bool = task_data.get("isDue", False)
        self.streak: int = int(task_data.get("streak", 0))
        self.collapse_checklist: bool = task_data.get("collapseChecklist", False)
        self.checklist: List[ChecklistItem] = [
            ChecklistItem(item) for item in task_data.get("checklist", []) if isinstance(item, dict)
        ]
        self.frequency: str = task_data.get("frequency", "weekly")
        self.every_x: int = int(task_data.get("everyX", 1))
        self.start_date: Optional[datetime] = convert_timestamp_to_utc(task_data.get("startDate"))
        self.days_of_month: List[int] = task_data.get("daysOfMonth", [])
        self.weeks_of_month: List[int] = task_data.get("weeksOfMonth", [])
        self.repeat: Dict[str, bool] = task_data.get("repeat", {})
        self.yesterday_completed: bool = task_data.get("yesterDaily", False)
        _next_due_ts = task_data.get("nextDue", [])
        self.next_due: List[datetime] = [
            dt for ts in _next_due_ts if (dt := convert_timestamp_to_utc(ts)) is not None
        ]
        self.history: List[Dict[str, Any]] = task_data.get("history", [])

    def __repr__(self) -> str:
        status_char = "[X]" if self.completed else ("[ ]" if self.is_due else "[-]")
        streak_str = f" (Streak: {self.streak})" if self.streak > 0 else ""
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"Daily(id='{self.id}', status='{status_char}', text='{text_preview}'{streak_str})"


class Reward(Task):
    def __init__(self, task_data: Dict[str, Any]):
        super().__init__(task_data)
        self.type = "reward"
        self.value = float(task_data.get("value", 0.0))

    def __repr__(self) -> str:
        cost_str = f" (Cost: {self.value:.0f} GP)"
        text_preview = self.text[:30] + ("..." if len(self.text) > 30 else "")
        return f"Reward(id='{self.id}', text='{text_preview}'{cost_str})"


class TaskList:
    _TASK_TYPE_MAP: Dict[str, type[Task]] = {
        "habit": Habit,
        "daily": Daily,
        "todo": Todo,
        "reward": Reward,
    }

    def __init__(
        self,
        processed_task_list: List[Task],
    ):
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

    def __iter__(self):
        yield from self.tasks

    def __getitem__(self, index: int) -> Task:
        if not isinstance(index, int):
            raise TypeError("Index must be an integer")
        if not 0 <= index < len(self.tasks):
            raise IndexError("Task index out of range")
        return self.tasks[index]

    def get_by_id(self, task_id: str) -> Optional[Task]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def filter_by_type(self, task_type: str) -> TaskList:
        filtered_tasks = [task for task in self.tasks if task.type == task_type]
        return self.__class__(filtered_tasks)

    def filter_by_tag_id(self, tag_id: str) -> TaskList:
        filtered_tasks = [task for task in self.tasks if tag_id in task.tags]
        return self.__class__(filtered_tasks)

    def filter_by_tag_name(self, tag_name: str) -> TaskList:
        if not self.tasks or not hasattr(self.tasks[0], "tag_names"):
            log.warning("Warning: Filtering by tag name, but 'tag_names' may not be populated.")
        filtered_tasks = [
            task for task in self.tasks if hasattr(task, "tag_names") and tag_name in task.tag_names
        ]
        return self.__class__(filtered_tasks)

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
        return self.__class__(filtered)

    def filter_by_attribute(self, attribute: str) -> TaskList:
        filtered_tasks = [task for task in self.tasks if task.attribute == attribute]
        return self.__class__(filtered_tasks)

    def filter_by_status(self, status: str) -> TaskList:
        if not self.tasks or not hasattr(self.tasks[0], "_status"):
            log.warning("Warning: Filtering by status, but '_status' may not be populated.")
        filtered_tasks = [
            task for task in self.tasks if hasattr(task, "_status") and task._status == status
        ]
        return self.__class__(filtered_tasks)

    def filter_completed(self, completed: bool = True) -> List[Union[Daily, Todo]]:
        filtered_tasks = [
            task
            for task in self.tasks
            if isinstance(task, (Daily, Todo)) and task.completed is completed
        ]
        return self.__class__(filtered_tasks)

    def filter_due_dailies(self, due: bool = True) -> List[Daily]:
        filtered_tasks = [
            task for task in self.tasks if isinstance(task, Daily) and task.is_due is due
        ]
        return self.__class__(filtered_tasks)

    def filter_past_due_todos(self) -> List[Todo]:
        filtered_tasks = [
            task for task in self.tasks if isinstance(task, Todo) and task.is_past_due
        ]
        return self.__class__(filtered_tasks)

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
        return self.__class__(filtered)

    def filter_by_habitica(self, by_habitica: bool = True) -> TaskList:
        filtered_tasks = [task for task in self.tasks if task.by_habitica is by_habitica]
        return self.__class__(filtered_tasks)

    def filter_needs_action(self) -> TaskList:
        actionable: List[Task] = []
        for task in self.tasks:
            if isinstance(task, Daily) and task.is_due and not task.completed:
                actionable.append(task)
            elif isinstance(task, Todo) and not task.completed:
                actionable.append(task)
        return self.__class__(actionable)
