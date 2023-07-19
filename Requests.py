import requests
from AuthFile import GetKey
from ratelimit import limits, sleep_and_retry

BASEURL = "https://habitica.com/api/v3/"
USER_ID = GetKey("habitica", "apiUser")
API_TOKEN = GetKey("habitica", "apiToken")
HEADERS = {
    "x-api-user": USER_ID,
    "x-api-key": API_TOKEN,
    "Content-Type": "application/json",
}
CALLS = 30
RATE_LIMIT = 60


@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT)
def CheckLimitCalls():
    """Empty function just to check for calls to API"""
    return


def GetAPI(text):
    """request GET from API (with limits).
    Text is the string of the type of data to get from the API"""
    CheckLimitCalls()
    response = requests.get(BASEURL + text, headers=HEADERS)
    if response.status_code == 400:
        print(response.status_code)
    else:
        return response.json()


def PostAPI(text):
    """request post from API (with limits).
    Text is the string of the type of data to get POST the API"""
    CheckLimitCalls()
    response = requests.post(BASEURL + text, headers=HEADERS)
    if response.status_code == 400:
        print(response.status_code)
    else:
        return response.json()
