# pixabit/models/task.py

# ─── Title ────────────────────────────────────────────────────────────────────
#      Habitica Task Models (Habits, Dailies, Todos, Rewards)
# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for representing Habitica Tasks (Habits, Dailies,
Todos, Rewards), including nested structures like ChecklistItem and
ChallengeLinkData. Provides a TaskList container for managing and processing
collections of Task objects, including methods for adding, removing, editing,
and reordering tasks.
"""

# SECTION: IMPORTS
from __future__ import annotations

import json
import logging
import math
import uuid  # Import uuid for generating temporary IDs
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Literal, Sequence  # Use standard types

# External Libs
import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,  # For internal state
    ValidationError,
    ValidationInfo,  # For field context
    computed_field,  # For computed properties in dumps
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError  # More specific error for validation

# Local Imports
try:
    # Helpers
    from pixabit.api.client import HabiticaClient

    # Required Models for processing/linking
    from pixabit.config import HABITICA_DATA_PATH
    from pixabit.helpers._json import save_json  # For demo
    from pixabit.helpers._logger import log
    from pixabit.helpers._md_to_rich import MarkdownRenderer  # Assuming already instantiated if needed globally
    from pixabit.helpers._rich import Text  # Type hint for styled text
    from pixabit.helpers.DateTimeHandler import DateTimeHandler

    # Use TYPE_CHECKING to avoid runtime circular imports if TagList/User import Task
    if TYPE_CHECKING:
        from .game_content import Quest as StaticQuestData
        from .game_content import StaticContentManager  # Need for Daily dmg calc context
        from .tag import TagList
        from .user import User


except ImportError:
    # Fallbacks for isolated testing
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    HABITICA_DATA_PATH = Path("./pixabit_cache")

    class MarkdownRenderer:
        def markdown_to_rich_text(self, s: str) -> str:
            return s  # Simple fallback

    class DateTimeHandler:
        def __init__(self, timestamp: Any):
            self._ts = timestamp

        @property
        def utc_datetime(self) -> datetime | None:
            return None  # Fallback

    class Text:
        pass  # Placeholder type

    class HabiticaClient:
        async def get_tasks(self):
            return []  # Mock

    def save_json(d, p, **k):
        pass

    if TYPE_CHECKING:  # Still provide types for checking

        class TagList:
            def get_by_id(self, tid: str) -> Any:
                return None

        class User:
            # Add placeholder for effective_stats if User needs it for damage calculation
            @property
            def effective_stats(self) -> dict[str, float]:
                return {}  # Mock empty stats

            @property
            def is_sleeping(self) -> bool:
                return False  # Mock not sleeping

            @property
            def stealth(self) -> float:
                return 0.0  # Mock no stealth

            @property
            def party(self) -> Any:  # Mock party structure needed for damage
                return None  # No party

        class StaticContentManager:
            pass

        class StaticQuestData:
            @property
            def is_boss_quest(self) -> bool:
                return False

            @property
            def boss(self) -> Any:
                return None

    log.warning("task.py: Could not import dependencies. Using fallbacks.")


# Create one instance of the renderer if used frequently
md_renderer = MarkdownRenderer()


# SECTION: TASKLIST CONTAINER


# KLASS: TaskList
class TaskList(BaseModel):
    """Container for a list of Habitica tasks, providing lookup and processing utilities."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        validate_assignment=True,  # Keep validate_assignment for edit_task
        arbitrary_types_allowed=True,
    )

    # List of raw task data before parsing into Task objects (Optional, for debugging/re-parsing)
    _raw_tasks_data: list[dict[str, Any]] | None = PrivateAttr(default=None)

    # The main list of parsed Task objects, maintaining the order from the API
    tasks: list[Task] = Field(default_factory=list, description="List of all Task objects.")

    # Internal lookup dictionaries for faster access
    # Mapped during process_tasks or initial parsing
    _tasks_by_id: Dict[str, Task] = PrivateAttr(default_factory=dict)
    _tasks_by_type: Dict[Literal["habit", "daily", "todo", "reward"], List[Task]] = PrivateAttr(default_factory=lambda: defaultdict(list))

    # Store context providers if available after initial processing
    # These can be used by add/edit/delete methods if available.
    _tags_provider: TagList | None = PrivateAttr(default=None)
    _user_data: User | None = PrivateAttr(default=None)
    _content_manager: StaticContentManager | None = PrivateAttr(default=None)

    # --- Class Factory Method ---

    @classmethod
    def from_raw_api_list(
        cls,
        raw_data: list[dict[str, Any]],
        user: User | None = None,
        tags_provider: TagList | None = None,
        content_manager: StaticContentManager | None = None,
    ) -> TaskList:
        """Factory method to create a TaskList from raw Habitica API task data.

        Processes the raw list into appropriate Task subclasses and populates
        internal lookup structures. Runs the initial processing.
        """
        parsed_tasks: list[Task] = []
        errors: list[tuple[str, str, ValidationError]] = []  # Store (task_id, task_type, error)

        log.info(f"Attempting to parse {len(raw_data)} raw task entries from API.")

        # Use a mapping for task types to Pydantic models
        # Ensure Daily and Todo models are available here (imported or defined)
        task_type_map: Dict[str, type[Task]] = {
            "habit": Habit,
            "daily": Daily,
            "todo": Todo,
            "reward": Reward,
        }

        for i, item in enumerate(raw_data):
            # Ensure 'type' exists and is a string before lookup
            task_type_str = str(item.get("type", "")).lower()
            TaskModel = task_type_map.get(task_type_str)

            if not TaskModel:
                task_id_preview = item.get("_id", item.get("id", "unknown ID"))[:8]
                log.warning(f"Skipping item {i} (ID: {task_id_preview}) with unknown or missing type '{task_type_str}'. " f"Data starts with: {str(item)[:100]}...")
                continue  # Skip items with unknown type

            try:
                # Validate and parse the raw data into the specific Task model
                task_instance = TaskModel(**item)
                # Assign a temporary position based on API order for initial state
                task_instance.position = i
                parsed_tasks.append(task_instance)

            except ValidationError as e:
                task_id_preview = item.get("_id", item.get("id", "unknown ID"))[:8]
                log.error(f"Validation error for task {task_id_preview} (Type: {task_type_str}): {e}")
                errors.append((item.get("_id", "N/A"), task_type_str, e))
            except Exception as e:
                task_id_preview = item.get("_id", item.get("id", "unknown ID"))[:8]
                log.exception(f"Unexpected error parsing task {task_id_preview} (Type: {task_type_str}): {e}")
                errors.append((item.get("_id", "N/A"), task_type_str, e))

        log.info(f"Successfully parsed {len(parsed_tasks)} tasks. Encountered {len(errors)} errors.")

        # Create the TaskList instance with the parsed tasks
        task_list_instance = cls(tasks=parsed_tasks)

        # Store the raw data and context providers for potential later use (e.g., saving, re-processing)
        task_list_instance._raw_tasks_data = raw_data
        task_list_instance._user_data = user
        task_list_instance._tags_provider = tags_provider
        task_list_instance._content_manager = content_manager

        # Perform initial processing to populate lookups and calculate statuses
        # Pass the context providers here
        task_list_instance.process_tasks(user=user, tags_provider=tags_provider, content_manager=content_manager)

        return task_list_instance

    # --- Processing Method ---

    def process_tasks(
        self,
        user: User | None = None,
        tags_provider: TagList | None = None,
        content_manager: StaticContentManager | None = None,
    ):
        """Processes all tasks in the list to populate internal lookups,
        calculate statuses, and resolve metadata (like tag names).

        This method iterates through the main 'tasks' list and updates
        _tasks_by_id, _tasks_by_type, and calls process_status_and_metadata
        on each task. Also assigns positional order.

        Args:
            user: The User model instance for context (e.g., damage calculation).
            tags_provider: The TagList instance for resolving tag names.
            content_manager: The StaticContentManager for game content lookups.
        """
        log.info(f"Processing statuses and metadata for {len(self.tasks)} tasks.")

        # Reset internal lookups
        self._tasks_by_id = {}
        self._tasks_by_type = defaultdict(list)

        # Store context providers if they are provided now
        # Prioritize new providers if passed, otherwise keep existing ones
        if user:
            self._user_data = user
        if tags_provider:
            self._tags_provider = tags_provider
        if content_manager:
            self._content_manager = content_manager

        # Iterate through the main list (maintaining original API order or current order)
        for i, task in enumerate(self.tasks):
            # Update position based on the current list order
            task.position = i

            # Populate lookups
            self._tasks_by_id[task.id] = task
            self._tasks_by_type[task.task_type].append(task)

            # Process task-specific status and metadata
            # Use stored providers, which were updated above if new ones were passed
            task.process_status_and_metadata(user=self._user_data, tags_provider=self._tags_provider, content_manager=self._content_manager)

        log.info("Task processing complete.")

    # --- Access Methods ---

    def get_task_by_id(self, task_id: str) -> Task | None:
        """Retrieves a task by its ID."""
        return self._tasks_by_id.get(task_id)

    def get_tasks_by_type(self, task_type: Literal["habit", "daily", "todo", "reward"]) -> List[Task]:
        """Retrieves a list of tasks of a specific type, in their current order."""
        return self._tasks_by_type.get(task_type, [])

    # --- New Methods for Add, Edit, Delete ---

    def add_task(self, task_data: Dict[str, Any] | Task) -> Task | None:
        """Adds a new task to the TaskList.

        Processes only the newly added task and updates internal structures
        without re-processing the entire list.

        Args:
            task_data: A dictionary representing the raw task data or a Task instance.

        Returns:
            The newly added Task instance, or None if validation fails.
        """
        # Determine the Task subclass based on type
        task_type_str = str(task_data.get("type", "")).lower() if isinstance(task_data, dict) else task_data.task_type
        task_type_map: Dict[str, type[Task]] = {
            "habit": Habit,
            "daily": Daily,
            "todo": Todo,
            "reward": Reward,
        }
        TaskModel = task_type_map.get(task_type_str)

        if not TaskModel:
            log.error(f"Cannot add task with unknown or missing type '{task_type_str}'.")
            return None

        new_task: Task
        if isinstance(task_data, Task):
            # Ensure the provided Task instance is of the correct subclass
            if not isinstance(task_data, TaskModel):
                log.warning(
                    f"Provided Task instance type ({type(task_data).__name__}) does not match data type ('{task_type_str}'). Attempting to use the provided instance."
                )
                new_task = task_data
            else:
                new_task = task_data
        elif isinstance(task_data, dict):
            try:
                # Validate and parse the raw data into the specific Task model
                new_task = TaskModel(**task_data)
            except ValidationError as e:
                task_id_preview = task_data.get("_id", task_data.get("id", "unknown ID"))[:8]
                log.error(f"Validation error adding task {task_id_preview} (Type: {task_type_str}): {e}")
                return None
            except Exception as e:
                task_id_preview = task_data.get("_id", task_data.get("id", "unknown ID"))[:8]
                log.exception(f"Unexpected error adding task {task_id_preview} (Type: {task_type_str}): {e}")
                return None
        else:
            log.error(f"Invalid input type for add_task: {type(task_data).__name__}. Expected dict or Task.")
            return None

        # If task already exists by ID, log a warning and return existing task?
        # Or overwrite? Let's assume adding means a *new* task ID.
        if new_task.id in self._tasks_by_id:
            log.warning(f"Task with ID {new_task.id[:8]} already exists. Not adding.")
            return self._tasks_by_id[new_task.id]  # Return existing task

        # Add the task to the main list (appends to the end by default)
        self.tasks.append(new_task)

        # Update internal lookups
        self._tasks_by_id[new_task.id] = new_task
        # Append to the list for its type
        self._tasks_by_type[new_task.task_type].append(new_task)

        # Assign a temporary position (at the end of the list)
        # Note: This position is based on the global list. Reordering will fix it.
        new_task.position = len(self.tasks) - 1

        # Process status and metadata only for the new task, using stored context
        success = new_task.process_status_and_metadata(user=self._user_data, tags_provider=self._tags_provider, content_manager=self._content_manager)

        if not success:
            log.warning(f"Failed to process status/metadata for added task {new_task.id[:8]}.")
            # Decide if we should remove the task or keep it. Let's keep it.

        log.info(f"Added new task: {new_task.id[:8]} (Type: {new_task.task_type}, Text: '{new_task.text[:30]}...')")

        return new_task

    def edit_task(self, task_id: str, update_data: Dict[str, Any]) -> Task | None:
        """Edits an existing task by its ID with new data.

        Updates only the specific task instance and re-processes its status
        and metadata without affecting other tasks. Handles potential type change.

        Args:
            task_id: The ID of the task to edit.
            update_data: A dictionary of the fields and values to update.

        Returns:
            The updated Task instance, or None if the task is not found or validation fails.
        """
        task = self.get_task_by_id(task_id)
        if not task:
            log.warning(f"Task with ID {task_id[:8]} not found for editing.")
            return None

        # Store old type in case the type changes
        old_task_type = task.task_type
        # Determine the potential new type from update_data, defaulting to current type
        new_type = update_data.get("type", old_task_type)

        try:
            # Use model_validate(update=True) to update the existing instance.
            # Pydantic handles attribute assignment validation.
            # Note: If 'type' is in update_data and changes, this will update task.task_type.
            updated_task = task.model_validate(update_data, update=True)  # Pydantic v2 way

            # Handle type change logic after successful validation and update
            if updated_task.task_type != old_task_type:
                log.info(f"Task type changed for {task_id[:8]} from '{old_task_type}' to '{updated_task.task_type}'.")
                # Remove from the old _tasks_by_type list
                if task in self._tasks_by_type[old_task_type]:
                    self._tasks_by_type[old_task_type].remove(task)
                    log.debug(f"Removed task {task_id[:8]} from old _tasks_by_type list '{old_task_type}'.")
                else:
                    log.warning(f"Task {task_id[:8]} not found in old _tasks_by_type list '{old_task_type}' during type change handling.")

                # Add to the new _tasks_by_type list (append)
                self._tasks_by_type[updated_task.task_type].append(task)  # task is the same object updated in place
                log.debug(f"Added task {task_id[:8]} to new _tasks_by_type list '{updated_task.task_type}'.")

                # Note: Position in self.tasks is not automatically updated by type change.
                # A full `process_tasks` or `reorder_tasks` will be needed to fix global order/positions.
                log.warning(f"Type change for task {task_id[:8]} affects its position. A subsequent reorder or full processing is recommended.")

            # Re-process status and metadata only for the updated task, using stored context
            success = updated_task.process_status_and_metadata(user=self._user_data, tags_provider=self._tags_provider, content_manager=self._content_manager)

            if not success:
                log.warning(f"Failed to re-process status/metadata for edited task {task_id[:8]}.")

            log.info(f"Edited task: {task_id[:8]} (Type: {updated_task.task_type}, Text: '{updated_task.text[:30]}...')")

            return updated_task

        except ValidationError as e:
            log.error(f"Validation error editing task {task_id[:8]}: {e}")
            # The task instance might be partially updated depending on where validation failed.
            # For simplicity, we let the partial update stand but return None to indicate failure.
            return None
        except Exception as e:
            log.exception(f"Unexpected error editing task {task_id[:8]}: {e}")
            return None

    def delete_task(self, task_id: str) -> Task | None:
        """Deletes a task by its ID from the TaskList.

        Removes the task from internal structures without affecting other tasks.

        Args:
            task_id: The ID of the task to delete.

        Returns:
            The deleted Task instance, or None if the task is not found.
        """
        task_to_delete = self.get_task_by_id(task_id)
        if not task_to_delete:
            log.warning(f"Task with ID {task_id[:8]} not found for deletion.")
            return None

        try:
            # Remove from the main list (maintains order of remaining tasks)
            # Finding by identity (the object itself) is reliable since we got it from _tasks_by_id
            try:
                self.tasks.remove(task_to_delete)
                log.debug(f"Removed task {task_id[:8]} from main tasks list.")
            except ValueError:
                log.warning(f"Task object {task_id[:8]} not found in main tasks list during deletion attempt.")

            # Remove from _tasks_by_type list (finding by identity)
            task_type = task_to_delete.task_type
            if task_type in self._tasks_by_type:
                try:
                    self._tasks_by_type[task_type].remove(task_to_delete)
                    log.debug(f"Removed task {task_id[:8]} from _tasks_by_type list for type '{task_type}'.")
                except ValueError:
                    log.warning(f"Task object {task_id[:8]} not found in _tasks_by_type list for type '{task_type}' during deletion attempt.")
                # If the list for this type becomes empty, we could consider removing the key
                # from the defaultdict, but it's usually not necessary.

            # Remove from _tasks_by_id dictionary
            if task_id in self._tasks_by_id:
                del self._tasks_by_id[task_id]
                log.debug(f"Removed task {task_id[:8]} from _tasks_by_id dictionary.")
            else:
                log.warning(f"Task ID {task_id[:8]} not found in _tasks_by_id dictionary during deletion attempt.")

            # Note: Deletion affects the positions of subsequent tasks in self.tasks
            # and _tasks_by_type lists implicitly. Positions are recalculated
            # during the full process_tasks call triggered by reorder.
            # We do not recalculate positions here to avoid iterating the whole list.

            log.info(f"Deleted task: {task_id[:8]} (Type: {task_to_delete.task_type}, Text: '{task_to_delete.text[:30]}...')")

            return task_to_delete

        except Exception as e:
            log.exception(f"Unexpected error deleting task {task_id[:8]}: {e}")
            return None

    def reorder_tasks(self, task_type: Literal["habit", "daily", "todo", "reward"], new_order_ids: List[str]):
        """Reorders tasks of a specific type based on a list of task IDs.

        This method will update the positions of tasks of the specified type
        within the internal lists and trigger a full processing to update
        global positions and ensure consistency.

        Args:
            task_type: The type of tasks to reorder.
            new_order_ids: A list of task IDs in the desired new order for this type.
        """
        if task_type not in self._tasks_by_type and self.get_tasks_by_type(task_type) == []:
            log.warning(f"No tasks found for type '{task_type}'. Cannot reorder.")
            return

        current_tasks_of_type = self.get_tasks_by_type(task_type)  # Use getter to ensure defaultdict creates list
        tasks_dict = {task.id: task for task in current_tasks_of_type}
        reordered_tasks_of_type = []
        seen_ids = set()

        # Build the reordered list for this specific type based on the new_order_ids
        for task_id in new_order_ids:
            if task_id in tasks_dict and task_id not in seen_ids:
                reordered_tasks_of_type.append(tasks_dict[task_id])
                seen_ids.add(task_id)
            elif task_id in seen_ids:
                log.warning(f"Duplicate task ID '{task_id[:8]}' found in new_order_ids for type '{task_type}'. Skipping duplicate.")
            else:
                # Handle tasks in new_order_ids that are not currently in this list type
                # This might happen if the API returns reorder data inconsistent with the current local list.
                log.warning(f"Task ID '{task_id[:8]}' in new_order_ids not found in current list for type '{task_type}'. Skipping.")

        # Add any tasks that were in the old list for this type but not in the new_order_ids.
        # This might happen if the API response is partial or inconsistent.
        # Append them to the end of the reordered list for this type.
        old_task_ids = {task.id for task in current_tasks_of_type}
        missing_ids = old_task_ids - seen_ids
        if missing_ids:
            log.warning(
                f"The following task IDs for type '{task_type}' were in the list but not in new_order_ids: {list(missing_ids)[:5]}... Appending them to the end of this type's list."
            )
            for task_id in missing_ids:
                # Use tasks_dict to get the actual task object
                if task_id in tasks_dict:
                    reordered_tasks_of_type.append(tasks_dict[task_id])

        # Update the _tasks_by_type list for this specific type
        self._tasks_by_type[task_type] = reordered_tasks_of_type

        # --- Rebuild the main `self.tasks` list and re-process all tasks ---
        # As requested, reordering triggers a full re-processing to update global
        # positions and ensure the main list's order is consistent with the
        # reordered type list and other types.

        log.info(f"Reordering tasks of type '{task_type}'. Re-processing all tasks to update global order and positions.")

        # Create a new combined list maintaining the relative order of tasks within
        # each type, based on the reordered_tasks_of_type for the specified type
        # and the existing order for other types.
        new_global_tasks_list = []
        processed_task_ids = set()  # Keep track of tasks added to the new list

        # Iterate through types in a predefined order (optional, but good for consistency)
        # Use a consistent order for types if important for the final self.tasks list structure
        type_display_order = ["daily", "todo", "habit", "reward"]
        all_types_in_list = list(self._tasks_by_type.keys())  # Get all types currently in the list
        # Ensure all types are considered, even if not in display_order, append them at the end
        ordered_types = list(dict.fromkeys(type_display_order + all_types_in_list))  # maintain order, remove duplicates

        for current_type in ordered_types:
            tasks_of_current_type = self._tasks_by_type.get(current_type, [])  # Get the list for this type
            for task in tasks_of_current_type:
                if task.id not in processed_task_ids:  # Avoid adding duplicates if a task somehow appeared in multiple types
                    new_global_tasks_list.append(task)
                    processed_task_ids.add(task.id)
                else:
                    log.warning(f"Duplicate task ID '{task.id[:8]}' encountered while rebuilding global list. Skipping.")

        # Replace the main tasks list with the new combined ordered list
        self.tasks = new_global_tasks_list

        # Re-run the full processing method. This will:
        # 1. Clear and re-populate _tasks_by_id based on the new self.tasks order.
        # 2. Clear and re-populate _tasks_by_type based on the new self.tasks order.
        # 3. Recalculate and set the `position` attribute for ALL tasks based on their index in the new `self.tasks` list.
        # 4. Re-run process_status_and_metadata for ALL tasks (less efficient, but guarantees consistent state after reorder).
        # This fulfills the requirement that reorder can update everything.
        self.process_tasks(user=self._user_data, tags_provider=self._tags_provider, content_manager=self._content_manager)  # Use stored context

        log.info(f"Reordering complete for tasks of type '{task_type}'.")

    # --- Other Methods ---

    def save_to_json(self, file_path: Path | str):
        """Saves the TaskList to a JSON file."""
        try:
            # Use model_dump_json for serialization
            # Excluding private attributes by default is handled by Pydantic v2 model_dump
            json_data = self.model_dump_json(indent=4)
            # save_json helper might expect a dict, load from json string first
            save_json(json.loads(json_data), Path(file_path))
            log.info(f"TaskList saved to {file_path}")
        except Exception as e:
            log.exception(f"Error saving TaskList to {file_path}: {e}")

    # Add a load method for completeness, though not explicitly requested
    @classmethod
    def load_from_json(
        cls,
        file_path: Path | str,
        user: User | None = None,
        tags_provider: TagList | None = None,
        content_manager: StaticContentManager | None = None,
    ):
        """Loads a TaskList from a JSON file."""
        try:
            with open(Path(file_path), encoding="utf-8") as f:
                raw_data = json.load(f)
            if not isinstance(raw_data, list):
                log.error(f"Expected a JSON list of tasks in {file_path}, but got {type(raw_data).__name__}.")
                return None

            # Use the factory method to parse and process the loaded data
            # Assuming the JSON file contains the raw list structure
            task_list = cls.from_raw_api_list(raw_data, user, tags_provider, content_manager)
            log.info(f"TaskList loaded from {file_path}")
            return task_list
        except FileNotFoundError:
            log.error(f"JSON file not found at {file_path}")
            return None
        except json.JSONDecodeError as e:
            log.error(f"Error decoding JSON from {file_path}: {e}")
            return None
        except Exception as e:
            log.exception(f"Error loading TaskList from {file_path}: {e}")
            return None

    def __len__(self) -> int:
        """Returns the total number of tasks."""
        return len(self.tasks)

    def __iter__(self) -> Iterator[Task]:
        """Iterates over all tasks in the list (maintaining current order)."""
        return iter(self.tasks)

    def __getitem__(self, index: int) -> Task:
        """Allows accessing tasks by index from the main list."""
        return self.tasks[index]

    def __repr__(self) -> str:
        """Concise developer representation."""
        task_counts = ", ".join([f"{type.capitalize()}:{len(tasks)}" for type, tasks in self._tasks_by_type.items() if tasks])
        if not task_counts:
            task_counts = "Empty"
        total_tasks = len(self.tasks)
        return f"TaskList({total_tasks} tasks - {task_counts})"

    def __str__(self) -> str:
        """User-friendly summary."""
        task_summary = []
        # Iterate through types in a consistent order for display
        for task_type in ["daily", "todo", "habit", "reward"]:
            tasks_of_type = self.get_tasks_by_type(task_type)
            if tasks_of_type:
                task_summary.append(f"{task_type.capitalize()}s: {len(tasks_of_type)}")

        # Include any other types found in the data but not in the preferred order
        other_types = [t for t in self._tasks_by_type.keys() if t not in ["daily", "todo", "habit", "reward"]]
        for task_type in other_types:
            tasks_of_type = self.get_tasks_by_type(task_type)
            if tasks_of_type:
                task_summary.append(f"{task_type.capitalize()}s: {len(tasks_of_type)}")

        return f"TaskList contains: {', '.join(task_summary) or 'No tasks'}"
