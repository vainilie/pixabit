import requests
import time
from pyrate_limiter import Duration, RequestRate, Limiter
from basis.auth_keys import get_user_id, get_api_token

rate_limits = (RequestRate(29, Duration.MINUTE), )  # 30 requests per minute
limiter = Limiter(*rate_limits)

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
    time.sleep(60 / 29)  # Sleep to comply with rate limits
    url = BASEURL + endpoint
    response = requests.request(method, url, headers=HEADERS, json=data)
    response_data = response.json()
    if not response.ok:
        raise requests.exceptions.RequestException(
            f"API Error: {response_data['error']}")
    return response_data
