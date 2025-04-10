# api_health_check.py
# ─── Api Check Module ─────────────────────────────────────────────────────────
# Contains check_api_status function to check the status of the Habitica API.
# ──────────────────────────────────────────────────────────────────────────────


"""Check the status of the Habitica API."""

import requests
from rich import print as rprint
from heart.basis import api_method, auth_file
from trogon import tui

@tui()
@click.group(...)
def cli():
    ...

def check_api_status():
    """Check if the Habitica API is working and can be used.

    Make a GET request to the 'status' endpoint and check if the response is valid.
    If so, print a success message and return True. If not, print an error message
    and return False.

    If there is a connection error when making the request, print an error message
    with the error details.

    Before making the request, ensure that the authentication file exists and
    contains valid information.
    """

    # Ensure authentication file exists and contains valid information
    auth_file.check_auth_file()

    try:
        # Make a simple GET request to the 'user' endpoint
        response = api_method.get("status")
        # Check if response is valid
        if response and response.get("data").get("status") == "up":
            rprint("[b #8ccf7e]:heavy_check_mark: Habitica API is working![/]")
            return True
        else:
            rprint(
                ":x: [b]Error[/]: Unable to fetch user data, API might not be working."
            )
            return False

    except requests.exceptions.RequestException as e:
        rprint(f":x: [b]API Error[/]: Unable to connect to Habitica API. {e}")
        return False
