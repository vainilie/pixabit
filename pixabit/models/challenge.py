# pixabit/models/challenge.py

# ─── Title ────────────────────────────────────────────────────────────────────
#            Habitica Challenge Models
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for representing Habitica Challenges, their associated
metadata (leader, group), and provides a container (`ChallengeList`) for managing
collections of challenges and linking them to tasks. Includes support for
group privacy and legacy status calculation.
"""

# SECTION: IMPORTS
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Literal

# External Libs
import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)

from pixabit.config import USER_ID

# Local Imports (Ensure these resolve correctly)
try:
    from pixabit.api.client import HabiticaClient
    from pixabit.config import HABITICA_DATA_PATH
    from pixabit.helpers._json import save_json, save_pydantic_model
    from pixabit.helpers._logger import log
    from pixabit.helpers.DateTimeHandler import DateTimeHandler

    from .task import AnyTask, Task, TaskList
    from .user import User
except ImportError:
    # --- Fallbacks ---
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    log.warning("Using placeholder dependencies.")

    class Task(BaseModel):
        id: str | None = None
        challenge: dict | None = None
        type: str = "unknown"
        text: str = ""

    AnyTask = Task

    class TaskList:
        def __init__(self, t=None):
            self.t = t or []

        def __iter__(self):
            return iter(self.t)

        def __len__(self):
            return len(self.t)

        @classmethod
        def from_raw_api_list(cls, l):
            return cls(l)

    class DateTimeHandler:
        __init__ = lambda s, t: None
        utc_datetime = None

    class HabiticaClient:
        async def get_challenges(self):
            return []

        async def get_tasks(self):
            return []

        async def get_user_data(self):
            return {"_id": "mock_user", "profile": {"challenges": []}}

    HABITICA_DATA_PATH = Path("./pixabit_cache")

    class User(BaseModel):
        id: str = "mock_user"
        profile: dict = {"challenges": []}
        auth: dict = {}

        @classmethod
        def model_validate(cls, data):
            return cls(**data)

    def save_json(d, f, **k):
        pass

    # --- End Fallbacks ---


# SECTION: PYDANTIC SUB-MODELS


# KLASS: ChallengeLeader
class ChallengeLeader(BaseModel):
    """Represents the leader info potentially nested within challenge data."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    id: str = Field(..., alias="_id", description="Leader's user ID.")
    name: str | None = Field(None, description="Leader's display name (parsed).")

    @model_validator(mode="before")
    @classmethod
    def extract_profile_name(cls, data: Any) -> dict[str, Any]:
        if isinstance(data, dict):
            if "name" not in data and "profile" in data and isinstance(data["profile"], dict):
                data["name"] = data["profile"].get("name")
            if "_id" in data and "id" not in data:
                data["id"] = data["_id"]
        return data if isinstance(data, dict) else {}

    @field_validator("name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> str | None:
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value).strip()
        return None


# KLASS: ChallengeGroup
class ChallengeGroup(BaseModel):
    """Represents the group info nested within challenge data."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    id: str = Field(..., alias="_id", description="Group ID.")
    name: str = Field("Unnamed Group", description="Group name (parsed).")
    type: Literal["party", "guild", "tavern"] | str | None = Field(None, description="Group type.")
    privacy: Literal["private", "public"] | str = Field("public", description="Group privacy setting.")  # Default to public

    @field_validator("name", mode="before")
    @classmethod
    def parse_name_emoji(cls, value: Any) -> str:
        default = "Unnamed Group"
        if isinstance(value, str):
            parsed = emoji_data_python.replace_colons(value).strip()
            return parsed if parsed else default
        return default

    @model_validator(mode="before")
    @classmethod
    def map_id(cls, data: Any) -> dict[str, Any]:
        if isinstance(data, dict):
            if "_id" in data and "id" not in data:
                data["id"] = data["_id"]
        return data if isinstance(data, dict) else {}

    @field_validator("privacy", mode="before")
    @classmethod
    def normalize_privacy(cls, value: Any) -> str:
        if isinstance(value, str):
            lower_val = value.lower()
            if lower_val in ["private", "public"]:
                return lower_val
            log.warning(f"Unknown privacy value '{value}'.")
            return value
        return "public"


# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MAIN CHALLENGE MODEL


# KLASS: Challenge
class Challenge(BaseModel):
    """Represents a single Habitica Challenge entity."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, validate_assignment=False)

    # --- Core Identification & Text ---
    id: str = Field(..., description="Unique challenge ID (mapped from _id if necessary).")
    name: str = Field("Unnamed Challenge", description="Challenge name (parsed emoji).")
    short_name: str | None = Field(None, alias="shortName", description="Short name/slug (parsed emoji).")
    summary: str = Field("", description="Summary text (parsed emoji).")  # Default to empty string
    description: str = Field("", description="Full description (parsed emoji).")  # Default to empty string

    # --- Relationships ---
    # Nested models, validated internally
    leader: ChallengeLeader | None = Field(None, description="Challenge leader details.")
    group: ChallengeGroup | None = Field(None, description="Associated group details (party/guild).")

    # --- Metadata & Status ---
    prize: int = Field(0, description="Gem prize for the winner (if any).")
    member_count: int = Field(0, alias="memberCount", description="Number of participants.")
    official: bool = Field(False, description="Is this an official Habitica challenge?")
    created_at: datetime | None = Field(None, alias="createdAt", description="Timestamp created (UTC).")
    updated_at: datetime | None = Field(None, alias="updatedAt", description="Timestamp updated (UTC).")
    # 'broken' indicates a problem (e.g., 'CHALLENGE_DELETED')
    broken: str | None = Field(None, description="Status if broken, e.g., 'CHALLENGE_DELETED'.")
    # Status flag derived from 'broken' field
    is_broken: bool = Field(False, description="True if the 'broken' field has a value.")

    # --- TUI Context Specific ---
    # Populated externally based on context (e.g., user's participation)
    owned: bool | None = Field(None, description="Is challenge owned by the fetching user? (Set externally)", exclude=False)
    joined: bool | None = Field(None, description="Has the fetching user joined this challenge? (Set externally)", exclude=False)

    # --- Linked Data ---
    # Populated externally by ChallengeList.link_tasks()
    tasks: list[Task] = Field(default_factory=list, description="Tasks belonging to this challenge.", exclude=False)

    @computed_field(description="True if not the Tavern challenge.")
    @property
    def is_legacy(self) -> bool:
        if self.group and isinstance(self.group.name, str) and self.group.name == "Tavern":
            return False
        return True

    @model_validator(mode="before")
    @classmethod
    def check_and_assign_id(cls, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        values = data.copy()
        values["is_broken"] = bool(values.get("broken"))
        if "_id" in values and "id" not in values:
            values["id"] = values["_id"]
        return values

    @model_validator(mode="after")
    def check_ownership(self, info: ValidationInfo) -> Challenge:
        """Sets the 'owned' flag based on comparing the leader ID to the
        current user ID provided in the validation context.
        Runs after initial fields and nested models are validated.
        """
        current_user_id: str | None = None
        # Get context if available
        if info.context and isinstance(info.context, dict):
            current_user_id = info.context.get("current_user_id")

        # Fallback to global config if context missing
        if current_user_id is None:
            current_user_id = USER_ID  # Assumes USER_ID is imported from config
            if not current_user_id or current_user_id == "fallback_user_id_from_config":  # Check usability
                current_user_id = None

        # Determine ownership
        if current_user_id and self.leader and self.leader.id == current_user_id:
            self.owned = True
            log.debug(f"Challenge {self.id} marked as owned by leader match.")
        else:
            # Set explicitly to False if context was available but didn't match,
            # otherwise keep None if context was missing.
            self.owned = False if current_user_id else None
            if not self.leader:
                log.debug(f"Challenge {self.id} has no leader, cannot determine ownership by leader.")
            elif not current_user_id:
                log.debug(f"Cannot determine ownership for Challenge {self.id}, missing user context.")

        # Need to return self for 'after' validator
        return self

    @field_validator("id", mode="after")
    @classmethod
    def check_id(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Challenge ID is required.")
        return v

    @field_validator("name", "short_name", "summary", "description", mode="before")
    @classmethod
    def parse_text_fields(cls, value: Any, info: ValidationInfo) -> str | None:
        # (Implementation remains the same - simplified for brevity here)
        default = "Unnamed Challenge" if info.field_name == "name" else ("" if info.field_name in ["summary", "description"] else None)
        if isinstance(value, str):
            p = emoji_data_python.replace_colons(value).strip()
            return p if (p or info.field_name != "name") else default
        return default

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetimes_utc(cls, value: Any) -> datetime | None:
        if value is None:
            return None
        h = DateTimeHandler(timestamp=value)
        return h.utc_datetime

    @field_validator("prize", "member_count", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        if value is None:
            return 0
        try:
            return int(float(value))
        except:
            return 0

    def add_task(self, task: AnyTask) -> None:
        if isinstance(task, Task) and task not in self.tasks:
            self.tasks.append(task)

    def add_tasks(self, tasks_to_add: list[AnyTask]) -> None:
        if isinstance(tasks_to_add, list):
            [self.add_task(task) for task in tasks_to_add]

    # --- Corrected Literal string types ---
    def get_tasks_by_type(self, task_type: Literal["habit", "daily", "todo", "reward"]) -> list[AnyTask]:
        return [t for t in self.tasks if hasattr(t, "task_type") and t.task_type == task_type]

    def __repr__(self) -> str:
        # Simplified repr construction
        parts = []
        if self.is_broken:
            parts.append(f"BROKEN({self.broken or ''})")
        if not self.is_legacy:
            parts.append("TAVERN")
        if self.joined:
            parts.append("Joined")
        if self.official:
            parts.append("Official")
        flags_str = f" ({', '.join(parts)})" if parts else ""
        task_count = len(self.tasks)
        name_str = self.name or "Unnamed"
        name_preview = name_str[:25].replace("\n", " ") + ("..." if len(name_str) > 25 else "")
        id_str = self.id[:8] if self.id else "NoID"
        return f"Challenge(id='{id_str}', name='{name_preview}', tasks={task_count}{flags_str})"

    def __str__(self) -> str:
        return self.name or "Unnamed Challenge"


# SECTION: CHALLENGE LIST CONTAINER


# KLASS: ChallengeList
class ChallengeList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, arbitrary_types_allowed=False)
    challenges: list[Challenge] = Field(default_factory=list)

    @classmethod
    def from_raw_data(
        cls,
        raw_challenge_list: list[dict[str, Any]],
        # --- Add Context Parameter ---
        context: dict[str, Any] | None = None,
        # --- End Add ---
    ) -> ChallengeList:
        """Processes raw API data, validating into Challenge models, passing context."""
        if not isinstance(raw_challenge_list, list):
            return cls(challenges=[])
        validated_challenges: list[Challenge] = []
        count = 0
        for i, raw in enumerate(raw_challenge_list):
            if not isinstance(raw, dict):
                continue
            try:
                challenge_instance = Challenge.model_validate(raw, context=context)

                validated_challenges.append(challenge_instance)
                count += 1
            except Exception as e:
                log.error(f"Chal[{i}] validation fail ID:{raw.get('_id','N/A')} Name:{raw.get('name','N/A')}: {e}")
        log.debug(f"ChallengeList.from_raw_data validated {count} challenges.")
        return cls(challenges=validated_challenges)

    def link_tasks(self, task_list_obj: TaskList) -> int:
        if not isinstance(task_list_obj, TaskList) or not self.challenges:
            return 0
        log.info(f"Linking tasks (count={len(task_list_obj)}) to {len(self.challenges)} challenges...")
        lookup = {c.id: c for c in self.challenges}
        for challenge in self.challenges:
            challenge.tasks.clear()  # Clear first
        linked, skip_link, skip_found = 0, 0, 0
        for task in task_list_obj:  # Iterate through the tasks from TaskList
            if not isinstance(task, Task) or not task.challenge:
                skip_link += 1
                continue
            challenge_id_from_task = task.challenge.challenge_id  # Correct variable name
            if not challenge_id_from_task:
                skip_link += 1
                continue
            target_challenge = lookup.get(challenge_id_from_task)  # Correct variable name
            if target_challenge:
                target_challenge.add_task(task)
                linked += 1
            else:
                skip_found += 1
                log.debug(f"Task {getattr(task,'id','N/A')} links to missing chal {challenge_id_from_task}")
        log.info(f"Linking done. Linked:{linked}, NoLinkInfo:{skip_link}, NotFound:{skip_found}.")
        return linked

    def __len__(self) -> int:
        return len(self.challenges)

    def __iter__(self) -> Iterator[Challenge]:
        return iter(self.challenges)

    def __getitem__(self, index: int | slice) -> Challenge | list[Challenge]:
        if isinstance(index, int):
            if not 0 <= index < len(self.challenges):
                raise IndexError("Challenge index out of range")
        # Slicing works inherently on the list
        return self.challenges[index]

    def get_by_id(self, challenge_id: str) -> Challenge | None:
        """Finds a challenge by its ID."""
        # Can optimize with the lookup dict if created/stored persistently, but linear scan is fine too
        return next((c for c in self.challenges if c.id == challenge_id), None)

    # --- Filter methods - Placeholder implementations returning empty lists ---
    def _filter(self, criteria: callable[[Challenge], bool]) -> ChallengeList:
        # Basic filter mechanism used by others
        return ChallengeList(challenges=[c for c in self.challenges if criteria(c)])  # Corrected this

    def filter_by_name(self, name_part: str, case_sensitive=False) -> ChallengeList:
        name_match = name_part if case_sensitive else name_part.lower()
        return self._filter(lambda c: name_match in (c.name if case_sensitive else c.name.lower()))

    def filter_by_leader(self, leader_id: str) -> ChallengeList:
        return self._filter(lambda c: c.leader and c.leader.id == leader_id)

    def filter_by_group(self, group_id: str | None = None, group_type: str | None = None) -> ChallengeList:
        def criteria(c: Challenge) -> bool:
            group = c.group
            if not group:
                return False  # Challenge must have group for filtering
            if group_id and group.id != group_id:
                return False
            if group_type and group.type != group_type:
                return False
            return True

        return self._filter(criteria)

    def filter_official(self, official: bool = True) -> ChallengeList:
        return self._filter(lambda c: c.official == official)

    def filter_broken(self, is_broken: bool = True) -> ChallengeList:
        return self._filter(lambda c: c.is_broken == is_broken)

    def filter_joined(self, joined: bool = True) -> ChallengeList:
        return self._filter(lambda c: c.joined == joined)

    # --- End Filters ---

    def __repr__(self) -> str:
        return f"ChallengeList(count={len(self.challenges)})"


# ──────────────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MAIN EXECUTION (Example/Test)


async def main():
    """Demo function to retrieve, process, and display challenges."""
    log.info("--- Challenge Models Demo ---")
    challenge_list_instance: ChallengeList | None = None
    user_instance: User | None = None
    task_list_instance: TaskList | None = None
    try:
        # --- >>> Import Helpers used ONLY in main HERE <<< ---
        try:
            from pixabit.api.client import HabiticaClient  # Ensure client is imported if not global
            from pixabit.helpers._json import save_json

            # Import models again locally IF the global ones might be placeholders
            # from .user import User
            # from .task import TaskList
        except ImportError as main_import_err:
            log.critical(f"Main function failed to import essential helpers/client: {main_import_err}")
            return  # Cannot proceed without save_json/client
        # --- >>> End Main-Specific Imports <<< ---

        # --- Setup ---
        cache_dir = HABITICA_DATA_PATH / "challenges_demo"
        cache_dir.mkdir(parents=True, exist_ok=True)
        # Use consistent path objects
        raw_challenges_path = cache_dir / "challenges_raw.json"
        raw_tasks_path = cache_dir / "tasks_for_challenges_raw.json"
        raw_user_path = cache_dir / "user_for_challenges_raw.json"
        # Define processed save path
        processed_challenges_path = cache_dir / "processed_challenges.json"  # More descriptive name

        api = HabiticaClient()  # Assumes configured

        log.info("Fetching data...")
        results = await asyncio.gather(
            api.get_all_challenges_paginated(), api.get_tasks(), api.get_user_data(), return_exceptions=True  # Assuming this fetches all pages
        )
        raw_challenges = results[0] if not isinstance(results[0], Exception) else None
        raw_tasks = results[1] if not isinstance(results[1], Exception) else None
        raw_user = results[2] if not isinstance(results[2], Exception) else None

        # --- Validate Fetched Data ---
        if not isinstance(raw_challenges, list):
            log.error("Failed to fetch challenges.")
            return
        # Allow tasks/user fetch to potentially fail but continue
        if not isinstance(raw_tasks, list):
            log.warning("Failed to fetch tasks.")
        if not isinstance(raw_user, dict):
            log.error("Failed to fetch user data.")

        log.success(f"Fetched {len(raw_challenges)} Chals, {len(raw_tasks or [])} Tasks, User: {'OK' if raw_user else 'Failed'}")
        # Save raw data
        save_json(raw_challenges, raw_challenges_path.name, folder=raw_challenges_path.parent)
        if raw_tasks:
            save_json(raw_tasks, raw_tasks_path.name, folder=raw_tasks_path.parent)
        if raw_user:
            save_json(raw_user, raw_user_path.name, folder=raw_user_path.parent)

        # --- Validate Models ---
        log.info("Validating models...")
        # Define context (even if ownership validation moved, pass for potential future use)
        user_id_context = getattr(User.model_validate(raw_user), "id", None) if raw_user and User else None  # Safely get user ID for context
        validation_context = {"current_user_id": user_id_context}

        challenge_list_instance = ChallengeList.from_raw_data(raw_challenges, context=validation_context)  # Pass context
        if raw_tasks:
            task_list_instance = TaskList.from_raw_api_list(raw_tasks)
        if raw_user and User:
            try:
                user_instance = User.model_validate(raw_user)
            except Exception as e:
                log.error(f"User validation failed: {e}")  # Keep user_instance=None on fail

        log.success(f"Validated: {len(challenge_list_instance)} Chals, {len(task_list_instance or [])} Tasks, User: {user_instance is not None}")

        # --- Process: Set Status & Link ---
        # Set Joined Status (using validated user_instance)
        if user_instance and challenge_list_instance:
            log.info("Setting joined status...")
            # ... (logic for getting joined_ids from user_instance.profile.challenges) ...
            joined_ids = set(getattr(getattr(user_instance, "profile", None), "challenges", []))
            # owned_ids = ... # Placeholder for owned IDs
            for chal in challenge_list_instance.challenges:
                chal.joined = chal.id in joined_ids
                # chal.owned = chal.id in owned_ids
            log.info("Joined status updated.")

        # Link Tasks
        if challenge_list_instance and task_list_instance:
            log.info("Linking tasks...")
            linked_count = challenge_list_instance.link_tasks(task_list_instance)  # Get count if needed for logging
            log.info(f"Linking complete ({linked_count} tasks linked).")

        # --- Save Processed Challenge List (After Linking) ---
        if challenge_list_instance:
            log.info(f"Saving processed challenge list to {processed_challenges_path}...")
            try:
                # 1. Dump the ChallengeList to a dict, carefully excluding nested fields
                #    We need to specify the path to exclude within the structure.
                #    Structure: ChallengeList -> challenges (list) -> [index] -> tasks (list) -> [index] -> styled_text/notes
                #    The exclude syntax for nested lists isn't straightforward for model_dump.
                #    Easier: Dump challenges individually excluding bad fields, then reconstruct.

                processed_challenges_list = []
                for challenge in challenge_list_instance.challenges:
                    # Dump each challenge, excluding the Task fields causing issues
                    # The 'tasks' list itself is included, but styled_text/notes WITHIN those tasks are not.
                    # NOTE: Pydantic's nested exclude doesn't easily target computed fields
                    #       within nested list models directly. We may need to dump tasks manually.

                    challenge_dict = challenge.model_dump(
                        mode="json",
                        exclude={  # Exclude from the Challenge level
                            "tasks": {"__all__": {"styled_text", "styled_notes"}}  # For items in the 'tasks' list...  # Exclude these fields for all tasks
                        },
                    )
                    processed_challenges_list.append(challenge_dict)

                # Re-wrap the list of challenge dicts into the structure expected by ChallengeList save
                # Our ChallengeList BaseModel *only* has the 'challenges' field
                data_to_save = {"challenges": processed_challenges_list}

                # 2. Save the resulting dictionary using the basic save_json helper
                from pixabit.helpers._json import save_json

                save_successful = save_json(data_to_save, processed_challenges_path.name, folder=processed_challenges_path.parent)

                if save_successful:
                    log.success("Processed challenges saved.")
                else:
                    log.error("Failed to save processed challenges (save_json returned False).")

            except ImportError:
                log.error("Cannot save processed challenges: save_json helper missing.")
            except ValidationError as dump_err:
                log.error(f"Pydantic error during challenge list dump: {dump_err}")
            except Exception as save_err:
                log.exception(f"Error saving processed challenges: {save_err}")

        # --- Display ---
        if challenge_list_instance:
            print("\n--- Loaded Challenges (Sample Display) ---")
            print(f"Total: {len(challenge_list_instance)}")
            # ... (Display logic as before, e.g., show first 5) ...
            for i, chal in enumerate(challenge_list_instance.challenges[:5]):
                print(f"\n[{i+1}] {repr(chal)}")
                if chal.group:
                    print(f"    Group: '{chal.group.name}' (Privacy: {chal.group.privacy})")
                if chal.leader:
                    print(f"    Leader: {chal.leader.name}")
                # Optionally show linked tasks preview
                if chal.tasks:
                    print(f"    Tasks Sample: [{chal.tasks[0].text[:20] if chal.tasks else ''}...]")

    except Exception as e:
        log.exception(f"Main execution error: {e}")

    log.info("--- Challenge Models Demo Finished ---")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)-8s] %(name)s - %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("Pixabit").setLevel(logging.DEBUG)
    asyncio.run(main())

# ──────────────────────────────────────────────────────────────────────────────
