# previous_tui_files/auth_file.py (LEGACY CONFIG - .ini based)

# SECTION: MODULE DOCSTRING
"""
LEGACY: Manages authentication configuration using `.ini` file format.

Provides functions to create and read credentials (`user`, `token`) and tag IDs
from a specified `.ini` file. This approach is **DEPRECATED** in favor of the
`.env` based configuration handled by `cli/config.py` and `cli/config_auth.py`.
Kept for reference only.
"""

# SECTION: IMPORTS
import configparser
import os.path
from typing import Any # Added Any

# Local Imports (These point to OLD structure - DEPRECATED)
# from heart.TUI.rich_utils import Confirm, Prompt, print # Old Rich utils

# Define dummy fallbacks
try:
    from pixabit.cli.rich_utils_fallback import Confirm, Prompt, print # Use fallback Rich utils
except ImportError:
     class Confirm: @staticmethod # type: ignore
     def ask(*a,**kw): return False
     class Prompt: @staticmethod # type: ignore
     def ask(*a,**kw): return ""
     print=builtins.print # type: ignore

# SECTION: CONSTANTS
DEFAULT_CONFIG_FILE_INI = "auth.ini" # Use different name to avoid clash

# SECTION: LEGACY FUNCTIONS

# FUNC: create_auth_file (Legacy - .ini)
def create_auth_file_legacy(filename: str = DEFAULT_CONFIG_FILE_INI) -> None: # Renamed
    """LEGACY: Create an auth config file using configparser (.ini format)."""
    print(f"--- Legacy .ini Auth File Creation ({filename}) ---")
    if Confirm.ask("Help create the file?", default=True):
        input_userid = Prompt.ask("Enter Habitica User ID", default="PLACEHOLDER_USER_ID")
        input_apitoken = Prompt.ask("Enter API Token", default="PLACEHOLDER_API_TOKEN")
    else:
        input_userid = "PLACEHOLDER_USER_ID"
        input_apitoken = "PLACEHOLDER_API_TOKEN"

    config = configparser.ConfigParser()
    config["habitica"] = {"user": input_userid, "token": input_apitoken}
    config["challenge_tags"] = {"challenge": "", "owned": ""}
    config["attributes_tags"] = {"STR": "", "INT": "", "CON": "", "PER": "", "NOT_ATR": ""}

    try:
        with open(filename, "w", encoding="utf-8") as configfile:
            config.write(configfile)
        print(f"✅ Legacy config file '{filename}' created/updated.")
    except OSError as e:
         print(f"❌ Error writing legacy config file '{filename}': {e}")

# FUNC: get_key_from_config (Legacy - .ini)
def get_key_from_config_legacy(section: str, key: str, filename: str = DEFAULT_CONFIG_FILE_INI) -> Optional[str]: # Renamed, added Optional
    """LEGACY: Get a key value from the .ini config file."""
    config = configparser.ConfigParser()
    try:
        read_ok = config.read(filename, encoding='utf-8')
        if not read_ok:
             # print(f"Warning: Could not read legacy config file '{filename}'")
             return None
        return config.get(section, key, fallback=None) # Use get with fallback
    except (configparser.Error, KeyError, Exception) as exc:
        # print(f"Error reading legacy config [{section}][{key}] from {filename}: {exc}")
        return None

# FUNC: check_auth_file (Legacy - .ini)
def check_auth_file_legacy(filename: str = DEFAULT_CONFIG_FILE_INI) -> None: # Renamed
    """LEGACY: Check if the .ini auth file exists and create if missing."""
    print(f"Checking for legacy config file '{filename}'...")
    if not os.path.exists(filename):
        print(f"File '{filename}' doesn't exist.")
        create_auth_file_legacy(filename)
    else:
        print(f"File '{filename}' exists.")

# FUNC: create_tags_file (Legacy - Unclear purpose, likely redundant)
# def create_tags_file(filename=DEFAULT_CONFIG_FILE_INI): ... # Seems duplicate of create_auth_file

