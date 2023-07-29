import requests
from auth_file import get_key_from_config
from ratelimit import limits, sleep_and_retry

# Initialize default values for rate limiting
CALLS = 30
RATE_LIMIT = 60

BASEURL = "https://habitica.com/api/v3/"
USER_ID = get_key_from_config("habitica", "user")
API_TOKEN = get_key_from_config("habitica", "token")
HEADERS = {
    "x-api-user": USER_ID,
    "x-api-key": API_TOKEN,
    "Content-Type": "application/json",
}


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


def get(text):
    """
    Make a GET request to the Habitica API with rate limiting.

    Args:
        text (str): The endpoint or type of data to get from the API.

    Returns:
        dict: The JSON response from the API.

    Raises:
        requests.exceptions.RequestException: If there is an error in the API response.
    """
    return make_api_request("GET", text)


def post(text):
    """
    Make a POST request to the Habitica API with rate limiting.

    Args:
        text (str): The endpoint or type of data to post to the API.

    Returns:
        dict: The JSON response from the API.

    Raises:
        requests.exceptions.RequestException: If there is an error in the API response.
    """
    return make_api_request("POST", text)
