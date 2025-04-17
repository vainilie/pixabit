# pixabit/data_store.py
# MARK: - MODULE DOCSTRING
"""Provides a central data store and query interface for Pixabit application state.

Holds references to the main data structures (tasks, tags, challenges, etc.)
fetched by the main application and offers methods to filter and retrieve
subsets of this data for UI display or action processing.
"""

# MARK: - IMPORTS
from typing import TYPE_CHECKING, Any, List, Optional

from .models.challenge import Challenge
from .models.tag import Tag  # Assuming you create models/tag.py

# Import your data models
from .models.task import Task

# ... import other models as needed ...

# Use TYPE_CHECKING to avoid circular imports at runtime
# The App needs the store, and the store needs the App's state.
if TYPE_CHECKING:
    from .cli.app import PixabitTUIApp  # Or wherever your App class is


# MARK: - PixabitDataStore Class
class PixabitDataStore:
    """Manages access and filtering of application data."""

    # & - def __init__(self, app: 'PixabitTUIApp'):
    def __init__(self, app: "PixabitTUIApp"):
        """Initializes the DataStore with a reference to the main app instance.

        Args:
            app: The main PixabitTUIApp instance containing the raw/processed data.
        """
        # Store a reference to the app to access its state attributes
        # Be mindful of potential circular dependencies if the app also
        # heavily relies on calling store methods during its own initialization.
        self.app = app
        # Note: We don't copy the data here, we just reference the app's
        # state attributes directly (e.g., self.app.processed_tasks).
        # This ensures the store always works with the latest refreshed data.

    # --- Task Retrieval Methods ---

    # & - def get_tasks(self, ...)
    def get_tasks(
        self,
        task_type: Optional[str] = None,
        tag_filter_id: Optional[str] = None,  # Filter by tag ID
        tag_filter_name: Optional[str] = None,  # Filter by tag name
        status_filter: Optional[str] = None,  # Filter by _status ('due', 'red', 'grey', 'success')
        text_contains: Optional[str] = None,  # Simple text search
        sort_by: str = "priority",  # Default sort key ('priority', 'text', 'date', etc.)
        sort_reverse: bool = False,
    ) -> List[Task]:
        """Retrieves and filters tasks based on various criteria.

        Args:
            task_type: Filter by 'habit', 'daily', 'todo', 'reward'.
            tag_filter_id: Keep only tasks containing this tag ID.
            tag_filter_name: Keep only tasks containing this tag name.
            status_filter: Keep only tasks with this '_status'.
            text_contains: Keep tasks where text or notes contain this string (case-insensitive).
            sort_by: Attribute to sort tasks by (e.g., 'priority', 'text', 'value', 'date').
            sort_reverse: Whether to sort in descending order.

        Returns:
            A list of Task objects matching the criteria.
        """
        # Start with all processed task objects from the app's state
        # Ensure processed_tasks contains Task objects, not just dicts
        all_tasks: List[Task] = list(self.app.processed_tasks.values())
        filtered_tasks = all_tasks

        # Apply filters sequentially
        if task_type:
            filtered_tasks = [t for t in filtered_tasks if t.type == task_type]

        if tag_filter_id:
            # Assumes Task object has a 'tags' attribute which is a list of IDs
            filtered_tasks = [t for t in filtered_tasks if tag_filter_id in t.tags]

        if tag_filter_name:
            # Assumes Task object has a 'tag_names' attribute populated by processor
            filtered_tasks = [t for t in filtered_tasks if tag_filter_name in t.tag_names]

        if status_filter:
            # Assumes Task object has '_status' attribute populated by processor
            # Adjust status names ('success' vs 'done' if needed)
            filtered_tasks = [t for t in filtered_tasks if t._status == status_filter]

        if text_contains:
            search_term = text_contains.lower()
            filtered_tasks = [
                t
                for t in filtered_tasks
                if search_term in t.text.lower() or search_term in t.notes.lower()
            ]

        # Apply sorting (handle potential None values in sort keys)
        try:
            # Define a default value for sorting if the key is None
            # For 'date', use a very old/future date; for numbers use 0 or infinity?
            # For 'priority', maybe default to 1.0?
            default_sort_val = 0.0
            if sort_by == "date":  # Use a very early date for None
                default_sort_val = (
                    datetime.min.replace(tzinfo=timezone.utc) if hasattr(datetime, "min") else 0
                )
            elif sort_by == "text":
                default_sort_val = ""

            filtered_tasks.sort(
                key=lambda t: getattr(t, sort_by, default_sort_val) or default_sort_val,
                reverse=sort_reverse,
            )
        except AttributeError:
            self.app.console.log(
                f"Warning: Cannot sort by invalid attribute '{sort_by}'", style="warning"
            )
        except TypeError as e:
            self.app.console.log(
                f"Warning: Type error during sorting by '{sort_by}': {e}", style="warning"
            )

        return filtered_tasks

    # --- Tag Retrieval Methods ---

    # & - def get_all_tags(self) -> List[Tag]:
    def get_all_tags(self) -> List[Tag]:
        """Returns the list of all Tag objects."""
        # Assumes self.app.all_tags holds Tag objects
        return self.app.all_tags if isinstance(self.app.all_tags, list) else []

    # & - def get_unused_tags(self) -> List[Tag]:
    def get_unused_tags(self) -> List[Tag]:
        """Returns the list of unused Tag objects."""
        # Assumes self.app.unused_tags holds Tag objects (or dicts to be converted)
        # If self.app.unused_tags just holds dicts:
        # return [Tag(tag_data) for tag_data in self.app.unused_tags]
        return self.app.unused_tags if isinstance(self.app.unused_tags, list) else []

    # --- Challenge Retrieval Methods ---

    # & - def get_challenges(self, ...)
    def get_challenges(
        self,
        member_only: bool = True,  # Default to only showing joined/owned
        owned_only: Optional[bool] = None,  # Filter specifically for owned/not owned
        text_contains: Optional[str] = None,
        sort_by: str = "name",  # Default sort by name
        sort_reverse: bool = False,
    ) -> List[Challenge]:
        """Retrieves and filters challenges from the cache.

        Args:
            member_only: If True (default), includes challenges the user is a member of.
                         (Note: API might already filter this depending on how cache was populated).
            owned_only: If True, show only owned. If False, show only joined (not owned).
                        If None, show based on member_only filter.
            text_contains: Filter by name/short_name containing text.
            sort_by: Attribute to sort by ('name', 'member_count', 'created_at').
            sort_reverse: Sort descending.

        Returns:
            List of Challenge objects matching criteria.
        """
        # Assumes self.app.all_challenges_cache holds Challenge objects or Dicts
        # If Dicts, instantiate Challenge objects here. For now, assume objects.
        challenges: List[Challenge] = self.app.all_challenges_cache or []
        filtered_challenges = challenges  # Start with all cached challenges

        my_user_id = self.app.user_data.get("id")  # Get current user ID

        # Apply filters
        if owned_only is not None and my_user_id:
            filtered_challenges = [
                c for c in filtered_challenges if (c.leader_id == my_user_id) == owned_only
            ]
        # Note: member_only is usually handled when *fetching* data into the cache via API.
        # Filtering here might be redundant depending on how the cache is populated.

        if text_contains:
            search_term = text_contains.lower()
            filtered_challenges = [
                c
                for c in filtered_challenges
                if search_term in c.name.lower() or search_term in c.short_name.lower()
            ]

        # Apply sorting
        try:
            default_sort_val: Any = ""
            if sort_by == "member_count":
                default_sort_val = 0
            elif sort_by == "created_at":
                default_sort_val = (
                    datetime.min.replace(tzinfo=timezone.utc) if hasattr(datetime, "min") else 0
                )

            filtered_challenges.sort(
                key=lambda c: getattr(c, sort_by, default_sort_val) or default_sort_val,
                reverse=sort_reverse,
            )
        except AttributeError:
            self.app.console.log(
                f"Warning: Cannot sort challenges by invalid attribute '{sort_by}'",
                style="warning",
            )
        except TypeError as e:
            self.app.console.log(
                f"Warning: Type error sorting challenges by '{sort_by}': {e}", style="warning"
            )

        return filtered_challenges

    # --- Other Data Retrieval (Examples) ---

    # & - def get_user_stats(self) -> Optional[UserStats]:
    def get_user_stats(self) -> Optional[Any]:  # Return your UserStats type
        """Returns the UserStats object."""
        # Assumes self.app.user_stats_obj holds the UserStats instance
        return self.app.user_stats_obj

    # Add methods for getting inbox messages, group chat, etc.
    # These might involve direct API calls if not cached, or filtering cached data.
