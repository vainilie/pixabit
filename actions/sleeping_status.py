from core import habitica_api
from utils.rich_utils import Confirm, print


def toggle_sleeping_status(on: str, off: str) -> None:
    """
    Toggle sleeping status for Habitica.

    Args:
        on (str): The current "on" status.
        off (str): The status to toggle to.

    Returns:
        None
    """
    prompt = f"You are {on}. Toggle {off} status?"
    if Confirm.ask(prompt, default=False):
        habitica_api.post("user/sleep")
        print(f"[b]You're now {off} :cherry_blossom:")
    else:
        print(f"[b]OK, you are still {on} :cherry_blossom:")