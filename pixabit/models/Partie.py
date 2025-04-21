# pixabit/models/party.py

# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for Habitica Parties and quest info.

Includes:
- `QuestProgress`: Holds progress data for an active quest.
- `QuestInfo`: Represents metadata about the party's current quest.
- `Party`: Represents the main Party group object.
"""

# SECTION: IMPORTS
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import emoji_data_python

# from textual import log # Use standard logger
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# Use standard logger
logger = logging.getLogger(__name__)

# Local Imports - Use placeholders if MessageList isn't defined elsewhere yet
try:
    from pixabit.models.message import MessageList  # Assuming this exists
except ImportError:
    logger.warning("Using placeholder for MessageList in party.py.")
    MessageList = list  # type: ignore # Placeholder


# SECTION: PYDANTIC MODELS


class QuestProgress(BaseModel):
    """Represents the progress within an active party quest."""

    model_config = ConfigDict(extra="ignore")  # Ignore unexpected progress fields

    # Use Field for defaults and potential future validation
    up: float = Field(default=0.0, description="Boss damage dealt or positive habit progress.")
    down: float = Field(default=0.0, description="Damage taken or negative habit progress.")
    collect_goal: Dict[str, int] = Field(
        default_factory=dict,
        alias="collect",
        description="Collection quest item goals {item_key: count_needed}.",
    )
    items_collected: int = Field(
        default=0,
        alias="collectedItems",
        description="Items collected so far for collection quests.",
    )
    hp: Optional[float] = Field(None, description="Boss HP.")  # Allow None
    rage: Optional[float] = Field(None, description="Boss Rage.")  # Allow None

    @field_validator("up", "down", "hp", "rage", mode="before")
    @classmethod
    def ensure_float_or_none(cls, value: Any) -> Optional[float]:
        """Ensures numeric progress fields are floats if present."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse quest progress value: {value}. Setting to None.")
            return None  # Or 0.0 depending on desired behavior

    @field_validator("items_collected", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensures items_collected is an integer."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def __repr__(self) -> str:
        """Concise representation."""
        parts = []
        if self.hp is not None:
            parts.append(f"hp={self.hp:.1f}")
        if self.rage is not None:
            parts.append(f"rage={self.rage:.1f}")
        if self.up != 0.0:
            parts.append(f"up={self.up:.1f}")
        if self.down != 0.0:
            parts.append(f"down={self.down:.1f}")
        if self.collect_goal:
            goal_total = sum(self.collect_goal.values())
            parts.append(f"collect#={self.items_collected}/{goal_total}")
        return f"QuestProgress({', '.join(parts)})"


class QuestInfo(BaseModel):
    """Represents the information about the party's current quest."""

    model_config = ConfigDict(extra="ignore")

    key: Optional[str] = Field(None, description="The unique key for the quest (e.g., 'basilisk').")
    active: bool = Field(False, description="Raw active flag from API.")
    rsvp_needed: bool = Field(
        False, alias="RSVPNeeded", description="Does leader need to accept invites?"
    )
    completed_status: Optional[str] = Field(
        None, alias="completed", description="Completion status or timestamp string."
    )
    leader_id: Optional[str] = Field(
        None, alias="leader", description="User ID of the quest leader/inviter."
    )
    members_rsvp: Optional[Dict[str, bool]] = Field(
        None, alias="members", description="Member RSVP status {userId: bool}."
    )  # Allow None
    extra_data: Optional[Dict[str, Any]] = Field(
        None, alias="extra", description="Additional quest-specific data."
    )  # Allow None

    # Nested progress model
    progress: QuestProgress = Field(default_factory=QuestProgress)

    @property
    def is_active(self) -> bool:
        """Calculates if the quest is truly active (active flag, not complete, has key)."""
        return self.active and not self.completed_status and bool(self.key)

    def __repr__(self) -> str:
        """Concise representation."""
        status = (
            "Active" if self.is_active else ("Completed" if self.completed_status else "Inactive")
        )
        key_str = f"key='{self.key}'" if self.key else "No Key"
        return f"QuestInfo({key_str}, status={status}, progress={self.progress})"


class Party(BaseModel):
    """Represents a Habitica Party group object using Pydantic."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: Optional[str] = Field(
        None, description="Unique party ID."
    )  # Allow None, might be missing in some contexts
    name: str = Field("Unnamed Party", description="Party name (emoji parsed).")
    description: Optional[str] = Field(None, description="Party description (emoji parsed).")
    summary: Optional[str] = Field(None, description="Party summary/tagline (emoji parsed).")
    leader_id: Optional[str] = Field(None, description="User ID of the party leader.")
    member_sort_order: Optional[str] = Field(
        None, alias="order", description="Field used for sorting members."
    )
    member_sort_ascending: Optional[bool] = Field(
        None, alias="orderAscending", description="Whether member sort is ascending."
    )

    # Nested QuestInfo model
    quest: QuestInfo = Field(default_factory=QuestInfo)

    # --- Placeholders for related data (populated separately) ---
    # Use Field(..., exclude=True) if these shouldn't be in model_dump output
    chat: Optional[MessageList] = Field(None, description="Party chat messages (populated externally).", exclude=True)  # type: ignore
    members: List[Any] = Field(
        default_factory=list, description="Party members (populated externally).", exclude=True
    )  # Placeholder type

    # --- Validators ---
    @field_validator("id", mode="before")
    @classmethod
    def handle_id_or_underscore_id(cls, v: Any, info: FieldValidationInfo) -> Optional[str]:
        """Use '_id' if 'id' is not present."""
        # Validator runs *before* alias resolution for `id` if not explicitly aliased
        if v is None and isinstance(info.data, dict):
            return info.data.get("_id")  # Check _id if id is missing
        return v

    @field_validator("name", "description", "summary", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any) -> Optional[str]:
        """Parses text fields and replaces emoji shortcodes."""
        if isinstance(value, str):
            # Ensure empty strings become None for optional fields if desired, or keep as ""
            text = emoji_data_python.replace_colons(value)
            return (
                text if text else None
            )  # Return None if empty after parsing? Or ""? Let's keep "" for name.
        # Handle name specifically to avoid it becoming None
        if value is None and cls is Party.__fields__["name"]:  # Check if validating name field
            return "Unnamed Party"  # Default name if input is None
        elif value is None:
            return None  # Return None for optional description/summary if input is None
        return str(value)  # Fallback conversion

    @field_validator("leader_id", mode="before")
    @classmethod
    def extract_leader_id(cls, v: Any, info: FieldValidationInfo) -> Optional[str]:
        """Extracts leader ID whether 'leader' field is a string or dict."""
        # Validator runs *before* alias resolution, check source 'leader' key
        if isinstance(info.data, dict):
            leader_info = info.data.get("leader")
            if isinstance(leader_info, str):
                return leader_info
            elif isinstance(leader_info, dict):
                return leader_info.get("_id") or leader_info.get("id")
        return None  # Handle cases where leader info isn't usable

    @field_validator("member_sort_ascending", mode="before")
    @classmethod
    def normalize_order_ascending(cls, v: Any) -> Optional[bool]:
        """Normalizes 'orderAscending' from string 'true'/'false' or bool."""
        if isinstance(v, bool):
            return v
        elif isinstance(v, str):
            return v.lower() == "true"
        return None  # Not a bool or recognized string

    # --- Methods ---
    def set_chat(self, message_list: MessageList) -> None:  # type: ignore
        """Assigns a MessageList containing the party's chat messages."""
        # Add type check if MessageList is properly defined
        # if isinstance(message_list, MessageList):
        self.chat = message_list
        # else:
        #     logger.warning("Invalid type provided to Party.set_chat. Expected MessageList.")

    def __repr__(self) -> str:
        """Concise representation."""
        quest_str = (
            f", quest='{self.quest.key}'" if self.quest and self.quest.key else ", quest=None"
        )
        active_str = " (Active)" if self.quest and self.quest.is_active else ""
        chat_len = (
            len(self.chat) if self.chat is not None else 0
        )  # Assuming MessageList is list-like
        chat_str = f", chat={chat_len} msgs" if chat_len > 0 else ", chat=N/A"
        name_preview = self.name[:30] + ("..." if len(self.name) > 30 else "")
        return f"Party(id='{self.id}', name='{name_preview}'{quest_str}{active_str}{chat_str})"
