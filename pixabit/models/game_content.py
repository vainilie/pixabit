# pixabit/models/game_content.py

# ─── Model ────────────────────────────────────────────────────────────────────
#          Habitica Static Game Content Models & Manager
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MODULE DOCSTRING
"""Manages Habitica's static game content (spells, gear, quests, etc.).
Provides Pydantic models for content items and a manager class (`StaticContentManager`)
for fetching, caching (raw and processed), and accessing this data efficiently.
"""

# SECTION: IMPORTS
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Type  # Use standard lowercase etc.

import emoji_data_python

# External Libs
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,  # <<<---- Import computed_field
    field_validator,
    model_validator,
)

# Local Imports (assuming helpers and api are accessible)
try:
    from pixabit.api.client import HabiticaClient  # Needed to fetch content
    from pixabit.config import (
        DEFAULT_CACHE_DURATION_DAYS,  # Default expiry
        HABITICA_DATA_PATH,  # Main cache dir
    )
    from pixabit.helpers._json import load_json, load_pydantic_model, save_json, save_pydantic_model
    from pixabit.helpers._logger import log
    from pixabit.helpers.DateTimeHandler import DateTimeHandler
except ImportError:
    import logging

    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())
    # Fallbacks for isolated testing
    HABITICA_DATA_PATH = Path("./pixabit_cache")
    DEFAULT_CACHE_DURATION_DAYS = 7

    def load_json(p, **k):
        return None

    def save_json(d, p, **k):
        log.warning("Save skipped, helper missing.")

    def load_pydantic_model(m, p, **k):
        return None

    def save_pydantic_model(m, p, **k):
        log.warning("Save skipped, helper missing.")

    log.warning("game_content.py: Could not import helpers/api/config. Using fallbacks.")


# SECTION: CONSTANTS & CONFIG
CACHE_SUBDIR_STATIC = "static_content"
RAW_CONTENT_FILENAME = "habitica_content_raw.json"
PROCESSED_CONTENT_FILENAME = "habitica_content_processed.json"

# Ensure base path exists
HABITICA_DATA_PATH.mkdir(parents=True, exist_ok=True)
STATIC_CACHE_DIR = HABITICA_DATA_PATH / CACHE_SUBDIR_STATIC
STATIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# SECTION: PYDANTIC MODELS FOR CONTENT ITEMS


# --- Gear Models ---


class GearEvent(BaseModel):
    """Nested event info within gear items."""

    model_config = ConfigDict(extra="ignore")
    start_date: datetime | None = Field(None, alias="startDate")
    end_date: datetime | None = Field(None, alias="endDate")
    # season: str | None = None # Season can also be top-level

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_datetime_utc(cls, v: Any) -> datetime | None:
        handler = DateTimeHandler(timestamp=v)
        return handler.utc_datetime


# KLASS: Gear
class Gear(BaseModel):
    """Habitica gear model (parsed from content.gear.flat)."""

    model_config = ConfigDict(
        extra="ignore",  # Ignore unused fields like 'purchase', 'canDrop', etc.
        populate_by_name=True,  # Use aliases for API fields
        frozen=True,  # Gear definitions are static
    )

    key: str = Field(..., description="Unique identifier key (e.g., 'weapon_warrior_1').")
    text: str = Field(..., description="Display name of the gear.")
    notes: str = Field("", description="Description or flavor text.")
    value: float = Field(0, description="Purchase price in Gold (sometimes Gems for special).")  # Often int, use float for safety

    # Direct stat attributes (no nesting)
    strength: float = Field(0.0, alias="str")
    intelligence: float = Field(0.0, alias="int")
    constitution: float = Field(0.0, alias="con")
    perception: float = Field(0.0, alias="per")

    # Other attributes
    type: Literal["weapon", "armor", "head", "shield", "back", "body", "eyewear", "headAccessory"] | None = Field(None, description="Slot type.")
    special_class: str | None = Field(None, alias="specialClass", description="Class required to get bonus ('warrior', 'rogue', etc.), or 'special'.")

    two_handed: bool = Field(False, alias="twoHanded", description="Whether the weapon is two-handed.")
    gear_set: str | None = Field(
        None, alias="set", description="Gear set key ('base', 'golden', 'seasonal', etc.)."
    )  # Changed from sett -> set to avoid python keyword conflict

    # Event info (if applicable)
    event: GearEvent | None = None
    # Season directly on item (sometimes overrides event.season?)
    season: str | None = None

    # Index/Order within set? Seems less useful.
    # index: str | None = None

    @field_validator("text", "notes", mode="before")
    @classmethod
    def parse_text_emoji(cls, v: Any) -> str:
        if isinstance(v, str):
            return emoji_data_python.replace_colons(v).strip()
        return ""

    @field_validator("value", mode="before")
    @classmethod
    def parse_value(cls, v: Any) -> float:
        # Sometimes value is gold, sometimes gems - often represented * 4 for gold value
        # Treat as float for flexibility. Raw might be integer gold amount.
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0


# --- Spell Models ---
# KLASS: Spell
class Spell(BaseModel):
    """Habitica spell/skill model."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)

    key: str = Field(..., description="Unique skill key (e.g., 'fireball').")
    text: str = Field(..., description="Display name of the skill.")
    notes: str = Field("", description="In-game description/notes.")
    mana: float = Field(0.0, description="Mana cost.")
    target: Literal["self", "user", "party", "task", "certainUsers"] | str | None = Field(None, description="Target type (e.g., 'self', 'user', 'party', 'task').")
    klass: Literal["wizard", "healer", "warrior", "rogue", "special"] | None = Field(None, description="Associated class or 'special'.")
    lvl: int = Field(1, description="Level required to learn/use.")

    # Optional API fields
    immediate_use: bool = Field(False, alias="immediateUse")
    purchase_type: str | None = Field(None, alias="purchaseType")  # Typically null for class skills
    value: int | None = Field(0)  # Gold value if purchasable (usually 0 for skills)

    @field_validator("text", "notes", mode="before")
    @classmethod
    def parse_text_emoji(cls, v: Any) -> str:
        if isinstance(v, str):
            return emoji_data_python.replace_colons(v).strip()
        return ""

    @field_validator("mana", mode="before")
    @classmethod
    def ensure_float(cls, v: Any) -> float:
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("lvl", "value", mode="before")
    @classmethod
    def ensure_int(cls, v: Any) -> int:
        if v is None:
            return 0
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0


# --- Quest Models ---
class QuestBoss(BaseModel):
    """Model for boss properties within a quest."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)
    name: str = Field(..., description="Boss display name.")
    hp: float = Field(0.0, description="Initial HP of the boss.")
    strength: float = Field(0.0, alias="str", description="Boss strength (influences damage to party).")
    defense: float = Field(0.0, alias="def", description="Boss defense (influences damage dealt).")
    # rage: float? # Maybe add if needed

    @field_validator("hp", "strength", "defense", mode="before")
    @classmethod
    def ensure_float(cls, v: Any) -> float:
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0


class QuestDropItem(BaseModel):
    """Individual item details within quest drops."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    type: str = Field(...)  # e.g., "Food", "Eggs", "HatchingPotions"
    key: str = Field(...)  # Item key


class QuestDrop(BaseModel):
    """Model for drop properties within a quest."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    exp: int = Field(0, description="Experience points awarded.")
    gp: float = Field(0.0, description="Gold awarded.")  # Can be float? Let's assume so.
    # Can be a list of Item dicts or a dict mapping Item Type -> List of Item Keys
    # We'll simplify to a list of specific item drops for now
    items: list[QuestDropItem] = Field(default_factory=list)

    @field_validator("exp", mode="before")
    @classmethod
    def ensure_int(cls, v: Any) -> int:
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0

    @field_validator("gp", mode="before")
    @classmethod
    def ensure_float(cls, v: Any) -> float:
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    @model_validator(mode="before")
    @classmethod
    def structure_drop_items(cls, data: Any) -> dict[str, Any]:
        """Standardizes the 'items' field into a list of QuestDropItem."""
        if not isinstance(data, dict):
            return data if isinstance(data, dict) else {}

        items_data = data.get("items", {})  # API response might have items directly
        if isinstance(items_data, dict):
            standardized_items = []
            for item_type, keys in items_data.items():
                if isinstance(keys, list):
                    for item_key in keys:
                        if isinstance(item_key, str):
                            standardized_items.append(QuestDropItem(type=item_type, key=item_key))
            data["items"] = standardized_items
        elif isinstance(items_data, list):
            # Assume list is already in {type:..., key:...} format? Adapt if needed.
            # For now, let validation handle it, or parse explicitly here if structure is known.
            pass  # Let Pydantic try parsing list of dicts into list[QuestDropItem]
        else:
            data["items"] = []  # Ensure items is a list

        return data


class QuestCollect(BaseModel):
    """Model for item collection goals within a quest."""

    model_config = ConfigDict(extra="allow", frozen=True)  # Allow any item keys
    # Stores {item_key: count_needed}
    # Pydantic will populate this dict directly from the API response.
    # Example: {"petal": 10, "shiny_seed": 5}


class QuestUnlockCondition(BaseModel):
    """Model for quest unlock condition."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    condition: str | None = None  # Textual description or key? API seems inconsistent
    text: str | None = None  # Unlock message


# KLASS: Quest
class Quest(BaseModel):
    """Habitica quest model (parsed from content.quests)."""

    model_config = ConfigDict(
        extra="ignore",  # Ignore other fields like wiki link, previous quest etc.
        populate_by_name=True,
        frozen=True,  # Quest definitions are static
    )

    key: str = Field(..., description="Unique quest key (e.g., 'atom1').")
    text: str = Field(..., description="Quest title/name.")
    notes: str = Field("", description="Quest description.")
    completion_msg: str = Field("", alias="completion", description="Message shown on completion.")
    category: str | None = Field(None, description="Quest category (e.g., 'boss', 'collect', 'pet').")

    # Nested models
    boss: QuestBoss | None = None
    collect: QuestCollect | None = None  # Holds item keys and counts needed
    drop: QuestDrop = Field(default_factory=QuestDrop)

    # Gold cost to buy quest scroll
    value: int = Field(0, description="Scroll cost in Gold (Gems*4?)")  # Seems to be Gold
    # Level required to start? Seems absent in static content, maybe implied by category/key?
    # lvl: int | None = Field(None, description="Minimum level required?")

    # Group quest can be started in
    # group: dict? # Seems complex, ignoring for now

    # Unlock conditions / Prerequisites (simplified)
    unlock_condition: str | None = Field(None, alias="unlockCondition", description="Text explaining how to unlock.")
    # prereqQuests: list[str] = [] # List of previous quest keys needed

    # --- Validators ---
    @field_validator("text", "notes", "completion_msg", mode="before")
    @classmethod
    def parse_text_emoji(cls, v: Any) -> str:
        if isinstance(v, str):
            return emoji_data_python.replace_colons(v).strip()
        return ""

    @field_validator("value", mode="before")
    @classmethod
    def ensure_int(cls, v: Any) -> int:
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0

    @field_validator("unlock_condition", mode="before")
    @classmethod
    def parse_unlock(cls, v: Any) -> str | None:
        """Handles unlockCondition being object or string."""
        if isinstance(v, dict):
            return v.get("text")  # Prefer text if object
        elif isinstance(v, str):
            return v
        return None

    # --- ADD computed_field properties ---
    @computed_field(description="Derived: True if quest has boss data.")
    @property
    def is_boss_quest(self) -> bool:
        """Calculates if this is a boss quest based on loaded boss data."""
        # Check if boss exists and has relevant stats > 0
        return self.boss is not None and (self.boss.hp > 0 or self.boss.strength > 0)

    @computed_field(description="Derived: True if quest has collection data.")
    @property
    def is_collect_quest(self) -> bool:
        """Calculates if this is a collection quest based on loaded collect data."""
        # Check if collect dict exists and is non-empty
        # Use model_dump to check content after potential validation/parsing
        return self.collect is not None and bool(self.collect.model_dump())

    # --- END computed_field properties ---


# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MAIN CONTENT CONTAINER MODEL


# KLASS: GameContent
class GameContent(BaseModel):
    """Container for processed static game content."""

    model_config = ConfigDict(frozen=True)  # Content is static once loaded

    gear: dict[str, Gear] = Field(default_factory=dict)
    quests: dict[str, Quest] = Field(default_factory=dict)
    spells: dict[str, Spell] = Field(default_factory=dict)  # Store all spells flat for easy lookup
    # Add other categories if needed (e.g., pets, mounts, backgrounds)
    # pets: dict[str, PetInfo] = Field(default_factory=dict)
    # mounts: dict[str, MountInfo] = Field(default_factory=dict)

    last_fetched_at: datetime | None = Field(None, description="Timestamp when the raw content was last fetched.")
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when this processed model was created.")

    @classmethod
    def from_raw_content(cls, raw_content: dict[str, Any], fetched_at: datetime) -> GameContent:
        """Parses the raw '/content' API response into structured models."""
        processed_gear: dict[str, Gear] = {}
        processed_quests: dict[str, Quest] = {}
        processed_spells: dict[str, Spell] = {}

        # --- Process Gear (from gear.flat) ---
        raw_gear_flat = raw_content.get("gear", {}).get("flat", {})
        if isinstance(raw_gear_flat, dict):
            for key, data in raw_gear_flat.items():
                if not isinstance(data, dict):
                    continue
                try:
                    # Inject key into data dict for validation
                    data["key"] = key
                    processed_gear[key] = Gear.model_validate(data)
                except ValidationError as e:
                    log.warning(f"Validation failed for gear '{key}': {e}")
                except Exception as e:
                    log.exception(f"Unexpected error processing gear '{key}': {e}")

        # --- Process Quests ---
        raw_quests = raw_content.get("quests", {})
        if isinstance(raw_quests, dict):
            for key, data in raw_quests.items():
                if not isinstance(data, dict):
                    continue
                try:
                    data["key"] = key  # Ensure key is present
                    processed_quests[key] = Quest.model_validate(data)
                except ValidationError as e:
                    log.warning(f"Validation failed for quest '{key}': {e}")
                except Exception as e:
                    log.exception(f"Unexpected error processing quest '{key}': {e}")

        # --- Process Spells (flatten all classes into one dict) ---
        raw_spells = raw_content.get("spells", {})
        if isinstance(raw_spells, dict):
            for spell_class, spells_in_class in raw_spells.items():
                if isinstance(spells_in_class, dict):
                    for key, data in spells_in_class.items():
                        if not isinstance(data, dict):
                            continue
                        try:
                            data["key"] = key  # Ensure key is present
                            data["klass"] = spell_class  # Inject class
                            processed_spells[key] = Spell.model_validate(data)
                        except ValidationError as e:
                            log.warning(f"Validation failed for spell '{key}' (class: {spell_class}): {e}")
                        except Exception as e:
                            log.exception(f"Unexpected error processing spell '{key}': {e}")

        log.info(f"Processed static content: {len(processed_gear)} gear items, {len(processed_quests)} quests, {len(processed_spells)} spells.")

        return cls(gear=processed_gear, quests=processed_quests, spells=processed_spells, last_fetched_at=fetched_at)


# ──────────────────────────────────────────────────────────────────────────────


# SECTION: STATIC CONTENT MANAGER


# KLASS: StaticContentManager
class StaticContentManager:
    """Manages fetching, caching, and access to Habitica's static game content."""

    def __init__(
        self,
        cache_dir: Path = STATIC_CACHE_DIR,
        raw_filename: str = RAW_CONTENT_FILENAME,
        processed_filename: str = PROCESSED_CONTENT_FILENAME,
        cache_duration_days: int = DEFAULT_CACHE_DURATION_DAYS,
        api_client: HabiticaClient | None = None,  # Optional: provide existing client
    ):
        """Initialize the content manager.

        Args:
            cache_dir: Directory for storing cached files.
            raw_filename: Filename for the raw API response cache.
            processed_filename: Filename for the processed GameContent model cache.
            cache_duration_days: How long processed cache is considered fresh.
            api_client: Optional HabiticaClient instance to use for fetching.
                        If None, a new instance will be created internally.
        """
        self.cache_dir = cache_dir
        self.raw_cache_path = cache_dir / raw_filename
        self.processed_cache_path = cache_dir / processed_filename
        self.cache_duration = timedelta(days=cache_duration_days)
        self.api_client = api_client or HabiticaClient()  # Create client if not provided

        self._content: GameContent | None = None  # In-memory cache
        self._lock = asyncio.Lock()  # Prevent race conditions during load

        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _is_cache_fresh(self, cache_model: GameContent) -> bool:
        """Check if the processed cache file is still fresh."""
        if not cache_model or not cache_model.processed_at:
            return False
        # Ensure processed_at is timezone-aware for comparison
        processed_at_aware = cache_model.processed_at
        if processed_at_aware.tzinfo is None:
            processed_at_aware = processed_at_aware.replace(tzinfo=timezone.utc)

        return (datetime.now(timezone.utc) - processed_at_aware) < self.cache_duration

    async def load_content(self, force_refresh: bool = False) -> GameContent | None:
        """Loads game content, using cache or fetching from API as needed.

        Handles locking to prevent simultaneous loads.

        Args:
            force_refresh: If True, bypass all caches and fetch directly from API.

        Returns:
            The processed GameContent model, or None if loading fails.
        """
        async with self._lock:  # Acquire lock before proceeding
            # 1. Check in-memory cache first (unless forcing refresh)
            if self._content and not force_refresh:
                # Optional: Re-check freshness even for in-memory? Only needed if long-running process
                # if self._is_cache_fresh(self._content): # Can add this check if desired
                log.debug("Using in-memory static content cache.")
                return self._content

            # 2. Try loading from processed Pydantic model cache (if not forcing refresh)
            if not force_refresh and self.processed_cache_path.exists():
                log.debug(f"Attempting to load processed content from: {self.processed_cache_path}")
                cached_model = load_pydantic_model(GameContent, self.processed_cache_path)
                if cached_model and self._is_cache_fresh(cached_model):
                    log.info("Using fresh processed static content cache.")
                    self._content = cached_model
                    return self._content
                elif cached_model:
                    log.info("Processed static content cache is stale.")
                else:
                    log.warning("Failed to load processed static content cache.")

            # 3. Try loading from raw JSON cache (parse if available)
            raw_content_data = None
            raw_fetch_time = None
            if self.raw_cache_path.exists():
                log.debug(f"Attempting to load raw content from: {self.raw_cache_path}")
                raw_content_data = load_json(self.raw_cache_path)
                if raw_content_data:
                    # Try to get modification time as fallback fetch time
                    try:
                        mtime = self.raw_cache_path.stat().st_mtime
                        raw_fetch_time = datetime.fromtimestamp(mtime, timezone.utc)
                        log.info(f"Using raw static content cache (fetched around {raw_fetch_time}). Processing...")
                    except Exception:
                        raw_fetch_time = datetime.now(timezone.utc)  # Fallback
                        log.info("Using raw static content cache (fetch time unknown). Processing...")

                    # Process the raw data loaded from cache
                    try:
                        self._content = GameContent.from_raw_content(raw_content_data, raw_fetch_time)
                        # Save the newly processed data back to processed cache
                        self.save_processed_content()
                        return self._content
                    except Exception as e:
                        log.exception(f"Error processing raw content from cache: {e}")
                        self._content = None  # Ensure content is cleared on error
                else:
                    log.warning("Failed to load raw static content cache file.")

            # 4. Fetch from API as last resort (or if force_refresh is True)
            log.info(f"{'Forcing refresh' if force_refresh else 'Fetching new'} static content from Habitica API...")
            try:
                current_time = datetime.now(timezone.utc)
                fetched_data = await self.api_client.get_content()
                log.success("Successfully fetched raw content from API.")

                # Save the newly fetched raw data
                save_json(fetched_data, self.raw_cache_path)

                # Process the fetched data
                self._content = GameContent.from_raw_content(fetched_data, current_time)

                # Save the newly processed data
                self.save_processed_content()
                return self._content

            except Exception as e:
                log.exception(f"Failed to fetch or process static content from API: {e}")
                # If fetch fails, try to return potentially stale in-memory cache if it exists
                if self._content:
                    log.warning("API fetch failed. Returning potentially stale in-memory content.")
                    return self._content
                else:
                    # If absolutely no content could be loaded/fetched
                    log.error("Could not load static content from any source.")
                    return None  # Indicate failure

    def save_processed_content(self) -> None:
        """Saves the current in-memory _content model to the processed cache file."""
        if not self._content:
            log.warning("No processed content available in memory to save.")
            return

        if save_pydantic_model(self._content, self.processed_cache_path):
            log.info(f"Saved processed static content to {self.processed_cache_path}")
        else:
            log.error(f"Failed to save processed static content to {self.processed_cache_path}")

    async def refresh_from_api(self) -> GameContent | None:
        """Convenience method to force a refresh from the API."""
        return await self.load_content(force_refresh=True)

    # --- Accessor Methods ---
    # These methods ensure content is loaded before returning data
    # They return the specific dictionaries directly.

    async def get_gear(self) -> dict[str, Gear]:
        """Returns the dictionary of all processed gear items."""
        content = await self.load_content()
        return content.gear if content else {}

    async def get_gear_item(self, key: str) -> Gear | None:
        """Gets a specific gear item by key."""
        gear_dict = await self.get_gear()
        return gear_dict.get(key)

    async def get_quests(self) -> dict[str, Quest]:
        """Returns the dictionary of all processed quest items."""
        content = await self.load_content()
        return content.quests if content else {}

    async def get_quest(self, key: str) -> Quest | None:
        """Gets a specific quest by key."""
        quest_dict = await self.get_quests()
        return quest_dict.get(key)

    async def get_spells(self) -> dict[str, Spell]:
        """Returns the dictionary of all processed spell items."""
        content = await self.load_content()
        return content.spells if content else {}

    async def get_spell(self, key: str) -> Spell | None:
        """Gets a specific spell by key."""
        spell_dict = await self.get_spells()
        return spell_dict.get(key)


# ──────────────────────────────────────────────────────────────────────────────

# SECTION: MAIN EXECUTION (Example/Test)
import asyncio  # Needed for running async main


async def main():
    """Demo function to initialize and use the StaticContentManager."""
    log.info("--- Static Content Manager Demo ---")

    # Initialize manager (will create client internally)
    content_manager = StaticContentManager(cache_dir=STATIC_CACHE_DIR)

    try:
        # --- Load Content (uses cache or fetches) ---
        log.info("Loading content (initial load)...")
        content_loaded = await content_manager.load_content()

        if not content_loaded:
            log.error("Failed to load initial content. Exiting demo.")
            return

        log.success("Initial content loaded.")
        print(f"  Gear items: {len(content_loaded.gear)}")
        print(f"  Quests: {len(content_loaded.quests)}")
        print(f"  Spells: {len(content_loaded.spells)}")

        # --- Access specific data types ---
        log.info("Accessing specific data...")
        all_gear = await content_manager.get_gear()
        all_quests = await content_manager.get_quests()
        # print(f"  Fetched all gear again: {len(all_gear)} items")

        # Example: Get a specific item
        test_gear_key = "weapon_warrior_1"  # Change if needed
        gear_item = await content_manager.get_gear_item(test_gear_key)
        if gear_item:
            print(f"  Found Gear '{test_gear_key}': {gear_item.text} (STR: {gear_item.stats.strength})")
        else:
            print(f"  Gear '{test_gear_key}' not found.")

        test_quest_key = "atom1"  # Change if needed
        quest_item = await content_manager.get_quest(test_quest_key)
        if quest_item:
            print(f"  Found Quest '{test_quest_key}': {quest_item.text} (Category: {quest_item.category})")
            if quest_item.is_boss_quest:
                print(f"    Boss Quest: Name={quest_item.boss.name}, HP={quest_item.boss.hp}")
        else:
            print(f"  Quest '{test_quest_key}' not found.")

        # --- Force Refresh ---
        # log.info("Forcing content refresh from API...")
        # await content_manager.refresh_from_api()
        # log.success("Content refreshed.")

    except Exception as e:
        log.exception(f"An error occurred during the content manager demo: {e}")


if __name__ == "__main__":
    # Basic logging config if running standalone
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(main())

# ──────────────────────────────────────────────────────────────────────────────
