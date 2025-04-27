# pixabit/habitica/client.py

# SECTION: MODULE DOCSTRING
"""Defines the main HabiticaClient integrating all API functionalities via mixins."""

# SECTION: IMPORTS
from .exception import HabiticaAPIError  # Import Exception for potential use
from .habitica_api import HabiticaAPI
from .mixin.challenge_mixin import ChallengesMixin
from .mixin.message_mixin import MessageMixin
from .mixin.party_mixin import PartyMixin
from .mixin.tag_mixin import TagMixin
from .mixin.task_mixin import TasksMixin
from .mixin.user_mixin import UserMixin

# SECTION: CLIENT CLASS


# KLASS: HabiticaClient
class HabiticaClient(
    # Order influences Method Resolution Order (MRO), place base API first or last typically
    HabiticaAPI,  # Base API functionality
    ChallengesMixin,
    MessageMixin,
    PartyMixin,
    TagMixin,
    TasksMixin,
    UserMixin,
):
    """A full Habitica API Client combining base API access with specific endpoint methods.

    Inherits authentication, request logic, and rate limiting from HabiticaAPI,
    and specific API call methods (like get_tasks, get_user_data, etc.) from the Mixin classes.
    """

    # FUNC: __init__ (Optional)
    # Inherits __init__ from HabiticaAPI. Add a custom one if needed.
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     # Add any client-specific initialization here
    #     log.info("HabiticaClient fully initialized.")

    # Methods from mixins and HabiticaAPI are directly available on instances
    # e.g., client = HabiticaClient(...)
    # await client.get_user_data()
    # await client.get_tasks()
    # await client.get_party_data()
    # ... etc ...

    pass  # No additional methods needed here currently
