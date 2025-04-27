# pixabit/cli/config.py (Utility / Core Config)

# SECTION: MODULE DOCSTRING
"""Loads configuration settings for the Pixabit application from a .env file.

Locates `.env` (project root expected), ensures mandatory credentials exist
(using `config_auth.check_env_file`), loads variables using `python-dotenv`,
validates mandatory credentials, and makes settings available as constants.

Exits if mandatory credentials are not found or invalid after the check.

Constants Defined:
- HABITICA_USER_ID (str): Habitica User ID.
- HABITICA_API_TOKEN (str): Habitica API Token.
- CACHE_FILE_CONTENT (str): Filename for the game content cache.
- Optional Tag IDs (str | None): CHALLENGE_TAG_ID, PERSONAL_TAG_ID, etc.
- Derived Maps (dict[str, str]): TAG_MAP, ATTR_TAG_MAP, POISON_MAP, CHALLENGE_MAP.
"""

# SECTION: IMPORTS
import logging
import os
import sys  # For sys.exit
from pathlib import Path
from typing import Any, Dict, Optional  # Added Dict/Any

from dotenv import load_dotenv
from pixabit.helpers._rich import console
from rich.logging import RichHandler
from textual import log

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

# Use themed display and auth check function
try:
    # Use relative import to get display from parent 'utils' package
    from ..utils.display import console, print

    # Use relative import to get check_env_file from sibling 'config_auth' module
    from .config_auth import check_env_file
except ImportError:
    # Fallback imports
    import builtins

    print = builtins.print

    class DummyConsole:
        def print(self, *args: Any, **kwargs: Any) -> None:
            builtins.print(*args)

        def log(self, *args: Any, **kwargs: Any) -> None:
            builtins.print("LOG:", *args)

    console = DummyConsole()

    def check_env_file(env_path: Path) -> None:  # Dummy function
        print(f"Dummy check_env_file called for {env_path}")
        # In real scenario, this fallback might need more logic or just fail

    print("[Warning] Could not import Pixabit display/auth utils in config.py")

# SECTION: PATH CALCULATION AND .ENV CHECK

try:
    # Assume config.py is in pixabit/cli/, .env is at project root
    # Go up two levels from cli/config.py to reach project root
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
except NameError:
    # Fallback if __file__ is not defined (e.g., interactive, testing)
    PROJECT_ROOT = Path(".").resolve()  # Assume running from project root
    log.warning(
        f"[warning]⚠️ `__file__` undefined. Assuming project root is CWD: [file]{PROJECT_ROOT}[/]",
        style="warning",
    )

ENV_FILE_PATH: Path = PROJECT_ROOT / ".env"
# Define cache filename constant relative to project structure or data location
# For simplicity, placing it in project root for now. Consider a dedicated cache dir.
CACHE_FILE_CONTENT: str = "content_cache.json"

# Ensure .env file exists, prompt for creation if needed (calls config_auth)
# This needs to run early to ensure credentials can be loaded.
check_env_file(env_path=ENV_FILE_PATH)

# SECTION: LOAD ENVIRONMENT VARIABLES

log.info(f"⌛ Loading environment variables from: [file]{ENV_FILE_PATH}[/]")
# load_dotenv will search for the .env file in current dir or parents
# Override=False ensures existing environment vars are not overwritten by .env
# Verbose=False keeps logs cleaner
loaded: bool = load_dotenv(
    dotenv_path=ENV_FILE_PATH, verbose=False, override=False
)

if not loaded and ENV_FILE_PATH.exists():
    # This might happen if the .env file is empty or has syntax errors
    log.warning(
        "[warning]⚠️ .env found but `load_dotenv` failed to load values (empty/malformed?).[/warning]"
    )
elif not ENV_FILE_PATH.exists():  # Should not happen if check_env_file worked
    log.error(
        f"[error]❌ CRITICAL: .env file still not found at [file]{ENV_FILE_PATH}[/]. Exiting.[/error]"
    )
    sys.exit(1)

# SECTION: APPLICATION CONSTANTS (Mandatory first)

# --- Habitica API Credentials ---
# Read from environment (which load_dotenv populated)
HABITICA_USER_ID: str | None = os.getenv("HABITICA_USER_ID")
HABITICA_API_TOKEN: str | None = os.getenv("HABITICA_API_TOKEN")

# --- Validation of Mandatory Credentials ---
# Perform check immediately after trying to load
if not HABITICA_USER_ID or not HABITICA_API_TOKEN:
    log.error("\n" + "=" * 60, style="error")
    log.error(
        " [error]❌ FATAL ERROR: Essential Configuration Missing![/error]"
    )
    if not HABITICA_USER_ID:
        log.error(
            " - `HABITICA_USER_ID` not found or empty in environment/.env."
        )
    if not HABITICA_API_TOKEN:
        log.error(
            " - `HABITICA_API_TOKEN` not found or empty in environment/.env."
        )
    log.error(f"   Location checked: [file]{ENV_FILE_PATH}[/]")
    log.error("   Please run setup or manually edit the `.env` file.")
    log.error("   Application cannot continue without these credentials.")
    log.error("=" * 60 + "\n", style="error")
    sys.exit(1)  # Exit if mandatory credentials are not loaded

# --- Optional Tag IDs ---
# Use .strip() to handle potential whitespace and default to None if empty string after strip
CHALLENGE_TAG_ID: str | None = os.getenv("CHALLENGE_TAG_ID", "").strip() or None
PERSONAL_TAG_ID: str | None = os.getenv("PERSONAL_TAG_ID", "").strip() or None
LEGACY_TAG_ID: str | None = os.getenv("LEGACY_TAG_ID", "").strip() or None
PSN_TAG_ID: str | None = os.getenv("PSN_TAG_ID", "").strip() or None
NOT_PSN_TAG_ID: str | None = os.getenv("NOT_PSN_TAG_ID", "").strip() or None
NO_ATTR_TAG_ID: str | None = os.getenv("NO_ATTR_TAG_ID", "").strip() or None
ATTR_TAG_STR_ID: str | None = os.getenv("ATTR_TAG_STR_ID", "").strip() or None
ATTR_TAG_INT_ID: str | None = os.getenv("ATTR_TAG_INT_ID", "").strip() or None
ATTR_TAG_CON_ID: str | None = os.getenv("ATTR_TAG_CON_ID", "").strip() or None
ATTR_TAG_PER_ID: str | None = os.getenv("ATTR_TAG_PER_ID", "").strip() or None

# --- Derived Config Maps (for convenience) ---
# These maps link configured Tag IDs to their functional meaning.

# TAG_MAP: General purpose tags (Challenge, Personal, Legacy)
TAG_MAP: dict[str, str] = {
    tag_id: purpose
    for tag_id, purpose in [
        (CHALLENGE_TAG_ID, "challenge"),
        (LEGACY_TAG_ID, "legacy"),
        (PERSONAL_TAG_ID, "personal"),
    ]
    if tag_id  # Only include if the ID is configured (not None)
}

# ATTR_TAG_MAP: Attribute-specific tags (TagID -> AttrKey)
ATTR_TAG_MAP: dict[str, str] = {
    tag_id: attr
    for tag_id, attr in [
        (ATTR_TAG_STR_ID, "str"),
        (ATTR_TAG_INT_ID, "int"),
        (ATTR_TAG_CON_ID, "con"),
        (ATTR_TAG_PER_ID, "per"),
        (LEGACY_TAG_ID, "legacy"),
    ]
    if tag_id
}
# Expose ATTR_TAG_MAP directly, ATTRIBUTE_MAP alias kept for compatibility if needed
ATTRIBUTE_MAP = ATTR_TAG_MAP

# POISON_MAP: Poison status tags
POISON_MAP: dict[str, str] = {
    tag_id: status
    for tag_id, status in [
        (PSN_TAG_ID, "psn"),
        (NOT_PSN_TAG_ID, "no_psn"),
    ]
    if tag_id
}

# CHALLENGE_MAP: Combined Challenge/Personal/Legacy map (duplicate of TAG_MAP?)
# Let's keep TAG_MAP as the primary for this group for clarity.
# CHALLENGE_MAP: dict[str, str] = TAG_MAP.copy() # Or redefine if needed

# SECTION: MODULE LOAD COMPLETION LOG
# This log confirms the config module itself loaded, not necessarily all values.
# The critical credential check handles fatal errors earlier.
log.info("[success]✅ Configuration module loaded successfully.[/success]")
