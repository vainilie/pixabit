#  _           _     _ _   _                         _
# | |         | |   (_) | (_)                       (_)
# | |__   __ _| |__  _| |_ _  ___ __ _    __ _ _ __  _
# | '_ \ / _` | '_ \| | __| |/ __/ _` |  / _` | '_ \| |
# | | | | (_| | |_) | | |_| | (_| (_| | | (_| | |_) | |
# |_| |_|\__,_|_.__/|_|\__|_|\___\__,_|  \__,_| .__/|_|
#                                             | |
#                                             |_|


"""
habitica_api Module
==================

This module provides functions to interact with the Habitica API, allowing the
user to make GET, POST, and DELETE requests to retrieve and manage data on the
Habitica platform. It handles user authentication using configuration values
retrieved from the auth_file module.

The module also includes rate limiting functionality to avoid exceeding the Habitica
API rate limits and getting blocked from making further requests.

Usage:
------
The functions in this module can be used to interact with the Habitica API. Ensure
that the auth_file module has been properly configured with the user ID and API
token before making API requests.

Example:
--------
import habitica_api

# Make a GET request to retrieve user data
response = habitica_api.get("user")
print(response)

# Make a POST request to create a new task
task_data = {
    "text": "New Task",
    "type": "todo",
    "priority": 2
}
response = habitica_api.post("tasks/user", data=task_data)
print(response)
"""


import requests
from core.auth_file import get_key_from_config, create_auth_file
from ratelimit import limits, sleep_and_retry
from utils.rich_utils import print

# Initialize default values for rate limiting
CALLS = 30
RATE_LIMIT = 60


def get_user_id():
    try:
        user_id = get_key_from_config("habitica", "user")
        return user_id
    except KeyError:
        print("Error: User ID not found in configuration file.")
        create_auth_file()
        return "DEFAULT_USER_ID"


def get_api_token():
    try:
        api_token = get_key_from_config("habitica", "token")
        return api_token
    except KeyError:
        print("Error: API token not found in configuration file.")
        create_auth_file()
        return "DEFAULT_API_TOKEN"


BASEURL = "https://habitica.com/api/v3/"
USER_ID = get_user_id()
API_TOKEN = get_api_token()
HEADERS = {
    "x-api-user": USER_ID,
    "x-api-key": API_TOKEN,
    "Content-Type": "application/json",
}


@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT)
def make_api_request(method, endpoint):
    """
    Make an API request to the Habitica API with rate limiting.

    Args:
        method (str): The HTTP method ('GET' or 'POST') for the API request.
        endpoint (str): The endpoint of the Habitica API to interact with.

    Returns:
        dict: The JSON response from the API.

    Raises:
        requests.exceptions.RequestException: If there is an error in the API response.
    """
    check_limit_calls()

    url = BASEURL + endpoint
    response = requests.request(method, url, headers=HEADERS)

    response_data = response.json()
    if not response.ok:
        raise requests.exceptions.RequestException(
            f"API Error: {response_data['error']}"
        )
    
    return response_data


@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT)
def check_limit_calls():
    """
    Empty function used for rate limiting. Decorated by `sleep_and_retry` and `limits`.
    """
    return


@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT)
def get(endpoint):
    """
    Make a GET request to the Habitica API with rate limiting.

    Args:
        endpoint (str): The endpoint or type of data to get from the API.

    Returns:
        dict: The JSON response from the API.

    Raises:
        requests.exceptions.RequestException: If there is an error in the API response.
    """
    return make_api_request("GET", endpoint)


@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT)
def post(endpoint):
    """
    Make a POST request to the Habitica API with rate limiting.

    Args:
        endpoint (str): The endpoint or type of data to post to the API.

    Returns:
        dict: The JSON response from the API.

    Raises:
        requests.exceptions.RequestException: If there is an error in the API response.
    """
    return make_api_request("POST", endpoint)


@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT)
def delete(endpoint):
    """
    Make a DELETE request to the Habitica API with rate limiting.

    Args:
        endpoint (str): The endpoint or type of data to delete to the API.

    Returns:
        dict: The JSON response from the API.

    Raises:
        requests.exceptions.RequestException: If there is an error in the API response.
    """
    return make_api_request("DELETE", endpoint)
