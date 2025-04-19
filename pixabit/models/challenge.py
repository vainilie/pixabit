# pixabit/models/challenge.py

# SECTION: MODULE DOCSTRING
"""Defines data model classes for representing Habitica Challenges and their tasks.

Includes:
- `Challenge`: Represents a single challenge with its metadata.
- `ChallengeList`: A container class to manage a collection of Challenge objects,
  including linking associated tasks and providing filtering methods.
"""

# SECTION: IMPORTS
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional  # Keep Dict/List for clarity

import emoji_data_python
from rich.logging import RichHandler
from textual import log

from pixabit.utils.display import console

FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)])

# Local Imports (assuming utils and models are siblings or configured in path)
try:
    from pixabit.models.task import (
        Task,
        TaskList,
    )  # Import Task and TaskList models
    from pixabit.utils.dates import convert_timestamp_to_utc
except ImportError:
    # Fallback placeholders if imports fail (e.g., during testing/dev)
    log.warning("Warning: Using placeholder Task/TaskList/convert_timestamp_to_utc in challenge.py.")
    Task = dict  # type: ignore
    TaskList = list  # type: ignore

    def convert_timestamp_to_utc(ts: Any) -> Optional[datetime]:  # noqa: D103
        return None  # type: ignore


# SECTION: DATA CLASSES


# KLASS: Challenge
class Challenge:
    """Represents a Habitica Challenge entity.

    Attributes are parsed from the Habitica API challenge object format.
    Tasks associated with the challenge are typically added externally.
    """

    # FUNC: __init__
    def __init__(self, challenge_data: Dict[str, Any]):
        """Initializes a Challenge object from API data dictionary.

        Args:
            challenge_data: A dictionary containing the raw challenge data from the API.

        Raises:
            TypeError: If challenge_data is not a dictionary.
        """
        if not isinstance(challenge_data, dict):
            raise TypeError("challenge_data must be a dictionary.")

        self.id: Optional[str] = challenge_data.get("id") or challenge_data.get("_id")
        _name = challenge_data.get("name", "Unnamed Challenge")
        self.name: str = emoji_data_python.replace_colons(_name) if _name else "Unnamed Challenge"
        _short_name = challenge_data.get("shortName")
        self.short_name: Optional[str] = emoji_data_python.replace_colons(_short_name) if _short_name else None
        _summary = challenge_data.get("summary", "")
        self.summary: str = emoji_data_python.replace_colons(_summary) if _summary else ""
        _description = challenge_data.get("description", "")
        self.description: str = emoji_data_python.replace_colons(_description) if _description else ""

        # Leader Info (can be string ID or object)
        leader_info = challenge_data.get("leader")
        self.leader_id: Optional[str] = None
        self.leader_name: Optional[str] = None  # Store name if available
        if isinstance(leader_info, str):
            self.leader_id = leader_info
        elif isinstance(leader_info, dict):
            self.leader_id = leader_info.get("_id")
            # Attempt to get name from common profile structure
            leader_profile = leader_info.get("profile", {})
            _leader_disp_name = leader_profile.get("name")
            self.leader_name = emoji_data_python.replace_colons(_leader_disp_name) if _leader_disp_name else None

        # Group Info
        group_info = challenge_data.get("group", {})
        self.group_id: Optional[str] = group_info.get("_id") if isinstance(group_info, dict) else None
        _group_name = group_info.get("name") if isinstance(group_info, dict) else None
        self.group_name: Optional[str] = emoji_data_python.replace_colons(_group_name) if _group_name else None
        self.group_type: Optional[str] = group_info.get("type") if isinstance(group_info, dict) else None  # 'party', 'guild', 'tavern'

        # Other Attributes
        self.prize: int = int(challenge_data.get("prize", 0))
        self.member_count: int = int(challenge_data.get("memberCount", 0))
        self.official: bool = challenge_data.get("official", False)
        self.created_at: Optional[datetime] = convert_timestamp_to_utc(challenge_data.get("createdAt"))
        self.updated_at: Optional[datetime] = convert_timestamp_to_utc(challenge_data.get("updatedAt"))
        self.broken: Optional[str] = challenge_data.get("broken")  # e.g., "CHALLENGE_DELETED"
        self.owned: Optional[bool] = challenge_data.get("owned")  # May be present if fetched via /user/challenges

        # Task container - populated externally (e.g., by ChallengeList._link_tasks)
        self.tasks: List[Task] = []  # type: ignore # Type hint using imported Task

    # FUNC: add_tasks
    def add_tasks(self, tasks_to_add: List[Task]) -> None:  # type: ignore
        """Adds a list of Task objects associated with this challenge.

        Args:
            tasks_to_add: A list of Task model objects.
        """
        # Basic check to add only Task instances (or subclasses)
        self.tasks.extend(task for task in tasks_to_add if isinstance(task, Task))
        # Optional: Sort tasks after adding
        # self.tasks.sort(key=lambda t: (t.type, getattr(t, 'position', 0)))

    # FUNC: get_tasks_by_type
    def get_tasks_by_type(self, task_type: str) -> List[Task]:  # type: ignore
        """Returns a list of linked tasks belonging to this challenge of a specific type.

        Args:
            task_type: The task type string ('habit', 'daily', 'todo', 'reward').

        Returns:
            A list of matching Task objects.
        """
        return [task for task in self.tasks if task.type == task_type]

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        status = f" (Broken: {self.broken})" if self.broken else ""
        owner_flag = " (Owned)" if self.owned else ""
        official_flag = " (Official)" if self.official else ""
        task_count = len(self.tasks)
        name_preview = self.name[:30] + ("..." if len(self.name) > 30 else "")
        return f"Challenge(id='{self.id}', name='{name_preview}', " f"tasks={task_count}{status}{owner_flag}{official_flag})"


# KLASS: ChallengeList
class ChallengeList:
    """Container for managing a list of Challenge objects.

    Processes raw challenge data, links associated tasks from a TaskList,
    and provides filtering capabilities.
    """

    # FUNC: __init__
    def __init__(
        self,
        raw_challenge_list: List[Dict[str, Any]],
        task_list: Optional[TaskList] = None,  # type: ignore  # Expects a TaskList object # type: ignore
    ):
        """Initializes the ChallengeList.

        Args:
            raw_challenge_list: List of dictionaries (raw challenge data from API).
            task_list: An optional TaskList instance containing processed Task objects.
                       If provided, tasks will be linked to their respective challenges.
        """
        self.challenges: List[Challenge] = []
        self._process_list(raw_challenge_list)

        if task_list is not None:
            # Ensure task_list is actually a TaskList instance (or duck-types)
            if hasattr(task_list, "tasks") and isinstance(task_list.tasks, list):
                self._link_tasks(task_list)
            else:
                log.warning(f"Warning: task_list provided to ChallengeList is not a valid TaskList object (type: {type(task_list)}). Skipping task linking.")

    # FUNC: _process_list
    def _process_list(self, raw_challenge_list: List[Dict[str, Any]]) -> None:
        """Processes the raw list, creating Challenge instances."""
        processed_challenges: List[Challenge] = []
        if not isinstance(raw_challenge_list, list):
            log.error(f"Error: raw_challenge_list must be a list, got {type(raw_challenge_list)}. Cannot process.")
            self.challenges = []
            return

        for raw_challenge in raw_challenge_list:
            if not isinstance(raw_challenge, dict):
                log.warning(f"Skipping invalid entry in raw_challenge_list: {raw_challenge}")
                continue
            try:
                challenge_instance = Challenge(raw_challenge)
                if challenge_instance.id:  # Only add valid challenges with an ID
                    processed_challenges.append(challenge_instance)
                else:
                    log.warning(f"Skipping challenge data missing ID: {raw_challenge.get('name', 'N/A')}")
            except Exception as e:
                log.error(f"Error processing challenge data for ID {raw_challenge.get('id', 'N/A')}: {e}")
        self.challenges = processed_challenges

    # FUNC: _link_tasks
    def _link_tasks(self, task_list: TaskList) -> None:  # type: ignore
        """Links Task objects from the TaskList to the corresponding Challenge objects.

        Assumes Task objects have a 'challenge' attribute which is a ChallengeData object
        containing the challenge ID. Modifies the `tasks` list within each Challenge object.

        Args:
            task_list: The TaskList instance containing processed Task objects.
        """
        # Create a map for faster challenge lookup by ID
        challenges_by_id: Dict[str, Challenge] = {chal.id: chal for chal in self.challenges if chal.id}

        # Clear existing tasks lists in challenges before linking
        for challenge in self.challenges:
            challenge.tasks = []

        linked_count = 0
        # Iterate through all tasks in the TaskList
        for task in task_list.tasks:  # Iterate through the tasks attribute of TaskList
            # Check if the task belongs to a challenge and has the necessary info
            # Assumes Task has a `challenge` attribute which is a ChallengeData object or None
            if task.challenge and isinstance(task.challenge.id, str):
                challenge_id = task.challenge.id
                # Find the corresponding challenge object in our list
                target_challenge = challenges_by_id.get(challenge_id)
                if target_challenge:
                    # Add the task object to that challenge's task list
                    target_challenge.tasks.append(task)
                    linked_count += 1

        # Optional: Sort tasks within each challenge after linking all of them
        # for challenge in self.challenges:
        #     challenge.tasks.sort(key=lambda t: (t.type, getattr(t, 'position', 0)))
        # print(f"Linked {linked_count} tasks to challenges.") # Debug log

    # SECTION: Access and Filtering Methods

    # FUNC: __len__
    def __len__(self) -> int:
        """Returns the number of challenges in the list."""
        return len(self.challenges)

    # FUNC: __iter__
    def __iter__(self):
        """Allows iterating over the Challenge objects in the list."""
        yield from self.challenges

    # FUNC: __getitem__
    def __getitem__(self, index: int) -> Challenge:
        """Allows accessing challenges by index."""
        if not isinstance(index, int):
            raise TypeError("Index must be an integer")
        if not 0 <= index < len(self.challenges):
            raise IndexError("Challenge index out of range")
        return self.challenges[index]

    # FUNC: get_by_id
    def get_by_id(self, challenge_id: str) -> Optional[Challenge]:
        """Finds a challenge by its ID.

        Args:
            challenge_id: The ID string of the challenge to find.

        Returns:
            The Challenge object if found, otherwise None.
        """
        for challenge in self.challenges:
            if challenge.id == challenge_id:
                return challenge
        return None

    # FUNC: filter_by_name
    def filter_by_name(self, name_part: str, case_sensitive: bool = False) -> List[Challenge]:
        """Filters challenges by name containing a specific substring.

        Args:
            name_part: The substring to search for in the challenge name.
            case_sensitive: Whether the search should be case-sensitive (default: False).

        Returns:
            A list of matching Challenge objects.
        """
        if not case_sensitive:
            name_part_lower = name_part.lower()
            return [c for c in self.challenges if name_part_lower in c.name.lower()]
        else:
            return [c for c in self.challenges if name_part in c.name]

    # FUNC: filter_by_short_name
    def filter_by_short_name(self, short_name: str) -> List[Challenge]:
        """Filters challenges by exact short name.

        Args:
            short_name: The exact short name to match.

        Returns:
            A list of matching Challenge objects.
        """
        # Note: short_name can be None, handle this comparison
        return [c for c in self.challenges if c.short_name == short_name]

    # FUNC: filter_by_leader
    def filter_by_leader(self, leader_id: str) -> List[Challenge]:
        """Filters challenges by leader's user ID.

        Args:
            leader_id: The user ID of the leader.

        Returns:
            A list of matching Challenge objects.
        """
        return [c for c in self.challenges if c.leader_id == leader_id]

    # FUNC: filter_by_group
    def filter_by_group(self, group_id: Optional[str] = None, group_type: Optional[str] = None) -> List[Challenge]:
        """Filters challenges by group ID and/or group type.

        Args:
            group_id: Optional group ID to filter by.
            group_type: Optional group type ('party', 'guild', 'tavern') to filter by.

        Returns:
            A list of matching Challenge objects.
        """
        filtered = self.challenges
        if group_id is not None:
            filtered = [c for c in filtered if c.group_id == group_id]
        if group_type is not None:
            filtered = [c for c in filtered if c.group_type == group_type]
        return filtered

    # FUNC: filter_by_official
    def filter_by_official(self, official: bool = True) -> List[Challenge]:
        """Filters for official or unofficial challenges.

        Args:
            official: Set to True to find official challenges, False for unofficial (default: True).

        Returns:
            A list of matching Challenge objects.
        """
        return [c for c in self.challenges if c.official is official]  # Explicit comparison

    # FUNC: filter_broken
    def filter_broken(self, is_broken: bool = True) -> List[Challenge]:
        """Filters challenges based on whether they have a 'broken' status field populated.

        Args:
            is_broken: Set to True to find challenges with a broken status,
                       False to find challenges without (default: True).

        Returns:
            A list of matching Challenge objects.
        """
        if is_broken:
            return [c for c in self.challenges if c.broken is not None]
        else:
            return [c for c in self.challenges if c.broken is None]

    # FUNC: filter_owned
    def filter_owned(self, owned: bool = True) -> List[Challenge]:
        """Filters challenges based on the 'owned' flag (if available from API context).

        Args:
            owned: Set to True to find challenges marked as owned by the user,
                   False to find those not marked as owned (default: True).

        Returns:
            A list of matching Challenge objects.
        """
        # Note: 'owned' might be None if not provided by the API endpoint used
        return [c for c in self.challenges if c.owned is owned]  # Explicit comparison

    # FUNC: filter_by_task_count
    def filter_by_task_count(self, min_tasks: int = 1, max_tasks: Optional[int] = None) -> List[Challenge]:
        """Filters challenges by the number of linked tasks.

        Args:
            min_tasks: The minimum number of tasks a challenge must have (inclusive, default: 1).
            max_tasks: The maximum number of tasks a challenge can have (inclusive).
                       If None, there is no upper limit (default: None).

        Returns:
            A list of matching Challenge objects.
        """
        if max_tasks is None:
            return [c for c in self.challenges if len(c.tasks) >= min_tasks]
        else:
            return [c for c in self.challenges if min_tasks <= len(c.tasks) <= max_tasks]

    # FUNC: filter_containing_task_id
    def filter_containing_task_id(self, task_id: str) -> List[Challenge]:
        """Filters challenges that contain a specific task ID in their linked tasks.

        Ensure tasks are linked before calling this method for accurate results.

        Args:
            task_id: The ID of the task to look for.

        Returns:
            A list of Challenge objects containing the specified task.
        """
        return [c for c in self.challenges if any(task.id == task_id for task in c.tasks)]
