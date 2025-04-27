# # pixabit/models/__init__.py

# ─── Title ────────────────────────────────────────────────────────────────────
#             Pixabit Data Models Package Index
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Exports the core Pydantic data models used to represent Habitica entities
within the Pixabit TUI application.

Provides structured representations for User, Tasks (Habits, Dailies, Todos, Rewards),
Tags, Challenges, Parties, Messages, and static Game Content items.
"""

# SECTION: EXPORTS

# --- User ---
# --- Challenge ---
from .challenge import Challenge, ChallengeGroup, ChallengeLeader, ChallengeList

# --- Game Content (Static) ---
from .game_content import (
    GameContent,  # The container for processed static data (usually via manager)
    Gear,  # Primary item models
    Quest,
    QuestBoss,  # Key nested models
    QuestCollect,
    QuestDrop,
    Spell,
)

# --- Message ---
from .message import Message, MessageList, MessageSenderStyles

# --- Party ---
from .party import Party, PartyMember, QuestInfo, QuestProgress  # Export main Party & key nested parts

# --- Tag ---
from .tag import Tag, TagList  # The simple/default Tag models & list container

# --- Task ---
from .task import (
    ChallengeLinkData,  # Nested challenge link model
    ChecklistItem,  # Nested item model
    Daily,
    Habit,
    Reward,
    Task,  # Base Task (less used directly)
    TaskList,  # The manager/container class
    Todo,
)
from .user import (
    Buffs,  # Less common direct access needed
    EquippedGear,  # Useful sub-model
    Training,
    User,
    UserProfile,  # Often accessed directly
    UserStats,  # Often accessed directly
)

# --- Explicit Export List (__all__) ---
# Controls `from pixabit.models import *` behaviour
__all__ = [
    # User Models
    "User",
    "UserProfile",
    "UserStats",
    "EquippedGear",
    "Buffs",
    "Training",
    # Task Models & Container
    "Task",
    "Habit",
    "Daily",
    "Todo",
    "Reward",
    "TaskList",
    "ChecklistItem",
    "ChallengeLinkData",
    # Tag Models & Container (Simple)
    "Tag",
    "TagList",
    # Challenge Models & Container
    "Challenge",
    "ChallengeList",
    "ChallengeGroup",
    "ChallengeLeader",
    # Party Models
    "Party",
    "PartyMember",  # Exporting basic member stub
    "QuestInfo",
    "QuestProgress",
    # Message Models & Container
    "Message",
    "MessageList",
    "MessageSenderStyles",
    # Static Game Content Models
    "GameContent",  # Processed content container
    "Gear",
    "Quest",
    "Spell",
    "QuestBoss",
    "QuestDrop",
    "QuestCollect",
    # Add other static types like PetInfo, MountInfo here if modeled and exported
]

# Note: TagFactory models (ParentTag, SubTag) and the factory-specific TagList
# are NOT exported here by default. They should be imported explicitly via:
# `from pixabit.models.tag_factory import TagFactory, TagList as AdvancedTagList`

# Note: Manager classes (DataManager, StaticContentManager) are typically
# part of a 'services' or 'managers' package, not exported from 'models'.

# ──────────────────────────────────────────────────────────────────────────────
