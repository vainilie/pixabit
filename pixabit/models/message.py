# pixabit/models/message.py

# ─── Model ────────────────────────────────────────────────────────────────────
#            Habitica Message Models (Inbox & Group Chat)
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Defines Pydantic models for Habitica messages (Inbox/PM and Group Chat).

Includes:
- `MessageSenderStyles`: Represents nested sender style information.
- `Message`: Represents an individual message entity with improved parsing.
- `MessageList`: A Pydantic `BaseModel` container class to manage a collection
  of Message objects, providing context-aware processing (like conversation IDs),
  sorting, and filtering.
"""

# SECTION: IMPORTS
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterator  # Use standard lowercase etc.

# External Libs
import emoji_data_python
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FieldValidationInfo,
    ValidationError,
    ValidationInfo,  # For context access
    field_validator,
    model_validator,
)

# Local Imports
try:
    from pixabit.config import USER_ID  # Import the actual user ID from config
    from pixabit.helpers._logger import log
    from pixabit.helpers.DateTimeHandler import DateTimeHandler
except ImportError:
    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    USER_ID = "fallback_user_id_from_config"  # Fallback if config not found

    class DateTimeHandler:
        def __init__(self, timestamp: Any):
            self._ts = timestamp

        @property
        def utc_datetime(self) -> datetime | None:
            try:
                return datetime.fromisoformat(str(self._ts).replace("Z", "+00:00"))
            except:
                return None

    log.warning("message.py: Could not import config/helpers. Using fallbacks.")


# SECTION: HELPER FUNCTIONS


# FUNC: determine_conversation_id
def determine_conversation_id(message: Message, current_user_id: str | None) -> str | None:
    """Calculates conversation ID based on processed Message object and current user context.

    Args:
        message: The validated Message object.
        current_user_id: The ID of the user viewing the messages.

    Returns:
        A string identifying the conversation (group ID, other user's ID, 'system',
        or a special ID for messages to self/unknown), or None if indeterminate.
    """
    # 1. Group Chats are simplest
    if message.group_id:
        return message.group_id

    # 2. System messages
    if message.sender_id == "system":
        return "system"  # Dedicated ID for system messages

    # 3. Private Messages - requires current_user_id context
    if not current_user_id:
        # Cannot determine PM partner without knowing 'me'
        log.debug(f"Cannot determine PM conversation ID for msg {message.id}: current_user_id missing.")
        # Return None or a placeholder? None seems cleaner for grouping logic.
        return None  # Or perhaps f"unknown_context_{message.id[:6]}"

    sender = message.sender_id
    recipient = message.recipient_id  # User ID of the inbox owner (present for inbox msgs)

    # Logic refinement based on message origin (inbox vs. sent)
    if message.sent_by_me:
        # Message was sent BY current_user
        # Check who it was sent TO. Often recipient_id is *not* populated for sent PMs in raw data.
        # The 'ownerId' (recipient_id) usually points to the *inbox owner*.
        # We need to rely on OTHER information if available (e.g., endpoint context or `userV` field)
        # For now, assume recipient_id IS the *other* person if populated and not 'me'.
        if recipient and recipient != current_user_id:
            return recipient  # Conversation with the recipient
        else:
            # Recipient is missing or is myself on a sent message. Cannot determine partner.
            # log.debug(f"Cannot determine conversation partner for SENT message {message.id}. Sender: {sender}, Recipient: {recipient}")
            # Need a way to distinguish 'message sent to self' from 'cannot determine recipient'.
            # If recipient == current_user_id -> it's a message to self.
            if recipient == current_user_id:
                return f"self:{current_user_id}"  # Special ID for messages to self
            else:
                return f"unknown_recipient:{message.id[:8]}"  # Placeholder for unknown

    else:
        # Message was received BY current_user (sent_by_me is False)
        # The conversation partner is the sender (unless it's system).
        if sender and sender != current_user_id:
            return sender  # Conversation is with the sender
        elif sender == current_user_id:
            # This means sender=me, but sent_by_me=False? Inconsistent data?
            # Could happen if viewing own messages in someone else's shared party/guild view?
            # Or if `sent_by_me` logic failed. Assume it's a message *I* sent.
            log.warning(
                f"Inconsistent state for message {message.id}: Sender is current user, but sent_by_me is False. Treating as 'sent to self' for conversation ID."
            )
            return f"self:{current_user_id}"
        else:
            # Sender is missing or invalid, and not sent by me.
            log.debug(f"Could not determine conversation partner for RECEIVED message {message.id}. Sender: {sender}, Recipient: {recipient}")
            return f"unknown_sender:{message.id[:8]}"  # Placeholder for unknown


# SECTION: PYDANTIC SUB-MODELS


# KLASS: MessageSenderStyles
class MessageSenderStyles(BaseModel):
    """Represents nested user style information potentially in message data."""

    # Allow other fields related to styles but ignore them for now
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    # Explicitly model fields we might care about (like class)
    klass: str | None = Field(None, alias="class", description="Sender's class ('rogue', 'wizard', etc.)")

    @model_validator(mode="before")
    @classmethod
    def extract_nested_class(cls, data: Any) -> dict[str, Any]:
        """Extracts 'class' from a nested 'stats' dictionary if present."""
        if not isinstance(data, dict):
            return data if isinstance(data, dict) else {}
        values = data.copy()
        # If 'class' is already top-level, use it
        if "class" not in values:
            stats_data = data.get("stats")
            if isinstance(stats_data, dict):
                # Map stats.class -> class (for alias 'klass')
                values["class"] = stats_data.get("class")
        return values


# SECTION: MAIN MESSAGE MODEL


# KLASS: Message
class Message(BaseModel):
    """Represents an individual message in Habitica (Inbox or Group Chat)."""

    # Allow fields like userV, _v which we ignore
    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True)

    # --- Core IDs & Context ---
    id: str = Field(..., description="Unique message document ID (mapped from _id).")
    # Sender ID ('uuid'): 'system' for system messages, user UUID otherwise
    sender_id: str | None = Field(None, alias="uuid", description="UUID of the sender ('system' for system messages).")
    # Group ID ('groupId'): 'party', guild ID, 'tavern', etc. Null for PMs.
    group_id: str | None = Field(None, alias="groupId", description="ID of the group chat context, if any.")
    # Recipient ID ('ownerId'): Primarily for inbox messages, user ID of the inbox owner.
    # Crucial for determining conversation partner in PMs.
    recipient_id: str | None = Field(None, alias="ownerId", description="User ID of the inbox owner (recipient context).")

    # --- Sender Info (Partially from direct fields, partially nested) ---
    # 'user' field often holds display name in chat messages
    sender_display_name: str | None = Field(None, alias="user", description="Sender's display name (parsed).")
    # 'username' field often holds login name
    sender_username: str | None = Field(None, alias="username", description="Sender's login name.")
    # Nested style information (optional)
    sender_styles: MessageSenderStyles | None = Field(None, alias="userStyles", description="Sender's style info.")

    # --- Content & Timestamp ---
    text: str = Field("", description="Formatted message text (parsed).")
    # Raw markdown source (less common in API now, but can be useful if present)
    unformatted_text: str | None = Field(None, alias="unformattedText", description="Raw markdown source text (parsed).")
    timestamp: datetime | None = Field(None, description="Timestamp message sent/received (UTC).")

    # --- Engagement & Flags ---
    # Store likes/flags as dict {user_id: bool/timestamp} - Use bool for simplicity
    # Default factory ensures these are initialized as empty dicts
    likes: dict[str, bool] = Field(default_factory=dict, description="Dictionary of user IDs who liked the message.")
    flags: dict[str, bool] = Field(default_factory=dict, description="Dictionary of user IDs who flagged the message.")
    flag_count: int = Field(0, alias="flagCount", description="Reported count of flags.")

    # --- System Message Info ---
    # 'info' field contains structured data for system messages (spell casts, quest progress, etc.)
    info: dict[str, Any] | None = Field(None, description="Structured data for system messages.")

    # --- Fields Calculated during MessageList Processing ---
    # These depend on context (current_user_id)
    sent_by_me: bool | None = Field(
        None,
        exclude=True,  # Exclude from model dump as it's context-dependent runtime info
        description="Derived: True if message was sent by the current user context.",
    )
    conversation_id: str | None = Field(
        None,
        exclude=True,  # Exclude from dump
        description="Derived: Grouping ID (group_id or other user's ID in PMs, 'system', etc.).",
    )
    is_pm: bool | None = Field(
        None,
        exclude=True,  # Exclude from dump
        description="Derived: True if message is likely a Private Message.",
    )

    # --- Validators ---

    @model_validator(mode="before")
    @classmethod
    def prepare_data(cls, data: Any) -> dict[str, Any]:
        """Map '_id' to 'id' before other validation."""
        if not isinstance(data, dict):
            # Let Pydantic raise type error
            return data

        values = data.copy()
        # Map _id if needed
        if "_id" in values and "id" not in values:
            values["id"] = values["_id"]

        # Default sender display name from username if needed?
        # This is tricky as 'user' field often contains the display name.
        # if not values.get('user') and values.get('username'):
        #      values['user'] = values['username'] # Risky, 'user' is primary

        return values

    @field_validator("id", mode="after")
    @classmethod
    def check_id(cls, v: str) -> str:
        """Ensure ID is a non-empty string after potential mapping."""
        if not v or not isinstance(v, str):
            raise ValueError("Message ID (_id) is required and must be a string.")
        return v

    # Consolidate text parsing for all relevant fields
    @field_validator("text", "unformatted_text", "sender_display_name", "sender_username", mode="before")
    @classmethod
    def parse_text_fields(cls, value: Any, info: FieldValidationInfo) -> str | None:
        """Parses text fields: replaces emoji, strips whitespace. Handles None for optional."""
        if isinstance(value, str):
            parsed = emoji_data_python.replace_colons(value).strip()
            # Defaulting behavior handled by Field(default=...)
            return parsed if parsed else None  # Return None if strip results in empty for optional fields
        # Allow None for optional fields like unformatted_text, sender_username, sender_display_name
        return None

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp_utc(cls, value: Any) -> datetime | None:
        """Parses timestamp using DateTimeHandler."""
        handler = DateTimeHandler(timestamp=value)
        if value is not None and handler.utc_datetime is None:
            log.warning(f"Could not parse timestamp for message field: {value!r}")
        return handler.utc_datetime

    @field_validator("flag_count", mode="before")
    @classmethod
    def ensure_int(cls, value: Any) -> int:
        """Ensures flag_count is an integer, defaulting to 0."""
        if value is None:
            return 0
        try:
            return int(float(value))  # Handle potential float input
        except (ValueError, TypeError):
            log.debug(f"Could not parse message flag_count: {value!r}. Using 0.")
            return 0

    # --- Computed Properties / Methods ---

    @property
    def is_system_message(self) -> bool:
        """Checks if this is likely a system message."""
        # Check sender_id explicitly or presence of 'info' field
        return self.sender_id == "system" or bool(self.info)

    @property
    def sender_class(self) -> str | None:
        """Extracts sender's class from sender_styles, if available."""
        return self.sender_styles.klass if self.sender_styles else None

    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        sender = "System" if self.is_system_message else (self.sender_username or self.sender_id or "Unknown")
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M") if self.timestamp else "NoTime"
        # Show derived conversation_id if available
        conv = f" (ConvID: {self.conversation_id})" if self.conversation_id else ""
        pm_flag = " (PM)" if self.is_pm else ""
        sent_flag = " (Sent)" if self.sent_by_me else (" (Rcvd)" if self.sent_by_me is False else "")
        text_preview = self.text[:30].replace("\n", " ") + ("..." if len(self.text) > 30 else "")
        return f"Message(id='{self.id}', from='{sender}', time='{ts}{sent_flag}{pm_flag}{conv}', text='{text_preview}')"


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: MESSAGE LIST CONTAINER


# KLASS: MessageList
class MessageList(BaseModel):
    """BaseModel container for managing Message objects.

    Handles validation, context-dependent field calculation (sent_by_me,
    conversation_id, is_pm), sorting, and provides filtering methods.
    """

    model_config = ConfigDict(
        extra="forbid",  # No unexpected fields
        arbitrary_types_allowed=False,
    )

    # The main data field: list of validated Message objects
    messages: list[Message] = Field(default_factory=list, description="Validated list of Message objects.")

    # Add context field directly? No, use ValidationInfo during validation.

    @model_validator(mode="before")
    @classmethod
    def process_raw_messages(cls, data: Any, info: ValidationInfo) -> dict[str, Any]:
        """Validates raw message data, calculates derived fields using context, sorts, and returns the structured data for the MessageList model.

        Expects 'current_user_id' in validation context (`info.context`).
        Expects input `data` to be the raw list of message dicts.
        """
        # --- Get Context ---
        # Fetch current_user_id from the validation context passed during instantiation.
        # Use the globally imported USER_ID as a fallback if context is missing (e.g., during tests).
        current_user_id: str | None = None
        if info.context and isinstance(info.context, dict):
            current_user_id = info.context.get("current_user_id")

        # If still None, maybe use the global USER_ID (consider implications)
        if current_user_id is None:
            # Use the one imported from config as a last resort, might not be right context always
            current_user_id = USER_ID  # Requires USER_ID to be imported from pixabit.config
            if not current_user_id or current_user_id == "fallback_user_id_from_config":  # Check if it's a real ID
                log.warning("'current_user_id' not found in context or config. Derived message fields (sent_by_me, conversation_id) may be inaccurate.")
                current_user_id = None  # Explicitly set to None if unusable

        # --- Process Input ---
        # This validator receives the *entire* input intended for the model.
        # If called like `MessageList.model_validate(raw_list, context=...)`, data is raw_list.
        # If called like `MessageList.model_validate({"messages": raw_list}, context=...)`, data is the dict.
        raw_message_list: list[Any] | None = None
        if isinstance(data, list):
            raw_message_list = data
        elif isinstance(data, dict):
            # Assume the list is under the 'messages' key if input is dict
            raw_message_list = data.get("messages")
            if not isinstance(raw_message_list, list):
                raise ValidationError.from_exception_data(
                    title=cls.__name__,
                    line_errors=[{"loc": ("messages",), "input": data.get("messages"), "type": "list_expected"}],
                )
        else:
            raise ValidationError.from_exception_data(
                title=cls.__name__,
                line_errors=[{"loc": (), "input": data, "type": "list_or_dict_expected"}],
            )

        # --- Validate, Enrich, and Collect Messages ---
        processed_messages: list[Message] = []
        validation_errors = []

        for index, item in enumerate(raw_message_list):
            if not isinstance(item, dict):
                log.warning(f"Skipping non-dict item at index {index} in message list.")
                validation_errors.append(f"Item at index {index} is not a dictionary.")
                continue

            try:
                # 1. Validate raw dict into Message model
                msg = Message.model_validate(item)

                # 2. Calculate context-dependent fields if user_id is known
                if current_user_id:
                    # Determine if sent by current user
                    # Explicit check against sender ID is primary.
                    # The old 'sent' flag from raw data is less reliable.
                    msg.sent_by_me = msg.sender_id == current_user_id
                    # Check if recipient is me when sent by someone else
                    # sent_to_me = not msg.sent_by_me and msg.recipient_id == current_user_id

                    # Determine conversation ID using the helper function
                    msg.conversation_id = determine_conversation_id(msg, current_user_id)

                    # Determine if PM (no group_id and not system message)
                    msg.is_pm = not msg.group_id and not msg.is_system_message
                else:
                    # Cannot reliably determine these without user context
                    msg.sent_by_me = None
                    msg.conversation_id = msg.group_id or ("system" if msg.is_system_message else None)  # Fallback
                    msg.is_pm = not msg.group_id and not msg.is_system_message  # Can still guess PM structure

                processed_messages.append(msg)

            except ValidationError as e:
                item_id = item.get("id", item.get("_id", f"index_{index}"))
                log.error(f"Validation failed for message ID '{item_id}': {e}")
                # Collect detailed errors if needed
                validation_errors.extend(e.errors(include_input=False))  # Pydantic v2 way
            except Exception as e:
                item_id = item.get("id", item.get("_id", f"index_{index}"))
                log.exception(f"Unexpected error processing message ID '{item_id}': {e}")
                validation_errors.append(f"Unexpected error processing message {item_id}")

        if validation_errors:
            # Decide how to handle errors: log, raise summary error, or continue
            # For robustness, log and continue is often preferred for lists.
            log.warning(f"Encountered {len(validation_errors)} errors during message list processing.")
            # Example: raise ValidationError.from_exception_data(...) if strictness needed

        # 3. Sort messages by timestamp (most recent last)
        # Use a safe default time for messages lacking a timestamp
        default_time = datetime.min.replace(tzinfo=timezone.utc)
        processed_messages.sort(key=lambda m: m.timestamp or default_time)
        log.debug(f"Processed and sorted {len(processed_messages)} messages.")

        # --- Return Structured Data for Model ---
        # Pydantic expects the validator to return a dictionary matching the model fields
        return {"messages": processed_messages}

    # --- Access and Filtering Methods ---
    # Operate on the validated `self.messages` list

    def __len__(self) -> int:
        return len(self.messages)

    def __iter__(self) -> Iterator[Message]:
        return iter(self.messages)

    def __getitem__(self, index: int | slice) -> Message | list[Message]:
        if isinstance(index, int):
            if not 0 <= index < len(self.messages):
                raise IndexError("Message index out of range")
        # Slicing works inherently
        return self.messages[index]

    def get_by_id(self, message_id: str) -> Message | None:
        """Finds a message by its unique ID."""
        return next((m for m in self.messages if m.id == message_id), None)

    def filter_by_sender(self, sender_id_or_name: str, case_sensitive: bool = False) -> MessageList:
        """Returns messages sent by a specific user ID or username. Returns new MessageList."""
        if not case_sensitive:
            sender_id_or_name_lower = sender_id_or_name.lower()
            filtered = [
                m
                for m in self.messages
                if (m.sender_id and m.sender_id.lower() == sender_id_or_name_lower) or (m.sender_username and m.sender_username.lower() == sender_id_or_name_lower)
            ]
        else:
            filtered = [m for m in self.messages if m.sender_id == sender_id_or_name or m.sender_username == sender_id_or_name]
        return MessageList(messages=filtered)  # Return new instance

    def filter_by_conversation(self, conversation_id: str) -> MessageList:
        """Returns messages belonging to a specific conversation ID (group or PM partner). Returns new MessageList."""
        # Uses the derived conversation_id field
        filtered = [m for m in self.messages if m.conversation_id == conversation_id]
        return MessageList(messages=filtered)

    def filter_by_group(self, group_id: str) -> MessageList:
        """Returns messages belonging to a specific group ID. Returns new MessageList."""
        filtered = [m for m in self.messages if m.group_id == group_id]
        return MessageList(messages=filtered)

    def filter_private_messages(self) -> MessageList:
        """Returns likely Private Messages (uses derived 'is_pm' flag). Returns new MessageList."""
        filtered = [m for m in self.messages if m.is_pm]
        return MessageList(messages=filtered)

    def filter_system_messages(self) -> MessageList:
        """Returns only system messages. Returns new MessageList."""
        filtered = [m for m in self.messages if m.is_system_message]
        return MessageList(messages=filtered)

    def filter_non_system_messages(self) -> MessageList:
        """Returns only non-system messages. Returns new MessageList."""
        filtered = [m for m in self.messages if not m.is_system_message]
        return MessageList(messages=filtered)

    # ... Add other filter methods from original code, ensuring they return MessageList ...

    def get_conversations(self) -> dict[str, list[Message]]:
        """Groups messages by their calculated conversation ID.

        Returns:
            A dictionary where keys are conversation IDs and values are lists
            of Message objects belonging to that conversation, sorted chronologically.
            Conversations themselves are ordered by the timestamp of the latest message.
        """
        grouped = defaultdict(list)
        valid_conv_ids = set()
        for msg in self.messages:
            # Group only messages that have a valid conversation_id
            if msg.conversation_id:
                grouped[msg.conversation_id].append(msg)
                valid_conv_ids.add(msg.conversation_id)  # Keep track of keys added

        # Sort by most recent activity (using timestamp of the last message in each group)
        default_time = datetime.min.replace(tzinfo=timezone.utc)
        sorted_ids = sorted(
            valid_conv_ids,  # Sort only the keys we actually added to grouped dict
            key=lambda cid: grouped[cid][-1].timestamp or default_time,
            reverse=True,  # Most recent conversations first
        )

        # Return ordered dictionary
        return {cid: grouped[cid] for cid in sorted_ids}

    def __repr__(self) -> str:
        """Simple representation."""
        return f"MessageList(count={len(self.messages)})"


# ──────────────────────────────────────────────────────────────────────────────
