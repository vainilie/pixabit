# pixabit/models/message.py
# MARK: - MODULE DOCSTRING
"""Defines data classes for representing Habitica messages (Inbox & Group Chat)."""

# MARK: - IMPORTS
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.dates import convert_timestamp_to_utc


# KLASS: - Message
class Message:
    """Represents an individual message in Habitica (Inbox or Group Chat).

    Attributes:
        id: The unique ID of the message document (_id).
        unique_message_id: A shared UUID across conversation participants (often called 'uuid').
        text: The content of the message.
        timestamp: When the message was sent (UTC datetime).
        likes: Dictionary of user IDs who liked the message.
        flags: Dictionary of user IDs who flagged the message.
        flag_count: Number of times the message was flagged.
        sender_id: The UUID of the user who sent the message ('uuid' field in API).
        recipient_id: The UUID of the recipient (for PMs, 'ownerId' might indicate this).
        group_id: The ID of the group ('party', 'tavern', or guild UUID) for group messages.
        user: Display name of the sender.
        username: Username of the sender.
        user_styles: User's cosmetic styles at the time of sending.
        # Note: 'from' and 'to' are Python keywords, often avoided as attribute names.
        # API might use 'uuid' for sender ID in newer versions. Check API response.
    """

    # FUNC: - __init__
    def __init__(self, message_data: Dict[str, Any]):
        """Initializes a Message object from API data."""
        self.id: Optional[str] = message_data.get("_id") or message_data.get(
            "id"
        )  # Handle both _id and id
        # Habitica often uses 'uuid' for the *sender's* user ID in message objects
        self.sender_id: Optional[str] = message_data.get("uuid")
        self.unique_message_id: Optional[str] = message_data.get(
            "sent"
        )  # Sometimes used as conversation key? Check API. Often also message_data.get("id") itself for PMs.
        self.text: str = message_data.get("text", "")
        self.timestamp: Optional[datetime] = convert_timestamp_to_utc(
            message_data.get("timestamp")
        )
        self.likes: Dict[str, bool] = message_data.get("likes", {})
        self.flags: Dict[str, bool] = message_data.get("flags", {})
        self.flag_count: int = message_data.get("flagCount", 0)
        # Recipient might be derived contextually for PMs, or in 'ownerId' field?
        self.recipient_id: Optional[str] = message_data.get(
            "ownerId"
        )  # Check if this holds recipient ID for PMs
        self.group_id: Optional[str] = message_data.get("groupId")  # For group messages
        self.user: Optional[str] = message_data.get("user")  # Sender display name
        self.username: Optional[str] = message_data.get("username")  # Sender username
        self.user_styles: Optional[Dict[str, Any]] = message_data.get("userStyles")

        # Unread status might be specific to the *fetching user's* inbox view, not on the message itself typically
        self.unread: Optional[bool] = message_data.get(
            "unread"
        )  # Usually not part of the core message object

    # FUNC: - __repr__
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        sender = self.username or self.sender_id or "Unknown"
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M") if self.timestamp else "No Timestamp"
        return f"Message(id={self.id}, from='{sender}', time='{ts}', text='{self.text[:30]}...')"


# KLASS: - Inbox
class Inbox:
    """Represents the user's private message inbox.

    Attributes:
        messages: A list of Message objects representing the conversations.
    """

    # FUNC: - __init__
    def __init__(self, messages_data: List[Dict[str, Any]]):
        """Initializes an Inbox object from a list of message API data."""
        self.messages: List[Message] = [
            Message(msg) for msg in messages_data if isinstance(msg, dict)
        ]

    # FUNC: - get_conversations
    def get_conversations(self) -> Dict[str, List[Message]]:
        """Groups messages by conversation (based on other participant)."""
        # This requires identifying the 'other' participant in a PM, which isn't
        # straightforward from just the message object. Usually requires user ID context.
        # Placeholder implementation. A real implementation needs more context.
        convos: Dict[str, List[Message]] = {}
        my_user_id = "YOUR_USER_ID"  # Need to get this from context (e.g., api_client)
        for msg in self.messages:
            # Determine other participant (needs refinement based on API structure)
            other_id = msg.recipient_id if msg.sender_id == my_user_id else msg.sender_id
            if other_id:
                convos.setdefault(other_id, []).append(msg)
        # Sort messages within each conversation by timestamp
        for convo_id in convos:
            convos[convo_id].sort(
                key=lambda m: m.timestamp or datetime.min.replace(tzinfo=timezone.utc)
            )
        return convos

    # Add methods like get_unread_count, get_messages_from_user etc. if needed

    # FUNC: - __repr__
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"Inbox(num_messages={len(self.messages)})"


# KLASS: - GroupChat
class GroupChat:
    """Represents the chat messages for a specific group.

    Attributes:
        group_id: The ID of the group this chat belongs to.
        messages: A list of Message objects in the chat.
    """

    # FUNC: - __init__
    def __init__(self, group_id: str, messages_data: List[Dict[str, Any]]):
        """Initializes a GroupChat object.

        Args:
            group_id: The ID ('party', 'tavern', or guild UUID) of the group.
            messages_data: A list of message dictionaries from the API.
        """
        self.group_id = group_id
        self.messages: List[Message] = [
            Message(msg) for msg in messages_data if isinstance(msg, dict)
        ]
        # Optionally sort messages by timestamp here
        self.messages.sort(key=lambda m: m.timestamp or datetime.min.replace(tzinfo=timezone.utc))

    # Add methods like get_messages_from_user etc. if needed
    # FUNC: -get messages from user
    def get_messages_from_user(self, user_id: str) -> List[Message]:
        """Obtiene todos los mensajes de un usuario específico en el chat del grupo

        Args:
            user_id: El ID del usuario del remitente

        Returns:
            Una lista de objetos Message enviados por el usuario
        """
        return [message for message in self.messages if message.sender_id == user_id]

    # FUNC: mark as read
    def mark_message_as_read(self, message_id: str) -> None:
        """Marca un mensaje como leído.

        Args:
            message_id: El ID del mensaje a marcar como leído.
        """
        for message in self.messages:
            if message.id == message_id:
                message.unread = False
                return  # Importante: Salir después de marcar el mensaje como leído

    # FUNC: - __repr__
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"GroupChat(group_id='{self.group_id}', num_messages={len(self.messages)})"
