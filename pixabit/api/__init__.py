# pixabit/habitica/__init__.py

# Expose key components for easier import
# Example: from pixabit.habitica import HabiticaClient, HabiticaAPIError

from .client import HabiticaClient
from .exception import HabiticaAPIError
from .habitica_api import HabiticaAPI, HabiticaConfig

__all__ = [
    "HabiticaAPI",
    "HabiticaClient",
    "HabiticaConfig",
    "HabiticaAPIError",
]
