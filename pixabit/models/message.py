# pixabit/models/message.py

# SECTION: MODULE DOCSTRING
"""Defines data model classes for representing Habitica messages.

Includes:
- `Message`: Represents an individual message (Inbox or Group Chat).
- `MessageList`: A container class to manage a collection of Message objects,
  providing processing, sorting, filtering, and conversation grouping.
"""

# SECTION: IMPORTS
from collections import defaultdict
from datetime import datetime, timezone  # Ensure timezone is imported
from typing import Any, Dict, List, Optional  # Keep Dict/List for clarity

import emoji_data_python

# Local Imports (assuming utils is a sibling or configured in path)
try:
    from ..utils.dates import convert_timestamp_to_utc
except ImportError:
    # Fallback placeholder if imports fail
    print("Warning: Using placeholder convert_timestamp_to_utc in message.py.")

    def convert_timestamp_to_utc(ts: Any) -> Optional[datetime]:  # type: ignore  # noqa: D103
        if isinstance(
            ts, (int, float)
        ):  # Handle epoch milliseconds common in JS/APIs
            try:
                # Assume ms if large number, otherwise seconds
                ts_sec = ts / 1000.0 if ts > 1e11 else ts
                return datetime.fromtimestamp(ts_sec, tz=timezone.utc)
            except (ValueError, OSError, TypeError):
                return None
        elif isinstance(ts, str):
            try:
                from dateutil.parser import (
                    isoparse,
                )  # Local import for fallback

                dt = isoparse(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                return None
        return None


# SECTION: DATA CLASSES


# KLASS: Message
class Message:
    """Represents an individual message in Habitica (Inbox or Group Chat).

    Attributes are parsed from Habitica API message objects. Provides methods
    for calculating conversation context.
    """

    # FUNC: __init__
    def __init__(
        self,
        message_data: Dict[str, Any],
        current_user_id: Optional[str] = None,
    ):
        """Initializes a Message object from API data dictionary.

        Args:
            message_data: A dictionary containing the raw message data from the API.
            current_user_id: The UUID of the user whose perspective is used for
                             calculating PM conversation IDs.

        Raises:
            TypeError: If message_data is not a dictionary.
        """
        if not isinstance(message_data, dict):
            raise TypeError("message_data must be a dictionary.")

        # Core IDs
        self.id: Optional[str] = message_data.get("_id") or message_data.get(
            "id"
        )  # Message/Document ID
        # Sender's User ID (usually 'uuid', but check 'sent' flag too)
        self.sender_id: Optional[str] = message_data.get("uuid")

        # Sometimes 'uuid' is system ID like 'system'. If 'sent' is True, sender is current user.
        self.sent_by_me: Optional[bool] = None
        if self.sender_id == current_user_id:
            self.sent_by_me = True
        elif (
            message_data.get("sent") is True
        ):  # Habitica API might use 'sent: true' for outgoing PMs
            self.sent_by_me = True
            if (
                not self.sender_id
            ):  # If uuid wasn't set, assume current user sent it
                self.sender_id = current_user_id

        # Content and Timestamp
        _text = message_data.get("text", "")
        self.text: str = (
            emoji_data_python.replace_colons(_text) if _text else ""
        )
        _unformatted = message_data.get("unformattedText")  # Might not exist
        self.unformatted_text: Optional[str] = (
            emoji_data_python.replace_colons(_unformatted)
            if _unformatted
            else None
        )
        # Use our standardized converter
        self.timestamp: Optional[datetime] = convert_timestamp_to_utc(
            message_data.get("timestamp")
        )

        # Engagement
        self.likes: Dict[str, bool] = message_data.get(
            "likes", {}
        )  # Keys are user IDs
        self.flags: Dict[str, bool] = message_data.get(
            "flags", {}
        )  # Keys are user IDs
        self.flag_count: int = int(message_data.get("flagCount", 0))

        # Context: Group ID (e.g., 'party', 'tavern', specific guild ID)
        self.group_id: Optional[str] = message_data.get("groupId")

        # Sender Info (often included directly in message objects)
        _sender_disp = message_data.get("user")  # Display name
        self.sender_display_name: Optional[str] = (
            emoji_data_python.replace_colons(_sender_disp)
            if _sender_disp
            else None
        )
        self.sender_username: Optional[str] = message_data.get(
            "username"
        )  # Login name
        self.sender_styles: Optional[Dict[str, Any]] = message_data.get(
            "userStyles"
        )
        # Extract class from styles if available
        self.sender_class: Optional[str] = (
            self.sender_styles.get("stats", {}).get("class")
            if isinstance(self.sender_styles, dict)
            else None
        )

        # System Message Info (for spells, quests, system announcements etc.)
        self.info: Optional[Dict[str, Any]] = message_data.get("info")

        # --- Calculated/Derived Attributes ---
        self.is_system_message: bool = (
            bool(self.info) or self.sender_id == "system"
        )  # Check info dict or system sender ID

        # Conversation ID (Crucial for grouping PMs or identifying group chat)
        self.conversation_id: Optional[str] = self._determine_conversation_id(
            message_data, current_user_id
        )

        # Recipient ID (mainly relevant for PMs)
        # 'ownerId' might indicate the owner of the inbox copy (recipient), OR it might
        # sometimes be the sender for messages *sent* by the current user. Needs careful handling.
        self.recipient_id: Optional[str] = message_data.get("ownerId")

    # FUNC: _determine_conversation_id
    def _determine_conversation_id(
        self, message_data: Dict[str, Any], current_user_id: Optional[str]
    ) -> Optional[str]:
        """Calculates a consistent ID for the conversation this message belongs to.

        - For group messages, it's the group_id.
        - For PMs, it's typically the *other* user's ID.

        Args:
            message_data: The raw message dictionary.
            current_user_id: The ID of the user viewing the messages.

        Returns:
            The calculated conversation ID string, or None if indeterminate.
        """
        if self.group_id:
            # Group messages use the group ID
            return self.group_id

        # --- Private Message (PM) Logic ---
        # Requires knowing the current user to identify the 'other' participant.
        sender = self.sender_id
        recipient_guess = message_data.get(
            "recipient"
        )  # Check if 'recipient' field exists (less common)
        owner_id = message_data.get(
            "ownerId"
        )  # ID of the user whose inbox this message copy belongs to

        if not current_user_id:
            # Cannot reliably determine PM conversation without current user context
            # Maybe fallback to sender if available? Or return None? Let's return None.
            return None

        if self.sent_by_me:
            # Current user SENT this message. Conversation is with the recipient.
            # Recipient ID might be in 'ownerId' *if fetched from recipient's inbox*
            # OR recipient ID might be a top-level 'recipient' field (less common)
            # OR it might be the 'uuid' field in the *original message* if fetched via /conversations?
            # Best guess based on typical /inbox/messages: recipient is 'ownerId' on the *other user's copy*.
            # If fetched from *my* inbox, ownerId is me. We need recipient info somehow.
            # Let's assume 'recipient' or 'ownerId' (if different from me) holds the recipient.
            # This logic is fragile and endpoint-dependent.
            other_user = recipient_guess or (
                owner_id if owner_id != current_user_id else None
            )
            return other_user

        elif sender and sender != current_user_id:
            # Someone else sent this message TO the current user. Conversation is with the sender.
            return sender
        else:
            # Cannot determine sender or recipient clearly.
            # Maybe it's a system message misinterpreted?
            # Or sender ID is missing.
            return None  # Cannot determine conversation ID

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        sender_repr = (
            "System"
            if self.is_system_message
            else (self.sender_username or self.sender_id or "Unknown")
        )
        ts_repr = (
            self.timestamp.strftime("%Y-%m-%d %H:%M")
            if self.timestamp
            else "No Timestamp"
        )
        conv_repr = (
            f" (Conv: {self.conversation_id})" if self.conversation_id else ""
        )
        text_preview = self.text[:30].replace("\n", " ") + (
            "..." if len(self.text) > 30 else ""
        )
        return f"Message(id={self.id}, from='{sender_repr}', time='{ts_repr}{conv_repr}', text='{text_preview}')"


# KLASS: MessageList
class MessageList:
    """Container for managing a list of Message objects.

    Processes raw message data, sorts messages chronologically,
    and provides filtering and conversation grouping methods.
    """

    # FUNC: __init__
    def __init__(
        self,
        raw_message_list: List[Dict[str, Any]],
        current_user_id: Optional[str] = None,
    ):
        """Initializes the MessageList.

        Args:
            raw_message_list: List of dictionaries (raw message data from API).
            current_user_id: The UUID of the user viewing the messages. Needed
                             to correctly determine conversation IDs for PMs.
        """
        self.messages: List[Message] = []
        self.current_user_id = current_user_id
        self._process_list(raw_message_list)

    # FUNC: _process_list
    def _process_list(self, raw_message_list: List[Dict[str, Any]]) -> None:
        """Processes the raw list, creating Message instances and sorting them."""
        processed_messages: List[Message] = []
        if not isinstance(raw_message_list, list):
            print(
                f"Error: raw_message_list must be a list, got {type(raw_message_list)}. Cannot process messages."
            )
            self.messages = []
            return

        for raw_message in raw_message_list:
            if not isinstance(raw_message, dict):
                print(
                    f"Skipping invalid entry in raw_message_list: {raw_message}"
                )
                continue
            try:
                # Pass current_user_id for conversation ID calculation
                message_instance = Message(raw_message, self.current_user_id)
                if message_instance.id:  # Require an ID
                    processed_messages.append(message_instance)
                else:
                    print(
                        f"Skipping message data missing ID: {raw_message.get('text', 'N/A')[:30]}..."
                    )
            except Exception as e:
                print(
                    f"Error processing message data for ID {raw_message.get('id', 'N/A')}: {e}"
                )

        # Sort messages chronologically (oldest first)
        # Provide a default datetime for messages lacking a timestamp to avoid errors
        default_time = datetime.min.replace(tzinfo=timezone.utc)
        processed_messages.sort(key=lambda m: m.timestamp or default_time)

        self.messages = processed_messages

    # SECTION: Access and Filtering Methods

    # FUNC: __len__
    def __len__(self) -> int:
        """Returns the total number of messages."""
        return len(self.messages)

    # FUNC: __iter__
    def __iter__(self):
        """Allows iterating over the Message objects."""
        yield from self.messages

    # FUNC: __getitem__
    def __getitem__(self, index: int) -> Message:
        """Allows accessing messages by index."""
        if not isinstance(index, int):
            raise TypeError("Index must be an integer")
        if not 0 <= index < len(self.messages):
            raise IndexError("Message index out of range")
        return self.messages[index]

    # FUNC: get_by_id
    def get_by_id(self, message_id: str) -> Optional[Message]:
        """Finds a message by its unique ID.

        Args:
            message_id: The ID string of the message to find.

        Returns:
            The Message object if found, otherwise None.
        """
        for message in self.messages:
            if message.id == message_id:
                return message
        return None

    # FUNC: filter_by_sender
    def filter_by_sender(self, sender_id: str) -> List[Message]:
        """Returns messages sent by a specific user ID.

        Args:
            sender_id: The user ID of the sender to filter by.

        Returns:
            A list of matching Message objects.
        """
        return [m for m in self.messages if m.sender_id == sender_id]

    # FUNC: filter_by_conversation
    def filter_by_conversation(self, conversation_id: str) -> List[Message]:
        """Returns messages belonging to a specific conversation ID.

        For groups, this is the group_id. For PMs, this is usually the other user's ID.

        Args:
            conversation_id: The conversation ID string to filter by.

        Returns:
            A list of matching Message objects, sorted chronologically.
        """
        # Messages are already sorted, so filtering preserves order
        return [
            m for m in self.messages if m.conversation_id == conversation_id
        ]

    # FUNC: filter_by_group
    def filter_by_group(self, group_id: str) -> List[Message]:
        """Returns messages belonging to a specific group ID.

        Args:
            group_id: The group ID string ('party', 'tavern', guild UUID).

        Returns:
            A list of matching Message objects.
        """
        # This is essentially a subset of filter_by_conversation where conv ID == group ID
        return [m for m in self.messages if m.group_id == group_id]

    # FUNC: filter_private_messages
    def filter_private_messages(self) -> List[Message]:
        """Returns messages that are likely Private Messages (no group_id populated).

        Returns:
            A list of likely PMs.
        """
        return [m for m in self.messages if m.group_id is None]

    # FUNC: filter_system_messages
    def filter_system_messages(self, is_system: bool = True) -> List[Message]:
        """Returns system messages or non-system messages.

        Args:
            is_system: Set to True to filter for system messages, False for user messages (default: True).

        Returns:
            A list of matching Message objects.
        """
        return [m for m in self.messages if m.is_system_message is is_system]

    # FUNC: filter_by_text
    def filter_by_text(
        self, text_part: str, case_sensitive: bool = False
    ) -> List[Message]:
        """Filters messages containing a specific text substring.

        Args:
            text_part: The substring to search for in the message text.
            case_sensitive: Whether the search should be case-sensitive (default: False).

        Returns:
            A list of matching Message objects.
        """
        if not case_sensitive:
            text_part_lower = text_part.lower()
            return [
                m for m in self.messages if text_part_lower in m.text.lower()
            ]
        else:
            return [m for m in self.messages if text_part in m.text]

    # FUNC: filter_by_date_range
    def filter_by_date_range(
        self, start: Optional[datetime] = None, end: Optional[datetime] = None
    ) -> List[Message]:
        """Filters messages within a specific date/time range (UTC, inclusive).

        Naive datetime inputs for start/end are assumed to be UTC.

        Args:
            start: The start datetime. Messages on or after this time are included.
            end: The end datetime. Messages on or before this time are included.

        Returns:
            A list of matching Message objects.
        """
        # Ensure start/end are timezone-aware UTC for comparison
        start_utc: Optional[datetime] = None
        if start:
            start_utc = (
                start if start.tzinfo else start.replace(tzinfo=timezone.utc)
            )
        end_utc: Optional[datetime] = None
        if end:
            end_utc = end if end.tzinfo else end.replace(tzinfo=timezone.utc)

        filtered_messages: List[Message] = []
        for m in self.messages:
            if not m.timestamp:  # Skip messages without a timestamp
                continue
            ts_utc = m.timestamp  # Already UTC from processing

            # Apply filters
            if start_utc and ts_utc < start_utc:
                continue
            if end_utc and ts_utc > end_utc:
                continue
            filtered_messages.append(m)
        return filtered_messages

    # FUNC: filter_liked_by
    def filter_liked_by(self, user_id: str) -> List[Message]:
        """Returns messages liked by a specific user ID.

        Args:
            user_id: The user ID to check likes for.

        Returns:
            A list of matching Message objects.
        """
        # Check if the user_id key exists in the message's likes dictionary
        return [m for m in self.messages if user_id in m.likes]

    # FUNC: filter_flagged
    def filter_flagged(self, min_flags: int = 1) -> List[Message]:
        """Returns messages flagged at least `min_flags` times.

        Args:
            min_flags: The minimum number of flags required (default: 1).

        Returns:
            A list of matching Message objects.
        """
        if min_flags < 0:
            min_flags = 0
        return [m for m in self.messages if m.flag_count >= min_flags]

    # FUNC: get_conversations
    def get_conversations(self) -> Dict[str, List[Message]]:
        """Groups all messages by their calculated conversation ID.

        Returns:
            A dictionary where keys are conversation IDs (group IDs or other user IDs for PMs)
            and values are lists of Message objects belonging to that conversation,
            sorted chronologically (inherits sorting from the main list). Returns an empty
            dict if no messages have determinable conversation IDs.
        """
        # Use defaultdict for easier appending
        convos: Dict[str, List[Message]] = defaultdict(list)
        for msg in self.messages:
            if (
                msg.conversation_id
            ):  # Only include messages where conversation could be determined
                convos[msg.conversation_id].append(msg)
        # Convert back to standard dict for return type consistency
        return dict(convos)
