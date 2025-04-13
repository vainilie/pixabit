# pixabit/config.py
"""
Loads configuration settings for the Pixabit application from a .env file. This module is responsible for:
1.  Locating the `.env` file expected to be in the project's root directory (one level up from this script's parent directory).
2.  Checking if the `.env` file exists and prompting the user to create it interactively using functions from `.auth_file` if it's missing.
3.  Loading the environment variables from the `.env` file using `python-dotenv`.
4.  Making key configuration values available as Python constants within the application, particularly Habitica credentials and various specific Tag IDs.
Constants Defined:
    - HABITICA_USER_ID (str | None): The user's Habitica User ID.
    - HABITICA_API_TOKEN (str | None): The user's Habitica API Token.
    - CHALLENGE_TAG_ID (str | None): Tag ID for Challenge tasks.
    - PERSONAL_TAG_ID (str | None): Tag ID for general Personal tasks.
    - PSN_TAG_ID (str | None): Tag ID for PlayStation related tasks.
    - NOT_PSN_TAG_ID (str | None): Tag ID for tasks explicitly not related to PlayStation.
    - NO_ATTR_TAG_ID (str | None): Tag ID for tasks with no specific attribute assigned.
    - ATTR_TAG_STR_ID (str | None): Tag ID for tasks assigned to Strength attribute.
    - ATTR_TAG_INT_ID (str | None): Tag ID for tasks assigned to Intelligence attribute.
    - ATTR_TAG_CON_ID (str | None): Tag ID for tasks assigned to Constitution attribute.
    - ATTR_TAG_PER_ID (str | None): Tag ID for tasks assigned to Perception attribute.
Usage:
    Import required constants directly from this module:
    >>> from pixabit import config
    >>> user_id = config.HABITICA_USER_ID
    >>> str_tag = config.ATTR_TAG_STR_ID
"""

import os
from pathlib import Path
from typing import Optional  # Use Optional for type hinting clarity

from dotenv import load_dotenv

from .config_auth import check_env_file
from .utils.display import console, print

# >> .env File Path Calculate
# Calculate the path to the .env file. Assumes this config.py is inside a subfolder (e.g., 'pixabit') and the .env file resides in the parent directory (project root).

try:
    # Resolve ensures the path is absolute before going parent.parent
    env_path = Path(__file__).resolve().parent.parent / ".env"

except NameError:
    # Fallback if __file__ is not defined (e.g., interactive session)
    env_path = Path(".").resolve() / ".env"  # Check in current working dir
    console.log(
        f"[warning]🚨 Warning: __file__ not defined, assuming .env is in current directory:[/] [file]{env_path}[/file]"
    )

# >> Ensure .env File Exists
# Check for the .env file and prompt for creation if it doesn't exist. This should happen *before* attempting to load it.
check_env_file(filename=env_path)  # Pass the calculated Path object

# >> Load Environment Variables ---
# Load variables from the specified .env file into the environment. If the file doesn't exist (e.g., user skipped creation), this will load nothing but won't raise an error. Subsequent getenv calls will return None.
console.log(f"⌛ Loading environment variables from: [file]{env_path}[/]")

# verbose=True logs which file is loaded by python-dotenv

loaded = load_dotenv(dotenv_path=env_path, verbose=True, override=False)

if not loaded:
    console.log(
        f"[warning]🚨 Warning:[/warning] .env file not found at {env_path} or is empty."
    )

# >> APPLICATION CONSTANTS
# --- Habitica API Credentials ---
HABITICA_USER_ID: Optional[str] = os.getenv("HABITICA_USER_ID")
HABITICA_API_TOKEN: Optional[str] = os.getenv("HABITICA_API_TOKEN")

# >> Specific Tag IDs ---
# These should correspond to Tag UUIDs created within Habitica by the user.
# General Task Tags
CHALLENGE_TAG_ID: Optional[str] = os.getenv(
    "CHALLENGE_TAG_ID"
)  # For tasks originating from challenges
PERSONAL_TAG_ID: Optional[str] = os.getenv(
    "PERSONAL_TAG_ID"
)  # For general personal tasks (if used)

# Challenge Tags (Example: Poison)
PSN_TAG_ID: Optional[str] = os.getenv("PSN_TAG_ID")  # Poison related tasks
NOT_PSN_TAG_ID: Optional[str] = os.getenv(
    "NOT_PSN_TAG_ID"
)  # Tasks explicitly NOT PSN related

# Attribute Assignment Tags (Used for assigning rewards/tasks to attributes)
NO_ATTR_TAG_ID: Optional[str] = os.getenv(
    "NO_ATTR_TAG_ID"
)  # Task has no specific attribute target
ATTR_TAG_STR_ID: Optional[str] = os.getenv(
    "ATTR_TAG_STR_ID"
)  # Task targets Strength (STR)
ATTR_TAG_INT_ID: Optional[str] = os.getenv(
    "ATTR_TAG_INT_ID"
)  # Task targets Intelligence (INT)
ATTR_TAG_CON_ID: Optional[str] = os.getenv(
    "ATTR_TAG_CON_ID"
)  # Task targets Constitution (CON)
ATTR_TAG_PER_ID: Optional[str] = os.getenv(
    "ATTR_TAG_PER_ID"
)  # Task targets Perception (PER)


# >> Validate Loaded Variables
# Check if essential variables were loaded successfully

if not HABITICA_USER_ID or not HABITICA_API_TOKEN:
    console.log("\n" + "=" * 60)
    console.log(
        " [error]🚨 Error: HABITICA_USER_ID or HABITICA_API_TOKEN not found![/]"
    )
    console.log(f" Please ensure they are correctly set in the '{env_path.name}' file.")
    console.log(f" Location checked: {env_path}")
    console.log(
        " You may need to run the setup script (e.g., auth_file creation) again."
    )
    console.log("=" * 60 + "\n")

    # Optionally raise an exception to halt execution if credentials are vital
    # raise ValueError("Missing Habitica credentials in .env file.")

# Example of another potential config value (remains commented out)
# DEFAULT_BACKUP_FOLDER = "hab_backups"

console.log("[success]✅ Configuration module loaded.[/]")
