# pixabit/tui/data_store.py

# SECTION: MODULE DOCSTRING
"""Provides the PixabitDataStore class, the central facade for application state and logic.

Manages application data using processed data models, orchestrates asynchronous
API calls via HabiticaAPI, coordinates data processing via TaskProcessor, handles
content caching via GameContent, and notifies the TUI of data changes.
"""

# SECTION: IMPORTS
import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union  # Keep Dict/List

from rich.logging import RichHandler
from rich.text import Text
from textual import log
from textual import log as textual_log  # Use textual's log
from textual.app import App

# Use themed console/log from utils
# TagManager logic should move into DataStore or be async helpers
# from .tag_manager import TagManager
# Utilities
from pixabit.helpers._json_helper import (
    load_json,
    save_json,
)  # For saving content cache
from pixabit.helpers.message import DataRefreshed, UIMessage

# Core services & data structures
from pixabit.tui.api import HabiticaAPI, HabiticaAPIError

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
from .data_processor import TaskProcessor, get_user_stats
from .game_content import GameContent  # Use the specific GameContent manager

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)


# SECTION: PixabitDataStore Class
# KLASS: PixabitDataStore
class PixabitDataStore:
    """Central facade for managing Habitica data, API interactions, and processing.

    Holds the application state (processed objects) and provides methods for access
    and modification, notifying the UI layer upon data refresh completion.
    """

    CHALLENGES_CACHE_PATH: Path = Path("challenges_cache.json")

    # FUNC: __init__
    def __init__(self, app: App):
        """Initializes the DataStore.

        Args:
            app_notify_update: A callable (likely from the TUI App's `call_from_thread` context)
                               invoked after data refresh to signal UI updates are needed.
        """
        self.app = app  # Store app instance

        log.info("DataStore: Initializing PixabitDataStore...")
        #        self.app_notify_update = app_notify_update  # Callback to signal UI
        try:
            self.api_client = HabiticaAPI()
            self.content_manager = GameContent()  # Uses lazy-loading cache
            # TagManager logic will be integrated here or called carefully if async
            # self.tag_manager = TagManager(self.api_client) # Avoid sync API calls from here
            self.processor: TaskProcessor | None = None  # Initialized during refresh
        except ValueError as e:  # Catch missing credentials from API init
            log.error(f"[red]FATAL: DataStore Init Error: {e}. Check .env file.[/red]")
            raise  # Propagate critical init errors
        except Exception as e:
            log.error(f"[red]DataStore Init Error:[/red] {e}")
            log.exception(show_locals=False)
            raise

        # --- Application State (using Optional and default empty collections) ---
        self.user_obj: User | None = None
        self.user_stats_dict: dict[str, Any] = {}  # Start with empty dict
        self.party_obj: Party | None = None
        self.tags_list_obj: TagList | None = None  # Use TagList class
        self.raw_challenges_cache: list[dict[str, Any]] = []  # Store raw challenge data

        self.challenges_list_obj: ChallengeList | None = None
        self.tasks_list_obj: TaskList | None = None
        self.spells_list_obj: SpellList | None = None
        # Stored processed categories from TaskProcessor
        self.cats_data: dict[str, Any] = {
            "tasks": {},
            "tags": [],
            "broken": [],
            "challenge": [],
        }

        # Concurrency control and state flags
        self.is_refreshing: asyncio.Lock = asyncio.Lock()
        self.data_loaded_at_least_once: bool = False

        log.info("DataStore: PixabitDataStore initialized.")

    # FUNC: _load_or_fetch_challenges (NEW METHOD)
    async def _load_or_fetch_challenges(self) -> None:
        """Loads challenges from cache or fetches from API if cache is missing/invalid."""
        log.info("DataStore: Loading/Fetching Challenges...")
        loaded_from_cache = False
        # Try loading from cache first
        cached_data = load_json(self.CHALLENGES_CACHE_PATH)
        if isinstance(cached_data, list):  # Check if it's a list (could be empty)
            log.info(f"DataStore: Loaded {len(cached_data)} challenges from cache: '{self.CHALLENGES_CACHE_PATH}'")
            self.raw_challenges_cache = cached_data
            loaded_from_cache = True
        else:
            log.info(f"DataStore: Challenge cache missing or invalid ('{self.CHALLENGES_CACHE_PATH}'). Fetching from API.")

        # Fetch if not loaded from cache
        if not loaded_from_cache:
            try:
                # Use the paginated fetch helper (ensure rate limit fix is applied there)
                fetched_challenges = await self.api_client.get_all_challenges_paginated(member_only=True)
                if isinstance(fetched_challenges, list):
                    log.info(f"DataStore: Fetched {len(fetched_challenges)} challenges from API.")
                    self.raw_challenges_cache = fetched_challenges
                    # Save the fetched data to cache
                    save_ok = save_json(self.raw_challenges_cache, self.CHALLENGES_CACHE_PATH)
                    if save_ok:
                        log.info(f"DataStore: Saved challenges to cache: '{self.CHALLENGES_CACHE_PATH}'")
                    else:
                        log.warning(
                            "DataStore: Failed to save challenges cache.",
                        )
                else:
                    log.error(
                        "DataStore: Fetched challenges API call returned invalid type.",
                    )
                    self.raw_challenges_cache = []  # Use empty list on fetch error
            except Exception as e:
                log.error(f"DataStore: Error fetching challenges: {e}")
                self.raw_challenges_cache = []  # Use empty list on exception

    # FUNC: force_refresh_challenges (NEW - Optional)
    async def force_refresh_challenges(self) -> bool:
        """Forces a fetch of challenges from the API and updates the cache."""
        log.info("DataStore: Forcing challenge refresh from API...")
        try:
            fetched_challenges = await self.api_client.get_all_challenges_paginated(member_only=True)
            if isinstance(fetched_challenges, list):
                log.info(f"DataStore: Force refresh fetched {len(fetched_challenges)} challenges.")
                self.raw_challenges_cache = fetched_challenges
                save_ok = save_json(self.raw_challenges_cache, self.CHALLENGES_CACHE_PATH)
                if save_ok:
                    log.info("DataStore: Force refresh updated challenges cache.")
                # Trigger a full refresh AFTER updating challenges cache to update UI
                asyncio.create_task(self.refresh_all_data())
                return True
            else:
                log.error(
                    "DataStore: Force refresh API call returned invalid type.",
                )
                return False
        except Exception as e:
            log.error(
                f"DataStore: Error during force challenge refresh: {e}",
            )
            return False

    # FUNC: refresh_all_data
    async def refresh_all_data(self) -> bool:
        """Fetches all required data concurrently, processes it, updates internal state, and triggers the UI update notification callback.

        Returns:
            True if the refresh process completed successfully (even with non-critical errors),
            False if a critical fetch (user, content, tasks) failed.
        """
        if self.is_refreshing.locked():
            log.warning("DataStore: Refresh already in progress, skipping.")
            return False  # Indicate not refreshed this time

        # Use async context manager for the lock
        async with self.is_refreshing:
            log.info("DataStore: Starting full data refresh...")
            start_time = time.monotonic()
            success = False  # Overall success flag
            critical_fetch_ok = True  # Track if essential data was fetched

            # Temporary storage for fetched raw data
            raw_data: dict[str, Any] = {}

            try:
                await self._load_or_fetch_challenges()  # Ensure challenges are ready

                # --- 1. Fetch Raw Data Concurrently ---
                log.info("DataStore: Fetching API data...")
                fetch_tasks = {
                    "user": self.api_client.get_user_data(),
                    "content": self.api_client.get_content(),  # Fetch fresh content
                    "tags": self.api_client.get_tags(),
                    "party": self.api_client.get_party_data(),
                    "tasks": self.api_client.get_tasks(),
                }
                results = await asyncio.gather(*fetch_tasks.values(), return_exceptions=True)
                # Map results back to keys
                raw_data = dict(zip(fetch_tasks.keys(), results))

                # --- ADD DETAILED LOGGING HERE ---
                log.info("DataStore: --- Gather Results ---")
                for key, result in raw_data.items():
                    if isinstance(result, Exception):
                        log.error(f"  - {key}: FAILED -> {type(result).__name__}: {result}")
                    elif result is None:
                        log.info(f"  - {key}: SUCCESS -> None")
                    elif isinstance(result, list):
                        log.info(f"  - {key}: SUCCESS -> List (len={len(result)})")
                    elif isinstance(result, dict):
                        log.info(f"  - {key}: SUCCESS -> Dict (keys={list(result.keys())[:5]}...)")  # Show first 5 keys
                    else:
                        log.info(f"  - {key}: SUCCESS -> Unknown type: {type(result).__name__}")
                log.info("DataStore: --- End Gather Results ---")
                # --- END ADDED LOGGING ---

                # --- 2. Validate Critical Data & Update Content Cache ---
                log.info("DataStore: Validating fetched data & updating content cache...")
                # Check for exceptions or None/empty dict/list for critical items
                if isinstance(raw_data.get("user"), Exception) or not raw_data.get("user"):
                    raise raw_data.get("user") or ValueError("User data fetch failed or was empty.")
                if isinstance(raw_data.get("tasks"), Exception):  # Allow empty task list
                    raise raw_data.get("tasks") or ValueError("Task data fetch failed.")
                if isinstance(raw_data.get("content"), Exception) or not raw_data.get("content"):
                    raise raw_data.get("content") or ValueError("Content fetch failed or was empty.")

                # If we got here, critical fetches were okay (or raised exception)
                log.info(
                    "DataStore: Critical data fetches successful.",
                )

                # Update content cache file ONLY if fetch was successful
                # save_json(
                #    raw_data["content"], self.content_manager.CACHE_FILE_PATH
                # )
                # Invalidate the content manager's internal cache so it reloads the new file
                # Assuming GameContent has a method like this, or handles it internally
                self.content_manager.invalidate_cache()
                log.info(
                    "DataStore: Main content cache file updated and invalidated.",
                )

                # Handle non-critical fetch errors gracefully
                log.info("DataStore: Pre-fetching content for Processor/Models...")
                # Await necessary content sections HERE
                gear_data = await self.content_manager.get_gear_data()
                quests_data = await self.content_manager.get_quest_data()
                spells_data = await self.content_manager.get_skill_data()  # <--- Await THIS call
                log.info("DataStore: Content getters awaited.")
                # --- !!! END Pre-fetch block !!! ---

                # --- 3. Initialize Processor ---
                # Needs validated user_data, party_data, tags, and the content manager
                log.info("DataStore: Initializing TaskProcessor...")
                # Pass the *results* (dictionaries) obtained above
                self.processor = TaskProcessor(
                    user_data=raw_data["user"],
                    party_data=raw_data["party"],
                    all_tags_list=raw_data["tags"],
                    gear_data_lookup=gear_data,  # Pass the awaited dict
                    quests_data_lookup=quests_data,  # Pass the awaited dict
                )
                log.info("DataStore: TaskProcessor Initialized successfully.")

                # --- 4. Process Tasks ---
                log.info("DataStore: Processing tasks...")
                processed_results = self.processor.process_and_categorize_all(raw_data["tasks"])
                processed_task_objects_dict: dict[str, Task] = processed_results.get("data", {})
                self.cats_data = processed_results.get("cats", self.cats_data)
                log.info(f"DataStore: Tasks processed. Found {len(processed_task_objects_dict)} tasks.")

                # --- 5. Instantiate/Update Model Objects & Containers ---
                log.info("DataStore: Updating state with new models...")
                try:  # Wrap model instantiation
                    self.user_obj = User(
                        raw_data["user"],
                        # Pass the awaited gear_data here too
                        all_gear_content=gear_data,
                    )
                    self.party_obj = Party(raw_data["party"]) if raw_data.get("party") else None
                    self.tags_list_obj = TagList(raw_data["tags"])
                    self.tasks_list_obj = TaskList(list(processed_task_objects_dict.values()))
                    self.challenges_list_obj = ChallengeList(self.raw_challenges_cache, task_list=self.tasks_list_obj)
                    # Instantiate SpellList using awaited spells_data

                    log.info(f"DataStore: BEFORE SpellList init. Type of spells_data: {type(spells_data).__name__}")
                    if isinstance(spells_data, dict):
                        log.info(f"   Keys: {list(spells_data.keys())[:5]}")
                    # --- End Re-check ---
                    self.spells_list_obj = SpellList(
                        raw_content_spells=spells_data,  # Pass awaited dict
                        current_user_class=(self.user_obj.klass if self.user_obj else None),
                    )
                    log.info("DataStore: SpellList instantiation attempted.")

                    log.info("DataStore: Models updated.")
                except Exception as model_err:
                    log.error(f"[red]DataStore: FAILED during model instantiation:[/red] {model_err}")
                    raise  # Likely critical if models fail

                # --- 6. Calculate Final Aggregate Stats ---
                log.info("DataStore: Calculating user stats...")
                try:
                    stats_result = get_user_stats(
                        cats_dict=self.cats_data,
                        processed_tasks_dict=processed_task_objects_dict,
                        user_data=raw_data["user"],
                    )
                    # Check if stats_result is None or empty
                    if stats_result is None:
                        log.warning(
                            "DataStore: get_user_stats returned None.",
                        )
                        self.user_stats_dict = {}  # Ensure it's an empty dict
                    elif not stats_result:
                        log.warning(
                            "DataStore: get_user_stats returned empty dict.",
                        )
                        self.user_stats_dict = {}
                    else:
                        self.user_stats_dict = stats_result
                        log.info(
                            f"DataStore: User stats calculated: { {k: v for k, v in self.user_stats_dict.items() if k in ['level', 'hp', 'mp']} }..."
                        )  # Log a sample
                except Exception as stats_err:
                    log.error(f"[red]DataStore: FAILED during stats calculation:[/red] {stats_err}")
                    self.user_stats_dict = {}  # Reset on error
                    # Decide if this is critical - maybe not? Let refresh finish.
                    # raise # Or re-raise if stats are critical

                # --- 7. Instantiate SpellList ---
                # Pass the specific spells section from content manager
                log.info("DataStore: SpellList updated.")

                success = True  # Mark overall success
                self.data_loaded_at_least_once = True
                log.info(
                    "DataStore: Refresh sequence inside try block completed.",
                )

            except Exception as e:
                critical_fetch_ok = False  # Mark failure if exception occurred
                log.error(f"[red]Error during DataStore refresh sequence:[/red] {e}")
                log.exception(show_locals=False)
                # Reset state to prevent UI showing stale data on critical failure? Optional.
                # self._reset_state()

            finally:
                # Notify UI regardless of success/failure, UI decides how to handle
                log.info("DataStore: Notifying UI for update.")
                # Ensure callback is called safely
                try:
                    self.app.post_message(DataRefreshed())
                    textual_log.info("DataStore: Posted DataRefreshed message.")

                except Exception as e:
                    textual_log.error(f"DataStore: Failed to post DataRefreshed message: {e}")

                end_time = time.monotonic()
                duration = end_time - start_time
                status_msg = "successful" if success else ("failed" if not critical_fetch_ok else "completed with non-critical errors")
                log_style = "success" if success else ("error" if not critical_fetch_ok else "warning")
                log.info(
                    f"DataStore: Refresh finished in {duration:.2f}s. Status: {status_msg}",
                )

        # Lock released automatically by async with
        # Return True if critical fetches succeeded, even if non-critical failed
        return critical_fetch_ok

    # FUNC: _handle_fetch_result
    def _handle_fetch_result(self, result: Any, name: str, default: Union[list[Any], dict[Any, Any]]) -> Union[list[Any], dict[Any, Any]]:
        """Handles results from asyncio.gather, logging errors and returning defaults."""
        if isinstance(result, Exception):
            log.warning(f"DataStore: Warning: Error fetching {name}: {result}")
            return default
        # Basic type check, could be stricter if needed
        if result is None or not isinstance(result, type(default)):
            log.warning(
                f"DataStore: Warning: Unexpected type for {name}: {type(result).__name__}. Using default.",
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
    #      log.warning("DataStore state reset due to critical refresh failure.")

    # SECTION: Data Accessor Methods (Synchronous - Read current state)

    # FUNC: get_user
    def get_user(self) -> User | None:
        """Returns the current User object, or None if not loaded."""
        return self.user_obj

    # FUNC: get_user_stats
    def get_user_stats(self) -> dict[str, Any]:
        """Returns the current calculated user stats dictionary."""
        return self.user_stats_dict

    # FUNC: get_party
    def get_party(self) -> Party | None:
        """Returns the current Party object, or None if not in party/not loaded."""
        return self.party_obj

    # FUNC: get_tags
    def get_tags(self, **filters: Any) -> list[Tag]:
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
    def get_tasks(self, **filters: Any) -> list[Task]:
        """Returns a list of Task objects, optionally filtered.

        Args:
            **filters: Keyword arguments for filtering (e.g., task_type='daily', status='due').

        Returns:
            A list of Task objects.
        """
        # Si la lista principal no se ha cargado, devuelve una TaskList vacía.
        if self.tasks_list_obj is None:
            self.console.log("DataStore.get_tasks called before tasks loaded, returning empty TaskList.")
            return TaskList([])  # Devuelve una instancia vacía

        # Empieza con la lista completa de tareas almacenada en el DataStore.
        filtered_task_list_obj: TaskList = self.tasks_list_obj

        # Aplica los filtros en cadena, usando los métodos de la clase TaskList.
        # Cada método de filtro debe devolver una *nueva* instancia de TaskList.
        if filters:
            task_type = filters.get("task_type")
            if task_type:
                # Llama al método de filtro en el objeto TaskList actual
                filtered_task_list_obj = filtered_task_list_obj.filter_by_type(task_type)

            status = filters.get("status")
            if status:
                filtered_task_list_obj = filtered_task_list_obj.filter_by_status(status)

            tag_id = filters.get("tag_id")
            if tag_id:
                filtered_task_list_obj = filtered_task_list_obj.filter_by_tag_id(tag_id)

            text_filter = filters.get("text_filter")
            if text_filter:  # Asegúrate que filter_by_text existe en TaskList
                filtered_task_list_obj = filtered_task_list_obj.filter_by_text(text_filter)

            # Añade aquí llamadas a otros métodos de filtro que implementes en TaskList
            # Ejemplo:
            # priority = filters.get("priority")
            # if priority:
            #     filtered_task_list_obj = filtered_task_list_obj.filter_by_priority(exact_priority=priority)

        # Devuelve el objeto TaskList final (original o filtrado).
        return filtered_task_list_obj

    # FUNC: get_challenges
    def get_challenges(self, **filters: Any) -> list[Challenge]:
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
                challenges = self.challenges_list_obj.filter_broken(filters["is_broken"])
            if "owned" in filters:
                challenges = [c for c in challenges if c.owned == filters["owned"]]  # Manual filter example
            # Add more filters
        return challenges

    # FUNC: get_spells
    def get_spells(self, **filters: Any) -> list[Spell]:
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
        log.info("DataStore: Action - Toggle sleep...")
        try:
            # toggle_user_sleep returns the new state or None on error
            result = await self.api_client.toggle_user_sleep()
            if result is not None:  # Check if API call itself succeeded
                new_state = result  # The actual boolean sleep state
                textual_log.info(Text.from_markup(f"[success]DataStore: Sleep toggle API successful. New state: {new_state}[/success]"))
                success_msg = f"Sleep status successfully set to: {new_state}"
                log.info(f">>> Posting UIMessage (SUCCESS): {success_msg}")  # ADD LOG
                self.app.post_message(UIMessage(success_msg, severity="information"))  # Optional success msg

                # Optimistic UI update (optional - update self.user_obj immediately)
                if self.user_obj:
                    self.user_obj.preferences.sleep = bool(new_state)
                    self.user_stats_dict["sleeping"] = bool(new_state)  # Update stats dict too
                    self.app.post_message(UIMessage(f"Sleep status set to: {new_state}"))

                    # self.app_notify_update()  # Notify UI of immediate change
                # Trigger full refresh in background to confirm state and update everything else
                asyncio.create_task(self.refresh_all_data())
                return True
            else:
                # API might return None or error wasn't caught below
                log.warning(
                    "DataStore: Sleep toggle API call failed or returned unexpected data.",
                )
                self.app.post_message(UIMessage("Failed to toggle sleep via API.", severity="warning"))

                return False
        except HabiticaAPIError as e:
            msg_text = f"API Error toggling sleep: {e}"

            log.info(f">>> Posting UIMessage (API ERROR): {msg_text}")  # ADD LOG

            textual_log.error(Text.from_markup(f"[error]DataStore: API Error toggling sleep:[/error] {e}"))
            self.app.post_message(UIMessage(msg_text, severity="error"))
            return False
        except Exception as e:
            msg_text = "Unexpected error toggling sleep."
            log.info(f">>> Posting UIMessage (UNEXPECTED ERROR): {msg_text}")  # ADD LOG

            textual_log.exception(Text.from_markup("[error]DataStore: Unexpected error toggling sleep:[/error]"))
            self.app.post_message(UIMessage(msg_text, severity="error"))

            return False

    # FUNC: score_task
    async def score_task(self, task_id: str, direction: str) -> bool:
        """Scores a task via API and triggers data refresh."""
        log.info(
            f"DataStore: Action - Scoring task {task_id} {direction}...",
        )
        try:
            # score_task returns score deltas dict or None on error
            result = await self.api_client.score_task(task_id, direction)
            if result:  # Check if result dict was returned
                log.info(
                    f"DataStore: Task {task_id} scored {direction}. Deltas: {result}",
                )
                # Trigger refresh in background
                asyncio.create_task(self.refresh_all_data())
                # TODO: Consider optimistic UI update based on deltas? Complex.
                return True
            else:
                log.warning(
                    f"DataStore: Score task API call failed or returned no data for {task_id}.",
                )
                return False
        except HabiticaAPIError as e:
            log.error(
                f"DataStore: API Error scoring task {task_id}: {e}",
            )
            return False
        except Exception as e:
            log.error(
                f"DataStore: Unexpected error scoring task {task_id}: {e}",
            )
            return False

    # FUNC: leave_challenge
    async def leave_challenge(self, challenge_id: str, keep: str = "keep-all") -> bool:
        """Leaves a challenge via API and triggers data refresh."""
        log.info(
            f"DataStore: Action - Leaving challenge {challenge_id} (keep={keep})...",
        )
        if keep not in ["keep-all", "remove-all"]:
            log.error("DataStore: Invalid 'keep' parameter for leave_challenge.")
            return False
        try:
            success = await self.api_client.leave_challenge(challenge_id, keep=keep)
            if success:
                log.info(
                    f"DataStore: Left challenge {challenge_id} successfully.",
                )
                # Optimistic UI: Remove challenge from self.challenges_list_obj?
                if self.challenges_list_obj:
                    self.challenges_list_obj.challenges = [c for c in self.challenges_list_obj.challenges if c.id != challenge_id]
                    self.app_notify_update()  # Notify UI of immediate change
                asyncio.create_task(self.refresh_all_data())
                return True
            else:
                log.warning(
                    f"DataStore: Leave challenge API call failed for {challenge_id}.",
                )
                return False
        except HabiticaAPIError as e:
            log.error(
                f"DataStore: API Error leaving challenge {challenge_id}: {e}",
            )
            return False
        except Exception as e:
            log.error(
                f"DataStore: Unexpected error leaving challenge {challenge_id}: {e}",
            )
            return False

    # FUNC: unlink_task
    async def unlink_task(self, task_id: str, keep: str = "keep") -> bool:
        """Unlinks a single task from its challenge via API and triggers data refresh."""
        log.info(
            f"DataStore: Action - Unlinking task {task_id} (keep={keep})...",
        )
        if keep not in ["keep", "remove"]:
            log.error("DataStore: Invalid 'keep' parameter for unlink_task.")
            return False
        try:
            success = await self.api_client.unlink_task_from_challenge(task_id, keep=keep)
            if success:
                log.info(
                    f"DataStore: Unlinked task {task_id} successfully.",
                )
                # Optimistic UI: Modify task object in self.tasks_list_obj?
                asyncio.create_task(self.refresh_all_data())
                return True
            else:
                log.warning(
                    f"DataStore: Unlink task API call failed for {task_id}.",
                )
                return False
        except HabiticaAPIError as e:
            log.error(
                f"DataStore: API Error unlinking task {task_id}: {e}",
            )
            return False
        except Exception as e:
            log.error(
                f"DataStore: Unexpected error unlinking task {task_id}: {e}",
            )
            return False

    # FUNC: delete_tag
    async def delete_tag(self, tag_id: str) -> bool:
        """Deletes a tag globally via API and triggers data refresh."""
        log.info(
            f"DataStore: Action - Deleting tag {tag_id} globally...",
        )
        try:
            success = await self.api_client.delete_tag(tag_id)
            if success:
                log.info(
                    f"DataStore: Deleted tag {tag_id} successfully.",
                )
                # Optimistic UI: Remove tag from self.tags_list_obj?
                if self.tags_list_obj:
                    self.tags_list_obj.tags = [t for t in self.tags_list_obj.tags if t.id != tag_id]
                    self.app_notify_update()  # Notify UI
                asyncio.create_task(self.refresh_all_data())
                return True
            else:
                log.warning(
                    f"DataStore: Delete tag API call failed for {tag_id}.",
                )
                return False
        except HabiticaAPIError as e:
            log.error(
                f"DataStore: API Error deleting tag {tag_id}: {e}",
            )
            return False
        except Exception as e:
            log.error(
                f"DataStore: Unexpected error deleting tag {tag_id}: {e}",
            )
            return False

    # --- Add more async action methods here for other API calls ---
    # (e.g., set_cds, create_task, update_task, delete_task, checklist actions, etc.)
    # Follow the pattern: call API, handle result/error, trigger refresh, return status.
