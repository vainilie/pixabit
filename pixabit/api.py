# pixabit/api.py
"""
Provides a client class for interacting with the Habitica API v3.

This module contains the `HabiticaAPI` class, which simplifies making calls
to the Habitica API (v3). It handles authentication using User ID and API Token
(read from configuration/environment variables by default via the `.config`
module), implements automatic rate limiting to comply with Habitica's limits (30
requests per minute), and offers both low-level HTTP method wrappers
(GET, POST, PUT, DELETE) and higher-level convenience methods for common
actions like managing tasks, tags, user settings, challenges, party data,
and inbox messages.

Key Features:
- Authentication header management.
- Automatic request rate limiting.
- Wrappers for standard HTTP verbs.
- Convenience methods for most common v3 API endpoints.
- Basic error handling and JSON response parsing.

Requires the 'requests' library. Credentials must be available either via
the associated `config` module (typically loading from a `.env` file containing
`HABITICA_USER_ID` and `HABITICA_API_TOKEN`) or passed directly during
`HabiticaAPI` initialization.

Typical Usage:
    >>> from pixabit.api import HabiticaAPI # Assuming pixabit is importable
    >>> # Assumes config loads credentials from .env
    >>> api = HabiticaAPI()
    >>> user_data = api.get_user_data()
    >>> print(user_data.get('profile', {}).get('name'))
    >>> tasks = api.get_tasks(task_type='todos')
    >>> # api.create_task({'text': 'My new To-Do', 'type': 'todo'}) # Example POST

Classes:
    HabiticaAPI: The main client class for API interactions.
"""

# ─── Imports ──────────────────────────────────────────────────────────────────


import time
from typing import Any, Dict, List, Optional, Union

import requests
from pixabit import config

from .utils.display import console, print

# ─── Import Configuration Loaded From Env File ────────────────────────────────
# Assumes config.py is in the same package (pixabit directory)
# and loads HABITICA_USER_ID and HABITICA_API_TOKEN from .env


# ─── Constants ────────────────────────────────────────────────────────────────


DEFAULT_BASE_URL = "https://habitica.com/api/v3"
# Habitica rate limit: 30 requests per minute. We aim for slightly less.
REQUESTS_PER_MINUTE = 29
MIN_REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE  # Minimum seconds between requests

# ─── Type Alias For API Response ──────────────────────────────────────────────


# Habitica API often returns a dict, but list endpoints (like getting tasks/tags) return lists.
HabiticaApiResponse = Union[Dict[str, Any], List[Dict[str, Any]]]

# ─── HabiticaAPI Class ────────────────────────────────────────────────────────


class HabiticaAPI:
    """
    A client class to interact with the Habitica API v3.

    Handles authentication, makes requests (GET, POST, PUT, DELETE),
    includes basic rate limiting, and provides convenience methods for
    common Habitica operations.

    Credentials (User ID and API Token) are required and loaded from the
    `config` module (which should load them from an .env file) by default,
    or can be passed directly during initialization.

    Navigation Anchors (for VS Code extensions like 'Comment Anchors'):
    ──────────────────────────────────────────────────────────────────────

    - Internal Methods (Rate Limiting, Request Handling)
    - Core HTTP Request Methods (get, post, put, delete)
    - User Methods
    - Task Methods
    - Tag Methods
    - Checklist Methods
    - Challenge Methods
    - Group & Party Methods
    - Inbox Methods

    Convenience Method Overview:
    ──────────────────────────────────────────────────────────────────────

    User:
        get_user_data()
        update_user(update_data)
        set_custom_day_start(hour)
        toggle_user_sleep()
    Tasks:
        get_tasks(task_type=None)
        create_task(data)
        update_task(task_id, data)
        delete_task(task_id)
        score_task(task_id, direction='up')
        set_attribute(task_id, attribute)
        move_task_to_position(task_id, position)
    Tags:
        get_tags()
        create_tag(name)
        update_tag(tag_id, name)
        add_tag(task_id, tag_id)       # Task-Tag link
        delete_tag(task_id, tag_id)     # Task-Tag link (confusing name, maybe rename?)
        # delete_tag_globally(tag_id) # Note: API might lack a direct global tag delete? Check docs.
    Checklists:
        add_checklist_item(task_id, text)
        update_checklist_item(task_id, item_id, text)
        delete_checklist_item(task_id, item_id)
        score_checklist_item(task_id, item_id)
    Challenges:
        get_challenges(member_only=True)
        create_challenge(data)
        get_challenge_tasks(challenge_id)
        unlink_task_from_challenge(task_id, keep='keep')
        unlink_all_challenge_tasks(challenge_id, keep='keep')
    Groups & Party:
        get_party_data()
        get_quest_status()
    Inbox:
        get_inbox_messages(page=0)

    """

    BASE_URL = DEFAULT_BASE_URL

    # ─── Initialization Attributes ────────────────────────────────────────────────

    def __init__(
        self,
        user_id: Optional[str] = None,
        api_token: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        # Accept console instance or create one
        console: Optional[console] = None,
    ):
        """
        Initializes the HabiticaAPI client.

        Reads credentials from the config module (loaded from .env) if not
        provided explicitly. Sets up headers and rate limiting state.

        Args:
            user_id (Optional[str]): Habitica User ID. Defaults to value from config.
            api_token (Optional[str]): Habitica API Token. Defaults to value from config.
            base_url (str): The base URL for the Habitica API.
                               Defaults to DEFAULT_BASE_URL.

        Raises:
            ValueError: If User ID or API Token is missing after checking args and config.
        """
        self.user_id = user_id or config.HABITICA_USER_ID
        self.api_token = api_token or config.HABITICA_API_TOKEN
        self.base_url = base_url

        self.console = console

        if not self.user_id or not self.api_token:
            raise ValueError(
                "Habitica User ID and API Token are required. "
                "Ensure they are set in your .env file or passed directly."
            )

        self.headers = {
            "x-api-user": self.user_id,
            "x-api-key": self.api_token,
            "Content-Type": "application/json",
        }

        # Rate limiting attributes
        self.last_request_time: float = 0.0
        # Using time.monotonic() for rate limiting as it's suitable for measuring intervals
        self.request_interval: float = MIN_REQUEST_INTERVAL

    # ─── Internal Methods ─────────────────────────────────────────────────────────
    # --- Add DEBUG prints inside ---

    def _wait_for_rate_limit(self) -> None:
        """
        Checks time since last request and sleeps if necessary based purely on timing.
        Does not produce any console output during wait.
        """
        current_time = time.monotonic()
        # Use getattr for safety, providing default if attributes somehow missing
        last_request_time = getattr(self, "last_request_time", 0.0)
        # Calculate default interval based on REQUESTS_PER_MINUTE constant if needed
        request_interval = getattr(self, "request_interval", (60.0 / 29.0))

        time_since_last = current_time - last_request_time

        if time_since_last < request_interval:
            wait_time = request_interval - time_since_last
            # --- Just sleep, no print or status ---
            time.sleep(wait_time)
            # ------------------------------------

        # Update last request time *after* the potential wait
        self.last_request_time = time.monotonic()

    # --- TEMPORARY SIMPLIFIED _request v2 ---

    def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> HabiticaApiResponse:
        """
        Internal method to make an API request with rate limiting and error handling.
        Handles Habitica's standard response wrapper.

        Args:
            method: HTTP method (e.g., 'GET', 'POST', 'PUT', 'DELETE').
            endpoint: API endpoint path (e.g., '/user', '/tasks/user').
            **kwargs: Additional arguments passed to `requests.request`
                      (e.g., `json` for POST/PUT body, `params` for GET query string).

        Returns:
            The JSON response data from the API, typically the content of the 'data' key.
            Can be a dictionary or a list depending on the endpoint.
            Returns an empty dict `{}` for responses with no content (e.g., HTTP 204).

        Raises:
            requests.exceptions.RequestException: For network issues, timeouts, or API errors.
            ValueError: For invalid JSON responses or unexpected structures.
        """
        self._wait_for_rate_limit()  # Call the simplified version here

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        response: Optional[requests.Response] = None

        # Optional: Print request details for debugging
        # print(f"DEBUG: Requesting {method} {url} with kwargs: {kwargs}")

        try:
            kwargs.setdefault("timeout", 120)  # Keep longer timeout
            response = requests.request(method, url, headers=self.headers, **kwargs)

            # Optional: Print basic response info
            # print(f"DEBUG: Response Status Code: {response.status_code if response else 'N/A'}")

            response.raise_for_status()  # Check for HTTP errors first

            if not response.content or response.status_code == 204:
                return {}  # Handle No Content

            response_data = response.json()

            # --- Handle Habitica's standard { "success": bool, "data": ... } wrapper ---
            if isinstance(response_data, dict) and "success" in response_data:
                if response_data["success"]:
                    # Return the actual data payload from the "data" key
                    return response_data.get("data", {})  # <<< Extracts data payload
                else:
                    # Handle { "success": false, ... }
                    error_type = response_data.get("error", "Unknown Habitica Error")
                    message = response_data.get("message", "No message provided.")
                    raise requests.exceptions.RequestException(
                        f"Habitica API Error ({response.status_code}): {error_type} - {message}"
                    )
            else:
                # Handle successful responses (2xx) that *don't* use the 'success' wrapper
                # Or cases where 'data' might be missing but success is implied by 2xx status
                print(
                    f"Warning: API response for {method} {endpoint} did not match standard "
                    "{'success': ..., 'data': ...} structure. Returning raw valid JSON."
                )
                if isinstance(response_data, (dict, list)):
                    return response_data
                else:
                    raise ValueError(
                        f"Unexpected non-dict/non-list JSON structure received "
                        f"from {method} {endpoint}: {type(response_data)}"
                    )
            # --------------------------------------------------------------------------

        except requests.exceptions.HTTPError as http_err:
            print(f"DEBUG: Caught HTTPError: {http_err}")
            error_details = f"HTTP Error: {http_err}"
            # Use http_err.response which should exist
            if http_err.response is not None:
                response = http_err.response
                print(f"DEBUG: Response Status: {response.status_code}")
                try:
                    err_data = response.json()
                    error_type = err_data.get("error", "N/A")
                    message = err_data.get("message", "N/A")
                    error_details += (
                        f" - API Response: Error='{error_type}', Message='{message}'"
                    )
                except requests.exceptions.JSONDecodeError:
                    error_details += (
                        f" - Response body (non-JSON): {response.text[:200]}"
                    )
            raise requests.exceptions.RequestException(error_details) from http_err

        except requests.exceptions.Timeout as timeout_err:
            print(f"DEBUG: Caught Timeout: {timeout_err}")
            msg = f"Error: Request timed out after {kwargs.get('timeout')}s for {method} {endpoint}: {timeout_err}"
            print(msg)
            raise requests.exceptions.RequestException(msg) from timeout_err

        except requests.exceptions.RequestException as req_err:
            # Catch other request errors (connection, DNS, etc.)
            print(
                f"DEBUG: Caught other RequestException: {type(req_err).__name__} - {req_err}"
            )
            msg = f"Error during API request to {method} {endpoint}: {req_err}"
            print(msg)
            raise  # Re-raise

        except requests.exceptions.JSONDecodeError as json_err:
            # OK status but invalid JSON body
            msg = f"Error: Could not decode JSON response from {method} {endpoint}. {json_err}"
            print(msg)
            # Check response exists before accessing attributes
            status = response.status_code if response is not None else "N/A"
            body = response.text[:200] if response is not None else "N/A"
            print(f"Response status: {status}, Body: {body}")
            raise ValueError(
                f"Invalid JSON received from {method} {endpoint}"
            ) from json_err

        except Exception as e:  # Catch any truly unexpected errors
            print(
                f"DEBUG: Caught unexpected error in _request: {type(e).__name__} - {e}"
            )
            traceback.print_exc()  # Print full traceback for these cases
            raise  # Re-raise the unexpected error

    def _request_original(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> HabiticaApiResponse:
        """
        Internal method to make an API request with rate limiting and error handling.

        Args:
            method: HTTP method (e.g., 'GET', 'POST', 'PUT', 'DELETE').
            endpoint: API endpoint path (e.g., '/user', '/tasks/user').
            **kwargs: Additional arguments passed to `requests.request`
                      (e.g., `json` for POST/PUT body, `params` for GET query string).

        Returns:
            The JSON response data from the API, typically the content of the
            'data' key if present in a standard Habitica success response.
            Can be a dictionary or a list depending on the endpoint.
            Returns an empty dict `{}` for responses with no content (e.g., HTTP 204).

        Raises:
            requests.exceptions.RequestException: If the request fails due to network issues,
                                                  timeouts, or if the API returns an HTTP
                                                  error status (4xx or 5xx). Includes details
                                                  from the Habitica error response if possible.
            ValueError: If the API response is not valid JSON or if the structure
                        is unexpected after a successful HTTP status.
        """
        self._wait_for_rate_limit()

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        response: Optional[requests.Response] = None  # Define before try block

        # Print request details for debugging before making the call
        print(f"DEBUG: Requesting {method} {url} with kwargs: {kwargs}")

        try:
            # Increase default timeout for potentially large responses
            kwargs.setdefault("timeout", 120)  # Set default timeout to 120 seconds
            response = requests.request(method, url, headers=self.headers, **kwargs)

            # Print basic response info immediately after getting it
            print(f"DEBUG: Response received: {response}, Type: {type(response)}")

            # Check for HTTP errors first
            response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses

            # Handle successful responses with no content (HTTP 204)
            if not response.content:
                print(
                    f"DEBUG: Received empty response body (Status: {response.status_code}) for {method} {endpoint}."
                )
                return {}  # Return empty dict for successful no-content responses

            # Try to parse JSON for responses with content
            response_data = response.json()

            # Handle Habitica's typical success wrapper { "success": bool, "data": ..., ... }
            if isinstance(response_data, dict) and "success" in response_data:
                if response_data["success"]:
                    # Return the actual data payload, default to empty dict if 'data' key is missing
                    return response_data.get("data", {})
                else:
                    # Handle cases where success is explicitly false
                    error_type = response_data.get("error", "Unknown Habitica Error")
                    message = response_data.get("message", "No message provided.")
                    # Raise RequestException for consistency in error handling
                    raise requests.exceptions.RequestException(
                        f"Habitica API Error ({response.status_code}): {error_type} - {message}"
                    )
            else:
                # Handle successful responses that don't use the 'success' wrapper
                # (e.g., endpoints returning a list directly like /tasks/user or /tags)
                print(
                    f"Warning: API response for {method} {endpoint} does not match "
                    "{'success': ..., 'data': ...} structure. Returning raw JSON."
                )
                # Return the parsed data if it's a dict or list
                if isinstance(response_data, (dict, list)):
                    return response_data
                else:
                    # Raise error if JSON is valid but not dict/list (unexpected)
                    raise ValueError(
                        f"Unexpected non-dict/non-list JSON structure received "
                        f"from {method} {endpoint}: {type(response_data)}"
                    )

        except requests.exceptions.HTTPError as http_err:
            # Handle HTTP errors (4xx, 5xx) caught by raise_for_status()
            print(f"DEBUG: Caught HTTPError: {http_err}")
            # Initialize error details with the basic HTTP error info
            error_details = f"HTTP Error: {http_err}"
            # 'response' should be available via http_err.response
            if http_err.response is not None:
                response = http_err.response  # Use the response from the exception
                print(f"DEBUG: Response object exists. Status: {response.status_code}")
                try:
                    # Try to get more specific error details from response body
                    err_data = response.json()
                    error_type = err_data.get("error", "N/A")
                    message = err_data.get("message", "N/A")
                    error_details += (
                        f" - API Response: Error='{error_type}', Message='{message}'"
                    )
                except requests.exceptions.JSONDecodeError:
                    # Handle cases where the error response itself isn't valid JSON
                    error_details += f" - Response body (non-JSON): {response.text[:200]}"  # Limit length
            else:
                # Should typically not happen with HTTPError, but check just in case
                print("DEBUG: Response object is None during HTTPError handling!")

            print(f"Error during API request to {method} {endpoint}: {error_details}")
            # Raise a more general RequestException containing the details
            raise requests.exceptions.RequestException(error_details) from http_err

        except requests.exceptions.Timeout as timeout_err:
            # Catch timeouts specifically
            print(f"DEBUG: Caught Timeout: {timeout_err}")
            msg = f"Error: Request timed out after {kwargs.get('timeout')}s for {method} {endpoint}: {timeout_err}"
            print(msg)
            raise requests.exceptions.RequestException(msg) from timeout_err

        except requests.exceptions.RequestException as req_err:
            # Catch other request errors (connection, DNS, etc.)
            print(
                f"DEBUG: Caught other RequestException: {type(req_err).__name__} - {req_err}"
            )
            msg = f"Error during API request to {method} {endpoint}: {req_err}"
            print(msg)
            raise  # Re-raise other request-related errors after printing

        except requests.exceptions.JSONDecodeError as json_err:
            # Handle cases where the response status was OK (2xx) but body wasn't valid JSON
            msg = f"Error: Could not decode JSON response from {method} {endpoint}. {json_err}"
            print(msg)
            if response is not None:
                print(
                    f"Response status: {response.status_code}, Body: {response.text[:200]}"
                )  # Limit length
            raise ValueError(
                f"Invalid JSON received from {method} {endpoint}"
            ) from json_err

        except Exception as e:  # Catch any truly unexpected errors
            print(
                f"DEBUG: Caught unexpected error in _request: {type(e).__name__} - {e}"
            )
            traceback.print_exc()  # Print full traceback for these cases
            raise  # Re-raise the unexpected error

    # ─── Core Http Request Methods ────────────────────────────────────────────────

    def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> HabiticaApiResponse:
        """
        Sends a GET request to the specified endpoint.

        Args:
            endpoint (str): The API endpoint path (e.g., '/user').
            params (Optional[Dict[str, Any]]): A dictionary of query parameters
                                                to include in the URL. Defaults to None.

        Returns:
            HabiticaApiResponse: The JSON response data (dict or list).

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        return self._request("GET", endpoint, params=params)

    def post(
        self, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> HabiticaApiResponse:
        """
        Sends a POST request to the specified endpoint.

        Args:
            endpoint (str): The API endpoint path (e.g., '/tasks/user').
            data (Optional[Dict[str, Any]]): A dictionary representing the JSON
                                              payload to send in the request body.
                                              Defaults to None (empty body).

        Returns:
            HabiticaApiResponse: The JSON response data (dict or list).

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        return self._request("POST", endpoint, json=data)

    def put(
        self, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> HabiticaApiResponse:
        """
        Sends a PUT request to the specified endpoint.

        Args:
            endpoint (str): The API endpoint path (e.g., '/tasks/{taskId}').
            data (Optional[Dict[str, Any]]): A dictionary representing the JSON
                                              payload to send in the request body.
                                              Defaults to None.

        Returns:
            HabiticaApiResponse: The JSON response data (dict or list).

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        return self._request("PUT", endpoint, json=data)

    def delete(self, endpoint: str) -> HabiticaApiResponse:
        """
        Sends a DELETE request to the specified endpoint.

        Args:
            endpoint (str): The API endpoint path (e.g., '/tasks/{taskId}').

        Returns:
            HabiticaApiResponse: The JSON response data (usually an empty dict
                                 or a dict indicating success/state).

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        return self._request("DELETE", endpoint)

    # ─── User Methods ─────────────────────────────────────────────────────────────

    def get_user_data(self) -> Dict[str, Any]:
        """
        Retrieves the full user object containing profile, stats, items, etc.

        Corresponds to GET /user.

        Returns:
            Dict[str, Any]: The user data dictionary. Returns an empty dict `{}`
                            if the API returns an unexpected non-dict type.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.get("/user")
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from GET /user, got {type(result)}. Returning empty dict."
        )
        return {}

    def update_user(self, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates general user settings, preferences, or other writable fields.

        Corresponds to PUT /user. Consult Habitica API docs for updatable fields.
        Common examples: 'preferences.XYZ', 'flags.XYZ', 'profile.name'.

        Args:
            update_data (Dict[str, Any]): Dictionary containing the fields to update
                                          and their new values. (e.g., `{"preferences.timezoneOffset": -6}`)

        Returns:
            Dict[str, Any]: The updated user data dictionary subset returned by the API.
                            Returns empty dict `{}` on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.put("/user", data=update_data)
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from PUT /user, got {type(result)}. Returning empty dict."
        )
        return {}

    def set_custom_day_start(self, hour: int) -> Dict[str, Any]:
        """
        Sets the user's custom day start hour (CDS).

        Uses `update_user` to modify 'preferences.dayStart'.

        Args:
            hour (int): The hour (0-23) for the custom day start.

        Returns:
            Dict[str, Any]: The API response from updating the user setting.

        Raises:
            ValueError: If the hour is outside the valid range (0-23).
            requests.exceptions.RequestException: For network or API errors.
        """
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        return self.update_user({"preferences.dayStart": hour})

    def toggle_user_sleep(self) -> Dict[str, Any]:
        """
        Toggles the user's sleep status (inn/tavern rest).

        Corresponds to POST /user/sleep.

        Returns:
            Dict[str, Any]: A dictionary usually containing the user's updated
                            `preferences.sleep` status. Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.post("/user/sleep")
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from POST /user/sleep, got {type(result)}. Returning empty dict."
        )
        return {}

    # ─── Task Methods ─────────────────────────────────────────────────────────────

    def get_tasks(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Gets user tasks, optionally filtered by type.

        Corresponds to GET /tasks/user.

        Args:
            task_type (Optional[str]): Filter tasks by type ('habits', 'dailys',
                                       'todos', 'rewards'). Defaults to None (all types).

        Returns:
            List[Dict[str, Any]]: A list of task objects. Returns an empty list `[]`
                                  if the API returns an unexpected non-list type.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        params = {"type": task_type} if task_type else None
        tasks_data = self.get("/tasks/user", params=params)
        if isinstance(tasks_data, list):
            return tasks_data
        print(
            f"Warning: Expected list from GET /tasks/user, got {type(tasks_data)}. Returning empty list."
        )
        return []

    def create_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a new task (Habit, Daily, To-Do, or Reward).

        Corresponds to POST /tasks/user. The `data` dictionary must include
        'text' (task name) and 'type' ('habit', 'daily', 'todo', 'reward').
        Other optional fields: 'notes', 'priority', 'attribute', 'tags' (list of tag IDs),
        'checklist' (list of { text: str, completed: bool }), etc.

        Args:
            data (Dict[str, Any]): Dictionary containing the properties for the new task.
                                   Requires at least 'text' and 'type'.

        Returns:
            Dict[str, Any]: The newly created task object. Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors (e.g., missing required fields).
            ValueError: For invalid JSON responses.
        """
        if "text" not in data or "type" not in data:
            print("Warning: Task creation data should include 'text' and 'type'.")
            # Consider raising ValueError here instead of just printing

        result = self.post("/tasks/user", data=data)
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from POST /tasks/user, got {type(result)}. Returning empty dict."
        )
        return {}

    def update_task(self, task_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates an existing task by its ID.

        Corresponds to PUT /tasks/{taskId}. Consult Habitica API docs for updatable fields.
        Common examples: 'text', 'notes', 'priority', 'attribute', 'checklist'.

        Args:
            task_id (str): The unique identifier of the task to update.
            data (Dict[str, Any]): Dictionary containing the fields to update
                                   and their new values.

        Returns:
            Dict[str, Any]: The updated task object. Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors (e.g., invalid task ID).
            ValueError: For invalid JSON responses.
        """
        result = self.put(f"/tasks/{task_id}", data=data)
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from PUT /tasks/{task_id}, got {type(result)}. Returning empty dict."
        )
        return {}

    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """
        Deletes a specific task by its ID.

        Corresponds to DELETE /tasks/{taskId}.

        Args:
            task_id (str): The unique identifier of the task to delete.

        Returns:
            Dict[str, Any]: Usually an empty dictionary `{}` upon success, or may
                            contain context like remaining tasks. Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors (e.g., invalid task ID).
            ValueError: For invalid JSON responses.
        """
        result = self.delete(f"/tasks/{task_id}")
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from DELETE /tasks/{task_id}, got {type(result)}. Returning empty dict."
        )
        return {}

    def score_task(self, task_id: str, direction: str = "up") -> Dict[str, Any]:
        """
        Scores a task ("clicks" it). Affects user stats and streaks.

        Corresponds to POST /tasks/{taskId}/score/{direction}.

        Args:
            task_id (str): The unique identifier of the task to score.
            direction (str): The direction to score ('up' for positive clicks on
                             Habits/Dailies/Todos, completing Todos/Dailies; 'down'
                             for negative clicks on Habits/Dailies). Defaults to 'up'.

        Returns:
            Dict[str, Any]: A dictionary containing details about the score impact
                            (delta, user stats, etc.). Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            ValueError: If `direction` is not 'up' or 'down'.
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        if direction not in ["up", "down"]:
            raise ValueError("Direction must be 'up' or 'down'")
        result = self.post(f"/tasks/{task_id}/score/{direction}")
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from POST /tasks/.../score/{direction}, got {type(result)}. Returning empty dict."
        )
        return {}

    def set_attribute(self, task_id: str, attribute: str) -> Dict[str, Any]:
        """
        Sets the primary attribute ('str', 'int', 'con', 'per') for a reward task.

        Uses `update_task` to modify the task's 'attribute' field.

        Args:
            task_id (str): The unique identifier of the reward task.
            attribute (str): The attribute to set ('str', 'int', 'con', 'per').

        Returns:
            Dict[str, Any]: The updated task object.

        Raises:
            ValueError: If `attribute` is not one of the valid options.
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        if attribute not in ["str", "int", "con", "per"]:
            raise ValueError("Attribute must be one of 'str', 'int', 'con', 'per'")
        return self.update_task(task_id, {"attribute": attribute})

    def move_task_to_position(self, task_id: str, position: int) -> Dict[str, Any]:
        """
        Moves a task to a specific position within its list (0 is the top).

        Corresponds to POST /tasks/{taskId}/move/to/{position}.

        Args:
            task_id (str): The unique identifier of the task to move.
            position (int): The desired 0-based index for the task. Non-negative.

        Returns:
            Dict[str, Any]: The API response, often contains the new order of tasks
                            or just indicates success. Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses or if `position` is negative.
        """
        if position < 0:
            raise ValueError("Position cannot be negative.")
        # API uses 0-based index directly
        result = self.post(f"/tasks/{task_id}/move/to/{position}")
        # The response format for move is sometimes just { "success": true },
        # _request handles extracting 'data' if present, otherwise returns the raw dict.
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from POST /tasks/.../move/to/{position}, got {type(result)}. Returning empty dict."
        )
        return {}

    # ─── Tag Methods ──────────────────────────────────────────────────────────────

    def get_tags(self) -> List[Dict[str, Any]]:
        """
        Gets all tags created by the user.

        Corresponds to GET /tags.

        Returns:
            List[Dict[str, Any]]: A list of tag objects, each containing 'id' and 'name'.
                                  Returns empty list `[]` on unexpected non-list response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        tags_data = self.get("/tags")
        if isinstance(tags_data, list):
            return tags_data
        print(
            f"Warning: Expected list from GET /tags, got {type(tags_data)}. Returning empty list."
        )
        return []

    def create_tag(self, name: str) -> Dict[str, Any]:
        """
        Creates a new tag.

        Corresponds to POST /tags.

        Args:
            name (str): The name for the new tag.

        Returns:
            Dict[str, Any]: The newly created tag object (with 'id' and 'name').
                            Returns empty dict `{}` on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.post("/tags", data={"name": name})
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from POST /tags, got {type(result)}. Returning empty dict."
        )
        return {}

    def update_tag(self, tag_id: str, name: str) -> Dict[str, Any]:
        """
        Updates the name of an existing tag.

        Corresponds to PUT /tags/{tagId}.

        Args:
            tag_id (str): The unique identifier of the tag to update.
            name (str): The new name for the tag.

        Returns:
            Dict[str, Any]: The updated tag object. Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.put(f"/tags/{tag_id}", data={"name": name})
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from PUT /tags/{tag_id}, got {type(result)}. Returning empty dict."
        )
        return {}

    # Note: Habitica API might lack a dedicated DELETE /tags/{tagId} endpoint for global deletion.
    # Tag deletion seems implicitly handled when no tasks use it, or via challenge edits.

    def add_tag(self, task_id: str, tag_id: str) -> Dict[str, Any]:
        """
        Associates an existing tag with a specific task.

        Corresponds to POST /tasks/{taskId}/tags/{tagId}.

        Args:
            task_id (str): The ID of the task to add the tag to.
            tag_id (str): The ID of the tag to add.

        Returns:
            Dict[str, Any]: API response, usually confirms success or returns updated task tags.
                            Returns empty dict `{}` on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.post(f"/tasks/{task_id}/tags/{tag_id}")
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from POST /tasks/.../tags/..., got {type(result)}. Returning empty dict."
        )
        return {}

    def delete_tag(self, task_id: str, tag_id: str) -> Dict[str, Any]:
        """
        Removes an association between a tag and a specific task.
        This does *not* delete the tag globally.

        Corresponds to DELETE /tasks/{taskId}/tags/{tagId}.

        Args:
            task_id (str): The ID of the task to remove the tag from.
            tag_id (str): The ID of the tag to remove.

        Returns:
            Dict[str, Any]: API response, usually confirms success or returns updated task tags.
                            Returns empty dict `{}` on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.delete(f"/tasks/{task_id}/tags/{tag_id}")
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from DELETE /tasks/.../tags/..., got {type(result)}. Returning empty dict."
        )
        return {}

    # ─── Checklist Methods ────────────────────────────────────────────────────────

    def add_checklist_item(self, task_id: str, text: str) -> Dict[str, Any]:
        """
        Adds a new checklist item to a specific task (Daily or To-Do).

        Corresponds to POST /tasks/{taskId}/checklist.

        Args:
            task_id (str): The ID of the task to add the checklist item to.
            text (str): The text content of the new checklist item.

        Returns:
            Dict[str, Any]: The updated task object, including the modified checklist.
                            Returns empty dict `{}` on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.post(f"/tasks/{task_id}/checklist", data={"text": text})
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from POST /tasks/.../checklist, got {type(result)}. Returning empty dict."
        )
        return {}

    def update_checklist_item(
        self, task_id: str, item_id: str, text: str
    ) -> Dict[str, Any]:
        """
        Updates the text of an existing checklist item within a task.

        Corresponds to PUT /tasks/{taskId}/checklist/{itemId}.

        Args:
            task_id (str): The ID of the task containing the checklist item.
            item_id (str): The ID of the checklist item to update.
            text (str): The new text content for the checklist item.

        Returns:
            Dict[str, Any]: The updated task object. Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.put(f"/tasks/{task_id}/checklist/{item_id}", data={"text": text})
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from PUT /tasks/.../checklist/..., got {type(result)}. Returning empty dict."
        )
        return {}

    def delete_checklist_item(self, task_id: str, item_id: str) -> Dict[str, Any]:
        """
        Deletes a checklist item from a task.

        Corresponds to DELETE /tasks/{taskId}/checklist/{itemId}.

        Args:
            task_id (str): The ID of the task containing the checklist item.
            item_id (str): The ID of the checklist item to delete.

        Returns:
            Dict[str, Any]: The updated task object. Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.delete(f"/tasks/{task_id}/checklist/{item_id}")
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from DELETE /tasks/.../checklist/..., got {type(result)}. Returning empty dict."
        )
        return {}

    def score_checklist_item(self, task_id: str, item_id: str) -> Dict[str, Any]:
        """
        Toggles the completion status (checked/unchecked) of a checklist item.

        Corresponds to POST /tasks/{taskId}/checklist/{itemId}/score.

        Args:
            task_id (str): The ID of the task containing the checklist item.
            item_id (str): The ID of the checklist item to score (toggle).

        Returns:
            Dict[str, Any]: The updated task object, reflecting the checklist change.
                            Returns empty dict `{}` on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.post(f"/tasks/{task_id}/checklist/{item_id}/score")
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from POST /tasks/.../checklist/.../score, got {type(result)}. Returning empty dict."
        )
        return {}

    # ─── Challenge Methods ────────────────────────────────────────────────────────

    def get_challenges(self, member_only: bool = True) -> List[Dict[str, Any]]:
        """
        Retrieves challenges the user is associated with, handling pagination automatically.

        Corresponds to GET /challenges/user.

        Args:
            member_only (bool): If True (default), retrieve only challenges the user
                                is currently a member of. If False, retrieves all
                                challenges owned by or participated in by the user.

        Returns:
            List[Dict[str, Any]]: A list of challenge objects the user is part of.
                                  Returns empty list `[]` if no challenges are found
                                  or if an error occurs during pagination.

        Raises:
            requests.exceptions.RequestException: If the *initial* request fails. Errors
                                                  during pagination are logged but don't
                                                  raise an exception, returning partial results.
            ValueError: If the *initial* JSON response is invalid.
        """
        all_challenges = []
        page_counter = 0
        member_param = "true" if member_only else "false"
        print(
            f"Fetching challenges (member_only={member_only}, handling pagination)..."
        )
        while True:
            try:
                # Use _request directly to handle potential list/dict return types consistently
                challenge_page_data: HabiticaApiResponse = self._request(
                    "GET", f"/challenges/user?member={member_param}&page={page_counter}"
                )

                if isinstance(challenge_page_data, list):
                    if not challenge_page_data:
                        break  # No more challenges on this page, assume end of list
                    all_challenges.extend(challenge_page_data)
                    print(
                        f"  Fetched page {page_counter} ({len(challenge_page_data)} challenges)"
                    )
                    page_counter += 1
                else:
                    # Should not happen with this endpoint if API is consistent, but handle defensively
                    print(
                        f"Warning: Expected list from /challenges/user page {page_counter}, "
                        f"got {type(challenge_page_data)}. Stopping pagination."
                    )
                    break
            except requests.exceptions.RequestException as e:
                # Log error during pagination but don't stop the whole process, return what we have
                print(
                    f"Error fetching challenges page {page_counter}: {e}. Stopping pagination."
                )
                break
            except ValueError as e:
                # Log JSON error during pagination
                print(
                    f"JSON decode error fetching challenges page {page_counter}: {e}. Stopping pagination."
                )
                break

        print(f"Finished fetching challenges. Total found: {len(all_challenges)}")
        return all_challenges

    def create_challenge(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a new challenge.

        Corresponds to POST /challenges. Requires challenge details in the `data` dict,
        such as 'group' (party/guild ID), 'name', 'shortName', 'summary', 'description',
        'prize'. Tasks are added separately.

        Args:
            data (Dict[str, Any]): Dictionary containing the properties for the new challenge.
                                   Consult Habitica API docs for required/optional fields.

        Returns:
            Dict[str, Any]: The newly created challenge object. Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        # Add basic validation if desired (e.g., check for 'group', 'name', 'shortName')
        result = self.post("/challenges", data=data)
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from POST /challenges, got {type(result)}. Returning empty dict."
        )
        return {}

    def get_challenge_tasks(self, challenge_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all tasks belonging to a specific challenge.

        Corresponds to GET /tasks/challenge/{challengeId}.

        Args:
            challenge_id (str): The ID of the challenge whose tasks are to be retrieved.

        Returns:
            List[Dict[str, Any]]: A list of task objects associated with the challenge.
                                  Returns empty list `[]` on unexpected non-list response.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.get(f"/tasks/challenge/{challenge_id}")
        if isinstance(result, list):
            return result
        print(
            f"Warning: Expected list from GET /tasks/challenge/{challenge_id}, got {type(result)}. Returning empty list."
        )
        return []

    def unlink_task_from_challenge(
        self, task_id: str, keep: str = "keep"
    ) -> Dict[str, Any]:
        """
        Unlinks a single task from its challenge, optionally removing it from users.

        Corresponds to POST /tasks/{taskId}/unlink.

        Args:
            task_id (str): The ID of the task to unlink.
            keep (str): Determines the behavior for users who have the task.
                        'keep' (default): Users keep their personal copies of the task.
                        'remove': The task is removed from users' task lists.

        Returns:
            Dict[str, Any]: API response confirming the unlink action. Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            ValueError: If `keep` is not 'keep' or 'remove'.
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        if keep not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")
        # The API uses a query parameter for keep
        result = self.post(f"/tasks/{task_id}/unlink?keep={keep}")
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from POST /tasks/.../unlink, got {type(result)}. Returning empty dict."
        )
        return {}

    def unlink_all_challenge_tasks(
        self, challenge_id: str, keep: str = "keep"
    ) -> Dict[str, Any]:
        """
        Unlinks all tasks associated with a challenge, optionally removing them from users.

        Corresponds to POST /tasks/challenge/{challengeId}/unlink.

        Args:
            challenge_id (str): The ID of the challenge whose tasks should be unlinked.
            keep (str): Determines the behavior for users ('keep' or 'remove'). See
                        `unlink_task_from_challenge` for details. Defaults to 'keep'.

        Returns:
            Dict[str, Any]: API response confirming the bulk unlink action. Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            ValueError: If `keep` is not 'keep' or 'remove'.
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        if keep not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")
        result = self.post(f"/tasks/challenge/{challenge_id}/unlink?keep={keep}")
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from POST /tasks/challenge/.../unlink, got {type(result)}. Returning empty dict."
        )
        return {}

    # ─── Party Methods ────────────────────────────────────────────────────────────

    def get_party_data(self) -> Dict[str, Any]:
        """
        Gets data about the user's current party, including members and quest status.

        Corresponds to GET /groups/party.

        Returns:
            Dict[str, Any]: A dictionary containing party information. Returns empty dict `{}`
                            on unexpected non-dict response.

        Raises:
            requests.exceptions.RequestException: For network or API errors (e.g., user not in a party).
            ValueError: For invalid JSON responses.
        """
        result = self.get("/groups/party")
        if isinstance(result, dict):
            return result
        print(
            f"Warning: Expected dict from GET /groups/party, got {type(result)}. Returning empty dict."
        )
        return {}

    def get_quest_status(self) -> bool:
        """
        Checks if the user's party is currently participating in an active quest.

        Uses `get_party_data` to check the 'quest.active' field.

        Returns:
            bool: True if the party is on an active quest, False otherwise (including
                  if not in a party or if an error occurs fetching party data).
        """
        try:
            party_data = self.get_party_data()
            # Safely access nested keys
            return party_data.get("quest", {}).get("active", False) is True
        except requests.exceptions.RequestException as e:
            print(f"Could not get party data for quest status: {e}")
            return False
        except ValueError as e:
            print(f"Invalid data received for party data: {e}")
            return False

    # ─── Inbox Methods ────────────────────────────────────────────────────────────

    def get_inbox_messages(self, page: int = 0) -> List[Dict[str, Any]]:
        """
        Gets inbox messages (private messages), paginated.

        Corresponds to GET /inbox/messages.

        Args:
            page (int): The page number to retrieve (0-based). Defaults to 0.

        Returns:
            List[Dict[str, Any]]: A list of message objects for the requested page.
                                  Returns empty list `[]` on unexpected response types.

        Raises:
            requests.exceptions.RequestException: For network or API errors.
            ValueError: For invalid JSON responses.
        """
        result = self.get(f"/inbox/messages?page={page}")
        # API might return { data: [...] } or just [...]
        if isinstance(result, dict) and isinstance(result.get("data"), list):
            # Habitica API sometimes wraps list results in { data: [...] }
            return result["data"]
        elif isinstance(result, list):
            return result  # Direct list response
        else:
            print(
                f"Warning: Expected list or dict containing list from /inbox/messages, "
                f"got {type(result)}. Returning empty list."
            )
            return []


# ─── End Of Habiticaapi Class ─────────────────────────────────────────────────
