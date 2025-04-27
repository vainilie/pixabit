# pixabit/services/archiver.py

# ─── Title ────────────────────────────────────────────────────────────────────
#            Persistent Data Archiver (SQLite Backend)
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""
Provides the Archiver class for long-term persistent storage of Habitica data
(e.g., Challenges, completed Todos) using an SQLite database. Separates archival
logic from the main live data management.
"""

# SECTION: IMPORTS
from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional

# Project Imports (Ensure these resolve)
try:
    # Import necessary MODELS that will be archived/retrieved
    from pixabit.models.challenge import Challenge
    from pixabit.models.task import Task, AnyTask, TaskList # For deserializing tasks/todos
    # Import Pydantic specifically for Validation Error if validating on load
    from pydantic import ValidationError
    from pixabit.helpers._logger import log
    from pixabit.helpers.DateTimeHandler import DateTimeHandler # For parsing dates from DB
    # Add other models here if they will be archived (e.g., Todo)
except ImportError as e:
     import logging
     log = logging.getLogger(__name__); log.addHandler(logging.NullHandler())
     log.critical(f"Archiver failed imports: {e}. Check structure."); raise

# SECTION: CONSTANTS & CONFIG

ARCHIVE_DB_FILENAME = "persistent_archive.db" # Default filename

# SECTION: ARCHIVER CLASS

# KLASS: Archiver
class Archiver:
    """
    Handles persistent storage and retrieval of Habitica data using SQLite.
    Manages challenges, and potentially completed tasks like Todos.
    """
    def __init__(self, db_path: Path):
        """
        Initializes the Archiver and connects to the database.

        Args:
            db_path: The full path to the SQLite database file.
        """
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        log.info(f"Initializing Archiver with DB: {self.db_path}")
        try:
            self._ensure_tables_exist() # Creates DB and tables if needed
        except Exception as e:
            log.critical(f"CRITICAL: Failed to initialize Archiver DB at {db_path}: {e}", exc_info=True)
            # Application might need to handle this critical failure

    def _get_conn(self) -> sqlite3.Connection | None:
        """Gets or establishes a connection to the archive SQLite database."""
        # Basic connection management (re-establish if closed)
        try:
             # Check if connection exists and is usable
            if self._conn:
                 # Quick check if connection is still active (may not be fully reliable)
                 try:
                    self._conn.execute("SELECT 1")
                    return self._conn
                 except sqlite3.Error:
                     self._close_db_conn() # Close broken connection

            # Establish new connection
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, timeout=10)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._conn.execute("PRAGMA journal_mode=WAL;")
            log.debug(f"Established connection to DB: {self.db_path}")
            return self._conn
        except sqlite3.Error as e:
            log.error(f"Failed to connect to archive DB {self.db_path}: {e}")
            self._conn = None # Ensure conn is None on failure
            return None

    def _close_db_conn(self):
        """Closes the database connection if open."""
        if self._conn:
            log.debug(f"Closing Archiver DB connection to {self.db_path}")
            try:
                self._conn.close()
            except sqlite3.Error as e:
                log.error(f"Error closing archiver DB: {e}")
            self._conn = None

    def _ensure_tables_exist(self):
        """Creates database tables if they don't already exist."""
        conn = self._get_conn()
        if not conn: return # Cannot proceed

        try:
            cursor = conn.cursor()
            log.debug("Ensuring Archiver tables exist...")

            # --- Challenges Table ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS challenges_archive (
                    id TEXT PRIMARY KEY,
                    name TEXT, short_name TEXT, summary TEXT, description TEXT,
                    leader_id TEXT, leader_name TEXT,
                    group_id TEXT, group_name TEXT, group_type TEXT, group_privacy TEXT,
                    prize INTEGER, official INTEGER, created_at TEXT, broken TEXT,
                    tasks_json TEXT, last_archived_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_challenges_archive_id ON challenges_archive(id)")

            # --- Add other tables as needed (e.g., Todos) ---
            # cursor.execute(""" CREATE TABLE IF NOT EXISTS todos_archive (...) """)
            # cursor.execute("CREATE INDEX IF NOT EXISTS ...")

            conn.commit()
            log.debug("Archiver tables ensured.")
        except sqlite3.Error as e:
            log.exception(f"Archiver failed to ensure tables: {e}")
            raise # Critical error
        # Keep connection open briefly? Or close? Close for simplicity unless bulk ops common.
        # self._close_db_conn()

    def _deserialize_challenge(self, row: sqlite3.Row) -> Challenge | None:
         """Helper to convert a DB row into a Challenge object."""
         if not row: return None
         try:
             challenge_data = dict(row)
             challenge_id = challenge_data.get("id")

             # Deserialize tasks from JSON
             tasks_list: list[AnyTask] = []
             tasks_json_str = challenge_data.pop("tasks_json", None)
             if tasks_json_str:
                  try:
                       raw_task_list = json.loads(tasks_json_str)
                       if isinstance(raw_task_list, list):
                            # Assuming TaskList class and from_processed_dicts are available
                            tasks_list = TaskList.from_processed_dicts(raw_task_list).tasks
                  except json.JSONDecodeError: log.warning(f"Invalid tasks JSON in archive for {challenge_id}")
                  except Exception as e: log.error(f"Error parsing tasks for {challenge_id} from archive: {e}")

             # Reconstruct nested models (if stored flat) and convert types
             challenge_data["official"] = bool(challenge_data.get("official", 0))
             challenge_data["created_at"] = DateTimeHandler(challenge_data.get("created_at")).utc_datetime
             # Rebuild leader dict if stored flat
             leader_data = None
             lid = challenge_data.pop('leader_id', None)
             if lid: leader_data = {'id': lid, 'name': challenge_data.pop('leader_name', None)}
             challenge_data['leader'] = leader_data
             # Rebuild group dict
             group_data = None
             gid = challenge_data.pop('group_id', None)
             if gid: group_data = {'id': gid, 'name': challenge_data.pop('group_name', None),
                                     'type': challenge_data.pop('group_type', None),
                                     'privacy': challenge_data.pop('group_privacy', None)}
             challenge_data['group'] = group_data

             # Validate dictionary against Challenge model
             challenge_instance = Challenge.model_validate(challenge_data)
             challenge_instance.tasks = tasks_list # Assign deserialized tasks
             return challenge_instance
         except ValidationError as e:
             log.warning(f"Skipping invalid archived challenge {challenge_id}: {e}")
             return None
         except Exception as e:
             log.exception(f"Error deserializing archived challenge {challenge_id} from DB")
             return None


    def archive_challenges(self, challenges: list[Challenge]) -> int:
        """Adds or replaces multiple challenges in the archive database. Returns count archived."""
        if not challenges: return 0
        conn = self._get_conn();
        if not conn: log.error("Cannot archive challenges, DB connection failed."); return 0
        log.info(f"Archiving {len(challenges)} challenges to DB...")
        success_count = 0
        try:
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")
            now_iso = datetime.now(timezone.utc).isoformat()

            for challenge in challenges:
                if not isinstance(challenge, Challenge) or not challenge.id: continue
                try:
                    tasks_dump = [t.model_dump(mode='json', exclude={'styled_text','styled_notes'}) for t in challenge.tasks]
                    tasks_json_str = json.dumps(tasks_dump) if tasks_dump else None # Store null if no tasks

                    db_data = (
                        challenge.id, challenge.name, challenge.short_name, challenge.summary, challenge.description,
                        challenge.leader.id if challenge.leader else None, challenge.leader.name if challenge.leader else None,
                        challenge.group.id if challenge.group else None, challenge.group.name if challenge.group else None,
                        challenge.group.type if challenge.group else None, challenge.group.privacy if challenge.group else None,
                        challenge.prize, int(challenge.official),
                        challenge.created_at.isoformat() if challenge.created_at else None,
                        challenge.broken, tasks_json_str, now_iso
                    )
                    cursor.execute("""
                        INSERT OR REPLACE INTO challenges_archive VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, db_data)
                    success_count += 1
                except Exception as item_e:
                     log.error(f"Failed preparing/saving chal {challenge.id} to archive DB: {item_e}")

            conn.commit()
            log.info(f"Archived {success_count}/{len(challenges)} challenges.")

        except sqlite3.Error as e:
            log.exception(f"Failed saving challenges archive batch: {e}")
            if conn: try: conn.rollback() except: pass
            success_count = 0 # Indicate failure
        finally:
             self._close_db_conn() # Close after operation

        return success_count

    def get_archived_challenge(self, challenge_id: str) -> Challenge | None:
        """Retrieves a single challenge from the archive DB."""
        conn = self._get_conn();
        if not conn: return None
        challenge_instance = None
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM challenges_archive WHERE id = ?", (challenge_id,))
            row = cursor.fetchone()
            if row:
                 challenge_instance = self._deserialize_challenge(row)
                 log.debug(f"Retrieved challenge '{challenge_id}' from archive.")
            else:
                 log.debug(f"Challenge '{challenge_id}' not found in archive.")
        except sqlite3.Error as e:
            log.exception(f"Failed get archived challenge {challenge_id}: {e}")
        # finally: self._close_db_conn() # Keep open potentially? Close for now.
        return challenge_instance

    def load_all_challenges_from_archive(self) -> Dict[str, Challenge]:
         """Loads all challenges from the archive DB into a dictionary."""
         log.info("Loading all challenges from archive DB...")
         all_challenges = {}
         conn = self._get_conn()
         if not conn:
             return {}
         try:
              cursor = conn.cursor()
              cursor.execute("SELECT * FROM challenges_archive ORDER BY last_archived_at DESC")
              rows = cursor.fetchall()
              for row in rows:
                   challenge = self._deserialize_challenge(row)
                   if challenge and challenge.id:
                       all_challenges[challenge.id] = challenge
              log.info(f"Loaded {len(all_challenges)} challenges from archive DB.")
         except sqlite3.Error as e:
              log.exception("Failed to load all challenges from archive DB.")
         finally:
              self._close_db_conn() # Close after potentially large load
         return all_challenges


    # --- Add methods for archiving/retrieving other items (e.g., Todos) ---
    # def archive_todo(self, todo: Todo) -> bool: ...
    # def get_archived_todos(self, ...) -> List[Todo]: ...

    def close(self):
        """Closes database connections and performs cleanup."""
        log.info("Closing DataManager resources...")
        self._close_db_conn()
        # Add other cleanup if needed
        log.info("DataManager closed.")


# ──────────────────────────────────────────────────────────────────────────────
