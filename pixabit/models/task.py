# pixabit/models/task.py

# ─── Title ────────────────────────────────────────────────────────────────────
#         Habitica Task Models (Habits, Dailies, Todos, Rewards)
# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for representing Habitica Tasks (Habits, Dailies,
Todos, Rewards), including nested structures like ChecklistItem and
ChallengeLinkData. Provides a TaskList container for managing and processing
collections of Task objects.
"""

# SECTION: IMPORTS
from __future__ import annotations

import json
import logging
import math
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Iterator, Literal

import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationError,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from pixabit.api.client import HabiticaClient
from pixabit.config import HABITICA_DATA_PATH
from pixabit.helpers._json import save_json
from pixabit.helpers._logger import log
from pixabit.helpers._md_to_rich import MarkdownRenderer
from pixabit.helpers._rich import Text
from pixabit.helpers.DateTimeHandler import DateTimeHandler

if TYPE_CHECKING:
    from .game_content import Quest as StaticQuestData
    from .game_content import StaticContentManager
    from .tag import TagList
    from .user import User

md_renderer = MarkdownRenderer()


# SECTION: NESTED DATA MODELS


# KLASS: ChecklistItem
class ChecklistItem(BaseModel):
    """Represents a single item within a task's checklist."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=False)
    id: str
    text: str = ""
    completed: bool = False

    @model_validator(mode="before")
    @classmethod
    def ensure_id(cls, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        if "id" not in data:
            generated_id = str(uuid.uuid4())
            log.warning(f"Checklist item missing 'id': {data.get('text', 'N/A')}")
            data["id"] = generated_id
        return data

    @field_validator("text", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any) -> str:
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value).strip()
        return ""

    def __repr__(self) -> str:
        status = "[x]" if self.completed else "[ ]"
        text_preview = self.text[:30].replace("\n", " ")
        if len(self.text) > 30:
            text_preview += "..."
        id_preview = self.id[:8] if self.id else "NoID"
        return f"ChecklistItem(id={id_preview}, status='{status}', text='{text_preview}')"

    def __str__(self) -> str:
        return f"{'[x]' if self.completed else '[ ]'} {self.text}"


# KLASS: ChallengeLinkData
class ChallengeLinkData(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)
    task_id: str | None = Field(None, alias="taskId")
    challenge_id: str = Field(..., alias="id")
    short_name: str | None = Field(None, alias="shortName")
    broken_reason: str | None = Field(None, alias="broken")
    is_broken: bool = False
    broken_status: Literal["task_deleted", "challenge_deleted", "unsubscribed", "challenge_closed", "unknown"] | None = None

    @field_validator("short_name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> str | None:
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value).strip()
        return None

    @model_validator(mode="before")
    @classmethod
    def process_broken_status(cls, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            return {} if not data else data
        values = data.copy()
        broken_raw = values.get("broken")
        is_broken_flag = bool(broken_raw)
        broken_status_val = None
        if is_broken_flag and isinstance(broken_raw, str):
            reason = broken_raw.upper().strip()
            match reason:
                case "TASK_DELETED" | "CHALLENGE_TASK_NOT_FOUND":
                    broken_status_val = "task_deleted"
                case "CHALLENGE_DELETED":
                    broken_status_val = "challenge_deleted"
                case "UNSUBSCRIBED":
                    broken_status_val = "unsubscribed"
                case "CHALLENGE_CLOSED":
                    broken_status_val = "challenge_closed"
                case _:
                    broken_status_val = "unknown"
                    log.debug(f"Unknown challenge 'broken' reason: {broken_raw}")
        values["is_broken"] = is_broken_flag
        values["broken_status"] = broken_status_val
        return values

    def __repr__(self) -> str:
        status = f", BROKEN='{self.broken_status}' ({self.broken_reason})" if self.is_broken else ""
        name = f", name='{self.short_name}'" if self.short_name else ""
        chid = self.challenge_id[:8] if self.challenge_id else "NoChalID"
        return f"ChallengeLinkData(challenge_id={chid}{name}{status})"


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: BASE TASK MODEL


# KLASS: Task
class Task(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )
    id: str = Field(..., alias="_id")
    text: str = ""
    notes: str = ""
    type: Literal["habit", "daily", "todo", "reward"] = Field(..., alias="type")
    tags_id: list[str] = Field(default_factory=list, alias="tags")
    value: float = 0.0
    priority: float = 1.0
    attribute: Literal["str", "int", "con", "per"] | None = "str"
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    challenge: ChallengeLinkData | None = None
    alias: str | None = None
    position: int | None = Field(None, exclude=True)
    calculated_status: str = "unknown"
    _styled_text: Text | None = PrivateAttr(default=None)
    _styled_notes: Text | None = PrivateAttr(default=None)
    _tag_names: list[str] = PrivateAttr(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def prepare_data(cls, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            return data
        values = data.copy()
        # Asegurar que siempre tengamos un ID
        if "_id" in values and "id" not in values:
            values["id"] = values["_id"]
        if "id" not in values or not values.get("id"):
            if "_id" not in values:
                values["id"] = str(uuid.uuid4())
                log.debug(f"Generated temporary ID: {values['id'][:8]}")
            else:
                log.warning(f"Task with _id but missing id: {values.get('_id')}")
        # Verificar el tipo de tarea
        if "type" not in values or not isinstance(values.get("type"), str):
            task_id_preview = values.get("id", values.get("_id", "unknown ID"))[:8]
            log.warning(f"Task {task_id_preview} missing valid 'type' field")
        return values

    @field_validator("id", mode="after")
    @classmethod
    def check_id(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise PydanticCustomError("value_error", "Task ID (_id) is required and must be a non-empty string", {"value": v})
        return v

    @field_validator("text", "notes", "alias", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any, info: ValidationInfo) -> str | None:
        is_optional = info.field_name == "alias"
        default = None if is_optional else ""
        if value is None or (isinstance(value, str) and not value.strip()):
            return default
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value).strip()
        log.warning(f"Field '{info.field_name}': Expected string, got {type(value).__name__}")
        return default

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_utc(cls, value: Any) -> datetime | None:
        if isinstance(value, str) and not value.strip():
            return None
        handler = DateTimeHandler(timestamp=value)
        if value is not None and handler.utc_datetime is None and value != "":
            log.warning(f"Could not parse timestamp: {value!r}")
        return handler.utc_datetime

    @field_validator("value", "priority", mode="before")
    @classmethod
    def ensure_float(cls, value: Any, info: ValidationInfo) -> float:
        default = 0.0 if info.field_name == "value" else 1.0
        try:
            if value is None or (isinstance(value, str) and not value.strip()):
                return default
            return float(value)
        except (ValueError, TypeError):
            log.debug(f"Could not parse {info.field_name} as float: {value!r}")
            return default

    @field_validator("attribute", mode="before")
    @classmethod
    def validate_attribute(cls, value: Any) -> str | None:
        allowed = {"str", "int", "con", "per"}
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if value in allowed:
            return value
        log.warning(f"Invalid attribute value '{value}'")
        return None

    @field_validator("challenge", mode="before")
    @classmethod
    def validate_challenge_data(cls, value: Any) -> dict[str, Any] | None:
        if value is None or not value:
            return None
        if isinstance(value, dict):
            return value
        log.warning(f"Unexpected 'challenge' type: {type(value).__name__}")
        return None

    @computed_field(repr=False)
    @property
    def styled_text(self) -> Text:
        if self._styled_text is None:
            self._styled_text = md_renderer.markdown_to_rich_text(self.text or "")
        return self._styled_text

    @computed_field(repr=False)
    @property
    def styled_notes(self) -> Text:
        if self._styled_notes is None:
            self._styled_notes = md_renderer.markdown_to_rich_text(self.notes or "")
        return self._styled_notes

    @computed_field
    @property
    def tag_names(self) -> list[str]:
        return self._tag_names

    def set_tag_names_from_provider(self, tags_provider: TagList | None) -> None:
        resolved_names = []
        if tags_provider and hasattr(tags_provider, "get_by_id"):
            for tag_id in self.tags_id:
                tag = tags_provider.get_by_id(tag_id)
                if tag and hasattr(tag, "name"):
                    resolved_names.append(tag.name)
                else:
                    log.debug(f"Tag ID '{tag_id}' not found for task {self.id}")
                    resolved_names.append(f"Unknown:{tag_id[:6]}")
        elif self.tags_id:
            log.debug(f"No tags_provider for task {self.id[:8]}")
            resolved_names = [f"ID:{tid[:6]}" for tid in self.tags_id]
        self._tag_names = resolved_names

    def process_status_and_metadata(
        self, user: User | None = None, tags_provider: TagList | None = None, content_manager: StaticContentManager | None = None
    ) -> bool:
        try:
            self.set_tag_names_from_provider(tags_provider)
            self.update_calculated_status()
            return True
        except Exception as e:
            log.exception(f"Error processing task {self.id}: {e}")
            return False

    @staticmethod
    def calculate_checklist_progress(checklist: list[ChecklistItem]) -> float:
        if not checklist:
            return 0.0
        completed_count = sum(1 for item in checklist if getattr(item, "completed", False))
        total_count = len(checklist)
        return completed_count / total_count if total_count > 0 else 0.0

    def calculate_value_color(self) -> str:
        value = self.value
        if value <= -20:
            return "red"
        elif value <= -10:
            return "orange"
        elif value < 0:
            return "yellow"
        elif value == 0:
            return "grey"
        elif value < 5:
            return "bright_blue"
        elif value <= 10:
            return "blue"
        else:
            return "green"

    def update_calculated_status(self):
        # Método implementado en subclases
        pass

    def __repr__(self) -> str:
        text_preview = self.text[:25].replace("\n", " ")
        if len(self.text) > 25:
            text_preview += "..."
        prio = f"P{self.priority}" if self.priority != 1.0 else ""
        attr = f"A:{self.attribute or '?'}"
        status = f"S:{self.calculated_status}"
        return f"{self.__class__.__name__}(id='{self.id[:8]}', {prio} {attr} {status} text='{text_preview}')"

    def __str__(self) -> str:
        return self.text


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: TASK SUBCLASSES


# KLASS: Habit
class Habit(Task):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    type: Literal["habit"] = Field("habit", frozen=True)
    up: bool = True
    down: bool = True
    counter_up: int = Field(0, alias="counterUp")
    counter_down: int = Field(0, alias="counterDown")
    frequency: str = "daily"  # 'daily', 'weekly', 'monthly'

    @field_validator("counter_up", "counter_down", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        if value is None:
            return 0
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    def update_calculated_status(self):
        if self.up and self.down:
            self.calculated_status = "good_bad"
        elif self.up:
            self.calculated_status = "good"
        elif self.down:
            self.calculated_status = "bad"
        else:
            self.calculated_status = "neutral"

    def __repr__(self) -> str:
        up_str = f"⬆️{self.counter_up}" if self.up else ""
        down_str = f"⬇️{self.counter_down}" if self.down else ""
        counters = f"{up_str} / {down_str}" if self.up and self.down else (up_str or down_str or "No Score")
        text_preview = self.text[:20].replace("\n", " ")
        if len(self.text) > 20:
            text_preview += "..."
        prio = f"P{self.priority}" if self.priority != 1.0 else ""
        return f"Habit(id='{self.id[:8]}' {prio} ctr='{counters}', text='{text_preview}')"


# KLASS: Daily
class Daily(Task):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    type: Literal["daily"] = Field("daily", frozen=True)
    completed: bool = False
    is_due: bool = Field(False, alias="isDue")
    streak: int = 0
    yesterday_completed: bool = Field(False, alias="yesterDaily")
    collapse_checklist: bool = Field(False, alias="collapseChecklist")
    checklist: list[ChecklistItem] = Field(default_factory=list)
    frequency: Literal["daily", "weekly", "monthly", "yearly"] = "weekly"
    every_x: int = Field(1, alias="everyX")
    repeat: dict[Literal["m", "t", "w", "th", "f", "s", "su"], bool] = Field(default_factory=dict)
    days_of_month: list[int] = Field(default_factory=list, alias="daysOfMonth")
    weeks_of_month: list[int] = Field(default_factory=list, alias="weeksOfMonth")
    start_date: datetime | None = Field(None, alias="startDate")
    _calculated_user_damage: float | None = PrivateAttr(default=None)
    _calculated_party_damage: float | None = PrivateAttr(default=None)

    @field_validator("streak", "every_x", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        default = 1 if value is None else 0
        try:
            val = int(float(value))
            return max(0, val)
        except (ValueError, TypeError):
            return default

    @field_validator("start_date", mode="before")
    @classmethod
    def parse_start_date_utc(cls, value: Any) -> datetime | None:
        handler = DateTimeHandler(timestamp=value)
        return handler.utc_datetime

    def update_calculated_status(self):
        if self.completed:
            self.calculated_status = "complete"
        elif self.is_due:
            self.calculated_status = "due"
        else:
            self.calculated_status = "not_due"

    @computed_field
    @property
    def user_damage(self) -> float | None:
        """Potential damage to user if missed."""
        return self._calculated_user_damage

    @computed_field
    @property
    def party_damage(self) -> float | None:
        """Potential damage to party/boss if missed."""
        return self._calculated_party_damage

    def calculate_and_store_damage(self, user: User, static_content: StaticContentManager | None = None) -> None:
        self._calculated_user_damage = None
        self._calculated_party_damage = None
        # Early returns para casos que no requieren cálculo
        if not self.is_due or self.completed or not user:
            return
        if getattr(user, "is_sleeping", True):
            return
        stealth = getattr(user, "stealth", 0)
        if stealth > 0:
            return
        try:
            eff_stats = getattr(user, "effective_stats", {})
            if not eff_stats:
                log.warning("Cannot calculate damage: No effective stats for user")
                return
            effective_con = eff_stats.get("con", 0.0)
            # Limitar y calcular valor base
            value = max(-47.27, min(self.value, 21.27))
            base_delta = math.pow(0.9747, value)
            # Mitigación por progreso de checklist
            checklist_progress = self.calculate_checklist_progress(self.checklist)
            checklist_mitigation = 1.0 - checklist_progress
            # Delta efectivo y mitigación por CON
            effective_delta = base_delta * checklist_mitigation
            con_mitigation = max(0.1, 1.0 - (effective_con / 250.0))
            # Daño HP calculado
            hp_damage = effective_delta * con_mitigation * self.priority * 2.0
            self._calculated_user_damage = max(0.0, round(hp_damage, 1))
            # Cálculo de daño de grupo si es aplicable
            party_info = getattr(user, "party", None)
            if party_info:
                party_quest_info = getattr(party_info, "quest", None)
                if party_quest_info and getattr(party_quest_info, "is_active_and_ongoing", False):
                    quest_key = getattr(party_quest_info, "key", None)
                    static_quest = getattr(party_info, "_static_quest_details", None)
                    if static_quest is None and quest_key and static_content:
                        log.warning(f"Static quest details not pre-fetched for {quest_key}")
                    if static_quest and getattr(static_quest, "is_boss_quest", False):
                        boss_stats = getattr(static_quest, "boss", None)
                        if boss_stats:
                            boss_strength = getattr(boss_stats, "strength", 0.0)
                            if boss_strength > 0:
                                party_delta = effective_delta * self.priority
                                party_damage = party_delta * boss_strength
                                self._calculated_party_damage = max(0.0, round(party_damage, 1))
            log.debug(
                f"Daily {self.id}: UserDmg={self._calculated_user_damage}, "
                f"PartyDmg={self._calculated_party_damage}, Value:{value:.1f}, "
                f"Prio:{self.priority:.1f}, Chk:{checklist_progress:.2f}"
            )
        except AttributeError as ae:
            log.error(f"AttributeError during damage calc for Daily {self.id}: {ae}")
        except Exception as e:
            log.exception(f"Error calculating damage for daily {self.id}: {e}")
            self._calculated_user_damage = None
            self._calculated_party_damage = None

    def process_status_and_metadata(
        self, user: User | None = None, tags_provider: TagList | None = None, content_manager: StaticContentManager | None = None
    ) -> bool:
        result = super().process_status_and_metadata(user, tags_provider, content_manager)
        if result and user:
            try:
                self.calculate_and_store_damage(user, content_manager)
            except Exception as e:
                log.exception(f"Error calculating damage: {e}")
                return False
        return result

    def __repr__(self) -> str:
        status = self.calculated_status.upper()
        streak_str = f" (Strk:{self.streak})" if self.streak > 0 else ""
        dmg_str = f" (DmgU:{self.user_damage or 0:.1f}|P:{self.party_damage or 0:.1f})" if self.is_due and not self.completed else ""
        checklist_str = f" Chk:{len(self.checklist)}" if self.checklist else ""
        text_preview = self.text[:15].replace("\n", " ")
        if len(self.text) > 15:
            text_preview += "..."
        prio = f"P{self.priority}" if self.priority != 1.0 else ""
        return f"Daily(id='{self.id[:8]}' {prio} S:{status}{streak_str}" f"{checklist_str}{dmg_str}, text='{text_preview}')"


# KLASS: Todo
class Todo(Task):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    type: Literal["todo"] = Field("todo", frozen=True)
    completed: bool = False
    completed_date: datetime | None = Field(None, alias="dateCompleted")
    due_date: datetime | None = Field(None, alias="date")
    collapse_checklist: bool = Field(False, alias="collapseChecklist")
    checklist: list[ChecklistItem] = Field(default_factory=list)

    @field_validator("completed_date", "due_date", mode="before")
    @classmethod
    def parse_todo_datetime_utc(cls, value: Any) -> datetime | None:
        if value == "":
            return None
        handler = DateTimeHandler(timestamp=value)
        return handler.utc_datetime

    @property
    def is_past_due(self) -> bool:
        if self.completed or not self.due_date:
            return False
        now_utc = datetime.now(timezone.utc)
        return self.due_date < now_utc

    def update_calculated_status(self):
        if self.completed:
            self.calculated_status = "complete"
        elif not self.due_date:
            self.calculated_status = "no_due_date"
        elif self.is_past_due:
            self.calculated_status = "past_due"
        else:
            self.calculated_status = "due"

    def calculate_progress(self) -> float:
        if self.completed:
            return 1.0
        return self.calculate_checklist_progress(self.checklist)

    def __repr__(self) -> str:
        status = self.calculated_status.upper()
        due_str = f", due={self.due_date.strftime('%y-%m-%d')}" if self.due_date else ""
        checklist_str = f" Chk:{len(self.checklist)}" if self.checklist else ""
        progress = self.calculate_progress()
        prog_str = f" Prg:{progress:.0%}" if progress < 1.0 and self.checklist else ""
        text_preview = self.text[:15].replace("\n", " ")
        if len(self.text) > 15:
            text_preview += "..."
        prio = f"P{self.priority}" if self.priority != 1.0 else ""
        return f"Todo(id='{self.id[:8]}' {prio} S:{status}{due_str}" f"{checklist_str}{prog_str}, text='{text_preview}')"


class Reward(Task):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    type: Literal["reward"] = Field("reward", frozen=True)
    value: float  # Gold cost of the reward

    def update_calculated_status(self):
        self.calculated_status = "available"

    def __repr__(self) -> str:
        cost_str = f"(Cost: {self.value:.1f} GP)"
        text_preview = self.text[:25].replace("\n", " ")
        if len(self.text) > 25:
            text_preview += "..."
        return f"Reward(id='{self.id[:8]}' {cost_str} text='{text_preview}')"


# Tipo unión para cualquier tarea
AnyTask = Habit | Daily | Todo | Reward

# ──────────────────────────────────────────────────────────────────────────────


# SECTION: TASK LIST CONTAINER / MANAGER


# KLASS: TaskList
class TaskList(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    tasks: list[Task] = Field(default_factory=list, description="List of all Task objects.")

    _raw_tasks_data: list[dict[str, Any]] | None = PrivateAttr(default=None)
    _tasks_by_id: dict[str, Task] = PrivateAttr(default_factory=dict)
    _tasks_by_type: dict[Literal["habit", "daily", "todo", "reward"], list[Task]] = PrivateAttr(default_factory=lambda: defaultdict(list))
    _tags_provider: TagList | None = PrivateAttr(default=None)
    _user_data: User | None = PrivateAttr(default=None)
    _content_manager: StaticContentManager | None = PrivateAttr(default=None)

    @classmethod
    def from_raw_api_list(
        cls,
        raw_data: list[dict[str, Any]],
        user: User | None = None,
        tags_provider: TagList | None = None,
        content_manager: StaticContentManager | None = None,
    ) -> TaskList:
        """Create a TaskList from raw API data with error handling and logging."""
        parsed_tasks: list[Task] = []
        errors: list[tuple[str, str, Exception]] = []

        log.info(f"Parsing {len(raw_data)} raw task entries from API")

        type_map: dict[str, type[Task]] = {
            "habit": Habit,
            "daily": Daily,
            "todo": Todo,
            "reward": Reward,
        }

        for i, item in enumerate(raw_data):
            type_str = str(item.get("type", "")).lower()
            task_model = type_map.get(type_str)

            if not task_model:
                task_id = item.get("_id", item.get("id", "unknown"))[:8]
                log.warning(f"Skipping item {i} (ID: {task_id}) with unknown type '{type_str}'")
                continue

            try:
                task = task_model(**item)
                task.position = i
                parsed_tasks.append(task)
            except ValidationError as e:
                task_id = item.get("_id", item.get("id", "unknown"))[:8]
                log.error(f"Validation error for task {task_id} (Type: {type_str}): {e}")
                errors.append((item.get("_id", "N/A"), type_str, e))
            except Exception as e:
                task_id = item.get("_id", item.get("id", "unknown"))[:8]
                log.exception(f"Error parsing task {task_id} (Type: {type_str}): {e}")
                errors.append((item.get("_id", "N/A"), type_str, e))

        log.info(f"Successfully parsed {len(parsed_tasks)} tasks. Encountered {len(errors)} errors")

        instance = cls(tasks=parsed_tasks)
        instance._raw_tasks_data = raw_data
        instance._user_data = user
        instance._tags_provider = tags_provider
        instance._content_manager = content_manager
        instance.process_tasks(user=user, tags_provider=tags_provider, content_manager=content_manager)

        return instance

    @classmethod
    def from_processed_dicts(cls, processed_task_dicts: list[dict[str, Any]]) -> TaskList:
        """Create a TaskList from pre-processed task dictionaries."""
        if not isinstance(processed_task_dicts, list):
            log.error(f"Invalid input: Expected list, got {type(processed_task_dicts)}")
            return cls(tasks=[])

        log.debug(f"Processing {len(processed_task_dicts)} task dictionaries")

        validated_tasks: list[AnyTask] = []
        task_map = {"habit": Habit, "daily": Daily, "todo": Todo, "reward": Reward}

        for index, task_data in enumerate(processed_task_dicts):
            if not isinstance(task_data, dict):
                continue

            type = task_data.get("type")
            model_class = task_map.get(type)

            if not model_class:
                task_id = task_data.get("id", f"index_{index}")
                log.warning(f"Unknown task type '{type!r}' for task ID '{task_id}'. Skipping")
                continue

            try:
                task = model_class.model_validate(task_data)
                validated_tasks.append(task)
            except Exception as e:
                task_id = task_data.get("id", f"index_{index}")
                log.exception(f"Error validating task '{task_id}' (Type: {type}): {e}")

        log.info(f"Validated {len(validated_tasks)} tasks from processed dictionary data")
        return cls(tasks=validated_tasks)

    def process_tasks(
        self,
        user: User | None = None,
        tags_provider: TagList | None = None,
        content_manager: StaticContentManager | None = None,
    ) -> None:
        """Process metadata for all tasks and organize them by ID and type."""
        log.info(f"Processing {len(self.tasks)} tasks")

        # Update instance attributes if provided
        if user:
            self._user_data = user
        if tags_provider:
            self._tags_provider = tags_provider
        if content_manager:
            self._content_manager = content_manager

        # Reset internal dictionaries
        self._tasks_by_id = {}
        self._tasks_by_type = defaultdict(list)

        # Process each task
        for i, task in enumerate(self.tasks):
            task.position = i
            self._tasks_by_id[task.id] = task
            self._tasks_by_type[task.type].append(task)
            task.process_status_and_metadata(user=self._user_data, tags_provider=self._tags_provider, content_manager=self._content_manager)

        log.info("Task processing complete")

    def get_task_by_id(self, task_id: str) -> Task | None:
        """Get a task by its ID."""
        return self._tasks_by_id.get(task_id)

    def get_tasks_by_type(self, type: Literal["habit", "daily", "todo", "reward"]) -> list[Task]:
        """Get all tasks of a specific type."""
        return self._tasks_by_type.get(type, [])

    def add_task(self, task_data: dict[str, Any] | Task) -> Task | None:
        """Add a new task to the list and all internal data structures."""
        # Determine task type and model
        if isinstance(task_data, Task):
            type_str = task_data.type
            new_task = task_data
        elif isinstance(task_data, dict):
            type_str = str(task_data.get("type", "")).lower()

            type_map: dict[str, type[Task]] = {
                "habit": Habit,
                "daily": Daily,
                "todo": Todo,
                "reward": Reward,
            }

            task_model = type_map.get(type_str)
            if not task_model:
                log.error(f"Cannot add task with unknown type '{type_str}'")
                return None

            try:
                new_task = task_model(**task_data)
            except ValidationError as e:
                task_id = task_data.get("_id", task_data.get("id", "unknown"))[:8]
                log.error(f"Validation error adding task {task_id}: {e}")
                return None
            except Exception as e:
                task_id = task_data.get("_id", task_data.get("id", "unknown"))[:8]
                log.exception(f"Error adding task {task_id}: {e}")
                return None
        else:
            log.error(f"Invalid input type: {type(task_data).__name__}. Expected dict or Task")
            return None

        # Check for duplicate ID
        if new_task.id in self._tasks_by_id:
            log.warning(f"Task ID {new_task.id[:8]} already exists")
            return self._tasks_by_id[new_task.id]

        # Add to collections
        self.tasks.append(new_task)
        self._tasks_by_id[new_task.id] = new_task
        self._tasks_by_type[new_task.type].append(new_task)
        new_task.position = len(self.tasks) - 1

        # Process task metadata
        success = new_task.process_status_and_metadata(user=self._user_data, tags_provider=self._tags_provider, content_manager=self._content_manager)

        if not success:
            log.warning(f"Failed to process metadata for task {new_task.id[:8]}")

        log.info(f"Added task: {new_task.id[:8]} (Type: {new_task.type})")
        return new_task

    def edit_task(self, task_id: str, update_data: dict[str, Any]) -> Task | None:
        """Update an existing task with new data."""
        task = self.get_task_by_id(task_id)
        if not task:
            log.warning(f"Task ID {task_id[:8]} not found for editing")
            return None
        try:
            # Use Pydantic's update mechanism
            updated_task = task.model_validate(update_data, update=True)

            # Process updated task metadata
            success = updated_task.process_status_and_metadata(user=self._user_data, tags_provider=self._tags_provider, content_manager=self._content_manager)

            if not success:
                log.warning(f"Failed to process metadata for edited task {task_id[:8]}")

            log.info(f"Edited task: {task_id[:8]} (Type: {updated_task.type})")
            return updated_task
        except ValidationError as e:
            log.error(f"Validation error editing task {task_id[:8]}: {e}")
            return None
        except Exception as e:
            log.exception(f"Error editing task {task_id[:8]}: {e}")
            return None

    def delete_task(self, task_id: str) -> Task | None:
        """Remove a task from the list and all internal data structures."""
        task = self.get_task_by_id(task_id)
        if not task:
            log.warning(f"Task ID {task_id[:8]} not found for deletion")
            return None

        try:
            # Remove from main list
            try:
                self.tasks.remove(task)
            except ValueError:
                log.warning(f"Task {task_id[:8]} not found in main tasks list")

            # Remove from type-specific list
            type = task.type
            if type in self._tasks_by_type:
                try:
                    self._tasks_by_type[type].remove(task)
                except ValueError:
                    log.warning(f"Task {task_id[:8]} not found in type list for '{type}'")

            # Remove from ID dictionary
            if task_id in self._tasks_by_id:
                del self._tasks_by_id[task_id]
            else:
                log.warning(f"Task ID {task_id[:8]} not found in ID dictionary")

            log.info(f"Deleted task: {task_id[:8]} (Type: {task.type})")
            return task
        except Exception as e:
            log.exception(f"Error deleting task {task_id[:8]}: {e}")
            return None

    def reorder_tasks(self, type: Literal["habit", "daily", "todo", "reward"], new_order_ids: list[str]) -> None:
        """Reorder tasks of a specific type according to a new ID order."""
        if type not in self._tasks_by_type:
            log.warning(f"No tasks found for type '{type}'")
            return

        # Get current tasks of this type
        current_tasks = self.get_tasks_by_type(type)
        tasks_dict = {task.id: task for task in current_tasks}

        # Create new ordered list
        reordered_tasks = []
        seen_ids = set()

        # First add tasks that are in the new order
        for task_id in new_order_ids:
            if task_id in tasks_dict and task_id not in seen_ids:
                reordered_tasks.append(tasks_dict[task_id])
                seen_ids.add(task_id)
            elif task_id in seen_ids:
                log.warning(f"Duplicate task ID '{task_id[:8]}' in new_order_ids")
            else:
                log.warning(f"Task ID '{task_id[:8]}' not found in current tasks")

        # Add any remaining tasks at the end
        missing_ids = set(tasks_dict.keys()) - seen_ids
        if missing_ids:
            log.warning(f"Tasks not in new_order_ids will be appended: {list(missing_ids)[:5]}")
            for task_id in missing_ids:
                reordered_tasks.append(tasks_dict[task_id])

        # Update type-specific list
        self._tasks_by_type[type] = reordered_tasks

        # Rebuild global task list in the desired display order
        log.info(f"Rebuilding global task list after reordering '{type}'")
        new_global_tasks = []
        processed_ids = set()

        # Define preferred display order
        type_display_order = ["daily", "todo", "habit", "reward"]
        all_types = set(self._tasks_by_type.keys())
        ordered_types = []

        # First add types in preferred order
        for t in type_display_order:
            if t in all_types:
                ordered_types.append(t)
                all_types.remove(t)

        # Then add any remaining types
        ordered_types.extend(sorted(all_types))

        # Build new global list in the correct order
        for current_type in ordered_types:
            for task in self._tasks_by_type.get(current_type, []):
                if task.id not in processed_ids:
                    new_global_tasks.append(task)
                    processed_ids.add(task.id)
                else:
                    log.warning(f"Duplicate task ID '{task.id[:8]}' while rebuilding global list")

        # Update global list and reprocess
        self.tasks = new_global_tasks
        self.process_tasks(user=self._user_data, tags_provider=self._tags_provider, content_manager=self._content_manager)

        log.info(f"Reordering complete for tasks of type '{type}'")

    # Collection-like methods
    def __len__(self) -> int:
        return len(self.tasks)

    def __iter__(self) -> Iterator[AnyTask]:
        return iter(self.tasks)

    def __getitem__(self, index: int | slice) -> AnyTask | list[AnyTask]:
        if isinstance(index, int) and not 0 <= index < len(self.tasks):
            raise IndexError("TaskList index out of range")
        return self.tasks[index]

    def __contains__(self, item: AnyTask | str) -> bool:
        if isinstance(item, str):
            return item in self._tasks_by_id
        return item in self.tasks

    def __repr__(self) -> str:
        counts = defaultdict(int)
        for task in self.tasks:
            counts[task.type] += 1
        count_str = ", ".join(f"{t}:{c}" for t, c in sorted(counts.items()))
        return f"TaskList(count={len(self.tasks)}, types=[{count_str}])"

    def __str__(self) -> str:
        task_summary = [f"{type.capitalize()}s: {len(self.get_tasks_by_type(type))}" for type in self._tasks_by_type.keys() if self.get_tasks_by_type(type)]
        return f"TaskList contains: {', '.join(task_summary) or 'No tasks'}"

    # Helper methods for filtering
    def get_by_id(self, task_id: str) -> AnyTask | None:
        """Get a task by its ID - alias for get_task_by_id."""
        return self._tasks_by_id.get(task_id)

    def filter(self, criteria_func: callable[[AnyTask], bool]) -> TaskList:
        """Filter tasks based on a custom criteria function."""
        filtered_tasks = [task for task in self.tasks if criteria_func(task)]
        return TaskList(tasks=filtered_tasks)

    def filter_by_type(self, type: Literal["habit", "daily", "todo", "reward"]) -> TaskList:
        """Filter tasks by type."""
        return TaskList(tasks=self.get_tasks_by_type(type))

    def filter_by_status(self, status: str) -> TaskList:
        """Filter tasks by calculated status."""
        return self.filter(lambda task: task.calculated_status == status)

    def filter_by_tag_id(self, tag_id: str) -> TaskList:
        """Filter tasks by tag ID."""
        return self.filter(lambda task: tag_id in task.tags_id)

    def filter_by_tag_name(self, tag_name: str, case_sensitive: bool = False) -> TaskList:
        """Filter tasks by tag name."""
        if case_sensitive:
            return self.filter(lambda task: tag_name in task.tag_names)

        tag_name_lower = tag_name.lower()
        return self.filter(lambda task: any(tag_name_lower in tn.lower() for tn in task.tag_names))

    def filter_by_text(self, text_part: str, case_sensitive: bool = False) -> TaskList:
        """Filter tasks by text content."""
        if case_sensitive:
            return self.filter(lambda task: text_part in task.text)

        text_part_lower = text_part.lower()
        return self.filter(lambda task: text_part_lower in task.text.lower())

    # Convenience methods for common task types
    def get_habits(self) -> TaskList:
        """Get all habits."""
        return self.filter_by_type("habit")

    def get_dailies(self) -> TaskList:
        """Get all dailies."""
        return self.filter_by_type("daily")

    def get_todos(self) -> TaskList:
        """Get all todos."""
        return self.filter_by_type("todo")

    def get_rewards(self) -> TaskList:
        """Get all rewards."""
        return self.filter_by_type("reward")

    # Serialization methods
    def to_dicts(self) -> list[dict[str, Any]]:
        """Convert all tasks to dictionaries."""
        return [task.model_dump(mode="json", exclude={"styled_text", "styled_notes"}) for task in self.tasks]

    def save_to_json(self, filename: str, folder: Path) -> bool:
        """Save tasks to a JSON file in the specified folder."""
        data = self.to_dicts()
        log.info(f"Saving {len(data)} tasks to {folder / filename}")

        try:
            return save_json(data, filename, folder=folder)
        except Exception as e:
            log.exception(f"Error saving tasks to JSON: {e}")
            return False

    @classmethod
    def load_from_json(
        cls,
        file_path: Path | str,
        user: User | None = None,
        tags_provider: TagList | None = None,
        content_manager: StaticContentManager | None = None,
    ) -> TaskList | None:
        """Load tasks from a JSON file."""
        path = Path(file_path)
        try:
            with open(path, encoding="utf-8") as f:
                raw_data = json.load(f)

            if not isinstance(raw_data, list):
                log.error(f"Expected JSON list of tasks in {path}, got {type(raw_data).__name__}")
                return None

            task_list = cls.from_raw_api_list(raw_data, user, tags_provider, content_manager)
            log.info(f"TaskList loaded from {path}")
            return task_list

        except FileNotFoundError:
            log.error(f"JSON file not found: {path}")
            return None
        except json.JSONDecodeError as e:
            log.error(f"Error decoding JSON from {path}: {e}")
            return None
        except Exception as e:
            log.exception(f"Error loading TaskList from {path}: {e}")
            return None


# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MAIN EXECUTION (Example/Test)


async def main():
    """Demo function to retrieve, process, and save tasks."""
    log.info("--- Task Models Demo ---")
    tasks_list_instance: TaskList | None = None
    try:
        cache_dir = HABITICA_DATA_PATH / "tasks"
        cache_dir.mkdir(exist_ok=True, parents=True)
        raw_path = cache_dir / "tasks_raw.json"
        processed_path = cache_dir / "tasks_processed.json"

        # 1. Fetch raw data
        log.info("Fetching tasks from API...")
        api = HabiticaClient()  # Assumes configured
        raw_data = await api.get_tasks()
        log.success(f"Fetched {len(raw_data)} raw task items.")
        save_json(raw_data, raw_path.name, folder=raw_path.parent)  # Save raw data

        # 2. Validate and create TaskList
        log.info("Validating raw data into TaskList...")
        tasks_list_instance = TaskList.from_raw_api_list()
        log.success(f"Created TaskList: {tasks_list_instance}")

        # 3. Process Tasks (Requires User, TagList, ContentManager - Mocked for demo if needed)
        log.info("Processing task statuses (requires User/Tags/Content)...")

        # 4. Example Access/Filtering
        dailies = tasks_list_instance.get_dailies()
        print(f"  - Number of Dailies: {len(dailies)}")
        if dailies:
            first_daily = dailies[0]
            print(f"  - First Daily: {first_daily}")
            # Access calculated damage (will be None if User was missing)
            print(f"    -> Calculated User Damage: {getattr(first_daily, 'user_damage', 'N/A')}")

        # 5. Save processed data
        log.info(f"Saving processed tasks to {processed_path}...")
        if tasks_list_instance.save_to_json(processed_path.name, folder=processed_path.parent):
            log.success("Processed tasks saved.")
        else:
            log.error("Failed to save processed tasks.")

    except ConnectionError as e:
        log.error(f"API Connection error: {e}")
    except ValidationError as e:
        log.error(f"Pydantic Validation Error: {e}")
    except Exception as e:
        log.exception(f"An unexpected error occurred in the task demo: {e}")

    return tasks_list_instance


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(main())

# ──────────────────────────────────────────────────────────────────────────────
