"""
This module contains the four basic HTTP methods for interacting with the API.

Args:
    method (str): The HTTP method for the request (GET, POST, PUT, DELETE).
    endpoint (str): The API endpoint.
    data (dict, optional): JSON data for the request payload.

Returns:
    dict: The JSON response data from the API.
"""

from heart.basis.api_request import make_api_request


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
