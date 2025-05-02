# pixabit/services/data_manager.py

# ─── Title ────────────────────────────────────────────────────────────────────
#          Habitica Data Orchestration Manager (Live Data Focus)
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Provides a DataManager class for loading, caching (live data as files), processing,
and accessing current Habitica Pydantic models (User, Tasks, Tags, Party, Challenges).
Coordinates API client, static content manager, and models. Persistent archiving
is handled by a separate Archiver class.
"""

# SECTION: IMPORTS
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Coroutine, Dict, Type

from pydantic import ValidationError

from pixabit.api.client import HabiticaClient
from pixabit.config import DEFAULT_CACHE_DURATION_DAYS, HABITICA_DATA_PATH, USER_ID
from pixabit.helpers._json import load_json, load_pydantic_model, save_json, save_pydantic_model
from pixabit.helpers._logger import log
from pixabit.helpers.DateTimeHandler import DateTimeHandler
from pixabit.models.challenge import Challenge, ChallengeList
from pixabit.models.game_content import Gear, Quest, StaticContentManager
from pixabit.models.party import Party
from pixabit.models.tag import Tag, TagList
from pixabit.models.task import AnyTask, Task, TaskList  # Need Task for user calc type hints if used
from pixabit.models.user import User

# SECTION: CONSTANTS & CONFIG

DEFAULT_LIVE_CACHE_TIMEOUT = timedelta(minutes=5)
DEFAULT_CHALLENGE_CACHE_TIMEOUT = timedelta(hours=2)
CACHE_SUBDIR_RAW = "raw"
CACHE_SUBDIR_PROCESSED = "processed"


# SECTION: DATA MANAGER CLASS
class DataManager:
    """Centralized manager for fetching, caching, processing, and accessing
    Habitica data models. Orchestrates API interaction and model processing.
    """

    def __init__(
        self,
        api_client: HabiticaClient,
        static_content_manager: StaticContentManager,
        cache_dir: Path = HABITICA_DATA_PATH,
        live_cache_timeout: timedelta = DEFAULT_LIVE_CACHE_TIMEOUT,
        challenge_cache_timeout: timedelta = DEFAULT_CHALLENGE_CACHE_TIMEOUT,
    ):
        """Initializes the DataManager.

        Args:
            api_client: An instance of HabiticaClient.
            static_content_manager: An instance of StaticContentManager.
            cache_dir: Base directory for caching data.
            live_cache_timeout: Duration for which cached live data is considered fresh.
        """
        self.api = api_client
        self.static_content_manager = static_content_manager
        self.cache_dir = cache_dir
        self.live_cache_timeout = live_cache_timeout
        self.challenge_cache_timeout = challenge_cache_timeout

        # Standard Cache Dirs
        self.raw_cache_dir = self.cache_dir / CACHE_SUBDIR_RAW
        self.processed_cache_dir = self.cache_dir / CACHE_SUBDIR_PROCESSED
        self.raw_cache_dir.mkdir(parents=True, exist_ok=True)
        self.processed_cache_dir.mkdir(parents=True, exist_ok=True)

        # Internal storage for LIVE data models
        self._user: User | None = None
        self._tasks: TaskList | None = None
        self._tags: TagList | None = None
        self._party: Party | None = None
        self._challenges: ChallengeList | None = None

        self._last_refresh_times: dict[str, datetime | None] = {
            "user": None,
            "tasks": None,
            "tags": None,
            "party": None,
            "challenges": None,
        }
        log.info(f"DataManager initialized. Cache Dir: {self.cache_dir}")

    # --- Cache Helper ---
    def _is_live_cache_stale(self, data_key: str) -> bool:
        """Checks if the LIVE cache for a specific data key is stale."""
        last_refresh = self._last_refresh_times.get(data_key)
        if last_refresh is None:
            return True
        timeout = self.challenge_cache_timeout if data_key == "challenges" else self.live_cache_timeout
        now_utc = datetime.now(timezone.utc)
        if last_refresh.tzinfo is None:
            last_refresh = last_refresh.replace(tzinfo=timezone.utc)
        is_stale = (now_utc - last_refresh) > timeout
        log.debug(f"Live cache check for '{data_key}': Stale={is_stale}")
        return is_stale

    def _get_cache_path(self, filename: str, processed: bool) -> Path:
        """Gets the full path for a cached file."""
        dir_path = self.processed_cache_dir if processed else self.raw_cache_dir
        return dir_path / filename

    def _update_refresh_time(self, data_key: str):
        """Updates the last refresh time for a given key."""
        self._last_refresh_times[data_key] = datetime.now(timezone.utc)

    # --- Properties for Accessing Data ---
    # Provides controlled access to the managed models

    @property
    def user(self) -> User | None:
        """Returns the loaded User object."""
        return self._user

    @property
    def tasks(self) -> TaskList | None:
        """Returns the loaded TaskList object."""
        return self._tasks

    @property
    def tags(self) -> TagList | None:  # Or AdvancedTagList
        """Returns the loaded TagList object."""
        return self._tags

    @property
    def party(self) -> Party | None:
        """Returns the loaded Party object."""
        return self._party

    @property
    def challenges(self) -> ChallengeList | None:
        return self._challenges

    # --- Static data access (unchanged) ---
    @property
    def static_gear_data(self) -> dict[str, Gear] | None:
        """Returns cached static gear data directly from the StaticContentManager (if loaded)."""
        # Note: This doesn't trigger loading, assumes load_all_data or equivalent called first.
        if self.static_content_manager._content:
            return self.static_content_manager._content.gear
        return None

    @property
    def static_quest_data(self) -> dict[str, Quest] | None:
        """Returns cached static quest data directly from the StaticContentManager (if loaded)."""
        if self.static_content_manager._content:
            return self.static_content_manager._content.quests
        return None

    # --- Loading Methods for LIVE Data ---

    async def load_user(self, force_refresh: bool = False) -> User | None:
        """Loads User data from cache or API."""
        data_key = "user"
        filename = "user.json"
        model_class = User

        if not force_refresh and self._user and not self._is_live_cache_stale(data_key):
            log.debug("Using in-memory user data.")
            return self._user

        # Try loading from processed cache first
        processed_path = self._get_cache_path(filename, processed=True)
        if not force_refresh and processed_path.exists():
            # Check modification time against timeout for file cache
            mtime = datetime.fromtimestamp(processed_path.stat().st_mtime, timezone.utc)
            if (datetime.now(timezone.utc) - mtime) <= self.live_cache_timeout:
                log.debug(f"Attempting to load user from processed cache: {processed_path}")
                cached_model = load_pydantic_model(model_class, processed_path)
                if cached_model:
                    self._user = cached_model
                    self._update_refresh_time(data_key)  # Update timestamp based on cache load
                    log.info("User loaded from fresh processed cache.")
                    return self._user
                else:
                    log.warning(f"Failed to load user model from presumably fresh cache file: {processed_path}")
            else:
                log.info("User processed cache file is stale.")

        # Fetch from API
        log.info(f"{'Forcing refresh for' if force_refresh else 'Fetching'} user data from API...")
        try:
            raw_data = await self.api.get_user_data()
            if not raw_data:
                log.error("Received empty data from user API endpoint.")
                # Should we return stale cache if available? Or None? Return None for now.
                self._user = None  # Clear potentially stale user
                return None

            # Validate raw data into model
            self._user = model_class.model_validate(raw_data)
            self._update_refresh_time(data_key)

            # Save raw and processed data
            save_json(raw_data, filename, folder=self.raw_cache_dir)
            save_pydantic_model(self._user, filename, folder=self.processed_cache_dir)
            log.success("User data fetched and processed.")
            return self._user

        except Exception as e:
            log.exception("Failed to fetch or process user data from API.")
            # Fallback to potentially stale in-memory data? Or clear? Clear is safer.
            self._user = None
            return None

    async def load_tasks(self, force_refresh: bool = False) -> TaskList | None:
        """Loads TaskList from cache or API."""
        data_key = "tasks"
        filename = "tasks.json"
        # Note: TaskList is a class, not a Pydantic model itself for saving/loading directly.
        # We cache the *list* of task dictionaries after TaskList validation.

        if not force_refresh and self._tasks and not self._is_live_cache_stale(data_key):
            log.debug("Using in-memory tasks data.")
            return self._tasks

        processed_path = self._get_cache_path(filename, processed=True)
        if not force_refresh and processed_path.exists():
            mtime = datetime.fromtimestamp(processed_path.stat().st_mtime, timezone.utc)
            if (datetime.now(timezone.utc) - mtime) <= self.live_cache_timeout:
                log.debug(f"Attempting to load tasks from processed cache: {processed_path}")
                # Load the *list* of task dicts from cache
                cached_task_dicts = load_json(processed_path)
                if isinstance(cached_task_dicts, list):
                    try:
                        # --- CHANGE HERE: Use from_processed_dicts ---
                        self._tasks = TaskList.from_processed_dicts(cached_task_dicts)

                        self._update_refresh_time(data_key)
                        log.success("Tasks loaded successfully from fresh processed cache.")
                        return self._tasks
                    except Exception as e:
                        log.exception(f"Error re-creating TaskList from cached data: {e}")
                else:
                    log.warning(f"Invalid data format in tasks cache file: {processed_path}. Expected list.")
            else:
                log.info("Tasks processed cache file is stale.")

        log.info(f"{'Forcing refresh for' if force_refresh else 'Fetching'} tasks data from API...")
        try:
            raw_data = await self.api.get_tasks()  # Returns list[dict]
            if not isinstance(raw_data, list):
                log.error(f"Received unexpected data type from tasks API: {type(raw_data)}")
                self._tasks = None
                return None
            self._tasks = TaskList.from_raw_api_list(raw_data)
            self._update_refresh_time(data_key)
            save_json(raw_data, filename, folder=self.raw_cache_dir)
            # Save the list of *processed* task dictionaries
            self._tasks.save_to_json(filename, folder=self.processed_cache_dir)
            log.success("Tasks data fetched and processed.")
            return self._tasks

        except Exception as e:
            log.exception("Failed to fetch or process tasks data from API.")
            self._tasks = None
            return None

    async def load_tags(self, force_refresh: bool = False) -> TagList | None:
        """Loads TagList from cache or API."""
        data_key = "tags"
        filename = "tags.json"
        model_class = TagList  # Simple TagList BaseModel

        if not force_refresh and self._tags and not self._is_live_cache_stale(data_key):
            log.debug("Using in-memory tags data.")
            return self._tags

        processed_path = self._get_cache_path(filename, processed=True)
        if not force_refresh and processed_path.exists():
            mtime = datetime.fromtimestamp(processed_path.stat().st_mtime, timezone.utc)
            if (datetime.now(timezone.utc) - mtime) <= self.live_cache_timeout:
                log.debug(f"Attempting to load tags from processed cache: {processed_path}")
                cached_model = load_pydantic_model(model_class, processed_path)
                if cached_model:
                    self._tags = cached_model
                    self._update_refresh_time(data_key)
                    log.info("Tags loaded from fresh processed cache.")
                    return self._tags
                else:
                    log.warning(f"Failed to load tags model from cache: {processed_path}")
            else:
                log.info("Tags processed cache file is stale.")

        log.info(f"{'Forcing refresh for' if force_refresh else 'Fetching'} tags data from API...")
        try:
            raw_data = await self.api.get_tags()  # Returns list[dict]
            if not isinstance(raw_data, list):
                log.error(f"Received unexpected data type from tags API: {type(raw_data)}")
                self._tags = None
                return None

            # Validate raw data using TagList's factory method
            self._tags = model_class.from_raw_data(raw_data)
            self._update_refresh_time(data_key)

            save_json(raw_data, filename, folder=self.raw_cache_dir)
            # Save the processed TagList model
            save_pydantic_model(self._tags, filename, folder=self.processed_cache_dir)
            log.success("Tags data fetched and processed.")
            return self._tags

        except Exception as e:
            log.exception("Failed to fetch or process tags data from API.")
            self._tags = None
            return None

    async def load_party(self, force_refresh: bool = False) -> Party | None:
        """Loads Party data from cache or API."""
        data_key = "party"
        filename = "party.json"
        model_class = Party

        # Party data includes chat, needs user context for validation
        # Get current USER_ID from config - assumes it's correctly set
        user_id_context = USER_ID
        if not user_id_context:
            log.error("USER_ID not configured. Cannot accurately process party chat messages.")
            # Decide whether to proceed without context or fail. Proceeding with warning.

        # Pass context to load_pydantic_model if needed
        validation_context = {"current_user_id": user_id_context}
        #        self._challenges = ChallengeList.from_raw_data(all_raw_challenges, context=validation_context)  # <<< Pass context

        if not force_refresh and self._party and not self._is_live_cache_stale(data_key):
            log.debug("Using in-memory party data.")
            return self._party

        processed_path = self._get_cache_path(filename, processed=True)
        if not force_refresh and processed_path.exists():
            mtime = datetime.fromtimestamp(processed_path.stat().st_mtime, timezone.utc)
            if (datetime.now(timezone.utc) - mtime) <= self.live_cache_timeout:
                log.debug(f"Attempting to load party from processed cache: {processed_path}")
                cached_model = load_pydantic_model(model_class, processed_path, context=validation_context)
                if cached_model:
                    self._party = cached_model
                    self._update_refresh_time(data_key)
                    log.info("Party loaded from fresh processed cache.")
                    return self._party
                else:
                    log.warning(f"Failed to load party model from cache: {processed_path}")
            else:
                log.info("Party processed cache file is stale.")

        log.info(f"{'Forcing refresh for' if force_refresh else 'Fetching'} party data from API...")
        try:
            raw_data = await self.api.get_party_data()  # Returns dict or None
            if not isinstance(raw_data, dict):
                # Handle API returning null/empty if not in party
                log.info("User is likely not in a party (API returned non-dict).")
                self._party = None  # Ensure party is None
                # Cache this None state? Maybe cache an empty dict raw/processed? Cache None for now.
                self._update_refresh_time(data_key)  # Update timestamp even for None result
                return None

            # Create Party model using factory method which handles context
            self._party = model_class.create_from_raw_data(raw_data, current_user_id=user_id_context)
            self._update_refresh_time(data_key)

            save_json(raw_data, filename, folder=self.raw_cache_dir)
            # Save the Party model (chat excluded by default based on field def)
            save_pydantic_model(self._party, filename, folder=self.processed_cache_dir)
            log.success("Party data fetched and processed.")
            return self._party

        except Exception as e:
            log.exception("Failed to fetch or process party data from API.")
            self._party = None  # Clear party on error
            return None

    # --- Modified load_challenges() ---
    async def load_challenges(self, force_refresh: bool = False) -> ChallengeList | None:
        """Loads LIVE user challenges list, saves raw/processed, handling pagination and caching."""
        data_key = "challenges"
        live_filename = "challenges.json"
        model_class = ChallengeList

        if not force_refresh and self._challenges and not self._is_live_cache_stale(data_key):
            log.debug("Using in-memory challenges data.")  # Added log
            return self._challenges

        live_processed_path = self._get_cache_path(live_filename, processed=True)
        # --- Determine User ID for context ---
        # Use loaded user if available, otherwise fallback to config
        user_id_context = self._user.id if self._user else USER_ID
        if not user_id_context:
            log.warning("Cannot determine current user ID for challenge context (ownership/joining). Proceeding without.")
        validation_context = {"current_user_id": user_id_context}
        # --- End User ID determination ---

        # Try loading from processed cache
        if not force_refresh and live_processed_path.exists():
            mtime = datetime.fromtimestamp(live_processed_path.stat().st_mtime, timezone.utc)
            timeout = self.challenge_cache_timeout  # Use specific timeout for challenges
            if (datetime.now(timezone.utc) - mtime) <= timeout:
                log.debug(f"Attempting to load challenges from processed cache: {live_processed_path}")
                # Pass context when loading from cache too, for re-validation consistency
                cached_model = load_pydantic_model(model_class, live_processed_path, context=validation_context)
                if cached_model:
                    self._challenges = cached_model
                    self._update_refresh_time(data_key)  # Update based on cache load time
                    log.info(f"Live challenges loaded from fresh processed cache ({len(self._challenges)} challenges).")
                    # --- Re-link tasks if loading from cache? ---
                    # If tasks are also loaded, linking might be needed again unless the cached
                    # challenges *already include* the tasks persistently. Assuming save_pydantic_model saves nested tasks.
                    # Let's rely on process_loaded_data to handle linking after all data is loaded.
                    return self._challenges
                else:
                    log.warning(f"Failed loading challenges model from cache file: {live_processed_path}")
            else:
                log.info("Live challenges processed cache stale.")

        # Fetch from API
        log.info(f"{'Forcing refresh for' if force_refresh else 'Fetching'} live challenges from API...")
        all_raw_challenges = []
        try:
            # Fetch all challenges (assuming pagination handled by the client method)
            fetched_challenges = await self.api.get_all_challenges_paginated()
            if not isinstance(fetched_challenges, list):
                log.error(f"Challenge API did not return a list. Received: {type(fetched_challenges)}")
                self._challenges = None  # Clear potentially stale data
                return None

            all_raw_challenges.extend(fetched_challenges)
            log.info(f"Fetched {len(all_raw_challenges)} raw challenges.")

            # --- >>> SAVE RAW DATA <<< ---
            raw_save_path = self._get_cache_path(live_filename, processed=False)
            log.debug(f"Saving raw challenges data to {raw_save_path}...")
            save_json(all_raw_challenges, live_filename, folder=self.raw_cache_dir)
            log.debug("Raw challenges data saved.")
            # --- >>> END SAVE RAW DATA <<< ---

            # Validate into ChallengeList model, passing context for ownership check etc.
            self._challenges = ChallengeList.from_raw_data(all_raw_challenges, context=validation_context)
            self._update_refresh_time(data_key)

            # Save the *initially* processed ChallengeList (without linked tasks yet)
            if self._challenges:
                log.debug(f"Saving initially processed challenges list to {live_processed_path}...")
                # Use save_pydantic_model which should handle the ChallengeList structure
                save_pydantic_model(self._challenges, live_filename, folder=self.processed_cache_dir)
                log.debug("Initially processed challenges saved.")
            else:
                log.warning("ChallengeList validation resulted in None or empty list, processed file not saved.")

            log.success(f"Live challenges fetched & processed ({len(self._challenges or [])} challenges).")
            return self._challenges

        except Exception as e:
            log.exception("Failed during challenge fetch, processing, or saving.")
            self._challenges = None  # Clear on error
            return None

    # --- Orchestration Methods ---

    async def load_all_data(self, force_refresh: bool = False) -> bool:
        """Loads all relevant data concurrently: User, Tasks, Tags, Party, and Static Content.
        Uses caching unless `force_refresh` is True for live data. Static content
        cache policy is managed by StaticContentManager (refreshed if needed).

        Args:
            force_refresh: If True, forces refresh for User, Tasks, Tags, Party.
                           StaticContentManager decides independently unless forced there too.
        """
        log.info(f"Initiating load_all_data (force_refresh={force_refresh})...")
        static_content_task: Coroutine = self.static_content_manager.load_content()

        # Define live data tasks *after* ensuring static is scheduled
        live_data_tasks: list[Coroutine] = [
            self.load_user(force_refresh=force_refresh),
            self.load_tasks(force_refresh=force_refresh),
            self.load_tags(force_refresh=force_refresh),
            self.load_party(force_refresh=force_refresh),
            self.load_challenges(force_refresh=force_refresh),
        ]

        all_tasks: list[Coroutine] = [static_content_task] + live_data_tasks

        # Run all loading tasks concurrently
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Log any errors encountered during loading
        success = True
        task_map = ["StaticContent", "User", "Tasks", "Tags", "Party", "Challenges"]  # Match new order
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Identify which task failed based on order (requires tasks list order to be consistent)
                failed_task_name = task_map[i] if i < len(task_map) else f"UnknownTask_{i}"
                log.error(f"Error loading {failed_task_name}: {result}")
                success = False

        # Models (_user, _tasks, etc.) are populated by the load methods.
        # Static content is loaded within static_content_manager.
        log.info("load_all_data finished.")
        return success

    async def process_loaded_data(self) -> bool:
        """Orchestrates post-loading processing of models. Requires data to be loaded first.

        Processes:
        1. User effective stats.
        2. Challenge joined/owned status.
        3. Task statuses, tag names, and Daily damage.
        4. Links Tasks to Challenges. <<< Added explicit save after this
        5. Party static quest details.

        Returns:
            True if processing was successful, False otherwise.
        """
        log.info("Initiating process_loaded_data...")
        # Add Challenges to required check
        required = {"User": self._user, "Tasks": self._tasks, "Tags": self._tags, "Challenges": self._challenges}
        missing = [k for k, v in required.items() if v is None]
        static_loaded = self.static_content_manager._content is not None

        # Handle optional Party dependency more gracefully
        optional = {"Party": self._party}

        if missing or not static_loaded:
            log.error(f"Cannot process - Missing Required: {', '.join(missing)}{', Static Content' if not static_loaded else ''}")
            return False

        log.debug(
            f"Data available for processing: User={self._user is not None}, Tasks={self._tasks is not None}, Tags={self._tags is not None}, Challenges={self._challenges is not None}, Party={self._party is not None}, Static={static_loaded}"
        )

        success = True
        try:
            # --- Processing Steps ---

            # 1. Process User Stats (Needs Static Gear)
            if self._user:
                gear_data = self.static_gear_data or {}
                self._user.calculate_effective_stats(gear_data=gear_data)
                log.debug("User stats processed.")

            # 2. Process Challenges Status (Needs User - already checked above)
            # Note: Ownership is now handled during validation via context.
            # We only need to explicitly set `joined` here.
            if self._user and self._challenges:
                # Ensure profile.challenges exists and is a list
                user_challenges_list = getattr(self._user, "challenges", [])
                joined_ids = set(user_challenges_list if isinstance(user_challenges_list, list) else [])
                # joined_ids = set(self._user.profile.challenges) if self._user.profile else set()
                count_joined = 0
                for c in self._challenges.challenges:
                    is_joined = c.id in joined_ids
                    if c.joined != is_joined:  # Only log if changed
                        pass
                        # log.debug(f"Challenge '{c.id[:8]}' joined status -> {is_joined}")
                    c.joined = is_joined
                    if is_joined:
                        count_joined += 1
                # log.debug(f"Challenge joined status processed ({count_joined} marked as joined).")

            # 3. Process Tasks (Needs User, Tags, Static Content Manager)
            if self._tasks and self._user and self._tags:
                self._tasks.process_tasks(user=self._user, tags_provider=self._tags, content_manager=self.static_content_manager)
                log.debug("Tasks processed.")
            else:
                log.error("Skipping task processing: User, Tasks or Tags missing.")  # Should fail dep check

            # 4. Link Tasks to LIVE Challenges (Needs Challenges, Tasks)
            linked_count = 0
            if self._challenges and self._tasks:
                log.debug(f"Linking {len(self._tasks)} tasks to {len(self._challenges)} challenges...")
                linked_count = self._challenges.link_tasks(self._tasks)
                log.debug(f"Tasks linked to challenges ({linked_count} links made).")

                # --- >>> SAVE CHALLENGES AGAIN (WITH LINKED TASKS) <<< ---
                log.info("Saving fully processed challenges state (with linked tasks)...")
                try:
                    chal_filename = "challenges.json"
                    processed_chal_path = self._get_cache_path(chal_filename, processed=True)
                    # Overwrite the previously saved processed file
                    challenges_to_save = self._challenges.model_dump(
                        mode="json",  # Use 'json' mode for JSON-compatible types
                        exclude={
                            # Exclude from items within the 'challenges' list:
                            "challenges": {
                                "__all__": {  # Apply to all Challenge items in the list
                                    # Exclude from items within the 'tasks' list of each Challenge:
                                    "tasks": {"__all__": {"styled_text", "styled_notes"}}  # Adjust these field names based on your Task model
                                }
                            }
                        },
                    )
                    save_successful = save_json(challenges_to_save, chal_filename, folder=self.processed_cache_dir)
                    log.success(f"Saved processed challenges state to {processed_chal_path}")
                except Exception as e:
                    log.error(f"Failed saving processed challenges state: {e}")
                    # Don't mark overall processing as failed just for this save failure
                # --- >>> END SAVE CHALLENGES AGAIN <<< ---
            else:
                log.warning("Skipping task linking to challenges due to missing Challenges or Tasks.")

            # 5. Process Party (Needs Party, Static Content Manager)
            if self._party and self._party.quest and self._party.quest.key:
                if not self._party.static_quest_details:
                    log.debug("Fetching Party quest details...")
                    # This modifies the self._party object in place
                    await self._party.fetch_and_set_static_quest_details(self.static_content_manager)
                    log.debug("Party quest details processed.")
            elif self._party:
                log.debug("Party exists but no active quest to process.")
            # No else needed if self._party is None

        except Exception as e:
            log.exception("Error during main processing steps of process_loaded_data.")
            success = False

        # --- Optionally save processed TASKS again AFTER processing ---
        if success and self._tasks:
            log.info("Saving fully processed tasks state post-processing...")
            try:
                tasks_filename = "tasks.json"
                processed_tasks_path = self._get_cache_path(tasks_filename, processed=True)
                # TaskList has its own save method
                self._tasks.save_to_json(tasks_filename, folder=self.processed_cache_dir)
                log.success(f"Saved processed tasks state to {processed_tasks_path}")
            except Exception as e:
                log.error(f"Failed saving processed tasks state: {e}")

        log.info(f"process_loaded_data finished {'successfully' if success else 'with errors'}.")
        return success

    # Helper for sync gear access during processing
    def _get_static_gear_data_sync(self) -> dict[str, Gear]:
        content = self.static_content_manager._content
        if content and content.gear:
            return content.gear
        log.warning("Static gear data accessed sync but not pre-loaded.")
        return {}

    # No close method needed as no DB connection managed here


# ──────────────────────────────────────────────────────────────────────────────
