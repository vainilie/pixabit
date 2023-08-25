#  _           _     _ _   _                         _
# | |         | |   (_) | (_)                       (_)
# | |__   __ _| |__  _| |_ _  ___ __ _    __ _ _ __  _
# | '_ \ / _` | '_ \| | __| |/ __/ _` |  / _` | '_ \| |
# | | | | (_| | |_) | | |_| | (_| (_| | | (_| | |_) | |
# |_| |_|\__,_|_.__/|_|\__|_|\___\__,_|  \__,_| .__/|_|
#                                             | |
#                                             |_|

"""
Habitica API Module
===================

This module provides functions to interact with the Habitica API, enabling users
to make GET, POST, PUT, and DELETE requests for retrieving and managing data on
the Habitica platform. User authentication is managed through configuration values
retrieved from the auth_file module.

The module incorporates rate limiting functionality to prevent exceeding the Habitica
API rate limits, thereby avoiding potential blocking from making further requests.

Usage:
------
The functions in this module facilitate interaction with the Habitica API. Before
making API requests, ensure that the auth_file module is properly configured with
the user ID and API token.

Module Structure:
-----------------
- get_user_id(): Retrieves the user ID from the configuration or generates a default ID.
- get_api_token(): Retrieves the API token from the config or generates a default token.
- make_api_request(method, endpoint, data=None): Executes API requests with rate limit.
- delete(endpoint): Sends a DELETE request using make_api_request().
- get(endpoint): Sends a GET request using make_api_request().
- post(endpoint, data=None): Sends a POST request using make_api_request().
- put(endpoint, data=None): Sends a PUT request using make_api_request().

Important Note:
---------------
Configure the auth_file module with valid user credentials before using the functions
in this module. Failing to do so may result in errors or default values being used.

For further information about the Habitica API, visit https://habitica.com/apidoc.

Please keep this module confidential to avoid potential misuse of authentication data.
"""

import requests
import time
from core.auth_file import get_key_from_config, create_auth_file
from utils.rich_utils import print
from pyrate_limiter import Duration, RequestRate, Limiter

rate_limits = (RequestRate(29, Duration.MINUTE),)  # 30 requests per minute
limiter = Limiter(*rate_limits)


def get_user_id():
    """
    Retrieve the user ID from the configuration or generate a default ID.

    Returns:
        str: The user ID.
    """
    try:
        return get_key_from_config("habitica", "user")
    except KeyError:
        print("Error: User ID not found in configuration file.")
        create_auth_file()
        return "DEFAULT_USER_ID"


def get_api_token():
    """
    Retrieve the API token from the configuration or generate a default token.

    Returns:
        str: The API token.
    """
    try:
        return get_key_from_config("habitica", "token")
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


def make_api_request(method, endpoint, data=None):
    """
    Execute an API request with rate limiting.

    Args:
        method (str): The HTTP method for the request (GET, POST, PUT, DELETE).
        endpoint (str): The API endpoint.
        data (dict, optional): JSON data for the request payload.

    Returns:
        dict: The JSON response data from the API.
    """
    time.sleep(60 / 30)
    url = BASEURL + endpoint
    response = requests.request(method, url, headers=HEADERS, json=data)
    response_data = response.json()
    if not response.ok:
        print(response)
        raise requests.exceptions.RequestException(
            f"API Error: {response_data['error']}"
        )
    return response_data


def delete(endpoint):
    """
    Send a DELETE request to the specified endpoint.

    Args:
        endpoint (str): The API endpoint.

    Returns:
        dict: The JSON response data from the API.
    """
    return make_api_request("DELETE", endpoint)


def get(endpoint):
    """
    Send a GET request to the specified endpoint.

    Args:
        endpoint (str): The API endpoint.

    Returns:
        dict: The JSON response data from the API.
    """
    return make_api_request("GET", endpoint)


def post(endpoint, data=None):
    """
    Send a POST request to the specified endpoint.

    Args:
        endpoint (str): The API endpoint.
        data (dict, optional): JSON data for the request payload.

    Returns:
        dict: The JSON response data from the API.
    """
    return make_api_request("POST", endpoint, data=data)


def put(endpoint, data=None):
    """
    Send a PUT request to the specified endpoint.

    Args:
        endpoint (str): The API endpoint.
        data (dict, optional): JSON data for the request payload.

    Returns:
        dict: The JSON response data from the API.
    """
    return make_api_request("PUT", endpoint, data=data)
