# pixabit/models/message.py

# SECTION: MODULE DOCSTRING
"""Defines Pydantic data model classes for representing Habitica messages.

Includes:
- `Message`: Represents an individual message (Inbox or Group Chat).
- `MessageList`: A container class to manage a collection of Message objects,
  providing processing, sorting, filtering, and conversation grouping.
"""

# SECTION: IMPORTS
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
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
# Assuming RichHandler is primarily for top-level script execution
# from rich.logging import RichHandler
# FORMAT = "%(message)s"
# logging.basicConfig(...) # Configure logging at application entry point
logger = logging.getLogger(__name__) # Use standard Python logger


# SECTION: PYDANTIC MODELS

class MessageSenderStyles(BaseModel):
    """Represents the nested userStyles object for sender styling info."""
    model_config = ConfigDict(extra='allow') # Allow other style fields

    # Example - extract class if present within stats sub-dict
    klass: Optional[str] = Field(None, alias='class') # Map 'class' to 'klass'

    @model_validator(mode='before')
    @classmethod
    def extract_class(cls, data: Any) -> Any:
        """Extracts class from stats sub-dictionary if present."""
        if isinstance(data, dict):
            stats_data = data.get('stats')
            if isinstance(stats_data, dict):
                # Assign to the alias 'class' so Pydantic maps it to 'klass'
                data['class'] = stats_data.get('class')
        return data

class Message(BaseModel):
    """Represents an individual message in Habitica (Inbox or Group Chat)."""
    model_config = ConfigDict(extra="allow", populate_by_name=True) # Allow extra fields, use aliases

    # Core IDs & Context
    id: str = Field(..., alias="_id", description="Unique message document ID.") # Assume ID is required
    sender_id: Optional[str] = Field(None, alias="uuid", description="User ID of the sender ('system' for system messages).")
    group_id: Optional[str] = Field(None, alias="groupId", description="ID of the group chat (e.g., party, guild ID, tavern). None for PMs.")
    recipient_id: Optional[str] = Field(None, alias="ownerId", description="User ID of the inbox owner (often the recipient in PMs).")

    # Sender Info (Partially from direct fields, partially nested)
    sender_display_name: Optional[str] = Field(None, alias="user", description="Sender's display name (emoji parsed).")
    sender_username: Optional[str] = Field(None, alias="username", description="Sender's login name.")
    sender_styles: Optional[MessageSenderStyles] = Field(None, alias="userStyles", description="Sender's style information.")

    # Content & Timestamp
    text: str = Field("", description="Formatted message text (emoji parsed).")
    unformatted_text: Optional[str] = Field(None, alias="unformattedText", description="Unformatted source text (emoji parsed).")
    timestamp: Optional[datetime] = Field(None, description="Timestamp message was sent/received (UTC).")

    # Engagement
    likes: Dict[str, bool] = Field(default_factory=dict, description="Dictionary of user IDs who liked the message.")
    flags: Dict[str, bool] = Field(default_factory=dict, description="Dictionary of user IDs who flagged the message.")
    flag_count: int = Field(0, alias="flagCount", description="Total number of flags.")

    # System Message Info
    info: Optional[Dict[str, Any]] = Field(None, description="Data for system messages (spells, quests, etc.).")

    # --- Fields calculated/set externally AFTER initial validation ---
    # These depend on `current_user_id` which is not part of the message data itself.
    sent_by_me: Optional[bool] = Field(None, exclude=True, description="True if the message was sent by the current user.")
    conversation_id: Optional[str] = Field(None, exclude=True, description="ID for grouping (group_id or other user's ID in PMs).")

    # --- Validators ---
    @field_validator('id', mode='before')
    @classmethod
    def handle_id_or_underscore_id(cls, v: Any, info: FieldValidationInfo) -> Optional[str]:
        """Use '_id' if 'id' is not present."""
        if v is None and isinstance(info.data, dict):
            _id = info.data.get('_id')
            if not _id: raise ValueError("Message data must contain 'id' or '_id'")
            return _id
        elif not v:
             raise ValueError("Message data must contain 'id' or '_id'")
        return v

    @field_validator("text", "unformatted_text", "sender_display_name", mode="before")
    @classmethod
    def parse_text_emoji(cls, value: Any) -> Optional[str]:
        """Parses text fields and replaces emoji shortcodes."""
        if isinstance(value, str):
            return emoji_data_python.replace_colons(value)
        return None # Return None if input is not string or None

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp_robust(cls, value: Any) -> Optional[datetime]:
        """Parses ISO string or epoch milliseconds/seconds into UTC datetime."""
        if isinstance(value, str):
            try:
                # Handle ISO 8601 format, ensuring UTC
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass # Fall through if not ISO string
        elif isinstance(value, (int, float)):
            try:
                # Assume ms if large number, otherwise seconds
                ts_sec = value / 1000.0 if value > 1e11 else value
                return datetime.fromtimestamp(ts_sec, tz=timezone.utc)
            except (ValueError, OSError, TypeError):
                pass # Fall through if invalid number
        elif isinstance(value, datetime):
             # Ensure timezone aware UTC
            if value.tzinfo is None: return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)

        logger.warning(f"Could not parse timestamp: {value}. Type: {type(value)}. Setting to None.")
        return None

    @field_validator("flag_count", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensures flag_count is an integer."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    # --- Properties ---
    @property
    def is_system_message(self) -> bool:
        """Checks if this is likely a system message."""
        # Consider sender ID or presence of 'info' field
        return bool(self.info) or self.sender_id == "system"

    @property
    def sender_class(self) -> Optional[str]:
         """Extracts sender's class from sender_styles, if available."""
         return self.sender_styles.klass if self.sender_styles else None

    # --- Methods ---
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        sender_repr = "System" if self.is_system_message else (self.sender_username or self.sender_id or "Unknown")
        ts_repr = self.timestamp.strftime("%Y-%m-%d %H:%M") if self.timestamp else "No Time"
        # Use post-processed conv_id if available
        conv_repr = f" (Conv: {self.conversation_id})" if hasattr(self, 'conversation_id') and self.conversation_id else ""
        text_preview = self.text[:30].replace("\n", " ") + ("..." if len(self.text) > 30 else "")
        return f"Message(id={self.id}, from='{sender_repr}', time='{ts_repr}{conv_repr}', text='{text_preview}')"


# --- CONTAINER CLASS ---

class MessageList:
    """Container for managing Message objects.

    Processes raw message data, calculates context-dependent fields (like
    conversation IDs based on the current user), sorts messages, and provides
    filtering methods.
    """

    def __init__(
        self,
        raw_message_list: List[Dict[str, Any]],
        current_user_id: Optional[str] = None,
    ):
        """Initializes the MessageList.

        Args:
            raw_message_list: List of dictionaries (raw message data from API).
            current_user_id: The UUID of the user viewing the messages. Needed
                               to correctly determine PM conversation IDs and sent_by_me.
        """
        self.messages: List[Message] = []
        self.current_user_id = current_user_id
        logger.debug(f"Initializing MessageList for user: {current_user_id}")
        self._process_list(raw_message_list)
        logger.info(f"Processed {len(self.messages)} messages.")

    def _process_list(self, raw_message_list: List[Dict[str, Any]]) -> None:
        """Processes raw list, creates/validates Message instances, calculates context fields, and sorts."""
        processed_messages: List[Message] = []
        if not isinstance(raw_message_list, list):
            logger.error(f"raw_message_list must be a list, got {type(raw_message_list)}.")
            self.messages = []
            return

        for raw_message in raw_message_list:
            if not isinstance(raw_message, dict):
                logger.warning(f"Skipping invalid non-dict entry in raw_message_list: {raw_message}")
                continue
            try:
                # 1. Validate raw data into Message object
                message_instance = Message.model_validate(raw_message)

                # 2. Post-processing: Calculate context-dependent fields
                # Calculate sent_by_me
                message_instance.sent_by_me = False # Default
                if self.current_user_id:
                    if message_instance.sender_id == self.current_user_id:
                         message_instance.sent_by_me = True
                    # Check 'sent' flag only if sender isn't current user or sender is missing
                    elif raw_message.get("sent") is True and message_instance.sender_id != self.current_user_id:
                         message_instance.sent_by_me = True
                         # If sent flag is true but uuid doesn't match, likely API inconsistency?
                         # Or potentially a message *I* sent but API represents sender differently?
                         # For safety, if 'sent' is true and sender isn't me, maybe log warning.
                         # if message_instance.sender_id and message_instance.sender_id != self.current_user_id:
                         #      logger.debug(f"Message {message_instance.id} has 'sent: true' but sender_id '{message_instance.sender_id}' != current_user_id '{self.current_user_id}'")


                # Calculate conversation_id (using logic moved from old Message.__init__)
                message_instance.conversation_id = self._determine_conversation_id(message_instance)

                # Only add if message has an ID (validation should catch this, but belt-and-suspenders)
                if message_instance.id:
                    processed_messages.append(message_instance)
                else:
                    # Should not happen if validator works, but log just in case
                    logger.warning(f"Skipping message missing ID after validation: {raw_message.get('text', 'N/A')[:30]}...")

            except ValidationError as e:
                 logger.error(f"Validation failed for message '{raw_message.get('text', raw_message.get('_id', 'N/A'))[:30]}...':\n{e}")
            except Exception as e:
                logger.error(f"Error processing message data for ID {raw_message.get('id', 'N/A')}: {e}", exc_info=True)

        # Sort messages chronologically
        default_time = datetime.min.replace(tzinfo=timezone.utc)
        processed_messages.sort(key=lambda m: m.timestamp or default_time)

        self.messages = processed_messages

    def _determine_conversation_id(self, message: Message) -> Optional[str]:
         """Calculates conversation ID based on processed Message object and current user context."""
         if message.group_id:
             return message.group_id # Group chat ID

         # Private Message Logic
         if not self.current_user_id:
             logger.debug(f"Cannot determine PM conversation ID for msg {message.id} without current_user_id.")
             return None # Cannot determine without context

         sender = message.sender_id
         recipient = message.recipient_id # 'ownerId' mapped to recipient_id

         if message.sent_by_me:
             # I sent it. Conversation is with the recipient.
             # If recipient_id is set AND it's not me, that's the other person.
             if recipient and recipient != self.current_user_id:
                 return recipient
             else:
                  # This can happen if fetching sent items where recipient info isn't clear
                  # or if ownerId was incorrectly my own ID on a sent message.
                  logger.debug(f"Could not determine recipient for sent message {message.id}.")
                  return None # Cannot determine other party
         elif sender and sender != self.current_user_id:
             # Someone else sent it to me. Conversation is with the sender.
             return sender
         elif sender == "system":
             return "system" # Assign a specific ID for system messages
         else:
             # Unknown state (e.g., sender missing, sender is me but sent_by_me wasn't true?)
             logger.debug(f"Could not determine conversation ID for message {message.id} (Sender: {sender}, Recipient: {recipient}).")
             return None

    # --- Access and Filtering Methods ---
    # Return List[Message] from filters

    def __len__(self) -> int: return len(self.messages)
    def __iter__(self) -> iter[Message]: return iter(self.messages)
    def __getitem__(self, index: int) -> Message:
        if not isinstance(index, int): raise TypeError("Index must be an integer")
        if not 0 <= index < len(self.messages): raise IndexError("Message index out of range")
        return self.messages[index]

    def get_by_id(self, message_id: str) -> Optional[Message]:
        """Finds a message by its unique ID."""
        return next((m for m in self.messages if m.id == message_id), None)

    def filter_by_sender(self, sender_id: str) -> List[Message]:
        """Returns messages sent by a specific user ID."""
        return [m for m in self.messages if m.sender_id == sender_id]

    def filter_by_conversation(self, conversation_id: str) -> List[Message]:
        """Returns messages belonging to a specific conversation ID."""
        # Uses the conversation_id calculated during _process_list
        return [m for m in self.messages if m.conversation_id == conversation_id]

    def filter_by_group(self, group_id: str) -> List[Message]:
        """Returns messages belonging to a specific group ID."""
        return [m for m in self.messages if m.group_id == group_id]

    def filter_private_messages(self) -> List[Message]:
        """Returns messages likely Private Messages (no group_id)."""
        return [m for m in self.messages if m.group_id is None]

    def filter_system_messages(self, is_system: bool = True) -> List[Message]:
        """Returns system messages or non-system messages based on the property."""
        return [m for m in self.messages if m.is_system_message is is_system]

    def filter_by_text(self, text_part: str, case_sensitive: bool = False) -> List[Message]:
        """Filters messages containing a specific text substring."""
        if not case_sensitive:
            text_part_lower = text_part.lower()
            return [m for m in self.messages if text_part_lower in m.text.lower()]
        else:
            return [m for m in self.messages if text_part in m.text]

    def filter_by_date_range(self, start: Optional[datetime] = None, end: Optional[datetime] = None) -> List[Message]:
        """Filters messages within a specific date/time range (UTC, inclusive)."""
        start_utc = None
        if start: start_utc = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
        end_utc = None
        if end: end_utc = end if end.tzinfo else end.replace(tzinfo=timezone.utc)

        filtered_messages: List[Message] = []
        for m in self.messages:
            if not m.timestamp: continue # Skip messages without timestamp
            ts_utc = m.timestamp # Already UTC
            if start_utc and ts_utc < start_utc: continue
            if end_utc and ts_utc > end_utc: continue
            filtered_messages.append(m)
        return filtered_messages

    def filter_liked_by(self, user_id: str) -> List[Message]:
        """Returns messages liked by a specific user ID."""
        return [m for m in self.messages if user_id in m.likes]

    def filter_flagged(self, min_flags: int = 1) -> List[Message]:
        """Returns messages flagged at least `min_flags` times
