# pixabit/tui/game_content.py

# SECTION: MODULE DOCSTRING
"""Provides the GameContent class for lazy-loading and caching Habitica game content.

Handles fetching the main content object from the API, saving it to a cache file,
and providing methods to access specific sections (e.g., gear, quests, spells)
from the cached data on demand.
"""

# SECTION: IMPORTS
import asyncio
import time
from pathlib import Path
from typing import Any, Dict, Optional  # Keep Dict/List

# Local Imports
try:
    from ..cli.config import CACHE_FILE_CONTENT  # Use config for cache filename
    from ..utils.display import console, print
    from ..utils.save_json import load_json, save_json

    # Direct import assumes flat structure or correct PYTHONPATH
    from .api import HabiticaAPI, HabiticaAPIError
except ImportError:
    # Fallback for standalone testing or import issues
    import builtins

    print = builtins.print

    class DummyConsole:
        def print(self, *args: Any, **kwargs: Any) -> None:
            builtins.print(*args)

        def log(self, *args: Any, **kwargs: Any) -> None:
            builtins.print("LOG:", *args)

        def print_exception(self, *args: Any, **kwargs: Any) -> None:
            import traceback

            traceback.print_exc()

    console = DummyConsole()

    # Define dummy fallback components
    class HabiticaAPI:  # type: ignore
        async def get_content(self) -> Optional[Dict[str, Any]]:
            return None

    HabiticaAPIError = Exception  # type: ignore

    def save_json(data: Any, filepath: Any) -> bool:
        print(f"Dummy save_json({filepath})")
        return False

    def load_json(filepath: Any) -> Any:
        print(f"Dummy load_json({filepath})")
        return None

    CACHE_FILE_CONTENT = "content_cache_fallback.json"
    print(
        "Warning: Could not import Pixabit components in game_content.py. Using fallbacks."
    )


# KLASS: GameContent
class GameContent:
    """Manages lazy-loading and caching of the main Habitica game content object."""

    # Class variable for the cache file path, using value from config
    CACHE_FILE_PATH: Path = Path(CACHE_FILE_CONTENT)

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
        # Internal cache storage
        self._main_content_cache: Optional[Dict[str, Any]] = None
        self._cache_loaded: bool = False
        self._last_fetch_attempt: float = 0.0
        self._fetch_lock = asyncio.Lock()  # Use asyncio lock for async fetch

    # FUNC: _get_api_client (Lazy instantiation)
    def _get_api_client(self) -> HabiticaAPI:
        """Returns the stored API client or attempts to create a new one."""
        if self._api_client_instance is None:
            self.console.log(
                "GameContent: API client not provided, creating instance...",
                style="info",
            )
            try:
                self._api_client_instance = (
                    HabiticaAPI()
                )  # Assumes config is available
            except Exception as e:
                self.console.print(
                    "[error]Failed to auto-create HabiticaAPI client in GameContent![/error]",
                    style="error",
                )
                raise RuntimeError(
                    "GameContent requires a valid HabiticaAPI client."
                ) from e
        return self._api_client_instance

    # FUNC: invalidate_cache
    def invalidate_cache(self) -> None:
        """Clears the internal cache, forcing a reload on next access."""
        self.console.log("GameContent cache invalidated.", style="info")
        self._main_content_cache = None
        self._cache_loaded = False

    # FUNC: _load_from_cache_file
    def _load_from_cache_file(self) -> bool:
        """Attempts to load content from the JSON cache file."""
        if not self.CACHE_FILE_PATH.is_file():
            self.console.log(
                f"Cache file not found: '{self.CACHE_FILE_PATH}'",
                style="subtle",
            )
            return False

        self.console.log(
            f"Attempting load from cache: '{self.CACHE_FILE_PATH}'...",
            style="info",
        )
        loaded_data = load_json(self.CACHE_FILE_PATH)  # Uses sync load_json

        if isinstance(loaded_data, dict) and loaded_data:
            self._main_content_cache = loaded_data
            self._cache_loaded = True
            self.console.log(
                "Successfully loaded content from cache.", style="success"
            )
            return True
        else:
            self.console.log(
                f"Cache file '{self.CACHE_FILE_PATH}' empty or invalid format.",
                style="warning",
            )
            # Optionally delete invalid cache file?
            # try: self.CACHE_FILE_PATH.unlink() except OSError: pass
            return False

    # FUNC: _fetch_and_save_content (Async)
    async def _fetch_and_save_content(self) -> bool:
        """Fetches content from API, saves to cache, and updates internal cache."""
        # Prevent multiple concurrent fetches
        async with self._fetch_lock:
            # Debounce fetching slightly if called rapidly
            now = time.monotonic()
            if now - self._last_fetch_attempt < 1.0:  # Avoid fetch spam
                self.console.log("Debouncing content fetch.", style="subtle")
                # Return status based on current cache state after debounce
                return self._cache_loaded
            self._last_fetch_attempt = now

            self.console.log("Fetching game content from API...", style="info")
            try:
                api = self._get_api_client()  # Get or create API client
                content = await api.get_content()  # Await the async call

                if isinstance(content, dict) and content:
                    self.console.log(
                        "Successfully fetched content from API.",
                        style="success",
                    )
                    # Save to file (using sync save_json for simplicity)
                    save_success = save_json(content, self.CACHE_FILE_PATH)
                    if save_success:
                        self.console.log(
                            f"Saved content to cache: '{self.CACHE_FILE_PATH}'",
                            style="info",
                        )
                    # Update internal cache immediately
                    self._main_content_cache = content
                    self._cache_loaded = True
                    return True
                else:
                    self.console.log(
                        "Failed to fetch valid content from API (None or empty dict returned).",
                        style="error",
                    )
                    # Keep existing cache if fetch failed? Or clear it? Let's keep it for now.
                    return False
            except HabiticaAPIError as e:
                self.console.print(
                    f"API Error fetching content: {e}", style="error"
                )
                return False
            except Exception as e:
                self.console.print(
                    f"Unexpected Error fetching content: {e}", style="error"
                )
                return False

    # FUNC: _ensure_content_loaded (Async)
    async def _ensure_content_loaded(self) -> None:
        """Ensures content is loaded, trying cache first, then fetching if needed."""
        if self._cache_loaded and self._main_content_cache is not None:
            return  # Already loaded

        # Try loading from file cache
        if self._load_from_cache_file():
            return  # Loaded from file successfully

        # File cache failed or missing, fetch from API
        await self._fetch_and_save_content()

        # After fetch attempt, check cache status again
        if not self._cache_loaded:
            # Fetching also failed, content is unavailable
            self.console.print(
                "Game content unavailable after fetch attempt.", style="error"
            )
            # Optionally raise an error here? Or just return None from getters?
            # Let's allow getters to return None/empty if content is missing.

    # --- Public Accessor Methods (Async) ---
    # These methods ensure data is loaded before returning sections.

    # FUNC: get_all_content (Async)
    async def get_all_content(self) -> Optional[Dict[str, Any]]:
        """Returns the full game content object, loading/fetching if necessary."""
        await self._ensure_content_loaded()
        return self._main_content_cache

    # FUNC: get_gear_data (Async)
    async def get_gear_data(self) -> Dict[str, Any]:
        """Returns the 'gear.flat' section of game content, loading/fetching if necessary."""
        await self._ensure_content_loaded()
        if self._main_content_cache:
            # Safely access nested structure
            gear = self._main_content_cache.get("gear", {})
            return gear.get("flat", {}) if isinstance(gear, dict) else {}
        return {}

    # FUNC: get_quest_data (Async)
    async def get_quest_data(self) -> Dict[str, Any]:
        """Returns the 'quests' section of game content, loading/fetching if necessary."""
        await self._ensure_content_loaded()
        if self._main_content_cache:
            return self._main_content_cache.get("quests", {})
        return {}

    # FUNC: get_skill_data (Async) - Assuming skills/spells are under 'spells' key
    async def get_skill_data(self) -> Dict[str, Any]:
        """Returns the 'spells' section (containing class skills) of game content."""
        await self._ensure_content_loaded()
        if self._main_content_cache:
            # Habitica content uses 'spells' key for class skills
            return self._main_content_cache.get("spells", {})
        return {}

    # Add more getters for other content sections as needed (e.g., pets, mounts, food)
    async def get_pets_data(self) -> Dict[str, Any]:
        """Returns the 'pets' section of game content."""
        await self._ensure_content_loaded()
        return (
            self._main_content_cache.get("pets", {})
            if self._main_content_cache
            else {}
        )

    async def get_mounts_data(self) -> Dict[str, Any]:
        """Returns the 'mounts' section of game content."""
        await self._ensure_content_loaded()
        return (
            self._main_content_cache.get("mounts", {})
            if self._main_content_cache
            else {}
        )
