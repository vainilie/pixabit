# pixabit/tui/game_content.py

# SECTION: MODULE DOCSTRING
"""Provides the GameContent class for lazy-loading and caching Habitica game content.

Handles fetching the main content object from the API, saving it to a cache file,
and providing methods to access specific sections (e.g., gear, quests, spells)
from the cached data on demand.
"""

# SECTION: IMPORTS
import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.logging import RichHandler
from textual import log

from pixabit.utils.display import console

FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)])

# Local Imports
try:
    # Direct import assumes flat structure or correct PYTHONPATH
    from pixabit.cli.config import CACHE_FILE_CONTENT

    CACHE_FILE_RAW = CACHE_FILE_CONTENT  # Keep original name? Or rename? Let's rename for clarity.
    # CACHE_FILE_RAW = "content_cache_raw.json"
    CACHE_FILE_EXTRACTED = "content_cache_extracted.json"

    from pixabit.tui.api import HabiticaAPI, HabiticaAPIError
    from pixabit.utils.display import console, print
    from pixabit.utils.save_json import load_json, save_json
except ImportError:

    # Define dummy fallback components
    class HabiticaAPI:  # type: ignore
        async def get_content(self) -> Optional[Dict[str, Any]]:
            return None

    HabiticaAPIError = Exception  # type: ignore

    def save_json(data: Any, filepath: Any) -> bool:
        log.info(f"Dummy save_json({filepath})")
        return False

    def load_json(filepath: Any) -> Any:
        log.info(f"Dummy load_json({filepath})")
        return None

    # ... (Keep fallbacks, define both cache filenames) ...
    CACHE_FILE_RAW = "content_cache_raw_fallback.json"
    CACHE_FILE_EXTRACTED = "content_cache_extracted_fallback.json"
    log.error("Warning: Could not import Pixabit components in game_content.py. Using fallbacks.")


# KLASS: GameContent
class GameContent:
    """Manages lazy-loading and caching (raw & extracted) of Habitica game content."""

    CACHE_PATH_RAW: Path = Path(CACHE_FILE_RAW)
    CACHE_PATH_EXTRACTED: Path = Path(CACHE_FILE_EXTRACTED)

    # FUNC: __init__
    def __init__(self, api_client: Optional[HabiticaAPI] = None):
        """Initializes the GameContent manager.

        Args:
            api_client: Optional HabiticaAPI client instance. If not provided,
                        an attempt will be made to create one internally for fetching,
                        which requires credentials to be configured.
        """
        self.console = console
        # Store API client if provided, otherwise create lazily if needed
        self._api_client_instance: Optional[HabiticaAPI] = api_client
        # Stores the *full* raw content if loaded directly or fetched
        self._raw_content_cache: Optional[Dict[str, Any]] = None
        # Stores *only* the extracted sections if loaded from extracted cache or after extraction
        self._extracted_content_cache: Optional[Dict[str, Any]] = None
        # Flags
        self._raw_cache_loaded: bool = False  # Tracks if full cache is in memory
        self._extracted_cache_loaded: bool = False  # Tracks if extracted cache is in memory/loaded
        # Locks and timestamp
        self._fetch_lock = asyncio.Lock()
        self._last_fetch_attempt: float = 0.0

    # FUNC: _get_api_client (Lazy instantiation)
    def _get_api_client(self) -> HabiticaAPI:
        """Returns the stored API client or attempts to create a new one."""
        if self._api_client_instance is None:
            log.info(
                "GameContent: API client not provided, creating instance...",
            )
            try:
                self._api_client_instance = HabiticaAPI()  # Assumes config is available
            except Exception as e:
                log.error(
                    "[error]Failed to auto-create HabiticaAPI client in GameContent![/error]",
                )
                raise RuntimeError("GameContent requires a valid HabiticaAPI client.") from e
        return self._api_client_instance

    # FUNC: invalidate_cache
    def invalidate_cache(self) -> None:
        """Clears internal caches, forcing a reload on next access."""
        log.info("GameContent caches invalidated.")
        self._raw_content_cache = None
        self._extracted_content_cache = None
        self._raw_cache_loaded = False
        self._extracted_cache_loaded = False

    # FUNC: _load_extracted_cache
    def _load_extracted_cache(self) -> bool:
        """Attempts to load content from the EXTRACTED JSON cache file."""
        if not self.CACHE_PATH_EXTRACTED.is_file():
            return False
        log.info(
            f"Attempting load from extracted cache: '{self.CACHE_PATH_EXTRACTED}'...",
        )
        loaded_data = load_json(self.CACHE_PATH_EXTRACTED)
        # Basic validation: is it a non-empty dictionary?
        if isinstance(loaded_data, dict) and loaded_data:
            self._extracted_content_cache = loaded_data
            self._extracted_cache_loaded = True
            self._raw_cache_loaded = False  # Don't need raw if extracted loaded
            self._raw_content_cache = None  # Clear raw from memory
            log.info(
                "Successfully loaded content from extracted cache.",
            )
            return True
        else:
            log.warning(
                f"Extracted cache '{self.CACHE_PATH_EXTRACTED}' empty or invalid format.",
            )
            return False

    # FUNC: _load_raw_cache
    def _load_raw_cache(self) -> bool:
        """Attempts to load content from the RAW JSON cache file."""
        if not self.CACHE_PATH_RAW.is_file():
            return False
        log.info(
            f"Attempting load from raw cache: '{self.CACHE_PATH_RAW}'...",
        )
        loaded_data = load_json(self.CACHE_PATH_RAW)
        if isinstance(loaded_data, dict) and loaded_data:
            self._raw_content_cache = loaded_data  # Store full raw data
            self._raw_cache_loaded = True
            self._extracted_cache = None  # Clear any old extracted data
            self._extracted_cache_loaded = False
            log.info(
                "Successfully loaded full content from raw cache.",
            )
            return True
        else:
            log.warning(
                f"Raw cache file '{self.CACHE_PATH_RAW}' empty or invalid format.",
            )
            # Optionally delete invalid cache file?
            # try: self.CACHE_FILE_PATH.unlink() except OSError: pass
            return False

    # FUNC: _fetch_and_save_raw_content (Async)
    async def _fetch_and_save_raw_content(self) -> bool:
        """Fetches full content from API, saves to raw cache, stores internally."""
        async with self._fetch_lock:
            # Debounce fetching slightly if called rapidly
            now = time.monotonic()
            debounce_time = 1.0
            if now - self._last_fetch_attempt < debounce_time:
                return self._raw_cache_loaded
            self._last_fetch_attempt = now

            log.info("Fetching full game content from API...")
            try:
                api = self._get_api_client()
                content = await api.get_content()
                if isinstance(content, dict) and content:
                    log.info(
                        "Successfully fetched full content from API.",
                    )
                    save_raw_ok = save_json(content, self.CACHE_PATH_RAW)
                    if save_raw_ok:
                        log.info(
                            f"Saved raw content to cache: '{self.CACHE_PATH_RAW}'",
                        )
                    self._raw_content_cache = content  # Store fetched raw data
                    self._raw_cache_loaded = True
                    self._extracted_cache = None  # Invalidate old extracted cache
                    self._extracted_cache_loaded = False
                    return True
                else:
                    log.error("Failed fetch valid content from API.")
                    return False
            except Exception as e:
                log.error(
                    f"Error fetching full content: {e}",
                )
                return False

    # FUNC: _generate_and_save_extracted_cache (NEW - Sync)
    def _generate_and_save_extracted_cache(self) -> None:
        """Generates the extracted data dict using getters and saves it."""
        if not self._raw_cache_loaded or not self._raw_content_cache:
            log.warning(
                "Cannot generate extracted cache: Raw content not loaded.",
            )
            return

        log.info("Generating and saving extracted content cache...")
        extracted_data = {
            "gear_flat": self._get_gear_data_internal(),  # Use internal getters
            "spells": self._get_skill_data_internal(),
            "quests": self._get_quest_data_internal(),
            "pets": self._get_pets_data_internal(),
            "mounts": self._get_mounts_data_internal(),
            # Add calls to other internal getters for keys in KEYS_TO_EXTRACT
        }

        save_success = save_json(extracted_data, self.CACHE_PATH_EXTRACTED)
        if save_success:
            log.info(
                f"Saved extracted content to cache: '{self.CACHE_PATH_EXTRACTED}'",
            )
            # Update internal extracted cache state
            self._extracted_content_cache = extracted_data
            self._extracted_cache_loaded = True
            # Optionally clear raw cache from memory now if desired
            # self._raw_content_cache = None
            # self._raw_cache_loaded = False
        else:
            log.warning(
                f"Failed to save extracted content cache: '{self.CACHE_PATH_EXTRACTED}'",
            )
            # If save failed, keep extracted data in memory anyway for this session
            self._extracted_content_cache = extracted_data
            self._extracted_cache_loaded = True

    # FUNC: _ensure_content_loaded (Async - Orchestrator - Modified)
    async def _ensure_content_loaded(self) -> None:
        """Ensures extracted content is loaded, using two-stage cache."""
        if self._extracted_cache_loaded:
            return  # Already have what we need

        # 1. Try loading the small extracted cache
        if self._load_extracted_cache():
            return

        # 2. Extracted cache failed, ensure RAW cache is loaded/fetched
        if not self._raw_cache_loaded:  # Check if raw is already in memory
            if not self._load_raw_cache():  # Try loading raw from file
                if not await self._fetch_and_save_raw_content():  # Fetch raw if load failed
                    log.error(
                        "Game content unavailable: Failed cache loads and API fetch.",
                    )
                    self._extracted_cache = {}  # Ensure empty dict
                    self._extracted_cache_loaded = True  # Mark as "attempted"
                    return

        # 3. We have raw content (in self._raw_content_cache), generate extracted cache
        self._generate_and_save_extracted_cache()  # Sync generation after load/fetch

        # Final check
        if not self._extracted_cache_loaded:
            log.error(
                "Failed to populate extracted cache.",
            )
            self._extracted_cache = {}
            self._extracted_cache_loaded = True  # Mark as attempted

    # --- Internal Getters (Operating on _raw_content_cache or _extracted_content_cache) ---
    # These are called by the public async getters OR by _generate_and_save_extracted_cache

    def _get_active_cache(self) -> Optional[Dict[str, Any]]:
        """Returns the currently active cache (prefer extracted)."""
        if self._extracted_cache_loaded:
            return self._extracted_content_cache
        elif self._raw_cache_loaded:
            return self._raw_content_cache
        else:
            return None  # Should not happen if _ensure_content_loaded is called first

    def _get_gear_data_internal(self) -> Dict[str, Any]:
        """Internal sync getter for gear data."""
        active_cache = self._get_active_cache()
        if active_cache:
            # If using extracted cache, the key is 'gear_flat'
            if self._extracted_cache_loaded:
                return active_cache.get("gear_flat", {})
            # If using raw cache, get nested 'gear.flat'
            else:
                gear = active_cache.get("gear", {})
                return gear.get("flat", {}) if isinstance(gear, dict) else {}
        return {}

    def _get_skill_data_internal(self) -> Dict[str, Any]:
        """Internal sync getter for spells data."""
        active_cache = self._get_active_cache()
        return active_cache.get("spells", {}) if active_cache else {}

    def _get_quest_data_internal(self) -> Dict[str, Any]:
        """Internal sync getter for quests data."""
        active_cache = self._get_active_cache()
        return active_cache.get("quests", {}) if active_cache else {}

    def _get_pets_data_internal(self) -> Dict[str, Any]:
        """Internal sync getter for pets data."""
        active_cache = self._get_active_cache()
        return active_cache.get("pets", {}) if active_cache else {}

    def _get_mounts_data_internal(self) -> Dict[str, Any]:
        """Internal sync getter for mounts data."""
        active_cache = self._get_active_cache()
        return active_cache.get("mounts", {}) if active_cache else {}

    # --- Public Accessor Methods (Async) ---
    # These methods ensure data is loaded before returning sections.

    # FUNC: get_all_content (Async)
    async def get_all_content(self) -> Optional[Dict[str, Any]]:
        """Returns the full game content object, loading/fetching if necessary."""
        await self._ensure_content_loaded()
        return self._main_content_cache

    # FUNC: get_gear_data (Async)
    async def get_gear_data(self) -> Dict[str, Any]:
        """Returns the 'gear.flat' section of game content."""
        await self._ensure_content_loaded()
        # --- CHANGE: Call internal getter ---
        return self._get_gear_data_internal()

    # FUNC: get_quest_data (Async)
    async def get_quest_data(self) -> Dict[str, Any]:
        """Returns the 'quests' section of game content, loading/fetching if necessary."""
        await self._ensure_content_loaded()
        return self._get_quest_data_internal()

    # FUNC: get_skill_data (Async) - Assuming skills/spells are under 'spells' key
    async def get_skill_data(self) -> Dict[str, Any]:
        """Returns the 'spells' section (containing class skills) of game content."""
        await self._ensure_content_loaded()
        return self._get_skill_data_internal()

    # Add more getters for other content sections as needed (e.g., pets, mounts, food)
    async def get_pets_data(self) -> Dict[str, Any]:
        """Returns the 'pets' section of game content."""
        await self._ensure_content_loaded()
        return self._get_pets_data_internal()

    async def get_mounts_data(self) -> Dict[str, Any]:
        """Returns the 'mounts' section of game content."""
        await self._ensure_content_loaded()
        return self._get_mounts_data_internal()
