# pixabit/__init__.py
"""Pixabit Package Initialization.

This package provides CLI tools for interacting with the Habitica API.
"""

# --- Define Package Metadata ---
__version__ = "0.1.0"  # Example version, update as needed
__author__ = "Your Name / Alias"
__email__ = "your.email@example.com"  # Optional

# --- Expose Key Components (Optional but good practice) ---
# This makes it easier for users (or other parts of your code)
# to import the main classes directly from the package root.
# try:
#     from .api import HabiticaAPI
#     from .challenge_backupper import ChallengeBackupper
#     from .cli.app import CliApp
#     from .config import HABITICA_API_TOKEN, HABITICA_USER_ID  # Expose essential config
#     from .data_processor import TaskProcessor
#     from .tag_manager import TagManager

#     # Add other classes/functions you want easily accessible
# except ImportError:
#     # Handle potential circular imports or issues during setup/testing
#     # Usually safe to ignore here if setup ensures things exist later
#     # print(f"Warning: Could not pre-import all pixabit components in __init__.py: {e}")
#     pass

# --- Define what 'from pixabit import *' imports (Optional) ---
# Generally discouraged, but can be defined if needed.
# __all__ = [
#     "HabiticaAPI",
#     "CliApp",
#     "TaskProcessor",
#     "TagManager",
#     "ChallengeBackupper",
#     "HABITICA_USER_ID",
#     "HABITICA_API_TOKEN",
# ]

# --- Package Level Logging Setup (Optional) ---
# import logging
# logging.getLogger(__name__).addHandler(logging.NullHandler())
# This prevents library code from adding handlers if the application doesn't configure logging.

print(f"Pixabit package initialized (version {__version__})")  # Optional confirmation
