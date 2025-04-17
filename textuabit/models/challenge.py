# pixabit/models/challenge.py
# MARK: - MODULE DOCSTRING
"""Defines data class for representing Habitica Challenges."""

# MARK: - IMPORTS
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.dates import convert_timestamp_to_utc

# Assuming Task class is defined in models.task
from .task import Task  # Import specific types if needed later


# KLASS: - Challenge
class Challenge:
    """Represents a Habitica Challenge, including references to its tasks.

    Attributes:
        id: The unique ID (_id) of the challenge.
        name: The full display name of the challenge.
        short_name: The short name (often used as a slug).
        summary: A brief summary of the challenge.
        description: The full description (can contain Markdown).
        leader_id: The User ID of the challenge creator/leader.
        group_id: The ID of the group (guild/party) the challenge belongs to.
        group_name: The name of the group.
        group_type: The type of the group ('party', 'guild').
        prize: The gem prize awarded for completing the challenge (if any).
        member_count: Number of participants.
        official: Boolean indicating if it's an official Habitica challenge.
        created_at: Timestamp when the challenge was created (UTC).
        updated_at: Timestamp when the challenge was last updated (UTC).
        tasks: A list containing Task objects associated with this challenge.
               (Populated separately after initialization).
        broken: String indicating broken status (e.g., "BROKEN") or None.
        cloned_from_id: ID of the challenge this was cloned from, if any.
    """

    # FUNC: - __init__
    def __init__(self, challenge_data: Dict[str, Any]):
        """Initializes a Challenge object from API data. Tasks are added separately.

        Args:
            challenge_data: Dictionary containing challenge data from the API.
        """
        if not isinstance(challenge_data, dict):
            raise TypeError("challenge_data must be a dictionary.")

        self.id: Optional[str] = challenge_data.get("id") or challenge_data.get("_id")
        self.name: str = challenge_data.get("name", "Unnamed Challenge")
        self.short_name: str = challenge_data.get("shortName", "")
        self.summary: str = challenge_data.get("summary", "")
        self.description: str = challenge_data.get("description", "")

        # Leader and Group Info
        leader_info = challenge_data.get("leader", {})  # Leader might be object or just ID string
        self.leader_id: Optional[str] = (
            leader_info
            if isinstance(leader_info, str)
            else (leader_info.get("_id") if isinstance(leader_info, dict) else None)
        )

        group_info = challenge_data.get("group", {})
        self.group_id: Optional[str] = (
            group_info.get("_id") if isinstance(group_info, dict) else None
        )
        self.group_name: Optional[str] = (
            group_info.get("name") if isinstance(group_info, dict) else None
        )
        self.group_type: Optional[str] = (
            group_info.get("type") if isinstance(group_info, dict) else None
        )

        self.prize: int = int(challenge_data.get("prize", 0))  # Ensure int
        self.member_count: int = challenge_data.get("memberCount", 0)
        self.official: bool = challenge_data.get("official", False)
        self.created_at: Optional[datetime] = convert_timestamp_to_utc(
            challenge_data.get("createdAt")
        )
        self.updated_at: Optional[datetime] = convert_timestamp_to_utc(
            challenge_data.get("updatedAt")
        )
        self.broken: Optional[str] = challenge_data.get("broken")  # e.g., "BROKEN"
        self.cloned_from_id: Optional[str] = challenge_data.get("clonedFrom")
        # todo exist?
        self.owned: bool = challenge_data.get("owned", False)
        self.legacy: bool = (
            False if challenge_data.get("group", {}).get("name") == "tavern" else True
        )
        # Task container - to be populated externally
        self.tasks: List[Task] = []  # List to hold Task objects

    # FUNC: - add_tasks
    def add_tasks(self, task_list: List[Task]) -> None:
        """Adds a list of Task objects associated with this challenge."""
        self.tasks.extend(task for task in task_list if isinstance(task, Task))
        # Optionally sort tasks here if needed
        # self.tasks.sort(key=lambda t: t.text.lower())

    # FUNC: - get_tasks_by_type
    def get_tasks_by_type(self, task_type: str) -> List[Task]:
        """Returns a list of tasks belonging to this challenge of a specific type."""
        return [task for task in self.tasks if task.type == task_type]

    # FUNC: - __repr__
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        status = f" ({self.broken})" if self.broken else ""
        return f"Challenge(id='{self.id}', name='{self.name}'{status}, tasks={len(self.tasks)})"

    # TENÍAMOS ESTO


"""
    def _populate_task_lists(self, all_tasks: Dict[str, "Task"]) -> None:
        Populates the task lists (dailies, habits, todos, rewards) based on the provided task IDs.

        Args:
            all_tasks: A dictionary mapping task IDs to Task objects.

        for task_id in self.dailies_order:
            task = all_tasks.get(task_id)
            if task:
                self.dailies.append(task)
        for task_id in self.habits_order:
            task = all_tasks.get(task_id)
            if task:
                self.habits.append(task)
        for task_id in self.todos_order:
            task = all_tasks.get(task_id)
            if task:
                self.todos.append(task)
        for task_id in self.rewards_order:
            task = all_tasks.get(task_id)
            if task:
                self.rewards.append(task)

    def __repr__(self) -> str:
        return f"Challenge(id={self.id}, name={self.name}, short_name={self.short_name})"


# Assuming you have these functions/data:
#   - get_challenge_data(challenge_id: str) -> Dict[str, Any]
#   - get_all_tasks_data() -> List[Dict[str, Any]]
#   - process_task_data(task_data: Dict[str, Any]) -> Task  (your function to create Task objects)


def process_challenge(api_client: HabiticaAPI, challenge_id: str) -> Challenge:
    Fetches challenge and related task data from the Habitica API and creates a Challenge object.
    challenge_data = get_challenge_data(api_client, challenge_id)  # Get challenge data
    all_tasks_data = get_all_tasks_data(api_client)  # Get all task data

    # 1. Process tasks and store them in a dictionary
    all_tasks: Dict[str, Task] = {}
    for task_data in all_tasks_data:
        task = process_task_data(task_data)  # Create Task object (or subclass)
        if task:
            all_tasks[task.id] = task  # Store by ID

    # 2. Create the Challenge object
    challenge = Challenge(challenge_data, all_tasks)
    return challenge


# Example usage
api_client = HabiticaAPI()  # Your API client
challenge = process_challenge(api_client, "some_challenge_id")
print(challenge)  # Print the Challenge object (using __repr__)
print(f"Challenge Name: {challenge.name}")
print(f"Number of Dailies: {len(challenge.dailies)}")
for daily in challenge.dailies:
    print(f"  - Daily: {daily.title}")  # Access properties of the Daily objects
 """
