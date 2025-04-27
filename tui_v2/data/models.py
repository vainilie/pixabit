# pixabit/services/data_manager.py

# ─── Title ────────────────────────────────────────────────────────────────────
#          Habitica Data Orchestration Manager
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Provides a centralized DataManager class for loading, caching, processing,
and accessing Habitica data models. Includes persistent SQLite archiving
for challenges.
"""

# SECTION: IMPORTS
from __future__ import annotations

import asyncio
import json
import sqlite3  # <<< Import SQLite
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Coroutine, Dict, Type  # Use standard types

# Project Imports (Ensure these are correct)
try:
    from pixabit.api.client import HabiticaClient
    from pixabit.config import DEFAULT_CACHE_DURATION_DAYS, HABITICA_DATA_PATH, USER_ID
    from pixabit.helpers._json import load_json, load_pydantic_model, save_json, save_pydantic_model
    from pixabit.helpers._logger import log
    from pixabit.helpers.DateTimeHandler import DateTimeHandler
    from pixabit.models.challenge import Challenge, ChallengeGroup, ChallengeLeader, ChallengeList  # Include submodels used by Challenge

    # Import all necessary models
    from pixabit.models.game_content import Gear, Quest, StaticContentManager
    from pixabit.models.party import Party
    from pixabit.models.tag import TagList
    from pixabit.models.task import AnyTask, Task, TaskList  # Import AnyTask for archive typing
    from pixabit.models.user import User
    from pydantic import ValidationError  # Import for exception handling

except ImportError as e:
    # ... (Fallback imports - critical failure is likely) ...
    import logging

    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    log.critical(f"DataManager failed to import critical dependencies: {e}. Check structure.")
    raise ImportError(f"DataManager could not load required modules: {e}") from e

# SECTION: CONSTANTS & CONFIG

# ... (Existing cache timeouts) ...
DEFAULT_CHALLENGE_CACHE_TIMEOUT = timedelta(hours=2)
CHALLENGE_ARCHIVE_FILENAME = "challenges_archive.db"  # <<< SQLite DB file


# SECTION: DATA MANAGER CLASS


# KLASS: DataManager
class DataManager:
    """Centralized manager using SQLite for persistent challenge archiving."""

    def __init__(
        self,
        api_client: HabiticaClient,
        static_content_manager: StaticContentManager,
        cache_dir: Path = HABITICA_DATA_PATH,
        live_cache_timeout: timedelta = DEFAULT_LIVE_CACHE_TIMEOUT,
        challenge_cache_timeout: timedelta = DEFAULT_CHALLENGE_CACHE_TIMEOUT,
    ):
        # ... (Assignment of api_client, static_content_manager, cache_dir, timeouts) ...
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

        # In-memory representation of the ARCHIVE, loaded from DB
        self._challenge_archive: Dict[str, Challenge] = {}
        self.challenge_archive_db_path = self.processed_cache_dir / CHALLENGE_ARCHIVE_FILENAME

        self._last_refresh_times: dict[str, datetime | None] = {
            "user": None,
            "tasks": None,
            "tags": None,
            "party": None,
            "challenges": None,  # Live challenge list refresh time
            "challenge_archive": None,  # Track when archive was last loaded/saved from DB
        }

        log.info(f"DataManager initialized. Cache Dir: {self.cache_dir}. Archive DB: {self.challenge_archive_db_path}")

        # --- Initialize Archive DB and Load ---
        self._db_conn = None  # Placeholder for connection
        self._ensure_archive_table_exists()
        self._load_challenge_archive()

    def _get_db_conn(self) -> sqlite3.Connection:
        """Gets a connection to the archive SQLite database."""
        # Simple connection management for now. Could use a pool for complex scenarios.
        if self._db_conn is None or not isinstance(self._db_conn, sqlite3.Connection):
            try:
                # Ensure parent directory exists
                self.challenge_archive_db_path.parent.mkdir(parents=True, exist_ok=True)
                self._db_conn = sqlite3.connect(self.challenge_archive_db_path, timeout=10)  # Add timeout
                self._db_conn.row_factory = sqlite3.Row  # Access columns by name
            except sqlite3.Error as e:
                log.exception(f"Failed to connect to archive database {self.challenge_archive_db_path}: {e}")
                raise  # Re-raise critical error
        return self._db_conn

    def _close_db_conn(self):
        """Closes the database connection if open."""
        if self._db_conn:
            try:
                self._db_conn.close()
            except sqlite3.Error as e:
                log.error(f"Error closing archive database connection: {e}")
            self._db_conn = None

    def _ensure_archive_table_exists(self) -> None:
        """Creates the challenges archive table if it doesn't exist."""
        try:
            conn = self._get_db_conn()
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS challenges_archive (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    short_name TEXT,
                    summary TEXT,
                    description TEXT,
                    leader_id TEXT,
                    leader_name TEXT,
                    group_id TEXT,
                    group_name TEXT,
                    group_type TEXT,
                    group_privacy TEXT,
                    prize INTEGER,
                    official INTEGER,
                    created_at TEXT,
                    broken TEXT,
                    tasks_json TEXT, -- Store task list definition as JSON
                    last_archived_at TEXT NOT NULL
                )
            """
            )
            # Add INDEX for faster lookups by id if table gets large
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_challenge_id ON challenges_archive(id)")
            conn.commit()
            log.debug("Challenge archive table ensured.")
        except sqlite3.Error as e:
            log.exception(f"Failed to create or ensure archive table exists: {e}")
            raise  # Cannot proceed without table
        # Removed finally: _close_db_conn() to keep connection potentially open

    def _load_challenge_archive(self) -> None:
        """Loads the challenge archive from the SQLite database."""
        log.debug(f"Loading challenge archive from {self.challenge_archive_db_path}...")
        loaded_archive: Dict[str, Challenge] = {}
        conn = None  # Ensure conn is defined
        try:
            conn = self._get_db_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM challenges_archive")
            rows = cursor.fetchall()  # Fetches all results as list of Row objects

            if not rows:
                log.info("Challenge archive database is empty.")
                self._challenge_archive = {}
                return

            for row in rows:
                challenge_id = row["id"]
                try:
                    challenge_data = dict(row)  # Convert Row to dict

                    # Deserialize tasks from JSON
                    tasks_list: list[AnyTask] = []
                    tasks_json_str = challenge_data.pop("tasks_json", None)  # Get and remove
                    if tasks_json_str:
                        try:
                            raw_task_list = json.loads(tasks_json_str)
                            # Re-create TaskList (doesn't need full validation maybe? Or use specific method)
                            # Need a way to parse list of dicts into list of Task objects directly
                            task_list_temp = TaskList.from_processed_dicts(raw_task_list)  # Assuming this method exists and works
                            tasks_list = task_list_temp.tasks
                        except json.JSONDecodeError:
                            log.warning(f"Invalid JSON in tasks_json for archive challenge {challenge_id}. Skipping tasks.")
                        except Exception as task_e:
                            log.error(f"Error parsing tasks from archive for challenge {challenge_id}: {task_e}")

                    # Deserialize nested group/leader? No, store directly
                    # Convert official back to bool
                    challenge_data["official"] = bool(challenge_data.get("official", 0))
                    # Convert timestamps back to datetime
                    # Using DateTimeHandler for consistency, although direct parsing works too
                    challenge_data["created_at"] = DateTimeHandler(challenge_data.get("created_at")).utc_datetime
                    # Need updated_at field? Archive doesn't store it yet.

                    # Create the Challenge object
                    challenge_instance = Challenge.model_validate(challenge_data)
                    challenge_instance.tasks = tasks_list  # Assign parsed tasks
                    loaded_archive[challenge_id] = challenge_instance

                except ValidationError as e:
                    log.warning(f"Skipping invalid challenge data in archive for ID {challenge_id}: {e}")
                except Exception as e:
                    log.exception(f"Unexpected error loading challenge {challenge_id} from archive DB row.")

            self._challenge_archive = loaded_archive
            mtime = datetime.fromtimestamp(self.challenge_archive_db_path.stat().st_mtime, timezone.utc) if self.challenge_archive_db_path.exists() else None
            self._last_refresh_times["challenge_archive"] = mtime
            log.info(f"Challenge archive loaded successfully from DB ({len(self._challenge_archive)} entries).")

        except sqlite3.Error as e:
            log.exception(f"Failed to load challenge archive from database: {e}")
            self._challenge_archive = {}  # Reset on error
        # Removed finally: _close_db_conn()

    def _save_challenge_archive(self) -> bool:
        """Saves the current in-memory challenge archive to the SQLite database."""
        if not self._challenge_archive:  # Avoid saving empty archive if it wasn't loaded properly
            log.debug("In-memory challenge archive is empty, skipping save to DB.")
            return False

        log.debug(f"Saving challenge archive ({len(self._challenge_archive)} entries) to DB {self.challenge_archive_db_path}...")
        conn = None
        success = False
        try:
            conn = self._get_db_conn()
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")  # Use transaction for performance

            now_iso = datetime.now(timezone.utc).isoformat()

            for challenge_id, challenge in self._challenge_archive.items():
                try:
                    # Serialize tasks list to JSON string
                    tasks_dump = [t.model_dump(mode="json", exclude={"styled_text", "styled_notes"}) for t in challenge.tasks]
                    tasks_json_str = json.dumps(tasks_dump)

                    # Extract data for DB columns
                    db_data = (
                        challenge.id,
                        challenge.name,
                        challenge.short_name,
                        challenge.summary,
                        challenge.description,
                        challenge.leader.id if challenge.leader else None,
                        challenge.leader.name if challenge.leader else None,
                        challenge.group.id if challenge.group else None,
                        challenge.group.name if challenge.group else None,
                        challenge.group.type if challenge.group else None,
                        challenge.group.privacy if challenge.group else None,
                        challenge.prize,
                        int(challenge.official),  # Store bool as int
                        challenge.created_at.isoformat() if challenge.created_at else None,
                        challenge.broken,
                        tasks_json_str,
                        now_iso,  # last_archived_at
                    )

                    cursor.execute(
                        """
                         INSERT OR REPLACE INTO challenges_archive (
                             id, name, short_name, summary, description,
                             leader_id, leader_name, group_id, group_name, group_type, group_privacy,
                             prize, official, created_at, broken, tasks_json, last_archived_at
                         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                     """,
                        db_data,
                    )

                except Exception as item_e:
                    log.error(f"Failed to prepare or save challenge {challenge_id} to archive DB: {item_e}")
                    # Continue with other items

            conn.commit()  # Commit transaction
            success = True
            self._last_refresh_times["challenge_archive"] = datetime.now(timezone.utc)
            log.info("Challenge archive saved successfully to DB.")

        except sqlite3.Error as e:
            log.exception(f"Failed to save challenge archive to database: {e}")
            if conn:
                try:
                    conn.rollback()  # Rollback on error
                except sqlite3.Error:
                    log.error("DB rollback failed.")
            success = False
        finally:
            self._close_db_conn()  # Ensure connection is closed after operation

        return success

    # --- Archive Access ---
    def get_archived_challenge(self, challenge_id: str) -> Challenge | None:
        """Retrieves a challenge from the persistent archive by its ID."""
        # Assumes archive is loaded in memory
        return self._challenge_archive.get(challenge_id)

    # --- Modified load_challenges() ---
    async def load_challenges(self, force_refresh: bool = False) -> ChallengeList | None:
        """Loads LIVE user challenges list, updates archive, handling pagination and caching."""
        data_key = "challenges"
        live_filename = "challenges.json"
        model_class = ChallengeList

        # Note: Archive loading is now done in __init__

        # Check live cache
        live_processed_path = self._get_cache_path(live_filename, processed=True)
        if not force_refresh and self._challenges and not self._is_live_cache_stale(data_key):
            log.debug("Using in-memory challenges data.")
            # Merge this potentially newer in-memory list into the archive
            # (Can be skipped if loading from file below handles merging)
            # self._challenge_archive.update({chal.id: chal for chal in self._challenges.challenges})
            # self._save_challenge_archive() # Optional save here
            return self._challenges

        if not force_refresh and live_processed_path.exists():
            mtime = datetime.fromtimestamp(live_processed_path.stat().st_mtime, timezone.utc)
            if (datetime.now(timezone.utc) - mtime) <= self.challenge_cache_timeout:
                cached_model = load_pydantic_model(model_class, live_processed_path)
                if cached_model:
                    self._challenges = cached_model
                    self._update_refresh_time(data_key)
                    # Merge loaded LIVE cache into archive
                    log.debug("Merging loaded LIVE challenge cache into archive...")
                    updated = False
                    for chal in self._challenges.challenges:
                        # Overwrite/add entry in the archive
                        if self._challenge_archive.get(chal.id) != chal:  # Prevent unnecessary writes if same
                            self._challenge_archive[chal.id] = chal
                            updated = True
                    if updated:
                        self._save_challenge_archive()  # Save archive only if changed
                    log.info(f"Challenges loaded from fresh processed cache ({len(self._challenges)} challenges).")
                    return self._challenges

        # --- Fetch from API ---
        # (Fetching loop remains the same, collecting into all_raw_challenges)
        # ...
        log.info(f"{'Forcing refresh for' if force_refresh else 'Fetching'} challenges data from API...")
        all_raw_challenges = []
        page = 0
        try:
            while True:  # Loop for pagination
                log.debug(f"Fetching challenge page {page}...")
                raw_page_data = []
                if hasattr(self.api, "get_user_challenges"):
                    raw_page_data = await self.api.get_user_challenges(page=page)
                else:  # Fallback if method name is different
                    raw_page_data = await self.api.get_data("/challenges/user", params={"page": page})

                if isinstance(raw_page_data, list) and raw_page_data:
                    all_raw_challenges.extend(raw_page_data)
                    page += 1
                elif isinstance(raw_page_data, list) and not raw_page_data:
                    break  # End of pages
                else:
                    log.error(f"Received unexpected data type from challenges API page {page}: {type(raw_page_data)}. Stopping pagination.")
                    break

            log.info(f"Fetched {len(all_raw_challenges)} raw challenges across {page} pages.")
            # ... (end fetch loop) ...
            self._challenges = ChallengeList.from_raw_data(all_raw_challenges)  # Validate LIVE list
            self._update_refresh_time(data_key)

            # MERGE into Archive & SAVE Archive
            if self._challenges:
                log.debug(f"Merging {len(self._challenges)} fetched challenges into archive...")
                updated_archive = False
                for chal in self._challenges.challenges:
                    if self._challenge_archive.get(chal.id) != chal:
                        self._challenge_archive[chal.id] = chal
                        updated_archive = True
                if updated_archive:
                    self._save_challenge_archive()  # Save the updated archive
                else:
                    log.debug("No changes detected between fetched challenges and archive.")

                # Save the LIVE cache file
                save_pydantic_model(self._challenges, live_filename, folder=self.processed_cache_dir)

            log.success("Challenges data fetched, processed, cached, and archive updated.")
            return self._challenges

        except Exception as e:  # Catch fetch/process errors
            log.exception("Failed to fetch or process challenges data from API.")
            self._challenges = None
            # Should we return stale live cache if available?
            # Should we clear in-memory archive on total failure? No, keep it maybe.
            return None

    # --- load_all_data (Needs slight adjustment for task order) ---
    async def load_all_data(self, force_refresh: bool = False) -> None:
        # ... (logging)
        # Load static first as it has its own robust caching
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

        results = await asyncio.gather(*all_tasks, return_exceptions=True)
        # ... (error logging remains same, adjust task_map order) ...
        task_map = ["StaticContent", "User", "Tasks", "Tags", "Party", "Challenges"]  # Match new order
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_task_name = task_map[i] if i < len(task_map) else f"UnknownTask_{i}"
                log.error(f"Error loading {failed_task_name}: {result}")
        log.info("load_all_data finished.")

    # --- process_loaded_data (No change needed, already uses self._challenges) ---
    async def process_loaded_data(self) -> bool:
        # ... (remains the same, links against the LIVE self._challenges)
        pass

    # --- Add cleanup method ---
    def close(self):
        """Closes database connections and performs cleanup."""
        log.info("Closing DataManager resources...")
        self._close_db_conn()
        # Add other cleanup if needed
        log.info("DataManager closed.")


# ... (Rest of file, main example would need changes to reflect archive) ...
