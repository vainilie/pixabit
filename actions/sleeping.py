# sleeping.py - Module

from core import habitica_api
from utils.rich_utils import Confirm, print


def toggle_sleeping_status(on: str, off: str) -> None:
    """
    Toggle sleeping status for Habitica.

    This function allows the user to toggle their sleeping status on Habitica.
    It prompts the user to confirm the change and then makes a request to the
    Habitica API to update the sleeping status accordingly. After toggling the
    status, it displays a message indicating the new sleeping status.

    Args:
        on (str): The current "on" status, indicating whether the user is sleeping.
        off (str): The status to toggle to, indicating whether the user is awake.

    Returns:
        None

    Example:
        toggle_sleeping_status("awake", "sleeping")

    Note:
        This function requires the Habitica API to be accessible and the user to
        have proper authentication and authorization.

    Raises:
        requests.exceptions.RequestException: If there is an error in the API response.
    """
    prompt = f"You are {on}. Toggle {off} status?"
    if Confirm.ask(prompt, default=False):
        habitica_api.post("user/sleep")
        print(f"[b]You're now {off} :cherry_blossom:")
    else:
        print(f"[b]OK, you are still {on} :cherry_blossom:")
