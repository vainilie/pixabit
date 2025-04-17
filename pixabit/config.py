# pixabit/config.py

# MARK: - MODULE DOCSTRING
"""Loads configuration settings for the Pixabit application from a .env file.

Locates `.env` (project root expected), ensures mandatory credentials exist
(using `config_auth.check_env_file`), loads variables using `python-dotenv`,
and makes settings available as constants. Exits if mandatory credentials
are missing after the check/creation step.

Constants Defined:
    - HABITICA_USER_ID (str): Habitica User ID (Validated).
    - HABITICA_API_TOKEN (str): Habitica API Token (Validated).
    - Optional Tag IDs (Optional[str]): CHALLENGE_TAG_ID, PERSONAL_TAG_ID,
      PSN_TAG_ID, NOT_PSN_TAG_ID, NO_ATTR_TAG_ID, ATTR_TAG_*_ID.
"""


# MARK: - IMPORTS
import os
import sys

# For sys.exit
from pathlib import Path
from typing import Optional

# Added Dict for ATTR_TAG_MAP
from dotenv import load_dotenv

# Use themed display and auth check function
try:
    from .config_auth import check_env_file
    from .utils.display import console, print
except ImportError:
    import builtins

    print = builtins.print

    # Define dummy components if run standalone or during setup issues
    def check_env_file(env_path):
        pass

    class DummyConsole:
        def print(self, *args, **kwargs):
            builtins.print(*args)

        def log(self, *args, **kwargs):
            builtins.print(*args)

    console = DummyConsole()
    print("[Warning] Could not import Pixabit display/auth utils in config.py")


# MARK: - PATH CALCULATION
try:
    ENV_FILE_PATH = Path(__file__).resolve().parent.parent / ".env"
except NameError:
    ENV_FILE_PATH = Path(".").resolve() / ".env"
    console.log(
        f"[warning]⚠️ `__file__` undefined. Assuming .env in CWD: [file]{ENV_FILE_PATH}[/]",
        style="warning",
        # Use direct style if console might be dummy
    )


# MARK: - ENSURE .ENV EXISTS (calls config_auth.py)

# This will prompt for creation or exit if skipped/failed
check_env_file(env_path=ENV_FILE_PATH)


# MARK: - LOAD ENVIRONMENT VARIABLES
console.log(f"⌛ Loading environment variables from: [file]{ENV_FILE_PATH}[/]")
loaded = load_dotenv(dotenv_path=ENV_FILE_PATH, verbose=False, override=False)
# verbose=False is quieter

if not loaded and ENV_FILE_PATH.exists():
    console.log("[warning]⚠️ .env found but `load_dotenv` failed (empty/malformed?).[/]")
elif not ENV_FILE_PATH.exists():
    # Should not happen if check_env_file worked
    console.log(f"[error]❌ .env file still not found at [file]{ENV_FILE_PATH}[/]. Exiting.[/]")
    sys.exit(1)


# MARK: - APPLICATION CONSTANTS (Mandatory first)


# --- Habitica API Credentials (Checked for None after loading) ---
HABITICA_USER_ID: Optional[str] = os.getenv("HABITICA_USER_ID")
HABITICA_API_TOKEN: Optional[str] = os.getenv("HABITICA_API_TOKEN")


# --- Validation of Mandatory Credentials ---
if not HABITICA_USER_ID or not HABITICA_API_TOKEN:
    console.print("\n" + "=" * 60, style="error")
    console.print(" [error]❌ FATAL ERROR: Essential Configuration Missing![/error]")
    if not HABITICA_USER_ID:
        console.print("   - `HABITICA_USER_ID` not found or empty in `.env` file.")
    if not HABITICA_API_TOKEN:
        console.print("   - `HABITICA_API_TOKEN` not found or empty in `.env` file.")
    console.print(f"   Location checked: [file]{ENV_FILE_PATH}[/]")
    console.print("   Please run setup (`pixabit setup-auth`) or manually edit the `.env` file.")
    console.print("   Application cannot continue without these credentials.")
    console.print("=" * 60 + "\n", style="error")
    sys.exit(1)
# Exit if mandatory credentials are not loaded


# --- Optional Tag IDs ---
CHALLENGE_TAG_ID: Optional[str] = os.getenv("CHALLENGE_TAG_ID")
PERSONAL_TAG_ID: Optional[str] = os.getenv("PERSONAL_TAG_ID")
LEGACY_TAG_ID: Optional[str] = os.getenv("LEGACY_TAG_ID")
PSN_TAG_ID: Optional[str] = os.getenv("PSN_TAG_ID")
NOT_PSN_TAG_ID: Optional[str] = os.getenv("NOT_PSN_TAG_ID")
NO_ATTR_TAG_ID: Optional[str] = os.getenv("NO_ATTR_TAG_ID")
ATTR_TAG_STR_ID: Optional[str] = os.getenv("ATTR_TAG_STR_ID")
ATTR_TAG_INT_ID: Optional[str] = os.getenv("ATTR_TAG_INT_ID")
ATTR_TAG_CON_ID: Optional[str] = os.getenv("ATTR_TAG_CON_ID")
ATTR_TAG_PER_ID: Optional[str] = os.getenv("ATTR_TAG_PER_ID")


# --- Derived Config: Attribute Tag Map (for convenience) ---
TAG_MAP: dict[str, str] = {
    tag_id: attr
    for tag_id, attr in [
        (CHALLENGE_TAG_ID, "challenge"),
        (LEGACY_TAG_ID, "legacy"),
        (PERSONAL_TAG_ID, "personal"),
        (PSN_TAG_ID, "psn"),
        (NOT_PSN_TAG_ID, "no_psn"),
    ]
    if tag_id
}
# Useful for TagManager and potentially other parts of the app

# Only includes tags that are actually configured in the .env
ATTRIBUTE_MAP: dict[str, str] = {
    tag_id: attr
    for tag_id, attr in [
        (ATTR_TAG_STR_ID, "str"),
        (ATTR_TAG_INT_ID, "int"),
        (ATTR_TAG_CON_ID, "con"),
        (ATTR_TAG_PER_ID, "per"),
    ]
    if tag_id
}
POISON_MAP: dict[str, str] = {
    tag_id: attr
    for tag_id, attr in [
        (PSN_TAG_ID, "psn"),
        (NOT_PSN_TAG_ID, "no_psn"),
    ]
    if tag_id
}

CHALLENGE_MAP: dict[str, str] = {
    tag_id: attr
    for tag_id, attr in [
        (CHALLENGE_TAG_ID, "challenge"),
        (LEGACY_TAG_ID, "legacy"),
        (PERSONAL_TAG_ID, "personal"),
    ]
    if tag_id
}


# MARK: - MODULE LOAD COMPLETION
console.log("[success]✅ Configuration module loaded successfully.[/success]")
