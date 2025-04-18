# pixabit/tui/data_store.py

# SECTION: MODULE DOCSTRING
"""Provides the PixabitDataStore class, the central facade for application state and logic.

Manages application data using processed data models, orchestrates asynchronous
API calls via HabiticaAPI, coordinates data processing via TaskProcessor, handles
content caching via GameContent, and notifies the TUI of data changes.
"""

# SECTION: IMPORTS
import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, Union  # Keep Dict/List

from ..models.challenge import Challenge, ChallengeList
from ..models.party import Party

# Renamed 'skill' to 'spell' in models, adjust import if needed
from ..models.spell import Spell, SpellList

# Renamed 'listTag' to 'TagList', adjust import
from ..models.tag import Tag, TagList  # Use TagList
from ..models.task import (
    Task,
    TaskList,
)  # Import Task subclasses if needed for type hints later
from ..models.user import User

# TagManager logic should move into DataStore or be async helpers
# from .tag_manager import TagManager
# Utilities
from ..utils.save_json import save_json  # For saving content cache

# Core services & data structures
from .api import HabiticaAPI, HabiticaAPIError
from .data_processor import TaskProcessor, get_user_stats
from .game_content import GameContent  # Use the specific GameContent manager

# Use themed console/print from utils
try:
    from ..utils.display import console, print
except ImportError:  # Basic fallback console
    import builtins

    print = builtins.print

    class DummyConsole:
        def print(self, *args: Any, **kwargs: Any) -> None:
            builtins.print(*args)

        def log(self, *args: Any, **kwargs: Any) -> None:
            builtins.print("LOG:", *args)

        def print_exception(self, *args: Any, **kwargs: Any) -> None:
            import traceback

            traceback.print_exc()

    console = DummyConsole()


# SECTION: PixabitDataStore Class
# KLASS: PixabitDataStore
class PixabitDataStore:
    """Central facade for managing Habitica data, API interactions, and processing.

    Holds the application state (processed objects) and provides methods for access
    and modification, notifying the UI layer upon data refresh completion.
    """

    # FUNC: __init__
    def __init__(self, app_notify_update: Callable[[], None]):
        """Initializes the DataStore.

        Args:
            app_notify_update: A callable (likely from the TUI App's `call_from_thread` context)
                               invoked after data refresh to signal UI updates are needed.
        """
        self.console = console
        self.console.log("Initializing PixabitDataStore...", style="info")
        self.app_notify_update = app_notify_update  # Callback to signal UI
        try:
            self.api_client = HabiticaAPI()
            self.content_manager = GameContent()  # Uses lazy-loading cache
            # TagManager logic will be integrated here or called carefully if async
            # self.tag_manager = TagManager(self.api_client) # Avoid sync API calls from here
            self.processor: Optional[TaskProcessor] = (
                None  # Initialized during refresh
            )
        except ValueError as e:  # Catch missing credentials from API init
            self.console.print(
                f"[error]FATAL: DataStore Init Error: {e}. Check .env file.[/error]"
            )
            raise  # Propagate critical init errors
        except Exception as e:
            self.console.print(f"[error]DataStore Init Error:[/error] {e}")
            self.console.print_exception(show_locals=False)
            raise

        # --- Application State (using Optional and default empty collections) ---
        self.user_obj: Optional[User] = None
        self.user_stats_dict: Dict[str, Any] = {}  # Start with empty dict
        self.party_obj: Optional[Party] = None
        self.tags_list_obj: Optional[TagList] = None  # Use TagList class
        self.challenges_list_obj: Optional[ChallengeList] = None
        self.tasks_list_obj: Optional[TaskList] = None
        self.spells_list_obj: Optional[SpellList] = None
        # Stored processed categories from TaskProcessor
        self.cats_data: Dict[str, Any] = {
            "tasks": {},
            "tags": [],
            "broken": [],
            "challenge": [],
        }

        # Concurrency control and state flags
        self.is_refreshing: asyncio.Lock = asyncio.Lock()
        self.data_loaded_at_least_once: bool = False

        self.console.log("PixabitDataStore initialized.", style="info")

    # FUNC: refresh_all_data
    async def refresh_all_data(self) -> bool:
        """Fetches all required data concurrently, processes it, updates internal state, and triggers the UI update notification callback.

        Returns:
            True if the refresh process completed successfully (even with non-critical errors),
            False if a critical fetch (user, content, tasks) failed.
        """
        if self.is_refreshing.locked():
            self.console.log(
                "Refresh already in progress, skipping.", style="warning"
            )
            return False  # Indicate not refreshed this time

        # Use async context manager for the lock
        async with self.is_refreshing:
            self.console.log(
                "DataStore: Starting full data refresh...", style="info"
            )
            start_time = time.monotonic()
            success = False  # Overall success flag
            critical_fetch_ok = True  # Track if essential data was fetched

            # Temporary storage for fetched raw data
            raw_data: Dict[str, Any] = {}

            try:
                # --- 1. Fetch Raw Data Concurrently ---
                self.console.log("DataStore: Fetching API data...")
                fetch_tasks = {
                    "user": self.api_client.get_user_data(),
                    "content": self.api_client.get_content(),  # Fetch fresh content
                    "tags": self.api_client.get_tags(),
                    "party": self.api_client.get_party_data(),
                    # Fetch all challenges using pagination helper
                    "challenges": self.api_client.get_all_challenges_paginated(
                        member_only=True
                    ),
                    "tasks": self.api_client.get_tasks(),
                }
                results = await asyncio.gather(
                    *fetch_tasks.values(), return_exceptions=True
                )
                # Map results back to keys
                raw_data = dict(zip(fetch_tasks.keys(), results))

                # --- 2. Validate Critical Data & Update Content Cache ---
                self.console.log(
                    "DataStore: Validating fetched data & updating content cache..."
                )
                # Check for exceptions or None/empty dict/list for critical items
                if isinstance(
                    raw_data.get("user"), Exception
                ) or not raw_data.get("user"):
                    raise raw_data.get("user") or ValueError(
                        "User data fetch failed or was empty."
                    )
                if isinstance(
                    raw_data.get("tasks"), Exception
                ):  # Allow empty task list
                    raise raw_data.get("tasks") or ValueError(
                        "Task data fetch failed."
                    )
                if isinstance(
                    raw_data.get("content"), Exception
                ) or not raw_data.get("content"):
                    raise raw_data.get("content") or ValueError(
                        "Content fetch failed or was empty."
                    )

                # If we got here, critical fetches were okay (or raised exception)
                self.console.log(
                    "DataStore: Critical data fetches successful.",
                    style="success",
                )

                # Update content cache file ONLY if fetch was successful
                save_json(
                    raw_data["content"], self.content_manager.CACHE_FILE_CONTENT
                )
                # Invalidate the content manager's internal cache so it reloads the new file
                # Assuming GameContent has a method like this, or handles it internally
                self.content_manager.invalidate_cache()
                self.console.log(
                    "DataStore: Main content cache file updated and invalidated.",
                    style="info",
                )

                # Handle non-critical fetch errors gracefully
                raw_data["tags"] = self._handle_fetch_result(
                    raw_data.get("tags"), "Tags", default=[]
                )
                raw_data["party"] = self._handle_fetch_result(
                    raw_data.get("party"), "Party", default={}
                )
                raw_data["challenges"] = self._handle_fetch_result(
                    raw_data.get("challenges"), "Challenges", default=[]
                )
                raw_data["tasks"] = self._handle_fetch_result(
                    raw_data.get("tasks"), "Tasks", default=[]
                )  # Ensure list

                # --- 3. Initialize Processor ---
                # Needs validated user_data, party_data, tags, and the content manager
                self.console.log("DataStore: Initializing TaskProcessor...")
                self.processor = TaskProcessor(
                    user_data=raw_data["user"],
                    party_data=raw_data["party"],
                    all_tags_list=raw_data["tags"],
                    game_content_manager=self.content_manager,  # Pass the manager instance
                )

                # --- 4. Process Tasks -> Task Objects & Categories ---
                self.console.log("DataStore: Processing tasks...")
                # Pass raw task list to the processor method
                processed_results = self.processor.process_and_categorize_all(
                    raw_data["tasks"]
                )
                # Dictionary of {task_id: TaskObject}
                processed_task_objects_dict: Dict[str, Task] = (
                    processed_results.get("data", {})
                )
                # Dictionary of categorized task IDs etc.
                self.cats_data = processed_results.get(
                    "cats", self.cats_data
                )  # Update categories

                # --- 5. Instantiate/Update Model Objects & Containers ---
                self.console.log("DataStore: Updating state with new models...")
                self.user_obj = User(
                    raw_data["user"],
                    # Pass gear content for UserStats calculation
                    all_gear_content=self.content_manager.get_gear_data(),
                )
                # Party can be None if user is not in one or fetch failed
                self.party_obj = (
                    Party(raw_data["party"]) if raw_data.get("party") else None
                )
                # Use TagList class
                self.tags_list_obj = TagList(raw_data["tags"])
                # TaskList now takes list of Task objects
                self.tasks_list_obj = TaskList(
                    list(processed_task_objects_dict.values())
                )
                # Pass the TaskList instance for linking tasks to challenges
                self.challenges_list_obj = ChallengeList(
                    raw_data["challenges"], task_list=self.tasks_list_obj
                )

                # --- 6. Calculate Final Aggregate Stats ---
                self.console.log("DataStore: Calculating user stats...")
                stats_result = get_user_stats(
                    cats_dict=self.cats_data,
                    processed_tasks_dict=processed_task_objects_dict,  # Pass processed Task objects
                    user_data=raw_data["user"],  # Pass raw user data
                )
                self.user_stats_dict = stats_result if stats_result else {}

                # --- 7. Instantiate SpellList ---
                # Pass the specific spells section from content manager
                self.spells_list_obj = SpellList(
                    raw_content_spells=self.content_manager.get_skill_data(),
                    current_user_class=(
                        self.user_obj.klass if self.user_obj else None
                    ),
                )

                success = True  # Mark overall success
                self.data_loaded_at_least_once = True
                self.console.log(
                    "DataStore: Refresh successful.", style="success"
                )

            except Exception as e:
                critical_fetch_ok = False  # Mark failure if exception occurred
                self.console.print(
                    f"[error]Error during DataStore refresh sequence:[/error] {e}"
                )
                self.console.print_exception(show_locals=False)
                # Reset state to prevent UI showing stale data on critical failure? Optional.
                # self._reset_state()

            finally:
                # Notify UI regardless of success/failure, UI decides how to handle
                self.console.log("DataStore: Notifying UI for update.")
                # Ensure callback is called safely
                try:
                    self.app_notify_update()
                except Exception as notify_err:
                    self.console.print(
                        f"[error]Error calling UI notification callback:[/error] {notify_err}"
                    )

                end_time = time.monotonic()
                duration = end_time - start_time
                status_msg = (
                    "successful"
                    if success
                    else (
                        "failed"
                        if not critical_fetch_ok
                        else "completed with non-critical errors"
                    )
                )
                log_style = (
                    "success"
                    if success
                    else ("error" if not critical_fetch_ok else "warning")
                )
                self.console.log(
                    f"DataStore: Refresh finished in {duration:.2f}s. Status: {status_msg}",
                    style=log_style,
                )

        # Lock released automatically by async with
        # Return True if critical fetches succeeded, even if non-critical failed
        return critical_fetch_ok

    # FUNC: _handle_fetch_result
    def _handle_fetch_result(
        self, result: Any, name: str, default: Union[List[Any], Dict[Any, Any]]
    ) -> Union[List[Any], Dict[Any, Any]]:
        """Handles results from asyncio.gather, logging errors and returning defaults."""
        if isinstance(result, Exception):
            self.console.log(
                f"Warning: Error fetching {name}: {result}", style="warning"
            )
            return default
        # Basic type check, could be stricter if needed
        if result is None or not isinstance(result, type(default)):
            self.console.log(
                f"Warning: Unexpected type for {name}: {type(result).__name__}. Using default.",
                style="warning",
            )
            return default
        return result

    # FUNC: _reset_state (Optional helper)
    # def _reset_state(self) -> None:
    #      """Resets core data attributes to prevent UI showing stale data after critical failure."""
    #      self.user_obj = None
    #      self.user_stats_dict = {}
    #      self.party_obj = None
    #      self.tags_list_obj = None
    #      self.challenges_list_obj = None
    #      self.tasks_list_obj = None
    #      self.spells_list_obj = None
    #      self.cats_data = {"tasks": {}, "tags": [], "broken": [], "challenge": []}
    #      self.console.log("DataStore state reset due to critical refresh failure.", style="warning")

    # SECTION: Data Accessor Methods (Synchronous - Read current state)

    # FUNC: get_user
    def get_user(self) -> Optional[User]:
        """Returns the current User object, or None if not loaded."""
        return self.user_obj

    # FUNC: get_user_stats
    def get_user_stats(self) -> Dict[str, Any]:
        """Returns the current calculated user stats dictionary."""
        return self.user_stats_dict

    # FUNC: get_party
    def get_party(self) -> Optional[Party]:
        """Returns the current Party object, or None if not in party/not loaded."""
        return self.party_obj

    # FUNC: get_tags
    def get_tags(self, **filters: Any) -> List[Tag]:
        """Returns a list of Tag objects, optionally filtered.

        Args:
            **filters: Keyword arguments for filtering (e.g., tag_type='parent').

        Returns:
            A list of Tag objects.
        """
        if not self.tags_list_obj:
            return []
        # Basic filtering example, enhance TagList if needed
        tags = self.tags_list_obj.tags
        if filters:
            if "tag_type" in filters:
                tags = [t for t in tags if t.tag_type == filters["tag_type"]]
            if "attr" in filters:
                tags = [t for t in tags if t.attr == filters["attr"]]
            # Add more filters as needed
        return tags

    # FUNC: get_tasks
    def get_tasks(self, **filters: Any) -> List[Task]:
        """Returns a list of Task objects, optionally filtered.

        Args:
            **filters: Keyword arguments for filtering (e.g., task_type='daily', status='due').

        Returns:
            A list of Task objects.
        """
        if not self.tasks_list_obj:
            return []
        # Use TaskList's filtering methods if available, or filter manually
        tasks = self.tasks_list_obj.tasks
        if filters:
            task_type = filters.get("task_type")
            status = filters.get("status")
            tag_id = filters.get("tag_id")
            text_filter = filters.get(
                "text_filter", ""
            ).lower()  # Example text filter

            if task_type:
                tasks = [t for t in tasks if t.type == task_type]
            if status:
                tasks = [
                    t
                    for t in tasks
                    if hasattr(t, "_status") and t._status == status
                ]
            if tag_id:
                tasks = [t for t in tasks if tag_id in t.tags]
            if text_filter:
                tasks = [t for t in tasks if text_filter in t.text.lower()]
            # Add more filters
        return tasks

    # FUNC: get_challenges
    def get_challenges(self, **filters: Any) -> List[Challenge]:
        """Returns a list of Challenge objects, optionally filtered.

        Args:
            **filters: Keyword arguments for filtering (e.g., is_broken=True).

        Returns:
            A list of Challenge objects.
        """
        if not self.challenges_list_obj:
            return []
        # Use ChallengeList's filtering methods
        challenges = self.challenges_list_obj.challenges
        if filters:
            if "is_broken" in filters:
                challenges = self.challenges_list_obj.filter_broken(
                    filters["is_broken"]
                )
            if "owned" in filters:
                challenges = [
                    c for c in challenges if c.owned == filters["owned"]
                ]  # Manual filter example
            # Add more filters
        return challenges

    # FUNC: get_spells
    def get_spells(self, **filters: Any) -> List[Spell]:
        """Returns a list of Spell objects, optionally filtered.

        Args:
            **filters: Keyword arguments for filtering (e.g., klass='wizard', available=True).

        Returns:
            A list of Spell objects.
        """
        if not self.spells_list_obj:
            return []
        spells = self.spells_list_obj.spells
        if filters:
            if "klass" in filters:
                spells = self.spells_list_obj.filter_by_class(filters["klass"])
            if filters.get("available") and self.user_obj:
                spells = self.spells_list_obj.get_available_spells(
                    user_level=self.user_obj.level,
                    user_class=self.user_obj.klass,
                )
            # Add more filters
        return spells

    # Add more specific getters as needed by UI components, e.g., get_task_by_id

    # SECTION: Action Methods (Asynchronous - Modify state via API)

    # FUNC: toggle_sleep
    async def toggle_sleep(self) -> bool:
        """Toggles the user's sleep status via API and triggers data refresh."""
        self.console.log("DataStore: Action - Toggle sleep...", style="info")
        try:
            # toggle_user_sleep returns the new state or None on error
            result = await self.api_client.toggle_user_sleep()
            if result is not None:  # Check if API call itself succeeded
                new_state = result  # The actual boolean sleep state
                self.console.log(
                    f"DataStore: Sleep toggle API successful. New state: {new_state}",
                    style="success",
                )
                # Optimistic UI update (optional - update self.user_obj immediately)
                if self.user_obj:
                    self.user_obj.preferences.sleep = bool(new_state)
                    self.user_stats_dict["sleeping"] = bool(
                        new_state
                    )  # Update stats dict too
                    self.app_notify_update()  # Notify UI of immediate change
                # Trigger full refresh in background to confirm state and update everything else
                asyncio.create_task(self.refresh_all_data())
                return True
            else:
                # API might return None or error wasn't caught below
                self.console.print(
                    "DataStore: Sleep toggle API call failed or returned unexpected data.",
                    style="warning",
                )
                return False
        except HabiticaAPIError as e:
            self.console.print(
                f"DataStore: API Error toggling sleep: {e}", style="error"
            )
            return False
        except Exception as e:
            self.console.print(
                f"DataStore: Unexpected error toggling sleep: {e}",
                style="error",
            )
            return False

    # FUNC: score_task
    async def score_task(self, task_id: str, direction: str) -> bool:
        """Scores a task via API and triggers data refresh."""
        self.console.log(
            f"DataStore: Action - Scoring task {task_id} {direction}...",
            style="info",
        )
        try:
            # score_task returns score deltas dict or None on error
            result = await self.api_client.score_task(task_id, direction)
            if result:  # Check if result dict was returned
                self.console.log(
                    f"DataStore: Task {task_id} scored {direction}. Deltas: {result}",
                    style="success",
                )
                # Trigger refresh in background
                asyncio.create_task(self.refresh_all_data())
                # TODO: Consider optimistic UI update based on deltas? Complex.
                return True
            else:
                self.console.print(
                    f"DataStore: Score task API call failed or returned no data for {task_id}.",
                    style="warning",
                )
                return False
        except HabiticaAPIError as e:
            self.console.print(
                f"DataStore: API Error scoring task {task_id}: {e}",
                style="error",
            )
            return False
        except Exception as e:
            self.console.print(
                f"DataStore: Unexpected error scoring task {task_id}: {e}",
                style="error",
            )
            return False

    # FUNC: leave_challenge
    async def leave_challenge(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> bool:
        """Leaves a challenge via API and triggers data refresh."""
        self.console.log(
            f"DataStore: Action - Leaving challenge {challenge_id} (keep={keep})...",
            style="info",
        )
        if keep not in ["keep-all", "remove-all"]:
            self.console.print(
                "Invalid 'keep' parameter for leave_challenge.", style="error"
            )
            return False
        try:
            success = await self.api_client.leave_challenge(
                challenge_id, keep=keep
            )
            if success:
                self.console.log(
                    f"DataStore: Left challenge {challenge_id} successfully.",
                    style="success",
                )
                # Optimistic UI: Remove challenge from self.challenges_list_obj?
                if self.challenges_list_obj:
                    self.challenges_list_obj.challenges = [
                        c
                        for c in self.challenges_list_obj.challenges
                        if c.id != challenge_id
                    ]
                    self.app_notify_update()  # Notify UI of immediate change
                asyncio.create_task(self.refresh_all_data())
                return True
            else:
                self.console.print(
                    f"DataStore: Leave challenge API call failed for {challenge_id}.",
                    style="warning",
                )
                return False
        except HabiticaAPIError as e:
            self.console.print(
                f"DataStore: API Error leaving challenge {challenge_id}: {e}",
                style="error",
            )
            return False
        except Exception as e:
            self.console.print(
                f"DataStore: Unexpected error leaving challenge {challenge_id}: {e}",
                style="error",
            )
            return False

    # FUNC: unlink_task
    async def unlink_task(self, task_id: str, keep: str = "keep") -> bool:
        """Unlinks a single task from its challenge via API and triggers data refresh."""
        self.console.log(
            f"DataStore: Action - Unlinking task {task_id} (keep={keep})...",
            style="info",
        )
        if keep not in ["keep", "remove"]:
            self.console.print(
                "Invalid 'keep' parameter for unlink_task.", style="error"
            )
            return False
        try:
            success = await self.api_client.unlink_task_from_challenge(
                task_id, keep=keep
            )
            if success:
                self.console.log(
                    f"DataStore: Unlinked task {task_id} successfully.",
                    style="success",
                )
                # Optimistic UI: Modify task object in self.tasks_list_obj?
                asyncio.create_task(self.refresh_all_data())
                return True
            else:
                self.console.print(
                    f"DataStore: Unlink task API call failed for {task_id}.",
                    style="warning",
                )
                return False
        except HabiticaAPIError as e:
            self.console.print(
                f"DataStore: API Error unlinking task {task_id}: {e}",
                style="error",
            )
            return False
        except Exception as e:
            self.console.print(
                f"DataStore: Unexpected error unlinking task {task_id}: {e}",
                style="error",
            )
            return False

    # FUNC: delete_tag
    async def delete_tag(self, tag_id: str) -> bool:
        """Deletes a tag globally via API and triggers data refresh."""
        self.console.log(
            f"DataStore: Action - Deleting tag {tag_id} globally...",
            style="info",
        )
        try:
            success = await self.api_client.delete_tag(tag_id)
            if success:
                self.console.log(
                    f"DataStore: Deleted tag {tag_id} successfully.",
                    style="success",
                )
                # Optimistic UI: Remove tag from self.tags_list_obj?
                if self.tags_list_obj:
                    self.tags_list_obj.tags = [
                        t for t in self.tags_list_obj.tags if t.id != tag_id
                    ]
                    self.app_notify_update()  # Notify UI
                asyncio.create_task(self.refresh_all_data())
                return True
            else:
                self.console.print(
                    f"DataStore: Delete tag API call failed for {tag_id}.",
                    style="warning",
                )
                return False
        except HabiticaAPIError as e:
            self.console.print(
                f"DataStore: API Error deleting tag {tag_id}: {e}",
                style="error",
            )
            return False
        except Exception as e:
            self.console.print(
                f"DataStore: Unexpected error deleting tag {tag_id}: {e}",
                style="error",
            )
            return False

    # --- Add more async action methods here for other API calls ---
    # (e.g., set_cds, create_task, update_task, delete_task, checklist actions, etc.)
    # Follow the pattern: call API, handle result/error, trigger refresh, return status.
