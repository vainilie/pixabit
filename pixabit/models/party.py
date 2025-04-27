# pixabit/models/party.py

# ─── Model ────────────────────────────────────────────────────────────────────
#            Habitica Party & Quest Models
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for Habitica Parties, including nested quest progress,
chat messages (via MessageList), and basic member information.
"""

# SECTION: IMPORTS
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator  # Use standard lowercase etc.

# External Libs
import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FieldValidationInfo,
    PrivateAttr,  # For internal, non-dumped attributes
    ValidationError,
    ValidationInfo,  # For context
    field_validator,
    model_validator,
)

# Local Imports
try:
    from pixabit.api.client import HabiticaClient
    from pixabit.config import HABITICA_DATA_PATH, USER_ID  # Import USER_ID
    from pixabit.helpers._json import load_pydantic_model, save_json, save_pydantic_model
    from pixabit.helpers._logger import log
    from pixabit.helpers.DateTimeHandler import DateTimeHandler

    from .game_content import Quest as StaticQuestData  # Rename to avoid clash
    from .game_content import StaticContentManager

    # Import models used within Party
    from .message import Message, MessageList
except ImportError:
    # Fallbacks for isolated testing
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    USER_ID = "fallback_user_id_from_config"
    HABITICA_DATA_PATH = Path("./pixabit_cache")

    def save_pydantic_model(m, p, **kwargs):
        pass

    def load_pydantic_model(cls, p, **kwargs):
        return None

    log.warning("party.py: Could not import dependencies. Using fallbacks.")

CACHE_SUBDIR = "party"
PARTY_RAW_FILENAME = "party_raw.json"
PARTY_PROCESSED_FILENAME = "party_processed.json"


# SECTION: PYDANTIC SUB-MODELS


# KLASS: QuestProgress
class QuestProgress(BaseModel):
    """Represents the progress within an active party quest."""

    model_config = ConfigDict(
        extra="ignore",  # Ignore fields like quest key/leader here
        populate_by_name=True,
        frozen=False,  # Progress changes
    )

    # Boss quest progress
    up: float = Field(0.0, description="Boss damage dealt or positive habit progress.")
    down: float = Field(0.0, description="Damage taken or negative habit progress.")
    hp: float | None = Field(None, description="Boss current HP (if applicable).")  # Boss HP can be None
    rage: float | None = Field(None, description="Boss current Rage (if applicable).")  # Rage can be None

    # Collection quest progress
    # Raw collect goals are dict like {item_key: count_needed} - Use extra='allow'? Or explicit model?
    # Pydantic can parse dicts directly, 'extra=allow' is simplest if keys vary widely
    # collect: dict[str, int] = Field(default_factory=dict, description="Item collection goals (key: count needed).")
    # Prefer defining if structure is consistent from API
    collect_goals: dict[str, int] = Field(default_factory=dict, alias="collect", description="Item collection goals (key: count needed).")

    # Actual collected count (often separate field from goals)
    collected_items_count: int = Field(0, alias="collectedItems", description="Items collected so far for collection quests.")

    # Validator for numeric fields
    @field_validator("up", "down", "hp", "rage", mode="before")
    @classmethod
    def ensure_float_or_none(cls, value: Any) -> float | None:
        """Ensures numeric progress fields are floats if present, else None."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            log.debug(f"Could not parse quest progress value: {value!r}. Defaulting.")
            # Defaulting to 0 might be wrong if None meant "not applicable"
            # Return 0 for up/down, None for hp/rage might be better? Let's default to 0.0 for now.
            return 0.0  # Or decide based on field if None is more appropriate default

    @field_validator("collected_items_count", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensures collected_items is an integer, defaulting to 0."""
        if value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            log.debug(f"Could not parse collected_items value: {value!r}. Setting to 0.")
            return 0

    # Collect goals validation? Could ensure keys are str, values are int.
    # Pydantic dict validation usually handles basic types.

    def __repr__(self) -> str:
        """Concise representation."""
        parts = []
        if self.hp is not None:
            parts.append(f"hp={self.hp:.1f}")
        if self.rage is not None:
            parts.append(f"rage={self.rage:.1f}")
        # Only show up/down if non-zero or hp exists (relevant for boss quests)
        if self.hp is not None or self.up != 0.0:
            parts.append(f"up={self.up:.1f}")
        if self.hp is not None or self.down != 0.0:
            parts.append(f"down={self.down:.1f}")
        if self.collect_goals:
            goal_str = ",".join(f"{k}:{v}" for k, v in self.collect_goals.items())
            parts.append(f"collect={self.collected_items_count}/[{goal_str}]")
        progress_str = ", ".join(parts) if parts else "No Progress"
        return f"QuestProgress({progress_str})"


# KLASS: QuestInfo
class QuestInfo(BaseModel):
    """Represents the metadata about the party's current quest."""

    model_config = ConfigDict(
        extra="ignore",  # Ignore fields like webhook url etc.
        populate_by_name=True,
        frozen=False,  # Status changes (active, completed)
    )

    key: str | None = Field(None, description="Unique key for the quest (e.g., 'basilisk'). Null if no quest.")
    active: bool = Field(False, description="Is the quest active (invitation sent/accepted)?")
    # Use alias for API's `RSVPNeeded`
    rsvp_needed: bool = Field(False, alias="RSVPNeeded", description="Does leader need to accept invites?")
    # Completion status: Can be timestamp string, 'allGuilds', or null/absent. Store as string.
    completed_status: str | None = Field(None, alias="completed", description="Completion status or timestamp string.")
    leader_id: str | None = Field(None, alias="leader", description="User ID of the quest leader/inviter.")

    # Member RSVP status {userId: bool | null} - Null means pending? bool means accepted/declined?
    # API might use `true` for accepted, `false` for declined?, absence=pending?
    # Using bool | None for flexibility.
    member_rsvp: dict[str, bool | None] = Field(default_factory=dict, alias="members")

    # Nested progress model
    progress: QuestProgress = Field(default_factory=QuestProgress)

    # --- Derived Properties ---
    @property
    def completed_timestamp(self) -> datetime | None:
        """Parses completed_status into a datetime if possible."""
        if self.completed_status:
            handler = DateTimeHandler(timestamp=self.completed_status)
            return handler.utc_datetime  # Returns None if parsing fails
        return None

    @property
    def is_active_and_ongoing(self) -> bool:
        """Calculates if the quest is active AND not yet completed."""
        # Active flag must be true AND completed_status must be missing/null/empty
        return self.active and not self.completed_status

    # --- Representation ---
    def __repr__(self) -> str:
        """Concise representation."""
        status = "Inactive"
        if self.completed_status:
            completion_time = self.completed_timestamp
            status = f"Completed ({completion_time.strftime('%Y-%m-%d')})" if completion_time else f"Completed ({self.completed_status})"
        elif self.active:
            status = "Active/Ongoing" if self.is_active_and_ongoing else "Pending"  # Or Invited?

        key_str = f"key='{self.key}'" if self.key else "No Quest"
        return f"QuestInfo({key_str}, status={status})"


# KLASS: PartyMember (Basic info available directly in party data)
class PartyMember(BaseModel):
    """Represents basic info about a member as found in party data (usually just ID)."""

    # API `/groups/{groupId}` returns a list of member *IDs*.
    # Full member details require additional calls.
    # So this model primarily just holds the ID found in the party structure itself.
    # If the API endpoint DOES provide more nested details, expand this model.

    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)
    # Assuming the list contains just IDs, not full member objects
    id: str  # This would be validated from the list of strings if members = ['id1', 'id2']

    # If API returns list of member objects:
    # id: str = Field(..., alias="_id") # Map from _id if needed
    # display_name: str | None = None # Often requires separate fetch
    # username: str | None = None     # Often requires separate fetch


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MAIN PARTY MODEL


# KLASS: Party
class Party(BaseModel):
    """Represents a Habitica Party group object, including quest and chat."""

    model_config = ConfigDict(
        extra="ignore",  # Ignore fields like leader message, leader object details
        populate_by_name=True,
        validate_assignment=True,  # Re-validate on assignment if needed
        arbitrary_types_allowed=True,  # Needed for MessageList initially, might be removable if MessageList validation works directly
    )

    # --- Core Identification & Info ---
    id: str = Field(..., description="Unique party ID (mapped from _id).")
    name: str = Field("Unnamed Party", description="Party name (parsed emoji).")
    description: str = Field("", description="Party description (parsed emoji).")
    # summary: str | None = Field(None, description="Party summary/tagline (parsed emoji).") # Less common

    # --- Leader & Members ---
    leader_id: str | None = Field(None, description="User ID of the party leader.")  # Extracted by validator
    # The raw API has `memberCount` and a separate `members` list (usually just IDs).
    # We store the count directly. Member objects would need separate loading/linking.
    member_count: int = Field(0, alias="memberCount", description="Number of members in the party.")
    # Optional: store member IDs if useful
    # member_ids: list[str] = Field(default_factory=list)

    # --- Quest ---
    quest: QuestInfo = Field(default_factory=QuestInfo, description="Details of the current party quest.")

    # --- Chat ---
    # Use the MessageList Pydantic model. Validation will happen here.
    # Context (`current_user_id`) is needed for MessageList validation.
    # Exclude from default serialization unless explicitly included.
    chat: MessageList | None = Field(None, description="Party chat messages.")

    # --- Sorting Info ---
    # order: str | None = Field(None, description="Field used for sorting members.") # Less commonly used?
    # order_ascending: bool | None = Field(None, alias="orderAscending")

    # --- Internal attribute for storing fetched static quest data ---
    _static_quest_details: StaticQuestData | None = PrivateAttr(default=None)

    # --- Validators ---

    @model_validator(mode="before")
    @classmethod
    def prepare_data(cls, data: Any) -> dict[str, Any]:
        """Prepare raw data: Map IDs, extract leader ID."""
        if not isinstance(data, dict):
            return data  # Let Pydantic handle type error

        values = data.copy()

        # Map _id -> id
        if "_id" in values and "id" not in values:
            values["id"] = values["_id"]

        # Extract leader ID from potentially nested structure
        leader_info = values.get("leader")
        if isinstance(leader_info, str):
            # Leader is just an ID string
            values["leader_id"] = leader_info
        elif isinstance(leader_info, dict):
            # Leader is an object, get ID from it
            values["leader_id"] = leader_info.get("_id") or leader_info.get("id")
        # 'leader' key itself might be absent

        # Handle potential direct 'chat' list/dict from API
        # Pydantic handles validating `chat` key against `MessageList` type hint

        # Extract member IDs? Assuming API provides `members` as list of IDs
        # member_data = values.get("members")
        # if isinstance(member_data, list) and all(isinstance(m, str) for m in member_data):
        #      values["member_ids"] = member_data

        return values

    # Ensure ID exists after potential mapping
    @field_validator("id", mode="after")
    @classmethod
    def check_id(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Party ID (_id) is required and must be a string.")
        return v

    # Consolidate text parsing
    @field_validator("name", "description", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any, info: FieldValidationInfo) -> str:
        """Parses text fields, replaces emoji, handles defaults."""
        default = "Unnamed Party" if info.field_name == "name" else ""
        if isinstance(value, str):
            parsed = emoji_data_python.replace_colons(value).strip()
            return parsed if parsed else default
        return default

    @field_validator("member_count", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensure member_count is an integer."""
        if value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    # --- Methods ---

    @classmethod
    def create_from_raw_data(cls, raw_data: dict, current_user_id: str | None = None) -> Party:
        """Factory method to create Party, passing context for chat validation."""
        if not isinstance(raw_data, dict):
            log.error(f"Invalid raw data type for Party creation: Expected dict, got {type(raw_data)}")
            raise TypeError("Invalid input data for Party creation.")

        # Define the context required by MessageList validation
        validation_context = {"current_user_id": current_user_id}

        log.debug(f"Creating Party from raw data with context: {validation_context}")
        try:
            # Validate the raw data using the context
            # Pydantic will automatically pass this context down when validating nested models
            # like 'chat: MessageList' if the nested model's validator requests it.
            party_instance = cls.model_validate(raw_data, context=validation_context)
            log.debug(f"Party instance created successfully: {party_instance.id}")
            return party_instance
        except ValidationError as e:
            log.error(f"Validation failed creating Party model: {e}", exc_info=False)  # Log less verbose error
            log.debug(f"Failed raw data keys: {list(raw_data.keys())}")  # Log keys for debugging
            # Optionally log parts of the data that failed, be mindful of size/privacy
            # log.debug(f"Failing quest data: {raw_data.get('quest')}")
            # log.debug(f"Failing chat data sample: {raw_data.get('chat', [])[:2]}")
            raise  # Re-raise the specific Pydantic error
        except Exception as e:
            log.exception("Unexpected error creating Party from raw data.")  # Log full trace
            raise

    def get_chat_messages(self) -> list[Message]:
        """Returns the validated list of chat messages, or an empty list."""
        # Access validated messages from the nested MessageList model
        return self.chat.messages if self.chat else []

    async def fetch_and_set_static_quest_details(self, content_manager: StaticContentManager) -> StaticQuestData | None:
        """Fetches static quest details using the content manager and caches it internally.

        Args:
            content_manager: An instance of StaticContentManager.

        Returns:
            The fetched static quest data, or None if not found or no quest active.
        """
        if not self.quest or not self.quest.key:
            log.debug("Party has no active quest key. Cannot fetch static details.")
            self._static_quest_details = None
            return None

        log.debug(f"Fetching static quest details for key: '{self.quest.key}'")
        try:
            # Use the provided manager instance to get quest details
            static_data = await content_manager.get_quest(self.quest.key)
            if static_data:
                log.success(f"Successfully fetched static details for quest '{self.quest.key}'.")
                self._static_quest_details = static_data  # Store internally
                return static_data
            else:
                log.warning(f"Static details not found for quest key '{self.quest.key}'.")
                self._static_quest_details = None
                return None
        except Exception as e:
            log.exception(f"Error fetching static quest details for '{self.quest.key}': {e}")
            self._static_quest_details = None
            return None

    @property
    def static_quest_details(self) -> StaticQuestData | None:
        """Returns the internally cached static quest details (if fetched)."""
        return self._static_quest_details

    # --- Representation ---
    def __repr__(self) -> str:
        """Concise representation."""
        quest_repr = repr(self.quest) if self.quest else "No Quest"
        chat_len = len(self.chat.messages) if self.chat and self.chat.messages else 0
        name_preview = self.name[:30].replace("\n", " ") + ("..." if len(self.name) > 30 else "")

        return f"Party(id='{self.id}', name='{name_preview}', members={self.member_count}, chat={chat_len}, {quest_repr})"

    def __str__(self) -> str:
        """User-friendly representation (name)."""
        return self.name


# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MAIN EXECUTION (Example/Test)


async def main():
    """Demo function to retrieve, process, and save party data."""
    log.info("--- Party Model Demo ---")
    party_instance: Party | None = None

    # Use USER_ID from config for context
    user_id_context = USER_ID
    if not user_id_context or user_id_context == "fallback_user_id_from_config":
        log.warning("Cannot run demo effectively: Valid USER_ID not found in config.")
        # Provide a dummy ID for testing if absolutely necessary
        user_id_context = "test-user-id-123"
        log.info(f"Using dummy USER_ID for context: {user_id_context}")

    try:
        # Ensure cache directory exists
        cache_dir = HABITICA_DATA_PATH / CACHE_SUBDIR
        cache_dir.mkdir(exist_ok=True, parents=True)
        raw_path = cache_dir / PARTY_RAW_FILENAME
        processed_path = cache_dir / PARTY_PROCESSED_FILENAME

        # 1. Get data from API
        log.info("Fetching party data from API...")
        api = HabiticaClient()  # Assumes configured
        raw_data = await api.get_party_data()

        if not raw_data:
            log.error("Failed to fetch party data from API. Exiting.")
            return None

        # Optionally save raw data
        save_json(raw_data, raw_path)

        # 2. Create Party model using the factory method with context
        log.info(f"Processing raw party data (using user ID '{user_id_context}' for chat context)...")
        party_instance = Party.create_from_raw_data(raw_data, current_user_id=user_id_context)
        log.success("Party model created successfully.")

        # 3. Example Data Access
        print(f"  Party Name: {party_instance.name}")
        print(f"  Party ID: {party_instance.id}")
        print(f"  Leader ID: {party_instance.leader_id}")
        print(f"  Member Count: {party_instance.member_count}")
        print(f"  Quest Info: {party_instance.quest}")
        print(f"  Quest Progress: {party_instance.quest.progress}")
        print(f"  Chat Message Count: {len(party_instance.get_chat_messages())}")

        # 4. Example: Fetch and store static quest data
        log.info("Attempting to fetch static quest details...")
        # Requires StaticContentManager to be instantiated
        content_manager = StaticContentManager()  # Use default paths
        static_details = await party_instance.fetch_and_set_static_quest_details(content_manager)
        if static_details:
            print(f"  Fetched Static Quest Title: {static_details.text}")  # Access field from StaticQuestData
        elif party_instance.quest.key:
            print(f"  Could not fetch static details for quest '{party_instance.quest.key}'.")
        else:
            print("  No active quest to fetch details for.")

        # 5. Save processed data (using pydantic helper)
        # Choose whether to include chat by controlling the dump excludes manually if needed,
        # or rely on the exclude=True in the Field definition. model_dump respects exclude=True by default.
        log.info(f"Saving processed party data to {processed_path}...")
        if save_pydantic_model(party_instance, processed_path):  # Chat excluded by default
            log.success("Processed party data saved.")
            # To explicitly include chat:
            data_to_save = party_instance.model_dump(mode="json", exclude_none=True)  # Pydantic handles exclude=True
            save_json(data_to_save, cache_dir / "party_with_chat.json")
        else:
            log.error("Failed to save processed party data.")

    except ValidationError as e:
        log.error(f"Pydantic validation error during party processing: {e}")
    except ConnectionError as e:
        log.error(f"API connection error fetching party data: {e}")
    except Exception as e:
        log.exception(f"An unexpected error occurred in the party demo: {e}")

    return party_instance


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(main())

# ──────────────────────────────────────────────────────────────────────────────
