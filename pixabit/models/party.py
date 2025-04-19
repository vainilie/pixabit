# pixabit/models/party.py

# SECTION: MODULE DOCSTRING
"""Defines data model classes for representing a Habitica Party and related quest info.

Includes:
- `QuestProgress`: Holds progress data for an active quest (HP, collection).
- `QuestInfo`: Represents metadata about the party's current quest.
- `Party`: Represents the main Party group object, potentially including quest info.
"""

# SECTION: IMPORTS
import logging
from typing import Any, Dict, List, Optional  # Keep Dict/List for clarity

import emoji_data_python
from rich.logging import RichHandler
from textual import log

from pixabit.utils.display import console

FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)])

# Local Imports (assuming models are siblings or configured in path)
try:
    # MessageList might be used to store chat later
    from pixabit.models.message import MessageList
except ImportError:
    # Fallback placeholder if imports fail
    log.info("Warning: Using placeholder MessageList in party.py.")
    MessageList = list  # type: ignore

# SECTION: DATA CLASSES


# KLASS: QuestProgress
class QuestProgress:
    """Represents the progress within an active party quest."""

    # FUNC: __init__
    def __init__(self, progress_data: Optional[Dict[str, Any]]):
        """Initializes QuestProgress from the 'progress' sub-object of a quest.

        Args:
            progress_data: The dictionary containing quest progress details, or None.
        """
        data = progress_data if isinstance(progress_data, dict) else {}

        # Boss quest damage dealt by party (positive values) or positive habit progress
        self.up: float = float(data.get("up", 0.0))
        # Damage taken by party (negative values) or negative habit progress
        self.down: float = float(data.get("down", 0.0))
        # For collection quests: target item counts {item_key: count_needed}
        self.collect_goal: Dict[str, int] = data.get("collect", {})
        # Number of items collected so far for collection quests
        self.items_collected: int = int(data.get("collectedItems", 0))
        # Boss HP (if applicable, often separate from 'up')
        self.hp: Optional[float] = data.get("hp")  # Can be null or number
        # Boss Rage (if applicable, often separate from 'down')
        self.rage: Optional[float] = data.get("rage")  # Can be null or number

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
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
            parts.append(f"collect#={self.items_collected}/{sum(self.collect_goal.values())}")
        return f"QuestProgress({', '.join(parts)})"


# KLASS: QuestInfo
class QuestInfo:
    """Represents the information about the party's current quest."""

    # FUNC: __init__
    def __init__(self, quest_data: Optional[Dict[str, Any]]):
        """Initializes QuestInfo from the 'quest' object within party data.

        Args:
            quest_data: The dictionary containing quest details, or None.
        """
        data = quest_data if isinstance(quest_data, dict) else {}

        self.key: Optional[str] = data.get("key")  # The unique key for the quest (e.g., 'basilisk')
        self.active: bool = data.get("active", False)  # Explicit active flag
        self.rsvp_needed: bool = data.get("RSVPNeeded", False)  # Does party leader need to accept invites?
        # Quest 'completed' field might be a status string or completion date string (or null)
        self.completed_status: Optional[str] = data.get("completed")
        # Leader might be here if it's a pending invite
        self.leader_id: Optional[str] = data.get("leader")
        # Member RSVP status might be in 'members' dict {userId: bool}
        self.members_rsvp: Optional[Dict[str, bool]] = data.get("members")
        # Additional quest-specific data might be in 'extra'
        self.extra_data: Optional[Dict[str, Any]] = data.get("extra")

        # Nested progress object
        self.progress: QuestProgress = QuestProgress(data.get("progress"))

        # Calculate active status more robustly
        self.is_active: bool = self.active and not self.completed_status and bool(self.key)

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        status = "Active" if self.is_active else ("Completed" if self.completed_status else "Inactive")
        key_str = f"key='{self.key}'" if self.key else "No Key"
        return f"QuestInfo({key_str}, status={status}, progress={self.progress})"


# KLASS: Party
class Party:
    """Represents a Habitica Party group object."""

    # FUNC: __init__
    def __init__(self, party_data: Dict[str, Any]):
        """Initializes a Party object from API data dictionary.

        Args:
            party_data: A dictionary containing the raw party data from the API.

        Raises:
            TypeError: If party_data is not a dictionary.
        """
        if not isinstance(party_data, dict):
            raise TypeError("party_data must be a dictionary.")

        # Core Party Info
        self.id: Optional[str] = party_data.get("id") or party_data.get("_id")
        _name = party_data.get("name", "Unnamed Party")
        self.name: str = emoji_data_python.replace_colons(_name) if _name else "Unnamed Party"
        _desc = party_data.get("description")
        self.description: Optional[str] = emoji_data_python.replace_colons(_desc) if _desc else None
        _summary = party_data.get("summary")
        self.summary: Optional[str] = emoji_data_python.replace_colons(_summary) if _summary else None

        # Leader Info (usually just ID string in party object)
        leader_info = party_data.get("leader")  # Can be string or object? Assume string usually.
        self.leader_id: Optional[str] = leader_info if isinstance(leader_info, str) else None
        # Could fetch leader details separately if needed

        # Member Sorting Info
        self.member_sort_order: Optional[str] = party_data.get("order")  # e.g., "stats.lvl"
        # API might return string "true"/"false" or boolean - normalize
        raw_order_asc = party_data.get("orderAscending")
        self.member_sort_ascending: Optional[bool] = None
        if isinstance(raw_order_asc, bool):
            self.member_sort_ascending = raw_order_asc
        elif isinstance(raw_order_asc, str):
            self.member_sort_ascending = raw_order_asc.lower() == "true"

        # Quest Info (using nested QuestInfo class)
        self.quest: QuestInfo = QuestInfo(party_data.get("quest"))  # Handles None input

        # --- Placeholders for related data (populate separately if needed) ---
        # Chat messages (assuming fetched/added later via set_chat)
        self.chat: Optional[MessageList] = None  # type: ignore
        # Party members (assuming fetched/added later - define a Member class?)
        self.members: List[Any] = []  # Placeholder type

    # FUNC: set_chat
    def set_chat(self, message_list: MessageList) -> None:  # type: ignore
        """Assigns a MessageList containing the party's chat messages.

        Args:
            message_list: An instance of the MessageList class.
        """
        if isinstance(message_list, MessageList):
            self.chat = message_list
        else:
            log.info("Warning: Invalid type provided to Party.set_chat. Expected MessageList.")

    # Add methods to add/manage members if you fetch member details

    # FUNC: __repr__
    def __repr__(self) -> str:
        """Provides a developer-friendly string representation."""
        quest_str = f", quest='{self.quest.key}'" if self.quest and self.quest.key else ", quest=None"
        active_str = " (Active)" if self.quest and self.quest.is_active else ""
        chat_len = len(self.chat.messages) if self.chat and hasattr(self.chat, "messages") else 0
        chat_str = f", chat={chat_len} msgs" if chat_len > 0 else ", chat=N/A"
        name_preview = self.name[:30] + ("..." if len(self.name) > 30 else "")
        return f"Party(id='{self.id}', name='{name_preview}'{quest_str}{active_str}{chat_str})"
