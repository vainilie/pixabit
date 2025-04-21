# pixabit/models/challenge.py

# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for Habitica Challenges.
# TODO (Suggestion) Alternatives for Linking: Instead of passing TaskList to ChallengeList.__init__, you could have a separate function link_challenges_and_tasks(challenges: List[Challenge], tasks: List[Task]) that performs the linking. This slightly decouples the list classes.

Includes:
- `Challenge`: Represents a single challenge with its metadata.
- `ChallengeList`: Processes raw challenge data, manages Challenge objects,
  and links associated Task objects.
"""

# SECTION: IMPORTS
from __future__ import annotations

import logging
from datetime import datetime, timezone  # Added timezone
from typing import Any, Dict, List, Optional

import emoji_data_python

# from textual import log # Use standard logger
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# Use standard logger
logger = logging.getLogger(__name__)

# Local Imports - Placeholders if models/utils not found
try:
    # Import Pydantic Task models from the refactored task module
    from pixabit.models.task import (  # Add ChallengeData if needed here, or define locally
        ChallengeData,
        Task,
        TaskList,
    )
except ImportError:
    logger.warning("Using placeholder Task/TaskList in challenge.py.")
    Task = dict  # type: ignore
    TaskList = list  # type: ignore

    # Define placeholder ChallengeData if needed and not imported
    class ChallengeData(BaseModel):
        id: Optional[str] = None


# SECTION: PYDANTIC MODELS


class ChallengeLeader(BaseModel):
    """Represents the leader info nested within challenge data (if object)."""

    model_config = ConfigDict(extra="ignore")  # Ignore extra fields like profile details for now
    id: Optional[str] = Field(None, alias="_id")
    name: Optional[str] = Field(None, description="Leader's display name (from profile).")

    @field_validator("name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> Optional[str]:
        # Assumes name might be within a 'profile' sub-dict in the leader object
        if isinstance(value, dict):  # Check if input is dict (like a profile object)
            name_str = value.get("name")
            if isinstance(name_str, str):
                return emoji_data_python.replace_colons(name_str)
        elif isinstance(value, str):  # Direct name string? Less common but possible
            return emoji_data_python.replace_colons(value)
        return None


class ChallengeGroup(BaseModel):
    """Represents the group info nested within challenge data."""

    model_config = ConfigDict(extra="ignore")
    id: Optional[str] = Field(None, alias="_id")
    name: Optional[str] = None
    type: Optional[Literal[party, guild, tavern]] = None  # Use Literal if types known

    @field_validator("name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> Optional[str]:
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value)
        return None


class Challenge(BaseModel):
    """Represents a Habitica Challenge entity using Pydantic."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: Optional[str] = Field(None, description="Unique challenge ID.")  # Allow None initially
    name: str = Field("Unnamed Challenge", description="Challenge name (emoji parsed).")
    short_name: Optional[str] = Field(
        None, alias="shortName", description="Challenge short name (emoji parsed)."
    )
    summary: str = Field("", description="Challenge summary (emoji parsed).")
    description: str = Field("", description="Challenge description (emoji parsed).")

    # Leader and Group info - parsed from potentially varied input
    leader_id: Optional[str] = Field(None, description="User ID of the challenge leader.")
    leader_name: Optional[str] = Field(
        None, description="Display name of the leader (if available)."
    )
    group_id: Optional[str] = Field(None, description="ID of the associated group.")
    group_name: Optional[str] = Field(
        None, description="Name of the associated group (if available)."
    )
    group_type: Optional[Literal[party, guild, tavern]] = Field(
        None, description="Type of the associated group."
    )

    # Other Attributes
    prize: int = Field(0, description="Gem prize for the challenge winner.")
    member_count: int = Field(0, alias="memberCount", description="Number of participants.")
    official: bool = Field(False, description="Whether this is an official Habitica challenge.")
    created_at: Optional[datetime] = Field(
        None, alias="createdAt", description="Timestamp created (UTC)."
    )
    updated_at: Optional[datetime] = Field(
        None, alias="updatedAt", description="Timestamp updated (UTC)."
    )
    broken: Optional[str] = Field(
        None, description="Status if challenge is broken (e.g., 'CHALLENGE_DELETED')."
    )
    owned: Optional[bool] = Field(
        None, description="Is challenge owned by the fetching user (context-dependent)."
    )

    # Task container - populated externally
    tasks: List[Task] = Field(default_factory=list, description="Tasks belonging to this challenge (populated externally).", exclude=True)  # type: ignore

    # --- Validators ---
    @field_validator("id", mode="before")
    @classmethod
    def handle_id_or_underscore_id(cls, v: Any, info: FieldValidationInfo) -> Optional[str]:
        """Use '_id' if 'id' is not present in source data."""
        if v is None and isinstance(info.data, dict):
            return info.data.get("_id")
        return v

    @field_validator("name", "short_name", "summary", "description", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any) -> Optional[str]:
        """Parses text fields and replaces emoji shortcodes."""
        if isinstance(value, str):
            # Return None for optional fields if empty? Or ""? Depends on desired null handling.
            text = emoji_data_python.replace_colons(value)
            return text  # Keep "" for name, maybe None for others if truly optional?
        return None if value is None else ""  # Default handling

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_utc(cls, value: Any) -> Optional[datetime]:
        """Parses timestamp strings into timezone-aware UTC datetime objects."""
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                return None
        elif isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return None

    @field_validator("prize", "member_count", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensures numeric fields are integers."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    @model_validator(mode="before")
    @classmethod
    def extract_leader_and_group(cls, data: Any) -> Any:
        """Extracts leader and group info from potentially nested/varied structures."""
        if not isinstance(data, dict):
            return data

        values = data.copy()

        # Leader processing
        leader_info = data.get("leader")
        leader_id = None
        leader_name = None
        if isinstance(leader_info, str):
            leader_id = leader_info
        elif isinstance(leader_info, dict):
            leader_id = leader_info.get("_id") or leader_info.get("id")
            leader_profile = leader_info.get("profile", {})
            _leader_disp_name = leader_profile.get("name")
            leader_name = (
                emoji_data_python.replace_colons(_leader_disp_name)
                if isinstance(_leader_disp_name, str)
                else None
            )
        values["leader_id"] = leader_id
        values["leader_name"] = leader_name

        # Group processing
        group_info = data.get("group")
        group_id = None
        group_name = None
        group_type = None
        if isinstance(group_info, dict):
            group_id = group_info.get("_id") or group_info.get("id")
            _group_n = group_info.get("name")
            group_name = (
                emoji_data_python.replace_colons(_group_n) if isinstance(_group_n, str) else None
            )
            group_type = group_info.get("type")
        values["group_id"] = group_id
        values["group_name"] = group_name
        values["group_type"] = group_type

        # Ensure name has a fallback if empty after parsing
        if not values.get("name"):
            values["name"] = "Unnamed Challenge"

        return values

    # --- Methods ---
    def add_tasks(self, tasks_to_add: List[Task]) -> None:  # type: ignore
        """Adds Task objects associated with this challenge."""
        # Add type checking if placeholder Task is replaced
        # self.tasks.extend(task for task in tasks_to_add if isinstance(task, Task))
        self.tasks.extend(tasks_to_add)  # Assume type check happens before call

    def get_tasks_by_type(self, task_type: str) -> List[Task]:  # type: ignore
        """Returns linked tasks of a specific type."""
        # Add type checking if placeholder Task is replaced
        # return [task for task in self.tasks if isinstance(task, Task) and task.type == task_type]
        return [task for task in self.tasks if getattr(task, "type", None) == task_type]

    def __repr__(self) -> str:
        """Concise representation."""
        status = f" (Broken: {self.broken})" if self.broken else ""
        owner_flag = " (Owned)" if self.owned else ""
        official_flag = " (Official)" if self.official else ""
        task_count = len(self.tasks)
        name_preview = self.name[:30] + ("..." if len(self.name) > 30 else "")
        return f"Challenge(id='{self.id}', name='{name_preview}', tasks={task_count}{status}{owner_flag}{official_flag})"


# KLASS: ChallengeList
class ChallengeList:
    """Container for managing Challenge objects, processing raw data, and linking tasks."""

    def __init__(
        self,
        raw_challenge_list: List[Dict[str, Any]],
        task_list: Optional[TaskList] = None,  # Expects TaskList instance
    ):
        """Initializes the ChallengeList.

        Args:
            raw_challenge_list: List of dictionaries (raw challenge data).
            task_list: Optional TaskList containing processed Task objects for linking.
        """
        self.challenges: List[Challenge] = []
        self._process_list(raw_challenge_list)
        logger.info(f"Processed {len(self.challenges)} challenges.")

        if task_list is not None:
            # Check if it looks like our TaskList class (has 'tasks' attribute which is a list)
            if hasattr(task_list, "tasks") and isinstance(getattr(task_list, "tasks", None), list):
                self._link_tasks(task_list)
            else:
                logger.warning(
                    f"task_list provided is not a valid TaskList object (type: {type(task_list)}). Skipping task linking."
                )

    def _process_list(self, raw_challenge_list: List[Dict[str, Any]]) -> None:
        """Processes the raw list, creating Challenge Pydantic instances."""
        processed_challenges: List[Challenge] = []
        if not isinstance(raw_challenge_list, list):
            logger.error(f"raw_challenge_list must be a list, got {type(raw_challenge_list)}.")
            self.challenges = []
            return

        for raw_challenge in raw_challenge_list:
            if not isinstance(raw_challenge, dict):
                logger.warning(
                    f"Skipping invalid non-dict entry in raw_challenge_list: {raw_challenge}"
                )
                continue
            try:
                # Use Pydantic validation to create the instance
                challenge_instance = Challenge.model_validate(raw_challenge)
                if challenge_instance.id:  # Only add valid challenges with an ID
                    processed_challenges.append(challenge_instance)
                else:
                    logger.warning(
                        f"Skipping challenge data missing ID: {raw_challenge.get('name', 'N/A')}"
                    )
            except ValidationError as e:
                logger.error(
                    f"Validation failed for challenge '{raw_challenge.get('name', raw_challenge.get('id', 'N/A'))}':\n{e}"
                )
            except Exception as e:
                logger.error(
                    f"Error processing challenge data for ID {raw_challenge.get('id', 'N/A')}: {e}",
                    exc_info=True,
                )
        self.challenges = processed_challenges

    def _link_tasks(self, task_list: TaskList) -> None:  # type: ignore
        """Links Task objects from the TaskList to the corresponding Challenge objects."""
        challenges_by_id: Dict[str, Challenge] = {
            chal.id: chal for chal in self.challenges if chal.id
        }
        for challenge in self.challenges:
            challenge.tasks = []  # Clear previous links

        linked_count = 0
        # Iterate through tasks from the provided TaskList instance
        for task in task_list:  # Assuming TaskList is iterable
            # Check if task has challenge info and ID (using Pydantic model attributes)
            if task.challenge and isinstance(task.challenge.id, str):
                challenge_id = task.challenge.id
                target_challenge = challenges_by_id.get(challenge_id)
                if target_challenge:
                    target_challenge.tasks.append(task)
                    linked_count += 1
        logger.info(f"Linked {linked_count} tasks to challenges.")
        # Optional: Sort tasks within each challenge
        # for challenge in self.challenges: challenge.tasks.sort(...)

    # --- Access and Filtering Methods ---
    # Filters now return List[Challenge]

    def __len__(self) -> int:
        return len(self.challenges)

    def __iter__(self) -> iter[Challenge]:
        return iter(self.challenges)

    def __getitem__(self, index: int) -> Challenge:
        if not isinstance(index, int):
            raise TypeError("Index must be an integer")
        if not 0 <= index < len(self.challenges):
            raise IndexError("Challenge index out of range")
        return self.challenges[index]

    def get_by_id(self, challenge_id: str) -> Optional[Challenge]:
        """Finds a challenge by its ID."""
        return next((c for c in self.challenges if c.id == challenge_id), None)

    def filter_by_name(self, name_part: str, case_sensitive: bool = False) -> List[Challenge]:
        """Filters challenges by name containing a specific substring."""
        if not case_sensitive:
            name_part_lower = name_part.lower()
            return [c for c in self.challenges if name_part_lower in c.name.lower()]
        else:
            return [c for c in self.challenges if name_part in c.name]

    def filter_by_short_name(self, short_name: str) -> List[Challenge]:
        """Filters challenges by exact short name."""
        return [c for c in self.challenges if c.short_name == short_name]

    def filter_by_leader(self, leader_id: str) -> List[Challenge]:
        """Filters challenges by leader's user ID."""
        return [c for c in self.challenges if c.leader_id == leader_id]

    def filter_by_group(
        self, group_id: Optional[str] = None, group_type: Optional[str] = None
    ) -> List[Challenge]:
        """Filters challenges by group ID and/or group type."""
        filtered = self.challenges
        if group_id is not None:
            filtered = [c for c in filtered if c.group_id == group_id]
        if group_type is not None:
            filtered = [c for c in filtered if c.group_type == group_type]
        return filtered

    def filter_by_official(self, official: bool = True) -> List[Challenge]:
        """Filters for official or unofficial challenges."""
        return [c for c in self.challenges if c.official is official]

    def filter_broken(self, is_broken: bool = True) -> List[Challenge]:
        """Filters challenges based on whether they have a 'broken' status string."""
        if is_broken:
            return [c for c in self.challenges if c.broken is not None]
        else:
            return [c for c in self.challenges if c.broken is None]

    def filter_owned(self, owned: bool = True) -> List[Challenge]:
        """Filters challenges based on the 'owned' flag (if available)."""
        return [c for c in self.challenges if c.owned is owned]

    def filter_by_task_count(
        self, min_tasks: int = 1, max_tasks: Optional[int] = None
    ) -> List[Challenge]:
        """Filters challenges by the number of linked tasks."""
        if max_tasks is None:
            return [c for c in self.challenges if len(c.tasks) >= min_tasks]
        else:
            return [c for c in self.challenges if min_tasks <= len(c.tasks) <= max_tasks]

    def filter_containing_task_id(self, task_id: str) -> List[Challenge]:
        """Filters challenges that contain a specific task ID."""
        return [
            c
            for c in self.challenges
            if any(task.id == task_id for task in c.tasks if hasattr(task, "id"))
        ]

    def __repr__(self) -> str:
        """Simple representation."""
        return f"ChallengeList(count={len(self.challenges)})"
